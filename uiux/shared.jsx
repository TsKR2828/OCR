/* Shared components: Sidebar, Topbar, Statusbar, Badges, SegmentCard, TimelineRuler */

const { useState, useEffect, useRef, useMemo, useCallback } = React;

const NAV = [
  { id: "dashboard", label: "Dashboard", jp: "ダッシュボード", icon: "Dashboard", hot: "1" },
  { id: "timeline", label: "Timeline", jp: "タイムライン", icon: "Timeline", hot: "2" },
  { id: "search", label: "Search", jp: "検索", icon: "Search", hot: "3" },
  { id: "conflict", label: "Conflict Review", jp: "衝突審稿", icon: "Conflict", hot: "4" },
  { id: "clips", label: "Clips", jp: "精彩片段", icon: "Clips", hot: "5" },
  { id: "stats", label: "Stats", jp: "統計", icon: "Stats", hot: "6" },
  { id: "settings", label: "Settings", jp: "設定", icon: "Settings", hot: "7" },
];

function Sidebar({ active, onNav, conflictsPending }) {
  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <div className="sidebar-brand__mark">VN</div>
        <div>
          <div className="sidebar-brand__name">VN-TRANSCRIBE</div>
          <div className="sidebar-brand__sub">v0.4.2 — STRUCTURED</div>
        </div>
      </div>

      <div className="sidebar-section">
        <div className="sidebar-section__label">WORKSPACE</div>
        <nav className="sidebar-nav">
          {NAV.map((n) => {
            const IconC = I[n.icon];
            return (
              <button
                key={n.id}
                className={"nav-item" + (active === n.id ? " nav-item--active" : "")}
                onClick={() => onNav(n.id)}
              >
                <IconC className="nav-item__icon" />
                <span>{n.label}</span>
                {n.id === "conflict" && conflictsPending > 0 && (
                  <span className="badge badge--status-conflict" style={{ marginLeft: "auto", padding: "1px 5px", fontSize: 9 }}>
                    {conflictsPending}
                  </span>
                )}
                {!(n.id === "conflict" && conflictsPending > 0) && (
                  <span className="nav-item__hot">⌘{n.hot}</span>
                )}
              </button>
            );
          })}
        </nav>
      </div>

      <div className="sidebar-info">
        <div className="sidebar-info__row">
          <span className="sidebar-info__label">FILE</span>
        </div>
        <div className="sidebar-info__file" title={CHANNEL.file}>{CHANNEL.file}</div>
        <div className="sidebar-info__row" style={{ marginTop: 4 }}>
          <span className="sidebar-info__label">GAME</span>
        </div>
        <div style={{ fontFamily: "var(--font-jp)", fontSize: 11, color: "var(--text-primary)" }}>{CHANNEL.game}</div>
        <div style={{ borderTop: "1px solid var(--ink-border)", marginTop: 8, paddingTop: 8, display: "flex", flexDirection: "column", gap: 4 }}>
          <div className="sidebar-info__row">
            <span className="sidebar-info__label">DURATION</span>
            <span className="sidebar-info__value">{fmtTime(STATS.duration)}</span>
          </div>
          <div className="sidebar-info__row">
            <span className="sidebar-info__label">SEGMENTS</span>
            <span className="sidebar-info__value">{STATS.totalSegments.toLocaleString()}</span>
          </div>
          <div className="sidebar-info__row">
            <span className="sidebar-info__label">CONFLICTS</span>
            <span className="sidebar-info__value" style={{ color: "var(--danger)" }}>{STATS.conflicts - STATS.resolvedConflicts}</span>
          </div>
        </div>
      </div>
    </aside>
  );
}

function Topbar({ title, jpTitle, actions, breadcrumb }) {
  return (
    <header className="topbar">
      <div className="topbar__title">
        <span className="topbar__title-main">{title}</span>
        {jpTitle && <span className="topbar__title-sub jp">/ {jpTitle}</span>}
        {breadcrumb && <span className="topbar__title-sub">— {breadcrumb}</span>}
      </div>
      <div className="topbar__actions">{actions}</div>
    </header>
  );
}

