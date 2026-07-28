/* Main app — landing page, router, tweaks, global keybindings */
const { useState, useEffect, useCallback, useRef } = React;

const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "accent": "gold",
  "density": "comfortable",
  "showSidebarInfo": true,
  "scenePalette": "default",
  "monoFont": "IBM Plex Mono",
  "serifHeadings": true
}/*EDITMODE-END*/;

/* ── Landing page — file picker / drag-drop for timeline.json ── */
function LandingPage({ onLoaded }) {
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const fileRef = useRef(null);

  const handleFile = async (file) => {
    if (!file) return;
    setError(null);
    setLoading(true);
    try {
      await window.loadTimelineFile(file);
      onLoaded();
    } catch (e) {
      setError(`載入失敗: ${e.message}`);
      setLoading(false);
    }
  };

  const onDrop = (e) => {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  };

  return (
    <div
      onDrop={onDrop}
      onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
      onDragLeave={() => setDragging(false)}
      style={{
        display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
        height: "100vh", background: "var(--ink-base, #161825)",
        fontFamily: "var(--font-sans, system-ui, sans-serif)",
      }}
    >
      {/* Brand */}
      <div style={{ marginBottom: 32, textAlign: "center" }}>
        <div style={{
          display: "inline-flex", alignItems: "center", gap: 12,
          fontFamily: "var(--font-mono, monospace)", letterSpacing: "0.18em",
          fontSize: 28, color: "var(--amber, #C9A86A)", fontWeight: 700,
        }}>
          <span style={{
            display: "inline-flex", alignItems: "center", justifyContent: "center",
            width: 48, height: 48, background: "var(--amber, #C9A86A)",
            color: "var(--ink-base, #161825)", borderRadius: 6, fontSize: 20, fontWeight: 800,
          }}>VN</span>
          VN-TRANSCRIBE
        </div>
        <div style={{
          marginTop: 8, fontFamily: "var(--font-mono, monospace)", fontSize: 11,
          letterSpacing: "0.1em", color: "var(--text-tertiary, #555)",
        }}>STRUCTURED TIMELINE VIEWER</div>
      </div>

      {/* Drop zone */}
      <div
        onClick={() => fileRef.current?.click()}
        style={{
          width: 420, padding: "48px 32px", textAlign: "center",
          border: `2px dashed ${dragging ? "var(--amber, #C9A86A)" : "var(--ink-border, #2a2c40)"}`,
          borderRadius: 12,
          background: dragging ? "var(--amber-glow, rgba(201,168,106,0.15))" : "var(--ink-light, #1e2035)",
          cursor: "pointer", transition: "all 0.2s",
        }}
      >
        {loading ? (
          <div style={{ color: "var(--amber, #C9A86A)", fontSize: 14 }}>
            <span style={{ display: "inline-block", animation: "spin 1s linear infinite",
              border: "2px solid var(--ink-border, #2a2c40)",
              borderTop: "2px solid var(--amber, #C9A86A)",
              borderRadius: "50%", width: 20, height: 20, marginBottom: 8,
            }} />
            <div>讀取中…</div>
          </div>
        ) : (
          <>
            <div style={{ fontSize: 36, marginBottom: 12, opacity: 0.5 }}>
              {I?.Import ? <I.Import size={36} style={{ color: "var(--amber, #C9A86A)", opacity: 0.6 }} /> : "📂"}
            </div>
            <div style={{ fontSize: 14, color: "var(--text-primary, #ddd)", marginBottom: 8 }}>
              將 <code style={{ color: "var(--amber, #C9A86A)", fontFamily: "var(--font-mono, monospace)",
                background: "var(--ink-deep, #12141f)", padding: "2px 6px", borderRadius: 4, fontSize: 13,
              }}>timeline.json</code> 拖放至此
            </div>
            <div style={{ fontSize: 11, color: "var(--text-tertiary, #555)" }}>
              或點擊選取檔案
            </div>
          </>
        )}
        <input
          ref={fileRef}
          type="file"
          accept=".json"
          style={{ display: "none" }}
          onChange={(e) => { handleFile(e.target.files[0]); e.target.value = ""; }}
        />
      </div>

      {error && (
        <div style={{
          marginTop: 16, padding: "8px 16px", maxWidth: 420,
          background: "color-mix(in srgb, var(--danger, #c44) 15%, transparent)",
          border: "1px solid var(--danger, #c44)",
          borderRadius: 6, fontSize: 12, color: "var(--danger, #c44)",
        }}>{error}</div>
      )}

      <div style={{
        marginTop: 24, fontSize: 10, color: "var(--text-tertiary, #555)",
        fontFamily: "var(--font-mono, monospace)", letterSpacing: "0.06em",
      }}>
        VN-Transcribe pipeline 產出的 timeline.json · OCR / ASR / Chat
      </div>

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}

/* ── Main dashboard app (only mounts after data is loaded) ── */
function App() {
  const [page, setPage] = useState("dashboard");
  const [conflictDecisions, setConflictDecisions] = useState({});
  const [t, setTweak] = useTweaks(TWEAK_DEFAULTS);

  const pending = CONFLICTS.filter((c) => c.status === "pending" && !conflictDecisions[c.idx]).length;

  // Apply tweaks
  useEffect(() => {
    const r = document.documentElement;
    const accents = {
      gold:      { main: "#C9A86A", dim: "#A08550", deep: "#7F6A3F" },
      brass:     { main: "#B89968", dim: "#8E764E", deep: "#6E5A39" },
      copper:    { main: "#C28868", dim: "#9D6B4F", deep: "#754F3A" },
      verdigris: { main: "#7AA89A", dim: "#5E8678", deep: "#456359" },
    };
    const a = accents[t.accent] || accents.gold;
    r.style.setProperty("--amber", a.main);
    r.style.setProperty("--amber-dim", a.dim);
    r.style.setProperty("--amber-deep", a.deep);
    r.style.setProperty("--amber-glow", `color-mix(in srgb, ${a.main} 15%, transparent)`);
    r.style.setProperty("--amber-glow-strong", `color-mix(in srgb, ${a.main} 28%, transparent)`);

    if (t.scenePalette === "muted") {
      r.style.setProperty("--scene-dialogue", "#6C8FA8");
      r.style.setProperty("--scene-narration", "#83749E");
      r.style.setProperty("--scene-reaction", "#9C4D40");
      r.style.setProperty("--scene-choice", "#B89C56");
    } else if (t.scenePalette === "vivid") {
      r.style.setProperty("--scene-dialogue", "#90BDD4");
      r.style.setProperty("--scene-narration", "#B099D0");
      r.style.setProperty("--scene-reaction", "#D06A56");
      r.style.setProperty("--scene-choice", "#E6CD7C");
    } else {
      r.style.setProperty("--scene-dialogue", "#7FA8C4");
      r.style.setProperty("--scene-narration", "#9A8AB8");
      r.style.setProperty("--scene-reaction", "#B85A4A");
      r.style.setProperty("--scene-choice", "#D4B96A");
    }

    if (t.monoFont === "JetBrains Mono") {
      r.style.setProperty("--font-mono", '"JetBrains Mono", monospace');
    } else if (t.monoFont === "Geist Mono") {
      r.style.setProperty("--font-mono", '"Geist Mono", monospace');
    } else {
      r.style.setProperty("--font-mono", '"IBM Plex Mono", monospace');
    }
  }, [t.accent, t.scenePalette, t.monoFont]);

  // Keyboard nav
  useEffect(() => {
    const handler = (e) => {
      if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA") return;
      if (e.metaKey || e.ctrlKey) {
        const map = { "1": "dashboard", "2": "timeline", "3": "search", "4": "conflict", "5": "clips", "6": "stats", "7": "settings" };
        if (map[e.key]) {
          e.preventDefault();
          setPage(map[e.key]);
        }
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  const handleResolve = useCallback((conflictIdx, choice) => {
    setConflictDecisions((prev) => ({ ...prev, [conflictIdx]: choice }));
  }, []);

  const handleJump = useCallback((time) => {
    setPage("timeline");
  }, []);

  let pageEl = null;
  if (page === "dashboard") pageEl = <DashboardPage onJump={handleJump} onNav={setPage} />;
  else if (page === "timeline") pageEl = <TimelinePage />;
  else if (page === "search") pageEl = <SearchPage onJump={handleJump} />;
  else if (page === "conflict") pageEl = <ConflictPage conflicts={CONFLICTS} decisions={conflictDecisions} onResolve={handleResolve} />;
  else if (page === "clips") pageEl = <ClipsPage onJump={handleJump} />;
  else if (page === "stats") pageEl = <StatsPage />;
  else if (page === "settings") pageEl = <SettingsPage />;

  return (
    <>
      <div className="app-shell" data-screen-label={`${page}`} style={{
        "--ink-light": t.density === "compact" ? "#1f2138" : "#232440",
      }}>
        <Sidebar active={page} onNav={setPage} conflictsPending={pending} />
        <div className="main-area">
          {pageEl}
        </div>
        <Statusbar page={page} />
      </div>

      <TweaksPanel title="Tweaks">
        <TweakSection label="Accent — 強調金屬">
          <TweakColor
            label="Highlight"
            value={t.accent}
            onChange={(v) => setTweak("accent", v)}
            options={["gold", "brass", "copper", "verdigris"]}
          />
        </TweakSection>

        <TweakSection label="Scene Palette">
          <TweakRadio
            label="Variant"
            value={t.scenePalette}
            onChange={(v) => setTweak("scenePalette", v)}
            options={["default", "muted", "vivid"]}
          />
        </TweakSection>

        <TweakSection label="Typography">
          <TweakSelect
            label="Mono font"
            value={t.monoFont}
            onChange={(v) => setTweak("monoFont", v)}
            options={["IBM Plex Mono", "JetBrains Mono", "Geist Mono"]}
          />
        </TweakSection>

        <TweakSection label="Density">
          <TweakRadio
            label="Spacing"
            value={t.density}
            onChange={(v) => setTweak("density", v)}
            options={["comfortable", "compact"]}
          />
        </TweakSection>
      </TweaksPanel>
    </>
  );
}

/* ── Shell: landing → dashboard switch ── */
function AppShell() {
  const [ready, setReady] = useState(window._VNT?.loaded || false);

  useEffect(() => {
    if (ready) return;
    if (window._VNT?.loaded) { setReady(true); return; }
    window._VNT?.onLoad(() => setReady(true));
  }, [ready]);

  if (!ready) return <LandingPage onLoaded={() => setReady(true)} />;
  return <App />;
}

ReactDOM.createRoot(document.getElementById("root")).render(<AppShell />);
