import React from 'react';
import type { PageId } from '../types';
import { CHANNEL, STATS } from '../data/mock';
import { fmtTime } from '../data/mock';
import { I } from './Icons';

const NAV = [
  { id: 'dashboard', label: 'Dashboard', jp: 'ダッシュボード', icon: 'Dashboard', hot: '1' },
  { id: 'timeline', label: 'Timeline', jp: 'タイムライン', icon: 'Timeline', hot: '2' },
  { id: 'search', label: 'Search', jp: '検索', icon: 'Search', hot: '3' },
  { id: 'conflict', label: 'Conflict Review', jp: '衝突審稿', icon: 'Conflict', hot: '4' },
  { id: 'clips', label: 'Clips', jp: '精彩片段', icon: 'Clips', hot: '5' },
  { id: 'stats', label: 'Stats', jp: '統計', icon: 'Stats', hot: '6' },
  { id: 'settings', label: 'Settings', jp: '設定', icon: 'Settings', hot: '7' },
] as const;

interface SidebarProps {
  active: PageId;
  onNav: (page: PageId) => void;
  conflictsPending: number;
}

export const Sidebar: React.FC<SidebarProps> = ({ active, onNav, conflictsPending }) => {
  return (
    <aside className="sidebar">
      {/* Brand */}
      <div className="sidebar-brand">
        <span className="sidebar-brand__mark">VN</span>
        <span className="sidebar-brand__name">VN-TRANSCRIBE</span>
        <span className="sidebar-brand__sub">v0.1.0</span>
      </div>

      {/* Navigation */}
      <div className="sidebar-section">
        <span className="sidebar-section__label">Navigation</span>
        <nav className="sidebar-nav">
          {NAV.map((item) => {
            const Icon = I[item.icon];
            const isActive = active === item.id;
            return (
              <button
                key={item.id}
                className={`nav-item${isActive ? ' nav-item--active' : ''}`}
                onClick={() => onNav(item.id as PageId)}
              >
                <span className="nav-item__icon">
                  {Icon && <Icon size={18} />}
                </span>
                <span>{item.label}</span>
                {item.id === 'conflict' && conflictsPending > 0 && (
                  <span className="badge badge--conflict">{conflictsPending}</span>
                )}
                <span className="nav-item__hot">{'⌘'}{item.hot}</span>
              </button>
            );
          })}
        </nav>
      </div>

      {/* Info */}
      <div className="sidebar-info">
        <div className="sidebar-info__row">
          <span className="sidebar-info__label">File</span>
          <span className="sidebar-info__value sidebar-info__file">{CHANNEL.file}</span>
        </div>
        <div className="sidebar-info__row">
          <span className="sidebar-info__label">Game</span>
          <span className="sidebar-info__value">{CHANNEL.game}</span>
        </div>
        <div className="sidebar-info__row">
          <span className="sidebar-info__label">Duration</span>
          <span className="sidebar-info__value">{fmtTime(STATS.duration)}</span>
        </div>
        <div className="sidebar-info__row">
          <span className="sidebar-info__label">Segments</span>
          <span className="sidebar-info__value">{STATS.totalSegments.toLocaleString()}</span>
        </div>
        <div className="sidebar-info__row">
          <span className="sidebar-info__label">Conflicts</span>
          <span className="sidebar-info__value">{STATS.conflicts} ({STATS.resolvedConflicts} resolved)</span>
        </div>
      </div>
    </aside>
  );
};