function Statusbar({ page }) {
  return (
    <div className="statusbar">
      <span className="statusbar__dot" />
      <span>PIPELINE IDLE</span>
      <span className="statusbar__sep" />
      <span>OCR: 1,247 / 1,247</span>
      <span className="statusbar__sep" />
      <span>ASR: large-v3 · ja</span>
      <span className="statusbar__sep" />
      <span>CHAT: 18,432 msgs</span>
      <div className="statusbar__right">
        <span>PAGE: {page.toUpperCase()}</span>
        <span>UTC+09:00</span>
        <span>NIGHTFALL THEME</span>
      </div>
    </div>
  );
}

/* ── Badge helpers ── */
function SceneBadge({ scene, jp }) {
  const map = {
    dialogue: { label: "dialogue", jp: "対話" },
    reaction: { label: "reaction", jp: "反応" },
    narration: { label: "narration", jp: "ナレ" },
    choice: { label: "choice", jp: "選択" },
    transition: { label: "transition", jp: "転場" },
    silence: { label: "silence", jp: "沈黙" },
  };
  const m = map[scene] || { label: scene };
  return <span className={`badge badge--${scene}`}>{jp ? m.jp : m.label}</span>;
}

function ScoreBadge({ score }) {
  const tier = score >= 60 ? "high" : score >= 30 ? "mid" : "low";
  return (
    <span className={`badge badge--score badge--score-${tier}`}>
      <span style={{ opacity: 0.7, fontSize: 9 }}>SCORE</span>
      <span>{score}</span>
    </span>
  );
}

function SpeakerBadge({ name, kind }) {
  if (!name) return null;
  const color =
    name === "ケイ" ? "var(--scene-dialogue)" :
    name === "ユリ" ? "var(--scene-narration)" :
    name === "ハルカ" ? "var(--scene-reaction)" :
    name === "streamer" ? "var(--amber)" : "var(--text-secondary)";
  return (
    <span className="badge badge--speaker" style={{ color, borderColor: `color-mix(in srgb, ${color} 35%, transparent)` }}>
      {name === "streamer" ? "夜風" : name}
    </span>
  );
}

