"""Chat Log Runner — YouTube Data API v3 chat replay 拉取 + 聚合."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional

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


def _cache_meta_path(cache_path: Path) -> Path:
    return cache_path.with_suffix(".meta.json")


def _build_cache_meta(source_path: Path, stage: str, settings: dict) -> dict:
    source = source_path.resolve()
    stat = source.stat()
    return {
        "fingerprint_version": 1,
        "stage": stage,
        "source": {
            "path": str(source),
            "size": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
        },
        "settings": settings,
    }


def _metadata_differences(expected: Any, actual: Any, prefix: str = "") -> list[str]:
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return [f"{prefix or 'metadata'} 型別變了"]
        differences = []
        for key, expected_value in expected.items():
            path = f"{prefix}.{key}" if prefix else key
            if key not in actual:
                differences.append(f"{path} 缺少")
                continue
            differences.extend(
                _metadata_differences(expected_value, actual[key], path)
            )
        for key, actual_value in actual.items():
            if key not in expected:
                path = f"{prefix}.{key}" if prefix else key
                differences.append(f"{path} 已移除（舊={actual_value!r}）")
        return differences
    if expected != actual:
        return [f"{prefix} 變了（舊={actual!r}，新={expected!r}）"]
    return []


def _cache_metadata_valid(cache_path: Path, expected_meta: dict, label: str) -> bool:
    if not cache_path.exists():
        return False
    meta_path = _cache_meta_path(cache_path)
    if not meta_path.exists():
        print(f"[{label}] 快取失效原因：缺少 {meta_path.name}（舊格式快取）")
        return False
    try:
        actual_meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        print(f"[{label}] 快取失效原因：{meta_path.name} JSON 損毀")
        return False
    except OSError as e:
        print(f"[{label}] 快取失效原因：無法讀取 {meta_path.name} ({e})")
        return False

    differences = _metadata_differences(expected_meta, actual_meta)
    for reason in differences:
        print(f"[{label}] 快取失效原因：{reason}")
    return not differences


def _atomic_write_json(path: Path, payload: Any) -> None:
    tmp_path = path.with_name(path.name + ".tmp")
    try:
        tmp_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        os.replace(tmp_path, path)
    finally:
        tmp_path.unlink(missing_ok=True)


def _load_valid_json_cache(
    cache_path: Path, expected_meta: dict, label: str,
) -> Optional[Any]:
    if not _cache_metadata_valid(cache_path, expected_meta, label):
        return None
    try:
        return json.loads(cache_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        print(f"[{label}] 快取失效原因：{cache_path.name} JSON 損毀")
        return None
    except OSError as e:
        print(f"[{label}] 快取失效原因：無法讀取 {cache_path.name} ({e})")
        return None


def _write_json_cache(cache_path: Path, payload: Any, metadata: dict) -> None:
    _atomic_write_json(cache_path, payload)
    _atomic_write_json(_cache_meta_path(cache_path), metadata)


def _load_chat_cache(
    cache_path: Path, expected_meta: dict,
) -> Optional[tuple[list[dict], Optional[float]]]:
    """讀取新舊格式 chat cache，回傳訊息與直播開始時間."""
    cached = _load_valid_json_cache(cache_path, expected_meta, "Chat")
    if cached is None:
        return None
    if isinstance(cached, list):
        return cached, None

    if not isinstance(cached, dict):
        print(f"[Chat] 快取失效原因：{cache_path.name} 格式不正確")
        return None

    if "messages" not in cached:
        print(f"[Chat] 快取失效原因：{cache_path.name} 缺少 messages")
        return None
    raw = cached["messages"]
    if not isinstance(raw, list):
        print(f"[Chat] 快取失效原因：{cache_path.name} messages 格式不正確")
        return None
    metadata = cached.get("metadata")
    if metadata is None:
        metadata = {}
    elif not isinstance(metadata, dict):
        print(f"[Chat] 快取失效原因：{cache_path.name} metadata 格式不正確")
        return None
    stream_start_ms = metadata.get("stream_start_ms")
    try:
        return raw, float(stream_start_ms) if stream_start_ms is not None else None
    except (TypeError, ValueError):
        return raw, None


def _fallback_stream_start_ms(messages: list[dict]) -> float:
    """舊快取沒有 metadata 時，以第一則訊息推算直播開始時間."""
    print(
        "[Chat] 警告：chat 快取缺少 stream_start_ms metadata，"
        "改用第一則訊息時間推算直播零點；時間軸可能不準"
    )
    if messages:
        first_ts = messages[0].get("timestamp_ms", "")
        if first_ts:
            try:
                from datetime import datetime
                dt = datetime.fromisoformat(first_ts.replace("Z", "+00:00"))
                return dt.timestamp() * 1000
            except (TypeError, ValueError):
                pass
    print("[Chat] 警告：第一則訊息時間無法解析，直播零點改用 0；時間軸可能不準")
    return 0.0


def aggregate_chat(
    messages: list[dict],
    stream_start_ms: float,
    window_sec: float,
    total_duration_sec: float,
    max_per_segment: int,
    spike_threshold: float,
    reaction_keywords: list[str],
    min_spike_messages: int = 3,
) -> list[dict]:
    for msg in messages:
        # yt-dlp 來源已自帶 offset_sec（videoOffsetTimeMsec），不重算；
        # 只有 Data API 來源才需要從 timestamp 回推 stream_start。
        if msg.get("offset_sec") is None:
            msg["offset_sec"] = _parse_offset_ms(msg.get("timestamp_ms", ""), stream_start_ms)

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
        # 雙閘門：相對 baseline 爆量 AND 絕對量達門檻。
        # 後者避免稀疏聊天室裡單則訊息被 10s 窗口量化就誤判 spike
        # （baseline 被大量空窗拉低 → 任何非空窗都 > baseline×threshold）。
        is_spike = density > baseline * spike_threshold and count >= min_spike_messages

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
             total_duration_sec: float = 0.0,
             chat_url: Optional[str] = None,
             source_path: Optional[Path] = None,
             stage_report: Optional[dict] = None) -> list[dict]:
    """執行 Chat Log 管線，回傳按時間窗口聚合的 chat 資料列表.

    回傳格式：list of (dict | None)，index 對應時間窗口。
    None 表示該窗口無訊息。

    來源優先序：
    1. yt-dlp live_chat（免 API key）——chat_url 參數 / config chat.live_chat_url /
       output_dir 內既有的 live_chat.live_chat.json。
    2. YouTube Data API v3（需 YOUTUBE_API_KEY）。
    """
    chat_cfg = config.get("chat", {})

    if not chat_cfg.get("enabled", True):
        reason = "chat.enabled = false"
        print(f"[Chat] {reason}，跳過")
        if stage_report is not None:
            stage_report.update(status="skipped", reason=reason)
        return []

    # --- 來源 1：yt-dlp live_chat ---
    yt_source = chat_url or chat_cfg.get("live_chat_url")
    if not yt_source:
        cached = output_dir / "live_chat.live_chat.json"
        if cached.exists():
            yt_source = str(cached)
    yt_attempted = bool(yt_source)
    if yt_source:
        from .chat_ytdlp import run_chat_ytdlp
        yt_path = Path(yt_source)
        yt_cache_hit = yt_path.exists() or (
            output_dir / "live_chat.live_chat.json"
        ).exists()
        result = run_chat_ytdlp(yt_source, config, output_dir, total_duration_sec)
        if result:
            if stage_report is not None:
                artifacts = []
                if yt_path.exists():
                    artifacts.append(str(yt_path.resolve()))
                else:
                    artifacts.extend(
                        str(path.resolve())
                        for path in output_dir.glob("*.live_chat.json")
                    )
                stage_report.update(
                    status="success",
                    cache_hit=yt_cache_hit,
                    artifacts=artifacts,
                    window_count=len(result),
                )
            return result
        print("[Chat] yt-dlp 來源無資料，改試 Data API")

    # --- 來源 2：YouTube Data API ---
    if not video_id:
        video_id = chat_cfg.get("video_id")

    if not video_id:
        if yt_attempted:
            error = "yt-dlp chat 來源無資料，且無 video_id 可供 Data API fallback"
            print(f"[Chat] {error}")
            if stage_report is not None:
                stage_report.update(status="failed", error=error)
        else:
            reason = "無 video_id"
            print(f"[Chat] {reason}，跳過 Chat Log")
            if stage_report is not None:
                stage_report.update(status="skipped", reason=reason)
        return []

    api_key = os.environ.get("YOUTUBE_API_KEY", "")
    if not api_key:
        env_path = Path(".env")
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                if line.startswith("YOUTUBE_API_KEY="):
                    api_key = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break

    if not api_key:
        if yt_attempted:
            error = "yt-dlp chat 來源無資料，且未設定 YOUTUBE_API_KEY"
            print(f"[Chat] {error}")
            if stage_report is not None:
                stage_report.update(status="failed", error=error)
        else:
            reason = "未設定 YOUTUBE_API_KEY"
            print(f"[Chat] {reason}，跳過 Chat Log")
            if stage_report is not None:
                stage_report.update(status="skipped", reason=reason)
        return []

    window_sec = chat_cfg.get("aggregate_window_sec", 10.0)
    spike_threshold = chat_cfg.get("spike_threshold", 2.5)
    max_per_seg = chat_cfg.get("max_messages_per_segment", 5)
    min_spike_msgs = chat_cfg.get("min_spike_messages", 3)
    reaction_kw = config.get("keywords", {}).get("reaction", [])
    chat_settings = {
        "video_id": video_id,
        "aggregate_window_sec": window_sec,
        "spike_threshold": spike_threshold,
        "max_messages_per_segment": max_per_seg,
        "min_spike_messages": min_spike_msgs,
        "include_superchat": chat_cfg.get("include_superchat", True),
        "reaction_keywords": reaction_kw,
    }

    cache_path = output_dir / "chat_cache.json"
    cache_meta = (
        _build_cache_meta(source_path, "chat", chat_settings)
        if source_path is not None
        else None
    )
    stream_start_ms: Optional[float] = None
    loaded = (
        _load_chat_cache(cache_path, cache_meta)
        if cache_meta is not None
        else None
    )
    cache_hit = loaded is not None
    if loaded is not None:
        raw, stream_start_ms = loaded
        print(f"[Chat] 沿用快取 ({len(raw)} 則)")
    else:
        if cache_path.exists() and cache_meta is None:
            print("[Chat] 快取失效原因：缺少來源檔路徑，無法驗證快取")
        try:
            youtube = _build_youtube_service(api_key)
            live_chat_id = _get_live_chat_id(youtube, video_id)
            if not live_chat_id:
                if stage_report is not None:
                    stage_report.update(
                        status="skipped",
                        reason="影片沒有可用的 chat replay",
                    )
                return []
            stream_start_ms = _get_stream_start_time(youtube, video_id)
            if stream_start_ms is None:
                error = "無法取得直播開始時間"
                print(f"[Chat] {error}")
                if stage_report is not None:
                    stage_report.update(status="failed", error=error)
                return []
            raw = _fetch_all_messages(youtube, live_chat_id)
            if cache_meta is not None:
                _write_json_cache(
                    cache_path,
                    {
                        "metadata": {"stream_start_ms": stream_start_ms},
                        "messages": raw,
                    },
                    cache_meta,
                )
                print(f"[Chat] 快取 → {cache_path}")
            else:
                print("[Chat] 警告：缺少來源檔路徑，本次不寫入無法驗證的快取")
        except Exception as e:
            error = f"{type(e).__name__}: {e}"
            print(f"[Chat] API 錯誤: {error}")
            if stage_report is not None:
                stage_report.update(status="failed", error=error)
            return []

    if stage_report is not None:
        artifact_paths = [cache_path, _cache_meta_path(cache_path)]
        stage_report.update(
            status="success",
            cache_hit=cache_hit,
            artifacts=[
                str(path.resolve()) for path in artifact_paths if path.exists()
            ],
            message_count=len(raw),
        )

    if not raw:
        return []

    if stream_start_ms is None:
        stream_start_ms = _fallback_stream_start_ms(raw)

    aggregated = aggregate_chat(
        messages=raw,
        stream_start_ms=stream_start_ms,
        window_sec=window_sec,
        total_duration_sec=total_duration_sec,
        max_per_segment=max_per_seg,
        spike_threshold=spike_threshold,
        reaction_keywords=reaction_kw,
        min_spike_messages=min_spike_msgs,
    )

    spike_count = sum(1 for a in aggregated if a and a["is_spike"])
    print(f"[Chat] {len(raw)} 則訊息 → {len(aggregated)} 窗口, {spike_count} 個 spike")
    return aggregated
