"""quick_clip — 一鍵出片：影片 → 辨識 → 精彩定位 → 切片（直式 + 燒字幕 + 精選合輯）.

把整條「辨識 → 定位 → 切片 → 燒字幕」串成一條龍，預設直接產出可發的短影音素材。
守 ROADMAP 原則：產出素材，最終剪輯仍留給人。

範例：
    # 最常用：一條指令拿到直式燒字幕 clip + 精選合輯
    python quick_clip.py "影片.mp4"

    # 帶 chat 訊號（免 API key，精彩定位更準）
    python quick_clip.py "影片.mp4" --chat-url "https://youtu.be/XXXX"

    # 只要橫式快切（不重編碼，最快）
    python quick_clip.py "影片.mp4" --fast

預設行為（短影音模式）：產 SRT + 直式 9:16 + 燒字幕 + 精選合輯。
"""

from pathlib import Path
from typing import Optional

import typer

app = typer.Typer(help="VN-Transcribe 一鍵出片")


@app.command()
def main(
    input_file: Path = typer.Argument(..., help="影片檔路徑"),
    config: Path = typer.Option(Path("config/channel.yaml"), "--config", "-c", help="頻道設定檔"),
    output: Path = typer.Option(Path("output"), "--output", "-o", help="輸出目錄根路徑"),
    chat_url: Optional[str] = typer.Option(
        None, "--chat-url",
        help="YouTube URL，用 yt-dlp 拉 live_chat 補 chat_spike 訊號（免 API key）",
    ),
    title: str = typer.Option("", "--title", "-t", help="影片標題"),
    vertical: bool = typer.Option(True, "--vertical/--horizontal", help="9:16 直式（預設）或維持橫式"),
    burn_subs: bool = typer.Option(True, "--burn-subs/--no-subs", help="燒字幕（預設開）"),
    reel: bool = typer.Option(True, "--reel/--no-reel", help="精選合輯（預設開）"),
    fast: bool = typer.Option(
        False, "--fast",
        help="極速模式：橫式 + 不燒字幕 + -c copy 快切（覆寫上面選項）",
    ),
):
    """一鍵把影片變成短影音素材."""
    if not input_file.exists():
        typer.echo(f"找不到檔案: {input_file}", err=True)
        raise typer.Exit(1)

    if fast:
        vertical = False
        burn_subs = False

    mode = []
    mode.append("直式 9:16" if vertical else "橫式")
    if burn_subs:
        mode.append("燒字幕")
    if reel:
        mode.append("精選合輯")
    typer.echo(f"[quick_clip] 模式：{' + '.join(mode)}")
    if chat_url:
        typer.echo(f"[quick_clip] chat 訊號：{chat_url}")

    from src.pipeline import run_pipeline
    out_dir = run_pipeline(
        input_file, config, output, None, title,
        enable_srt=True,
        enable_clips=True,
        chat_url=chat_url,
        clip_vertical=vertical,
        clip_burn_subs=burn_subs,
        clip_reel=reel,
    )

    clips_dir = out_dir / "clips"
    n_clips = len(list(clips_dir.glob("*.mp4"))) if clips_dir.exists() else 0
    reel_path = out_dir / "highlight_reel.mp4"

    typer.echo("\n" + "=" * 50)
    typer.echo("🎬 出片完成")
    typer.echo(f"   片段：{n_clips} 個 → {clips_dir}")
    if reel and reel_path.exists():
        typer.echo(f"   精選合輯 → {reel_path}")
    typer.echo(f"   清單 → {out_dir / 'clips_index.md'}")
    typer.echo("=" * 50)


if __name__ == "__main__":
    app()
