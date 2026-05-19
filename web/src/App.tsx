import { useState, useEffect, useCallback } from 'react';
import { Sidebar } from './components/Sidebar';
import { Statusbar } from './components/Statusbar';
import { DashboardPage } from './pages/Dashboard';
import { TimelinePage } from './pages/Timeline';
import { SearchPage } from './pages/Search';
import { ConflictPage } from './pages/Conflict';
import { ClipsPage } from './pages/Clips';
import { StatsPage } from './pages/Stats';
import { SettingsPage } from './pages/Settings';
import { CONFLICTS } from './data/mock';
import type { PageId, AccentColor, ScenePalette } from './types';

export default function App() {
  const [page, setPage] = useState<PageId>('dashboard');
  const [conflictDecisions, setConflictDecisions] = useState<Record<number, string>>({});
  const [accent, setAccent] = useState<AccentColor>('gold');
  const [scenePalette] = useState<ScenePalette>('default');

  const pending = CONFLICTS.filter((c) => c.status === 'pending' && !conflictDecisions[c.idx]).length;

  // Apply accent colors
  useEffect(() => {
    const r = document.documentElement;
    const accents = {
      gold:      { main: '#C9A86A', dim: '#A08550', deep: '#7F6A3F' },
      brass:     { main: '#B89968', dim: '#8E764E', deep: '#6E5A39' },
      copper:    { main: '#C28868', dim: '#9D6B4F', deep: '#754F3A' },
      verdigris: { main: '#7AA89A', dim: '#5E8678', deep: '#456359' },
    };
    const a = accents[accent];
    r.style.setProperty('--amber', a.main);
    r.style.setProperty('--amber-dim', a.dim);
    r.style.setProperty('--amber-deep', a.deep);
    r.style.setProperty('--amber-glow', `color-mix(in srgb, ${a.main} 15%, transparent)`);
    r.style.setProperty('--amber-glow-strong', `color-mix(in srgb, ${a.main} 28%, transparent)`);

    if (scenePalette === 'muted') {
      r.style.setProperty('--scene-dialogue', '#6C8FA8');
      r.style.setProperty('--scene-narration', '#83749E');
      r.style.setProperty('--scene-reaction', '#9C4D40');
      r.style.setProperty('--scene-choice', '#B89C56');
    } else if (scenePalette === 'vivid') {
      r.style.setProperty('--scene-dialogue', '#90BDD4');
      r.style.setProperty('--scene-narration', '#B099D0');
      r.style.setProperty('--scene-reaction', '#D06A56');
      r.style.setProperty('--scene-choice', '#E6CD7C');
    } else {
      r.style.setProperty('--scene-dialogue', '#7FA8C4');
      r.style.setProperty('--scene-narration', '#9A8AB8');
      r.style.setProperty('--scene-reaction', '#B85A4A');
      r.style.setProperty('--scene-choice', '#D4B96A');
    }
  }, [accent, scenePalette]);

  // Keyboard nav
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement).tagName === 'INPUT' || (e.target as HTMLElement).tagName === 'TEXTAREA') return;
      if (e.metaKey || e.ctrlKey) {
        const map: Record<string, PageId> = { '1': 'dashboard', '2': 'timeline', '3': 'search', '4': 'conflict', '5': 'clips', '6': 'stats', '7': 'settings' };
        if (map[e.key]) {
          e.preventDefault();
          setPage(map[e.key]);
        }
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  const handleResolve = useCallback((conflictIdx: number, choice: string) => {
    setConflictDecisions((prev) => ({ ...prev, [conflictIdx]: choice }));
  }, []);

  const handleJump = useCallback((_time: number) => {
    setPage('timeline');
  }, []);

  let pageEl: React.ReactNode = null;
  if (page === 'dashboard') pageEl = <DashboardPage onJump={handleJump} onNav={setPage} />;
  else if (page === 'timeline') pageEl = <TimelinePage />;
  else if (page === 'search') pageEl = <SearchPage onJump={handleJump} />;
  else if (page === 'conflict') pageEl = <ConflictPage conflicts={CONFLICTS} decisions={conflictDecisions} onResolve={handleResolve} />;
  else if (page === 'clips') pageEl = <ClipsPage onJump={handleJump} />;
  else if (page === 'stats') pageEl = <StatsPage />;
  else if (page === 'settings') pageEl = <SettingsPage />;

  return (
    <div className="app-shell">
      <Sidebar active={page} onNav={setPage} conflictsPending={pending} />
      <div className="main-area">
        {pageEl}
      </div>
      <Statusbar page={page} />
    </div>
  );
}
