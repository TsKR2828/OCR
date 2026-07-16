"""Clipper — 精彩片段自動剪輯 + 短影音適配（Phase 3 / Phase 4，需要 FFmpeg）.

能力：
- select_highlights / _merge_intervals：挑分數高的段落、合併相鄰區間
- keyframe 對齊：-c copy 切點吸附到關鍵影格，開頭不黑/不破格
- 長度夾制：min_clip_sec / max_clip_sec
- 燒字幕：把對應時段 SRT 切片+平移後用 libass 燒進畫面（重編碼）
- 9:16 直式：blur-pad（保全畫面）/ crop（置中裁切）
- 精選合輯：top-N 串成一支 highlight_reel.mp4
"""

from __future__ import annotations

import subprocess
import shutil
from pathlib import Path
from typing import Optional

from .chat_runner import (
    _atomic_write_json,
    _build_cache_meta,
    _load_valid_json_cache,
    _write_json_cache,
)
from .schema import Segment, fmt_ts


# ---------------------------------------------------------------------------
# 區間挑選 / 合併 / 夾制
# ---------------------------------------------------------------------------

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


def _clamp_duration(
    start: float,
    end: float,
    min_sec: float,
    max_sec: float,
    video_dur: float,
) -> tuple[float, float]:
    """把區間長度夾到 [min_sec, max_sec].

    太短 → 從中心對稱往外擴到 min_sec（碰到 0 / 影片尾端就往另一邊補）。
    太長 → 從 start 截到 max_sec（保留最前面，通常是反應的起點）。
    """
    dur = end - start
    if dur < min_sec:
        center = (start + end) / 2.0
        start = center - min_sec / 2.0
        end = center + min_sec / 2.0
        if start < 0:
            end += -start
            start = 0.0
        if video_dur > 0 and end > video_dur:
            start = max(0.0, start - (end - video_dur))
            end = video_dur
    elif dur > max_sec:
        end = start + max_sec
    return start, end


def select_highlights(
    segments: list[Segment],
    min_score: float = 15.0,
    top_n: int = 30,
) -> list[Segment]:
    """篩選精彩段落：score >= min_score，取前 top_n 段."""
    candidates = [s for s in segments if s.score.total >= min_score]
    candidates.sort(key=lambda s: s.score.total, reverse=True)
    return candidates[:top_n]


# ---------------------------------------------------------------------------
# Keyframe 對齊（修 -c copy 開頭黑畫面）
# ---------------------------------------------------------------------------

def _list_keyframes(video_path: Path, cache_dir: Path) -> list[float]:
    """列出影片的關鍵影格 pts（秒），由小到大. 結果快取到 sidecar JSON.

    用 ffprobe 讀 packet flags（demux-only，不解碼，快），flags 含 'K' 即關鍵影格。
    失敗回傳空列表（呼叫端會退回不吸附）。
    """
    cache_path = cache_dir / f"keyframes_{video_path.stem[:16]}.json"
    cache_meta = _build_cache_meta(
        video_path,
        "clipper_keyframes",
        {"probe": "ffprobe packet=pts_time,flags v:0"},
    )
    cached = _load_valid_json_cache(cache_path, cache_meta, "Clipper keyframe")
    if isinstance(cached, list):
        return cached
    if cached is not None:
        print(f"[Clipper] 快取失效原因：{cache_path.name} 格式不正確")

    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "packet=pts_time,flags",
        "-of", "csv=print_section=0",
        str(video_path),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300, check=True)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        print(f"[Clipper] keyframe 偵測失敗，改用原始切點: {e}")
        return []

    keyframes: list[float] = []
    for line in proc.stdout.splitlines():
        parts = line.split(",")
        if len(parts) < 2:
            continue
        pts_str, flags = parts[0], parts[1]
        if "K" not in flags:
            continue
        try:
            keyframes.append(float(pts_str))
        except ValueError:
            continue

    keyframes.sort()
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        _write_json_cache(cache_path, keyframes, cache_meta)
    except OSError as e:
        print(f"[Clipper] 警告：無法寫入 keyframe 快取 ({e})")
    print(f"[Clipper] keyframe 偵測：{len(keyframes)} 個關鍵影格")
    return keyframes


