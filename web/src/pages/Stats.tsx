import React, { useState } from 'react';
import { I } from '../components/Icons';
import { Topbar } from '../components/Topbar';
import { fmtTime, STATS, CHARACTERS, SCENE_TYPES, DENSITY, HOT_SPOTS, VIDEO_DURATION } from '../data/mock';
import type { Character } from '../types';

type CharSort = 'lines' | 'first' | 'last';

export const StatsPage: React.FC = () => {
  const [charSort, setCharSort] = useState<CharSort>('lines');

  const sortedChars = [...CHARACTERS].sort((a, b) => {
    if (charSort === 'lines') return b.lines - a.lines;
    if (charSort === 'first') return a.firstAt - b.firstAt;
    return b.lastAt - a.lastAt;
  });

  const maxLines = Math.max(...CHARACTERS.map((c) => c.lines));

  const topbarActions = (
    <>
      <button className="btn btn--sm"><I.Download size={14} /> JSON</button>
      <button className="btn btn--sm"><I.Download size={14} /> CSV</button>
    </>
  );

  return (
    <div className="page page--stats">
      <Topbar title="Stats" jpTitle="統計" actions={topbarActions} />

      {/* Big stat cards */}
      <div className="stats-cards">
        <StatCard label="Duration" value={fmtTime(STATS.duration)} sub="02:15:30" />
        <StatCard label="Segments" value={STATS.totalSegments.toLocaleString()} sub={`avg ${STATS.avgSegLen}s`} />
        <StatCard label="Highlights" value={STATS.highlights.toString()} sub={`>= 60 score`} />
        <StatCard label="SC Total" value={`${STATS.scTotal.toLocaleString()}`} sub={`${STATS.scDistinctUsers} users`} />
      </div>

      {/* Character table */}
      <section className="stats-section">
        <div className="stats-section__header">
          <h3>Characters</h3>
          <div className="stats-section__sort">
            <span>Sort:</span>
            {(['lines', 'first', 'last'] as CharSort[]).map((k) => (
              <button
                key={k}
                className={`pill ${charSort === k ? 'pill--active' : ''}`}
                onClick={() => setCharSort(k)}
              >
                {k === 'lines' ? 'Lines' : k === 'first' ? 'First' : 'Last'}
              </button>
            ))}
          </div>
        </div>
        <table className="stats-table">
          <thead>
            <tr>
              <th></th>
              <th>Name</th>
              <th>Aliases</th>
              <th>Lines</th>
              <th>First</th>
              <th>Last</th>
              <th>Distribution</th>
            </tr>
          </thead>
          <tbody>
            {sortedChars.map((ch) => (
              <tr key={ch.id}>
                <td><span className="color-dot" style={{ background: ch.color }} /></td>
                <td className="stats-table__name">{ch.name}</td>
                <td className="stats-table__aliases">{ch.aliases.join(', ')}</td>
                <td>{ch.lines}</td>
                <td>{fmtTime(ch.firstAt)}</td>
                <td>{fmtTime(ch.lastAt)}</td>
                <td>
                  <div className="stats-table__bar-container">
                    <div
                      className="stats-table__bar"
                      style={{ width: `${(ch.lines / maxLines) * 100}%`, background: ch.color }}
                    />
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      {/* Two-column: Donut + Histogram */}
      <div className="stats-two-col">
        <section className="stats-section">
          <h3>Scene Distribution</h3>
          <SceneDonut />
        </section>
        <section className="stats-section">
          <h3>Score Histogram</h3>
          <ScoreHistogram />
        </section>
      </div>

      {/* Chat Density over Time */}
      <section className="stats-section stats-section--full">
        <h3>Chat Density over Time</h3>
        <ChatDensityChart />
      </section>

      {/* Two-column: Reaction Keywords + Events */}
      <div className="stats-two-col">
        <section className="stats-section">
          <h3>Top Reaction Keywords</h3>
          <ReactionKeywords />
        </section>
        <section className="stats-section">
          <h3>Events Summary</h3>
          <EventsSummary />
        </section>
      </div>
    </div>
  );
};

/* --- Sub-components --- */

const StatCard: React.FC<{ label: string; value: string; sub: string }> = ({ label, value, sub }) => (
  <div className="stat-card">
    <div className="stat-card__value">{value}</div>
    <div className="stat-card__label">{label}</div>
    <div className="stat-card__sub">{sub}</div>
  </div>
);

/* Scene Distribution Donut using strokeDasharray */
const SceneDonut: React.FC = () => {
  const total = SCENE_TYPES.reduce((sum, s) => sum + s.count, 0);
  const radius = 60;
  const circumference = 2 * Math.PI * radius;
  let offset = 0;

  return (
    <div className="donut-container">
      <svg viewBox="0 0 200 200" width={200} height={200}>
        {SCENE_TYPES.map((st) => {
          const dashLen = (st.count / total) * circumference;
          const dash = `${dashLen} ${circumference - dashLen}`;
          const currentOffset = offset;
          offset += dashLen;
          return (
            <circle
              key={st.id}
              cx={100}
              cy={100}
              r={radius}
              fill="none"
              stroke={st.color}
              strokeWidth={24}
              strokeDasharray={dash}
              strokeDashoffset={-currentOffset}
              transform="rotate(-90 100 100)"
            />
          );
        })}
        <text x={100} y={96} textAnchor="middle" className="donut-total">{total}</text>
        <text x={100} y={114} textAnchor="middle" className="donut-label">segments</text>
      </svg>
      <div className="donut-legend">
        {SCENE_TYPES.map((st) => (
          <div key={st.id} className="donut-legend__item">
            <span className="color-dot" style={{ background: st.color }} />
            <span>{st.label}</span>
            <span className="donut-legend__count">{st.count}</span>
          </div>
        ))}
      </div>
    </div>
  );
};

/* Score Histogram */
const ScoreHistogram: React.FC = () => {
  const data = STATS.scoreHistogram;
  const maxCount = Math.max(...data.map((d) => d.count));

  const barColor = (range: string): string => {
    const num = parseInt(range);
    if (num >= 60) return 'var(--score-high)';
    if (num >= 30) return 'var(--score-mid)';
    return 'var(--score-low)';
  };

  return (
    <div className="histogram">
      <div className="histogram__bars">
        {data.map((d) => (
          <div key={d.range} className="histogram__col">
            <div
              className="histogram__bar"
              style={{
                height: `${(d.count / maxCount) * 100}%`,
                background: barColor(d.range),
              }}
            />
            <span className="histogram__label">{d.range}</span>
          </div>
        ))}
      </div>
    </div>
  );
};

/* Chat Density Area Chart */
const ChatDensityChart: React.FC = () => {
  const width = 1000;
  const height = 180;
  const padding = { top: 10, bottom: 30, left: 0, right: 0 };
  const chartW = width - padding.left - padding.right;
  const chartH = height - padding.top - padding.bottom;

  const points = DENSITY.map((v, i) => {
    const x = padding.left + (i / (DENSITY.length - 1)) * chartW;
    const y = padding.top + chartH - v * chartH;
    return `${x},${y}`;
  });

  const areaPath = `M${padding.left},${padding.top + chartH} ` +
    points.map((p) => `L${p}`).join(' ') +
    ` L${padding.left + chartW},${padding.top + chartH} Z`;

  const linePath = points.map((p, i) => `${i === 0 ? 'M' : 'L'}${p}`).join(' ');

  return (
    <div className="density-chart">
      <svg viewBox={`0 0 ${width} ${height}`} width="100%" height={height} preserveAspectRatio="none">
        <path d={areaPath} fill="var(--accent)" opacity={0.15} />
        <path d={linePath} fill="none" stroke="var(--accent)" strokeWidth={1.5} />
        {/* Hot spot markers */}
        {HOT_SPOTS.map((idx) => {
          const x = padding.left + (idx / (DENSITY.length - 1)) * chartW;
          const y = padding.top + chartH - DENSITY[idx] * chartH;
          return (
            <circle key={idx} cx={x} cy={y} r={4} fill="var(--scene-reaction)" stroke="#fff" strokeWidth={1} />
          );
        })}
        {/* SC markers (mock: place at a few hot spots) */}
        {[16, 79, 230].map((idx) => {
          const x = padding.left + (idx / (DENSITY.length - 1)) * chartW;
          return (
            <g key={`sc-${idx}`}>
              <line x1={x} y1={padding.top} x2={x} y2={padding.top + chartH} stroke="var(--sc-color, #f5a623)" strokeWidth={1} strokeDasharray="3 2" opacity={0.6} />
              <text x={x} y={padding.top + chartH + 18} textAnchor="middle" className="density-chart__time">
                {fmtTime(Math.round((idx / DENSITY.length) * VIDEO_DURATION))}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
};

/* Top Reaction Keywords (horizontal bars) */
const ReactionKeywords: React.FC = () => {
  const keywords = [
    { word: 'www / 草', count: 312 },
    { word: '泣ける', count: 187 },
    { word: 'かわいい', count: 145 },
    { word: 'やば', count: 128 },
    { word: '最高', count: 96 },
    { word: 'エモい', count: 74 },
    { word: '神回', count: 61 },
  ];
  const maxCount = keywords[0].count;

  return (
    <div className="keyword-bars">
      {keywords.map((kw) => (
        <div key={kw.word} className="keyword-bar">
          <span className="keyword-bar__word">{kw.word}</span>
          <div className="keyword-bar__track">
            <div
              className="keyword-bar__fill"
              style={{ width: `${(kw.count / maxCount) * 100}%` }}
            />
          </div>
          <span className="keyword-bar__count">{kw.count}</span>
        </div>
      ))}
    </div>
  );
};

/* Events Summary (colored list) */
const EventsSummary: React.FC = () => {
  const events = [
    { label: 'chat_spike', count: 47, color: 'var(--scene-reaction)' },
    { label: 'streamer_reaction', count: 38, color: 'var(--scene-dialogue)' },
    { label: 'superchat', count: 12, color: 'var(--sc-color, #f5a623)' },
    { label: 'choice_point', count: 28, color: 'var(--scene-choice)' },
    { label: 'laughter_burst', count: 22, color: 'var(--scene-narration)' },
    { label: 'silence_break', count: 15, color: 'var(--scene-silence)' },
  ];

  return (
    <div className="events-summary">
      {events.map((ev) => (
        <div key={ev.label} className="events-summary__item">
          <span className="events-summary__dot" style={{ background: ev.color }} />
          <span className="events-summary__label">{ev.label}</span>
          <span className="events-summary__count">{ev.count}</span>
        </div>
      ))}
    </div>
  );
};

export default StatsPage;
