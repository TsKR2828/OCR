"""yt-dlp Chat Replay Runner — 免 YouTube API key 取得直播聊天室回放.

yt-dlp 用 `--write-subs --sub-langs live_chat` 會把聊天室回放存成
`<name>.live_chat.json`，內容是 JSONL（每行一個 replayChatItemAction）。
每則訊息自帶 `videoOffsetTimeMsec`（相對影片開頭的毫秒），直接對齊影片時間，
不需要像 Data API 那樣回推 stream_start。

對外提供：
- download_live_chat(url, out_dir)  → 下載並回傳 .live_chat.json 路徑
- parse_live_chat(json_path)        → 解析成 messages（含 offset_sec）
- run_chat_ytdlp(url_or_path, config, out_dir, total_duration_sec)
                                    → 下載/解析/聚合，回傳與 run_chat 相同的窗口列表
"""

from __future__ import annotations

import json
import shutil
import subprocess
from collections import Counter
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import Iterator, Optional

from .chat_runner import aggregate_chat


_CHAT_STAGE_REPORT: ContextVar[Optional[dict]] = ContextVar(
    "chat_ytdlp_stage_report", default=None
)
_CHAT_PARTIAL_REASON: ContextVar[Optional[str]] = ContextVar(
    "chat_ytdlp_partial_reason", default=None
)


@contextmanager
def chat_stage_report(stage_report: dict) -> Iterator[None]:
    """Bind the pipeline chat report while the yt-dlp backend is running."""
    report_token = _CHAT_STAGE_REPORT.set(stage_report)
    reason_token = _CHAT_PARTIAL_REASON.set(None)
    try:
        yield
    finally:
        partial_reason = _CHAT_PARTIAL_REASON.get()
        if partial_reason and stage_report.get("status") != "failed":
            stage_report.update(status="partial", reason=partial_reason)
        _CHAT_PARTIAL_REASON.reset(reason_token)
        _CHAT_STAGE_REPORT.reset(report_token)


# ---------------------------------------------------------------------------
# 下載
# ---------------------------------------------------------------------------

def download_live_chat(url: str, out_dir: Path) -> Optional[Path]:
    """用 yt-dlp 抓 live_chat 回放（不下載影片），回傳 .live_chat.json 路徑.

    失敗（無 yt-dlp / 非直播 / chat 已關）回傳 None，不丟例外。
    """
    if not shutil.which("yt-dlp"):
        print("[Chat/yt-dlp] 找不到 yt-dlp，跳過")
        return None

    out_dir.mkdir(parents=True, exist_ok=True)
    # 固定輸出檔名，避免標題含特殊字元造成路徑問題
    out_tmpl = str(out_dir / "live_chat.%(ext)s")
    target = out_dir / "live_chat.live_chat.json"

    if target.exists():
        print(f"[Chat/yt-dlp] 沿用既有 {target.name}")
        return target

    cmd = [
        "yt-dlp",
        "--skip-download",
        "--write-subs",
        "--sub-langs", "live_chat",
        "-o", out_tmpl,
        url,
    ]
    try:
        # encoding/errors 明指 utf-8：yt-dlp 輸出含非 ASCII，Windows 預設 cp950
        # 會在 subprocess reader thread 丟 UnicodeDecodeError。
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=600)
    except subprocess.TimeoutExpired:
        print("[Chat/yt-dlp] 下載逾時")
        return None

    if target.exists():
        size_kb = target.stat().st_size / 1024
        print(f"[Chat/yt-dlp] 下載完成 {target.name} ({size_kb:.0f} KB)")
        return target

    # yt-dlp 有時把檔名存成別的 ext；掃一下目錄
    found = list(out_dir.glob("*.live_chat.json"))
    if found:
        print(f"[Chat/yt-dlp] 下載完成 {found[0].name}")
        return found[0]

    err = (proc.stderr or proc.stdout or "").strip().splitlines()
    tail = err[-1] if err else "無 live_chat（可能非直播或 chat 已關）"
    print(f"[Chat/yt-dlp] 未取得 live_chat：{tail}")
    return None


# ---------------------------------------------------------------------------
# 解析
# ---------------------------------------------------------------------------

def _extract_text(message: dict) -> str:
    """從 message.runs 取出文字（含 emoji 以 shortcut 表示）."""
    runs = message.get("runs", [])
    parts: list[str] = []
    for run in runs:
        if "text" in run:
            parts.append(run["text"])
        elif "emoji" in run:
            emoji = run["emoji"]
            shortcuts = emoji.get("shortcuts")
            if shortcuts:
                parts.append(shortcuts[0])
            else:
                # 自訂貼圖無 shortcut，用 emojiId 尾段佔位
                parts.append(emoji.get("emojiId", ""))
    return "".join(parts).strip()


