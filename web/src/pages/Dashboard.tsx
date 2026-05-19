import React from 'react';
import { I } from '../components/Icons';
import { SceneBadge, ScoreBadge } from '../components/Badges';
import { Topbar } from '../components/Topbar';
import { TimelineThumbnail } from '../components/TimelineThumbnail';
import {
  CHANNEL, STATS, CHARACTERS, SCENE_TYPES, CLIPS, DENSITY,
  HOT_SPOTS, CHAR_PRESENCE, VIDEO_DURATION, fmtTime,
} from '../data/mock';
import type { PageId } from '../types';

/* ── Local components ── */

interface StatCardProps {
  label: string;
  value: string | number;
  sub: string;
  icon: string;
  accent?: string;
}

const StatCard: React.FC<StatCardProps> = ({ label, value, sub, icon, accent }) => {
  const Icon = I[icon];
  return (
    <div className="stat-card">
      <span className="stat-card__label">{label}</span>
      <span className="stat-card__value">{value}</span>
      <span className="stat-card__sub">{sub}</span>
      {Icon && (
        <span className="stat-card__accent" style={accent ? { color: accent } : undefined}>
          <Icon size={14} />
        </span>
      )}
    </div>
  );
};

const SC_POSITIONS = [20, 47, 79, 138, 174];

