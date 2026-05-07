"""Align — MVP 版對齊演算法（ASR 骨架 + Chat 疊加）."""

from __future__ import annotations

from .schema import (
    Segment, ChatData, ChatMessage, Events, Score, ScoreBreakdown, MergeInfo,
)


def overlay_chat_on_segments(
    segments: list[Segment],
    chat_windows: list[dict | None],
    highlight_weights: dict,
) -> list[Segment]:
    """把 chat 聚合資料疊加到 ASR segments 上.

    chat_windows: chat_runner 回傳的按時間窗口聚合列表，
                  index × window_sec = 時間起點。
    """
    if not chat_windows:
        return segments

    window_sec = 10.0
    if len(chat_windows) >= 2:
        for cw in chat_windows:
            if cw is not None:
                window_sec = cw.get("time_end", 10.0) - cw.get("time_start", 0.0)
                break

    for seg in segments:
        start_idx = int(seg.time_start / window_sec)
        end_idx = int(seg.time_end / window_sec)

        total_count = 0
        total_sc = 0
        all_messages: list[dict] = []
        max_density = 0.0
        baseline = 0.0
        any_spike = False

        for idx in range(start_idx, end_idx + 1):
            if idx < 0 or idx >= len(chat_windows):
                continue
            cw = chat_windows[idx]
            if cw is None:
                continue
            total_count += cw["message_count"]
            total_sc += cw["superchat_count"]
            all_messages.extend(cw["messages"])
            if cw["density_per_min"] > max_density:
                max_density = cw["density_per_min"]
            baseline = cw["baseline_per_min"]
            if cw["is_spike"]:
                any_spike = True

        if total_count == 0:
            continue

        seg.chat = ChatData(
            message_count=total_count,
            messages=[
                ChatMessage(
                    author=m["author"],
                    text=m["text"],
                    type=m["type"],
                    amount=m.get("amount"),
                )
                for m in all_messages[:10]
            ],
            superchat_count=total_sc,
            density_per_min=round(max_density, 1),
            baseline_per_min=round(baseline, 1),
            is_spike=any_spike,
        )

        if any_spike:
            seg.events.chat_spike = True
            spike_score = highlight_weights.get("chat_spike", 25)
            seg.score.breakdown.chat_spike = spike_score
            seg.score.total += spike_score

    return segments


def generate_event_segments(
    chat_windows: list[dict | None],
    existing_segments: list[Segment],
    highlight_weights: dict,
) -> list[Segment]:
    """對於沒有 ASR 覆蓋但有 chat spike 的時間窗口，產生 event_only segment."""
    if not chat_windows:
        return []

    covered = set()
    window_sec = 10.0
    for cw in chat_windows:
        if cw is not None:
            window_sec = cw.get("time_end", 10.0) - cw.get("time_start", 0.0)
            break

    for seg in existing_segments:
        start_idx = int(seg.time_start / window_sec)
        end_idx = int(seg.time_end / window_sec)
        for idx in range(start_idx, end_idx + 1):
            covered.add(idx)

    event_segs = []
    for i, cw in enumerate(chat_windows):
        if cw is None or i in covered or not cw["is_spike"]:
            continue

        spike_score = highlight_weights.get("chat_spike", 25)
        seg = Segment(
            time_start=cw["time_start"],
            time_end=cw["time_end"],
            chat=ChatData(
                message_count=cw["message_count"],
                messages=[
                    ChatMessage(author=m["author"], text=m["text"],
                                type=m["type"], amount=m.get("amount"))
                    for m in cw["messages"][:5]
                ],
                superchat_count=cw["superchat_count"],
                density_per_min=cw["density_per_min"],
                baseline_per_min=cw["baseline_per_min"],
                is_spike=True,
            ),
            events=Events(chat_spike=True),
            score=Score(total=spike_score, breakdown=ScoreBreakdown(chat_spike=spike_score)),
            merge=MergeInfo(source_type="event_only", match_status="not_applicable"),
        )
        event_segs.append(seg)

    return event_segs


def align_mvp(
    asr_segments: list[Segment],
    chat_windows: list[dict | None],
    config: dict,
) -> list[Segment]:
    """MVP 對齊：ASR 為骨架，Chat 疊加，補上 event_only."""
    weights = config.get("highlight", {}).get("weights", {})

    segments = overlay_chat_on_segments(asr_segments, chat_windows, weights)
    event_segs = generate_event_segments(chat_windows, segments, weights)
    all_segments = segments + event_segs
    all_segments.sort(key=lambda s: s.time_start)

    print(f"[Align] {len(asr_segments)} ASR + {len(event_segs)} event_only → {len(all_segments)} 總段")
    return all_segments
