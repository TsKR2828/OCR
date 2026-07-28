"""Subtitle Renderer — 從 timeline segments 產出 SRT 字幕檔."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from ..schema import Segment


def _fmt_srt_time(seconds: float) -> str:
    """秒數 → SRT 時間格式 HH:MM:SS,mmm.

    用整數毫秒運算，避免浮點數導致 ms=1000 的格式錯誤。
    """
    if seconds < 0:
        seconds = 0.0
    total_ms = int(round(seconds * 1000))
    ms = total_ms % 1000
    total_ms //= 1000
    s = total_ms % 60
    total_ms //= 60
    m = total_ms % 60
    h = total_ms // 60
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _srt_block(index: int, start: float, end: float, text: str) -> str:
    """組成一個 SRT 字幕區塊."""
    return (
        f"{index}\n"
        f"{_fmt_srt_time(start)} --> {_fmt_srt_time(end)}\n"
        f"{text}\n"
    )


# ---------------------------------------------------------------------------
# 日文原文軌（OCR 優先，fallback ASR game_voice）
# ---------------------------------------------------------------------------

def _source_priority(seg: Segment) -> int:
    """來源優先級：數字越大越優先."""
    if seg.merge and seg.merge.source_type == "ocr_asr":
        return 3
    if seg.merge and seg.merge.source_type == "ocr_only":
        return 2
    return 1  # asr_only, event_only


def _dedup_overlapping(segments: list[Segment]) -> list[Segment]:
    """去除時間重疊的段落，保留來源優先級高的."""
    if not segments:
        return []
    sorted_segs = sorted(segments, key=lambda s: (s.time_start, -_source_priority(s)))
    result = [sorted_segs[0]]
    for seg in sorted_segs[1:]:
        prev = result[-1]
        overlap_start = max(prev.time_start, seg.time_start)
        overlap_end = min(prev.time_end, seg.time_end)
        overlap = max(0.0, overlap_end - overlap_start)
        seg_dur = seg.time_end - seg.time_start
        if seg_dur <= 0:
            continue
        overlap_ratio = overlap / seg_dur
        if overlap_ratio > 0.5:
            if _source_priority(seg) > _source_priority(prev):
                result[-1] = seg
        else:
            result.append(seg)
    return result


def render_srt_original(
    segments: list[Segment],
    output_path: Path,
    include_character_name: bool = True,
) -> int:
    """產出日文原文 SRT.

    來源優先順序：
    1. OCR dialogue（畫面文字，最準確）
    2. ASR text（speaker_guess == game_voice 的段落）

    回傳字幕數量。
    """
    deduped = _dedup_overlapping(segments)
    blocks: list[str] = []
    idx = 0

    for seg in deduped:
        text = _get_original_text(seg, include_character_name)
        if not text:
            continue

        idx += 1
        blocks.append(_srt_block(idx, seg.time_start, seg.time_end, text))

    _write_srt(blocks, output_path)
    print(f"[SRT] 原文軌 → {output_path} ({idx} 條字幕, 去重前 {len(segments)})")
    return idx


def _get_original_text(seg: Segment, include_name: bool) -> Optional[str]:
    """從 segment 取得日文原文."""
    # 優先用 OCR
    if seg.ocr and seg.ocr.dialogue:
        prefix = ""
        if include_name and seg.ocr.character:
            prefix = f"【{seg.ocr.character}】"
        return f"{prefix}{seg.ocr.dialogue}"

    # Fallback: ASR game_voice
    if seg.asr and seg.asr.speaker_guess == "game_voice" and seg.asr.text:
        return seg.asr.text

    return None


# ---------------------------------------------------------------------------
# 實況主語音軌（ASR streamer / mixed）
# ---------------------------------------------------------------------------

def render_srt_streamer(
    segments: list[Segment],
    output_path: Path,
) -> int:
    """產出實況主語音 SRT.

    只取 speaker_guess == streamer 或 mixed 的 ASR 段落。

    回傳字幕數量。
    """
    deduped = _dedup_overlapping(segments)
    blocks: list[str] = []
    idx = 0

    for seg in deduped:
        if not seg.asr or not seg.asr.text:
            continue
        if seg.asr.speaker_guess not in ("streamer", "mixed"):
            continue

        idx += 1
        blocks.append(_srt_block(idx, seg.time_start, seg.time_end, seg.asr.text))

    _write_srt(blocks, output_path)
    print(f"[SRT] 實況主軌 → {output_path} ({idx} 條字幕)")
    return idx


# ---------------------------------------------------------------------------
# 雙軌合併 SRT（上行原文、下行實況主）
# ---------------------------------------------------------------------------

def render_srt_dual(
    segments: list[Segment],
    output_path: Path,
    include_character_name: bool = True,
) -> int:
    """產出雙軌合併 SRT.

    格式：
      上行 = 日文原文（OCR 或 game_voice ASR）
      下行 = 實況主語音（streamer ASR）

    只有一側有資料時也會輸出（單行）。

    回傳字幕數量。
    """
    deduped = _dedup_overlapping(segments)
    blocks: list[str] = []
    idx = 0

    for seg in deduped:
        original = _get_original_text(seg, include_character_name)
        streamer = None
        if seg.asr and seg.asr.text and seg.asr.speaker_guess in ("streamer", "mixed"):
            streamer = seg.asr.text

        if not original and not streamer:
            continue

        # 組合雙行
        lines = []
        if original:
            lines.append(original)
        if streamer:
            lines.append(streamer)

        idx += 1
        blocks.append(_srt_block(idx, seg.time_start, seg.time_end, "\n".join(lines)))

    _write_srt(blocks, output_path)
    print(f"[SRT] 雙軌合併 → {output_path} ({idx} 條字幕)")
    return idx


# ---------------------------------------------------------------------------
# 共用
# ---------------------------------------------------------------------------

def _write_srt(blocks: list[str], path: Path) -> None:
    """寫出 SRT 檔（UTF-8 with BOM，相容性最好）."""
    path.parent.mkdir(parents=True, exist_ok=True)
    content = "\n".join(blocks)
    # SRT 用 UTF-8 BOM 確保 VLC / MPV / PotPlayer 都能正確讀取日文
    path.write_text(content, encoding="utf-8-sig")


def render_all_srt(
    segments: list[Segment],
    output_dir: Path,
    stem: str = "subtitle",
) -> dict[str, int]:
    """一次產出三種 SRT.

    回傳 {filename: count} 字典。
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    results = {}

    original_path = output_dir / f"{stem}_original.srt"
    results[original_path.name] = render_srt_original(segments, original_path)

    streamer_path = output_dir / f"{stem}_streamer.srt"
    results[streamer_path.name] = render_srt_streamer(segments, streamer_path)

    dual_path = output_dir / f"{stem}_dual.srt"
    results[dual_path.name] = render_srt_dual(segments, dual_path)

    return results
