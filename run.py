"""VN-Transcribe CLI 入口."""

from pathlib import Path
from typing import Optional

import typer

app = typer.Typer(help="VN-Transcribe：VN 實況結構化引擎")


@app.command()
def transcribe(
    input_file: Path = typer.Argument(..., help="影片或音訊檔路徑"),
    config: Path = typer.Option(
        Path("config/channel.yaml"), "--config", "-c",
        help="頻道設定檔路徑",
    ),
    output: Path = typer.Option(
        Path("output"), "--output", "-o",
        help="輸出目錄根路徑",
    ),
    video_id: Optional[str] = typer.Option(
        None, "--video-id", "-v",
        help="YouTube video ID（用於拉 chat replay）",
    ),
    title: str = typer.Option(
        "", "--title", "-t",
        help="影片標題（用於 index.md 標題）",
    ),
    ocr: bool = typer.Option(
        False, "--ocr",
        help="啟用 OCR 層（Phase 1：需要 MangaOCR + ROI 校準）",
    ),
    ocr_config: Optional[Path] = typer.Option(
        None, "--ocr-config",
        help="OCR ROI 設定檔路徑（OCR-Tool 校準產出的 config.json）",
    ),
    srt: bool = typer.Option(
        False, "--srt",
        help="產出 SRT 字幕檔（原文軌 + 實況主軌 + 雙軌合併）",
    ),
    clips: bool = typer.Option(
        False, "--clips",
        help="自動剪輯精彩片段（需要 FFmpeg）",
    ),
):
    """對一段 VN 實況錄影執行結構化管線.

    預設產出 timeline.json + index.md + transcript.xlsx + stats.md。
    加 --ocr 啟用三層模式。加 --srt 輸出字幕。加 --clips 自動剪輯。
    """
    if not input_file.exists():
        typer.echo(f"找不到檔案: {input_file}", err=True)
        raise typer.Exit(1)

    if ocr_config and not ocr:
        typer.echo("提示：指定了 --ocr-config 但未啟用 --ocr，自動啟用 OCR 層", err=True)
        ocr = True

    from src.pipeline import run_pipeline
    run_pipeline(
        input_file, config, output, video_id, title,
        enable_ocr=ocr,
        ocr_config_path=ocr_config,
        enable_srt=srt,
        enable_clips=clips,
    )


if __name__ == "__main__":
    app()
