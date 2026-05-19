/* Main app — router + tweaks + global keybindings */
const { useState, useEffect, useCallback } = React;

const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "accent": "gold",
  "density": "comfortable",
  "showSidebarInfo": true,
  "scenePalette": "default",
  "monoFont": "IBM Plex Mono",
  "serifHeadings": true
}/*EDITMODE-END*/;

function App() {
  const [page, setPage] = useState("dashboard");
  const [conflictDecisions, setConflictDecisions] = useState({});
  const [t, setTweak] = useTweaks(TWEAK_DEFAULTS);

  // Compute pending conflicts for sidebar badge
  const pending = CONFLICTS.filter((c) => c.status === "pending" && !conflictDecisions[c.idx]).length;

  // Apply tweaks
  useEffect(() => {
    const r = document.documentElement;
    // Brass / library accent palette — warm, low-saturation
    const accents = {
      gold:      { main: "#C9A86A", dim: "#A08550", deep: "#7F6A3F" }, // 燙金
      brass:     { main: "#B89968", dim: "#8E764E", deep: "#6E5A39" }, // 黃銅
      copper:    { main: "#C28868", dim: "#9D6B4F", deep: "#754F3A" }, // 紅銅
      verdigris: { main: "#7AA89A", dim: "#5E8678", deep: "#456359" }, // 銅綠
    };
    const a = accents[t.accent] || accents.gold;
    r.style.setProperty("--amber", a.main);
    r.style.setProperty("--amber-dim", a.dim);
    r.style.setProperty("--amber-deep", a.deep);
    r.style.setProperty("--amber-glow", `color-mix(in srgb, ${a.main} 15%, transparent)`);
    r.style.setProperty("--amber-glow-strong", `color-mix(in srgb, ${a.main} 28%, transparent)`);

    // Scene palette — dusk library defaults, muted/vivid as variants
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

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
