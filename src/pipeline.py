"""Pipeline — 主流程控制，串接 ASR → Chat → Align → Render."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Optional

import yaml

from .asr_runner import run_asr
from .chat_runner import run_chat
from .align import align_mvp
from .schema import save_timeline
from .renderers.index import render_index
from .renderers.excel import render_excel


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
) -> Path:
    """執行完整 MVP 管線.

    回傳 output 目錄路徑。
    """
    config = load_config(config_path)
    out_dir = make_output_dir(input_path, output_base)

    if not title:
        channel_name = config.get("channel", {}).get("name", "")
        title = f"【{channel_name}】{input_path.stem}" if channel_name else input_path.stem

    print(f"\n{'='*60}")
    print(f"VN-Transcribe MVP Pipeline")
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

    # Step 3: Align
    print("\n── Step 3: Align ──")
    timeline = align_mvp(asr_segments, chat_windows, config)

    # Step 4: Render
    print("\n── Step 4: Render ──")
    timeline_path = out_dir / "timeline.json"
    save_timeline(timeline, timeline_path)
    print(f"[Timeline] 寫出 → {timeline_path} ({len(timeline)} 段)")

    index_path = out_dir / "index.md"
    render_index(timeline, index_path, title)

    excel_path = out_dir / "transcript.xlsx"
    render_excel(timeline, excel_path, title)

    print(f"\n{'='*60}")
    print(f"完成！輸出目錄: {out_dir}")
    print(f"  - timeline.json  ({len(timeline)} 段)")
    print(f"  - index.md")
    print(f"  - transcript.xlsx")
    print(f"{'='*60}\n")

    return out_dir