def _simple_text(node: Optional[dict]) -> str:
    """取 {simpleText:...} 或 {runs:[...]} 的純文字."""
    if not node:
        return ""
    if "simpleText" in node:
        return node["simpleText"]
    if "runs" in node:
        return "".join(r.get("text", "") for r in node["runs"])
    return ""


def _parse_renderer(item: dict) -> Optional[dict]:
    """從 addChatItemAction.item 取出一則訊息 dict（不含 offset）.

    回傳 None 表示不是聊天訊息（系統訊息、互動提示等）。
    """
    # 一般文字
    if "liveChatTextMessageRenderer" in item:
        r = item["liveChatTextMessageRenderer"]
        return {
            "author": _simple_text(r.get("authorName")),
            "text": _extract_text(r.get("message", {})),
            "type": "normal",
            "amount": None,
        }
    # Super Chat
    if "liveChatPaidMessageRenderer" in item:
        r = item["liveChatPaidMessageRenderer"]
        return {
            "author": _simple_text(r.get("authorName")),
            "text": _extract_text(r.get("message", {})),
            "type": "superchat",
            "amount": _simple_text(r.get("purchaseAmountText")),
        }
    # Super Sticker
    if "liveChatPaidStickerRenderer" in item:
        r = item["liveChatPaidStickerRenderer"]
        return {
            "author": _simple_text(r.get("authorName")),
            "text": "",
            "type": "super_sticker",
            "amount": _simple_text(r.get("purchaseAmountText")),
        }
    # 會員加入 / 里程碑（當作一般反應訊號保留，type 標記）
    if "liveChatMembershipItemRenderer" in item:
        r = item["liveChatMembershipItemRenderer"]
        text = _simple_text(r.get("headerSubtext")) or _extract_text(r.get("message", {}))
        return {
            "author": _simple_text(r.get("authorName")),
            "text": text,
            "type": "membership",
            "amount": None,
        }
    return None


def _numeric_offset(action: dict) -> tuple[Optional[float], Optional[str]]:
    """取數字時間；保留 yt-dlp 既有毫秒欄位的解析語意."""
    for key in ("videoOffsetTimeMsec", "videoOffsetTimeMsecText"):
        val = action.get(key)
        if val is not None:
            try:
                return int(val) / 1000.0, "video_offset_msec"
            except (ValueError, TypeError):
                pass

    for key in ("time_in_seconds", "timestamp", "time", "offset"):
        val = action.get(key)
        if val is not None and not isinstance(val, bool):
            try:
                return float(val), "numeric_seconds"
            except (ValueError, TypeError):
                pass
    return None, None


def _time_text_offset(action: dict) -> Optional[float]:
    """解析 MM:SS 或 HH:MM:SS 格式的 fallback 時間."""
    value = action.get("time_text")
    if value is None:
        return None
    parts = str(value).strip().split(":")
    if len(parts) not in (2, 3):
        return None
    try:
        numbers = [float(part) for part in parts]
    except (TypeError, ValueError):
        return None
    if any(number < 0 for number in numbers) or numbers[-1] >= 60:
        return None
    if len(numbers) == 2:
        return numbers[0] * 60 + numbers[1]
    if numbers[1] >= 60:
        return None
    return numbers[0] * 3600 + numbers[1] * 60 + numbers[2]


def _resolve_offset(*actions: dict) -> tuple[Optional[float], Optional[str]]:
    """逐則解析時間，所有數字欄位優先於 time_text fallback."""
    for action in actions:
        offset, source = _numeric_offset(action)
        if offset is not None:
            return offset, source
    for action in actions:
        offset = _time_text_offset(action)
        if offset is not None:
            return offset, "time_text"
    return None, None


def _offset_sec(action: dict) -> Optional[float]:
    """從單一 chat action 取影片偏移秒數."""
    return _resolve_offset(action)[0]


