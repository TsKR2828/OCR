import React, { useState, useMemo } from 'react';
import { I } from '../components/Icons';
import { Topbar } from '../components/Topbar';
import { TimelineThumbnail } from '../components/TimelineThumbnail';
import { SegmentCard } from '../components/SegmentCard';
import {
  FEATURED_SEGMENTS, SCENE_TYPES, CHARACTERS, VIDEO_DURATION, fmtTime,
} from '../data/mock';
import type { SceneType } from '../types';

interface TimelinePageProps {
  initialTime?: number;
}

export const TimelinePage: React.FC<TimelinePageProps> = ({ initialTime }) => {
  const [expanded, setExpanded] = useState<Set<number>>(new Set());
  const [selectedIdx, setSelectedIdx] = useState<number | null>(null);
  const [filterScene, setFilterScene] = useState<SceneType | ''>('');
  const [filterSpeaker, setFilterSpeaker] = useState<string>('');
  const [query, setQuery] = useState('');
  const [showWaveform, setShowWaveform] = useState(true);
  const [jumpInput, setJumpInput] = useState(initialTime ? fmtTime(initialTime) : '');

  // Apply filters
  const filteredSegments = useMemo(() => {
    return FEATURED_SEGMENTS.filter(seg => {
      if (filterScene && seg.scene !== filterScene) return false;
      if (filterSpeaker) {
        const ocrMatch = seg.ocr?.speaker?.includes(filterSpeaker);
        const asrMatch = seg.asr?.speaker?.includes(filterSpeaker);
        if (!ocrMatch && !asrMatch) return false;
      }
      if (query) {
        const q = query.toLowerCase();
        const ocrText = seg.ocr?.text?.toLowerCase() || '';
        const asrText = seg.asr?.text?.toLowerCase() || '';
        if (!ocrText.includes(q) && !asrText.includes(q)) return false;
      }
      return true;
    });
  }, [filterScene, filterSpeaker, query]);

  const toggleExpand = (idx: number) => {
    setExpanded(prev => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx);
      else next.add(idx);
      return next;
    });
  };

  const handleJump = () => {
    // Parse HH:MM:SS or MM:SS
    const parts = jumpInput.split(':').map(Number);
    let seconds = 0;
    if (parts.length === 3) seconds = parts[0] * 3600 + parts[1] * 60 + parts[2];
    else if (parts.length === 2) seconds = parts[0] * 60 + parts[1];
    else seconds = parts[0] || 0;
    // Scroll to nearest segment
    const nearest = FEATURED_SEGMENTS.reduce((best, seg) =>
      Math.abs(seg.start - seconds) < Math.abs(best.start - seconds) ? seg : best
    );
    setSelectedIdx(nearest.idx);
  };

  // Time scale labels for ruler
  const timeLabels = useMemo(() => {
    const count = 9;
    return Array.from({ length: count }, (_, i) => {
      const t = Math.floor((VIDEO_DURATION / (count - 1)) * i);
      return { t, label: fmtTime(t) };
    });
  }, []);

  return (
    <div className="page-content" style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* ── Topbar with filters ── */}
      <Topbar title="Timeline" jpTitle="タイムライン">
        {/* Scene filter */}
        <div className="select-wrap">
          <select
            className="select"
            value={filterScene}
            onChange={e => setFilterScene(e.target.value as SceneType | '')}
          >
            <option value="">All Scenes</option>
            {SCENE_TYPES.map(st => (
              <option key={st.id} value={st.id}>{st.label} ({st.count})</option>
            ))}
          </select>
        </div>

        {/* Speaker filter */}
        <div className="select-wrap">
          <select
            className="select"
            value={filterSpeaker}
            onChange={e => setFilterSpeaker(e.target.value)}
          >
            <option value="">All Speakers</option>
            <option value="streamer">Streamer</option>
            {CHARACTERS.map(c => (
              <option key={c.id} value={c.name}>{c.name}</option>
            ))}
          </select>
        </div>

        {/* Text search */}
        <div className="input" style={{ width: 200 }}>
          <I.Search size={14} className="input__icon" />
          <input
            placeholder="Search text..."
            value={query}
            onChange={e => setQuery(e.target.value)}
          />
        </div>

        {/* Time jump */}
        <div className="input" style={{ width: 110 }}>
          <I.Play size={12} className="input__icon" />
          <input
            placeholder="00:00:00"
            value={jumpInput}
            onChange={e => setJumpInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleJump()}
          />
        </div>

        {/* Waveform toggle */}
        <button
          className={`btn btn--sm ${showWaveform ? 'btn--amber' : 'btn--ghost'}`}
          onClick={() => setShowWaveform(!showWaveform)}
          title="Toggle waveform"
        >
          <I.Mic size={12} />
        </button>
      </Topbar>

      {/* ── Sticky ruler area ── */}
      <div className="timeline-ruler">
        <div style={{ marginBottom: 6 }}>
          <TimelineThumbnail onClick={() => {}} />
        </div>
        {/* Time scale labels */}
        <div className="timeline-ruler__bar" style={{ height: 20 }}>
          {timeLabels.map(({ t, label }) => {
            const pct = (t / VIDEO_DURATION) * 100;
            return (
              <div key={t} className="timeline-ruler__tick" style={{ left: `${pct}%` }}>
                <span className="timeline-ruler__tick-label">{label}</span>
              </div>
            );
          })}
        </div>
        {showWaveform && <div className="timeline-ruler__waveform" />}
      </div>

      {/* ── Segment list ── */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '16px 28px' }}>
        {filteredSegments.length === 0 && (
          <div style={{ textAlign: 'center', padding: 40, color: 'var(--text-tertiary)' }}>
            <I.Search size={32} style={{ opacity: 0.3, marginBottom: 12 }} />
            <p>No segments match current filters.</p>
          </div>
        )}
        {filteredSegments.map(seg => (
          <SegmentCard
            key={seg.idx}
            seg={seg}
            selected={selectedIdx === seg.idx}
            expanded={expanded.has(seg.idx)}
            onClick={() => setSelectedIdx(seg.idx === selectedIdx ? null : seg.idx)}
            onToggle={() => toggleExpand(seg.idx)}
          />
        ))}
      </div>
    </div>
  );
};

export default TimelinePage;
