"""Pipeline — 主流程控制，串接 ASR → Chat → OCR → Align → Render."""

from __future__ import annotations

import hashlib
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yaml

from .asr_runner import run_asr
from .chat_runner import _atomic_write_json, run_chat
from .align import align_mvp, align_full
from .schema import save_timeline
from .renderers.index import render_index
from .renderers.excel import render_excel
from .renderers.conflict import render_conflict_report
from .renderers.subtitle import render_all_srt
from .renderers.stats import render_stats
from .classifier import classify_all
from .clipper import extract_clips, render_clips_index
from .renderers.markers import render_edl, render_mpv_chapters


_STAGE_NAMES = ("asr", "chat", "ocr", "clipper")
_STAGE_STATUSES = {"success", "partial", "skipped", "failed"}


class PipelineFailed(SystemExit):
    """Pipeline 已寫完 job/摘要，但至少一個 stage 失敗."""

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        super().__init__(1)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _normalise_artifacts(artifacts: list) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for artifact in artifacts:
        path = str(Path(artifact).resolve())
        if path not in seen:
            seen.add(path)
            result.append(path)
    return result


def _write_job(job_path: Path, job: dict) -> None:
    _atomic_write_json(job_path, job)


def _finish_stage(
    job: dict,
    job_path: Path,
    stage_name: str,
    report: dict,
    started_at: str,
    started_perf: float,
) -> dict:
    status = report.get("status", "success")
    if status not in _STAGE_STATUSES:
        report["error"] = f"無效 stage status: {status!r}"
        status = "failed"

    fixed_keys = {"status", "error", "reason", "artifacts", "cache_hit"}
    stage = {
        "status": status,
        "started_at": started_at,
        "ended_at": _now_iso(),
        "duration_sec": round(time.perf_counter() - started_perf, 3),
        "error": str(report["error"]) if report.get("error") else None,
        "reason": str(report["reason"]) if report.get("reason") else None,
        "artifacts": _normalise_artifacts(report.get("artifacts", [])),
        "cache_hit": bool(report.get("cache_hit", False)),
    }
    for key, value in report.items():
        if key not in fixed_keys:
            stage[key] = value

    job["stages"][stage_name] = stage
    _write_job(job_path, job)
    return stage


def _run_stage(
    job: dict,
    job_path: Path,
    stage_name: str,
    runner,
    fallback,
):
    started_at = _now_iso()
    started_perf = time.perf_counter()
    report = {
        "status": "success",
        "error": None,
        "reason": None,
        "artifacts": [],
        "cache_hit": False,
    }
    try:
        result = runner(report)
    except Exception as e:
        report.update(
            status="failed",
            error=f"{type(e).__name__}: {e}",
        )
        print(f"[Pipeline] {stage_name} 失敗: {type(e).__name__}: {e}")
        result = fallback
    _finish_stage(
        job, job_path, stage_name, report, started_at, started_perf,
    )
    return result


def _skip_stage(job: dict, job_path: Path, stage_name: str, reason: str) -> None:
    started_at = _now_iso()
    started_perf = time.perf_counter()
    _finish_stage(
        job,
        job_path,
        stage_name,
        {
            "status": "skipped",
            "reason": reason,
            "artifacts": [],
            "cache_hit": False,
        },
        started_at,
        started_perf,
    )


def _print_stage_summary(job: dict) -> None:
    labels = {
        "asr": "ASR",
        "chat": "Chat",
        "ocr": "OCR",
        "clipper": "Clipper",
    }
    status_labels = {
        "success": "SUCCESS",
        "partial": "⚠ PARTIAL",
        "skipped": "SKIPPED",
        "failed": "FAILED",
    }
    print("\n階段狀態摘要")
    print("階段     | 狀態       | 耗時     | 原因")
    print("---------+------------+----------+------------------------------")
    for stage_name in _STAGE_NAMES:
        stage = job["stages"][stage_name]
        reason = stage.get("error") or stage.get("reason") or ""
        print(
            f"{labels[stage_name]:<8} | "
            f"{status_labels[stage['status']]:<10} | "
            f"{stage['duration_sec']:>7.3f}s | {reason}"
        )