const ChatActivityChart: React.FC = () => {
  const w = 800;
  const h = 120;
  const buckets = DENSITY.length;
  const dx = w / buckets;

  // Build area path
  const points = DENSITY.map((v, i) => ({ x: i * dx, y: h - v * h }));
  const areaPath =
    `M0,${h} ` +
    points.map(p => `L${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ') +
    ` L${w},${h} Z`;

  const linePath = points.map((p, i) =>
    `${i === 0 ? 'M' : 'L'}${p.x.toFixed(1)},${p.y.toFixed(1)}`
  ).join(' ');

  return (
    <svg viewBox={`0 0 ${w} ${h}`} width="100%" height={h} preserveAspectRatio="none" style={{ display: 'block' }}>
      <defs>
        <linearGradient id="chat-grad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="var(--amber)" stopOpacity={0.35} />
          <stop offset="100%" stopColor="var(--amber)" stopOpacity={0.02} />
        </linearGradient>
      </defs>
      <path d={areaPath} fill="url(#chat-grad)" />
      <path d={linePath} fill="none" stroke="var(--amber)" strokeWidth={1.5} opacity={0.7} />
      {/* HOT_SPOTS markers */}
      {HOT_SPOTS.map(idx => {
        const x = idx * dx;
        const y = h - DENSITY[idx] * h;
        return (
          <circle key={`hot-${idx}`} cx={x} cy={y} r={3.5}
            fill="var(--score-high)" stroke="var(--ink-deep)" strokeWidth={1.5} />
        );
      })}
      {/* SC markers */}
      {SC_POSITIONS.map(idx => {
        const x = idx * dx;
        return (
          <g key={`sc-${idx}`}>
            <line x1={x} y1={0} x2={x} y2={h} stroke="var(--superchat)" strokeWidth={1} strokeDasharray="3 3" opacity={0.5} />
            <circle cx={x} cy={8} r={4} fill="var(--superchat)" opacity={0.8} />
            <text x={x} y={11} textAnchor="middle" fontSize={5} fill="var(--ink-deep)" fontWeight={700}>$</text>
          </g>
        );
      })}
    </svg>
  );
};

/* ── Dashboard Page ── */

interface DashboardPageProps {
  onJump: (time: number) => void;
  onNav: (page: PageId) => void;
}

export const DashboardPage: React.FC<DashboardPageProps> = ({ onJump, onNav }) => {
  return (
    <div className="page-content">
      <Topbar title="Dashboard" jpTitle="ダッシュボード" breadcrumb={CHANNEL.game} />

      <div className="page-pad col gap-lg">
        {/* ── Stat cards ── */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 12 }}>
          <StatCard label="Segments" value={STATS.totalSegments} sub={`avg ${STATS.avgSegLen}s / seg`} icon="Timeline" />
          <StatCard label="Duration" value={fmtTime(STATS.duration)} sub={CHANNEL.file} icon="Play" />
          <StatCard label="Conflicts" value={STATS.conflicts} sub={`${STATS.resolvedConflicts} resolved`} icon="Conflict" accent="var(--danger)" />
          <StatCard label="Highlights" value={STATS.highlights} sub="top clips auto-cut" icon="Clips" accent="var(--amber)" />
          <StatCard label="Characters" value={STATS.characters} sub={`${STATS.scDistinctUsers} SC users`} icon="User" />
        </div>

        {/* ── Timeline Overview ── */}
        <div className="panel">
          <div className="panel__head">
            <span className="panel__title">Timeline Overview</span>
            <span className="panel__label">全體タイムライン</span>
          </div>
          <div className="panel__body">
            <TimelineThumbnail onClick={onJump} />
          </div>
        </div>

        {/* ── Two-column: Scene Distribution | Top Highlights ── */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
          {/* Scene Distribution */}
          <div className="panel">
            <div className="panel__head">
              <span className="panel__title">Scene Distribution</span>
              <span className="panel__label">場面分布</span>
            </div>
            <div className="panel__body">
              {/* Stacked bar */}
              <div style={{ height: 28, display: 'flex', borderRadius: 3, overflow: 'hidden', marginBottom: 12 }}>
                {SCENE_TYPES.map(st => {
                  const total = SCENE_TYPES.reduce((s, t) => s + t.count, 0);
                  const pct = (st.count / total) * 100;
                  return (
                    <div
                      key={st.id}
                      style={{ width: `${pct}%`, background: st.color, minWidth: 2 }}
                      title={`${st.label}: ${st.count}`}
                    />
                  );
                })}
              </div>
              {/* Legend */}
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px 16px' }}>
                {SCENE_TYPES.map(st => (
                  <div key={st.id} className="row gap-sm" style={{ fontSize: 11 }}>
                    <span style={{ width: 8, height: 8, borderRadius: 2, background: st.color, flexShrink: 0 }} />
                    <span className="muted">{st.label}</span>
                    <span className="mono dim" style={{ fontSize: 10 }}>{st.count}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Top Highlights */}
          <div className="panel">
            <div className="panel__head">
              <span className="panel__title">Top Highlights</span>
              <span className="panel__label">ハイライト TOP 5</span>
              <span style={{ marginLeft: 'auto' }}>
                <button className="btn btn--sm btn--ghost" onClick={() => onNav('clips')}>
                  View All
                </button>
              </span>
            </div>
            <div className="panel__body" style={{ padding: '8px 16px' }}>
              {CLIPS.slice(0, 5).map((clip, i) => (
                <div
                  key={clip.id}
                  className="row"
                  style={{ padding: '8px 0', borderBottom: i < 4 ? '1px solid var(--ink-border)' : undefined, cursor: 'pointer' }}
                  onClick={() => onJump(clip.start)}
                >
                  <span className="mono dim" style={{ fontSize: 10, width: 18 }}>#{i + 1}</span>
                  <span className="mono" style={{ fontSize: 11, color: 'var(--text-primary)', width: 64 }}>
                    {fmtTime(clip.start)}
                  </span>
                  <SceneBadge scene={clip.scene} />
                  <span className="tc flex-1" style={{ fontSize: 12 }}>{clip.quote}</span>
                  <ScoreBadge score={clip.score} />
                  {clip.sc > 0 && (
                    <span className="badge badge--sc" style={{ fontSize: 10 }}>
                      <I.SC size={10} /> ¥{clip.sc}
                    </span>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* ── Character Presence gantt chart ── */}
        <div className="panel">
          <div className="panel__head">
            <span className="panel__title">Character Presence</span>
            <span className="panel__label">キャラ出演マップ</span>
          </div>
          <div className="panel__body">
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {CHARACTERS.map(char => {
                const presence = CHAR_PRESENCE[char.id] || [];
                return (
                  <div key={char.id} style={{ display: 'grid', gridTemplateColumns: '80px 1fr', alignItems: 'center', gap: 12 }}>
                    <span className="jp" style={{ fontSize: 12, color: char.color }}>{char.name}</span>
                    <div style={{ display: 'flex', gap: 2 }}>
                      {presence.map((v, i) => (
                        <div
                          key={i}
                          style={{
                            flex: 1,
                            height: 14,
                            borderRadius: 2,
                            background: v ? char.color : 'var(--ink-deep)',
                            opacity: v ? 0.8 : 0.3,
                            transition: 'opacity 100ms',
                          }}
                        />
                      ))}
                    </div>
                  </div>
                );
              })}
              {/* time labels */}
              <div style={{ display: 'grid', gridTemplateColumns: '80px 1fr', gap: 12 }}>
                <span />
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  {[0, 0.25, 0.5, 0.75, 1].map(pct => (
                    <span key={pct} className="mono dim" style={{ fontSize: 9 }}>
                      {fmtTime(Math.floor(VIDEO_DURATION * pct))}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* ── Two-column: Chat Activity | Superchats ── */}
        <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 14 }}>
          {/* Chat Activity */}
          <div className="panel">
            <div className="panel__head">
              <span className="panel__title">Chat Activity</span>
              <span className="panel__label">チャット密度</span>
            </div>
            <div className="panel__body">
              <ChatActivityChart />
            </div>
          </div>

          {/* Superchats */}
          <div className="panel">
            <div className="panel__head">
              <span className="panel__title">Superchats</span>
              <span className="panel__label">スパチャ一覧</span>
              <span className="badge badge--sc" style={{ marginLeft: 'auto' }}>
                ¥{STATS.scTotal.toLocaleString()}
              </span>
            </div>
            <div className="panel__body" style={{ padding: '8px 16px', maxHeight: 180, overflowY: 'auto' }}>
              {CLIPS.filter(c => c.sc > 0).sort((a, b) => b.sc - a.sc).map(clip => (
                <div
                  key={clip.id}
                  className="row"
                  style={{ padding: '6px 0', borderBottom: '1px solid var(--ink-border)', cursor: 'pointer' }}
                  onClick={() => onJump(clip.start)}
                >
                  <I.SC size={12} style={{ color: 'var(--superchat)' }} />
                  <span className="mono" style={{ fontSize: 11, color: 'var(--superchat)' }}>¥{clip.sc}</span>
                  <span className="mono dim" style={{ fontSize: 11 }}>{fmtTime(clip.start)}</span>
                  <span className="tc muted flex-1" style={{ fontSize: 11 }}>{clip.title}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default DashboardPage;
