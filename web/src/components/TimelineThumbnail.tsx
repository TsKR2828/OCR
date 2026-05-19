import { useRef } from 'react';
import { DENSITY, SCENE_BAND, HOT_SPOTS, VIDEO_DURATION, fmtTime } from '../data/mock';

interface Props {
  onClick?: (time: number) => void;
  height?: number;
  showWaveform?: boolean;
  showHotspots?: boolean;
  playhead?: number | null;
}

export function TimelineThumbnail({ onClick, height = 56, showWaveform = true, showHotspots = true, playhead }: Props) {
  const total = DENSITY.length;
  const ref = useRef<HTMLDivElement>(null);

  const handleClick = (e: React.MouseEvent) => {
    if (!ref.current) return;
    const rect = ref.current.getBoundingClientRect();
    const pct = (e.clientX - rect.left) / rect.width;
    onClick?.(pct * VIDEO_DURATION);
  };

  return (
    <div
      ref={ref}
      onClick={handleClick}
      style={{
        position: 'relative',
        height,
        background: 'var(--ink-deep)',
        borderRadius: 4,
        border: '1px solid var(--ink-border)',
        cursor: 'pointer',
        overflow: 'hidden',
      }}
    >
      {/* Scene band — bottom 30% */}
      <div style={{ position: 'absolute', left: 0, right: 0, bottom: 0, height: '30%', display: 'flex' }}>
        {SCENE_BAND.map((s, i) => (
          <div key={i} style={{ flex: 1, background: `var(--scene-${s})`, opacity: 0.75 }} />
        ))}
      </div>

      {/* Density waveform */}
      {showWaveform && (
        <div style={{ position: 'absolute', left: 0, right: 0, top: 0, bottom: '30%', display: 'flex', alignItems: 'flex-end' }}>
          {DENSITY.map((d, i) => (
            <div key={i} style={{
              flex: 1,
              height: `${d * 100}%`,
              background: HOT_SPOTS.includes(i) ? 'var(--amber)' : 'color-mix(in srgb, var(--text-secondary) 60%, transparent)',
              opacity: HOT_SPOTS.includes(i) ? 0.95 : 0.5,
              marginRight: 1,
            }} />
          ))}
        </div>
      )}

      {/* Hotspot markers */}
      {showHotspots && HOT_SPOTS.map((i) => (
        <div key={i} style={{
          position: 'absolute',
          left: `${(i / total) * 100}%`,
          top: 0, height: '70%',
          width: 1,
          background: 'var(--amber)',
          opacity: 0.5,
          pointerEvents: 'none',
        }} />
      ))}

      {/* Playhead */}
      {playhead != null && (
        <div style={{
          position: 'absolute',
          left: `${(playhead / VIDEO_DURATION) * 100}%`,
          top: 0, bottom: 0, width: 2,
          background: 'var(--amber)',
          boxShadow: '0 0 6px var(--amber)',
        }} />
      )}

      {/* Time labels */}
      <div style={{ position: 'absolute', left: 0, right: 0, top: 0, height: 14, display: 'flex', justifyContent: 'space-between', padding: '0 4px', pointerEvents: 'none' }}>
        {[0, 0.25, 0.5, 0.75, 1].map((p) => (
          <span key={p} style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 8,
            color: 'var(--text-tertiary)',
            background: 'var(--ink-deep)',
            padding: '0 3px',
            letterSpacing: '0.06em',
          }}>{fmtTime(VIDEO_DURATION * p)}</span>
        ))}
      </div>
    </div>
  );
}
