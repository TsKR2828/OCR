"""sfx_selector — SRT 字幕自動配音效.

讀取 SRT，根據文字語氣/關鍵字建議搭配的音效，
輸出 JSON 配對檔給 premiere_setup.jsx 使用。

範例：
    python sfx_selector.py subtitle.srt -o premiere_config.json
    python sfx_selector.py subtitle.srt --preview
    python sfx_selector.py subtitle.srt --rules config/sfx_rules.yaml
"""

import json
import re
import sys
from pathlib import Path
from dataclasses import dataclass, field

import typer

sys.stdout.reconfigure(encoding="utf-8")

app = typer.Typer(help="SRT 字幕自動配音效")

SFX_LIB_DEFAULT = Path(r"E:\影片剪輯\常用素材\音效")
STYLE_DEFAULT = Path(r"E:\影片剪輯\常用素材\字幕樣式\apple.prtextstyle")


# ── SRT parser ────────────────────────────────────────────────────────────


@dataclass
class SrtEntry:
    index: int
    start: float
    end: float
    text: str


def _parse_srt_time(t: str) -> float:
    h, m, rest = t.strip().split(":")
    s, ms = rest.split(",")
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000


def parse_srt(path: Path) -> list[SrtEntry]:
    raw = path.read_text(encoding="utf-8-sig")
    blocks = re.split(r"\n\s*\n", raw.strip())
    entries: list[SrtEntry] = []
    for block in blocks:
        lines = block.strip().split("\n")
        if len(lines) < 2:
            continue
        try:
            idx = int(lines[0].strip())
        except ValueError:
            continue
        m = re.match(r"(\S+)\s*-->\s*(\S+)", lines[1].strip())
        if not m:
            continue
        start = _parse_srt_time(m.group(1))
        end = _parse_srt_time(m.group(2))
        body = "\n".join(lines[2:]).strip() if len(lines) > 2 else ""
        entries.append(SrtEntry(idx, start, end, body))
    return entries


# ── Rule engine ───────────────────────────────────────────────────────────


@dataclass
class SfxRule:
    sfx: str
    name: str
    keywords: list[str] = field(default_factory=list)
    patterns: list[str] = field(default_factory=list)
    weight: float = 0.6


