"""Stats Renderer — 角色出場統計（Phase 3）."""

from __future__ import annotations

from pathlib import Path
from collections import defaultdict

from ..schema import Segment, fmt_ts


def _format_duration(seconds: float) -> str:
    """秒數 → 簡短格式 (e.g. 12m30s, 1h5m)."""
    if seconds < 60:
        return f"{seconds:.0f}s"
    m = int(seconds // 60)
    s = int(seconds % 60)
    if m < 60:
        return f"{m}m{s:02d}s" if s > 0 else f"{m}m"
    h = m // 60
    m = m % 60
    return f"{h}h{m:02d}m"


def compute_character_stats(segments: list[Segment]) -> list[dict]:
    """計算每個角色的出場統計.

    回傳按台詞數降序排列的 list[dict]：
    {name, line_count, first_appearance, last_appearance, total_duration_sec}
    """
    data: dict[str, dict] = {}

    for seg in segments:
        if not seg.ocr or not seg.ocr.character:
            continue

        name = seg.ocr.character
        dur = seg.time_end - seg.time_start

        if name not in data:
            data[name] = {
                "name": name,
                "line_count": 0,
                "first_appearance": seg.time_start,
                "last_appearance": seg.time_end,
                "total_duration_sec": 0.0,
            }

        d = data[name]
        d["line_count"] += 1
        d["total_duration_sec"] += dur
        if seg.time_start < d["first_appearance"]:
            d["first_appearance"] = seg.time_start
        if seg.time_end > d["last_appearance"]:
            d["last_appearance"] = seg.time_end

    result = sorted(data.values(), key=lambda x: x["line_count"], reverse=True)
    return result


def compute_scene_stats(segments: list[Segment]) -> dict[str, int]:
    """計算場景類型分布."""
    counts: dict[str, int] = defaultdict(int)
    for seg in segments:
        counts[seg.scene_type] += 1
    return dict(sorted(counts.items(), key=lambda x: -x[1]))


def render_stats(
    segments: list[Segment],
    output_path: Path,
    title: str = "",
) -> None:
    """產出統計報告 Markdown."""
    char_stats = compute_character_stats(segments)
    scene_stats = compute_scene_stats(segments)

    header = f"# 統計報告：{title}\n" if title else "# 統計報告\n"
    lines = [header]

    # --- 角色統計 ---
    lines.append("## 角色統計\n")

    if char_stats:
        lines.append("| 角色 | 台詞數 | 首次出場 | 最後出場 | 總時長 |")
        lines.append("|------|--------|----------|----------|--------|")

        for ch in char_stats:
            lines.append(
                f"| {ch['name']} "
                f"| {ch['line_count']} "
                f"| {fmt_ts(ch['first_appearance'])} "
                f"| {fmt_ts(ch['last_appearance'])} "
                f"| {_format_duration(ch['total_duration_sec'])} |"
            )

        total_lines = sum(ch["line_count"] for ch in char_stats)
        lines.append(f"\n> 共 {len(char_stats)} 個角色，{total_lines} 段台詞\n")
    else:
        lines.append("*無角色資料（需要 OCR 層才能偵測角色名）*\n")

    # --- 場景類型分布 ---
    lines.append("## 場景類型分布\n")

    total_segs = len(segments)
    lines.append("| 場景類型 | 數量 | 比例 |")
    lines.append("|----------|------|------|")

    type_labels = {
        "dialogue": "對白",
        "narration": "旁白",
        "choice": "選択肢",
        "transition": "轉場",
        "reaction": "實況主反應",
        "silence": "靜默",
        "unknown": "未分類",
    }

    for scene_type, count in scene_stats.items():
        pct = count / total_segs * 100 if total_segs > 0 else 0
        label = type_labels.get(scene_type, scene_type)
        lines.append(f"| {label} ({scene_type}) | {count} | {pct:.1f}% |")

    lines.append(f"\n> 共 {total_segs} 段\n")

    # --- 時間分布 ---
    if segments:
        total_dur = segments[-1].time_end - segments[0].time_start
        lines.append("## 時間概覽\n")
        lines.append(f"- 總時長：{_format_duration(total_dur)}")
        lines.append(f"- 起始：{fmt_ts(segments[0].time_start)}")
        lines.append(f"- 結束：{fmt_ts(segments[-1].time_end)}")
        lines.append(f"- 段落數：{total_segs}")

        avg_dur = sum(s.time_end - s.time_start for s in segments) / total_segs
        lines.append(f"- 平均段落長度：{avg_dur:.1f} 秒")
        lines.append("")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"[Stats] 寫出 → {output_path}")
