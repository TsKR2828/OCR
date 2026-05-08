"""Conflict Report Renderer — OCR/ASR 衝突清單報告."""

from __future__ import annotations

from pathlib import Path

from ..schema import Segment, fmt_ts


def render_conflict_report(
    segments: list[Segment],
    output_path: Path,
    title: str = "",
) -> None:
    """掃描 timeline 中 match_status == 'conflict' 的段落，輸出 Markdown 報告."""
    conflicts = [
        seg for seg in segments
        if seg.merge.match_status == "conflict"
    ]

    header = f"# 衝突報告：{title}\n" if title else "# OCR / ASR 衝突報告\n"
    lines = [
        header,
        f"> 共 {len(conflicts)} 處衝突\n",
    ]

    if not conflicts:
        lines.append("**無衝突。所有段落 OCR 與 ASR 一致或僅有單側資料。**\n")
    else:
        for i, seg in enumerate(conflicts, 1):
            ts = fmt_ts(seg.time_start)
            ocr_text = seg.ocr.dialogue if seg.ocr and seg.ocr.dialogue else "（無文字框）"
            asr_text = seg.asr.text if seg.asr and seg.asr.text else "（無語音辨識）"

            lines.append(f"### #{i} — {ts}\n")
            lines.append(f"- **OCR**: 「{ocr_text}」")
            lines.append(f"- **ASR**: 「{asr_text}」")

            # 自動建議
            suggestion = _suggest_resolution(seg)
            if suggestion:
                lines.append(f"- **建議**: {suggestion}")

            if seg.merge.conflict_note:
                lines.append(f"- **備註**: {seg.merge.conflict_note}")

            lines.append("")

    # 統計摘要
    total = len(segments)
    ocr_asr = sum(1 for s in segments if s.merge.source_type == "ocr_asr")
    consistent = sum(1 for s in segments if s.merge.match_status == "consistent")
    readback = sum(1 for s in segments if s.merge.match_status == "readback_possible")
    unverified = sum(1 for s in segments if s.merge.match_status == "unverified")

    lines.extend([
        "---\n",
        "## 統計摘要\n",
        f"| 項目 | 數量 |",
        f"|------|------|",
        f"| 總段數 | {total} |",
        f"| OCR+ASR 配對 | {ocr_asr} |",
        f"| 一致 (consistent) | {consistent} |",
        f"| 衝突 (conflict) | {len(conflicts)} |",
        f"| 跟讀可能 (readback) | {readback} |",
        f"| 單側未驗證 (unverified) | {unverified} |",
        "",
    ])

    if ocr_asr > 0:
        match_rate = consistent / ocr_asr * 100
        lines.append(f"> 配對一致率：{match_rate:.1f}% ({consistent}/{ocr_asr})\n")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"[Conflict] 寫出 → {output_path} ({len(conflicts)} 處衝突)")


def _suggest_resolution(seg: Segment) -> str:
    """根據衝突內容自動生成簡單建議."""
    if not seg.ocr or not seg.asr:
        if seg.ocr and not seg.asr:
            return "僅有 OCR 文字，無對應語音（可能是靜音段或文字演出）"
        if seg.asr and not seg.ocr:
            return "僅有語音，無畫面文字（可能是過場語音或實況主獨白）"
        return ""

    ocr_text = seg.ocr.dialogue or ""
    asr_text = seg.asr.text or ""

    # 長度差異大 → 可能一邊漏字
    if len(ocr_text) > 0 and len(asr_text) > 0:
        ratio = len(ocr_text) / len(asr_text) if len(asr_text) > 0 else 999
        if ratio > 3:
            return "OCR 文字明顯長於 ASR，可能 ASR 漏聽或語音較短"
        if ratio < 0.3:
            return "ASR 文字明顯長於 OCR，可能 OCR 只抓到部分文字"

    # 常見 OCR 誤判字（日文漢字容易混）
    common_ocr_errors = {
        "伺": "何", "巳": "己", "已": "己",
        "末": "未", "士": "土", "壺": "壷",
    }
    for wrong, right in common_ocr_errors.items():
        if wrong in ocr_text and right in asr_text:
            return f"ASR 版可能較正確（「{wrong}」→「{right}」是常見 OCR 誤判）"

    return "需人工確認哪一側更準確"
