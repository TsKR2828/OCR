"""Timeline Segment Schema — VN-Transcribe 的核心資料結構."""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional


@dataclass
class OcrData:
    chapter: Optional[str] = None
    character: Optional[str] = None
    dialogue: Optional[str] = None
    confidence: float = 0.0
    source_frame: Optional[int] = None


@dataclass
class AsrData:
    text: str = ""
    speaker_guess: str = "unknown"  # streamer | game_voice | mixed | unknown
    language: str = "zh"            # zh | ja | mixed
    confidence: float = 0.0


@dataclass
class ChatMessage:
    author: str = ""
    text: str = ""
    type: str = "normal"            # normal | superchat | super_sticker
    amount: Optional[str] = None    # e.g. "¥500"


@dataclass
class ChatData:
    message_count: int = 0
    messages: list[ChatMessage] = field(default_factory=list)
    superchat_count: int = 0
    density_per_min: float = 0.0
    baseline_per_min: float = 0.0
    is_spike: bool = False


@dataclass
class Events:
    chapter_change: bool = False
    new_character: bool = False
    choice_point: bool = False
    cg_unlock: bool = False
    streamer_reaction: bool = False
    chat_spike: bool = False


@dataclass
class ScoreBreakdown:
    volume_spike: float = 0.0
    laughter: float = 0.0
    keyword_hit: float = 0.0
    streamer_reaction: float = 0.0
    chat_spike: float = 0.0
    silence_then_burst: float = 0.0
    speech_rate_change: float = 0.0
    repeated_word: float = 0.0


@dataclass
class Score:
    total: float = 0.0
    breakdown: ScoreBreakdown = field(default_factory=ScoreBreakdown)


@dataclass
class MergeInfo:
    source_type: str = "asr_only"   # ocr_asr | ocr_only | asr_only | event_only
    match_status: str = "unverified"  # consistent | conflict | readback_possible | unverified | not_applicable
    conflict_note: Optional[str] = None


@dataclass
class Segment:
    time_start: float = 0.0
    time_end: float = 0.0
    time_display: str = ""

    ocr: Optional[OcrData] = None
    asr: Optional[AsrData] = None
    chat: Optional[ChatData] = None

    scene_type: str = "unknown"  # dialogue|narration|choice|transition|reaction|silence|unknown

    events: Events = field(default_factory=Events)
    score: Score = field(default_factory=Score)
    merge: MergeInfo = field(default_factory=MergeInfo)

    def __post_init__(self):
        if not self.time_display and self.time_start >= 0:
            self.time_display = fmt_ts(self.time_start)


def fmt_ts(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def segment_to_dict(seg: Segment) -> dict:
    d = asdict(seg)
    if d["ocr"] is None:
        del d["ocr"]
    if d["asr"] is None:
        del d["asr"]
    if d["chat"] is None:
        del d["chat"]
    return d


def dict_to_segment(d: dict) -> Segment:
    seg = Segment(
        time_start=d["time_start"],
        time_end=d["time_end"],
        time_display=d.get("time_display", ""),
        scene_type=d.get("scene_type", "unknown"),
    )
    if "ocr" in d and d["ocr"] is not None:
        seg.ocr = OcrData(**d["ocr"])
    if "asr" in d and d["asr"] is not None:
        seg.asr = AsrData(**d["asr"])
    if "chat" in d and d["chat"] is not None:
        chat_d = d["chat"].copy()
        msgs = [ChatMessage(**m) for m in chat_d.pop("messages", [])]
        seg.chat = ChatData(messages=msgs, **chat_d)
    if "events" in d:
        seg.events = Events(**d["events"])
    if "score" in d:
        bd = d["score"].get("breakdown", {})
        seg.score = Score(total=d["score"].get("total", 0), breakdown=ScoreBreakdown(**bd))
    if "merge" in d:
        seg.merge = MergeInfo(**d["merge"])
    return seg


def save_timeline(segments: list[Segment], path: Path) -> None:
    data = [segment_to_dict(s) for s in segments]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_timeline(path: Path) -> list[Segment]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return [dict_to_segment(d) for d in data]
