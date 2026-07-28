/* data.jsx — VN-Transcribe dashboard data layer
   Loads timeline.json → computes all window globals the UI components expect. */

const fmtTime = (s) => {
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = Math.floor(s % 60);
  return `${String(h).padStart(2,"0")}:${String(m).padStart(2,"0")}:${String(sec).padStart(2,"0")}`;
};

const _CHAR_PALETTE = [
  "#6EC4E8","#A78BDB","#E86C5A","#5AB88F","#D4A85C",
  "#8BAAD6","#C77DA3","#6BC9A7","#D68E6A","#9B8EC4",
  "#5CB3C9","#D4717A","#7FC486","#C4A25C","#6EABD6",
  "#B87D9A","#78C4B8","#D49A5C","#9A7EC8","#5CBDB5",
];

/* ── 黒星劇場 應援色 (official support colors) ── */
const _BLACKSTAR_COLORS = {
  "ケイ":   "#fed300", "銀星":   "#424a76", "吉野":   "#fadce9",
  "ソテツ": "#004025", "ギィ":   "#c7b897", "夜光":   "#9fa0d7",
  "黒曜":   "#d7003a", "晶":     "#80c8ef", "シン":   "#83ccd2",
  "鷹見":   "#003149", "大牙":   "#884898",
  "リンドウ":"#3eb370","メノウ": "#e83929", "真珠":   "#0086cc",
  "マイカ": "#e94e66", "ネコメ": "#C4A3BF",
  "ミズキ": "#eb6101", "リコ":   "#ff7f50", "ヒース": "#4d4a26",
  "藍":     "#005baa", "金剛":   "#ffdc00", "ヒナタ": "#F4C430",
  "モクレン":"#581bb4","カスミ": "#7baa17", "クー":   "#4d4398",
  "玻璃":   "#007F89", "柘榴":   "#d3381c", "青桐":   "#007FFF",
};

/* window._VNT_CHAR_COLORS: external overrides (loaded config, etc.)
   Priority: _VNT_CHAR_COLORS > _BLACKSTAR_COLORS > _CHAR_PALETTE */
window._VNT_CHAR_COLORS = window._VNT_CHAR_COLORS || {};

const _SCENE_META = {
  dialogue:   { label: "對話",     jp: "対話" },
  reaction:   { label: "實況反應", jp: "反応" },
  narration:  { label: "旁白",     jp: "ナレーション" },
  choice:     { label: "選擇肢",   jp: "選択肢" },
  transition: { label: "轉場",     jp: "転場" },
  silence:    { label: "靜默",     jp: "沈黙" },
  unknown:    { label: "未分類",   jp: "不明" },
};

const _SCENE_CSS = {
  dialogue: "var(--scene-dialogue)", narration: "var(--scene-narration)",
  reaction: "var(--scene-reaction)", choice: "var(--scene-choice)",
  transition: "var(--scene-transition, #666)", silence: "var(--scene-silence, #444)",
  unknown: "var(--text-tertiary)",
};

/* ── Convert one raw segment (from timeline.json) to the UI shape SegmentCard expects ── */
function _toUI(seg, idx) {
  const ev = [];
  if (seg.events) {
    if (seg.events.chapter_change)    ev.push("chapter_change");
    if (seg.events.new_character)     ev.push("new_character");
    if (seg.events.choice_point)      ev.push("choice_point");
    if (seg.events.cg_unlock)         ev.push("cg_unlock");
    if (seg.events.streamer_reaction) ev.push("streamer_reaction");
    if (seg.events.chat_spike)        ev.push("chat_spike");
  }

  const scList = (seg.chat?.messages || [])
    .filter(m => m.type === "superchat" || m.type === "super_sticker")
    .map(m => ({ user: m.author, amount: parseInt(String(m.amount || "0").replace(/[^0-9]/g, "")) || 0 }));

  if (seg.chat?.is_spike && !ev.includes("chat_spike")) ev.push("chat_spike");
  if (scList.length > 0) ev.push("superchat");

  const bd = seg.score?.breakdown || {};

  return {
    idx: idx + 1,
    start: seg.time_start,
    end:   seg.time_end,
    scene: seg.scene_type || "unknown",
    score: Math.round(seg.score?.total || 0),
    ocr: seg.ocr
      ? { speaker: seg.ocr.character || null, text: seg.ocr.dialogue || "", chapter: seg.ocr.chapter || "" }
      : { speaker: null, text: "", chapter: "" },
    asr: seg.asr
      ? { speaker: seg.asr.speaker_guess || null, text: seg.asr.text || "" }
      : { speaker: null, text: "" },
    chat: seg.chat ? {
      count: seg.chat.message_count || 0,
      rate:  Math.round(seg.chat.density_per_min || 0),
      spike: seg.chat.is_spike || false,
      sc:    scList,
    } : null,
    merge:         seg.merge?.source_type   || "unknown",
    status:        seg.merge?.match_status  || "unverified",
    conflict_note: seg.merge?.conflict_note || null,
    events:        ev,
    breakdown: {
      volume:        Math.round(bd.volume_spike        || 0),
      laughter:      Math.round(bd.laughter            || 0),
      keyword:       Math.round(bd.keyword_hit         || 0),
      chat:          Math.round(bd.chat_spike          || 0),
      speech_rate:   Math.round(bd.speech_rate_change  || 0),
      silence_burst: Math.round(bd.silence_then_burst  || 0),
    },
  };
}

