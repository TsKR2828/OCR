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

import json
from pathlib import Path
from typing import Optional

import typer

app = typer.Typer(help="VN-Transcribe 一鍵出片")


def _is_nonempty_file(path: Path) -> bool:
    try:
        return path.is_file() and path.stat().st_size > 0
    except OSError:
        return False


def _current_clip_counts(out_dir: Path) -> tuple[int, int]:
    manifest_path = out_dir / "clips_manifest.json"
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            clips = manifest.get("clips") if isinstance(manifest, dict) else None
            if not isinstance(clips, list):
                raise ValueError("clips 欄位不是陣列")
            if any(
                not isinstance(clip, dict)
                or not isinstance(clip.get("filename"), str)
                for clip in clips
            ):
                raise ValueError("clips 項目缺少有效 filename")
            clips_dir = out_dir / "clips"
            existing = 0
            missing = 0
            for clip in clips:
                clip_path = clips_dir / clip["filename"]
                if _is_nonempty_file(clip_path):
                    existing += 1
                else:
                    missing += 1
            if missing:
                typer.echo(
                    f"[quick_clip] 警告：manifest 中有 {missing} 個 clip "
                    "缺少有效輸出檔"
                )
            return existing, missing
        except (json.JSONDecodeError, OSError, ValueError) as e:
            typer.echo(
                f"[quick_clip] 警告：clips_manifest.json 無法讀取 ({e})，"
                "改用掃描 clips 目錄的舊行為"
            )
    else:
        typer.echo(
            "[quick_clip] 警告：找不到 clips_manifest.json，"
            "改用掃描 clips 目錄的舊行為"
        )

    clips_dir = out_dir / "clips"
    files = list(clips_dir.glob("*.mp4")) if clips_dir.exists() else []
    existing = sum(_is_nonempty_file(path) for path in files)
    return existing, len(files) - existing


def _count_current_clips(out_dir: Path) -> int:
    return _current_clip_counts(out_dir)[0]


def _load_job(out_dir: Path) -> dict:
    job_path = out_dir / "job.json"
    try:
        job = json.loads(job_path.read_text(encoding="utf-8"))
        if not isinstance(job, dict):
            raise ValueError("job.json 根節點不是物件")
        return job
    except (json.JSONDecodeError, OSError, ValueError) as e:
        typer.echo(f"[quick_clip] 警告：無法讀取 job.json ({e})")
        return {}


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

    from src.pipeline import PipelineFailed, run_pipeline
    pipeline_failed = False
    try:
        out_dir = run_pipeline(
            input_file, config, output, None, title,
            enable_srt=True,
            enable_clips=True,
            chat_url=chat_url,
            clip_vertical=vertical,
            clip_burn_subs=burn_subs,
            clip_reel=reel,
        )
    except PipelineFailed as e:
        out_dir = e.output_dir
        pipeline_failed = True

    clips_dir = out_dir / "clips"
    n_clips, invalid_clips = _current_clip_counts(out_dir)
    job = _load_job(out_dir)
    clip_stage = job.get("stages", {}).get("clipper", {})
    reported_failed = int(clip_stage.get("failed_count", 0) or 0)
    attempted_clips = int(clip_stage.get("attempted_count", 0) or 0)
    failed_clips = max(
        reported_failed,
        invalid_clips,
        max(0, attempted_clips - n_clips),
    )
    clip_status = clip_stage.get("status")
    pipeline_failed = pipeline_failed or job.get("exit_code") == 1
    reel_path = out_dir / "highlight_reel.mp4"
    reel_created = bool(
        clip_stage.get("reel_created") and _is_nonempty_file(reel_path)
        if "reel_created" in clip_stage
        else _is_nonempty_file(reel_path)
    )

    typer.echo("\n" + "=" * 50)
    if n_clips == 0:
        typer.echo("🎬 出片失敗")
    elif pipeline_failed:
        typer.echo("🎬 出片部分成功（管線有失敗階段）")
    elif clip_status == "partial":
        typer.echo("🎬 出片部分成功")
    else:
        typer.echo("🎬 出片完成")
    typer.echo(f"   片段：成功 {n_clips} / 失敗 {failed_clips} → {clips_dir}")
    typer.echo(f"   合輯：{'有' if reel_created else '無'}")
    if reel_created:
        typer.echo(f"   精選合輯 → {reel_path}")
    clips_index_path = out_dir / "clips_index.md"
    if n_clips > 0 and clips_index_path.exists():
        typer.echo(f"   清單 → {clips_index_path}")
    else:
        typer.echo("   清單：無")
    typer.echo("=" * 50)

    if n_clips == 0 or pipeline_failed:
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
