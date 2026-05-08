"""Clipper — 精彩片段自動剪輯（Phase 3，需要 FFmpeg）."""

from __future__ import annotations

import subprocess
import shutil
from pathlib import Path

from .schema import Segment, fmt_ts


def _merge_intervals(
    intervals: list[tuple[float, float]],
    gap_sec: float = 2.0,
) -> list[tuple[float, float]]:
    """合併相鄰或重疊的時間區間."""
    if not intervals:
        return []
    intervals.sort()
    merged = [intervals[0]]
    for start, end in intervals[1:]:
        prev_start, prev_end = merged[-1]
        if start <= prev_end + gap_sec:
            merged[-1] = (prev_start, max(prev_end, end))
        else:
            merged.append((start, end))
    return merged


def select_highlights(
    segments: list[Segment],
    min_score: float = 15.0,
    top_n: int = 30,
) -> list[Segment]:
    """篩選精彩段落：score > min_score，取前 top_n 段."""
    candidates = [s for s in segments if s.score.total >= min_score]
    candidates.sort(key=lambda s: s.score.total, reverse=True)
    return candidates[:top_n]


def extract_clips(
    video_path: Path,
    segments: list[Segment],
    output_dir: Path,
    config: dict,
) -> list[dict]:
    """從影片中截取精彩片段.

    回傳 clip 資訊列表 [{index, time_start, time_end, duration, score, path}, ...]
    """
    if not shutil.which("ffmpeg"):
        print("[Clipper] 找不到 ffmpeg，跳過剪輯")
        print("         請安裝 ffmpeg 並加入 PATH")
        return []

    highlight_cfg = config.get("highlight", {})
    min_score = highlight_cfg.get("min_score", 15)
    top_n = highlight_cfg.get("top_n", 30)
    padding_sec = highlight_cfg.get("clip_padding_sec", 3.0)
    merge_gap_sec = highlight_cfg.get("clip_merge_gap_sec", 2.0)

    highlights = select_highlights(segments, min_score, top_n)
    if not highlights:
        print("[Clipper] 沒有達到門檻的精彩段落，跳過剪輯")
        return []

    # 加 padding 後合併相鄰區間
    intervals = []
    seg_map: dict[int, list[Segment]] = {}  # interval_idx → contributing segments

    for seg in highlights:
        intervals.append((
            max(0.0, seg.time_start - padding_sec),
            seg.time_end + padding_sec,
        ))

    merged = _merge_intervals(intervals, merge_gap_sec)

    # 為每個合併區間找回對應的 segments
    clip_segments: list[list[Segment]] = [[] for _ in merged]
    for seg in highlights:
        padded_start = max(0.0, seg.time_start - padding_sec)
        for i, (m_start, m_end) in enumerate(merged):
            if padded_start >= m_start - merge_gap_sec and seg.time_end <= m_end + merge_gap_sec:
                clip_segments[i].append(seg)
                break

    clips_dir = output_dir / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)

    clip_results = []

    for i, (start, end) in enumerate(merged):
        duration = end - start
        clip_score = max((s.score.total for s in clip_segments[i]), default=0)
        clip_name = f"clip_{i+1:03d}_{fmt_ts(start).replace(':', '')}.mp4"
        clip_path = clips_dir / clip_name

        cmd = [
            "ffmpeg", "-y",
            "-ss", f"{start:.3f}",
            "-i", str(video_path),
            "-t", f"{duration:.3f}",
            "-c", "copy",       # 不重新編碼，秒切
            "-avoid_negative_ts", "make_zero",
            str(clip_path),
        ]

        try:
            subprocess.run(
                cmd,
                capture_output=True,
                timeout=60,
                check=True,
            )
            clip_results.append({
                "index": i + 1,
                "time_start": start,
                "time_end": end,
                "duration": round(duration, 1),
                "score": clip_score,
                "path": str(clip_path),
                "filename": clip_name,
                "segment_count": len(clip_segments[i]),
            })
        except subprocess.CalledProcessError as e:
            print(f"[Clipper] clip {i+1} 失敗: {e.stderr[:200] if e.stderr else 'unknown error'}")
        except subprocess.TimeoutExpired:
            print(f"[Clipper] clip {i+1} 超時")

    print(f"[Clipper] 產出 {len(clip_results)} 個精彩片段 → {clips_dir}")
    return clip_results


def render_clips_index(
    clip_results: list[dict],
    output_path: Path,
    title: str = "",
) -> None:
    """產出 clips_index.md."""
    header = f"# 精彩片段索引：{title}\n" if title else "# 精彩片段索引\n"
    lines = [
        header,
        f"> 共 {len(clip_results)} 個片段\n",
        "| # | 時間範圍 | 長度 | 精彩度 | 檔名 |",
        "|---|----------|------|--------|------|",
    ]

    total_duration = 0.0
    for clip in clip_results:
        ts_start = fmt_ts(clip["time_start"])
        ts_end = fmt_ts(clip["time_end"])
        dur = clip["duration"]
        total_duration += dur
        lines.append(
            f"| {clip['index']} | {ts_start} ~ {ts_end} | {dur:.0f}s | "
            f"{clip['score']:.0f} | `{clip['filename']}` |"
        )

    lines.append("")
    lines.append(f"> 總長 {total_duration:.0f} 秒 ({total_duration/60:.1f} 分鐘)\n")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"[Clipper] 索引 → {output_path}")
