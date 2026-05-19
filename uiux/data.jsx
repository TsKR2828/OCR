/* Mock data for VN-Transcribe — 深紅の月夜 -Crimson Moon- */

const fmtTime = (s) => {
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = Math.floor(s % 60);
  return `${String(h).padStart(2,"0")}:${String(m).padStart(2,"0")}:${String(sec).padStart(2,"0")}`;
};

const VIDEO_DURATION = 8130; // 02:15:30

const CHANNEL = {
  name: "夜風チャンネル",
  game: "深紅の月夜 -Crimson Moon-",
  game_language: "ja",
  default_language: "zh-TW",
  file: "crimson-moon-ep07.mp4",
  date: "2026-05-10",
};

const CHARACTERS = [
  { id: "kei", name: "ケイ", aliases: ["景", "Kei"], color: "#6EC4E8", lines: 47, firstAt: 525, lastAt: 6753 },
  { id: "yuri", name: "ユリ", aliases: ["優里"], color: "#A78BDB", lines: 31, firstAt: 1330, lastAt: 6480 },
  { id: "haruka", name: "ハルカ", aliases: ["遥"], color: "#E86C5A", lines: 18, firstAt: 2140, lastAt: 5535 },
];

const SCENE_TYPES = [
  { id: "dialogue", label: "對話", jp: "対話", count: 648, color: "var(--scene-dialogue)" },
  { id: "reaction", label: "實況反應", jp: "反応", count: 224, color: "var(--scene-reaction)" },
  { id: "narration", label: "旁白", jp: "ナレーション", count: 187, color: "var(--scene-narration)" },
  { id: "choice", label: "選擇肢", jp: "選択肢", count: 28, color: "var(--scene-choice)" },
  { id: "transition", label: "轉場", jp: "転場", count: 112, color: "var(--scene-transition)" },
  { id: "silence", label: "靜默", jp: "沈黙", count: 48, color: "var(--scene-silence)" },
];

// Hand-crafted segments for realism (the headline list)
const FEATURED_SEGMENTS = [
  { idx: 42, start: 763, end: 768, scene: "dialogue", score: 67,
    ocr: { speaker: "ケイ", text: "君は、ここにいてくれるのか。" },
    asr: { speaker: "streamer", text: "啊啊啊他這句好溫柔我不行了" },
    chat: { count: 23, rate: 138, spike: true, sc: [{ user: "vip_fan", amount: 500 }] },
    merge: "ocr_asr", status: "consistent", events: ["streamer_reaction", "chat_spike"],
    breakdown: { volume: 12, laughter: 0, keyword: 18, chat: 22, speech_rate: 8, silence_burst: 7 } },
  { idx: 43, start: 768, end: 775, scene: "reaction", score: 81,
    ocr: { speaker: null, text: "" },
    asr: { speaker: "streamer", text: "我真的要哭了你們看他眼神！" },
    chat: { count: 47, rate: 218, spike: true, sc: [{ user: "moon_lover", amount: 1200 }, { user: "haruka_4ever", amount: 300 }] },
    merge: "asr_only", status: "consistent", events: ["streamer_reaction", "chat_spike", "superchat"],
    breakdown: { volume: 22, laughter: 14, keyword: 12, chat: 19, speech_rate: 8, silence_burst: 6 } },
  { idx: 44, start: 775, end: 783, scene: "dialogue", score: 52,
    ocr: { speaker: "ユリ", text: "もう、二人だけの世界に入らないでよ……" },
    asr: { speaker: "streamer", text: "ユリ吃醋了！ユリ吃醋了！" },
    chat: { count: 19, rate: 95, spike: false, sc: [] },
    merge: "ocr_asr", status: "consistent", events: [],
    breakdown: { volume: 10, laughter: 8, keyword: 15, chat: 11, speech_rate: 5, silence_burst: 3 } },
  { idx: 45, start: 783, end: 795, scene: "choice", score: 73,
    ocr: { speaker: null, text: "▶ 一緒にいたい / そばを離れる" },
    asr: { speaker: "streamer", text: "選哪個選哪個！我選一起待著啦這還用問" },
    chat: { count: 64, rate: 312, spike: true, sc: [] },
    merge: "ocr_asr", status: "consistent", events: ["choice_point", "chat_spike"],
    breakdown: { volume: 15, laughter: 0, keyword: 22, chat: 28, speech_rate: 8, silence_burst: 0 } },
  { idx: 87, start: 1655, end: 1668, scene: "dialogue", score: 45,
    ocr: { speaker: "ケイ", text: "お前は伺を言っているんだ" },
    asr: { speaker: "streamer", text: "他在說什麼啊？「お前は何を言っているんだ」對吧？" },
    chat: { count: 14, rate: 71, spike: false, sc: [] },
    merge: "ocr_asr", status: "conflict",
    conflict_note: "OCR 「伺」應為「何」（常見錯誤辨識）",
    events: [],
    breakdown: { volume: 8, laughter: 0, keyword: 16, chat: 8, speech_rate: 7, silence_burst: 6 } },
  { idx: 88, start: 1668, end: 1672, scene: "silence", score: 12,
    ocr: { speaker: null, text: "" },
    asr: { speaker: null, text: "" },
    chat: { count: 3, rate: 18, spike: false, sc: [] },
    merge: "none", status: "consistent", events: [],
    breakdown: { volume: 1, laughter: 0, keyword: 0, chat: 2, speech_rate: 0, silence_burst: 9 } },
];

