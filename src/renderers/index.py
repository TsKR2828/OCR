"""Index Renderer — 從 timeline segments 產出影片導航索引 index.md."""

from __future__ import annotations

from pathlib import Path

from ..schema import Segment, fmt_ts


def _detect_chapter_changes(segments: list[Segment]) -> list[tuple[float, str]]:
    events = []
    last_chapter = None
    for seg in segments:
        if seg.ocr and seg.ocr.chapter and seg.ocr.chapter != last_chapter:
            events.append((seg.time_start, f"章節 | {seg.ocr.chapter}"))
            last_chapter = seg.ocr.chapter
    return events


def _detect_new_characters(segments: list[Segment]) -> list[tuple[float, str]]:
    events = []
    seen = set()
    for seg in segments:
        if seg.ocr and seg.ocr.character and seg.ocr.character not in seen:
            seen.add(seg.ocr.character)
            events.append((seg.time_start, f"新角色 | {seg.ocr.character} 初登場"))
    return events


def _detect_chat_spikes(segments: list[Segment]) -> list[tuple[float, str]]:
    events = []
    for seg in segments:
        if seg.events.chat_spike and seg.chat:
            density = seg.chat.density_per_min
            baseline = seg.chat.baseline_per_min
            sc = seg.chat.superchat_count
            detail = f"訊息爆量 {density:.0f} msgs/min（平均 {baseline:.0f}）"
            if sc > 0:
                detail += f"、SC ×{sc}"
            events.append((seg.time_start, f"聊天室 | {detail}"))
    return events


def _detect_reactions(segments: list[Segment], top_n: int = 10) -> list[tuple[float, str]]:
    scored = [(seg, seg.score.total) for seg in segments if seg.score.total > 0]
    scored.sort(key=lambda x: x[1], reverse=True)

    events = []
    for seg, score in scored[:top_n]:
        text_preview = ""
        if seg.asr:
            text_preview = seg.asr.text[:30]
            if len(seg.asr.text) > 30:
                text_preview += "..."
        events.append((seg.time_start, f"強反應 | {text_preview}（score: {score:.0f}）"))
    return events


def render_index(segments: list[Segment], output_path: Path, title: str = "") -> None:
    all_events: list[tuple[float, str]] = []

    if segments:
        first_asr = next((s for s in segments if s.asr and s.asr.speaker_guess == "streamer"), None)
        if first_asr:
            all_events.append((first_asr.time_start, "開場 | 實況主開場白"))

    all_events.extend(_detect_chapter_changes(segments))
    all_events.extend(_detect_new_characters(segments))
    all_events.extend(_detect_chat_spikes(segments))
    all_events.extend(_detect_reactions(segments, top_n=10))

    all_events.sort(key=lambda x: x[0])

    seen_times: dict[str, bool] = {}
    deduped = []
    for ts, desc in all_events:
        key = f"{fmt_ts(ts)}_{desc.split('|')[0].strip()}"
        if key not in seen_times:
            seen_times[key] = True
            deduped.append((ts, desc))

    header = f"# 影片索引：{title}\n" if title else "# 影片索引\n"
    lines = [
        header,
        f"> 共 {len(deduped)} 個事件\n",
        "| 時間 | 事件 | 內容摘要 |",
        "|------|------|----------|",
    ]

    for ts, desc in deduped:
        parts = desc.split("|", 1)
        event_type = parts[0].strip()
        summary = parts[1].strip() if len(parts) > 1 else ""
        lines.append(f"| {fmt_ts(ts)} | {event_type} | {summary} |")

    lines.append("")

    yt_lines = ["\n## YouTube 章節格式\n", "```"]
    for ts, desc in deduped:
        parts = desc.split("|", 1)
        summary = parts[1].strip() if len(parts) > 1 else parts[0].strip()
        t = fmt_ts(ts)
        if t.startswith("00:"):
            t = t[3:]
        yt_lines.append(f"{t} {summary}")
    yt_lines.append("```\n")
    lines.extend(yt_lines)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"[Index] 寫出 → {output_path} ({len(deduped)} 事件)")
