"""Ground Truth 比對工具 — 拿 pipeline SRT 輸出和手抄 Excel 對白比較準確率.

用法:
  # 比對單個分頁
  python compare_gt.py <srt_file> <excel_file> --sheet "SideA 第1話 セカンドポジション"

  # 比對整個 Excel（列出各分頁統計）
  python compare_gt.py --list-sheets <excel_file>

  # 從 timeline.json 比對
  python compare_gt.py <timeline.json> <excel_file> --sheet "..." --from-timeline
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import openpyxl


# ---------------------------------------------------------------------------
# Excel Ground Truth 解析
# ---------------------------------------------------------------------------

def parse_excel_sheet(excel_path: Path, sheet_name: str) -> list[dict]:
    """解析 Excel 單一分頁，回傳 [{character, dialogue}, ...].

    規則：
    - Row 1 = header，跳過
    - Row 2 = 章節標題，跳過
    - Column A = 角色名（空白 = 延續上一個角色的台詞）
    - Column B = 日文原文台詞
    - 音效行（Column A 有值但 Column B 無值）跳過
    """
    wb = openpyxl.load_workbook(str(excel_path), read_only=True)
    if sheet_name not in wb.sheetnames:
        wb.close()
        raise ValueError(f"找不到分頁: {sheet_name}\n可用: {wb.sheetnames[:5]}...")

    ws = wb[sheet_name]
    entries: list[dict] = []
    current_char = ""

    for i, row in enumerate(ws.iter_rows(min_col=1, max_col=2, values_only=True), 1):
        if i <= 2:
            continue

        char_cell = str(row[0]).strip() if row[0] else ""
        dialogue_cell = str(row[1]).strip() if row[1] else ""

        if not dialogue_cell:
            continue

        if char_cell:
            current_char = char_cell

        entries.append({
            "character": current_char,
            "dialogue": dialogue_cell,
        })

    wb.close()
    return entries


def list_excel_sheets(excel_path: Path) -> list[dict]:
    """列出 Excel 所有分頁及其對白數量."""
    wb = openpyxl.load_workbook(str(excel_path), read_only=True)
    results = []
    for name in wb.sheetnames:
        ws = wb[name]
        count = 0
        chars = set()
        for i, row in enumerate(ws.iter_rows(min_col=1, max_col=2, values_only=True), 1):
            if i <= 2:
                continue
            dialogue = str(row[1]).strip() if row[1] else ""
            char = str(row[0]).strip() if row[0] else ""
            if dialogue:
                count += 1
            if char and dialogue:
                chars.add(char)
        results.append({"name": name, "lines": count, "characters": sorted(chars)})
    wb.close()
    return results


# ---------------------------------------------------------------------------
# SRT 解析
# ---------------------------------------------------------------------------

_SRT_TIME_RE = re.compile(r"(\d{1,2}):(\d{2}):(\d{2})[,.](\d{3})")
_CHAR_PREFIX_RE = re.compile(r"^【(.+?)】(.*)$")


def _parse_srt_time(s: str) -> float:
    m = _SRT_TIME_RE.match(s.strip())
    if not m:
        return 0.0
    h, mi, sec, ms = int(m[1]), int(m[2]), int(m[3]), int(m[4])
    return h * 3600 + mi * 60 + sec + ms / 1000


def parse_srt(srt_path: Path) -> list[dict]:
    """解析 SRT 檔案，回傳 [{character, dialogue, start, end}, ...]."""
    text = srt_path.read_text(encoding="utf-8-sig").lstrip("﻿")
    entries = []
    blocks = re.split(r"\n\s*\n", text.strip())

    for block in blocks:
        lines = block.strip().split("\n")
        if len(lines) < 3:
            continue

        time_line = lines[1].strip()
        time_match = re.match(r"(.+?)\s*-->\s*(.+?)$", time_line)
        if not time_match:
            continue

        start = _parse_srt_time(time_match[1])
        end = _parse_srt_time(time_match[2])
        content = "\n".join(lines[2:]).strip()

        character = ""
        dialogue = content
        char_match = _CHAR_PREFIX_RE.match(content)
        if char_match:
            character = char_match[1]
            dialogue = char_match[2].strip()

        entries.append({
            "character": character,
            "dialogue": dialogue,
            "start": start,
            "end": end,
        })

    return entries


# ---------------------------------------------------------------------------
# Timeline.json 解析
# ---------------------------------------------------------------------------

def parse_timeline(timeline_path: Path, prefer_asr: bool = False) -> list[dict]:
    """解析 timeline.json，回傳和 SRT 相同格式.

    prefer_asr=True 時優先使用 ASR 文字（測量 ASR 獨立品質用）。
    """
    data = json.loads(timeline_path.read_text(encoding="utf-8"))
    entries = []
    for seg in data:
        ocr = seg.get("ocr") or {}
        asr = seg.get("asr") or {}

        if prefer_asr:
            dialogue = ""
            if asr.get("speaker_guess") == "game_voice":
                dialogue = asr.get("text", "")
            if not dialogue:
                dialogue = ocr.get("dialogue", "")
        else:
            dialogue = ocr.get("dialogue", "")
            if not dialogue:
                if asr.get("speaker_guess") == "game_voice":
                    dialogue = asr.get("text", "")

        if not dialogue:
            continue
        entries.append({
            "character": ocr.get("character", "") or "",
            "dialogue": dialogue,
            "start": seg.get("time_start", 0),
            "end": seg.get("time_end", 0),
        })
    return entries


# ---------------------------------------------------------------------------
# 比對演算法
# ---------------------------------------------------------------------------

def _edit_distance(a: str, b: str) -> int:
    if len(a) < len(b):
        return _edit_distance(b, a)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a):
        curr = [i + 1]
        for j, cb in enumerate(b):
            curr.append(min(prev[j + 1] + 1, curr[j] + 1,
                            prev[j] + (0 if ca == cb else 1)))
        prev = curr
    return prev[-1]


def _similarity(a: str, b: str) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    dist = _edit_distance(a, b)
    return 1.0 - dist / max(len(a), len(b))


def _normalize_for_compare(text: str) -> str:
    """正規化文字以利比對（移除全形空白、標點差異等）."""
    text = text.replace("\n", "")
    text = text.replace("　", "").replace(" ", "")
    text = text.replace("⋯", "…").replace("．．．", "…")
    text = text.replace("．", ".").replace("，", "、")
    text = text.replace("？", "?").replace("！", "!")
    return text.strip()


_SENTENCE_SPLIT_RE = re.compile(r"(?<=[。？！?!」）\)…])")


def _split_sentences(entries: list[dict], min_part_len: int = 4) -> list[dict]:
    """把長 ASR 段落拆成句子，讓比對粒度接近 GT.

    日文 Whisper 常不加句號，所以也在「、」處嘗試拆分，
    但只接受兩邊都 >= min_part_len 的拆法。
    """
    result = []
    for e in entries:
        text = e["dialogue"]

        # 1) 先試句號 / 問號 / 驚嘆號拆
        parts = _SENTENCE_SPLIT_RE.split(text)
        parts = [p.strip() for p in parts if p.strip()]

        # 2) 如果沒拆開（Whisper 不加句號），嘗試用「、」拆
        if len(parts) <= 1 and "、" in text:
            comma_parts = text.split("、")
            # 只接受每段都夠長的拆法（避免把「ケイに頼まれて、あんたを迎えに来た」拆壞）
            if all(len(p.strip()) >= min_part_len for p in comma_parts):
                parts = [p.strip() for p in comma_parts if p.strip()]

        if len(parts) <= 1:
            result.append(e)
            continue

        dur = e.get("end", 0) - e.get("start", 0)
        total_len = sum(len(p) for p in parts)
        t = e.get("start", 0)
        for p in parts:
            frac = len(p) / total_len if total_len else 1.0 / len(parts)
            seg_dur = dur * frac
            result.append({
                "character": e["character"],
                "dialogue": p,
                "start": t,
                "end": t + seg_dur,
            })
            t += seg_dur
    return result


def align_and_compare(
    gt_entries: list[dict],
    pipeline_entries: list[dict],
    name_map: dict[str, str] | None = None,
) -> dict:
    """對齊 ground truth 和 pipeline 輸出，計算準確率.

    使用貪婪序列比對：對每個 GT 行，在 pipeline 中找最相似的對白。

    name_map: 名字映射，如 {"風見咲月": "風見早希"}
    """
    if name_map is None:
        name_map = {}

    # 正規化 GT 角色名
    gt_normalized = []
    for g in gt_entries:
        char = g["character"]
        if char in name_map:
            char = name_map[char]
        gt_normalized.append({**g, "character": char})

    # 逐句比對（順序貪婪）
    results = []
    used_pipeline = set()

    for gt in gt_normalized:
        gt_dial = _normalize_for_compare(gt["dialogue"])
        best_sim = 0.0
        best_idx = -1

        for i, p in enumerate(pipeline_entries):
            if i in used_pipeline:
                continue
            p_dial = _normalize_for_compare(p["dialogue"])
            sim = _similarity(gt_dial, p_dial)
            if sim > best_sim:
                best_sim = sim
                best_idx = i

        match = None
        if best_sim >= 0.3 and best_idx >= 0:
            match = pipeline_entries[best_idx]
            used_pipeline.add(best_idx)

        results.append({
            "gt_character": gt["character"],
            "gt_dialogue": gt["dialogue"],
            "matched": match is not None,
            "pipeline_character": match["character"] if match else "",
            "pipeline_dialogue": match["dialogue"] if match else "",
            "dialogue_similarity": best_sim if match else 0.0,
            "character_correct": (
                match is not None
                and gt["character"] == match["character"]
            ),
        })

    # 統計
    total = len(results)
    matched = sum(1 for r in results if r["matched"])
    char_correct = sum(1 for r in results if r["character_correct"])
    avg_sim = (sum(r["dialogue_similarity"] for r in results) / total) if total else 0

    gt_chars = set(g["character"] for g in gt_normalized if g["character"])
    pipeline_chars = set(p["character"] for p in pipeline_entries if p["character"])

    stats = {
        "total_gt_lines": total,
        "matched_lines": matched,
        "match_rate": matched / total if total else 0,
        "character_accuracy": char_correct / matched if matched else 0,
        "avg_dialogue_similarity": avg_sim,
        "gt_characters": sorted(gt_chars),
        "pipeline_characters": sorted(pipeline_chars),
        "character_coverage": sorted(gt_chars & pipeline_chars),
        "missing_characters": sorted(gt_chars - pipeline_chars),
        "extra_characters": sorted(pipeline_chars - gt_chars),
    }

    return {"results": results, "stats": stats}


# ---------------------------------------------------------------------------
# 報告輸出
# ---------------------------------------------------------------------------

def print_report(comparison: dict, verbose: bool = False) -> None:
    stats = comparison["stats"]
    results = comparison["results"]

    print("\n" + "=" * 60)
    print("Ground Truth 比對報告")
    print("=" * 60)

    print(f"\n【整體統計】")
    print(f"  GT 台詞數:        {stats['total_gt_lines']}")
    print(f"  配對成功:          {stats['matched_lines']} ({stats['match_rate']:.1%})")
    print(f"  角色名準確率:      {stats['character_accuracy']:.1%} (配對成功的行)")
    print(f"  對白平均相似度:    {stats['avg_dialogue_similarity']:.1%}")

    print(f"\n【角色統計】")
    print(f"  GT 角色:    {', '.join(stats['gt_characters'])}")
    print(f"  Pipeline:   {', '.join(stats['pipeline_characters']) or '(無)'}")
    print(f"  正確偵測:   {', '.join(stats['character_coverage']) or '(無)'}")
    if stats["missing_characters"]:
        print(f"  漏掉:       {', '.join(stats['missing_characters'])}")
    if stats["extra_characters"]:
        print(f"  多出:       {', '.join(stats['extra_characters'])}")

    if verbose:
        print(f"\n【逐句比對】")
        for i, r in enumerate(results, 1):
            status = "✓" if r["matched"] else "✗"
            char_mark = "=" if r["character_correct"] else "≠"
            sim_pct = f"{r['dialogue_similarity']:.0%}"
            print(f"\n  [{i:3d}] {status} sim={sim_pct}")
            gt_char = r["gt_character"] or "(無名)"
            print(f"    GT:  【{gt_char}】{r['gt_dialogue'][:60]}")
            if r["matched"]:
                p_char = r["pipeline_character"] or "(無名)"
                print(f"    OCR: 【{p_char}】{r['pipeline_dialogue'][:60]}  {char_mark}")

    # 錯誤樣本（只顯示前 10 個）
    errors = [r for r in results if r["matched"] and not r["character_correct"]]
    if errors:
        print(f"\n【角色名錯誤樣本】(共 {len(errors)} 處)")
        for r in errors[:10]:
            print(f"  GT: {r['gt_character']}  →  OCR: {r['pipeline_character']}")
            print(f"      {r['gt_dialogue'][:40]}")

    low_sim = [r for r in results if r["matched"] and r["dialogue_similarity"] < 0.5]
    if low_sim:
        print(f"\n【對白低相似度樣本】(共 {len(low_sim)} 處, sim < 50%)")
        for r in low_sim[:10]:
            print(f"  GT:  {r['gt_dialogue'][:50]}")
            print(f"  OCR: {r['pipeline_dialogue'][:50]}")
            print(f"       sim={r['dialogue_similarity']:.0%}")

    print("\n" + "=" * 60)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Ground Truth 比對工具")
    parser.add_argument("pipeline_file", nargs="?", type=Path,
                        help="Pipeline 輸出檔（SRT 或 timeline.json）")
    parser.add_argument("excel_file", type=Path,
                        help="Excel ground truth 檔案")
    parser.add_argument("--sheet", type=str, default=None,
                        help="Excel 分頁名稱")
    parser.add_argument("--from-timeline", action="store_true",
                        help="Pipeline 檔案為 timeline.json（預設為 SRT）")
    parser.add_argument("--list-sheets", action="store_true",
                        help="列出 Excel 所有分頁")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="顯示逐句比對細節")
    parser.add_argument("--prefer-asr", action="store_true",
                        help="Timeline 模式下優先使用 ASR 文字（測量 ASR 品質）")
    parser.add_argument("--split-sentences", action="store_true",
                        help="把 Pipeline 長段落拆成句子再比對（ASR 常合併多句）")
    parser.add_argument("--name-map", type=str, default=None,
                        help="角色名映射 JSON（如 '{\"風見咲月\":\"風見早希\"}'）")

    args = parser.parse_args()

    if args.list_sheets:
        sheets = list_excel_sheets(args.excel_file)
        print(f"\n{args.excel_file.name} — {len(sheets)} 個分頁\n")
        for s in sheets:
            chars = ", ".join(s["characters"][:5])
            if len(s["characters"]) > 5:
                chars += f"... (+{len(s['characters'])-5})"
            print(f"  [{s['lines']:3d} 行] {s['name']}")
            if chars:
                print(f"          角色: {chars}")
        return

    if args.pipeline_file is None:
        parser.print_help()
        sys.exit(1)

    if args.sheet is None:
        print("錯誤: 請用 --sheet 指定 Excel 分頁名稱")
        print("      用 --list-sheets 查看可用分頁")
        sys.exit(1)

    # 解析 name_map
    name_map = {}
    if args.name_map:
        name_map = json.loads(args.name_map)

    # 預設映射
    if "風見咲月" not in name_map:
        name_map["風見咲月"] = "風見早希"

    # 解析來源
    gt = parse_excel_sheet(args.excel_file, args.sheet)
    print(f"[GT] 載入 {len(gt)} 行 ground truth（{args.sheet}）")

    if args.from_timeline:
        pipeline = parse_timeline(args.pipeline_file, prefer_asr=args.prefer_asr)
    else:
        pipeline = parse_srt(args.pipeline_file)
    print(f"[Pipeline] 載入 {len(pipeline)} 行")

    if args.split_sentences:
        before = len(pipeline)
        pipeline = _split_sentences(pipeline)
        print(f"[Split] 句子拆分: {before} → {len(pipeline)} 行")

    # 比對
    comparison = align_and_compare(gt, pipeline, name_map)
    print_report(comparison, verbose=args.verbose)


if __name__ == "__main__":
    main()
