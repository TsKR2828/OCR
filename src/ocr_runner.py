"""OCR Runner — 包裝 OCR-Tool 的 headless 模式，輸出帶時間戳的 Segment."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

import cv2
import imagehash
from PIL import Image

from .schema import OcrData, Segment, Events, MergeInfo


# ---------------------------------------------------------------------------
# OCR engine (lazy-load MangaOCR，和 OCR-Tool 相同的 singleton 模式)
# ---------------------------------------------------------------------------

_mocr = None


def _get_ocr():
    global _mocr
    if _mocr is None:
        from manga_ocr import MangaOcr
        print("[OCR] 載入 MangaOCR 模型...")
        _mocr = MangaOcr()
        print("[OCR] 模型載入完成")
    return _mocr


def _ocr_image(pil_image: Image.Image) -> str:
    if pil_image is None:
        return ""
    w, h = pil_image.size
    if w < 4 or h < 4:
        return ""
    return _get_ocr()(pil_image).strip()


# ---------------------------------------------------------------------------
# ROI 裁切（和 OCR-Tool 相同）
# ---------------------------------------------------------------------------

def _crop_roi(pil_img: Image.Image, roi: dict) -> Image.Image:
    w, h = pil_img.size
    x1 = int(roi["x1_norm"] * w)
    y1 = int(roi["y1_norm"] * h)
    x2 = int(roi["x2_norm"] * w)
    y2 = int(roi["y2_norm"] * h)
    return pil_img.crop((x1, y1, x2, y2))


# ---------------------------------------------------------------------------
# 影片逐幀 OCR（從 OCR-Tool video_processor.py 移植，加上精確時間戳）
# ---------------------------------------------------------------------------

def _process_video_headless(
    video_path: Path,
    rois: dict,
    sample_interval_sec: float = 0.5,
    stable_threshold: int = 2,
    hash_diff_threshold: int = 4,
) -> list[dict]:
    """逐幀 OCR，回傳帶 frame_time 的 raw 結果列表."""
    if "dialogue" not in rois:
        raise ValueError("dialogue ROI 必須設定")

    cap = cv2.VideoCapture(str(video_path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
    sample_step = max(1, int(fps * sample_interval_sec))

    results = []
    prev_dialogue_hash = None
    prev_dialogue_text = None
    stable_count = 0
    pending_pil = None
    pending_frame_idx = 0
    frame_idx = 0

    print(f"[OCR] 開始處理影片 ({total_frames} 幀, fps={fps:.1f})")

    while True:
        ret, frame_bgr = cap.read()
        if not ret:
            break
        if frame_idx % sample_step != 0:
            frame_idx += 1
            continue

        if frame_idx % (sample_step * 50) == 0:
            pct = frame_idx / total_frames * 100
            print(f"[OCR] 進度 {pct:.0f}% ({frame_idx}/{total_frames})")

        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        pil = Image.fromarray(frame_rgb)
        d_crop = _crop_roi(pil, rois["dialogue"])
        h = imagehash.phash(d_crop)

        if prev_dialogue_hash is None or abs(h - prev_dialogue_hash) > hash_diff_threshold:
            prev_dialogue_hash = h
            stable_count = 1
            pending_pil = pil
            pending_frame_idx = frame_idx
        else:
            stable_count += 1

        if stable_count == stable_threshold and pending_pil is not None:
            d_text = _ocr_image(_crop_roi(pending_pil, rois["dialogue"]))
            if d_text:
                if (prev_dialogue_text
                        and d_text.startswith(prev_dialogue_text)
                        and d_text != prev_dialogue_text):
                    # 漸進式文字揭露 → 更新最後一筆
                    if results and results[-1]["dialogue"] == prev_dialogue_text:
                        results[-1]["dialogue"] = d_text
                        prev_dialogue_text = d_text
                elif d_text != prev_dialogue_text:
                    name = ""
                    if "name" in rois:
                        name = _ocr_image(_crop_roi(pending_pil, rois["name"]))
                    chapter = ""
                    if "chapter" in rois:
                        chapter = _ocr_image(_crop_roi(pending_pil, rois["chapter"]))

                    results.append({
                        "chapter": chapter,
                        "name": name or "",
                        "dialogue": d_text,
                        "frame_time": pending_frame_idx / fps,
                        "frame_index": pending_frame_idx,
                    })
                    prev_dialogue_text = d_text
            pending_pil = None

        frame_idx += 1

    cap.release()
    print(f"[OCR] 完成：{len(results)} 段對白")
    return results


# ---------------------------------------------------------------------------
# OCR Segment Duration 規則
# ---------------------------------------------------------------------------

def _apply_duration_rules(
    raw: list[dict],
    default_duration_sec: float = 4.0,
    max_dialogue_duration_sec: float = 12.0,
) -> list[dict]:
    """把逐幀 OCR 結果轉成有 time_start / time_end 的段落.

    規則（來自 ROADMAP）：
    1. time_start = 第一次偵測到該文字框的 timestamp
    2. time_end = 下一個不同文字框出現前一刻（優先）
    3. 超過 max_dialogue_duration_sec → 強制以 default_duration_sec 截斷
    4. 尾段 → 使用 default_duration_sec
    """
    if not raw:
        return []

    for i, r in enumerate(raw):
        r["time_start"] = r["frame_time"]

        if i + 1 < len(raw):
            next_start = raw[i + 1]["frame_time"]
            duration = next_start - r["frame_time"]
            if duration > max_dialogue_duration_sec:
                r["time_end"] = r["frame_time"] + default_duration_sec
            else:
                r["time_end"] = next_start
        else:
            r["time_end"] = r["frame_time"] + default_duration_sec

    return raw


# ---------------------------------------------------------------------------
# config.json 載入（OCR-Tool 的 ROI 校準結果）
# ---------------------------------------------------------------------------

def _load_ocr_config(config_path: Path) -> dict:
    if not config_path.exists():
        return {}
    data = json.loads(config_path.read_text(encoding="utf-8"))
    return data.get("rois", {})


# ---------------------------------------------------------------------------
# 公開 API
# ---------------------------------------------------------------------------

def run_ocr(
    video_path: Path,
    config: dict,
    output_dir: Path,
    ocr_config_path: Optional[Path] = None,
) -> list[Segment]:
    """執行完整 OCR 管線，回傳 Segment 列表."""
    ocr_cfg = config.get("ocr", {})
    sample_interval = ocr_cfg.get("sample_interval_sec", 0.5)
    stable_threshold = ocr_cfg.get("stable_threshold", 2)
    hash_diff = ocr_cfg.get("hash_diff_threshold", 4)
    default_dur = ocr_cfg.get("default_duration_sec", 4.0)
    max_dur = ocr_cfg.get("max_dialogue_duration_sec", 12.0)

    # 載入 ROI 設定
    if ocr_config_path is None:
        # 嘗試預設位置
        candidates = [
            output_dir / "ocr_config.json",
            Path("config/ocr_config.json"),
        ]
        for c in candidates:
            if c.exists():
                ocr_config_path = c
                break

    if ocr_config_path is None or not ocr_config_path.exists():
        print("[OCR] 找不到 ROI 設定檔 (config.json)，需要先校準")
        print("      請執行 OCR-Tool 的 calibrate 功能產出 config.json")
        print("      然後用 --ocr-config 指定路徑")
        return []

    rois = _load_ocr_config(ocr_config_path)
    if "dialogue" not in rois:
        print("[OCR] ROI 設定缺少 dialogue 區域，跳過 OCR")
        return []

    print(f"[OCR] ROI 設定: {list(rois.keys())}")

    # 檢查快取
    cache_path = output_dir / "ocr_cache.json"
    if cache_path.exists():
        raw = json.loads(cache_path.read_text(encoding="utf-8"))
        print(f"[OCR] 沿用快取 ({len(raw)} 段)")
    else:
        raw = _process_video_headless(
            video_path, rois,
            sample_interval_sec=sample_interval,
            stable_threshold=stable_threshold,
            hash_diff_threshold=hash_diff,
        )
        # 快取
        cache_path.write_text(
            json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"[OCR] 快取 → {cache_path}")

    # 套用 Duration 規則
    raw = _apply_duration_rules(raw, default_dur, max_dur)

    # 轉成 Segment
    characters_cfg = config.get("characters", [])
    known_names = set()
    for ch in characters_cfg:
        known_names.add(ch.get("name", ""))
        for alias in ch.get("aliases", []):
            known_names.add(alias)

    seen_chapters = set()
    seen_characters = set()
    segments: list[Segment] = []

    for r in raw:
        chapter = r.get("chapter", "")
        character = r.get("name", "")
        dialogue = r.get("dialogue", "")

        events = Events()
        if chapter and chapter not in seen_chapters:
            events.chapter_change = True
            seen_chapters.add(chapter)
        if character and character not in seen_characters:
            events.new_character = True
            seen_characters.add(character)

        # 偵測選択肢、CG 等事件關鍵字
        story_kw = config.get("keywords", {}).get("story", [])
        for kw in story_kw:
            if kw in dialogue:
                if "選択" in kw or "分岐" in kw:
                    events.choice_point = True
                if "CG" in kw:
                    events.cg_unlock = True
                break

        seg = Segment(
            time_start=r["time_start"],
            time_end=r["time_end"],
            ocr=OcrData(
                chapter=chapter or None,
                character=character or None,
                dialogue=dialogue,
                confidence=0.9,
                source_frame=r.get("frame_index"),
            ),
            events=events,
            merge=MergeInfo(source_type="ocr_only", match_status="unverified"),
        )
        segments.append(seg)

    print(f"[OCR] 產出 {len(segments)} 段 Segment")
    return segments