const CONFLICTS = [
  { idx: 7, segmentIdx: 87, time: 1655, status: "pending",
    ocr: "お前は伺を言っているんだ",
    asr: "お前は何を言っているんだ",
    diff: [{ pos: 4, ocr: "伺", asr: "何" }],
    suggestion: "asr",
    reason: "「伺」→「何」是常見 OCR 誤判（字形相似）。ASR 結果在語境上更合理。",
    confidence: 0.92 },
  { idx: 8, segmentIdx: 134, time: 2310, status: "pending",
    ocr: "また会えるよ、きっと。",
    asr: "また会えるよ、絶対。",
    diff: [{ pos: 7, ocr: "きっと", asr: "絶対" }],
    suggestion: "ocr",
    reason: "OCR 與遊戲畫面文字一致，ASR 為實況主口語替換。建議採用 OCR。",
    confidence: 0.78 },
  { idx: 9, segmentIdx: 201, time: 3625, status: "pending",
    ocr: "二人で帰ろう。",
    asr: "二人で歩こう。",
    diff: [{ pos: 4, ocr: "帰", asr: "歩" }],
    suggestion: "manual",
    reason: "兩者語義差異大（回家 vs 走路），建議人工確認原作。",
    confidence: 0.45 },
  { idx: 10, segmentIdx: 245, time: 4118, status: "resolved",
    ocr: "ハルカ……ありがとう。",
    asr: "ハルカちゃん、ありがとう。",
    resolution: "asr",
    diff: [{ pos: 3, ocr: "……", asr: "ちゃん、" }],
    suggestion: "asr",
    reason: "ASR 補上了實況主口語化的稱呼。" },
];

// Clip data (highlights)
const CLIPS = [
  { id: 1, segIdx: 43, start: 768, end: 775, score: 81, scene: "reaction",
    title: "ケイの告白に涙",
    quote: "我真的要哭了你們看他眼神！", quoteJp: "君は、ここにいてくれるのか。",
    sc: 1500 },
  { id: 2, segIdx: 45, start: 783, end: 795, score: 73, scene: "choice",
    title: "迷わず「一緒にいたい」",
    quote: "選哪個選哪個！我選一起待著啦", quoteJp: "▶ 一緒にいたい / そばを離れる",
    sc: 0 },
  { id: 3, segIdx: 42, start: 763, end: 768, score: 67, scene: "dialogue",
    title: "君は、ここにいてくれるのか。",
    quote: "啊啊啊他這句好溫柔我不行了", quoteJp: "君は、ここにいてくれるのか。",
    sc: 500 },
  { id: 4, segIdx: 198, start: 3548, end: 3563, score: 71, scene: "dialogue",
    title: "ユリの本音",
    quote: "ユリ終於說出來了我等了三集！", quoteJp: "ずっと、好きだったの。",
    sc: 0 },
  { id: 5, segIdx: 312, start: 5210, end: 5224, score: 78, scene: "reaction",
    title: "選択肢で大爆笑",
    quote: "等等這選項是什麼鬼啊哈哈哈哈哈哈", quoteJp: "▶ 黙ってお茶を飲む / 窓から飛び降りる",
    sc: 800 },
  { id: 6, segIdx: 387, start: 6420, end: 6432, score: 65, scene: "dialogue",
    title: "ハルカの過去",
    quote: "原來ハルカ的過去這麼沉重……", quoteJp: "あの夜、私は何もできなかった。",
    sc: 0 },
];

