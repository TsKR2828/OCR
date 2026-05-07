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
):
    """對一段 VN 實況錄影執行 ASR + Chat Log 管線，產出 timeline.json + index.md + transcript.xlsx."""
    if not input_file.exists():
        typer.echo(f"找不到檔案: {input_file}", err=True)
        raise typer.Exit(1)

    from src.pipeline import run_pipeline
    run_pipeline(input_file, config, output, video_id, title)


if __name__ == "__main__":
    app()
