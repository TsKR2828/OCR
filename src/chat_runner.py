"""Chat Log Runner — YouTube Data API v3 chat replay 拉取 + 聚合."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from .schema import ChatData, ChatMessage


def _build_youtube_service(api_key: str):
    from googleapiclient.discovery import build
    return build("youtube", "v3", developerKey=api_key)


def _get_live_chat_id(youtube, video_id: str) -> Optional[str]:
    resp = youtube.videos().list(
        part="liveStreamingDetails",
        id=video_id,
    ).execute()

    items = resp.get("items", [])
    if not items:
        print(f"[Chat] 找不到影片 {video_id}")
        return None

    details = items[0].get("liveStreamingDetails", {})
    chat_id = details.get("activeLiveChatId")
    if not chat_id:
        print(f"[Chat] 影片 {video_id} 沒有 chat replay")
        return None
    return chat_id


def _fetch_all_messages(youtube, live_chat_id: str) -> list[dict]:
    messages = []
    page_token = None

    while True:
        kwargs = {
            "liveChatId": live_chat_id,
            "part": "snippet,authorDetails",
            "maxResults": 2000,
        }
        if page_token:
            kwargs["pageToken"] = page_token

        resp = youtube.liveChatMessages().list(**kwargs).execute()

        for item in resp.get("items", []):
            snippet = item.get("snippet", {})
            author = item.get("authorDetails", {})

            msg = {
                "author": author.get("displayName", ""),
                "text": snippet.get("displayMessage", ""),
                "timestamp_ms": snippet.get("publishedAt", ""),
                "type": "normal",
                "amount": None,
            }

            msg_type = snippet.get("type", "")
            if msg_type == "superChatEvent":
                sc = snippet.get("superChatDetails", {})
                msg["type"] = "superchat"
                msg["amount"] = sc.get("amountDisplayString", "")
            elif msg_type == "superStickerEvent":
                ss = snippet.get("superStickerDetails", {})
                msg["type"] = "super_sticker"
                msg["amount"] = ss.get("amountDisplayString", "")

            messages.append(msg)

        page_token = resp.get("nextPageToken")
        if not page_token:
            break

    print(f"[Chat] 拉到 {len(messages)} 則訊息")
    return messages


def _parse_offset_ms(published_at: str, stream_start_ms: float) -> float:
    from datetime import datetime, timezone
    if not published_at:
        return 0.0
    try:
        dt = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
        return (dt.timestamp() * 1000 - stream_start_ms) / 1000.0
    except Exception:
        return 0.0


def _get_stream_start_time(youtube, video_id: str) -> Optional[float]:
    resp = youtube.videos().list(
        part="liveStreamingDetails",
        id=video_id,
    ).execute()
    items = resp.get("items", [])
    if not items:
        return None
    details = items[0].get("liveStreamingDetails", {})
    start_str = details.get("actualStartTime")
    if not start_str:
        return None
    from datetime import datetime
    dt = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
    return dt.timestamp() * 1000


def aggregate_chat(
    messages: list[dict],
    stream_start_ms: float,
    window_sec: float,
    total_duration_sec: float,
    max_per_segment: int,
    spike_threshold: float,
    reaction_keywords: list[str],
) -> list[dict]:
    for msg in messages:
        msg["offset_sec"] = _parse_offset_ms(msg["timestamp_ms"], stream_start_ms)

    messages.sort(key=lambda m: m["offset_sec"])

    n_windows = max(1, int(total_duration_sec / window_sec) + 1)
    windows: list[list[dict]] = [[] for _ in range(n_windows)]

    for msg in messages:
        idx = int(msg["offset_sec"] / window_sec)
        if 0 <= idx < n_windows:
            windows[idx].append(msg)

    total_msgs = sum(len(w) for w in windows)
    total_mins = total_duration_sec / 60.0
    baseline = total_msgs / total_mins if total_mins > 0 else 0.0

    results = []
    for i, w_msgs in enumerate(windows):
        if not w_msgs:
            results.append(None)
            continue

        count = len(w_msgs)
        window_mins = window_sec / 60.0
        density = count / window_mins if window_mins > 0 else 0.0
        is_spike = density > baseline * spike_threshold

        superchats = [m for m in w_msgs if m["type"] in ("superchat", "super_sticker")]
        sc_count = len(superchats)

        kept: list[dict] = []
        kept.extend(superchats)
        remaining = [m for m in w_msgs if m not in superchats]
        kw_matches = [m for m in remaining if any(kw in m["text"] for kw in reaction_keywords)]
        kept.extend(kw_matches[:max_per_segment])
        slots_left = max_per_segment - len(kept)
        if slots_left > 0:
            others = [m for m in remaining if m not in kw_matches]
            kept.extend(others[:slots_left])

        results.append({
            "message_count": count,
            "superchat_count": sc_count,
            "density_per_min": round(density, 1),
            "baseline_per_min": round(baseline, 1),
            "is_spike": is_spike,
            "messages": [
                {"author": m["author"], "text": m["text"], "type": m["type"], "amount": m["amount"]}
                for m in kept
            ],
            "time_start": i * window_sec,
            "time_end": (i + 1) * window_sec,
        })

    return results


def run_chat(video_id: Optional[str], config: dict, output_dir: Path,
             total_duration_sec: float = 0.0) -> list[dict]:
    """執行 Chat Log 管線，回傳按時間窗口聚合的 chat 資料列表.

    回傳格式：list of (dict | None)，index 對應時間窗口。
    None 表示該窗口無訊息。
    """
    chat_cfg = config.get("chat", {})

    if not chat_cfg.get("enabled", True):
        print("[Chat] chat.enabled = false，跳過")
        return []

    if not video_id:
        video_id = chat_cfg.get("video_id")

    if not video_id:
        print("[Chat] 無 video_id，跳過 Chat Log")
        return []

    import os
    api_key = os.environ.get("YOUTUBE_API_KEY", "")
    if not api_key:
        env_path = Path(".env")
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                if line.startswith("YOUTUBE_API_KEY="):
                    api_key = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break

    if not api_key:
        print("[Chat] 未設定 YOUTUBE_API_KEY，跳過 Chat Log")
        return []

    cache_path = output_dir / "chat_cache.json"
    if cache_path.exists():
        raw = json.loads(cache_path.read_text(encoding="utf-8"))
        print(f"[Chat] 沿用快取 ({len(raw)} 則)")
    else:
        try:
            youtube = _build_youtube_service(api_key)
            live_chat_id = _get_live_chat_id(youtube, video_id)
            if not live_chat_id:
                return []
            stream_start_ms = _get_stream_start_time(youtube, video_id)
            if stream_start_ms is None:
                print("[Chat] 無法取得直播開始時間")
                return []
            raw = _fetch_all_messages(youtube, live_chat_id)
            cache_path.write_text(
                json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            print(f"[Chat] 快取 → {cache_path}")
        except Exception as e:
            print(f"[Chat] API 錯誤: {e}")
            return []

    if not raw:
        return []

    window_sec = chat_cfg.get("aggregate_window_sec", 10.0)
    spike_threshold = chat_cfg.get("spike_threshold", 2.5)
    max_per_seg = chat_cfg.get("max_messages_per_segment", 5)
    reaction_kw = config.get("keywords", {}).get("reaction", [])

    import os as _os
    api_key_for_start = _os.environ.get("YOUTUBE_API_KEY", api_key)
    stream_start_ms = None
    if cache_path.exists():
        if raw and "timestamp_ms" in raw[0]:
            from datetime import datetime
            first_ts = raw[0].get("timestamp_ms", "")
            if first_ts:
                try:
                    dt = datetime.fromisoformat(first_ts.replace("Z", "+00:00"))
                    stream_start_ms = dt.timestamp() * 1000
                except Exception:
                    stream_start_ms = 0.0
    if stream_start_ms is None:
        stream_start_ms = 0.0

    aggregated = aggregate_chat(
        messages=raw,
        stream_start_ms=stream_start_ms,
        window_sec=window_sec,
        total_duration_sec=total_duration_sec,
        max_per_segment=max_per_seg,
        spike_threshold=spike_threshold,
        reaction_keywords=reaction_kw,
    )

    spike_count = sum(1 for a in aggregated if a and a["is_spike"])
    print(f"[Chat] {len(raw)} 則訊息 → {len(aggregated)} 窗口, {spike_count} 個 spike")
    return aggregated
