/* Pages part 2: Conflict, Clips, Stats, Settings */

const { useState: uS2, useEffect: uE2, useMemo: uM2 } = React;

/* ─────────────────────────────────────────────
   CONFLICT REVIEW
   ───────────────────────────────────────────── */
function ConflictPage({ onResolve, conflicts, decisions }) {
  const [idx, setIdx] = uS2(0);
  const [editMode, setEditMode] = uS2(false);
  const [editValue, setEditValue] = uS2("");

  const pending = conflicts.filter((c) => !decisions[c.idx]);
  const resolved = conflicts.length - pending.length;
  const current = pending[idx] || conflicts[0];

  const renderDiff = (text, otherText, isOcr) => {
    // Simple char-by-char diff highlight (works for our hand-crafted samples)
    const t = text.split("");
    const o = otherText.split("");
    return t.map((ch, i) => {
      if (o[i] !== ch) {
        return <span key={i} className={isOcr ? "diff-highlight-del" : "diff-highlight-add"}>{ch}</span>;
      }
      return <span key={i}>{ch}</span>;
    });
  };

  const handleResolve = (choice) => {
    if (!current) return;
    onResolve(current.idx, choice);
    setEditMode(false);
    setEditValue("");
    // Stay on same index — next item slides in
  };

  if (!current) {
    return (
      <>
        <Topbar title="Conflict Review" jpTitle="衝突審稿" actions={<button className="btn btn--success"><I.Check size={13} /> 全部完成</button>} />
        <div className="page-content"><div className="page-pad">
          <EmptyState icon="Check" title="所有衝突已審畢" hint="共處理 47 筆。可前往 Timeline 或 Clips 繼續工作。" />
        </div></div>
      </>
    );
  }

  return (
    <>
      <Topbar
        title="Conflict Review"
        jpTitle="衝突審稿"
        breadcrumb={`待審 ${pending.length} / ${conflicts.length}`}
        actions={<>
          <button className="btn btn--ghost" onClick={() => exportConflictJSON(conflicts, decisions)}><I.Download size={13} /> 匯出 JSON</button>
          <button className="btn">快速模式 <span className="kbd">⌥K</span></button>
        </>}
      />
      <div className="page-content">
        <div className="page-pad" style={{ maxWidth: 920, margin: "0 auto", display: "flex", flexDirection: "column", gap: 14 }}>
          {/* Progress */}
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <div className="progress-bar" style={{ flex: 1 }}>
              <div className="progress-bar__fill" style={{ width: `${(resolved / conflicts.length) * 100}%` }} />
            </div>
            <div className="mono" style={{ fontSize: 12 }}>
              <span style={{ color: "var(--success)" }}>{resolved}</span>
              <span className="dim"> / {conflicts.length}</span>
              <span className="dim" style={{ marginLeft: 8 }}>({((resolved / conflicts.length) * 100).toFixed(0)}%)</span>
            </div>
          </div>

          {/* Header */}
          <div className="panel">
            <div className="panel__head">
              <span className="panel__title">衝突 #{current.idx}</span>
              <span className="panel__label">SEGMENT #{String(current.segmentIdx).padStart(4, "0")} · {fmtTime(current.time)}</span>
              <div style={{ marginLeft: "auto", display: "flex", gap: 6, alignItems: "center" }}>
                <span className="mono dim" style={{ fontSize: 10 }}>CONFIDENCE</span>
                <div style={{ width: 80, height: 4, background: "var(--ink-hover)", borderRadius: 2, overflow: "hidden" }}>
                  <div style={{ width: `${current.confidence * 100}%`, height: "100%", background: current.confidence > 0.7 ? "var(--success)" : current.confidence > 0.4 ? "var(--warning)" : "var(--danger)" }} />
                </div>
                <span className="mono" style={{ fontSize: 11 }}>{(current.confidence * 100).toFixed(0)}%</span>
              </div>
            </div>

            <div className="panel__body" style={{ display: "flex", flexDirection: "column", gap: 0 }}>
              {/* OCR */}
              <div className="diff-block diff-block--ocr">
                <div className="diff-block__head">
                  <I.Eye size={12} style={{ color: "var(--scene-dialogue)" }} />
                  <span className="diff-block__source" style={{ color: "var(--scene-dialogue)" }}>OCR · 畫面文字</span>
                  <span style={{ marginLeft: "auto" }} className="mono dim" style={{ fontSize: 10 }}>
                    confidence 0.84
                  </span>
                </div>
                <div className="diff-block__text">{renderDiff(current.ocr, current.asr, true)}</div>
              </div>

              <div className="diff-vs">VS</div>

              {/* ASR */}
              <div className="diff-block diff-block--asr">
                <div className="diff-block__head">
                  <I.Mic size={12} style={{ color: "var(--amber)" }} />
                  <span className="diff-block__source" style={{ color: "var(--amber)" }}>ASR · 語音辨識</span>
                  <span className="mono dim" style={{ fontSize: 10, marginLeft: "auto" }}>ASR · {CHANNEL.game_language || "ja"}</span>
                </div>
                <div className="diff-block__text">{renderDiff(current.asr, current.ocr, false)}</div>
              </div>
            </div>
          </div>

          {/* Suggestion */}
          <div style={{
            padding: 14,
            background: "color-mix(in srgb, var(--amber) 8%, var(--ink-light))",
            border: "1px solid color-mix(in srgb, var(--amber) 30%, var(--ink-border))",
            borderRadius: 6,
            display: "flex",
            gap: 12,
          }}>
            <I.Alert size={18} style={{ color: "var(--amber)", flexShrink: 0, marginTop: 2 }} />
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 11, fontFamily: "var(--font-mono)", letterSpacing: "0.16em", color: "var(--amber)", marginBottom: 4 }}>
                SYSTEM SUGGESTION — 建議採用 {current.suggestion.toUpperCase()}
              </div>
              <div style={{ fontSize: 12, color: "var(--text-primary)", lineHeight: 1.55 }}>
                {current.reason}
              </div>
            </div>
          </div>

          {/* Manual edit */}
          {editMode && (
            <div style={{ padding: 14, background: "var(--ink-deep)", border: "1px solid var(--ink-border)", borderRadius: 6 }}>
              <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, letterSpacing: "0.16em", color: "var(--text-tertiary)", marginBottom: 8 }}>
                MANUAL CORRECTION
              </div>
              <div className="input" style={{ padding: "10px 14px" }}>
                <input
                  className="jp"
                  style={{ fontSize: 16 }}
                  placeholder="輸入修正後文字..."
                  value={editValue || current.ocr}
                  onChange={(e) => setEditValue(e.target.value)}
                  autoFocus
                />
              </div>
              <div style={{ display: "flex", gap: 6, marginTop: 8 }}>
                <button className="btn btn--success btn--sm" onClick={() => handleResolve("manual")}>
                  <I.Check size={11} /> 套用修正
                </button>
                <button className="btn btn--ghost btn--sm" onClick={() => setEditMode(false)}>
                  取消 <span className="kbd">Esc</span>
                </button>
              </div>
            </div>
          )}

          {/* Actions */}
          {!editMode && (
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr", gap: 8 }}>
              <button className="btn btn--success" style={{ justifyContent: "center", padding: "12px 0" }} onClick={() => handleResolve("ocr")}>
                <span className="kbd">1</span> 採用 OCR
              </button>
              <button className="btn btn--success" style={{ justifyContent: "center", padding: "12px 0" }} onClick={() => handleResolve("asr")}>
                <span className="kbd">2</span> 採用 ASR
              </button>
              <button className="btn" style={{ justifyContent: "center", padding: "12px 0" }} onClick={() => setEditMode(true)}>
                <span className="kbd">3</span> 手動修正
              </button>
              <button className="btn btn--ghost" style={{ justifyContent: "center", padding: "12px 0", border: "1px solid var(--ink-border)" }} onClick={() => handleResolve("skip")}>
                <span className="kbd">Space</span> 跳過
              </button>
            </div>
          )}

          {/* Navigation */}
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "12px 0", borderTop: "1px solid var(--ink-border)" }}>
            <button className="btn btn--ghost" onClick={() => setIdx(Math.max(0, idx - 1))} disabled={idx === 0}>
              <I.ChevronLeft size={13} /> <span className="kbd">←</span> 上一筆
            </button>
            <div className="mono dim" style={{ fontSize: 11, letterSpacing: "0.1em" }}>
              {idx + 1} / {pending.length}
            </div>
            <button className="btn btn--ghost" onClick={() => setIdx(Math.min(pending.length - 1, idx + 1))} disabled={idx >= pending.length - 1}>
              下一筆 <span className="kbd">→</span> <I.ChevronRight size={13} />
            </button>
          </div>

          {/* Mini queue */}
          <div className="panel">
            <div className="panel__head">
              <span className="panel__title">Queue</span>
              <span className="panel__label">前後 5 筆</span>
            </div>
            <div className="panel__body" style={{ padding: 0 }}>
              {pending.slice(Math.max(0, idx - 2), idx + 4).map((c, i) => {
                const isCurrent = c.idx === current.idx;
                return (
                  <div key={c.idx}
                    style={{
                      display: "grid",
                      gridTemplateColumns: "32px 80px 1fr 80px",
                      gap: 10,
                      padding: "8px 16px",
                      borderTop: i === 0 ? "none" : "1px solid color-mix(in srgb, var(--ink-border) 40%, transparent)",
                      background: isCurrent ? "var(--amber-glow)" : "transparent",
                      cursor: "pointer",
                    }}
                  >
                    <span className="mono" style={{ fontSize: 11, color: isCurrent ? "var(--amber)" : "var(--text-tertiary)" }}>
                      #{c.idx}
                    </span>
                    <span className="mono" style={{ fontSize: 11 }}>{fmtTime(c.time)}</span>
                    <span className="jp" style={{ fontSize: 12, color: "var(--text-jp)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                      {c.ocr}
                    </span>
                    <span className="mono dim" style={{ fontSize: 10, textAlign: "right" }}>
                      建議: {c.suggestion}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Hotkey hint */}
          <div style={{ display: "flex", gap: 14, fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--text-tertiary)", justifyContent: "center", padding: "8px 0" }}>
            <span><span className="kbd">1</span> ocr</span>
            <span><span className="kbd">2</span> asr</span>
            <span><span className="kbd">3</span> edit</span>
            <span><span className="kbd">␣</span> skip</span>
            <span><span className="kbd">←</span><span className="kbd">→</span> nav</span>
            <span><span className="kbd">Esc</span> close</span>
          </div>
        </div>
      </div>
    </>
  );
}

/* ─────────────────────────────────────────────
   CLIPS BROWSER
   ───────────────────────────────────────────── */
function ClipsPage({ onJump }) {
  const [filter, setFilter] = uS2("all");
  const [sort, setSort] = uS2("score");
  const [selected, setSelected] = uS2(CLIPS[0].id);

  const filtered = filter === "all" ? CLIPS : CLIPS.filter((c) => c.scene === filter);
  const sorted = [...filtered].sort((a, b) =>
    sort === "score" ? b.score - a.score :
    sort === "time" ? a.start - b.start :
    sort === "sc" ? b.sc - a.sc : 0
  );

  const sel = CLIPS.find((c) => c.id === selected);

  return (
    <>
      <Topbar
        title="Clips"
        jpTitle="精彩片段"
        breadcrumb={`${STATS.highlights} 個片段`}
        actions={<>
          <button className="btn btn--ghost" onClick={() => exportChapters()}><I.Download size={13} /> .chapters</button>
          <button className="btn btn--ghost" onClick={() => exportSRT()}><I.Download size={13} /> .srt</button>
          <button className="btn btn--amber" onClick={() => exportEDL()}><I.Download size={13} /> EDL (CMX 3600)</button>
        </>}
      />
      <div className="page-content">
        <div style={{ display: "grid", gridTemplateColumns: "1fr 340px", height: "100%" }}>
          {/* Main */}
          <div className="page-pad" style={{ overflowY: "auto" }}>
            <div style={{ display: "flex", alignItems: "center", marginBottom: 14, gap: 12 }}>
              <PillRow
                items={SCENE_TYPES.filter((s) => ["dialogue", "reaction", "choice", "narration"].includes(s.id))
                  .map((s) => ({ ...s, color: `var(--scene-${s.id})` }))}
                value={filter}
                onChange={setFilter}
              />
              <div style={{ marginLeft: "auto" }} className="select-wrap">
                <select className="select" value={sort} onChange={(e) => setSort(e.target.value)}>
                  <option value="score">sort: score ↓</option>
                  <option value="time">sort: time ↑</option>
                  <option value="sc">sort: SC ¥ ↓</option>
                </select>
              </div>
            </div>

            <div className="clips-grid">
              {sorted.map((c, i) => (
                <div key={c.id}
                  className={"clip-card" + (selected === c.id ? " clip-card--selected" : "")}
                  onClick={() => setSelected(c.id)}
                >
                  <div className="clip-card__thumb">
                    <div className="clip-card__thumb-top">
                      <span className="clip-card__rank">#{String(i + 1).padStart(2, "0")}</span>
                      <span className="clip-card__duration">{(c.end - c.start).toFixed(0)}s</span>
                    </div>
                    <div className="clip-card__thumb-overlay">
                      <div className="clip-card__time">{fmtTime(c.start)} → {fmtTime(c.end)}</div>
                    </div>
                    {/* Mini score viz at bottom of thumb */}
                    <div style={{ position: "absolute", left: 0, right: 0, bottom: 0, height: 3, zIndex: 2 }}>
                      <div style={{
                        width: `${c.score}%`, height: "100%",
                        background: c.score >= 60 ? "var(--score-high)" : c.score >= 30 ? "var(--score-mid)" : "var(--score-low)",
                      }} />
                    </div>
                  </div>
                  <div className="clip-card__body">
                    <div className="clip-card__quote clip-card__quote--jp">{c.quoteJp}</div>
                    <div className="dim tc" style={{ fontSize: 11, fontStyle: "italic" }}>「{c.quote}」</div>
                    <div className="clip-card__meta">
                      <ScoreBadge score={c.score} />
                      <SceneBadge scene={c.scene} />
                      {c.sc > 0 && (
                        <span className="badge badge--sc" style={{ marginLeft: "auto" }}>
                          <I.SC size={9} /> ¥{c.sc.toLocaleString()}
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Detail panel */}
          <aside style={{
            borderLeft: "1px solid var(--ink-border)",
            background: "var(--ink-deep)",
            overflowY: "auto",
            padding: 20,
            display: "flex",
            flexDirection: "column",
            gap: 14,
          }}>
            {sel && (
              <>
                <div>
                  <div className="mono dim" style={{ fontSize: 10, letterSpacing: "0.16em" }}>SELECTED CLIP</div>
                  <div className="jp" style={{ fontSize: 18, color: "var(--text-jp)", marginTop: 6, lineHeight: 1.4 }}>
                    {sel.title}
                  </div>
                  <div className="mono" style={{ fontSize: 12, color: "var(--amber)", marginTop: 4 }}>
                    {fmtTime(sel.start)} → {fmtTime(sel.end)}  ·  {(sel.end - sel.start).toFixed(1)}s
                  </div>
                </div>

                {/* Mock player */}
                <div style={{
                  aspectRatio: "16 / 9",
                  background: "repeating-linear-gradient(45deg, var(--ink), var(--ink) 8px, var(--ink-hover) 8px, var(--ink-hover) 9px)",
                  borderRadius: 4,
                  border: "1px solid var(--ink-border)",
                  position: "relative",
                  display: "grid",
                  placeItems: "center",
                }}>
                  <button style={{
                    width: 48, height: 48, borderRadius: "50%",
                    background: "var(--amber)", color: "var(--ink-deep)",
                    display: "grid", placeItems: "center",
                  }}>
                    <I.Play size={18} />
                  </button>
                  <div style={{ position: "absolute", left: 8, bottom: 8, right: 8, height: 4, background: "rgba(0,0,0,0.4)", borderRadius: 2, overflow: "hidden" }}>
                    <div style={{ width: "35%", height: "100%", background: "var(--amber)" }} />
                  </div>
                </div>

                <div className="col gap-sm">
                  <div className="mono dim" style={{ fontSize: 10, letterSpacing: "0.16em" }}>SCORE BREAKDOWN</div>
                  {[
                    ["volume", "音量", 14],
                    ["laughter", "笑聲", 11],
                    ["keyword", "關鍵字", 18],
                    ["chat", "聊天密度", 24],
                    ["speech_rate", "語速突變", 7],
                    ["silence_burst", "靜默爆發", 4],
                  ].map(([k, l, v]) => (
                    <div className="score-bar" key={k}>
                      <span className="score-bar__label">{l}</span>
                      <div className="score-bar__track">
                        <div className="score-bar__fill" style={{ width: `${v * 4}%` }} />
                      </div>
                      <span className="score-bar__value">{v}</span>
                    </div>
                  ))}
                  <div className="score-bar" style={{ marginTop: 6, paddingTop: 6, borderTop: "1px dashed var(--ink-border)" }}>
                    <span className="score-bar__label" style={{ fontWeight: 600 }}>TOTAL</span>
                    <div className="score-bar__track"><div className="score-bar__fill" style={{ width: `${sel.score}%` }} /></div>
                    <span className="score-bar__value" style={{ color: "var(--amber)", fontWeight: 600 }}>{sel.score}</span>
                  </div>
                </div>

                <div className="col gap-sm">
                  <div className="mono dim" style={{ fontSize: 10, letterSpacing: "0.16em" }}>EVENTS</div>
                  {["chat_spike", "streamer_reaction", "superchat"].map((e) => (
                    <div className="event-list__item" key={e}>
                      <span style={{ color: "var(--amber)" }}>●</span> {e}
                    </div>
                  ))}
                </div>

                <div className="col gap-sm">
                  <div className="mono dim" style={{ fontSize: 10, letterSpacing: "0.16em" }}>CHAT (PEAK)</div>
                  {[
                    "夜風さん泣いてる",
                    "ケイの目！ケイの目！",
                    "ここで¥1500投げる",
                    "神回確定",
                    "もう何度目だこのシーン",
                  ].map((msg, i) => (
                    <div key={i} className="jp" style={{
                      fontSize: 11,
                      color: "var(--text-secondary)",
                      padding: "4px 8px",
                      background: "var(--ink-light)",
                      borderRadius: 3,
                      borderLeft: i === 2 ? "2px solid var(--superchat)" : "1px solid var(--ink-border)",
                    }}>{msg}</div>
                  ))}
                </div>

                <div style={{ display: "flex", gap: 6, marginTop: "auto", paddingTop: 12, borderTop: "1px solid var(--ink-border)" }}>
                  <button className="btn btn--amber flex-1" onClick={() => onJump?.(sel.start)}>
                    <I.Play size={12} /> 播放片段
                  </button>
                  <button className="btn" style={{ flex: 1 }}>
                    <I.Timeline size={12} /> Viewer
                  </button>
                  <button className="btn btn--ghost"><I.Copy size={13} /></button>
                </div>
              </>
            )}
          </aside>
        </div>
      </div>
    </>
  );
}

/* ─────────────────────────────────────────────
   STATS
   ───────────────────────────────────────────── */
function StatsPage() {
  const [sortKey, setSortKey] = uS2("lines");

  const charSorted = [...CHARACTERS].sort((a, b) =>
    sortKey === "lines" ? b.lines - a.lines :
    sortKey === "first" ? a.firstAt - b.firstAt :
    sortKey === "last" ? b.lastAt - a.lastAt : 0
  );

  return (
    <>
      <Topbar title="Stats" jpTitle="統計"
        actions={<>
          <button className="btn btn--ghost" onClick={() => exportExcel()}><I.Download size={13} /> Export Excel</button>
          <button className="btn btn--amber" onClick={() => exportEditedTimeline()}><I.Download size={13} /> Export JSON</button>
        </>}
      />
      <div className="page-content">
        <div className="page-pad" style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          {/* Summary row */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12 }}>
            <StatBig label="總時長" jp="DURATION" value={fmtTime(STATS.duration)} sub={`${Math.floor(STATS.duration/3600)}h ${Math.floor((STATS.duration%3600)/60)}m ${Math.floor(STATS.duration%60)}s`} />
            <StatBig label="總段數" jp="SEGMENTS" value={STATS.totalSegments.toLocaleString()} sub={`平均 ${STATS.avgSegLen}s / 段`} />
            <StatBig label="精彩片段" jp="HIGHLIGHTS" value={STATS.highlights} sub="score ≥ 60" accent="amber" />
            <StatBig label="SC 總額" jp="SUPERCHATS" value={`¥${STATS.scTotal.toLocaleString()}`} sub={`${STATS.scDistinctUsers} unique users`} accent="superchat" />
          </div>

          {/* Character table */}
          <div className="panel">
            <div className="panel__head">
              <I.User size={14} />
              <span className="panel__title">Character Statistics</span>
              <span className="panel__label">CLICK COLUMN TO SORT</span>
            </div>
            <table className="data-table">
              <thead>
                <tr>
                  <th>角色</th>
                  <th>ALIASES</th>
                  <th onClick={() => setSortKey("lines")} style={{ color: sortKey === "lines" ? "var(--amber)" : null }}>台詞數 ↓</th>
                  <th onClick={() => setSortKey("first")} style={{ color: sortKey === "first" ? "var(--amber)" : null }}>首次出場</th>
                  <th onClick={() => setSortKey("last")} style={{ color: sortKey === "last" ? "var(--amber)" : null }}>最後出場</th>
                  <th>總時長</th>
                  <th>互動段</th>
                </tr>
              </thead>
              <tbody>
                {charSorted.map((c) => (
                  <tr key={c.id}>
                    <td>
                      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <span style={{ width: 8, height: 8, background: c.color, borderRadius: 2 }} />
                        <span className="jp" style={{ fontSize: 14 }}>{c.name}</span>
                      </div>
                    </td>
                    <td className="dim mono" style={{ fontSize: 11 }}>{c.aliases.join(", ")}</td>
                    <td className="num">{c.lines}</td>
                    <td className="num">{fmtTime(c.firstAt)}</td>
                    <td className="num">{fmtTime(c.lastAt)}</td>
                    <td className="num">{Math.floor(c.lines * 6.2)}s</td>
                    <td>
                      <div style={{ display: "flex", height: 4, background: "var(--ink-hover)", borderRadius: 2, overflow: "hidden", width: 80 }}>
                        <div style={{ width: `${(c.lines / 47) * 100}%`, background: c.color }} />
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Two columns: scene distribution + score histogram */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
            <div className="panel">
              <div className="panel__head">
                <span className="panel__title">Scene Distribution</span>
                <span className="panel__label">{STATS.totalSegments} TOTAL</span>
              </div>
              <div className="panel__body">
                <SceneDonut />
              </div>
            </div>

            <div className="panel">
              <div className="panel__head">
                <span className="panel__title">Score Histogram</span>
                <span className="panel__label">DISTRIBUTION</span>
              </div>
              <div className="panel__body">
                <ScoreHistogram />
              </div>
            </div>
          </div>

          {/* Chat density line */}
          <div className="panel">
            <div className="panel__head">
              <I.Chat size={14} />
              <span className="panel__title">Chat Density Over Time</span>
              <span className="panel__label">DENSITY / MIN · SPIKES MARKED</span>
            </div>
            <div className="panel__body">
              <ChatActivityChartLarge />
            </div>
          </div>

          {/* Top keywords */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
            <div className="panel">
              <div className="panel__head">
                <span className="panel__title">Top Reaction Keywords</span>
                <span className="panel__label">FROM ASR</span>
              </div>
              <div className="panel__body" style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                {[
                  ["好溫柔", 42, "tc"],
                  ["やばい", 38, "jp"],
                  ["不行了", 31, "tc"],
                  ["かわいい", 28, "jp"],
                  ["哈哈哈哈", 24, "tc"],
                  ["尊い", 22, "jp"],
                  ["選哪個", 19, "tc"],
                  ["神回", 18, "jp"],
                ].map(([w, c, lang]) => (
                  <div key={w} style={{ display: "grid", gridTemplateColumns: "100px 1fr 40px", gap: 8, alignItems: "center" }}>
                    <span className={lang} style={{ fontSize: 12 }}>{w}</span>
                    <div style={{ height: 6, background: "var(--ink-deep)", borderRadius: 3, overflow: "hidden" }}>
                      <div style={{ width: `${(c / 42) * 100}%`, height: "100%", background: "var(--amber)" }} />
                    </div>
                    <span className="mono dim" style={{ textAlign: "right" }}>{c}</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="panel">
              <div className="panel__head">
                <span className="panel__title">Events Summary</span>
                <span className="panel__label">TIMELINE EVENTS</span>
              </div>
              <div className="panel__body" style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {[
                  ["chapter_change", 12, "var(--scene-narration)"],
                  ["new_character", 3, "var(--scene-dialogue)"],
                  ["choice_point", 28, "var(--scene-choice)"],
                  ["streamer_reaction", 224, "var(--scene-reaction)"],
                  ["chat_spike", 16, "var(--chat-spike)"],
                  ["superchat", 24, "var(--superchat)"],
                ].map(([name, count, color]) => (
                  <div key={name} style={{ display: "flex", alignItems: "center", gap: 10, padding: "6px 10px", background: "var(--ink-deep)", borderRadius: 3, borderLeft: `3px solid ${color}` }}>
                    <span className="mono" style={{ fontSize: 11, color }}>●</span>
                    <span style={{ fontSize: 12 }}>{name}</span>
                    <span className="mono dim" style={{ marginLeft: "auto", fontVariantNumeric: "tabular-nums" }}>{count}</span>
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

function StatBig({ label, jp, value, sub, accent }) {
  const color = accent === "amber" ? "var(--amber)" :
                accent === "superchat" ? "var(--superchat)" : "var(--text-primary)";
  return (
    <div className="stat-card" style={{ padding: "16px 18px" }}>
      <div className="stat-card__label">
        <span>{jp}</span>
        <span className="dim" style={{ marginLeft: 6 }}>· {label}</span>
      </div>
      <div className="stat-card__value" style={{ color, fontSize: 30 }}>{value}</div>
      <div className="stat-card__sub">{sub}</div>
    </div>
  );
}

function SceneDonut() {
  const total = SCENE_TYPES.reduce((s, t) => s + t.count, 0);
  const r = 60, c = 2 * Math.PI * r;
  let offset = 0;
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 24 }}>
      <svg viewBox="0 0 160 160" style={{ width: 160, height: 160 }}>
        <circle cx="80" cy="80" r={r} fill="none" stroke="var(--ink-hover)" strokeWidth="20" />
        {SCENE_TYPES.map((s) => {
          const pct = s.count / total;
          const len = c * pct;
          const arc = (
            <circle key={s.id}
              cx="80" cy="80" r={r}
              fill="none"
              stroke={s.color}
              strokeWidth="20"
              strokeDasharray={`${len} ${c - len}`}
              strokeDashoffset={-offset}
              transform="rotate(-90 80 80)"
              opacity="0.9"
            />
          );
          offset += len;
          return arc;
        })}
        <text x="80" y="76" textAnchor="middle" fontFamily="var(--font-mono)" fontSize="20" fill="var(--text-primary)" fontWeight="600">{total}</text>
        <text x="80" y="92" textAnchor="middle" fontFamily="var(--font-mono)" fontSize="9" fill="var(--text-tertiary)" letterSpacing="0.16em">SEGMENTS</text>
      </svg>
      <div style={{ display: "flex", flexDirection: "column", gap: 6, flex: 1 }}>
        {SCENE_TYPES.map((s) => (
          <div key={s.id} style={{ display: "grid", gridTemplateColumns: "12px 1fr 50px 40px", gap: 8, fontSize: 12, alignItems: "center" }}>
            <span style={{ width: 10, height: 10, background: s.color, borderRadius: 2 }} />
            <span>{s.label}</span>
            <span className="mono">{s.count}</span>
            <span className="mono dim" style={{ textAlign: "right" }}>{((s.count / total) * 100).toFixed(1)}%</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function ScoreHistogram() {
  const max = Math.max(...STATS.scoreHistogram.map((b) => b.count));
  return (
    <div style={{ display: "flex", alignItems: "flex-end", gap: 4, height: 160 }}>
      {STATS.scoreHistogram.map((b, i) => {
        const tier = i < 3 ? "low" : i < 6 ? "mid" : "high";
        const color = tier === "high" ? "var(--score-high)" : tier === "mid" ? "var(--score-mid)" : "var(--score-low)";
        return (
          <div key={b.range} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: 4 }}>
            <span className="mono" style={{ fontSize: 10, color: "var(--text-primary)" }}>{b.count}</span>
            <div style={{
              width: "100%",
              height: `${(b.count / max) * 130}px`,
              background: color,
              opacity: 0.85,
              borderRadius: "3px 3px 0 0",
            }} />
            <span className="mono dim" style={{ fontSize: 9, letterSpacing: "0.08em" }}>{b.range}</span>
          </div>
        );
      })}
    </div>
  );
}

function ChatActivityChartLarge() {
  const w = 1000, h = 180;
  const data = DENSITY;
  const path = data.map((d, i) => {
    const x = (i / (data.length - 1)) * w;
    const y = h - d * h * 0.85;
    return `${i === 0 ? "M" : "L"} ${x.toFixed(1)} ${y.toFixed(1)}`;
  }).join(" ");
  const areaPath = path + ` L ${w} ${h} L 0 ${h} Z`;

  return (
    <div>
      <svg viewBox={`0 0 ${w} ${h}`} style={{ width: "100%", height: 200 }} preserveAspectRatio="none">
        <defs>
          <linearGradient id="density-grad-2" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="var(--amber)" stopOpacity="0.55" />
            <stop offset="100%" stopColor="var(--amber)" stopOpacity="0" />
          </linearGradient>
        </defs>
        {[0.25, 0.5, 0.75].map((y) => (
          <g key={y}>
            <line x1="0" x2={w} y1={h * y} y2={h * y} stroke="var(--ink-border)" strokeWidth="0.5" strokeDasharray="2 4" />
            <text x="4" y={h * y - 2} fontFamily="var(--font-mono)" fontSize="9" fill="var(--text-tertiary)">
              {Math.round((1 - y) * 350)}
            </text>
          </g>
        ))}
        <path d={areaPath} fill="url(#density-grad-2)" />
        <path d={path} fill="none" stroke="var(--amber)" strokeWidth="1.4" />
        {HOT_SPOTS.map((i) => (
          <g key={i}>
            <line x1={(i / (data.length - 1)) * w} x2={(i / (data.length - 1)) * w} y1={h - data[i] * h * 0.85} y2={h} stroke="var(--chat-spike)" strokeWidth="0.5" opacity="0.4" />
            <circle cx={(i / (data.length - 1)) * w} cy={h - data[i] * h * 0.85} r="3" fill="var(--chat-spike)" />
          </g>
        ))}
        {[20, 47, 79, 138, 174].map((i) => (
          <g key={i} transform={`translate(${(i / (data.length - 1)) * w}, ${h - 8})`}>
            <line y1="-10" y2="0" stroke="var(--superchat)" strokeWidth="1.5" />
            <polygon points="0,-14 -4,-8 4,-8" fill="var(--superchat)" />
          </g>
        ))}
      </svg>
      <div style={{ display: "flex", justifyContent: "space-between", fontFamily: "var(--font-mono)", fontSize: 9, color: "var(--text-tertiary)", letterSpacing: "0.1em", marginTop: 4 }}>
        {[0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1].map((p) => (
          <span key={p}>{fmtTime(VIDEO_DURATION * p)}</span>
        ))}
      </div>
      <div style={{ display: "flex", gap: 14, marginTop: 8, fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--text-secondary)" }}>
        <span><span style={{ color: "var(--amber)" }}>━</span> density</span>
        <span><span style={{ color: "var(--chat-spike)" }}>●</span> spike (16)</span>
        <span><span style={{ color: "var(--superchat)" }}>▼</span> superchat (5 of 24 shown)</span>
      </div>
    </div>
  );
}

/* ─────────────────────────────────────────────
   SETTINGS
   ───────────────────────────────────────────── */
function SettingsPage() {
  const [weights, setWeights] = uS2({
    volume: 1.0, laughter: 1.2, keyword: 1.5,
    chat: 1.8, speech_rate: 0.8, silence_burst: 0.6,
  });

  const [scoreThresh, setScoreThresh] = uS2(60);
  const [spikeThresh, setSpikeThresh] = uS2(180);

  return (
    <>
      <Topbar title="Settings" jpTitle="設定"
        actions={<>
          <button className="btn btn--ghost"><I.Upload size={13} /> 載入 channel.yaml</button>
          <button className="btn btn--amber"><I.Download size={13} /> 匯出 YAML</button>
        </>}
      />
      <div className="page-content">
        <div className="page-pad" style={{ maxWidth: 1000, display: "flex", flexDirection: "column", gap: 14 }}>
          {/* Channel */}
          <div className="settings-section">
            <div className="settings-section__head">
              <I.Folder size={14} />
              <span className="settings-section__title">頻道資訊</span>
              <span className="settings-section__sub">channel.yaml :: channel</span>
            </div>
            <div className="settings-grid">
              <div className="settings-row">
                <div className="settings-row__label">NAME 頻道名稱</div>
                <div className="input"><input defaultValue={CHANNEL.name} className="jp" /></div>
              </div>
              <div className="settings-row">
                <div className="settings-row__label">FILE 檔名</div>
                <div className="input"><input defaultValue={CHANNEL.file} /></div>
              </div>
              <div className="settings-row">
                <div className="settings-row__label">GAME_LANGUAGE 遊戲語言</div>
                <div className="select-wrap" style={{ width: "100%" }}>
                  <select className="select" style={{ width: "100%" }} defaultValue={CHANNEL.game_language || "ja"}>
                    <option value="ja">ja — 日本語</option>
                    <option value="en">en — English</option>
                    <option value="zh">zh — 中文</option>
                  </select>
                </div>
              </div>
              <div className="settings-row">
                <div className="settings-row__label">DEFAULT_LANGUAGE 預設語言</div>
                <div className="select-wrap" style={{ width: "100%" }}>
                  <select className="select" style={{ width: "100%" }} defaultValue={CHANNEL.default_language || "ja"}>
                    <option value="ja">ja — 日本語</option>
                    <option value="zh-TW">zh-TW — 繁體中文</option>
                    <option value="zh-CN">zh-CN — 简体中文</option>
                  </select>
                </div>
              </div>
            </div>
          </div>

          {/* ASR / OCR */}
          <div className="settings-section">
            <div className="settings-section__head">
              <I.Mic size={14} style={{ color: "var(--amber)" }} />
              <span className="settings-section__title">ASR · 語音辨識</span>
              <span className="settings-section__sub">whisper</span>
            </div>
            <div className="settings-grid">
              <div className="settings-row">
                <div className="settings-row__label">MODEL_SIZE</div>
                <div className="select-wrap" style={{ width: "100%" }}>
                  <select className="select" style={{ width: "100%" }} defaultValue="large-v3">
                    <option>tiny</option><option>base</option><option>small</option><option>medium</option>
                    <option>large-v3</option><option>large-v3-turbo</option>
                  </select>
                </div>
              </div>
              <div className="settings-row">
                <div className="settings-row__label">DEVICE</div>
                <div className="select-wrap" style={{ width: "100%" }}>
                  <select className="select" style={{ width: "100%" }} defaultValue="cuda">
                    <option>cpu</option><option>cuda</option><option>mps</option>
                  </select>
                </div>
              </div>
              <div className="settings-row">
                <div className="settings-row__label">VAD_THRESHOLD 語音判定閾值</div>
                <SliderRow value={0.5} min={0} max={1} step={0.05} />
              </div>
              <div className="settings-row">
                <div className="settings-row__label">BEAM_SIZE 解碼束寬</div>
                <SliderRow value={5} min={1} max={10} step={1} />
              </div>
            </div>
          </div>

          {/* Chat */}
          <div className="settings-section">
            <div className="settings-section__head">
              <I.Chat size={14} />
              <span className="settings-section__title">CHAT · 聊天室分析</span>
              <span className="settings-section__sub">chat_density</span>
            </div>
            <div className="settings-grid">
              <div className="settings-row">
                <div className="settings-row__label">SPIKE_THRESHOLD 爆量閾值 (msg/min)</div>
                <SliderRow value={spikeThresh} min={50} max={500} step={10} onChange={setSpikeThresh} />
                <div className="settings-row__hint">高於此值的密度視為 spike，目前匹配 16 段</div>
              </div>
              <div className="settings-row">
                <div className="settings-row__label">WINDOW_SEC 滑動視窗（秒）</div>
                <SliderRow value={30} min={5} max={120} step={5} />
              </div>
              <div className="settings-row">
                <div className="settings-row__label">MAX_MESSAGES 每段最多保留</div>
                <SliderRow value={50} min={10} max={200} step={10} />
              </div>
              <div className="settings-row">
                <div className="settings-row__label">SC_MIN_AMOUNT 最低 SC 金額</div>
                <SliderRow value={100} min={0} max={5000} step={100} suffix="¥" />
              </div>
            </div>
          </div>

          {/* OCR */}
          <div className="settings-section">
            <div className="settings-section__head">
              <I.Eye size={14} />
              <span className="settings-section__title">OCR · 畫面文字辨識</span>
              <span className="settings-section__sub">paddleocr</span>
            </div>
            <div className="settings-grid">
              <div className="settings-row">
                <div className="settings-row__label">SAMPLE_INTERVAL 取樣間隔 (s)</div>
                <SliderRow value={0.5} min={0.1} max={3} step={0.1} suffix="s" />
              </div>
              <div className="settings-row">
                <div className="settings-row__label">HASH_THRESHOLD 重複幀閾值</div>
                <SliderRow value={8} min={0} max={32} step={1} />
              </div>
              <div className="settings-row">
                <div className="settings-row__label">MIN_DURATION 最短保留時長 (s)</div>
                <SliderRow value={0.8} min={0.1} max={5} step={0.1} suffix="s" />
              </div>
              <div className="settings-row">
                <div className="settings-row__label">MAX_DURATION 最長合併時長 (s)</div>
                <SliderRow value={8} min={1} max={30} step={1} suffix="s" />
              </div>
            </div>
          </div>

          {/* Scoring */}
          <div className="settings-section">
            <div className="settings-section__head">
              <I.Reaction size={14} style={{ color: "var(--score-high)" }} />
              <span className="settings-section__title">SCORING · 精彩度評分</span>
              <span className="settings-section__sub">scoring.weights</span>
              <button className="btn btn--ghost btn--sm" style={{ marginLeft: 8 }}>恢復預設</button>
            </div>
            <div className="settings-grid">
              {Object.entries(weights).map(([key, val]) => (
                <div className="settings-row" key={key}>
                  <div className="settings-row__label">{key.toUpperCase()} {({
                    volume: "音量峰值",
                    laughter: "笑聲偵測",
                    keyword: "關鍵字命中",
                    chat: "聊天密度",
                    speech_rate: "語速突變",
                    silence_burst: "靜默 → 爆發",
                  })[key]}</div>
                  <SliderRow value={val} min={0} max={3} step={0.1}
                    onChange={(v) => setWeights({ ...weights, [key]: v })}
                    suffix="×" />
                </div>
              ))}
              <div className="settings-row" style={{ gridColumn: "1 / 3" }}>
                <div className="settings-row__label">SCORE_THRESHOLD 精彩判定 (highlight 入選)</div>
                <SliderRow value={scoreThresh} min={0} max={100} step={1} onChange={setScoreThresh} />
                <div className="settings-row__hint">
                  目前 score ≥ {scoreThresh} 的段落：<span className="amber mono">{STATS.highlights}</span> 個 highlights
                </div>
              </div>
            </div>
          </div>

          {/* Characters */}
          <div className="settings-section">
            <div className="settings-section__head">
              <I.User size={14} />
              <span className="settings-section__title">角色管理</span>
              <span className="settings-section__sub">{CHARACTERS.length} characters</span>
              <button className="btn btn--ghost btn--sm" style={{ marginLeft: "auto" }}>+ 新增角色</button>
            </div>
            <div style={{ padding: 12, display: "flex", flexDirection: "column", gap: 8 }}>
              {CHARACTERS.map((c) => (
                <div key={c.id} style={{
                  display: "grid",
                  gridTemplateColumns: "12px 100px 1fr 100px 32px",
                  gap: 10,
                  alignItems: "center",
                  padding: 8,
                  background: "var(--ink-deep)",
                  borderRadius: 4,
                  borderLeft: `3px solid ${c.color}`,
                }}>
                  <input type="color" defaultValue={c.color} style={{ width: 16, height: 16, border: "none", background: "none", padding: 0 }} />
                  <div className="input"><input defaultValue={c.name} className="jp" style={{ fontSize: 13 }}/></div>
                  <div className="input"><input defaultValue={c.aliases.join(", ")} placeholder="aliases (逗號分隔)" /></div>
                  <div className="mono dim" style={{ fontSize: 11, textAlign: "right" }}>{c.lines} 台詞</div>
                  <button className="btn btn--ghost btn--sm" style={{ padding: 4 }}><I.Close size={12} /></button>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </>
  );
}

function SliderRow({ value, min, max, step, onChange, suffix = "" }) {
  return (
    <div className="settings-slider">
      <input type="range" min={min} max={max} step={step} value={value} onChange={(e) => onChange?.(Number(e.target.value))} />
      <span className="settings-slider__value">{value}{suffix}</span>
    </div>
  );
}

Object.assign(window, { ConflictPage, ClipsPage, StatsPage, SettingsPage });
