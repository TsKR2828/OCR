"""make_fcpxml — 從 timeline.json 產 Premiere 2023 可匯入的 FCPXML 審稿時間軸.

⚠️ 實驗性（2026-06-13）：FCPXML 結構已嚴格自驗（well-formed / frame 對齊 /
   引用解析 / offset 連續 / 媒體路徑存在），但「Premiere 是否真的吃這個格式」
   尚未在 Premiere 端驗證過。確認能乾淨匯入後再考慮收進 pipeline。

把選中的精彩片段（引用原始影片 + in/out）依序排上 V1，附原音訊，輸出：
- <stem>.fcpxml ：時間軸（--markers 會在每段加一個精彩點標記）
- <stem>.srt    ：對齊「這條序列」時間的字幕（拖進時間軸 = caption 軌）

範例：
    python make_fcpxml.py "影片.mp4" -t output/xxx/timeline.json \
        -s output/xxx/subtitle_streamer.srt -o output/xxx --top-n 2 --markers
"""

import subprocess
from pathlib import Path
from typing import Optional

import typer

from src.schema import load_timeline
from src.clipper import _parse_srt_time

app = typer.Typer(help="產 Premiere FCPXML 審稿時間軸（實驗性）")


def _probe(video: Path):
    def q(entry, stream=False):
        sel = ["-select_streams", "v:0"] if stream else []
        cmd = ["ffprobe", "-v", "error", *sel, "-show_entries", entry,
               "-of", "csv=p=0", str(video)]
        return subprocess.run(cmd, capture_output=True, text=True).stdout.strip()
    num, den = q("stream=r_frame_rate", stream=True).split("/")
    fps = int(num) / int(den)
    w = int(q("stream=width", stream=True))
    h = int(q("stream=height", stream=True))
    dur = float(q("format=duration"))
    return fps, w, h, dur