BUILTIN_RULES: list[dict] = [
    # ── 驚嘆/讚嘆 ──
    {"sfx": "#WOW.mp3", "name": "驚嘆",
     "keywords": ["好厲害", "太厲害", "厲害", "好強", "太強", "好帥", "太帥",
                   "好美", "太美", "超猛", "天才", "太扯", "誇張",
                   "空前絕後", "大幅提升", "佩服"],
     "patterns": [r"好.+[啊呀哦喔]$", r"也太.+了"], "weight": 0.8},
    # ── 疑問/困惑 ──
    {"sfx": "What？男聲.mp3", "name": "疑問",
     "keywords": ["什麼", "蛤", "啥", "咦", "欸", "為什麼", "怎麼會",
                   "不會吧", "真假", "怎麼可能", "何關聯", "怎麼現在"],
     "patterns": [r"[？?]{2,}", r"^[蛤啥欸咦]",
                  r"怎麼.{0,6}[？?]?$"], "weight": 0.7},
    # ── 糟糕/完蛋 ──
    {"sfx": "#OH NO.mp3", "name": "糟糕",
     "keywords": ["糟糕", "完蛋", "慘了", "不好了", "死定了", "涼了", "掰掰",
                   "你自找的", "別怪"],
     "weight": 0.7},
    # ── 爆炸/震驚 ──
    {"sfx": "#爆炸.mp3", "name": "爆炸驚訝",
     "keywords": ["居然", "竟然", "嚇死", "天啊", "我的天", "傻眼", "崩潰",
                   "不敢相信", "死全家", "揍死", "打死"],
     "patterns": [r"[！!]{2,}", r"看我不把你", r"死全家"],
     "weight": 0.75},
    # ── 搞笑/吐槽 ──
    {"sfx": "#噗資嗯.mp3", "name": "搞笑吐槽",
     "keywords": ["哈哈", "笑死", "好笑", "欸不是", "什麼啦", "拜託", "有夠",
                   "超好笑", "笑爛", "臭八婆", "吃屎", "狗渣",
                   "好過分", "沒禮貌", "呵呵"],
     "patterns": [r"[哈呵]{2,}", r"[wW]{2,}", r"XD",
                  r"也太.+了吧"], "weight": 0.6},
    # ── 輕吐槽/無奈 ──
    {"sfx": "#常用-噗03.mp3", "name": "輕吐槽",
     "keywords": ["呃", "唉", "好吧", "是喔", "這樣喔", "真的假的", "隨便",
                   "算了", "誰相信", "誰信"],
     "weight": 0.5},
    # ── 出糗/翻車 ──
    {"sfx": "#綜藝叮咚嗚趴趴.mp3", "name": "出糗",
     "keywords": ["尷尬", "丟臉", "出糗", "失敗", "搞砸", "翻車", "GG", "gg",
                   "撒謊", "被打", "又被"],
     "weight": 0.65},
    # ── 重擊/威嚇 ──
    {"sfx": "#常用-咚重擊.mp3", "name": "重點強調",
     "keywords": ["重點是", "注意", "就是說", "原來如此", "所以說", "結論",
                   "閉嘴", "給我", "我警告你", "上"],
     "patterns": [r"^(閉嘴|給我|我警告)", r"們上$"],
     "weight": 0.55},
    # ── 提示/轉場 ──
    {"sfx": "#叮咚.mp3", "name": "提示轉場",
     "keywords": ["對了", "話說", "接下來", "不過", "但是", "想了一下"],
     "weight": 0.4},
    # ── 昇天/感動 ──
    {"sfx": "#天使升天聲.mp3", "name": "昇天感動",
     "keywords": ["好可愛", "太可愛", "可愛", "感動", "幸福", "天堂", "昇天",
                   "戀愛", "順眼"],
     "weight": 0.7},
    # ── 閃亮/登場 ──
    {"sfx": "#閃亮亮魔法聲.mp3", "name": "閃亮登場",
     "keywords": ["登場", "出現", "變身", "魔法", "特別", "全新"], "weight": 0.6},
    # ── 快速/動作 ──
    {"sfx": "#唰.mp3", "name": "快速動作",
     "keywords": ["衝啊", "跑", "閃開", "瞬間", "馬上", "拖出去"],
     "patterns": [r"^.{1,4}[！!]$"], "weight": 0.5},
    # ── 嚴肅/壓迫 ──
    {"sfx": "#低沉端喔.mp3", "name": "嚴肅壓迫",
     "keywords": ["危險", "可怕", "恐怖", "不妙", "緊張", "殺", "賭殺"],
     "patterns": [r"殺.{0,4}(人|此人)"], "weight": 0.55},
]

DEFAULT_DENSITY = {
    "min_gap_sec": 3.0,
    "max_per_minute": 5,
    "confidence_threshold": 0.3,
}


def _load_rules(rules_path: Path | None) -> tuple[list[SfxRule], dict]:
    rules_data = BUILTIN_RULES
    density = dict(DEFAULT_DENSITY)

    if rules_path and rules_path.exists():
        try:
            import yaml
            data = yaml.safe_load(rules_path.read_text(encoding="utf-8"))
            if data.get("rules"):
                rules_data = data["rules"]
            if data.get("density"):
                density.update(data["density"])
        except ImportError:
            typer.echo("[warn] pyyaml 未安裝，使用內建規則", err=True)

    rules = [
        SfxRule(
            sfx=r["sfx"], name=r["name"],
            keywords=r.get("keywords", []),
            patterns=r.get("patterns", []),
            weight=r.get("weight", 0.5),
        )
        for r in rules_data
    ]
    return rules, density


# ── Scoring ───────────────────────────────────────────────────────────────


def _score(entry: SrtEntry, rule: SfxRule) -> float:
    text = entry.text
    score = 0.0

    for kw in rule.keywords:
        if kw in text:
            score += 0.5
            if text.startswith(kw) or text.endswith(kw):
                score += 0.15

    for pat in rule.patterns:
        if re.search(pat, text):
            score += 0.4

    score *= rule.weight

    tlen = len(text.replace("\n", ""))
    if tlen < 2:
        score *= 0.3
    elif tlen > 50:
        score *= 0.6

    return min(score, 1.0)


# ── Selection ─────────────────────────────────────────────────────────────


@dataclass
class SfxMatch:
    srt_index: int
    start: float
    end: float
    text: str
    sfx: str
    sfx_path: str
    confidence: float
    rule_name: str