def load_config(config_path: Path) -> dict:
    if not config_path.exists():
        print(f"[Pipeline] 設定檔不存在: {config_path}，使用預設值")
        return {}
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def make_output_dir(input_path: Path, base_dir: Path) -> Path:
    stem = input_path.stem
    h = hashlib.md5(stem.encode("utf-8")).hexdigest()[:8]
    safe = "".join(c for c in stem[:20] if c not in r'\/:*?"<>|')
    out_dir = base_dir / f"{h}_{safe}"
    out_dir.mkdir(parents=True, exist_ok=True)
    source_file = out_dir / "source.txt"
    if not source_file.exists():
        source_file.write_text(str(input_path.name), encoding="utf-8")
    return out_dir


def _get_media_duration(input_path: Path, asr_segments: list) -> float:
    """以 ffprobe 取得媒體實際時長，失敗時退回 ASR 推算."""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(input_path),
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, check=True, timeout=60,
        )
        duration = float(result.stdout.strip())
        if duration <= 0:
            raise ValueError(f"無效時長: {duration}")
        return duration
    except (OSError, subprocess.SubprocessError, ValueError) as e:
        fallback = max((s.time_end for s in asr_segments), default=0.0)
        print(
            f"[Pipeline] 警告：ffprobe 無法取得媒體實際時長 ({e})，"
            f"改用 ASR 推算 {fallback:.1f}s；chat window 可能截斷"
        )
        return fallback


