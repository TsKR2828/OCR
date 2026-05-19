import { I } from './Icons';
import { SceneBadge, ScoreBadge, SpeakerBadge } from './Badges';
import { fmtTime } from '../data/mock';
import type { Segment } from '../types';

interface Props {
  seg: Segment;
  expanded?: boolean;
  selected?: boolean;
  onToggle?: () => void;
  onClick?: () => void;
}

export function SegmentCard({ seg, expanded, selected, onToggle, onClick }: Props) {
  const sceneColor = `var(--scene-${seg.scene})`;
  const cls = ['segment-card'];
  if (expanded) cls.push('segment-card--expanded');
  if (selected) cls.push('segment-card--selected');
  if (seg.status === 'conflict') cls.push('segment-card--conflict');

  return (
    <div className={cls.join(' ')} style={{ '--scene-color': sceneColor } as React.CSSProperties} onClick={onClick}>
      <div className="segment-card__head">
        <span className="segment-card__idx">#{String(seg.idx).padStart(4, '0')}</span>
        <span className="segment-card__time">
          {fmtTime(seg.start)}
          <span className="segment-card__time-arrow"> → </span>
          {fmtTime(seg.end)}
        </span>
        <span className="dim mono" style={{ fontSize: 10 }}>{(seg.end - seg.start).toFixed(1)}s</span>
        <div className="segment-card__head-right">
          <SceneBadge scene={seg.scene} />
          {seg.events?.includes('chat_spike') && (
            <span className="badge badge--spike"><I.Spike size={9} /> SPIKE</span>
          )}
          {seg.events?.includes('superchat') && (
            <span className="badge badge--sc"><I.SC size={9} /> SC</span>
          )}
          <ScoreBadge score={seg.score} />
        </div>
      </div>

      {seg.ocr?.text && (
        <div className="segment-card__layer segment-card__layer--ocr">
          <div className="segment-card__layer-label">
            <I.Eye size={10} style={{ marginRight: 3, verticalAlign: -1 }} />OCR
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
            <I.Mic size={10} style={{ marginRight: 3, verticalAlign: -1 }} />ASR
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
            <I.Chat size={10} style={{ marginRight: 3, verticalAlign: -1 }} />CHAT
          </div>
          <div className={'segment-card__chat-stats' + (seg.chat.spike ? ' segment-card__chat-stats--spike' : '')}>
            <span><strong>{seg.chat.count}</strong> msgs</span>
            <span><strong>{seg.chat.rate}</strong>/min</span>
            {seg.chat.spike && <span style={{ color: 'var(--chat-spike)' }}>● SPIKE</span>}
            {seg.chat.sc?.map((s, i) => (
              <span key={i} style={{ color: 'var(--superchat)' }}>SC: {s.user} ¥{s.amount}</span>
            ))}
          </div>
        </div>
      )}

      <div className="segment-card__foot">
        <span>merge: {seg.merge}</span>
        <span>·</span>
        <span className={
          seg.status === 'consistent' ? 'badge badge--status-ok' :
          seg.status === 'conflict' ? 'badge badge--status-conflict' :
          'badge badge--status-unverified'
        } style={{ padding: '1px 5px', fontSize: 9 }}>
          {seg.status === 'consistent' ? '✓ consistent' :
           seg.status === 'conflict' ? '⚠ conflict' : '○ unverified'}
        </span>
        {(seg.events?.length ?? 0) > 0 && (
          <>
            <span>·</span>
            <span>{seg.events!.length} event{seg.events!.length > 1 ? 's' : ''}</span>
          </>
        )}
        <div className="segment-card__foot-right">
          <button className="segment-card__expand-btn" onClick={(e) => { e.stopPropagation(); onToggle?.(); }}>
            {expanded ? '收合' : '展開'} <I.Chevron size={10} style={{ transform: expanded ? 'rotate(180deg)' : 'none' }} />
          </button>
        </div>
      </div>

      {expanded && (
        <div className="segment-card__expanded-area">
          <div className="score-breakdown">
            <div className="score-breakdown__title">SCORE BREAKDOWN</div>
            {([
              ['volume', '音量'],
              ['laughter', '笑聲'],
              ['keyword', '關鍵字'],
              ['chat', '聊天密度'],
              ['speech_rate', '語速突變'],
              ['silence_burst', '靜默爆發'],
            ] as const).map(([key, label]) => (
              <div className="score-bar" key={key}>
                <span className="score-bar__label">{label}</span>
                <div className="score-bar__track">
                  <div className="score-bar__fill" style={{ width: `${((seg.breakdown as any)?.[key] || 0) * 4}%` }} />
                </div>
                <span className="score-bar__value">{(seg.breakdown as any)?.[key] || 0}</span>
              </div>
            ))}
          </div>

          <div className="event-list">
            <div className="score-breakdown__title">EVENTS</div>
            {(seg.events?.length ?? 0) > 0 ? seg.events!.map((e, i) => (
              <div className="event-list__item" key={i}>
                <span style={{ color: 'var(--amber)' }}>●</span> {e}
              </div>
            )) : <div className="dim" style={{ fontSize: 11 }}>— no events —</div>}
            {seg.conflict_note && (
              <div style={{
                marginTop: 8, padding: 8,
                background: 'color-mix(in srgb, var(--danger) 12%, transparent)',
                borderRadius: 3, fontSize: 11, color: 'var(--danger)',
                border: '1px solid color-mix(in srgb, var(--danger) 30%, transparent)'
              }}>
                <strong style={{ display: 'block', fontFamily: 'var(--font-mono)', fontSize: 9, letterSpacing: '0.16em', marginBottom: 4 }}>CONFLICT</strong>
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
                <div className="event-list__item">配信主の反応かわ��い</div>
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
