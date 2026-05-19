import React, { useState, useMemo, useCallback } from 'react';
import { I } from '../components/Icons';
import { fmtTime } from '../data/mock';
import type { Conflict } from '../types';

interface ConflictPageProps {
  conflicts: Conflict[];
  decisions: Record<number, string>;
  onResolve: (idx: number, choice: string) => void;
}

/* ── Diff highlighting: char-by-char comparison ── */

function renderDiffChars(text: string, otherText: string, source: 'ocr' | 'asr'): React.ReactNode[] {
  const chars = [...text];
  const otherChars = [...otherText];
  const cls = source === 'ocr' ? 'diff-highlight-del' : 'diff-highlight-add';

  return chars.map((ch, i) => {
    if (i >= otherChars.length || ch !== otherChars[i]) {
      return <span key={i} className={cls}>{ch}</span>;
    }
    return <span key={i}>{ch}</span>;
  });
}

export const ConflictPage: React.FC<ConflictPageProps> = ({ conflicts, decisions, onResolve }) => {
  const [currentIdx, setCurrentIdx] = useState(0);
  const [editMode, setEditMode] = useState(false);
  const [editValue, setEditValue] = useState('');

  const pendingConflicts = useMemo(
    () => conflicts.filter(c => !decisions[c.idx]),
    [conflicts, decisions]
  );

  const resolvedCount = Object.keys(decisions).length;
  const totalCount = conflicts.length;
  const progressPct = totalCount > 0 ? (resolvedCount / totalCount) * 100 : 0;

  const current = pendingConflicts[currentIdx] || null;

  const goNext = useCallback(() => {
    if (currentIdx < pendingConflicts.length - 1) setCurrentIdx(currentIdx + 1);
  }, [currentIdx, pendingConflicts.length]);

  const goPrev = useCallback(() => {
    if (currentIdx > 0) setCurrentIdx(currentIdx - 1);
  }, [currentIdx]);

  const handleResolve = useCallback((choice: string) => {
    if (!current) return;
    onResolve(current.idx, choice);
    setEditMode(false);
    setEditValue('');
    // After resolve, the pending list shrinks; stay at same index (or clamp)
  }, [current, onResolve]);

  /* ── Empty state: all resolved ── */
  if (totalCount > 0 && pendingConflicts.length === 0) {
    return (
      <div className="page-content" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
        <div style={{ textAlign: 'center', maxWidth: 420 }}>
          <I.Check size={52} style={{ color: 'var(--success)', marginBottom: 16 }} />
          <h2 className="serif" style={{ fontSize: 24, marginBottom: 8 }}>All Conflicts Resolved</h2>
          <p className="muted" style={{ fontSize: 13, lineHeight: 1.7 }}>
            {totalCount} conflicts have been reviewed. The transcript is now conflict-free.
          </p>
          <p className="dim mono" style={{ fontSize: 11, marginTop: 12, letterSpacing: '0.08em' }}>
            全てのコンフリクトが解決されました
          </p>
        </div>
      </div>
    );
  }

  if (!current) {
    return (
      <div className="page-content" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <p className="muted">No conflicts to display.</p>
      </div>
    );
  }

  return (
    <div className="page-content">
      <div className="page-pad" style={{ maxWidth: 920, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 14 }}>

        {/* ── 1. Progress bar ── */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div className="progress-bar" style={{ flex: 1 }}>
            <div className="progress-bar__fill" style={{ width: `${progressPct}%` }} />
          </div>
          <div className="mono" style={{ fontSize: 12 }}>
            <span style={{ color: 'var(--success)' }}>{resolvedCount}</span>
            <span className="dim"> / {totalCount}</span>
            <span className="dim" style={{ marginLeft: 8 }}>
              ({progressPct.toFixed(0)}%)
            </span>
          </div>
        </div>

        {/* ── 2. Current conflict display ── */}
        <div className="panel">
          <div className="panel__head">
            <span className="panel__title">Conflict #{current.idx}</span>
            <span className="panel__label">
              SEGMENT #{String(current.segmentIdx).padStart(4, '0')} &middot; {fmtTime(current.time)}
            </span>
            <div style={{ marginLeft: 'auto', display: 'flex', gap: 6, alignItems: 'center' }}>
              <span className="mono dim" style={{ fontSize: 10 }}>CONFIDENCE</span>
              <div style={{ width: 80, height: 4, background: 'var(--ink-hover)', borderRadius: 2, overflow: 'hidden' }}>
                <div style={{
                  width: `${current.confidence * 100}%`,
                  height: '100%',
                  background: current.confidence > 0.7 ? 'var(--success)' : current.confidence > 0.4 ? 'var(--warning)' : 'var(--danger)',
                }} />
              </div>
              <span className="mono" style={{ fontSize: 11 }}>{(current.confidence * 100).toFixed(0)}%</span>
            </div>
          </div>
          <div className="panel__body" style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
            {/* OCR block */}
            <div className="diff-block diff-block--ocr">
              <div className="diff-block__head">
                <I.Eye size={12} style={{ color: 'var(--scene-dialogue)' }} />
                <span className="diff-block__source" style={{ color: 'var(--scene-dialogue)' }}>OCR</span>
                {current.suggestion === 'ocr' && (
                  <span className="badge badge--status-ok" style={{ fontSize: 9, marginLeft: 8 }}>RECOMMENDED</span>
                )}
              </div>
              <div className="diff-block__text">
                {renderDiffChars(current.ocr, current.asr, 'ocr')}
              </div>
            </div>

            <div className="diff-vs">VS</div>

            {/* ASR block */}
            <div className="diff-block diff-block--asr">
              <div className="diff-block__head">
                <I.Mic size={12} style={{ color: 'var(--amber)' }} />
                <span className="diff-block__source" style={{ color: 'var(--amber)' }}>ASR</span>
                {current.suggestion === 'asr' && (
                  <span className="badge badge--status-ok" style={{ fontSize: 9, marginLeft: 8 }}>RECOMMENDED</span>
                )}
              </div>
              <div className="diff-block__text">
                {renderDiffChars(current.asr, current.ocr, 'asr')}
              </div>
            </div>
          </div>
        </div>

        {/* ── 3. System suggestion box ── */}
        <div style={{
          padding: 14,
          background: 'color-mix(in srgb, var(--amber) 8%, var(--ink-light))',
          border: '1px solid color-mix(in srgb, var(--amber) 30%, var(--ink-border))',
          borderRadius: 6,
          display: 'flex',
          gap: 12,
        }}>
          <I.Alert size={18} style={{ color: 'var(--amber)', flexShrink: 0, marginTop: 2 }} />
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 11, fontFamily: 'var(--font-mono)', letterSpacing: '0.16em', color: 'var(--amber)', marginBottom: 4 }}>
              SYSTEM SUGGESTION: {current.suggestion.toUpperCase()}
            </div>
            <div style={{ fontSize: 12, color: 'var(--text-primary)', lineHeight: 1.55 }}>
              {current.reason}
            </div>
          </div>
        </div>

        {/* ── Manual edit area (conditional) ── */}
        {editMode && (
          <div style={{ padding: 14, background: 'var(--ink-deep)', border: '1px solid var(--ink-border)', borderRadius: 6 }}>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, letterSpacing: '0.16em', color: 'var(--text-tertiary)', marginBottom: 8 }}>
              MANUAL CORRECTION
            </div>
            <div className="input" style={{ padding: '10px 14px' }}>
              <input
                className="jp"
                style={{ fontSize: 16 }}
                placeholder="Enter corrected text..."
                value={editValue || current.ocr}
                onChange={e => setEditValue(e.target.value)}
                autoFocus
              />
            </div>
            <div style={{ display: 'flex', gap: 6, marginTop: 8 }}>
              <button className="btn btn--success btn--sm" onClick={() => handleResolve('manual')}>
                <I.Check size={11} /> Apply
              </button>
              <button className="btn btn--ghost btn--sm" onClick={() => setEditMode(false)}>
                Cancel
              </button>
            </div>
          </div>
        )}

        {/* ── 4. Action buttons ── */}
        {!editMode && (
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr', gap: 8 }}>
            <button
              className={`btn${current.suggestion === 'ocr' ? ' btn--success' : ''}`}
              style={{ justifyContent: 'center', padding: '12px 0' }}
              onClick={() => handleResolve('ocr')}
            >
              <span className="kbd">1</span> 採用 OCR
            </button>
            <button
              className={`btn${current.suggestion === 'asr' ? ' btn--success' : ''}`}
              style={{ justifyContent: 'center', padding: '12px 0' }}
              onClick={() => handleResolve('asr')}
            >
              <span className="kbd">2</span> 採用 ASR
            </button>
            <button
              className="btn"
              style={{ justifyContent: 'center', padding: '12px 0' }}
              onClick={() => setEditMode(true)}
            >
              <span className="kbd">3</span> 手動修正
            </button>
            <button
              className="btn btn--ghost"
              style={{ justifyContent: 'center', padding: '12px 0', border: '1px solid var(--ink-border)' }}
              onClick={() => handleResolve('skip')}
            >
              <span className="kbd">S</span> 跳過
            </button>
          </div>
        )}

        {/* ── 5. Navigation (prev/next) + mini queue list ── */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 0', borderTop: '1px solid var(--ink-border)' }}>
          <button className="btn btn--ghost btn--sm" onClick={goPrev} disabled={currentIdx === 0}>
            <I.ChevronLeft size={13} /> Prev
          </button>
          <div className="mono dim" style={{ fontSize: 11, letterSpacing: '0.1em' }}>
            {currentIdx + 1} / {pendingConflicts.length}
          </div>
          <button className="btn btn--ghost btn--sm" onClick={goNext} disabled={currentIdx >= pendingConflicts.length - 1}>
            Next <I.ChevronRight size={13} />
          </button>
        </div>

        {/* Mini queue */}
        <div style={{ display: 'flex', gap: 4, justifyContent: 'center', flexWrap: 'wrap' }}>
          {conflicts.map((c, i) => {
            const isResolved = !!decisions[c.idx];
            const pendingIdx = pendingConflicts.indexOf(c);
            const isCurrent = pendingIdx === currentIdx;
            return (
              <button
                key={c.idx}
                onClick={() => {
                  if (!isResolved && pendingIdx >= 0) setCurrentIdx(pendingIdx);
                }}
                style={{
                  width: 20,
                  height: 20,
                  borderRadius: 3,
                  border: isCurrent ? '1px solid var(--amber)' : '1px solid var(--ink-border)',
                  background: isResolved
                    ? 'var(--success)'
                    : isCurrent
                      ? 'var(--amber-glow)'
                      : 'var(--ink-deep)',
                  opacity: isResolved ? 0.4 : 1,
                  fontSize: 8,
                  fontFamily: 'var(--font-mono)',
                  color: isResolved ? 'var(--ink-deep)' : 'var(--text-tertiary)',
                  display: 'grid',
                  placeItems: 'center',
                  cursor: isResolved ? 'default' : 'pointer',
                }}
                title={`#${c.idx} - ${decisions[c.idx] || 'pending'}`}
              >
                {i + 1}
              </button>
            );
          })}
        </div>

        {/* ── 6. Hotkey hints ── */}
        <div style={{
          display: 'flex',
          gap: 14,
          fontFamily: 'var(--font-mono)',
          fontSize: 10,
          color: 'var(--text-tertiary)',
          justifyContent: 'center',
          padding: '8px 0',
          borderTop: '1px dashed var(--ink-border)',
        }}>
          <span><span className="kbd">1</span> OCR</span>
          <span><span className="kbd">2</span> ASR</span>
          <span><span className="kbd">3</span> Manual</span>
          <span><span className="kbd">S</span> Skip</span>
          <span><span className="kbd">&larr;</span> Prev</span>
          <span><span className="kbd">&rarr;</span> Next</span>
        </div>
      </div>
    </div>
  );
};

export default ConflictPage;
