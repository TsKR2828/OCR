"""VN-Transcribe Search CLI — 在 timeline.json 上做快速查詢."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from src.schema import load_timeline, Segment, fmt_ts

app = typer.Typer(help="VN-Transcribe 搜尋工具：在 timeline.json 中查詢段落")


def _print_segment(seg: Segment, show_score: bool = False) -> None:
    """格式化輸出一個 segment."""
    ts = fmt_ts(seg.time_start)
    source = seg.merge.source_type

    parts = [f"[{ts}]"]

    if seg.ocr and seg.ocr.character:
        parts.append(f"【{seg.ocr.character}】")

    if seg.ocr and seg.ocr.dialogue:
        parts.append(f"OCR: {seg.ocr.dialogue[:60]}")
        if len(seg.ocr.dialogue) > 60:
            parts[-1] += "..."

    if seg.asr and seg.asr.text:
        parts.append(f"ASR: {seg.asr.text[:60]}")
        if len(seg.asr.text) > 60:
            parts[-1] += "..."

    if seg.chat and seg.chat.is_spike:
        parts.append(f"Chat: {seg.chat.density_per_min:.0f}/min")

    if show_score and seg.score.total > 0:
        parts.append(f"(score: {seg.score.total:.0f})")

    parts.append(f"[{source}]")

    typer.echo("  ".join(parts))


def _load(timeline_path: Path) -> list[Segment]:
    if not timeline_path.exists():
        typer.echo(f"找不到 timeline: {timeline_path}", err=True)
        raise typer.Exit(1)
    return load_timeline(timeline_path)


@app.command()
def character(
    name: str = typer.Argument(..., help="角色名（支援部分比對）"),
    timeline: Path = typer.Option(
        Path("output"), "--timeline", "-t",
        help="timeline.json 路徑或 output 目錄",
    ),
) -> None:
    """搜尋某角色的所有台詞."""
    timeline_path = _resolve_timeline(timeline)
    segments = _load(timeline_path)

    results = [
        seg for seg in segments
        if seg.ocr and seg.ocr.character and name in seg.ocr.character
    ]

    typer.echo(f"\n角色「{name}」— 共 {len(results)} 段\n")
    for seg in results:
        _print_segment(seg)
    typer.echo("")


@app.command()
def keyword(
    word: str = typer.Argument(..., help="關鍵字"),
    timeline: Path = typer.Option(
        Path("output"), "--timeline", "-t",
        help="timeline.json 路徑或 output 目錄",
    ),
) -> None:
    """搜尋包含關鍵字的段落（OCR + ASR 都搜）."""
    timeline_path = _resolve_timeline(timeline)
    segments = _load(timeline_path)

    results = []
    for seg in segments:
        ocr_text = seg.ocr.dialogue if seg.ocr and seg.ocr.dialogue else ""
        asr_text = seg.asr.text if seg.asr and seg.asr.text else ""
        if word in ocr_text or word in asr_text:
            results.append(seg)

    typer.echo(f"\n關鍵字「{word}」— 共 {len(results)} 段\n")
    for seg in results:
        _print_segment(seg)
    typer.echo("")


@app.command()
def reaction(
    top: int = typer.Option(10, "--top", "-n", help="顯示前 N 段"),
    timeline: Path = typer.Option(
        Path("output"), "--timeline", "-t",
        help="timeline.json 路徑或 output 目錄",
    ),
) -> None:
    """列出精彩度最高的段落（含 chat spike）."""
    timeline_path = _resolve_timeline(timeline)
    segments = _load(timeline_path)

    scored = [(seg, seg.score.total) for seg in segments if seg.score.total > 0]
    scored.sort(key=lambda x: x[1], reverse=True)

    typer.echo(f"\n精彩段落 Top {top} — 共 {len(scored)} 段有分數\n")
    for seg, _score in scored[:top]:
        _print_segment(seg, show_score=True)
    typer.echo("")


@app.command()
def chapter(
    name: str = typer.Argument("", help="章節名（留空列出所有章節）"),
    timeline: Path = typer.Option(
        Path("output"), "--timeline", "-t",
        help="timeline.json 路徑或 output 目錄",
    ),
) -> None:
    """列出指定章節的段落，或列出所有章節."""
    timeline_path = _resolve_timeline(timeline)
    segments = _load(timeline_path)

    if not name:
        # 列出所有章節
        chapters: dict[str, list[Segment]] = {}
        for seg in segments:
            if seg.ocr and seg.ocr.chapter:
                ch = seg.ocr.chapter
                if ch not in chapters:
                    chapters[ch] = []
                chapters[ch].append(seg)

        typer.echo(f"\n章節列表 — 共 {len(chapters)} 章\n")
        for ch, segs in chapters.items():
            ts = fmt_ts(segs[0].time_start)
            typer.echo(f"  [{ts}] {ch} ({len(segs)} 段)")
        typer.echo("")
    else:
        results = [
            seg for seg in segments
            if seg.ocr and seg.ocr.chapter and name in seg.ocr.chapter
        ]
        typer.echo(f"\n章節「{name}」— 共 {len(results)} 段\n")
        for seg in results:
            _print_segment(seg)
        typer.echo("")


@app.command()
def conflict(
    timeline: Path = typer.Option(
        Path("output"), "--timeline", "-t",
        help="timeline.json 路徑或 output 目錄",
    ),
) -> None:
    """列出 OCR/ASR 衝突清單."""
    timeline_path = _resolve_timeline(timeline)
    segments = _load(timeline_path)

    conflicts = [
        seg for seg in segments
        if seg.merge.match_status == "conflict"
    ]

    typer.echo(f"\nOCR/ASR 衝突 — 共 {len(conflicts)} 處\n")
    for seg in conflicts:
        ts = fmt_ts(seg.time_start)
        ocr_text = seg.ocr.dialogue[:40] if seg.ocr and seg.ocr.dialogue else "（無）"
        asr_text = seg.asr.text[:40] if seg.asr and seg.asr.text else "（無）"
        typer.echo(f"  [{ts}]")
        typer.echo(f"    OCR: {ocr_text}")
        typer.echo(f"    ASR: {asr_text}")
        typer.echo("")


@app.command()
def superchat(
    timeline: Path = typer.Option(
        Path("output"), "--timeline", "-t",
        help="timeline.json 路徑或 output 目錄",
    ),
) -> None:
    """列出所有 superchat 時間點."""
    timeline_path = _resolve_timeline(timeline)
    segments = _load(timeline_path)

    results = []
    for seg in segments:
        if seg.chat and seg.chat.superchat_count > 0:
            results.append(seg)

    typer.echo(f"\nSuperchat 時間點 — 共 {len(results)} 段\n")
    for seg in results:
        ts = fmt_ts(seg.time_start)
        sc_count = seg.chat.superchat_count if seg.chat else 0
        sc_msgs = [
            m for m in (seg.chat.messages if seg.chat else [])
            if m.type == "superchat"
        ]
        typer.echo(f"  [{ts}] SC x{sc_count}")
        for m in sc_msgs:
            amount_str = f" ({m.amount})" if m.amount else ""
            typer.echo(f"    {m.author}: {m.text[:40]}{amount_str}")
    typer.echo("")


def _resolve_timeline(path: Path) -> Path:
    """如果 path 是目錄，自動尋找裡面最新的 timeline.json."""
    if path.is_file():
        return path

    if path.is_dir():
        # 直接在目錄下找
        direct = path / "timeline.json"
        if direct.exists():
            return direct

        # 在子目錄下找最新的
        candidates = list(path.glob("*/timeline.json"))
        if candidates:
            # 取最新修改的
            candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            return candidates[0]

    typer.echo(f"找不到 timeline.json（搜尋路徑: {path}）", err=True)
    raise typer.Exit(1)


if __name__ == "__main__":
    app()
