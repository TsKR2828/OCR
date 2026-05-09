"""Markers Renderer — EDL 剪輯標記 + YouTube 章節（移植自 StreamClip-Tool）."""

from __future__ import annotations

from pathlib import Path

from ..schema import Segment, fmt_ts


def _smpte_tc(seconds: float, fps: int = 30) -> str:
    """秒 → SMPTE timecode HH:MM:SS:FF."""
    total_frames = int(round(seconds * fps))
    ff = total_frames % fps
    total_sec = total_frames // fps
    ss = total_sec % 60
    total_sec //= 60
    mm = total_sec % 60
    hh = total_sec // 60
    return f"{hh:02d}:{mm:02d}:{ss:02d}:{ff:02d}"


def render_edl(
    clip_results: list[dict],
    output_path: Path,
    title: str = "",
    fps: int = 30,
) -> None:
    """產出 CMX 3600 EDL 檔案（Premiere / DaVinci Resolve / FCPX 可匯入）."""
    lines = [
        f"TITLE: {title or 'VN-Transcribe Highlights'}",
        "FCM: NON-DROP FRAME",
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
