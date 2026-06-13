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
        help="YouTube video ID（用於 Data API 拉 chat replay）",
    ),
    chat_url: Optional[str] = typer.Option(
        None, "--chat-url",
        help="YouTube 影片 URL，用 yt-dlp 拉 live_chat（免 API key，優先於 --video-id）",
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
    vertical: bool = typer.Option(
        False, "--vertical",
        help="剪輯時輸出 9:16 直式短影音（需重編碼，隱含 --clips）",
    ),
    burn_subs: bool = typer.Option(
        False, "--burn-subs",
        help="剪輯時把字幕燒進畫面（需重編碼，自動產 SRT，隱含 --clips）",
    ),
    reel: bool = typer.Option(
        False, "--reel",
        help="把分數最高的片段串成一支精選合輯 highlight_reel.mp4（隱含 --clips）",
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

    # 短影音相關旗標隱含啟用剪輯
    if vertical or burn_subs or reel:
        clips = True

    from src.pipeline import run_pipeline
    run_pipeline(
        input_file, config, output, video_id, title,
        enable_ocr=ocr,
        ocr_config_path=ocr_config,
        enable_srt=srt,
        enable_clips=clips,
        chat_url=chat_url,
        clip_vertical=vertical,
        clip_burn_subs=burn_subs,
        clip_reel=reel,
    )


if __name__ == "__main__":
    app()