/* ── Segment Card ── */
function SegmentCard({ seg, expanded, selected, onToggle, onClick, compact }) {
  const sceneColor = `var(--scene-${seg.scene})`;
  const cls = ["segment-card"];
  if (expanded) cls.push("segment-card--expanded");
  if (selected) cls.push("segment-card--selected");
  if (seg.status === "conflict") cls.push("segment-card--conflict");

  return (
    <div className={cls.join(" ")} style={{ "--scene-color": sceneColor }} onClick={onClick}>
      <div className="segment-card__head">
        <span className="segment-card__idx">#{String(seg.idx).padStart(4, "0")}</span>
        <span className="segment-card__time">
          {fmtTime(seg.start)}
          <span className="segment-card__time-arrow"> → </span>
          {fmtTime(seg.end)}
        </span>
        <span className="dim mono" style={{ fontSize: 10 }}>{(seg.end - seg.start).toFixed(1)}s</span>
        <div className="segment-card__head-right">
          <SceneBadge scene={seg.scene} />
          {seg.events?.includes("chat_spike") && (
            <span className="badge badge--spike">
              <I.Spike size={9} /> SPIKE
            </span>
          )}
          {seg.events?.includes("superchat") && (
            <span className="badge badge--sc">
              <I.SC size={9} /> SC
            </span>
          )}
          <ScoreBadge score={seg.score} />
        </div>
      </div>

      {seg.ocr?.text && (
        <div className="segment-card__layer segment-card__layer--ocr">
          <div className="segment-card__layer-label">
            <I.Eye size={10} style={{ marginRight: 3, verticalAlign: -1 }} />
            OCR
          </div>
          <div className="segment-card__layer-body">
            {seg.ocr.speaker && <SpeakerBadge name={seg.ocr.speaker} />}
            <span className="segment-card__jp-text">{seg.ocr.text}</span>
          </div>
        </div>
      )}

      {seg.asr?.text && (
        <div className="segment-card__layer segment-card__layer--asr">
          <div className="segment-card__layer-label">
            <I.Mic size={10} style={{ marginRight: 3, verticalAlign: -1 }} />
            ASR
          </div>
          <div className="segment-card__layer-body">
            {seg.asr.speaker && <SpeakerBadge name={seg.asr.speaker} />}
            <span className="segment-card__asr-text">{seg.asr.text}</span>
          </div>
        </div>
      )}

      {seg.chat && (
        <div className="segment-card__layer segment-card__layer--chat">
          <div className="segment-card__layer-label">
            <I.Chat size={10} style={{ marginRight: 3, verticalAlign: -1 }} />
            CHAT
          </div>
          <div className={"segment-card__chat-stats" + (seg.chat.spike ? " segment-card__chat-stats--spike" : "")}>
            <span><strong>{seg.chat.count}</strong> msgs</span>
            <span><strong>{seg.chat.rate}</strong>/min</span>
            {seg.chat.spike && <span style={{ color: "var(--chat-spike)" }}>● SPIKE</span>}
            {seg.chat.sc?.map((s, i) => (
              <span key={i} style={{ color: "var(--superchat)" }}>
                SC: {s.user} ¥{s.amount}
              </span>
            ))}
          </div>
        </div>
      )}

      <div className="segment-card__foot">
        <span>merge: {seg.merge}</span>
        <span>·</span>
        <span className={
          seg.status === "consistent" ? "badge badge--status-ok" :
          seg.status === "conflict" ? "badge badge--status-conflict" :
          "badge badge--status-unverified"
        } style={{ padding: "1px 5px", fontSize: 9 }}>
          {seg.status === "consistent" ? "✓ consistent" :
           seg.status === "conflict" ? "⚠ conflict" : "○ unverified"}
        </span>
        {seg.events?.length > 0 && (
          <>
            <span>·</span>
            <span>{seg.events.length} event{seg.events.length > 1 ? "s" : ""}</span>
          </>
        )}
        <div className="segment-card__foot-right">
          <button className="segment-card__expand-btn" onClick={(e) => { e.stopPropagation(); onToggle?.(); }}>
            {expanded ? "收合" : "展開"} <I.Chevron size={10} style={{ transform: expanded ? "rotate(180deg)" : "none" }} />
          </button>
        </div>
      </div>

      {expanded && (
        <div className="segment-card__expanded-area">
          <div className="score-breakdown">
            <div className="score-breakdown__title">SCORE BREAKDOWN</div>
            {[
              ["volume", "音量"],
              ["laughter", "笑聲"],
              ["keyword", "關鍵字"],
              ["chat", "聊天密度"],
              ["speech_rate", "語速突變"],
              ["silence_burst", "靜默爆發"],
            ].map(([key, label]) => (
              <div className="score-bar" key={key}>
                <span className="score-bar__label">{label}</span>
                <div className="score-bar__track">
                  <div className="score-bar__fill" style={{ width: `${(seg.breakdown?.[key] || 0) * 4}%` }} />
                </div>
                <span className="score-bar__value">{seg.breakdown?.[key] || 0}</span>
              </div>
            ))}
          </div>

          <div className="event-list">
            <div className="score-breakdown__title">EVENTS</div>
            {seg.events?.length > 0 ? seg.events.map((e, i) => (
              <div className="event-list__item" key={i}>
                <span style={{ color: "var(--amber)" }}>●</span> {e}
              </div>
            )) : <div className="dim" style={{ fontSize: 11 }}>— no events —</div>}
            {seg.conflict_note && (
              <div style={{
                marginTop: 8, padding: 8,
                background: "color-mix(in srgb, var(--danger) 12%, transparent)",
                borderRadius: 3, fontSize: 11, color: "var(--danger)",
                border: "1px solid color-mix(in srgb, var(--danger) 30%, transparent)"
              }}>
                <strong style={{ display: "block", fontFamily: "var(--font-mono)", fontSize: 9, letterSpacing: "0.16em", marginBottom: 4 }}>CONFLICT</strong>
                {seg.conflict_note}
              </div>
            )}
          </div>

          <div className="event-list">
            <div className="score-breakdown__title">CHAT SAMPLE</div>
            {seg.chat?.spike ? (
              <>
                <div className="event-list__item">夜風さん最高すぎる</div>
                <div className="event-list__item">これは泣くわ……</div>
                <div className="event-list__item">ケイ尊い</div>
                <div className="event-list__item">配信主の反応かわいい</div>
                <div className="event-list__item dim">... +{(seg.chat?.count || 4) - 4} more</div>
              </>
            ) : (
              <div className="dim" style={{ fontSize: 11 }}>chat density normal</div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

/* ── Timeline ruler component (mini + large) ── */
function TimelineThumbnail({ onClick, height = 56, showWaveform = true, showHotspots = true, playhead }) {
  const total = DENSITY.length;
  const ref = useRef(null);
  const handleClick = (e) => {
    const rect = ref.current.getBoundingClientRect();
    const pct = (e.clientX - rect.left) / rect.width;
    onClick?.(pct * VIDEO_DURATION);
  };

  return (
    <div
      ref={ref}
      onClick={handleClick}
      style={{
        position: "relative",
        height,
        background: "var(--ink-deep)",
        borderRadius: 4,
        border: "1px solid var(--ink-border)",
        cursor: "pointer",
        overflow: "hidden",
      }}
    >
      {/* Scene band — bottom 30% */}
      <div style={{ position: "absolute", left: 0, right: 0, bottom: 0, height: "30%", display: "flex" }}>
        {SCENE_BAND.map((s, i) => (
          <div key={i} style={{
            flex: 1,
            background: `var(--scene-${s})`,
            opacity: 0.75,
          }} />
        ))}
      </div>

      {/* Density waveform */}
      {showWaveform && (
        <div style={{ position: "absolute", left: 0, right: 0, top: 0, bottom: "30%", display: "flex", alignItems: "flex-end" }}>
          {DENSITY.map((d, i) => (
            <div key={i} style={{
              flex: 1,
              height: `${d * 100}%`,
              background: HOT_SPOTS.includes(i) ? "var(--amber)" : "color-mix(in srgb, var(--text-secondary) 60%, transparent)",
              opacity: HOT_SPOTS.includes(i) ? 0.95 : 0.5,
              marginRight: 1,
            }} />
          ))}
        </div>
      )}

      {/* Hotspot markers */}
      {showHotspots && HOT_SPOTS.map((i) => (
        <div key={i} style={{
          position: "absolute",
          left: `${(i / total) * 100}%`,
          top: 0, height: "70%",
          width: 1,
          background: "var(--amber)",
          opacity: 0.5,
          pointerEvents: "none",
        }} />
      ))}

      {/* Playhead */}
      {playhead != null && (
        <div style={{
          position: "absolute",
          left: `${(playhead / VIDEO_DURATION) * 100}%`,
          top: 0, bottom: 0, width: 2,
          background: "var(--amber)",
          boxShadow: "0 0 6px var(--amber)",
        }} />
      )}

      {/* Time labels */}
      <div style={{ position: "absolute", left: 0, right: 0, top: 0, height: 14, display: "flex", justifyContent: "space-between", padding: "0 4px", pointerEvents: "none" }}>
        {[0, 0.25, 0.5, 0.75, 1].map((p) => (
          <span key={p} style={{
            fontFamily: "var(--font-mono)",
            fontSize: 8,
            color: "var(--text-tertiary)",
            background: "var(--ink-deep)",
            padding: "0 3px",
            letterSpacing: "0.06em",
          }}>{fmtTime(VIDEO_DURATION * p)}</span>
        ))}
      </div>
    </div>
  );
}

/* ── Pill toggle row ── */
function PillRow({ items, value, onChange, showAll = true }) {
  return (
    <div className="pill-row">
      {showAll && (
        <button className={"pill" + (value === "all" ? " pill--active" : "")} onClick={() => onChange("all")}>
          全部
        </button>
      )}
      {items.map((it) => (
        <button key={it.id}
          className={"pill" + (value === it.id ? " pill--active" : "")}
          onClick={() => onChange(it.id)}>
          <span className="pill__dot" style={{ background: it.color }} />
          {it.label}
          {it.count != null && <span className="pill__count">{it.count}</span>}
        </button>
      ))}
    </div>
  );
}

/* ── Empty state ── */
function EmptyState({ icon, title, hint, action }) {
  const IconC = icon ? I[icon] : null;
  return (
    <div style={{
      padding: 40, textAlign: "center",
      border: "1px dashed var(--ink-border)",
      borderRadius: 8,
      color: "var(--text-tertiary)",
    }}>
      {IconC && <IconC size={32} style={{ color: "var(--ink-hover)", marginBottom: 12 }} />}
      <div style={{ fontSize: 13, color: "var(--text-secondary)", marginBottom: 6 }}>{title}</div>
      {hint && <div style={{ fontSize: 11 }}>{hint}</div>}
      {action}
    </div>
  );
}

Object.assign(window, {
  NAV, Sidebar, Topbar, Statusbar,
  SceneBadge, ScoreBadge, SpeakerBadge,
  SegmentCard, TimelineThumbnail, PillRow, EmptyState,
});