def _select(
    entries: list[SrtEntry],
    rules: list[SfxRule],
    density: dict,
    sfx_lib: Path,
) -> list[SfxMatch]:
    matches: list[SfxMatch] = []
    last_t = -999.0
    min_gap = density["min_gap_sec"]
    thresh = density["confidence_threshold"]

    for entry in entries:
        best_s, best_r = 0.0, None
        for rule in rules:
            s = _score(entry, rule)
            if s > best_s:
                best_s, best_r = s, rule

        if best_r is None or best_s < thresh:
            continue
        if entry.start - last_t < min_gap:
            continue

        matches.append(SfxMatch(
            srt_index=entry.index, start=entry.start, end=entry.end,
            text=entry.text, sfx=best_r.sfx,
            sfx_path=str(sfx_lib / best_r.sfx),
            confidence=round(best_s, 3), rule_name=best_r.name,
        ))
        last_t = entry.start

    max_pm = density["max_per_minute"]
    if max_pm > 0 and matches and entries:
        total_dur = entries[-1].end - entries[0].start
        cap = max(1, int(total_dur / 60 * max_pm) + 1)
        if len(matches) > cap:
            matches.sort(key=lambda m: -m.confidence)
            matches = matches[:cap]
            matches.sort(key=lambda m: m.start)

    return matches


# ── CLI ───────────────────────────────────────────────────────────────────


def _ts(sec: float) -> str:
    m, s = divmod(sec, 60)
    return f"{int(m):02d}:{s:05.2f}"


@app.command()
def main(
    srt_file: Path = typer.Argument(..., help="SRT 字幕檔路徑"),
    video: Path = typer.Option(
        None, "--video", "-v", help="影片檔路徑（寫入 JSON 供 Premiere 用）"),
    sfx_lib: Path = typer.Option(
        SFX_LIB_DEFAULT, "--sfx-lib", help="音效素材庫目錄"),
    style: Path = typer.Option(
        STYLE_DEFAULT, "--style", help="字幕樣式檔路徑"),
    rules_file: Path = typer.Option(
        None, "--rules", "-r", help="自訂規則 YAML"),
    output: Path = typer.Option(
        None, "--output", "-o", help="輸出 JSON（預設 <srt>.sfx.json）"),
    preview: bool = typer.Option(
        False, "--preview", "-p", help="只預覽不寫檔"),
    min_gap: float = typer.Option(
        None, "--min-gap", help="覆寫：兩個音效最少間隔秒數"),
    max_pm: int = typer.Option(
        None, "--max-pm", help="覆寫：每分鐘最多幾個音效"),
):
    """讀 SRT，自動建議音效搭配，輸出 JSON 給 premiere_setup.jsx."""
    if not srt_file.exists():
        typer.echo(f"找不到 SRT: {srt_file}", err=True)
        raise typer.Exit(1)

    entries = parse_srt(srt_file)
    typer.echo(f"[sfx_selector] {len(entries)} 行字幕")

    rules, density = _load_rules(rules_file)
    if min_gap is not None:
        density["min_gap_sec"] = min_gap
    if max_pm is not None:
        density["max_per_minute"] = max_pm

    matches = _select(entries, rules, density, sfx_lib)

    total_dur = entries[-1].end if entries else 0
    rate = len(matches) / (total_dur / 60) if total_dur > 0 else 0
    typer.echo(f"[sfx_selector] {len(matches)} 個音效配對 "
               f"({rate:.1f}/min)\n")

    for m in matches:
        typer.echo(
            f"  {_ts(m.start)}  [{m.rule_name:<6s}] "
            f"{m.confidence:.0%}  {m.sfx:<28s} "
            f"「{m.text[:35]}」"
        )

    if preview:
        return

    out_path = output or srt_file.with_suffix(".sfx.json")
    result = {
        "srt_file": str(srt_file.resolve()),
        "video_file": str(video.resolve()) if video else "",
        "sfx_lib": str(sfx_lib),
        "subtitle_style": str(style),
        "total_entries": len(entries),
        "total_sfx": len(matches),
        "assignments": [
            {
                "srt_index": m.srt_index,
                "start": m.start,
                "end": m.end,
                "text": m.text,
                "sfx": m.sfx,
                "sfx_path": m.sfx_path,
                "confidence": m.confidence,
                "rule": m.rule_name,
            }
            for m in matches
        ],
    }
    out_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    typer.echo(f"\n=> {out_path}")


if __name__ == "__main__":
    app()
