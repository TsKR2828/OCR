"""角色語音抽取工具 — 從 SRT 字幕 + 原始影片抽出指定角色的語音片段.

用法:
  # 從 SRT 抽（推薦 — 可先人工校正時間軸再抽）
  python extract_voices.py -c ケイ single <video.mp4> <subtitle.srt>
  python extract_voices.py -c ケイ --aliases KEI single <video.mp4> <subtitle.srt>

  # 從 timeline.json 抽（fallback）
  python extract_voices.py -c ケイ --from-timeline single <video.mp4> <timeline.json>

  # 批次（掃描 output 目錄下所有 SRT / timeline.json）
  python extract_voices.py -c ケイ batch <video_dir> <output_dir>

  # 指定輸出資料夾
  python extract_voices.py -c ケイ --out D:\\Blackstar-game-video\\voices single ...

輸出結構:
  voices/ケイ/{video_stem}/001_00m07s_それでも、.wav
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# 工具函式
# ---------------------------------------------------------------------------

def _time_fmt(sec: float) -> str:
    """秒數 → 00m07s 格式（用於檔名）."""
    m, s = divmod(int(sec), 60)
    return f"{m:02d}m{s:02d}s"


def _ffmpeg_ts(sec: float) -> str:
    """秒數 → HH:MM:SS.mmm 格式（FFmpeg 用）."""
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h):02d}:{int(m):02d}:{s:06.3f}"


def _sanitize(text: str, max_len: int = 20) -> str:
    """清理文字讓它能安全當檔名."""
    safe = text.replace("/", "").replace("\\", "").replace(":", "")
    safe = safe.replace("?", "").replace("*", "").replace('"', "")
    safe = safe.replace("<", "").replace(">", "").replace("|", "")
    safe = safe.replace("\n", " ").replace("\r", "").strip()
    safe = safe.replace("．", ".").replace("　", " ")
    if len(safe) > max_len:
        safe = safe[:max_len]
    return safe or "_"


# ---------------------------------------------------------------------------
# SRT 解析
# ---------------------------------------------------------------------------

# SRT 時間格式: 00:01:23,456
_SRT_TIME_RE = re.compile(
    r"(\d{1,2}):(\d{2}):(\d{2})[,.](\d{3})"
)

# pipeline 產出的角色名前綴: 【角色名】
_CHAR_PREFIX_RE = re.compile(r"^【(.+?)】(.*)$")


def _parse_srt_time(s: str) -> float:
    """SRT 時間字串 → 秒數."""
    m = _SRT_TIME_RE.match(s.strip())
    if not m:
        raise ValueError(f"無法解析 SRT 時間: {s}")
    h, mi, sec, ms = int(m[1]), int(m[2]), int(m[3]), int(m[4])
    return h * 3600 + mi * 60 + sec + ms / 1000


def parse_srt(srt_path: Path) -> list[dict]:
    """解析 SRT 檔案，回傳 [{start, end, character, dialogue}, ...].

    支援格式:
      - 【角色名】對白       → character = 角色名, dialogue = 對白
      - 純對白（無角色名）   → character = "", dialogue = 全文
    """
    text = srt_path.read_text(encoding="utf-8-sig")
    # 移除 BOM 殘留
    text = text.lstrip("﻿")

    entries = []
    blocks = re.split(r"\n\s*\n", text.strip())

    for block in blocks:
        lines = block.strip().split("\n")
        if len(lines) < 3:
            continue

        # 第一行: 序號（跳過）
        # 第二行: 時間軸
        time_line = lines[1].strip()
        time_match = re.match(
            r"(.+?)\s*-->\s*(.+?)$", time_line
        )
        if not time_match:
            continue

        try:
            start = _parse_srt_time(time_match[1])
            end = _parse_srt_time(time_match[2])
        except ValueError:
            continue

        # 第三行起: 字幕內容（可能多行）
        content = "\n".join(lines[2:]).strip()

        # 解析角色名前綴
        character = ""
        dialogue = content
        char_match = _CHAR_PREFIX_RE.match(content)
        if char_match:
            character = char_match[1]
            dialogue = char_match[2].strip()

        entries.append({
            "start": start,
            "end": end,
            "character": character,
            "dialogue": dialogue,
        })

    return entries


# ---------------------------------------------------------------------------
# timeline.json 解析（fallback）
# ---------------------------------------------------------------------------

def parse_timeline(timeline_path: Path) -> list[dict]:
    """解析 timeline.json，回傳與 SRT 相同格式的 list."""
    data = json.loads(timeline_path.read_text(encoding="utf-8"))
    entries = []
    for seg in data:
        ocr = seg.get("ocr") or {}
        entries.append({
            "start": seg.get("time_start", 0),
            "end": seg.get("time_end", 0),
            "character": ocr.get("character", ""),
            "dialogue": ocr.get("dialogue", ""),
        })
    return entries


# ---------------------------------------------------------------------------
# 音檔抽取
# ---------------------------------------------------------------------------

def extract_clips(
    video_path: Path,
    entries: list[dict],
    character: str,
    out_dir: Path,
    aliases: list[str] | None = None,
    padding_sec: float = 0.15,
) -> int:
    """從影片中抽出指定角色的語音片段.

    Args:
        video_path: 原始影片路徑
        entries: parse_srt() 或 parse_timeline() 的輸出
        character: 目標角色名
        out_dir: 輸出根資料夾
        aliases: 額外比對的角色名別名
        padding_sec: 前後各加的緩衝秒數

    Returns:
        抽出的片段數量
    """
    # 建比對集合
    match_names = {character}
    if aliases:
        match_names.update(aliases)

    # 篩選目標角色
    clips = [
        e for e in entries
        if e["character"] in match_names
    ]

    if not clips:
        return 0

    # 建輸出目錄: voices/{character}/{video_stem}/
    video_tag = _sanitize(video_path.stem, 40)
    clip_dir = out_dir / character / video_tag
    clip_dir.mkdir(parents=True, exist_ok=True)

    extracted = 0
    for i, clip in enumerate(clips, 1):
        t_start = max(0, clip["start"] - padding_sec)
        t_end = clip["end"] + padding_sec

        dialogue_tag = _sanitize(clip["dialogue"], 15)
        time_tag = _time_fmt(clip["start"])
        filename = f"{i:03d}_{time_tag}_{dialogue_tag}.wav"
        out_path = clip_dir / filename

        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-ss", _ffmpeg_ts(t_start),
            "-to", _ffmpeg_ts(t_end),
            "-vn",                    # 不要影像
            "-acodec", "pcm_s16le",   # WAV 16bit
            "-ar", "44100",           # 44.1kHz
            "-ac", "1",               # mono
            str(out_path),
        ]

        result = subprocess.run(
            cmd, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
        if result.returncode == 0:
            extracted += 1
        else:
            print(f"  [WARN] FFmpeg failed for clip {i}: {result.stderr[:200]}")

    return extracted


# ---------------------------------------------------------------------------
# 影片反查（批次用）
# ---------------------------------------------------------------------------

def _find_video_for_output(
    output_subdir: Path, video_dir: Path
) -> Path | None:
    """從 output 子目錄反查原始影片."""
    # source.txt 裡面可能有原始路徑
    source_txt = output_subdir / "source.txt"
    if source_txt.exists():
        raw = source_txt.read_text(encoding="utf-8").strip()
        p = Path(raw)
        if p.exists():
            return p
        # source.txt 可能只存檔名，遞迴找
        for mp4 in video_dir.rglob(p.name):
            return mp4

    # 用目錄名 fallback: {hash}_{video_stem_prefix}
    dirname = output_subdir.name
    parts = dirname.split("_", 1)
    if len(parts) > 1:
        stem_prefix = parts[1]
        for mp4 in video_dir.rglob("*.mp4"):
            if mp4.stem.startswith(stem_prefix[:20]):
                return mp4
    return None


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="角色語音抽取工具 — 從 SRT + 影片抽出指定角色語音"
    )
    parser.add_argument("--character", "-c", required=True,
                        help="目標角色名（如 ケイ）")
    parser.add_argument("--aliases", nargs="*", default=[],
                        help="角色別名（如 KEI）")
    parser.add_argument("--out", "-o", type=Path, default=None,
                        help="輸出資料夾（預設: voices/）")
    parser.add_argument("--padding", type=float, default=0.15,
                        help="前後緩衝秒數（預設 0.15）")
    parser.add_argument("--from-timeline", action="store_true",
                        help="使用 timeline.json 而非 SRT")

    sub = parser.add_subparsers(dest="mode")

    single = sub.add_parser("single", help="單支影片模式")
    single.add_argument("video", type=Path, help="影片路徑")
    single.add_argument("source", type=Path,
                        help="SRT 字幕檔（或 --from-timeline 時為 timeline.json）")

    batch = sub.add_parser("batch", help="批次模式")
    batch.add_argument("video_dir", type=Path, help="影片資料夾")
    batch.add_argument("output_dir", type=Path, help="pipeline 輸出資料夾")
    batch.add_argument("--srt-name", default="subtitle_original.srt",
                        help="SRT 檔名（預設 subtitle_original.srt）")

    args = parser.parse_args()

    if args.mode is None:
        parser.print_help()
        sys.exit(1)

    character = args.character
    aliases = args.aliases or []
    padding = args.padding
    use_timeline = args.from_timeline
    source_type = "timeline.json" if use_timeline else "SRT"

    if args.mode == "single":
        out_dir = args.out or Path("voices")

        # 解析來源
        if use_timeline:
            entries = parse_timeline(args.source)
        else:
            entries = parse_srt(args.source)

        # 統計
        match_names = {character, *aliases}
        total_entries = len(entries)
        char_entries = sum(1 for e in entries if e["character"] in match_names)

        print(f"[Voice] 角色: {character}")
        print(f"[Voice] 來源: {args.source} ({source_type}, {total_entries} 條)")
        print(f"[Voice] 命中: {char_entries} 條")
        print(f"[Voice] 影片: {args.video}")
        print(f"[Voice] 輸出: {out_dir}")

        if char_entries == 0:
            print(f"[Voice] {character} 不在這支影片中，跳過")
            return

        n = extract_clips(
            args.video, entries, character, out_dir,
            aliases=aliases, padding_sec=padding,
        )
        print(f"[Voice] 抽出 {n} 段語音")

    elif args.mode == "batch":
        out_dir = args.out or args.output_dir / "voices"
        srt_name = args.srt_name

        print(f"[Voice] 角色: {character}")
        print(f"[Voice] 影片目錄: {args.video_dir}")
        print(f"[Voice] 輸出目錄: {args.output_dir}")
        print(f"[Voice] 語音輸出: {out_dir}")

        # 掃描所有 output 子目錄
        if use_timeline:
            source_files = sorted(args.output_dir.rglob("timeline.json"))
            print(f"[Voice] 找到 {len(source_files)} 個 timeline.json")
        else:
            source_files = sorted(args.output_dir.rglob(srt_name))
            if not source_files:
                # fallback: 試找任何 .srt
                source_files = sorted(args.output_dir.rglob("*.srt"))
            print(f"[Voice] 找到 {len(source_files)} 個 SRT")

        total = 0
        match_names = {character, *aliases}

        for sf in source_files:
            video = _find_video_for_output(sf.parent, args.video_dir)
            if video is None:
                print(f"  [SKIP] 找不到影片: {sf.parent.name}")
                continue

            if use_timeline:
                entries = parse_timeline(sf)
            else:
                entries = parse_srt(sf)

            char_count = sum(1 for e in entries if e["character"] in match_names)
            if char_count == 0:
                continue

            n = extract_clips(
                video, entries, character, out_dir,
                aliases=aliases, padding_sec=padding,
            )
            if n > 0:
                print(f"  [{n:3d} clips] {video.name}")
                total += n

        print(f"\n[Voice] 總計抽出 {total} 段 {character} 語音")


if __name__ == "__main__":
    main()
