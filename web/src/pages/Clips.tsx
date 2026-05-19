import React, { useState } from 'react';
import { I } from '../components/Icons';
import { SceneBadge, ScoreBadge } from '../components/Badges';
import { Topbar } from '../components/Topbar';
import { fmtTime, CLIPS, SCENE_TYPES } from '../data/mock';
import type { Clip, SceneType } from '../types';

interface ClipsPageProps {
  onJump: (time: number) => void;
}

type SortKey = 'score' | 'time' | 'sc';

export const ClipsPage: React.FC<ClipsPageProps> = ({ onJump }) => {
  const [activeScene, setActiveScene] = useState<SceneType | null>(null);
  const [sortBy, setSortBy] = useState<SortKey>('score');
  const [selected, setSelected] = useState<Clip | null>(CLIPS[0] ?? null);

  const filtered = CLIPS.filter((c) => !activeScene || c.scene === activeScene);
  const sorted = [...filtered].sort((a, b) => {
    if (sortBy === 'score') return b.score - a.score;
    if (sortBy === 'time') return a.start - b.start;
    return b.sc - a.sc;
  });

  const topbarActions = (
    <>
      <button className="btn btn--sm"><I.Download size={14} /> .chapters</button>
      <button className="btn btn--sm"><I.Download size={14} /> .srt</button>
      <button className="btn btn--sm"><I.Download size={14} /> EDL CMX 3600</button>
    </>
  );

  return (
    <div className="page page--clips">
      <Topbar title="Clips" jpTitle="ハイライト" actions={topbarActions} />

      <div className="clips-layout">
        {/* Main area */}
        <div className="clips-main">
          {/* Filter pills + sort */}
          <div className="clips-toolbar">
            <div className="clips-filters">
              <button
                className={`pill ${activeScene === null ? 'pill--active' : ''}`}
                onClick={() => setActiveScene(null)}
              >
                ALL
              </button>
              {SCENE_TYPES.map((st) => (
                <button
                  key={st.id}
                  className={`pill ${activeScene === st.id ? 'pill--active' : ''}`}
                  onClick={() => setActiveScene(activeScene === st.id ? null : st.id)}
                >
                  {st.label}
                </button>
              ))}
            </div>
            <div className="clips-sort">
              <I.Filter size={14} />
              <select value={sortBy} onChange={(e) => setSortBy(e.target.value as SortKey)}>
                <option value="score">Score</option>
                <option value="time">Time</option>
                <option value="sc">SC</option>
              </select>
            </div>
          </div>

          {/* Clips grid */}
          <div className="clips-grid">
            {sorted.map((clip, idx) => (
              <div
                key={clip.id}
                className={`clip-card ${selected?.id === clip.id ? 'clip-card--selected' : ''}`}
                onClick={() => setSelected(clip)}
              >
                {/* Thumbnail placeholder */}
                <div className="clip-card__thumb">
                  <div className="clip-card__thumb-inner">
                    <I.Play size={24} />
                  </div>
                  <span className="clip-card__rank">#{idx + 1}</span>
                  <span className="clip-card__duration">
                    {fmtTime(clip.end - clip.start).slice(6)}s
                  </span>
                </div>

                <div className="clip-card__body">
                  <div className="clip-card__time">
                    {fmtTime(clip.start)} - {fmtTime(clip.end)}
                  </div>
                  <div className="clip-card__quote-jp">{clip.quoteJp}</div>
                  <div className="clip-card__quote">{clip.quote}</div>
                  <div className="clip-card__badges">
                    <ScoreBadge score={clip.score} />
                    <SceneBadge scene={clip.scene} />
                    {clip.sc > 0 && (
                      <span className="badge badge--sc">
                        <I.SC size={12} /> {clip.sc.toLocaleString()}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Detail sidebar */}
        <aside className="clips-detail" style={{ width: 340, minWidth: 340 }}>
          {selected ? (
            <ClipDetail clip={selected} onJump={onJump} />
          ) : (
            <div className="clips-detail__empty">Select a clip</div>
          )}
        </aside>
      </div>
    </div>
  );
};

/* --- Detail Panel --- */

interface ClipDetailProps {
  clip: Clip;
  onJump: (time: number) => void;
}

const BREAKDOWN_KEYS = ['volume', 'laughter', 'keyword', 'chat', 'speech_rate', 'silence_burst'] as const;
const BREAKDOWN_LABELS: Record<string, string> = {
  volume: 'Volume',
  laughter: 'Laughter',
  keyword: 'Keyword',
  chat: 'Chat',
  speech_rate: 'Speech Rate',
  silence_burst: 'Silence Burst',
};

const ClipDetail: React.FC<ClipDetailProps> = ({ clip, onJump }) => {
  // Mock breakdown proportional to score
  const mockBreakdown = BREAKDOWN_KEYS.map((k, i) => {
    const base = [18, 10, 16, 20, 12, 5];
    return { key: k, value: Math.round(base[i] * clip.score / 80) };
  });
  const maxVal = Math.max(...mockBreakdown.map((b) => b.value), 1);

  // Mock events
  const mockEvents = clip.sc > 0
    ? ['streamer_reaction', 'chat_spike', 'superchat']
    : ['streamer_reaction', 'chat_spike'];

  // Mock chat messages
  const mockChat = [
    { user: 'sakura_fan', msg: 'ここやばいwww' },
    { user: 'vip_viewer', msg: '泣ける...' },
    { user: 'game_love', msg: '最高の瞬間！' },
  ];

  return (
    <div className="clip-detail-panel">
      <h3 className="clip-detail-panel__title">{clip.title}</h3>

      {/* Mock player */}
      <div className="clip-detail-panel__player">
        <div className="clip-detail-panel__player-inner">
          <I.Play size={32} />
        </div>
        <div className="clip-detail-panel__player-bar">
          <span>{fmtTime(clip.start)}</span>
          <span>{fmtTime(clip.end)}</span>
        </div>
      </div>

      {/* Score breakdown bars */}
      <div className="clip-detail-panel__section">
        <h4>Score Breakdown</h4>
        <div className="breakdown-bars">
          {mockBreakdown.map((b) => (
            <div key={b.key} className="breakdown-bar">
              <span className="breakdown-bar__label">{BREAKDOWN_LABELS[b.key]}</span>
              <div className="breakdown-bar__track">
                <div
                  className="breakdown-bar__fill"
                  style={{ width: `${(b.value / maxVal) * 100}%` }}
                />
              </div>
              <span className="breakdown-bar__value">{b.value}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Events */}
      <div className="clip-detail-panel__section">
        <h4>Events</h4>
        <div className="clip-detail-panel__events">
          {mockEvents.map((ev) => (
            <span key={ev} className="badge badge--event">{ev}</span>
          ))}
        </div>
      </div>

      {/* Chat sample */}
      <div className="clip-detail-panel__section">
        <h4>Chat Sample</h4>
        <div className="clip-detail-panel__chat">
          {mockChat.map((m, i) => (
            <div key={i} className="clip-detail-panel__chat-msg">
              <span className="clip-detail-panel__chat-user">{m.user}</span>
              <span>{m.msg}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Action buttons */}
      <div className="clip-detail-panel__actions">
        <button className="btn btn--primary" onClick={() => onJump(clip.start)}>
          <I.Play size={14} /> Jump to Clip
        </button>
        <button className="btn btn--sm"><I.Copy size={14} /> Copy SRT</button>
        <button className="btn btn--sm"><I.Download size={14} /> Export</button>
      </div>
    </div>
  );
};

export default ClipsPage;
