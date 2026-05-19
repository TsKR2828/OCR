import React from 'react';
import { SCENE_TYPES, CHARACTERS } from '../data/mock';

/* --- SceneBadge --- */

interface SceneBadgeProps {
  scene: string;
  jp?: boolean;
}

const sceneLabels: Record<string, { label: string; jp: string }> = {};
SCENE_TYPES.forEach((s) => {
  sceneLabels[s.id] = { label: s.label, jp: s.jp };
});

export const SceneBadge: React.FC<SceneBadgeProps> = ({ scene, jp }) => {
  const info = sceneLabels[scene];
  const label = info ? (jp ? info.jp : info.label) : scene;
  return (
    <span className={`badge badge--${scene}`}>
      {label}
    </span>
  );
};

/* --- ScoreBadge --- */

interface ScoreBadgeProps {
  score: number;
}

function scoreTier(score: number): string {
  if (score >= 60) return 'high';
  if (score >= 30) return 'mid';
  return 'low';
}

export const ScoreBadge: React.FC<ScoreBadgeProps> = ({ score }) => {
  const tier = scoreTier(score);
  return (
    <span className={`badge badge--score badge--score-${tier}`}>
      {score}
    </span>
  );
};

/* --- SpeakerBadge --- */

interface SpeakerBadgeProps {
  name: string | null;
  kind?: string;
}

const charColors: Record<string, string> = {};
CHARACTERS.forEach((c) => {
  charColors[c.name] = c.color;
  c.aliases.forEach((a) => {
    charColors[a] = c.color;
  });
});

export const SpeakerBadge: React.FC<SpeakerBadgeProps> = ({ name, kind }) => {
  if (!name) return null;
  const color = charColors[name];
  const style = color ? { borderColor: color, color } : undefined;
  return (
    <span className="badge badge--speaker" style={style}>
      {name}
      {kind && <span> ({kind})</span>}
    </span>
  );
};
