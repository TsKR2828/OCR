"""Markers Renderer — EDL 剪輯標記 + YouTube 章節（移植自 StreamClip-Tool）."""

from __future__ import annotations

import math
from pathlib import Path

from ..schema import Segment, fmt_ts


def _drop_frame_spec(fps: float) -> tuple[int, int] | None:
    """回傳 (名目 fps, 每分鐘丟棄編號數)，非 DF rate 則回傳 None."""
    if math.isclose(fps, 30000 / 1001, abs_tol=0.001):
        return 30, 2
    if math.isclose(fps, 60000 / 1001, abs_tol=0.001):
        return 60, 4
    return None


def _smpte_tc(seconds: float, fps: float = 30.0) -> str:
    """秒 → SMPTE timecode；29.97/59.94 使用 Drop-Frame."""
    total_frames = int(round(seconds * fps))
    drop_spec = _drop_frame_spec(fps)
    nominal_fps = drop_spec[0] if drop_spec else int(round(fps))

    if drop_spec:
        _, drop_frames = drop_spec
        frames_per_minute = nominal_fps * 60 - drop_frames
        frames_per_10_minutes = nominal_fps * 600 - drop_frames * 9
        ten_minute_blocks, remainder = divmod(total_frames, frames_per_10_minutes)
        dropped_labels = drop_frames * 9 * ten_minute_blocks
        if remainder > drop_frames:
            dropped_labels += drop_frames * (
                (remainder - drop_frames) // frames_per_minute
            )
        total_frames += dropped_labels

    ff = total_frames % nominal_fps
    total_sec = total_frames // nominal_fps
    ss = total_sec % 60
    total_sec //= 60
    mm = total_sec % 60
    hh = total_sec // 60
    frame_separator = ";" if drop_spec else ":"
    return f"{hh:02d}:{mm:02d}:{ss:02d}{frame_separator}{ff:02d}"


def render_edl(
    clip_results: list[dict],
    output_path: Path,
    title: str = "",
    fps: float = 30.0,
) -> None:
    """產出 CMX 3600 EDL 檔案（Premiere / DaVinci Resolve / FCPX 可匯入）."""
    frame_count_mode = "DROP FRAME" if _drop_frame_spec(fps) else "NON-DROP FRAME"
    lines = [
        f"TITLE: {title or 'VN-Transcribe Highlights'}",
        f"FCM: {frame_count_mode}",
        "",
    ]

    by_time = sorted(clip_results, key=lambda c: c["time_start"])

    for i, clip in enumerate(by_time, 1):
        src_in = _smpte_tc(clip["time_start"], fps)
        src_out = _smpte_tc(clip["time_end"], fps)
        label = f"Clip #{clip['index']} (score: {clip['score']:.0f})"
        lines.append(
            f"{i:03d}  001      V     C        "
            f"{src_in} {src_out} {src_in} {src_out}"
        )
        lines.append(f"* FROM CLIP NAME: {label}")
        lines.append("")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"[Markers] EDL → {output_path} ({len(by_time)} 段)")


def render_mpv_chapters(
    segments: list[Segment],
    output_path: Path,
) -> None:
    """產出 MPV chapter file（.chapters 格式）."""
    chapters = []
    last_chapter = None

    for seg in segments:
        if seg.ocr and seg.ocr.chapter and seg.ocr.chapter != last_chapter:
            last_chapter = seg.ocr.chapter
            chapters.append((seg.time_start, seg.ocr.chapter))

    if not chapters:
        return

    lines = []
    for ts, name in chapters:
        total_ms = int(round(ts * 1000))
        ms = total_ms % 1000
        total_ms //= 1000
        s = total_ms % 60
        total_ms //= 60
        m = total_ms % 60
        h = total_ms // 60
        lines.append(f"{h:02d}:{m:02d}:{s:02d}.{ms:03d} {name}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"[Markers] MPV chapters → {output_path} ({len(chapters)} 章)")
