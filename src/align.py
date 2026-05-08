"""Align — 對齊演算法（MVP: ASR+Chat / Phase 1: ASR+Chat+OCR）."""

from __future__ import annotations

from .schema import (
    Segment, OcrData, AsrData, ChatData, ChatMessage,
    Events, Score, ScoreBreakdown, MergeInfo,
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


# ---------------------------------------------------------------------------
# Phase 1: 三層對齊（ASR + Chat + OCR）
# ---------------------------------------------------------------------------

def _compute_overlap(a_start: float, a_end: float, b_start: float, b_end: float) -> float:
    """計算兩個時間段的 overlap ratio（相對於較短段）."""
    overlap_start = max(a_start, b_start)
    overlap_end = min(a_end, b_end)
    overlap = max(0.0, overlap_end - overlap_start)
    min_dur = min(a_end - a_start, b_end - b_start)
    if min_dur <= 0:
        return 0.0
    return overlap / min_dur


def _edit_distance_ratio(a: str, b: str) -> float:
    """計算兩個字串的正規化 edit distance（0=完全相同, 1=完全不同）."""
    if not a and not b:
        return 0.0
    if not a or not b:
        return 1.0
    n, m = len(a), len(b)
    dp = list(range(m + 1))
    for i in range(1, n + 1):
        prev = dp[0]
        dp[0] = i
        for j in range(1, m + 1):
            temp = dp[j]
            if a[i - 1] == b[j - 1]:
                dp[j] = prev
            else:
                dp[j] = 1 + min(prev, dp[j], dp[j - 1])
            prev = temp
    return dp[m] / max(n, m)


def _determine_match_status(
    ocr_text: str,
    asr_text: str,
    speaker_guess: str,
    edit_dist_consistent: float,
    edit_dist_readback: float,
) -> str:
    """判斷 OCR 和 ASR 的 match_status."""
    ratio = _edit_distance_ratio(ocr_text, asr_text)

    if ratio < edit_dist_readback and speaker_guess == "game_voice":
        return "readback_possible"
    if ratio < edit_dist_consistent:
        return "consistent"
    return "conflict"


def merge_ocr_into_timeline(
    asr_chat_segments: list[Segment],
    ocr_segments: list[Segment],
    config: dict,
) -> list[Segment]:
    """把 OCR segments 合併到已有的 ASR+Chat timeline 中.

    策略：
    - overlap > threshold → 配對，合併成 ocr_asr
    - OCR 沒配對到 → 保留為 ocr_only
    - ASR 沒配對到 → 保持原樣（asr_only 或 event_only）
    """
    align_cfg = config.get("alignment", {})
    overlap_threshold = align_cfg.get("overlap_ratio_threshold", 0.3)
    edit_consistent = align_cfg.get("edit_distance_consistent", 0.2)
    edit_readback = align_cfg.get("edit_distance_readback", 0.15)

    # 追蹤哪些 OCR segment 已被配對
    ocr_matched = [False] * len(ocr_segments)

    for asr_seg in asr_chat_segments:
        best_overlap = 0.0
        best_ocr_idx = -1

        for i, ocr_seg in enumerate(ocr_segments):
            if ocr_matched[i]:
                continue
            overlap = _compute_overlap(
                asr_seg.time_start, asr_seg.time_end,
                ocr_seg.time_start, ocr_seg.time_end,
            )
            if overlap > best_overlap:
                best_overlap = overlap
                best_ocr_idx = i

        if best_overlap >= overlap_threshold and best_ocr_idx >= 0:
            ocr_seg = ocr_segments[best_ocr_idx]
            ocr_matched[best_ocr_idx] = True

            # 合併 OCR 資料到 ASR segment
            asr_seg.ocr = ocr_seg.ocr

            # 繼承 OCR 偵測到的事件
            if ocr_seg.events.chapter_change:
                asr_seg.events.chapter_change = True
            if ocr_seg.events.new_character:
                asr_seg.events.new_character = True
            if ocr_seg.events.choice_point:
                asr_seg.events.choice_point = True
            if ocr_seg.events.cg_unlock:
                asr_seg.events.cg_unlock = True

            # 更新 merge 資訊
            if asr_seg.asr and asr_seg.ocr:
                asr_seg.merge.source_type = "ocr_asr"
                ocr_text = asr_seg.ocr.dialogue or ""
                asr_text = asr_seg.asr.text or ""
                speaker = asr_seg.asr.speaker_guess
                asr_seg.merge.match_status = _determine_match_status(
                    ocr_text, asr_text, speaker, edit_consistent, edit_readback,
                )
                if asr_seg.merge.match_status == "conflict":
                    asr_seg.merge.conflict_note = (
                        f"OCR: {ocr_text[:50]} | ASR: {asr_text[:50]}"
                    )

    # 未配對的 OCR segments 保留為 ocr_only
    unmatched_ocr = []
    for i, ocr_seg in enumerate(ocr_segments):
        if not ocr_matched[i]:
            unmatched_ocr.append(ocr_seg)

    all_segments = asr_chat_segments + unmatched_ocr
    all_segments.sort(key=lambda s: s.time_start)

    matched_count = sum(1 for m in ocr_matched if m)
    print(f"[Align] OCR 整合：{matched_count} 配對, {len(unmatched_ocr)} 未配對 (ocr_only)")
    return all_segments


def align_full(
    asr_segments: list[Segment],
    chat_windows: list[dict | None],
    ocr_segments: list[Segment],
    config: dict,
) -> list[Segment]:
    """Phase 1 完整三層對齊：ASR + Chat + OCR."""
    # Step 1: MVP 對齊（ASR + Chat）
    asr_chat = align_mvp(asr_segments, chat_windows, config)

    # Step 2: 合併 OCR
    if ocr_segments:
        result = merge_ocr_into_timeline(asr_chat, ocr_segments, config)
        print(f"[Align] 三層對齊完成：{len(result)} 總段")
        return result
    else:
        return asr_chat
