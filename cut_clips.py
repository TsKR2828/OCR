"""cut_clips — 從手動指定的時間範圍剪 clips（人工/LLM 選段用）.

quick_clip.py 是「自動挑精彩段」；cut_clips.py 是「我已經知道要剪哪幾段」的版本：
直接給時間範圍 + 標籤，可選燒字幕（從 SRT 切片平移）/ 9:16 直式。
範圍也可由 LLM 讀逐字稿後產出，再餵進來。

範例：
    python cut_clips.py "影片.mp4" \
        --ranges "08:36-09:50,30:21-31:02" \
        --labels "蛋包飯,我不能接受" \
        --srt output/xxx/subtitle_streamer.srt --burn-subs -o output/funny
"""

from pathlib import Path
from typing import Optional

import typer

from src.clipper import cut_manual_ranges, render_clips_index

app = typer.Typer(help="從手動時間範圍剪 clips（可燒字幕/直式）")


def _parse_t(x: str) -> float:
    x = x.strip()
    if ":" in x:
        m, s = x.split(":")
        return int(m) * 60 + float(s)
    return float(x)


@app.command()
def main(
    video: Path = typer.Argument(..., help="原始影片檔"),
    ranges: str = typer.Option(..., "--ranges", help="片段範圍，如 '08:36-09:50,30:21-31:02'"),
    labels: Optional[str] = typer.Option(None, "--labels", help="對應標籤，逗號分隔"),
    srt: Optional[Path] = typer.Option(None, "--srt", "-s", help="燒字幕用的 SRT（切片+平移）"),
    output: Path = typer.Option(Path("clips"), "--output", "-o", help="輸出目錄"),
    burn_subs: bool = typer.Option(False, "--burn-subs", help="燒字幕（需 --srt）"),
    vertical: bool = typer.Option(False, "--vertical", help="9:16 直式輸出"),
    config_path: Optional[Path] = typer.Option(None, "--config", "-c", help="頻道設定（取字型等）"),
):
    """剪指定範圍的 clips."""
    if not video.exists():
        typer.echo("找不到影片", err=True)
        raise typer.Exit(1)

    range_list = []
    for part in ranges.split(","):
        a, b = part.split("-")
        range_list.append((_parse_t(a), _parse_t(b)))
    label_list = [s.strip() for s in labels.split(",")] if labels else None

    config = {}
    if config_path and config_path.exists():
        import yaml
        config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}

    results = cut_manual_ranges(
        video, range_list, output, config,
        srt_path=srt, burn_subs=burn_subs, vertical=vertical, labels=label_list,
    )
    if results:
        render_clips_index(results, output / "clips_index.md", title=video.stem)
        typer.echo(f"\n🎬 剪出 {len(results)} 段 → {output}")


if __name__ == "__main__":
    app()