def _snap_start_to_keyframe(start: float, keyframes: list[float]) -> float:
    """把 start 吸附到 ≤ start 的最近關鍵影格（開頭乾淨）."""
    if not keyframes:
        return start
    import bisect
    idx = bisect.bisect_right(keyframes, start + 0.001) - 1
    if idx < 0:
        return keyframes[0] if keyframes[0] <= start + 0.5 else start
    return keyframes[idx]


# ---------------------------------------------------------------------------
# SRT 切片（給燒字幕用）
# ---------------------------------------------------------------------------

def _parse_srt_time(s: str) -> float:
    """SRT 時間 HH:MM:SS,mmm → 秒."""
    s = s.strip().replace(".", ",")
    hms, _, ms = s.partition(",")
    h, m, sec = hms.split(":")
    return int(h) * 3600 + int(m) * 60 + int(sec) + (int(ms) if ms else 0) / 1000.0


def _fmt_srt_time(seconds: float) -> str:
    if seconds < 0:
        seconds = 0.0
    total_ms = int(round(seconds * 1000))
    ms = total_ms % 1000
    total_ms //= 1000
    s = total_ms % 60
    total_ms //= 60
    m = total_ms % 60
    h = total_ms // 60
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def slice_srt(srt_path: Path, start: float, end: float, out_path: Path) -> int:
    """取 [start,end] 窗內的字幕、時間平移到 clip-local（減 start），寫到 out_path.

    回傳寫出的字幕條數。重疊即保留（部分落在窗內也算）。
    """
    if not srt_path or not srt_path.exists():
        return 0
    raw = srt_path.read_text(encoding="utf-8-sig")
    blocks = [b for b in raw.replace("\r\n", "\n").split("\n\n") if b.strip()]

    clip_dur = end - start
    out_blocks: list[str] = []
    idx = 0
    for block in blocks:
        lines = block.strip().split("\n")
        # 找含 --> 的那行
        ti = next((i for i, ln in enumerate(lines) if "-->" in ln), -1)
        if ti < 0:
            continue
        left, _, right = lines[ti].partition("-->")
        try:
            t0 = _parse_srt_time(left)
            t1 = _parse_srt_time(right)
        except Exception:
            continue
        # 與窗口重疊？
        if t1 <= start or t0 >= end:
            continue
        ns = max(0.0, t0 - start)
        ne = min(clip_dur, t1 - start)
        if ne <= ns:
            continue
        text = "\n".join(lines[ti + 1:]).strip()
        if not text:
            continue
        idx += 1
        out_blocks.append(
            f"{idx}\n{_fmt_srt_time(ns)} --> {_fmt_srt_time(ne)}\n{text}\n"
        )

    out_path.write_text("\n".join(out_blocks), encoding="utf-8-sig")
    return idx


# ---------------------------------------------------------------------------
# ffmpeg filter 組裝
# ---------------------------------------------------------------------------

def _vertical_filter(style: str, target_w: int = 1080, target_h: int = 1920) -> str:
    """回傳 9:16 直式的 ffmpeg filter 字串（單入單出 filterchain）."""
    if style == "crop":
        # 置中裁切到 9:16 再縮放（會切掉左右）
        return (
            f"crop='min(iw,ih*{target_w}/{target_h})':'min(ih,iw*{target_h}/{target_w})',"
            f"scale={target_w}:{target_h},setsar=1"
        )
    # 預設 blur-pad：模糊放大鋪底 + 原畫面置中（保全畫面）
    return (
        f"split=2[bg][fg];"
        f"[bg]scale={target_w}:{target_h}:force_original_aspect_ratio=increase,"
        f"crop={target_w}:{target_h},gblur=sigma=20[bg];"
        f"[fg]scale={target_w}:-2:force_original_aspect_ratio=decrease[fg];"
        f"[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1"
    )


