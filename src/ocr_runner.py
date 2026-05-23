"""OCR Runner — 包裝 OCR-Tool 的 headless 模式，輸出帶時間戳的 Segment."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

import re

import cv2
import imagehash
import numpy as np
from PIL import Image, ImageStat

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


def _upscale(img: np.ndarray, min_width: int = 1024) -> np.ndarray:
    """小裁切放大到至少 min_width（MangaOCR 對小圖辨識率低）."""
    h, w = img.shape[:2]
    if w < min_width:
        scale = min_width / w
        img = cv2.resize(
            img, (int(w * scale), int(h * scale)),
            interpolation=cv2.INTER_LANCZOS4,
        )
    return img


def _preprocess_dialogue(pil_image: Image.Image) -> Image.Image:
    """對白 ROI 前處理：白字(~250) on 半透明暗底.

    策略：高閾值切出純白字 → 反轉成黑字白底 → 放大。
    比 Otsu 更能過濾半透明遮罩後面的背景噪點。
    """
    gray = np.array(pil_image.convert("L"))

    # 1) Bilateral filter 消壓縮 artifact
    denoised = cv2.bilateralFilter(gray, 9, 75, 75)

    # 2) 高閾值二值化 — 只留亮度 > 190 的像素（白字）
    #    半透明遮罩透出的背景 ~100-150，會被濾掉
    _, binary = cv2.threshold(denoised, 190, 255, cv2.THRESH_BINARY)

    # 3) 反轉 → 黑字白底（MangaOCR 偏好格式）
    inverted = cv2.bitwise_not(binary)

    # 4) Morphological close 補筆畫斷裂
    kernel_close = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    cleaned = cv2.morphologyEx(inverted, cv2.MORPH_CLOSE, kernel_close)

    # 5) 放大
    result = _upscale(cleaned)
    return Image.fromarray(cv2.cvtColor(result, cv2.COLOR_GRAY2RGB))


def _preprocess_name(pil_image: Image.Image) -> Image.Image:
    """角色名 ROI 前處理：金字(~150) on 暗底梯形框.

    金字灰度偏中，不能用高閾值（會被切掉）。
    改用 CLAHE + 銳化 + 放大，保留 MangaOCR 自己判斷。
    """
    gray = np.array(pil_image.convert("L"))

    # 1) Bilateral filter 消壓縮 artifact
    denoised = cv2.bilateralFilter(gray, 5, 50, 50)

    # 2) CLAHE 拉對比
    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
    enhanced = clahe.apply(denoised)

    # 3) 銳化文字筆畫
    kernel = np.array([[0, -1, 0],
                       [-1,  5, -1],
                       [0, -1, 0]], dtype=np.float32)
    sharpened = cv2.filter2D(enhanced, -1, kernel)

    # 4) 放大
    result = _upscale(sharpened)
    return Image.fromarray(cv2.cvtColor(result, cv2.COLOR_GRAY2RGB))


def _ocr_image(pil_image: Image.Image, roi_type: str = "dialogue") -> str:
    """OCR 單張裁切圖。roi_type 決定前處理策略: 'dialogue' | 'name' | 'chapter'."""
    if pil_image is None:
        return ""
    w, h = pil_image.size
    if w < 4 or h < 4:
        return ""
    if roi_type == "dialogue":
        processed = _preprocess_dialogue(pil_image)
    else:
        processed = _preprocess_name(pil_image)
    return _get_ocr()(processed).strip()


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
    brightness_mean_min: float = 0,
    brightness_std_min: float = 0,
    dialogue_text_ratio: float = 1.0,
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
    skipped_bright = 0

    use_brightness_gate = brightness_mean_min > 0 or brightness_std_min > 0
    print(f"[OCR] 開始處理影片 ({total_frames} 幀, fps={fps:.1f})")
    if use_brightness_gate:
        print(f"[OCR] Brightness gate: mean>={brightness_mean_min}, std>={brightness_std_min}")

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

        # ── Brightness gate：偵測對白框是否存在 ──
        # 有對白框 = 半透明深色遮罩 + 白字 → 高亮度 + 高對比
        # 無對白框 = 純場景背景 → 低亮度 + 低對比
        if use_brightness_gate:
            d_stat = ImageStat.Stat(d_crop.convert("L"))
            if (d_stat.mean[0] < brightness_mean_min
                    or d_stat.stddev[0] < brightness_std_min):
                skipped_bright += 1
                frame_idx += 1
                continue

        h = imagehash.phash(d_crop)

        if prev_dialogue_hash is None or abs(h - prev_dialogue_hash) > hash_diff_threshold:
            prev_dialogue_hash = h
            stable_count = 1
            pending_pil = pil
            pending_frame_idx = frame_idx
        else:
            stable_count += 1

        if stable_count == stable_threshold and pending_pil is not None:
            d_crop_ocr = _crop_roi(pending_pil, rois["dialogue"])
            # 裁掉右側人物透出噪點 — 只取左側文字區
            if dialogue_text_ratio < 1.0:
                dw, dh = d_crop_ocr.size
                d_crop_ocr = d_crop_ocr.crop((0, 0, int(dw * dialogue_text_ratio), dh))
            d_text = _ocr_image(d_crop_ocr, roi_type="dialogue")
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
                        name = _ocr_image(_crop_roi(pending_pil, rois["name"]), roi_type="name")
                    chapter = ""
                    if "chapter" in rois:
                        chapter = _ocr_image(_crop_roi(pending_pil, rois["chapter"]), roi_type="chapter")

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
    if use_brightness_gate and skipped_bright:
        print(f"[OCR] Brightness gate 過濾 {skipped_bright} 幀（無對白框）")
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
# Name Normalization（OCR 角色名修正）
# ---------------------------------------------------------------------------

# MangaOCR 常在角色名後面黏上尾巴雜訊（．．．、は、、ウォーキング 等）
_TRAILING_NOISE = re.compile(
    r"[．。、，！？\s]+"   # 全形標點 / 空白
    r"|ー?．．．$"          # ー．．．
    r"|は[、。]?$"          # は、
    r"|が[、。]?$"          # が、
    r"|の$"                 # の
)

# 真角色名不會含的句讀／對白標記——用來過濾 name ROI 讀到的對白殘留
_DIALOGUE_PUNCTUATION = re.compile(r"[、。．！？》《〉〈＞＞]")


def _edit_distance(a: str, b: str) -> int:
    """Levenshtein distance（短字串用，不需外部套件）."""
    if len(a) < len(b):
        return _edit_distance(b, a)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a):
        curr = [i + 1]
        for j, cb in enumerate(b):
            curr.append(min(
                prev[j + 1] + 1,
                curr[j] + 1,
                prev[j] + (0 if ca == cb else 1),
            ))
        prev = curr
    return prev[-1]


def _normalize_names(raw: list[dict], name_map: dict[str, str]) -> tuple[int, int, int]:
    """就地修正 raw 中的 name 欄位，回傳 (exact, fuzzy_fixed, unfixed) 計數.

    name_map: alias/name → canonical name 的映射。
    """
    if not name_map:
        return 0, 0, 0

    # 預排序：長名字優先（prefix match 取最長命中）
    sorted_keys = sorted(name_map.keys(), key=len, reverse=True)
    exact = 0
    fixed = 0
    unfixed = 0

    for r in raw:
        name = r.get("name", "")
        if not name:
            continue

        # 1) Exact match
        if name in name_map:
            r["name"] = name_map[name]
            exact += 1
            continue

        # 2) Strip trailing noise → retry exact
        stripped = _TRAILING_NOISE.sub("", name).strip()
        if stripped in name_map:
            r["name"] = name_map[stripped]
            fixed += 1
            continue

        # 3) Prefix match（OCR 名字以已知角色名開頭）
        matched = False
        for kn in sorted_keys:
            if len(kn) >= 2 and name.startswith(kn):
                r["name"] = name_map[kn]
                fixed += 1
                matched = True
                break
        if matched:
            continue

        # 4) Edit distance ≤ 2（救回一字之差，如 羽瀬田→羽瀬山）
        best_dist = 999
        best_key = None
        for kn in sorted_keys:
            if abs(len(kn) - len(stripped)) > 2:
                continue
            d = _edit_distance(stripped, kn)
            if d < best_dist:
                best_dist = d
                best_key = kn
        max_dist = 1 if len(stripped) <= 2 else 2
        if best_key and best_dist <= max_dist:
            r["name"] = name_map[best_key]
            fixed += 1
            continue

        # 5) 含句讀標點 → 不可能是角色名，清掉
        if _DIALOGUE_PUNCTUATION.search(name):
            r["name"] = ""
            fixed += 1
            continue

        unfixed += 1

    return exact, fixed, unfixed


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
    bright_mean = ocr_cfg.get("brightness_mean_min", 0)
    bright_std = ocr_cfg.get("brightness_std_min", 0)
    dial_ratio = ocr_cfg.get("dialogue_text_ratio", 1.0)

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
            brightness_mean_min=bright_mean,
            brightness_std_min=bright_std,
            dialogue_text_ratio=dial_ratio,
        )
        # 快取
        cache_path.write_text(
            json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"[OCR] 快取 → {cache_path}")

    # 轉成 Segment 前先建 alias → canonical 映射
    characters_cfg = config.get("characters", [])
    name_map: dict[str, str] = {}
    for ch in characters_cfg:
        canonical = ch.get("name", "")
        name_map[canonical] = canonical
        for alias in ch.get("aliases", []):
            name_map[alias] = canonical

    # Name normalization：修正 OCR 角色名雜訊 + alias→canonical
    if name_map:
        n_exact, n_fixed, n_unfixed = _normalize_names(raw, name_map)
        print(f"[OCR] Name normalization: {n_exact} exact, {n_fixed} fixed, {n_unfixed} unfixed")

    # 套用 Duration 規則
    raw = _apply_duration_rules(raw, default_dur, max_dur)

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