def run_pipeline(
    input_path: Path,
    config_path: Path,
    output_base: Path,
    video_id: Optional[str] = None,
    title: str = "",
    enable_ocr: bool = False,
    ocr_config_path: Optional[Path] = None,
    enable_srt: bool = False,
    enable_clips: bool = False,
    chat_url: Optional[str] = None,
    clip_vertical: bool = False,
    clip_burn_subs: bool = False,
    clip_reel: bool = False,
) -> Path:
    """執行管線（MVP → Phase 1 → Phase 2 → Phase 3）.

    enable_ocr=False → MVP（ASR + Chat）
    enable_ocr=True  → Phase 1（ASR + Chat + OCR）
    enable_srt=True  → Phase 2 SRT 字幕輸出
    enable_clips=True → Phase 3 精彩片段自動剪輯

    回傳 output 目錄路徑。
    """
    config = load_config(config_path)
    out_dir = make_output_dir(input_path, output_base)
    job_path = out_dir / "job.json"
    job_started_at = _now_iso()
    job_started_perf = time.perf_counter()
    job = {
        "version": 1,
        "source": str(input_path.resolve()),
        "status": "running",
        "started_at": job_started_at,
        "ended_at": None,
        "duration_sec": 0.0,
        "exit_code": None,
        "stages": {},
    }
    _write_job(job_path, job)

    if not title:
        channel_name = config.get("channel", {}).get("name", "")
        title = f"【{channel_name}】{input_path.stem}" if channel_name else input_path.stem

    mode_label = "Phase 1 (ASR + Chat + OCR)" if enable_ocr else "MVP (ASR + Chat)"

    print(f"\n{'='*60}")
    print(f"VN-Transcribe Pipeline — {mode_label}")
    print(f"輸入: {input_path}")
    print(f"輸出: {out_dir}")
    print(f"{'='*60}\n")

    # Step 1: ASR
    print("── Step 1: ASR ──")
    asr_segments = _run_stage(
        job,
        job_path,
        "asr",
        lambda report: run_asr(
            input_path, config, out_dir, stage_report=report,
        ),
        [],
    )

    # Step 2: Chat Log
    print("\n── Step 2: Chat Log ──")
    total_duration = _get_media_duration(input_path, asr_segments)
    chat_windows = _run_stage(
        job,
        job_path,
        "chat",
        lambda report: run_chat(
            video_id,
            config,
            out_dir,
            total_duration,
            chat_url=chat_url,
            source_path=input_path,
            stage_report=report,
        ),
        [],
    )

    # Step 3: OCR (Phase 1)
    ocr_segments = []
    if enable_ocr:
        print("\n── Step 3: OCR ──")
        def run_ocr_stage(report: dict):
            from .ocr_runner import run_ocr
            return run_ocr(
                input_path,
                config,
                out_dir,
                ocr_config_path,
                stage_report=report,
            )

        ocr_segments = _run_stage(
            job,
            job_path,
            "ocr",
            run_ocr_stage,
            [],
        )
    else:
        _skip_stage(job, job_path, "ocr", "OCR 未啟用")

    # Step 4: Align
    step_n = 4 if enable_ocr else 3
    print(f"\n── Step {step_n}: Align ──")
    if enable_ocr and ocr_segments:
        timeline = align_full(asr_segments, chat_windows, ocr_segments, config)
    else:
        timeline = align_mvp(asr_segments, chat_windows, config)

    # Phase 3: 場景分類（永遠執行，零成本）
    step_n += 1
    print(f"\n── Step {step_n}: Classify ──")
    classify_all(timeline)

    # Render
    step_n += 1
    print(f"\n── Step {step_n}: Render ──")
    timeline_path = out_dir / "timeline.json"
    save_timeline(timeline, timeline_path)
    print(f"[Timeline] 寫出 → {timeline_path} ({len(timeline)} 段)")

    index_path = out_dir / "index.md"
    render_index(timeline, index_path, title)

    excel_path = out_dir / "transcript.xlsx"
    render_excel(timeline, excel_path, title)

    # 統計報告（永遠產出）
    stats_path = out_dir / "stats.md"
    render_stats(timeline, stats_path, title)

    outputs = [
        f"  - timeline.json  ({len(timeline)} 段)",
        f"  - index.md",
        f"  - transcript.xlsx",
        f"  - stats.md",
        f"  - job.json",
    ]

    # 衝突報告（有 OCR 時才產出）
    if enable_ocr:
        conflict_path = out_dir / "conflict_report.md"
        render_conflict_report(timeline, conflict_path, title)
        outputs.append(f"  - conflict_report.md")

    # SRT 字幕（Phase 2）。燒字幕需要 SRT 先存在，故 burn_subs 時自動產出。
    need_srt = enable_srt or (enable_clips and clip_burn_subs)
    if need_srt:
        srt_results = render_all_srt(timeline, out_dir, stem="subtitle")
        for name, count in srt_results.items():
            outputs.append(f"  - {name}  ({count} 條字幕)")

    # 精彩片段剪輯（Phase 3 + Phase 4 短影音，需要 FFmpeg + 影片檔）
    if enable_clips:
        step_n += 1
        print(f"\n── Step {step_n}: Clips ──")
        srt_path = None
        if clip_burn_subs:
            track = config.get("highlight", {}).get("subtitle_track", "streamer")
            srt_path = out_dir / f"subtitle_{track}.srt"
        clip_results = _run_stage(
            job,
            job_path,
            "clipper",
            lambda report: extract_clips(
                input_path, timeline, out_dir, config,
                burn_subs=clip_burn_subs,
                vertical=clip_vertical,
                srt_path=srt_path,
                make_reel=clip_reel,
                stage_report=report,
            ),
            [],
        )
        if clip_results:
            clips_index_path = out_dir / "clips_index.md"
            render_clips_index(clip_results, clips_index_path, title)
            edl_path = out_dir / "markers.edl"
            render_edl(clip_results, edl_path, title)
            outputs.append(f"  - clips/ ({len(clip_results)} 個片段)")
            outputs.append(f"  - clips_index.md")
            outputs.append(f"  - markers.edl")
            if job["stages"]["clipper"].get("reel_created"):
                outputs.append(f"  - highlight_reel.mp4")
    else:
        _skip_stage(job, job_path, "clipper", "剪輯未啟用")

    statuses = [job["stages"][name]["status"] for name in _STAGE_NAMES]
    has_failed = "failed" in statuses
    has_partial = "partial" in statuses
    job.update(
        status="failed" if has_failed else ("partial" if has_partial else "success"),
        ended_at=_now_iso(),
        duration_sec=round(time.perf_counter() - job_started_perf, 3),
        exit_code=1 if has_failed else 0,
    )
    _write_job(job_path, job)

    print(f"\n{'='*60}")
    _print_stage_summary(job)
    if has_failed:
        print(f"\nPipeline 失敗；輸出目錄: {out_dir}")
    elif has_partial:
        print(f"\nPipeline 部分成功；輸出目錄: {out_dir}")
    else:
        print(f"\nPipeline 成功；輸出目錄: {out_dir}")
    for o in outputs:
        print(o)
    print(f"{'='*60}\n")

    if has_failed:
        raise PipelineFailed(out_dir)
    return out_dir