def _subtitles_filter(srt_name: str, font: str, font_size: int) -> str:
    """回傳 subtitles= filter（在 cwd 內用純檔名，避開 Windows 路徑跳脫）."""
    style = (
        f"FontName={font},FontSize={font_size},"
        f"PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
        f"BorderStyle=1,Outline=2,Shadow=0,Alignment=2,MarginV=60"
    )
    return f"subtitles={srt_name}:force_style='{style}'"


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def _probe_duration(video_path: Path) -> float:
    cmd = [
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "csv=p=0", str(video_path),
    ]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=60, check=True)
        return float(out.stdout.strip())
    except Exception:
        return 0.0


def _is_nonempty_file(path: Path) -> bool:
    try:
        return path.is_file() and path.stat().st_size > 0
    except OSError:
        return False


def _archive_previous_clips(output_dir: Path) -> Path:
    clips_dir = output_dir / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)
    old_clips = sorted(
        path for path in clips_dir.iterdir()
        if path.is_file() and path.suffix.lower() == ".mp4"
    )
    if not old_clips:
        return clips_dir

    archive_dir = output_dir / "clips_old"
    archive_dir.mkdir(parents=True, exist_ok=True)
    for clip_path in old_clips:
        target = archive_dir / clip_path.name
        suffix = 1
        while target.exists():
            target = archive_dir / f"{clip_path.stem}.{suffix}{clip_path.suffix}"
            suffix += 1
        shutil.move(str(clip_path), str(target))
    print(f"[Clipper] 已將上一輪 {len(old_clips)} 個片段移至 {archive_dir}")
    return clips_dir


def _write_clips_manifest(
    output_dir: Path,
    video_path: Path,
    clip_results: list[dict],
) -> None:
    clips = [
        {
            "filename": clip["filename"],
            "time_start": clip["time_start"],
            "time_end": clip["time_end"],
            "segments": clip.get("segments", []),
        }
        for clip in clip_results
    ]
    _atomic_write_json(
        output_dir / "clips_manifest.json",
        {
            "version": 1,
            "source": str(video_path.resolve()),
            "clips": clips,
        },
    )


