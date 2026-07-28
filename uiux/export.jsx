/* export.jsx — Download helpers for VN-Transcribe dashboard */

function _dl(content, filename, mime) {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function _baseName() {
  return (CHANNEL?.file || "timeline").replace(/\.json$/i, "");
}

/* ── Apply edits overlay ── */
function _applyEdits(seg) {
  const ed = window._VNT_EDITS?.[seg.idx];
  if (!ed) return seg;
  return {
    ...seg,
    ocr: { ...seg.ocr, speaker: ed.speaker ?? seg.ocr?.speaker, text: ed.text ?? seg.ocr?.text },
  };
}

/* ══════════════════════════════════════════════
   1.  EXCEL  — full segments + characters + conflicts
   ══════════════════════════════════════════════ */
function exportExcel() {
  if (typeof XLSX === "undefined") {
    alert("SheetJS 未載入，無法匯出 Excel。請確認網路連線。");
    return;
  }

  const segs = generateAllSegments().map(_applyEdits);

  const rows = segs.map(s => ({
    "#": s.idx,
    "開始": fmtTime(s.start),
    "結束": fmtTime(s.end),
    "秒數": +(s.end - s.start).toFixed(1),
    "章節": s.ocr?.chapter || "",
    "角色": s.ocr?.speaker || "",
    "台詞(OCR)": s.ocr?.text || "",
    "ASR": s.asr?.text || "",
    "場景": s.scene,
    "Score": s.score,
    "合併": s.merge,
    "狀態": s.status,
    "備註": s.conflict_note || "",
  }));

  const ws = XLSX.utils.json_to_sheet(rows);
  const keys = Object.keys(rows[0] || {});
  ws["!cols"] = keys.map(k => ({
    wch: Math.min(60, Math.max(k.length + 2,
      ...rows.slice(0, 200).map(r => String(r[k] || "").length + 1)))
  }));

  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, "Segments");

  if (CHARACTERS?.length) {
    const cRows = CHARACTERS.map(c => ({
      "角色": c.name, "台詞數": c.lines,
      "初登場": fmtTime(c.firstAt), "末登場": fmtTime(c.lastAt),
    }));
    XLSX.utils.book_append_sheet(wb, XLSX.utils.json_to_sheet(cRows), "Characters");
  }

  if (CONFLICTS?.length) {
    const fRows = CONFLICTS.map(c => ({
      "#": c.idx, "Segment": c.segmentIdx, "時間": fmtTime(c.time),
      "OCR": c.ocr, "ASR": c.asr, "建議": c.suggestion, "原因": c.reason,
    }));
    XLSX.utils.book_append_sheet(wb, XLSX.utils.json_to_sheet(fRows), "Conflicts");
  }

  XLSX.writeFile(wb, _baseName() + "_export.xlsx");
}

/* ══════════════════════════════════════════════
   2.  CONFLICT REPORT  — JSON with decisions
   ══════════════════════════════════════════════ */
function exportConflictJSON(conflicts, decisions) {
  const items = (conflicts || CONFLICTS || []).map(c => {
    const d = (decisions || {})[c.idx];
    return {
      conflict_idx: c.idx,
      segment_idx: c.segmentIdx,
      time: fmtTime(c.time),
      ocr: c.ocr,
      asr: c.asr,
      suggestion: c.suggestion,
      decision: d || "pending",
    };
  });

  const report = {
    source: CHANNEL?.file || "unknown",
    exported_at: new Date().toISOString(),
    total: items.length,
    resolved: items.filter(i => i.decision !== "pending").length,
    decisions: items,
  };

  _dl(JSON.stringify(report, null, 2), _baseName() + "_conflicts.json", "application/json");
}

/* ══════════════════════════════════════════════
   3.  CLIPS EXPORT  — chapters / SRT / EDL
   ══════════════════════════════════════════════ */
function exportChapters() {
  const lines = (CLIPS || []).map((c, i) => {
    const t = c.start;
    const h = Math.floor(t / 3600);
    const m = Math.floor((t % 3600) / 60);
    const s = t % 60;
    const ts = `${String(h).padStart(2,"0")}:${String(m).padStart(2,"0")}:${s.toFixed(3).padStart(6,"0")}`;
    return `${ts} ${c.title}`;
  });
  _dl(lines.join("\n"), _baseName() + ".chapters", "text/plain");
}

function exportSRT() {
  const lines = (CLIPS || []).map((c, i) => {
    const fmt = (t) => {
      const h = Math.floor(t / 3600);
      const m = Math.floor((t % 3600) / 60);
      const s = Math.floor(t % 60);
      const ms = Math.round((t % 1) * 1000);
      return `${String(h).padStart(2,"0")}:${String(m).padStart(2,"0")}:${String(s).padStart(2,"0")},${String(ms).padStart(3,"0")}`;
    };
    return `${i + 1}\n${fmt(c.start)} --> ${fmt(c.end)}\n${c.quoteJp || c.title}\n`;
  });
  _dl(lines.join("\n"), _baseName() + "_clips.srt", "text/plain;charset=utf-8");
}

function exportEDL() {
  const lines = ["TITLE: " + (_baseName()), "FCM: NON-DROP FRAME", ""];
  (CLIPS || []).forEach((c, i) => {
    const fmt = (t) => {
      const h = Math.floor(t / 3600);
      const m = Math.floor((t % 3600) / 60);
      const s = Math.floor(t % 60);
      const f = Math.round((t % 1) * 30);
      return `${String(h).padStart(2,"0")}:${String(m).padStart(2,"0")}:${String(s).padStart(2,"0")}:${String(f).padStart(2,"0")}`;
    };
    const num = String(i + 1).padStart(3, "0");
    lines.push(`${num}  001  V  C  ${fmt(c.start)} ${fmt(c.end)} ${fmt(c.start)} ${fmt(c.end)}`);
    lines.push(`* ${c.title}`);
    lines.push("");
  });
  _dl(lines.join("\n"), _baseName() + ".edl", "text/plain");
}

/* ══════════════════════════════════════════════
   4.  EDITED TIMELINE  — re-export timeline.json with edits applied
   ══════════════════════════════════════════════ */
function exportEditedTimeline() {
  const segs = generateAllSegments().map(_applyEdits);
  _dl(JSON.stringify(segs, null, 2), _baseName() + "_edited.json", "application/json");
}

Object.assign(window, {
  exportExcel, exportConflictJSON,
  exportChapters, exportSRT, exportEDL,
  exportEditedTimeline,
});
