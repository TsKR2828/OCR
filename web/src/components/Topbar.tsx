import React from 'react';

interface TopbarProps {
  title: string;
  jpTitle?: string;
  breadcrumb?: string;
  actions?: React.ReactNode;
  children?: React.ReactNode;
}

export const Topbar: React.FC<TopbarProps> = ({ title, jpTitle, breadcrumb, actions, children }) => {
  return (
    <header className="topbar">
      <div className="topbar__title">
        <span className="topbar__title-main">
          {breadcrumb && <span>{breadcrumb} / </span>}
          {title}
        </span>
        {jpTitle && <span className="topbar__title-sub">{jpTitle}</span>}
      </div>
      {(actions || children) && <div className="topbar__actions">{actions}{children}</div>}
    </header>
  );
};