def extract_clips(
    video_path: Path,
    segments: list[Segment],
    output_dir: Path,
    config: dict,
    burn_subs: bool = False,
    vertical: bool = False,
    srt_path: Optional[Path] = None,
    make_reel: bool = False,
    stage_report: Optional[dict] = None,
) -> list[dict]:
    """從影片中截取精彩片段，可選燒字幕 / 直式 / 精選合輯.

    回傳 clip 資訊列表 [{index, time_start, time_end, duration, score, path, filename, ...}]
    """
    clips_dir = _archive_previous_clips(output_dir)
    _write_clips_manifest(output_dir, video_path, [])
    manifest_path = output_dir / "clips_manifest.json"
    if stage_report is not None:
        stage_report.update(
            cache_hit=False,
            artifacts=[str(manifest_path.resolve())],
            attempted_count=0,
            success_count=0,
            failed_count=0,
            reel_requested=make_reel,
            reel_created=False,
        )

    if not shutil.which("ffmpeg"):
        error = "找不到 ffmpeg（請安裝 ffmpeg 並加入 PATH）"
        print(f"[Clipper] {error}，無法剪輯")
        if stage_report is not None:
            stage_report.update(status="failed", error=error)
        return []

    hl = config.get("highlight", {})
    min_score = hl.get("min_score", 15)
    top_n = hl.get("top_n", 30)
    padding = hl.get("clip_padding_sec", 3.0)
    merge_gap = hl.get("clip_merge_gap_sec", 2.0)
    min_clip = hl.get("min_clip_sec", 4.0)
    max_clip = hl.get("max_clip_sec", 90.0)
    v_style = hl.get("vertical_style", "blur")
    font = hl.get("burn_font", "Microsoft JhengHei")
    font_size = hl.get("burn_font_size", 18)
    try:
        render_workers = max(1, int(hl.get("render_workers", 2)))
    except (TypeError, ValueError):
        render_workers = 2

    highlights = select_highlights(segments, min_score, top_n)
    if not highlights:
        reason = "沒有達到門檻的精彩段落"
        print(f"[Clipper] {reason}，跳過剪輯")
        if stage_report is not None:
            stage_report.update(status="skipped", reason=reason)
        return []

    video_dur = _probe_duration(video_path)

    # 加 padding → 合併 → 夾制長度
    intervals = [
        (max(0.0, s.time_start - padding), s.time_end + padding)
        for s in highlights
    ]
    merged = _merge_intervals(intervals, merge_gap)
    merged = [_clamp_duration(s, e, min_clip, max_clip, video_dur) for s, e in merged]

    # 回填每個區間的貢獻 segments（取分數）
    clip_segments: list[list[Segment]] = [[] for _ in merged]
    for seg in highlights:
        for i, (m_start, m_end) in enumerate(merged):
            if seg.time_start < m_end and seg.time_end > m_start:
                clip_segments[i].append(seg)
                break

    reencode = burn_subs or vertical
    keyframes = _list_keyframes(video_path, output_dir) if not reencode else []

    tmp_dir = clips_dir / "_tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    segment_indices = {id(segment): index for index, segment in enumerate(segments, 1)}
    attempted_count = len(merged)
    clip_errors: list[str] = []
    clip_results: list[dict] = []

    def render_clip(i: int, start: float, end: float) -> tuple[Optional[dict], Optional[str], Optional[str]]:
        try:
            if not reencode:
                start = _snap_start_to_keyframe(start, keyframes)
            duration = end - start
            if duration <= 0:
                return None, f"clip {i+1}: 起訖時間無效", None

            clip_score = max((s.score.total for s in clip_segments[i]), default=0)
            clip_name = f"clip_{i+1:03d}_{fmt_ts(start).replace(':', '')}.mp4"
            clip_path = clips_dir / clip_name
            cmd, cwd, sub_count = _build_clip_cmd(
                video_path, start, duration, clip_path, tmp_dir, i,
                reencode, burn_subs, vertical, v_style, srt_path, font, font_size,
            )
            subprocess.run(cmd, capture_output=True, timeout=300, check=True, cwd=cwd)
            if not _is_nonempty_file(clip_path):
                raise RuntimeError("ffmpeg 未產生有效 clip 輸出檔")
            burned = burn_subs and sub_count > 0
            return {
                "index": i + 1,
                "time_start": round(start, 3),
                "time_end": round(end, 3),
                "duration": round(duration, 1),
                "score": clip_score,
                "path": str(clip_path),
                "filename": clip_name,
                "segment_count": len(clip_segments[i]),
                "segments": [
                    {
                        "index": segment_indices[id(segment)],
                        "time_start": round(segment.time_start, 3),
                        "time_end": round(segment.time_end, 3),
                    }
                    for segment in clip_segments[i]
                ],
                "vertical": vertical,
                "subtitled": burned,
            }, None, None
        except subprocess.CalledProcessError as e:
            err = e.stderr.decode("utf-8", "ignore")[-300:] if e.stderr else "unknown"
            return None, f"clip {i+1}: {err}", f"[Clipper] clip {i+1} 失敗: {err}"
        except subprocess.TimeoutExpired:
            return None, f"clip {i+1}: 執行超時", f"[Clipper] clip {i+1} 超時"
        except Exception as e:
            message = f"{type(e).__name__}: {e}"
            return None, f"clip {i+1}: {message}", f"[Clipper] clip {i+1} 例外: {message}"

    from concurrent.futures import ThreadPoolExecutor, as_completed

    outcomes: dict[int, tuple[Optional[dict], Optional[str], Optional[str]]] = {}
    worker_count = min(render_workers, attempted_count)
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        future_indices = {
            executor.submit(render_clip, i, start, end): i
            for i, (start, end) in enumerate(merged)
        }
        for future in as_completed(future_indices):
            i = future_indices[future]
            try:
                outcomes[i] = future.result()
            except Exception as e:
                message = f"{type(e).__name__}: {e}"
                outcomes[i] = (
                    None,
                    f"clip {i+1}: {message}",
                    f"[Clipper] clip {i+1} 例外: {message}",
                )

    for i in range(attempted_count):
        result, error, log_message = outcomes[i]
        if log_message:
            print(log_message)
        if error:
            clip_errors.append(error)
        if result:
            clip_results.append(result)

    clip_results.sort(key=lambda clip: clip["index"])

    # 清暫存 SRT
    try:
        shutil.rmtree(tmp_dir, ignore_errors=True)
    except Exception:
        pass

    tag = []
    if vertical:
        tag.append("直式")
    if burn_subs:
        tag.append("燒字幕")
    suffix = f"（{'+'.join(tag)}）" if tag else ""
    print(f"[Clipper] 產出 {len(clip_results)} 個精彩片段{suffix} → {clips_dir}")
    _write_clips_manifest(output_dir, video_path, clip_results)

    reel_result = None
    reel_ready = True
    if make_reel and len(clip_results) >= 2:
        reel_path = output_dir / "highlight_reel.mp4"
        if reel_path.exists():
            archive_dir = output_dir / "clips_old"
            archive_dir.mkdir(parents=True, exist_ok=True)
            archived_reel = archive_dir / reel_path.name
            suffix = 1
            while archived_reel.exists():
                archived_reel = archive_dir / (
                    f"{reel_path.stem}.{suffix}{reel_path.suffix}"
                )
                suffix += 1
            try:
                shutil.move(str(reel_path), str(archived_reel))
                print(f"[Clipper] 已將上一輪合輯移至 {archived_reel}")
            except OSError as e:
                clip_errors.append(f"無法封存上一輪合輯: {e}")
                reel_ready = False
        if reel_ready:
            reel_result = render_highlight_reel(
                clip_results, reel_path, top_n=hl.get("reel_top_n", 10),
            )

    success_count = len(clip_results)
    failed_count = attempted_count - success_count
    reel_attempted = make_reel and success_count >= 2
    reel_created = (
        reel_result is not None and _is_nonempty_file(Path(reel_result))
    )
    if reel_attempted and not reel_created:
        clip_errors.append("精選合輯產出失敗")
    reel_insufficient = make_reel and success_count == 1
    if reel_insufficient:
        clip_errors.append("精選合輯至少需要 2 個成功 clip")

    if success_count == 0:
        status = "failed"
        error = f"所有 {attempted_count} 個 clip 剪輯失敗"
    elif (
        failed_count > 0
        or (reel_attempted and not reel_created)
        or reel_insufficient
    ):
        status = "partial"
        error = f"clip 成功 {success_count} / 失敗 {failed_count}"
    else:
        status = "success"
        error = None

    if error and clip_errors:
        error = f"{error}：{'；'.join(clip_errors)}"

    if stage_report is not None:
        artifacts = [str(manifest_path.resolve())]
        artifacts.extend(clip["path"] for clip in clip_results)
        if reel_created:
            artifacts.append(str(Path(reel_result).resolve()))
        stage_report.update(
            status=status,
            error=error,
            artifacts=artifacts,
            attempted_count=attempted_count,
            success_count=success_count,
            failed_count=failed_count,
            errors=clip_errors,
            reel_requested=make_reel,
            reel_created=reel_created,
        )

    return clip_results


