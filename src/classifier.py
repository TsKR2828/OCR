"""Classifier — 規則式場景自動分類（Phase 3）."""

from __future__ import annotations

from .schema import Segment


# scene_type 定義：
#   dialogue    — OCR 有角色名 + 對白
#   narration   — OCR 有文字但無角色名（旁白、系統提示）
#   choice      — 選択肢出現
#   transition  — 章節轉場 / 長時間無文字
#   reaction    — 無遊戲文字 + ASR 有實況主語音
#   silence     — 兩側都無內容
#   unknown     — 無法判定


def classify_segment(seg: Segment) -> str:
    """根據 segment 內容判斷 scene_type."""

    has_ocr_dialogue = bool(seg.ocr and seg.ocr.dialogue)
    has_ocr_character = bool(seg.ocr and seg.ocr.character)
    has_asr = bool(seg.asr and seg.asr.text)
    is_streamer = has_asr and seg.asr.speaker_guess in ("streamer", "mixed")

    # 選択肢最優先（events 標記或 OCR 偵測到）
    if seg.events.choice_point:
        return "choice"

    # 章節轉場
    if seg.events.chapter_change and not has_ocr_dialogue:
        return "transition"

    # OCR 有角色名 + 對白 → dialogue
    if has_ocr_dialogue and has_ocr_character:
        return "dialogue"

    # OCR 有文字但沒角色名 → narration
    if has_ocr_dialogue and not has_ocr_character:
        return "narration"

    # 無遊戲文字 + 有實況主語音 → reaction
    if not has_ocr_dialogue and is_streamer:
        return "reaction"

    # 有 game_voice ASR 但沒 OCR（可能過場語音）
    if has_asr and not has_ocr_dialogue:
        if seg.asr.speaker_guess == "game_voice":
            return "narration"
        return "reaction"

    # 什麼都沒有
    if not has_ocr_dialogue and not has_asr:
        # 有 chat spike → 可能是觀眾反應的靜默段
        if seg.events.chat_spike:
            return "reaction"
        return "silence"

    return "unknown"


def classify_all(segments: list[Segment]) -> list[Segment]:
    """對所有 segments 執行場景分類，直接寫入 scene_type 欄位.

    回傳同一個 list（in-place 修改）。
    """
    counts: dict[str, int] = {}

    for seg in segments:
        st = classify_segment(seg)
        seg.scene_type = st
        counts[st] = counts.get(st, 0) + 1

    total = len(segments)
    parts = [f"{k}: {v}" for k, v in sorted(counts.items(), key=lambda x: -x[1])]
    print(f"[Classifier] {total} 段分類完成 — {', '.join(parts)}")

    return segments