def _esc(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def _pick_highlights(segments, top_n: int, separation: float):
    """挑分數最高、彼此間隔 > separation 秒的 top_n 段."""
    ranked = sorted(segments, key=lambda s: s.score.total, reverse=True)
    picks = []
    for s in ranked:
        if all(abs(s.time_start - p.time_start) > separation for p in picks):
            picks.append(s)
        if len(picks) >= top_n:
            break
    picks.sort(key=lambda s: s.time_start)
    return picks


def build_fcpxml(video: Path, clips: list[dict], fps_i: int, w: int, h: int,
                 total_src_f: int, seq_total_f: int, with_markers: bool) -> str:
    """組 FCPXML 字串。clips: [{sf,ef,peak,label}]（單位 frame）."""
    tb = fps_i * 100                      # timebase 分母（30→3000）
    fd = tb // fps_i                      # frameDuration 分子（→100）

    def t(frames: int) -> str:
        return f"{frames * fd}/{tb}s"

    src_uri = _esc(video.resolve().as_uri())
    head = f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE fcpxml>
<fcpxml version="1.9">
  <resources>
    <format id="r1" name="FFVideoFormat{h}p{fps_i}" frameDuration="{fd}/{tb}s" width="{w}" height="{h}" colorSpace="1-1-1 (Rec. 709)"/>
    <asset id="r2" name="{_esc(video.stem)}" start="0s" duration="{t(total_src_f)}" hasVideo="1" hasAudio="1" videoSources="1" audioSources="1" audioChannels="2" audioRate="44100" format="r1">
      <media-rep kind="original-media" src="{src_uri}"/>
    </asset>
  </resources>
  <library>
    <event name="VN-Transcribe Review">
      <project name="review">
        <sequence format="r1" duration="{t(seq_total_f)}" tcStart="0s" tcFormat="NDF" audioLayout="stereo" audioRate="44100">
          <spine>'''
    body = head
    offset = 0
    for i, c in enumerate(clips, 1):
        sf, ef, peak = c["sf"], c["ef"], c["peak"]
        label = _esc(c["label"])
        dur_f = ef - sf
        marker = ""
        if with_markers:
            marker = (f'\n              <marker start="{t(peak)}" '
                      f'duration="{t(1)}" value="{label}"/>')
        body += (
            f'\n            <asset-clip ref="r2" offset="{t(offset)}" '
            f'name="clip{i} {label}" start="{t(sf)}" duration="{t(dur_f)}" '
            f'format="r1" tcFormat="NDF">{marker}\n            </asset-clip>'
        )
        offset += dur_f
    return body + '''
          </spine>
        </sequence>
      </project>
    </event>
  </library>
</fcpxml>
'''


def build_fcp7xml(video: Path, clips: list[dict], fps_i: int, w: int, h: int,
                  total_src_f: int, seq_total_f: int, with_markers: bool,
                  with_audio: bool = True) -> str:
    """組 Final Cut Pro 7 XML (xmeml) — Premiere 2023 原生支援，免插件。時間單位=frame。"""
    pathurl = _esc(video.resolve().as_uri().replace("file:///", "file://localhost/"))
    fname = _esc(video.name)
    rate = f"<rate><timebase>{fps_i}</timebase><ntsc>FALSE</ntsc></rate>"

    # 完整 file 定義（第一個 clip 用），後續 clip 用 <file id="file-1"/> 引用
    file_full = (
        f'<file id="file-1"><name>{fname}</name><pathurl>{pathurl}</pathurl>'
        f'{rate}<duration>{total_src_f}</duration><media>'
        f'<video><samplecharacteristics>{rate}<width>{w}</width><height>{h}</height>'
        f'</samplecharacteristics></video>'
        f'<audio><samplecharacteristics><depth>16</depth><samplerate>44100</samplerate>'
        f'</samplecharacteristics><channelcount>2</channelcount></audio>'
        f'</media></file>'
    )

    def items(prefix: str, audio: bool) -> str:
        out, offset = [], 0
        for i, c in enumerate(clips, 1):
            sf, ef = c["sf"], c["ef"]
            label = _esc(c["label"])
            dur_f = ef - sf
            fileref = file_full if (i == 1 and not audio) else '<file id="file-1"/>'
            src = ('<sourcetrack><mediatype>audio</mediatype><trackindex>1</trackindex>'
                   '</sourcetrack>') if audio else ''
            out.append(
                f'<clipitem id="{prefix}-{i}"><name>clip{i} {label}</name>'
                f'<enabled>TRUE</enabled><duration>{total_src_f}</duration>{rate}'
                f'<start>{offset}</start><end>{offset + dur_f}</end>'
                f'<in>{sf}</in><out>{ef}</out>{fileref}{src}</clipitem>'
            )
            offset += dur_f
        return "".join(out)

    v_track = f"<track>{items('vclip', False)}</track>"
    a_block = ""
    if with_audio:
        a_block = (
            '<audio><numOutputChannels>2</numOutputChannels><format>'
            '<samplecharacteristics><depth>16</depth><samplerate>44100</samplerate>'
            f'</samplecharacteristics></format><track>{items("aclip", True)}</track></audio>'
        )

    markers, offset = "", 0
    if with_markers:
        for c in clips:
            tl_peak = offset + (c["peak"] - c["sf"])
            markers += (f'<marker><name>{_esc(c["label"])}</name><comment></comment>'
                        f'<in>{tl_peak}</in><out>-1</out></marker>')
            offset += c["ef"] - c["sf"]

    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE xmeml>\n<xmeml version="4">\n'
        f'<sequence id="review"><name>review</name><duration>{seq_total_f}</duration>{rate}'
        f'<media><video><format><samplecharacteristics>{rate}'
        f'<width>{w}</width><height>{h}</height><pixelaspectratio>square</pixelaspectratio>'
        f'</samplecharacteristics></format>{v_track}</video>{a_block}</media>'
        f'{markers}</sequence>\n</xmeml>\n'
    )


def build_sequence_srt(streamer_srt: Path, clips: list[dict], fps_i: int) -> str:
    """把原片字幕切片+平移成「這條序列」時間軸的 SRT."""
    raw = streamer_srt.read_text(encoding="utf-8-sig")
    blocks = [b for b in raw.replace("\r", "").split("\n\n") if b.strip()]

    def fmt(x: float) -> str:
        ms = int(round(x * 1000)); h = ms // 3600000; ms %= 3600000
        m = ms // 60000; ms %= 60000; s = ms // 1000; ms %= 1000
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    out, idx, seq_off = [], 0, 0.0
    for c in clips:
        s_sec, e_sec = c["sf"] / fps_i, c["ef"] / fps_i
        dur = e_sec - s_sec
        for blk in blocks:
            ls = blk.split("\n")
            ti = next((j for j, l in enumerate(ls) if "-->" in l), -1)
            if ti < 0:
                continue
            L, _, R = ls[ti].partition("-->")
            try:
                t0, t1 = _parse_srt_time(L), _parse_srt_time(R)
            except Exception:
                continue
            if t1 <= s_sec or t0 >= e_sec:
                continue
            ns = seq_off + max(0.0, t0 - s_sec)
            ne = seq_off + min(dur, t1 - s_sec)
            if ne - ns < 0.25:          # 跳過邊緣碎片
                continue
            text = "\n".join(ls[ti + 1:]).strip()
            if not text:
                continue
            idx += 1
            out.append(f"{idx}\n{fmt(ns)} --> {fmt(ne)}\n{text}\n")
        seq_off += dur
    return "\n".join(out)


@app.command()
def main(
    video: Path = typer.Argument(..., help="原始影片檔"),
    timeline: Path = typer.Option(..., "--timeline", "-t", help="timeline.json"),
    srt: Optional[Path] = typer.Option(None, "--srt", "-s", help="實況主軌 SRT（產序列字幕用）"),
    output: Path = typer.Option(Path("."), "--output", "-o", help="輸出目錄"),
    stem: str = typer.Option("review", "--stem", help="輸出檔名前綴"),
    top_n: int = typer.Option(2, "--top-n", help="挑幾段精彩片段"),
    pad: float = typer.Option(3.0, "--pad", help="每段前後 padding 秒"),
    separation: float = typer.Option(60.0, "--separation", help="片段彼此最小間隔秒"),
    markers: bool = typer.Option(False, "--markers", help="每段加一個精彩點 marker"),
    fmt: str = typer.Option("fcp7", "--format", help="fcp7（.xml，Premiere 原生免插件）| fcpxml（.fcpxml，FCP X）"),
):
    """產 Premiere 審稿時間軸 + 序列字幕.

    --format fcp7（預設）：Final Cut Pro 7 XML，Premiere 2023 原生匯入、免插件。
    --format fcpxml      ：FCP X 格式（Premiere 原生不吃，需轉換工具）。
    """
    if not video.exists() or not timeline.exists():
        typer.echo("找不到影片或 timeline.json", err=True)
        raise typer.Exit(1)

    fps, w, h, dur = _probe(video)
    fps_i = round(fps)

    def f(sec: float) -> int:
        return round(sec * fps_i)

    segments = load_timeline(timeline)
    picks = _pick_highlights(segments, top_n, separation)
    if not picks:
        typer.echo("沒有精彩片段可選", err=True)
        raise typer.Exit(1)

    clips = []
    for s in picks:
        a = max(0.0, s.time_start - pad)
        b = min(dur, s.time_end + pad)
        clips.append({"sf": f(a), "ef": f(b), "peak": f(s.time_start),
                      "label": f"{s.scene_type} score={s.score.total:.0f}"})
    seq_total_f = sum(c["ef"] - c["sf"] for c in clips)

    output.mkdir(parents=True, exist_ok=True)
    if fmt == "fcp7":
        xml = build_fcp7xml(video, clips, fps_i, w, h, f(dur), seq_total_f, markers)
        out_path = output / f"{stem}.xml"
        kind = "FCP7-XML"
    else:
        xml = build_fcpxml(video, clips, fps_i, w, h, f(dur), seq_total_f, markers)
        out_path = output / f"{stem}.fcpxml"
        kind = "FCPXML"
    out_path.write_text(xml, encoding="utf-8")
    typer.echo(f"[{kind}] {out_path}  ({len(clips)} 段, {seq_total_f/fps_i:.0f}s, "
               f"{w}x{h}@{fps_i}fps{', +markers' if markers else ''})")

    if srt and srt.exists():
        seq_srt = build_sequence_srt(srt, clips, fps_i)
        srt_path = output / f"{stem}.srt"
        srt_path.write_text(seq_srt, encoding="utf-8-sig")
        typer.echo(f"[FCPXML] {srt_path}  ({seq_srt.count('-->')} 條序列字幕)")


if __name__ == "__main__":
    app()