def _build_clip_cmd(
    video_path: Path, start: float, duration: float, clip_path: Path,
    tmp_dir: Path, idx: int, reencode: bool, burn_subs: bool, vertical: bool,
    v_style: str, srt_path: Optional[Path], font: str, font_size: int,
) -> tuple[list[str], Optional[str], int]:
    """組 ffmpeg 命令。回傳 (cmd, cwd, sub_count).

    cwd 非 None 時表示要在 tmp_dir 內跑（燒字幕用純檔名避開 Windows 路徑跳脫）；
    sub_count 是該 clip 燒進的字幕條數（0 表示沒燒）。
    """
    if not reencode:
        # 快切：keyframe 對齊 + -c copy
        cmd = [
            "ffmpeg", "-y",
            "-ss", f"{start:.3f}", "-i", str(video_path),
            "-t", f"{duration:.3f}",
            "-c", "copy", "-avoid_negative_ts", "make_zero",
            str(clip_path),
        ]
        return cmd, None, 0

    # 重編碼路徑（直式 / 燒字幕）
    filters: list[str] = []
    if vertical:
        filters.append(_vertical_filter(v_style))

    cwd: Optional[str] = None
    out_arg = str(clip_path)
    sub_count = 0
    if burn_subs and srt_path:
        srt_name = f"clip_{idx+1:03d}.srt"
        clip_srt = tmp_dir / srt_name
        sub_count = slice_srt(srt_path, start, start + duration, clip_srt)
        if sub_count > 0:
            filters.append(_subtitles_filter(srt_name, font, font_size))
            cwd = str(tmp_dir)            # 在 tmp_dir 內跑，subtitles 用純檔名
            out_arg = str(clip_path.resolve())

    vf = ",".join(filters) if filters else None
    cmd = [
        "ffmpeg", "-y",
        "-ss", f"{start:.3f}", "-i", str(video_path.resolve()),
        "-t", f"{duration:.3f}",
    ]
    if vf:
        cmd += ["-vf", vf]
    cmd += [
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-c:a", "aac", "-b:a", "160k",
        "-movflags", "+faststart",
        out_arg,
    ]
    return cmd, cwd, sub_count