// Density buckets (per ~30s) for timeline visualization — 270 buckets
const DENSITY = (() => {
  const buckets = 270;
  const arr = [];
  // pseudo-random but deterministic
  let seed = 42;
  const rand = () => { seed = (seed * 9301 + 49297) % 233280; return seed / 233280; };
  for (let i = 0; i < buckets; i++) {
    // base sine wave + bursts
    const base = 0.3 + 0.25 * Math.sin(i / 8) + 0.15 * Math.sin(i / 22);
    const noise = rand() * 0.3;
    let v = base + noise;
    // inject some spikes
    if ([15, 16, 17, 47, 48, 78, 79, 80, 110, 138, 139, 174, 200, 230, 231, 252].includes(i)) v = 0.85 + rand() * 0.15;
    arr.push(Math.max(0.05, Math.min(1, v)));
  }
  return arr;
})();

// Scene colorband per bucket
const SCENE_BAND = (() => {
  const order = ["dialogue", "reaction", "dialogue", "narration", "dialogue", "reaction", "dialogue",
                 "transition", "dialogue", "choice", "dialogue", "reaction", "silence"];
  let i = 0;
  const arr = [];
  let runs = 0;
  let cur = "dialogue";
  let seed = 17;
  const rand = () => { seed = (seed * 9301 + 49297) % 233280; return seed / 233280; };
  while (arr.length < 270) {
    cur = order[i % order.length];
    const len = 3 + Math.floor(rand() * 8);
    for (let j = 0; j < len && arr.length < 270; j++) arr.push(cur);
    i++;
  }
  return arr;
})();

// Score heatmap markers (positions where score is high)
const HOT_SPOTS = [16, 30, 47, 60, 79, 88, 105, 138, 174, 195, 230, 252];

// Character gantt — 36 buckets per char
const CHAR_PRESENCE = {
  kei:    [1,1,1,0,1,1,1,1,0,0,1,1,1,1,0,1,1,0,0,1,1,1,1,0,0,1,1,1,0,0,0,1,1,1,1,1],
  yuri:   [0,0,1,1,0,0,1,1,1,0,0,1,1,0,0,0,1,1,1,0,0,0,1,1,1,1,0,0,0,1,1,1,1,0,0,1],
  haruka: [0,0,0,0,0,0,1,1,1,1,1,0,0,0,1,1,0,0,0,0,1,1,1,0,0,0,0,1,1,1,0,0,0,0,0,0],
};

// Stats
const STATS = {
  totalSegments: 1247,
  duration: VIDEO_DURATION,
  avgSegLen: 6.5,
  conflicts: 47,
  resolvedConflicts: 25,
  highlights: 82,
  characters: 3,
  scDistinctUsers: 12,
  scTotal: 24800,
  scoreHistogram: [
    { range: "0-10", count: 412 },
    { range: "10-20", count: 285 },
    { range: "20-30", count: 187 },
    { range: "30-40", count: 142 },
    { range: "40-50", count: 98 },
    { range: "50-60", count: 67 },
    { range: "60-70", count: 38 },
    { range: "70-80", count: 14 },
    { range: "80+", count: 4 },
  ],
};

// Generate full segment list (1247 items) procedurally for virtual scroll demo
function generateAllSegments() {
  const total = 1247;
  const segs = [];
  let seed = 7;
  const rand = () => { seed = (seed * 9301 + 49297) % 233280; return seed / 233280; };
  let t = 0;
  for (let i = 1; i <= total; i++) {
    const dur = 3 + rand() * 9;
    const start = t;
    t += dur;
    const scene = ["dialogue", "dialogue", "dialogue", "reaction", "narration", "transition", "dialogue", "choice", "silence"][Math.floor(rand() * 9)];
    const score = Math.floor(rand() * 80);
    segs.push({ idx: i, start, end: t, scene, score });
  }
  return segs;
}

Object.assign(window, {
  fmtTime, VIDEO_DURATION, CHANNEL, CHARACTERS, SCENE_TYPES,
  FEATURED_SEGMENTS, CONFLICTS, CLIPS, DENSITY, SCENE_BAND, HOT_SPOTS,
  CHAR_PRESENCE, STATS, generateAllSegments,
});
