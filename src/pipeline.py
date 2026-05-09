"""Pipeline — 主流程控制，串接 ASR → Chat → OCR → Align → Render."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Optional

import yaml

from .asr_runner import run_asr
from .chat_runner import run_chat
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
    asr_segments = run_asr(input_path, config, out_dir)

    # Step 2: Chat Log
    print("\n── Step 2: Chat Log ──")
    total_duration = 0.0
    if asr_segments:
        total_duration = max(s.time_end for s in asr_segments)
    chat_windows = run_chat(video_id, config, out_dir, total_duration)

    # Step 3: OCR (Phase 1)
    ocr_segments = []
    if enable_ocr:
        print("\n── Step 3: OCR ──")
        from .ocr_runner import run_ocr
        ocr_segments = run_ocr(input_path, config, out_dir, ocr_config_path)

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
    ]

    # 衝突報告（有 OCR 時才產出）
    if enable_ocr:
        conflict_path = out_dir / "conflict_report.md"
        render_conflict_report(timeline, conflict_path, title)
        outputs.append(f"  - conflict_report.md")

    # SRT 字幕（Phase 2）
    if enable_srt:
        srt_results = render_all_srt(timeline, out_dir, stem="subtitle")
        for name, count in srt_results.items():
            outputs.append(f"  - {name}  ({count} 條字幕)")

    # 精彩片段剪輯（Phase 3，需要 FFmpeg + 影片檔）
    if enable_clips:
        step_n += 1
        print(f"\n── Step {step_n}: Clips ──")
        clip_results = extract_clips(input_path, timeline, out_dir, config)
        if clip_results:
            clips_index_path = out_dir / "clips_index.md"
            render_clips_index(clip_results, clips_index_path, title)
            edl_path = out_dir / "markers.edl"
            render_edl(clip_results, edl_path, title)
            outputs.append(f"  - clips/ ({len(clip_results)} 個片段)")
            outputs.append(f"  - clips_index.md")
            outputs.append(f"  - markers.edl")

    print(f"\n{'='*60}")
    print(f"完成！輸出目錄: {out_dir}")
    for o in outputs:
        print(o)
    print(f"{'='*60}\n")

    return out_dir