def render_highlight_reel(
    clip_results: list[dict],
    output_path: Path,
    top_n: int = 10,
) -> Optional[Path]:
    """把分數最高的前 top_n 個 clip 依分數串成一支精選合輯.

    用 concat demuxer + -c copy（同一次產出的 clip 編碼參數一致，可直接 copy）。
    """
    if len(clip_results) < 2:
        return None
    ranked = sorted(clip_results, key=lambda c: c["score"], reverse=True)[:top_n]
    ranked.sort(key=lambda c: c["time_start"])   # 合輯內仍按時間排，敘事順

    list_file = output_path.parent / "_reel_list.txt"
    lines = [f"file '{Path(c['path']).resolve().as_posix()}'" for c in ranked]
    list_file.write_text("\n".join(lines), encoding="utf-8")

    cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(list_file), "-c", "copy",
        "-movflags", "+faststart", str(output_path),
    ]
    try:
        subprocess.run(cmd, capture_output=True, timeout=300, check=True)
        list_file.unlink(missing_ok=True)
        total = sum(c["duration"] for c in ranked)
        print(f"[Clipper] 精選合輯 → {output_path} ({len(ranked)} 段, {total:.0f}s)")
        return output_path
    except subprocess.CalledProcessError as e:
        err = e.stderr.decode("utf-8", "ignore")[-300:] if e.stderr else "unknown"
        print(f"[Clipper] 合輯失敗（嘗試重編碼 concat）: {err}")
        # 退回 concat filter 重編碼
        return _reel_reencode(ranked, output_path)
    except subprocess.TimeoutExpired:
        print("[Clipper] 合輯超時")
        return None


def _reel_reencode(ranked: list[dict], output_path: Path) -> Optional[Path]:
    """concat demuxer 失敗時的退路：用 concat filter 重編碼（統一參數）."""
    inputs: list[str] = []
    for c in ranked:
        inputs += ["-i", str(Path(c["path"]).resolve())]
    n = len(ranked)
    streams = "".join(f"[{i}:v][{i}:a]" for i in range(n))
    filter_complex = f"{streams}concat=n={n}:v=1:a=1[v][a]"
    cmd = [
        "ffmpeg", "-y", *inputs,
        "-filter_complex", filter_complex,
        "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-c:a", "aac", "-b:a", "160k",
        "-movflags", "+faststart", str(output_path),
    ]
    try:
        subprocess.run(cmd, capture_output=True, timeout=600, check=True)
        print(f"[Clipper] 精選合輯（重編碼）→ {output_path}")
        return output_path
    except Exception as e:
        print(f"[Clipper] 合輯重編碼也失敗: {e}")
        return None


