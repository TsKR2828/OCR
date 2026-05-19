import React, { useState } from 'react';
import { I } from '../components/Icons';
import { SceneBadge, ScoreBadge } from '../components/Badges';
import { Topbar } from '../components/Topbar';
import { SEARCH_MODES, SEARCH_RESULTS, fmtTime } from '../data/mock';
import type { SearchMode, SearchResult } from '../types';

interface SearchPageProps {
  onJump: (time: number) => void;
}

const SAVED_QUERIES = [
  'char: ケイ', 'char: ユリ', 'char: ハルカ',
  'kw: 大丈夫', 'kw: 好きだ', 'reaction: top 20',
  'conflict: pending', 'sc: amount >= 1000',
];

export const SearchPage: React.FC<SearchPageProps> = ({ onJump }) => {
  const [activeMode, setActiveMode] = useState<string>(SEARCH_MODES[0].id);
  const [query, setQuery] = useState('ケイ');
  const [topN, setTopN] = useState<string>('20');
  const [sortBy, setSortBy] = useState<'time' | 'score' | 'chat'>('score');
  const [results, setResults] = useState<SearchResult[]>(SEARCH_RESULTS);

  const currentMode = SEARCH_MODES.find(m => m.id === activeMode) || SEARCH_MODES[0];

  const handleSearch = () => {
    if (!query.trim()) {
      setResults(SEARCH_RESULTS);
      return;
    }
    const q = query.toLowerCase();
    const filtered = SEARCH_RESULTS.filter(r =>
      r.char.toLowerCase().includes(q) ||
      r.jp.toLowerCase().includes(q) ||
      r.asr.toLowerCase().includes(q)
    );
    setResults(filtered);
  };

  const limit = topN === 'all' ? Infinity : Number(topN);
  const sortedResults = [...results].sort((a, b) => {
    if (sortBy === 'score') return b.score - a.score;
    if (sortBy === 'chat') return b.chat - a.chat;
    return a.time - b.time;
  }).slice(0, limit);

  const handleCopy = () => {
    const text = sortedResults.map(r =>
      `${fmtTime(r.time)}\t${r.scene}\t${r.char}\t${r.jp}\t${r.asr}\t${r.score}`
    ).join('\n');
    navigator.clipboard?.writeText(text);
  };

  const handleExport = () => {
    const header = 'Time\tScene\tCharacter\tJP\tASR\tScore\tChat\n';
    const body = sortedResults.map(r =>
      `${fmtTime(r.time)}\t${r.scene}\t${r.char}\t${r.jp}\t${r.asr}\t${r.score}\t${r.chat}`
    ).join('\n');
    const blob = new Blob([header + body], { type: 'text/tab-separated-values' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'search-results.tsv';
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <>
      <Topbar title="Search" jpTitle="検索"
        actions={<>
          <button className="btn btn--ghost" onClick={handleCopy}><I.Copy size={13} /> Copy</button>
          <button className="btn" onClick={handleExport}><I.Download size={13} /> Export</button>
        </>}
      />
      <div className="page-content">
        <div className="page-pad" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {/* ── Mode tabs (6 modes) ── */}
          <div className="search-mode-tabs">
            {SEARCH_MODES.map(mode => {
              const Icon = I[mode.icon];
              return (
                <button
                  key={mode.id}
                  className={`search-mode-tabs__item${activeMode === mode.id ? ' search-mode-tabs__item--active' : ''}`}
                  onClick={() => setActiveMode(mode.id)}
                >
                  {Icon && <Icon size={13} />}
                  <span>{mode.label}</span>
                  <span className="jp dim" style={{ fontSize: 10, marginLeft: 2 }}>{mode.jp}</span>
                </button>
              );
            })}
          </div>

          {/* ── Search input panel ── */}
          <div className="panel">
            <div className="panel__body" style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
              {/* Query */}
              <div className="input flex-1" style={{ minWidth: 260, padding: '10px 14px' }}>
                <I.Search className="input__icon" size={16} />
                <input
                  placeholder={currentMode.placeholder}
                  value={query}
                  onChange={e => setQuery(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && handleSearch()}
                  style={{ fontSize: 14 }}
                />
              </div>

              {/* topN select */}
              <div className="select-wrap">
                <select className="select" value={topN} onChange={e => setTopN(e.target.value)}>
                  <option value="10">top 10</option>
                  <option value="20">top 20</option>
                  <option value="50">top 50</option>
                  <option value="all">all</option>
                </select>
              </div>

              {/* sortBy select */}
              <div className="select-wrap">
                <select className="select" value={sortBy} onChange={e => setSortBy(e.target.value as 'time' | 'score' | 'chat')}>
                  <option value="time">sort: time</option>
                  <option value="score">sort: score</option>
                  <option value="chat">sort: chat</option>
                </select>
              </div>

              {/* Search button */}
              <button className="btn btn--amber" onClick={handleSearch}>
                <I.Search size={12} /> Search
              </button>
            </div>
          </div>

          {/* ── Results table ── */}
          <div className="panel" style={{ overflow: 'hidden' }}>
            <div className="panel__head">
              <span className="panel__title">Results</span>
              <span className="panel__label">{sortedResults.length} matches</span>
              <div style={{ marginLeft: 'auto', display: 'flex', gap: 6, fontSize: 11, color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }}>
                <span>scope: {SEARCH_RESULTS.length} segments</span>
              </div>
            </div>
            <div style={{ overflowX: 'auto' }}>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Time</th>
                    <th>Scene</th>
                    <th>Character / JP</th>
                    <th>ASR</th>
                    <th>Score</th>
                    <th>Chat</th>
                  </tr>
                </thead>
                <tbody>
                  {sortedResults.map((r, i) => (
                    <tr key={i} onClick={() => onJump(r.time)} style={{ cursor: 'pointer' }}>
                      <td className="mono" style={{ fontSize: 12, color: 'var(--amber)', whiteSpace: 'nowrap' }}>
                        {fmtTime(r.time)}
                      </td>
                      <td>
                        <SceneBadge scene={r.scene} />
                      </td>
                      <td>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
                          <span className="badge badge--speaker">{r.char}</span>
                          <span className="jp" style={{ fontSize: 14, color: 'var(--text-jp)' }}>{r.jp}</span>
                        </div>
                      </td>
                      <td>
                        <span className="tc" style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{r.asr}</span>
                      </td>
                      <td>
                        <ScoreBadge score={r.score} />
                      </td>
                      <td>
                        <span className="mono" style={{ fontSize: 11 }}>
                          {r.chat}
                          {r.spike && (
                            <I.Spike size={11} style={{ color: 'var(--chat-spike)', marginLeft: 4, verticalAlign: 'middle' }} />
                          )}
                        </span>
                        {r.conflict && (
                          <span className="badge badge--status-conflict" style={{ fontSize: 9, padding: '1px 5px', marginLeft: 4 }}>conflict</span>
                        )}
                      </td>
                    </tr>
                  ))}
                  {sortedResults.length === 0 && (
                    <tr>
                      <td colSpan={6} style={{ textAlign: 'center', padding: 32, color: 'var(--text-tertiary)' }}>
                        No results found.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* ── Saved Queries ── */}
          <div className="panel">
            <div className="panel__head">
              <I.Pin size={13} style={{ color: 'var(--text-tertiary)' }} />
              <span className="panel__title">Saved Queries</span>
              <span className="panel__label">保存済みクエリ</span>
            </div>
            <div className="panel__body" style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {SAVED_QUERIES.map((q, i) => (
                <button
                  key={i}
                  className={`pill${query === q ? ' pill--active' : ''}`}
                  onClick={() => { setQuery(q); }}
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </>
  );
};

export default SearchPage;