def parse_live_chat(json_path: Path, stats: Optional[dict] = None) -> list[dict]:
    """解析 yt-dlp 的 .live_chat.json（JSONL）→ messages 列表.

    每則 message 含：author, text, type, amount, offset_sec, timestamp_ms("")。
    offset_sec 直接來自 videoOffsetTimeMsec，已對齊影片時間。
    """
    messages: list[dict] = []
    skipped = 0
    total_lines = 0
    time_sources: Counter[str] = Counter()

    with open(json_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            total_lines += 1
            try:
                entry = json.loads(line)
            except (json.JSONDecodeError, TypeError):
                skipped += 1
                continue

            replay = entry.get("replayChatItemAction")
            if not replay:
                continue

            parsed_messages: list[dict] = []
            for action in replay.get("actions", []):
                add = action.get("addChatItemAction")
                if not add:
                    continue
                item = add.get("item", {})
                msg = _parse_renderer(item)
                if msg is None:
                    continue
                parsed_messages.append(msg)

            if not parsed_messages:
                continue

            offset, time_source = _resolve_offset(replay, entry)
            if offset is None:
                skipped += 1
                continue

            for msg in parsed_messages:
                msg["offset_sec"] = offset
                msg["timestamp_ms"] = ""  # 占位；aggregate_chat 看 offset_sec
                messages.append(msg)
                time_sources[time_source or "unknown"] += 1

    if skipped:
        print(f"[Chat] 警告：跳過 {skipped} 行無法解析的 chat 記錄")
    print(f"[Chat/yt-dlp] 解析出 {len(messages)} 則訊息")

    if stats is not None:
        stats.update(
            message_count=len(messages),
            skipped_count=skipped,
            line_count=total_lines,
            corruption_rate=(skipped / total_lines if total_lines else 0.0),
            time_sources=dict(sorted(time_sources.items())),
        )
    return messages


# ---------------------------------------------------------------------------
# 管線入口
# ---------------------------------------------------------------------------

def run_chat_ytdlp(
    url_or_path: str,
    config: dict,
    output_dir: Path,
    total_duration_sec: float = 0.0,
    stage_report: Optional[dict] = None,
) -> list[dict]:
    """yt-dlp 路徑的 chat 管線：下載/解析/聚合.

    url_or_path 可以是 YouTube URL（會用 yt-dlp 下載）或既有 .live_chat.json 路徑。
    回傳與 chat_runner.run_chat 相同的窗口列表（list of dict|None）。
    """
    chat_cfg = config.get("chat", {})
    if not chat_cfg.get("enabled", True):
        print("[Chat/yt-dlp] chat.enabled = false，跳過")
        return []

    p = Path(url_or_path)
    if p.exists() and p.suffix == ".json":
        json_path: Optional[Path] = p
    else:
        json_path = download_live_chat(url_or_path, output_dir)

    if not json_path or not json_path.exists():
        return []

    parse_stats: dict = {}
    messages = parse_live_chat(json_path, stats=parse_stats)

    report = stage_report if stage_report is not None else _CHAT_STAGE_REPORT.get()
    if report is not None:
        report.update(
            message_count=parse_stats["message_count"],
            skipped_count=parse_stats["skipped_count"],
            chat_line_count=parse_stats["line_count"],
            corruption_rate=parse_stats["corruption_rate"],
            time_sources=parse_stats["time_sources"],
        )
        if parse_stats["corruption_rate"] > 0.10:
            partial_reason = (
                "yt-dlp chat 損毀率超過 10%："
                f"跳過 {parse_stats['skipped_count']}/{parse_stats['line_count']} 行"
            )
            report.update(status="partial", reason=partial_reason)
            if report is _CHAT_STAGE_REPORT.get():
                _CHAT_PARTIAL_REASON.set(partial_reason)

    if not messages:
        return []

    window_sec = chat_cfg.get("aggregate_window_sec", 10.0)
    spike_threshold = chat_cfg.get("spike_threshold", 2.5)
    max_per_seg = chat_cfg.get("max_messages_per_segment", 5)
    min_spike_msgs = chat_cfg.get("min_spike_messages", 3)
    reaction_kw = config.get("keywords", {}).get("reaction", [])

    # 若沒帶 total_duration（例如只測 chat），用最後一則訊息的 offset 當邊界
    if total_duration_sec <= 0:
        total_duration_sec = max(m["offset_sec"] for m in messages) + window_sec

    aggregated = aggregate_chat(
        messages=messages,
        stream_start_ms=0.0,       # offset_sec 已存在，aggregate_chat 不會重算
        window_sec=window_sec,
        total_duration_sec=total_duration_sec,
        max_per_segment=max_per_seg,
        spike_threshold=spike_threshold,
        reaction_keywords=reaction_kw,
        min_spike_messages=min_spike_msgs,
    )

    spike_count = sum(1 for a in aggregated if a and a["is_spike"])
    print(f"[Chat/yt-dlp] {len(messages)} 則 → {len(aggregated)} 窗口, {spike_count} 個 spike")
    if report is not None:
        report["window_count"] = len(aggregated)
    return aggregated
