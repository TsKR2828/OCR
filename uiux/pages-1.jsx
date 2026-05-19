/* Pages part 1: Dashboard, Timeline, Search */

const { useState: uS1, useEffect: uE1, useMemo: uM1, useRef: uR1 } = React;

/* ─────────────────────────────────────────────
   DASHBOARD
   ───────────────────────────────────────────── */
function DashboardPage({ onJump, onNav }) {
  const sceneTotal = SCENE_TYPES.reduce((s, t) => s + t.count, 0);

  return (
    <>
      <Topbar
        title="Dashboard"
        jpTitle="ダッシュボード"
        breadcrumb={CHANNEL.game}
        actions={
          <>
            <button className="btn btn--ghost"><I.Upload size={13} /> Import timeline.json</button>
            <button className="btn"><I.Download size={13} /> Export Report</button>
            <button className="btn btn--amber"><I.Play size={13} /> Open in Viewer</button>
          </>
        }
      />

      <div className="page-content">
        <div className="page-pad" style={{ display: "flex", flexDirection: "column", gap: 18 }}>
          {/* Stat cards row */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 12 }}>
            <StatCard label="SEGMENTS" value={STATS.totalSegments.toLocaleString()} sub="平均 6.5s/段" icon="Timeline" />
            <StatCard label="DURATION" value={fmtTime(STATS.duration)} sub="ep07 — 5/10 配信" icon="Stats" />
            <StatCard label="CONFLICTS" value={STATS.conflicts} sub={`${STATS.resolvedConflicts} 已審 · ${STATS.conflicts - STATS.resolvedConflicts} 待審`} icon="Conflict" accent="danger" />
            <StatCard label="HIGHLIGHTS" value={STATS.highlights} sub="score ≥ 60" icon="Clips" accent="amber" />
            <StatCard label="CHARACTERS" value={STATS.characters} sub="3 主角 · 12 SC ユーザー" icon="User" />
          </div>

          {/* Timeline thumbnail */}
          <div className="panel">
            <div className="panel__head">
              <I.Timeline size={14} style={{ color: "var(--amber)" }} />
              <span className="panel__title">Timeline Overview</span>
              <span className="panel__label">3-LAYER · SCENE / DENSITY / HEAT</span>
              <div style={{ marginLeft: "auto", display: "flex", gap: 6 }}>
                <button className="pill pill--active">場景</button>
                <button className="pill pill--active">密度</button>
                <button className="pill pill--active">精彩</button>
              </div>
            </div>
            <div className="panel__body">
              <TimelineThumbnail height={88} onClick={(t) => onJump?.(t)} playhead={4118} />
              <div style={{ display: "flex", justifyContent: "space-between", marginTop: 10, fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--text-tertiary)" }}>
                <div>HOVER: timestamp / segment</div>
                <div>DRAG: select range  ·  CLICK: jump in Viewer  ·  WHEEL: zoom</div>
                <div>HOTSPOTS: <span className="amber">{HOT_SPOTS.length}</span></div>
              </div>
            </div>
          </div>

          {/* Two columns */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
            {/* Scene distribution */}
            <div className="panel">
              <div className="panel__head">
                <I.Stats size={14} />
                <span className="panel__title">Scene Distribution</span>
                <span className="panel__label">{sceneTotal} TOTAL</span>
              </div>
              <div className="panel__body" style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                {/* Stacked horizontal bar */}
                <div style={{ display: "flex", height: 12, borderRadius: 3, overflow: "hidden", border: "1px solid var(--ink-border)" }}>
                  {SCENE_TYPES.map((s) => (
                    <div key={s.id} title={`${s.label} ${((s.count / sceneTotal) * 100).toFixed(1)}%`}
                      style={{
                        flex: s.count,
                        background: s.color,
                        opacity: 0.85,
                      }} />
                  ))}
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
                  {SCENE_TYPES.map((s) => (
                    <div key={s.id} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12, padding: "4px 0" }}>
                      <span style={{ width: 8, height: 8, background: s.color, borderRadius: 2 }} />
                      <span>{s.label}</span>
                      <span className="dim jp" style={{ fontSize: 10 }}>{s.jp}</span>
                      <span className="mono dim" style={{ marginLeft: "auto", fontSize: 11 }}>
                        {s.count} <span style={{ color: "var(--text-tertiary)" }}>· {((s.count / sceneTotal) * 100).toFixed(0)}%</span>
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Top highlights */}
            <div className="panel">
              <div className="panel__head">
                <I.Clips size={14} />
                <span className="panel__title">Top Highlights</span>
                <span className="panel__label">RANK BY SCORE</span>
                <button className="btn btn--ghost btn--sm" style={{ marginLeft: "auto" }} onClick={() => onNav?.("clips")}>
                  All {STATS.highlights} <I.ChevronRight size={11} />
                </button>
              </div>
              <div className="panel__body" style={{ padding: 0 }}>
                {CLIPS.slice(0, 5).map((c, i) => (
                  <div key={c.id} style={{
                    display: "grid",
                    gridTemplateColumns: "32px 80px 60px 1fr auto",
                    gap: 10,
                    alignItems: "center",
                    padding: "10px 16px",
                    borderTop: i === 0 ? "none" : "1px solid color-mix(in srgb, var(--ink-border) 50%, transparent)",
                    cursor: "pointer",
                  }} onClick={() => onJump?.(c.start)}>
                    <span className="mono" style={{ fontSize: 11, color: "var(--text-tertiary)" }}>#{String(i + 1).padStart(2, "0")}</span>
                    <span className="mono" style={{ fontSize: 11 }}>{fmtTime(c.start)}</span>
                    <ScoreBadge score={c.score} />
                    <span className="jp" style={{ fontSize: 12, color: "var(--text-jp)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                      {c.quoteJp}
                    </span>
                    <SceneBadge scene={c.scene} />
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Character gantt */}
          <div className="panel">
            <div className="panel__head">
              <I.User size={14} />
              <span className="panel__title">Character Presence</span>
              <span className="panel__label">GANTT — APPEARANCE OVER TIME</span>
              <div style={{ marginLeft: "auto" }} className="mono dim">{STATS.totalSegments} segments</div>
            </div>
            <div className="panel__body">
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {CHARACTERS.map((c) => {
                  const presence = CHAR_PRESENCE[c.id];
                  const totalLines = presence.filter(Boolean).length * (1247 / 36);
                  return (
                    <div key={c.id} style={{ display: "grid", gridTemplateColumns: "120px 1fr 80px", gap: 12, alignItems: "center" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <span style={{ width: 10, height: 10, background: c.color, borderRadius: 2 }} />
                        <span className="jp" style={{ fontSize: 13 }}>{c.name}</span>
                        <span className="dim mono" style={{ fontSize: 10 }}>{c.aliases.join("/")}</span>
                      </div>
                      <div style={{ display: "flex", height: 18, gap: 1, background: "var(--ink-deep)", padding: 2, borderRadius: 3, border: "1px solid var(--ink-border)" }}>
                        {presence.map((p, i) => (
                          <div key={i} style={{
                            flex: 1,
                            background: p ? c.color : "transparent",
                            opacity: p ? 0.85 : 0,
                            borderRadius: 1,
                          }} />
                        ))}
                      </div>
                      <div style={{ textAlign: "right" }} className="mono">
                        <span style={{ color: "var(--text-primary)" }}>{c.lines}</span>
                        <span className="dim" style={{ fontSize: 10 }}> 台詞</span>
                      </div>
                    </div>
                  );
                })}
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", marginTop: 12, fontFamily: "var(--font-mono)", fontSize: 9, color: "var(--text-tertiary)", letterSpacing: "0.12em" }}>
                <span>{fmtTime(0)}</span>
                <span>{fmtTime(VIDEO_DURATION * 0.25)}</span>
                <span>{fmtTime(VIDEO_DURATION * 0.5)}</span>
                <span>{fmtTime(VIDEO_DURATION * 0.75)}</span>
                <span>{fmtTime(VIDEO_DURATION)}</span>
              </div>
            </div>
          </div>

          {/* Chat / SC summary */}
          <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 14 }}>
            <div className="panel">
              <div className="panel__head">
                <I.Chat size={14} />
                <span className="panel__title">Chat Activity</span>
                <span className="panel__label">DENSITY PER MIN · SPIKE × 16</span>
              </div>
              <div className="panel__body">
                <ChatActivityChart />
              </div>
            </div>
            <div className="panel">
              <div className="panel__head">
                <I.SC size={14} style={{ color: "var(--superchat)" }} />
                <span className="panel__title">Superchats</span>
                <span className="panel__label">¥ {STATS.scTotal.toLocaleString()}</span>
              </div>
              <div className="panel__body" style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {[
                  { user: "moon_lover", amount: 5000, msg: "夜風さん大好き！", time: 4732 },
                  { user: "vip_fan", amount: 3000, msg: "ケイ尊い…", time: 763 },
                  { user: "haruka_4ever", amount: 2500, msg: "ハルカ推し！", time: 5210 },
                  { user: "yuri_fan_07", amount: 2000, msg: "ユリの本音回ありがとう", time: 3548 },
                ].map((s, i) => (
                  <div key={i} style={{ display: "flex", alignItems: "center", gap: 8, padding: 6, background: "var(--ink-deep)", borderRadius: 3, borderLeft: "3px solid var(--superchat)" }}>
                    <I.SC size={14} style={{ color: "var(--superchat)" }} />
                    <div style={{ minWidth: 0, flex: 1 }}>
                      <div style={{ fontSize: 11, color: "var(--text-primary)" }}>
                        {s.user} <span style={{ color: "var(--superchat)" }}>¥{s.amount}</span>
                      </div>
                      <div className="jp" style={{ fontSize: 11, color: "var(--text-secondary)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                        {s.msg}
                      </div>
                    </div>
                    <span className="mono dim" style={{ fontSize: 10 }}>{fmtTime(s.time)}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}

function StatCard({ label, value, sub, icon, accent }) {
  const IconC = icon ? I[icon] : null;
  const accentColor = accent === "amber" ? "var(--amber)" : accent === "danger" ? "var(--danger)" : null;
  return (
    <div className="stat-card">
      {IconC && <IconC className="stat-card__accent" size={14} />}
      <div className="stat-card__label">{label}</div>
      <div className="stat-card__value" style={accentColor ? { color: accentColor } : null}>{value}</div>
      <div className="stat-card__sub">{sub}</div>
    </div>
  );
}

function ChatActivityChart() {
  const w = 800, h = 100;
  const data = DENSITY;
  const path = data.map((d, i) => {
    const x = (i / (data.length - 1)) * w;
    const y = h - d * h * 0.9;
    return `${i === 0 ? "M" : "L"} ${x.toFixed(1)} ${y.toFixed(1)}`;
  }).join(" ");
  const areaPath = path + ` L ${w} ${h} L 0 ${h} Z`;

  return (
    <div style={{ position: "relative" }}>
      <svg viewBox={`0 0 ${w} ${h}`} style={{ width: "100%", height: 110 }} preserveAspectRatio="none">
        <defs>
          <linearGradient id="density-grad" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="var(--amber)" stopOpacity="0.5" />
            <stop offset="100%" stopColor="var(--amber)" stopOpacity="0" />
          </linearGradient>
        </defs>
        {/* Grid lines */}
        {[0.25, 0.5, 0.75].map((y) => (
          <line key={y} x1="0" x2={w} y1={h * y} y2={h * y} stroke="var(--ink-border)" strokeWidth="0.5" strokeDasharray="2 4" />
        ))}
        <path d={areaPath} fill="url(#density-grad)" />
        <path d={path} fill="none" stroke="var(--amber)" strokeWidth="1.2" />
        {/* Spikes as dots */}
        {HOT_SPOTS.map((i) => (
          <circle key={i} cx={(i / (data.length - 1)) * w} cy={h - data[i] * h * 0.9} r="2.5" fill="var(--chat-spike)" />
        ))}
        {/* SC markers */}
        {[20, 47, 79, 138, 174].map((i) => (
          <g key={i} transform={`translate(${(i / (data.length - 1)) * w}, ${h - 4})`}>
            <line y1="-8" y2="0" stroke="var(--superchat)" strokeWidth="1.5" />
            <circle cx="0" cy="-10" r="2" fill="var(--superchat)" />
          </g>
        ))}
      </svg>
      <div style={{ display: "flex", justifyContent: "space-between", fontFamily: "var(--font-mono)", fontSize: 9, color: "var(--text-tertiary)", letterSpacing: "0.1em", marginTop: 4 }}>
        <span>{fmtTime(0)}</span>
        <span>{fmtTime(VIDEO_DURATION * 0.25)}</span>
        <span>{fmtTime(VIDEO_DURATION * 0.5)}</span>
        <span>{fmtTime(VIDEO_DURATION * 0.75)}</span>
        <span>{fmtTime(VIDEO_DURATION)}</span>
      </div>
    </div>
  );
}

/* ─────────────────────────────────────────────
   TIMELINE VIEWER
   ───────────────────────────────────────────── */
function TimelinePage({ initialTime }) {
  const [expanded, setExpanded] = uS1(new Set([43, 87]));
  const [selected, setSelected] = uS1(43);
  const [filterScene, setFilterScene] = uS1("all");
  const [filterSpeaker, setFilterSpeaker] = uS1("all");
  const [query, setQuery] = uS1("");
  const [showWaveform, setShowWaveform] = uS1(true);

  const toggle = (idx) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx); else next.add(idx);
      return next;
    });
  };

  const filtered = FEATURED_SEGMENTS.filter((s) => {
    if (filterScene !== "all" && s.scene !== filterScene) return false;
    if (filterSpeaker !== "all") {
      const speakers = [s.ocr?.speaker, s.asr?.speaker].filter(Boolean);
      if (!speakers.includes(filterSpeaker)) return false;
    }
    if (query && !(s.ocr?.text + s.asr?.text).toLowerCase().includes(query.toLowerCase())) return false;
    return true;
  });

  return (
    <>
      <Topbar
        title="Timeline"
        jpTitle="タイムライン"
        breadcrumb={`${STATS.totalSegments} segments`}
        actions={
          <>
            <div className="select-wrap">
              <select className="select" value={filterScene} onChange={(e) => setFilterScene(e.target.value)}>
                <option value="all">all scenes</option>
                {SCENE_TYPES.map((s) => <option key={s.id} value={s.id}>{s.id}</option>)}
              </select>
            </div>
            <div className="select-wrap">
              <select className="select" value={filterSpeaker} onChange={(e) => setFilterSpeaker(e.target.value)}>
                <option value="all">all speakers</option>
                {CHARACTERS.map((c) => <option key={c.id} value={c.name}>{c.name}</option>)}
                <option value="streamer">streamer</option>
              </select>
            </div>
            <div className="input" style={{ width: 220 }}>
              <I.Search className="input__icon" size={12} />
              <input placeholder="搜尋台詞 / OCR / ASR..." value={query} onChange={(e) => setQuery(e.target.value)} />
              <span className="input__hot">F</span>
            </div>
            <div className="input" style={{ width: 130 }}>
              <span className="input__icon mono" style={{ fontSize: 10, width: "auto" }}>⏱</span>
              <input placeholder="00:__:__" />
              <span className="input__hot">G</span>
            </div>
          </>
        }
      />

      <div className="page-content" style={{ display: "flex", flexDirection: "column" }}>
        {/* Ruler */}
        <div style={{ position: "sticky", top: 0, zIndex: 5, background: "var(--ink)", borderBottom: "1px solid var(--ink-border)", padding: "12px 20px 8px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 8 }}>
            <span className="mono dim" style={{ fontSize: 10, letterSpacing: "0.16em" }}>RULER</span>
            <div className="flex-1" />
            <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11, color: "var(--text-secondary)", cursor: "pointer" }}>
              <span className={"toggle " + (showWaveform ? "toggle--on" : "")} onClick={() => setShowWaveform(!showWaveform)} />
              密度波形
            </label>
            <button className="btn btn--sm btn--ghost"><I.Filter size={11} /> score ≥ 0</button>
          </div>
          <TimelineThumbnail height={64} showWaveform={showWaveform} playhead={765} />
          {/* Time scale */}
          <div style={{ position: "relative", height: 16, marginTop: 4 }}>
            {[0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1].map((p) => (
              <div key={p} style={{
                position: "absolute",
                left: `${p * 100}%`,
                transform: "translateX(-50%)",
                fontFamily: "var(--font-mono)",
                fontSize: 9,
                color: "var(--text-tertiary)",
                letterSpacing: "0.1em",
              }}>
                {fmtTime(VIDEO_DURATION * p)}
              </div>
            ))}
          </div>
        </div>

        {/* Segment list */}
        <div style={{ padding: "16px 20px", flex: 1 }}>
          <div className="section-header">
            <span className="section-header__title">Segments</span>
            <span className="section-header__count">{filtered.length} of {STATS.totalSegments} visible · virtual scroll</span>
            <div className="section-header__after">
              <span className="kbd">↑</span><span className="kbd">↓</span>
              <span className="dim" style={{ fontSize: 10 }}>navigate</span>
              <span className="kbd">↵</span>
              <span className="dim" style={{ fontSize: 10 }}>expand</span>
            </div>
          </div>

          {filtered.map((seg) => (
            <SegmentCard
              key={seg.idx}
              seg={seg}
              expanded={expanded.has(seg.idx)}
              selected={selected === seg.idx}
              onClick={() => setSelected(seg.idx)}
              onToggle={() => toggle(seg.idx)}
            />
          ))}

          {/* Spacer with virtual scroll hint */}
          <div style={{
            textAlign: "center",
            padding: "20px 0",
            color: "var(--text-tertiary)",
            fontFamily: "var(--font-mono)",
            fontSize: 10,
            letterSpacing: "0.16em",
            borderTop: "1px dashed var(--ink-border)",
            marginTop: 12,
          }}>
            — {STATS.totalSegments - filtered.length} more segments below (virtual scroll) —
          </div>
        </div>
      </div>
    </>
  );
}

/* ─────────────────────────────────────────────
   SEARCH
   ───────────────────────────────────────────── */
const SEARCH_MODES = [
  { id: "character", label: "角色", jp: "キャラ", icon: "User", placeholder: "輸入角色名（例: ケイ / ユリ / ハルカ）" },
  { id: "keyword",   label: "關鍵字", jp: "キーワード", icon: "Search", placeholder: "輸入關鍵字（會在 OCR / ASR / Chat 中搜尋）" },
  { id: "reaction",  label: "反應", jp: "リアクション", icon: "Reaction", placeholder: "top N reactions（按 score 排序）" },
  { id: "chapter",   label: "章節", jp: "チャプター", icon: "Folder", placeholder: "章節名 / 事件標籤" },
  { id: "conflict",  label: "衝突", jp: "コンフリクト", icon: "Conflict", placeholder: "篩選 conflict / unverified 段落" },
  { id: "sc",        label: "SC", jp: "スパチャ", icon: "SC", placeholder: "查看所有 superchat 段落（按金額排序）" },
];

const SEARCH_RESULTS_BY_MODE = {
  character: [
    { time: 525, scene: "dialogue", char: "ケイ", jp: "はじめまして。", asr: "欸這是誰啊好可愛", chat: 12, score: 34 },
    { time: 763, scene: "dialogue", char: "ケイ", jp: "君は、ここにいてくれるのか。", asr: "啊啊啊他這句好溫柔我不行了", chat: 23, score: 67, spike: true },
    { time: 920, scene: "dialogue", char: "ケイ", jp: "大丈夫だよ。", asr: "ケイ太溫柔了吧", chat: 28, score: 45, spike: true },
    { time: 1655, scene: "dialogue", char: "ケイ", jp: "お前は伺を言っているんだ", asr: "他在說什麼啊？", chat: 14, score: 45, conflict: true },
    { time: 3548, scene: "dialogue", char: "ケイ", jp: "ユリ……すまない。", asr: "ケイ你說啊！說啊！", chat: 31, score: 58 },
    { time: 5210, scene: "dialogue", char: "ケイ", jp: "選ぶのは君だ。", asr: "選哪個選哪個！", chat: 64, score: 73, spike: true },
    { time: 6753, scene: "dialogue", char: "ケイ", jp: "また、明日。", asr: "啊啊啊結尾這句太狠了", chat: 51, score: 68, spike: true },
  ],
  keyword: [],
  reaction: [],
  chapter: [],
  conflict: [],
  sc: [],
};

function SearchPage({ onJump }) {
  const [mode, setMode] = uS1("character");
  const [query, setQuery] = uS1("ケイ");
  const [topN, setTopN] = uS1(20);
  const [sortBy, setSortBy] = uS1("time");

  const modeInfo = SEARCH_MODES.find((m) => m.id === mode);
  const results = SEARCH_RESULTS_BY_MODE.character;

  return (
    <>
      <Topbar title="Search" jpTitle="検索"
        actions={<>
          <button className="btn btn--ghost"><I.Copy size={13} /> Copy as List</button>
          <button className="btn"><I.Download size={13} /> Export CSV</button>
        </>}
      />
      <div className="page-content">
        <div className="page-pad" style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          {/* Mode tabs */}
          <div className="search-mode-tabs">
            {SEARCH_MODES.map((m) => {
              const IconC = I[m.icon];
              return (
                <button key={m.id}
                  className={"search-mode-tabs__item" + (mode === m.id ? " search-mode-tabs__item--active" : "")}
                  onClick={() => setMode(m.id)}>
                  <IconC size={13} />
                  <span>{m.label}</span>
                  <span className="jp dim" style={{ fontSize: 10, marginLeft: 2 }}>{m.jp}</span>
                </button>
              );
            })}
          </div>

          {/* Search input */}
          <div className="panel">
            <div className="panel__body" style={{ display: "flex", gap: 10, alignItems: "center" }}>
              <div className="input flex-1" style={{ padding: "10px 14px" }}>
                <I.Search className="input__icon" size={16} />
                <input placeholder={modeInfo.placeholder} value={query} onChange={(e) => setQuery(e.target.value)}
                  style={{ fontSize: 14 }} />
              </div>
              <div className="select-wrap">
                <select className="select" value={topN} onChange={(e) => setTopN(e.target.value)}>
                  <option value="10">top 10</option>
                  <option value="20">top 20</option>
                  <option value="50">top 50</option>
                  <option value="all">all</option>
                </select>
              </div>
              <div className="select-wrap">
                <select className="select" value={sortBy} onChange={(e) => setSortBy(e.target.value)}>
                  <option value="time">sort: time ↑</option>
                  <option value="score">sort: score ↓</option>
                  <option value="chat">sort: chat ↓</option>
                </select>
              </div>
              <button className="btn btn--amber">
                <I.Search size={12} /> 搜尋
              </button>
            </div>
          </div>

          {/* Results */}
          <div className="panel">
            <div className="panel__head">
              <span className="panel__title">Results</span>
              <span className="panel__label">{results.length} 筆 · 角色 = ケイ · ja → zh-TW</span>
              <div style={{ marginLeft: "auto", display: "flex", gap: 6, fontSize: 11, color: "var(--text-tertiary)", fontFamily: "var(--font-mono)" }}>
                <span>共 0.012s</span>
                <span>·</span>
                <span>scope: 1,247 segments</span>
              </div>
            </div>
            <div>
              {results.map((r, i) => (
                <div key={i}
                  onClick={() => onJump?.(r.time)}
                  style={{
                    display: "grid",
                    gridTemplateColumns: "80px 90px 1fr 110px",
                    gap: 14,
                    padding: "12px 16px",
                    borderTop: i === 0 ? "none" : "1px solid color-mix(in srgb, var(--ink-border) 50%, transparent)",
                    cursor: "pointer",
                    transition: "background 100ms",
                  }}
                  onMouseEnter={(e) => e.currentTarget.style.background = "var(--ink-hover)"}
                  onMouseLeave={(e) => e.currentTarget.style.background = "transparent"}
                >
                  <div className="mono" style={{ fontSize: 12, color: "var(--amber)" }}>
                    {fmtTime(r.time)}
                  </div>
                  <div><SceneBadge scene={r.scene} /></div>
                  <div style={{ display: "flex", flexDirection: "column", gap: 4, minWidth: 0 }}>
                    <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
                      <SpeakerBadge name={r.char} />
                      <span className="jp" style={{ fontSize: 14, color: "var(--text-jp)" }}>{r.jp}</span>
                    </div>
                    <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
                      <span className="mono dim" style={{ fontSize: 10, letterSpacing: "0.12em" }}>ASR ▸</span>
                      <span style={{ fontSize: 12, color: "var(--text-secondary)" }}>{r.asr}</span>
                    </div>
                  </div>
                  <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 4 }}>
                    <ScoreBadge score={r.score} />
                    <span className="mono dim" style={{ fontSize: 10 }}>{r.chat} msgs {r.spike && <span style={{ color: "var(--chat-spike)" }}>● SPIKE</span>}</span>
                    {r.conflict && <span className="badge badge--status-conflict" style={{ fontSize: 9, padding: "1px 5px" }}>⚠ conflict</span>}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Saved queries (suggestion) */}
          <div className="panel">
            <div className="panel__head">
              <I.Pin size={13} style={{ color: "var(--text-tertiary)" }}/>
              <span className="panel__title">Saved Queries</span>
            </div>
            <div className="panel__body" style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
              {[
                "char: ケイ", "char: ユリ", "char: ハルカ",
                "kw: 大丈夫", "kw: 好きだ", "kw: 帰ろう",
                "reaction: top 20", "conflict: pending",
                "sc: amount ≥ 1000",
              ].map((q, i) => (
                <button key={i} className="pill" style={{ fontSize: 11 }}>{q}</button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </>
  );
}

Object.assign(window, { DashboardPage, TimelinePage, SearchPage });