/* ── Main compute: raw segment array → all window globals ── */
function computeFromTimeline(rawSegments, filename) {
  const total = rawSegments.length;

  // VIDEO_DURATION
  const VIDEO_DURATION = total > 0
    ? Math.ceil(Math.max(...rawSegments.map(s => s.time_end || 0)))
    : 0;

  // CHANNEL
  const CHANNEL = {
    name: "VN-Transcribe",
    game: filename.replace(/\.json$/i, "").replace(/[-_]/g, " "),
    game_language: "ja",
    default_language: "ja",
    file: filename,
    date: new Date().toISOString().slice(0, 10),
  };

  // CHARACTERS — from ocr.character
  const cMap = new Map();
  rawSegments.forEach(seg => {
    const name = seg.ocr?.character;
    if (!name) return;
    if (!cMap.has(name)) {
      cMap.set(name, {
        id: name.toLowerCase().replace(/[^a-z0-9぀-鿿]/gi, "_") || `char${cMap.size}`,
        name,
        aliases: [],
        color: window._VNT_CHAR_COLORS[name] || _BLACKSTAR_COLORS[name] || _CHAR_PALETTE[cMap.size % _CHAR_PALETTE.length],
        lines: 0,
        firstAt: seg.time_start,
        lastAt:  seg.time_start,
      });
    }
    const c = cMap.get(name);
    c.lines++;
    if (seg.time_start < c.firstAt) c.firstAt = seg.time_start;
    if (seg.time_start > c.lastAt)  c.lastAt  = seg.time_start;
  });
  const CHARACTERS = [...cMap.values()].sort((a, b) => b.lines - a.lines);

  // SCENE_TYPES
  const sCounts = {};
  rawSegments.forEach(s => { const t = s.scene_type || "unknown"; sCounts[t] = (sCounts[t] || 0) + 1; });
  const SCENE_TYPES = Object.entries(sCounts)
    .sort((a, b) => b[1] - a[1])
    .map(([id, count]) => ({
      id, count,
      label: (_SCENE_META[id] || {}).label || id,
      jp:    (_SCENE_META[id] || {}).jp    || id,
      color: _SCENE_CSS[id] || "var(--text-tertiary)",
    }));

  // All UI segments
  const allUI = rawSegments.map((s, i) => _toUI(s, i));

  // FEATURED_SEGMENTS — top 30 by score
  const FEATURED_SEGMENTS = [...allUI].sort((a, b) => b.score - a.score).slice(0, 30);

  // CONFLICTS
  let cIdx = 0;
  const CONFLICTS = allUI
    .filter(s => s.status === "conflict")
    .map(s => ({
      idx: ++cIdx,
      segmentIdx: s.idx,
      time: s.start,
      status: "pending",
      ocr: s.ocr?.text || "",
      asr: s.asr?.text || "",
      diff: [],
      suggestion: "manual",
      reason: s.conflict_note || "OCR 與 ASR 內容不一致，建議人工確認。",
      confidence: 0.5,
    }));

  // CLIPS — top 20 highlights
  const CLIPS = [...allUI]
    .sort((a, b) => b.score - a.score)
    .slice(0, 20)
    .map((s, i) => ({
      id: i + 1,
      segIdx: s.idx,
      start: s.start,
      end: s.end,
      score: s.score,
      scene: s.scene,
      title: (s.ocr?.text || s.asr?.text || `Segment #${s.idx}`).slice(0, 40),
      quote: s.asr?.text || "",
      quoteJp: s.ocr?.text || "",
      sc: (s.chat?.sc || []).reduce((sum, x) => sum + (x.amount || 0), 0),
    }));

  // DENSITY + SCENE_BAND — time buckets for waveform
  const BUCKET_N = Math.max(80, Math.min(400, Math.round(VIDEO_DURATION / 30)));
  const bSize = VIDEO_DURATION / (BUCKET_N || 1);
  const dRaw = new Float64Array(BUCKET_N);
  const sBMap = Array.from({ length: BUCKET_N }, () => ({}));

  rawSegments.forEach(seg => {
    const b0 = Math.max(0, Math.floor(seg.time_start / bSize));
    const b1 = Math.min(BUCKET_N - 1, Math.floor((seg.time_end || seg.time_start) / bSize));
    const sc = seg.score?.total || 1;
    const st = seg.scene_type || "unknown";
    for (let b = b0; b <= b1; b++) {
      dRaw[b] += sc;
      sBMap[b][st] = (sBMap[b][st] || 0) + 1;
    }
  });

  const maxD = Math.max(...dRaw, 1);
  const DENSITY = Array.from(dRaw, d => Math.max(0.03, d / maxD));

  const SCENE_BAND = sBMap.map(m => {
    const e = Object.entries(m);
    return e.length === 0 ? "silence" : e.sort((a, b) => b[1] - a[1])[0][0];
  });

  // HOT_SPOTS — top 5% density buckets
  const sortedD = [...DENSITY].sort((a, b) => b - a);
  const hotThresh = sortedD[Math.floor(BUCKET_N * 0.05)] || 0.8;
  const HOT_SPOTS = DENSITY.reduce((acc, d, i) => { if (d >= hotThresh) acc.push(i); return acc; }, []);

  // CHAR_PRESENCE — 36 buckets per character
  const P_BUCKETS = 36;
  const pSize = VIDEO_DURATION / (P_BUCKETS || 1);
  const CHAR_PRESENCE = {};
  CHARACTERS.forEach(ch => {
    const arr = new Uint8Array(P_BUCKETS);
    rawSegments.forEach(seg => {
      if (seg.ocr?.character === ch.name) {
        const b = Math.min(Math.floor(seg.time_start / pSize), P_BUCKETS - 1);
        arr[b] = 1;
      }
    });
    CHAR_PRESENCE[ch.id] = Array.from(arr);
  });

  // STATS
  const scUsers = new Set();
  let scTotal = 0;
  rawSegments.forEach(seg => {
    (seg.chat?.messages || []).forEach(m => {
      if (m.type === "superchat" || m.type === "super_sticker") {
        scUsers.add(m.author);
        scTotal += parseInt(String(m.amount || "0").replace(/[^0-9]/g, "")) || 0;
      }
    });
  });

  const histBins = [
    [0,10],[10,20],[20,30],[30,40],[40,50],[50,60],[60,70],[70,80],[80,Infinity],
  ];
  const scoreHistogram = histBins.map(([lo,hi]) => ({
    range: hi === Infinity ? "80+" : `${lo}-${hi}`,
    count: allUI.filter(s => s.score >= lo && s.score < hi).length,
  }));

  const avgLen = total > 0
    ? rawSegments.reduce((sum, s) => sum + ((s.time_end || 0) - (s.time_start || 0)), 0) / total
    : 0;

  const STATS = {
    totalSegments: total,
    duration: VIDEO_DURATION,
    avgSegLen: Math.round(avgLen * 10) / 10,
    conflicts: CONFLICTS.length,
    resolvedConflicts: 0,
    highlights: FEATURED_SEGMENTS.filter(s => s.score >= 50).length,
    characters: CHARACTERS.length,
    scDistinctUsers: scUsers.size,
    scTotal,
    scoreHistogram,
  };

  function generateAllSegments() { return allUI; }

  Object.assign(window, {
    fmtTime, VIDEO_DURATION, CHANNEL, CHARACTERS, SCENE_TYPES,
    FEATURED_SEGMENTS, CONFLICTS, CLIPS, DENSITY, SCENE_BAND, HOT_SPOTS,
    CHAR_PRESENCE, STATS, generateAllSegments,
  });
}

/* ── Loading infrastructure ── */
window._VNT = {
  loaded: false,
  filename: null,
  segmentCount: 0,
  _cbs: [],
  onLoad(fn) { this._cbs.push(fn); },
  _fire()    { this._cbs.forEach(fn => fn()); },
};

async function loadTimelineFile(file) {
  const text = await file.text();
  const raw = JSON.parse(text);
  if (!Array.isArray(raw))
    throw new Error("timeline.json 必須是 segment 陣列");
  computeFromTimeline(raw, file.name);
  window._VNT.loaded = true;
  window._VNT.filename = file.name;
  window._VNT.segmentCount = raw.length;
  window._VNT._fire();
}

window._VNT_EDITS = {};

/* Expose fmtTime immediately (Sidebar etc. reference it at render time) */
Object.assign(window, { fmtTime, loadTimelineFile });
