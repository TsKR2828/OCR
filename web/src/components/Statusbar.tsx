import React from 'react';
import { STATS } from '../data/mock';

interface StatusbarProps {
  page: string;
}

export const Statusbar: React.FC<StatusbarProps> = ({ page }) => {
  return (
    <footer className="statusbar">
      <span className="statusbar__dot" title="Pipeline OK" />
      <span>OCR: {STATS.totalSegments} segments</span>
      <span className="statusbar__sep" />
      <span>ASR: whisper-large-v3</span>
      <span className="statusbar__sep" />
      <span>Chat: {STATS.scDistinctUsers} users</span>
      <span className="statusbar__sep" />
      <span className="statusbar__right">
        <span>{page}</span>
        <span className="statusbar__sep" />
        <span>UTC+8</span>
        <span className="statusbar__sep" />
        <span>Crimson</span>
      </span>
    </footer>
  );
};