def cut_manual_ranges(
    video_path: Path,
    ranges: list[tuple[float, float]],
    output_dir: Path,
    config: dict,
    srt_path: Optional[Path] = None,
    burn_subs: bool = False,
    vertical: bool = False,
    labels: Optional[list[str]] = None,
    export_srt: bool = True,
) -> list[dict]:
    """從手動指定的時間範圍剪 clips（人工/LLM 選段用）.

    與 extract_clips 共用 ffmpeg 組裝，但跳過分數選段。一律 re-encode（frame
    精準、開頭不黑）。可選燒字幕（從 srt_path 切片平移）/ 9:16 直式。
    給了 srt_path 時，**一律**在每段旁輸出對應的切片+平移 SRT（export_srt，
    供匯入剪輯軟體自己上字幕，不管有沒有燒進畫面）。
    回傳 clip 資訊列表。
    """
    if not shutil.which("ffmpeg"):
        print("[Clipper] 找不到 ffmpeg，跳過剪輯")
        return []

    hl = config.get("highlight", {})
    v_style = hl.get("vertical_style", "blur")
    font = hl.get("burn_font", "Microsoft JhengHei")
    font_size = hl.get("burn_font_size", 18)
    video_dur = _probe_duration(video_path)

    output_dir.mkdir(parents=True, exist_ok=True)
    tmp_dir = output_dir / "_tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    results = []
    for i, (start, end) in enumerate(ranges):
        start = max(0.0, start)
        end = min(end, video_dur) if video_dur > 0 else end
        duration = end - start
        if duration <= 0:
            continue
        label = labels[i] if labels and i < len(labels) else f"clip{i+1:02d}"
        safe = "".join(c for c in label if c not in r'\/:*?"<>|')
        clip_name = f"{i+1:02d}_{safe}.mp4"
        clip_path = output_dir / clip_name

        # 手動範圍一律 re-encode（reencode=True）以求精準切點
        cmd, cwd, sub_count = _build_clip_cmd(
            video_path, start, duration, clip_path, tmp_dir, i,
            True, burn_subs, vertical, v_style, srt_path, font, font_size,
        )
        try:
            subprocess.run(cmd, capture_output=True, timeout=300, check=True, cwd=cwd)
            # 一律輸出對應的切片 SRT（給剪輯軟體匯入用），與燒字幕獨立
            srt_count = 0
            if export_srt and srt_path and Path(srt_path).exists():
                sidecar = output_dir / f"{i+1:02d}_{safe}.srt"
                srt_count = slice_srt(Path(srt_path), start, end, sidecar)
            results.append({
                "index": i + 1, "time_start": round(start, 3), "time_end": round(end, 3),
                "duration": round(duration, 1), "label": label, "path": str(clip_path),
                "filename": clip_name, "subtitled": burn_subs and sub_count > 0,
                "vertical": vertical, "score": 0, "srt_lines": srt_count,
            })
            print(f"[Clipper] {clip_name}  ({duration:.0f}s"
                  f"{', 燒字幕'+str(sub_count) if sub_count else ''}"
                  f"{', SRT'+str(srt_count) if srt_count else ''})")
        except subprocess.CalledProcessError as e:
            err = e.stderr.decode("utf-8", "ignore")[-300:] if e.stderr else "unknown"
            print(f"[Clipper] {clip_name} 失敗: {err}")
        except subprocess.TimeoutExpired:
            print(f"[Clipper] {clip_name} 超時")

    shutil.rmtree(tmp_dir, ignore_errors=True)
    print(f"[Clipper] 手動剪輯產出 {len(results)} 段 → {output_dir}")
    return results


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
        "| # | 時間範圍 | 長度 | 精彩度 | 直式 | 字幕 | 檔名 |",
        "|---|----------|------|--------|------|------|------|",
    ]
    total_duration = 0.0
    for clip in clip_results:
        ts_start = fmt_ts(clip["time_start"])
        ts_end = fmt_ts(clip["time_end"])
        dur = clip["duration"]
        total_duration += dur
        v = "✓" if clip.get("vertical") else ""
        sub = "✓" if clip.get("subtitled") else ""
        lines.append(
            f"| {clip['index']} | {ts_start} ~ {ts_end} | {dur:.0f}s | "
            f"{clip['score']:.0f} | {v} | {sub} | `{clip['filename']}` |"
        )
    lines.append("")
    lines.append(f"> 總長 {total_duration:.0f} 秒 ({total_duration/60:.1f} 分鐘)\n")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"[Clipper] 索引 → {output_path}")
