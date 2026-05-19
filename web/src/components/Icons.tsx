import React from 'react';

interface IconProps {
  size?: number;
  className?: string;
  style?: React.CSSProperties;
}

const svg = (children: React.ReactNode): React.FC<IconProps> => {
  const Icon: React.FC<IconProps> = ({ size = 20, className, style }) => (
    <svg
      viewBox="0 0 20 20"
      width={size}
      height={size}
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      style={style}
    >
      {children}
    </svg>
  );
  return Icon;
};

export const Dashboard = svg(
  <>
    <rect x="3" y="3" width="6.5" height="6.5" rx="1" />
    <rect x="10.5" y="3" width="6.5" height="6.5" rx="1" />
    <rect x="3" y="10.5" width="6.5" height="6.5" rx="1" />
    <rect x="10.5" y="10.5" width="6.5" height="6.5" rx="1" />
  </>
);

export const Timeline = svg(
  <>
    <line x1="2.5" y1="10" x2="17.5" y2="10" />
    <circle cx="5" cy="10" r="1.5" fill="currentColor" />
    <circle cx="10" cy="10" r="1.5" />
    <circle cx="15" cy="10" r="1.5" fill="currentColor" />
    <line x1="5" y1="13" x2="5" y2="15" />
    <line x1="10" y1="5" x2="10" y2="7" />
    <line x1="15" y1="13" x2="15" y2="15" />
  </>
);

export const Search = svg(
  <>
    <circle cx="8.5" cy="8.5" r="5" />
    <line x1="12.5" y1="12.5" x2="16.5" y2="16.5" />
  </>
);

export const Conflict = svg(
  <>
    <path d="M4 5 L10 5 L10 15 L16 15" />
    <path d="M4 15 L10 15 L10 5 L16 5" />
    <circle cx="4" cy="5" r="1.3" fill="currentColor" />
    <circle cx="16" cy="15" r="1.3" fill="currentColor" />
  </>
);

export const Clips = svg(
  <>
    <circle cx="6" cy="6" r="2.5" />
    <circle cx="6" cy="14" r="2.5" />
    <line x1="8" y1="7.5" x2="17" y2="13" />
    <line x1="8" y1="12.5" x2="17" y2="7" />
  </>
);

export const Stats = svg(
  <>
    <line x1="3" y1="17" x2="17" y2="17" />
    <rect x="4.5" y="10" width="2.5" height="7" />
    <rect x="8.75" y="6" width="2.5" height="11" />
    <rect x="13" y="12" width="2.5" height="5" />
  </>
);

export const Settings = svg(
  <>
    <circle cx="10" cy="10" r="2.5" />
    <path d="M10 2.5 L10 4.5 M10 15.5 L10 17.5 M2.5 10 L4.5 10 M15.5 10 L17.5 10 M4.7 4.7 L6.1 6.1 M13.9 13.9 L15.3 15.3 M4.7 15.3 L6.1 13.9 M13.9 6.1 L15.3 4.7" />
  </>
);

export const Eye = svg(
  <>
    <path d="M2 10 C 4.5 5, 7 4, 10 4 S 15.5 5, 18 10 C 15.5 15, 13 16, 10 16 S 4.5 15, 2 10 Z" />
    <circle cx="10" cy="10" r="2.5" />
  </>
);

export const Mic = svg(
  <>
    <rect x="7.5" y="3" width="5" height="9" rx="2.5" />
    <path d="M4.5 10 C 4.5 13.5, 7 15, 10 15 S 15.5 13.5, 15.5 10" />
    <line x1="10" y1="15" x2="10" y2="17.5" />
  </>
);

export const Chat = svg(
  <path d="M3 6 C 3 4.5, 4 3.5, 5.5 3.5 L 14.5 3.5 C 16 3.5, 17 4.5, 17 6 L 17 12 C 17 13.5, 16 14.5, 14.5 14.5 L 8 14.5 L 4.5 17 L 4.5 14.5 C 3.5 14.3, 3 13.5, 3 12 Z" />
);

export const Spike = svg(
  <path d="M11 2 L 5 11 L 9.5 11 L 8 18 L 14 9 L 9.5 9 Z" />
);

export const SC = svg(
  <>
    <circle cx="10" cy="10" r="7" />
    <path d="M12.5 7 C 11 6, 8 6.5, 8 8.5 C 8 11, 12 10, 12 12 C 12 14, 8.5 14.5, 7 13" />
    <line x1="10" y1="4" x2="10" y2="5.5" />
    <line x1="10" y1="14.5" x2="10" y2="16" />
  </>
);

export const Download = svg(
  <>
    <line x1="10" y1="3" x2="10" y2="13" />
    <path d="M6 9.5 L 10 13 L 14 9.5" />
    <line x1="3.5" y1="16.5" x2="16.5" y2="16.5" />
  </>
);

export const Filter = svg(
  <path d="M3 4 L 17 4 L 12 10 L 12 16 L 8 14 L 8 10 Z" />
);

export const Chevron = svg(
  <polyline points="6 8 10 12 14 8" />
);

export const ChevronRight = svg(
  <polyline points="8 5 12 10 8 15" />
);

export const ChevronLeft = svg(
  <polyline points="12 5 8 10 12 15" />
);

export const Close = svg(
  <>
    <line x1="5" y1="5" x2="15" y2="15" />
    <line x1="15" y1="5" x2="5" y2="15" />
  </>
);

export const Play = svg(
  <path d="M5 4 L 16 10 L 5 16 Z" fill="currentColor" />
);

export const Pause = svg(
  <>
    <rect x="5" y="4" width="3" height="12" fill="currentColor" />
    <rect x="12" y="4" width="3" height="12" fill="currentColor" />
  </>
);

export const Upload = svg(
  <>
    <line x1="10" y1="13" x2="10" y2="3" />
    <path d="M6 6.5 L 10 3 L 14 6.5" />
    <line x1="3.5" y1="16.5" x2="16.5" y2="16.5" />
  </>
);

export const Check = svg(
  <polyline points="4 10 8.5 14.5 16 6.5" />
);

export const Cross = svg(
  <>
    <line x1="5" y1="5" x2="15" y2="15" />
    <line x1="15" y1="5" x2="5" y2="15" />
  </>
);

export const Edit = svg(
  <>
    <path d="M3 17 L 6 16 L 15 7 L 13 5 L 4 14 Z" />
    <line x1="12" y1="6" x2="14" y2="8" />
  </>
);

export const Skip = svg(
  <>
    <polyline points="6 5 11 10 6 15" />
    <polyline points="11 5 16 10 11 15" />
  </>
);

export const Alert = svg(
  <>
    <path d="M10 3 L 17 16 L 3 16 Z" />
    <line x1="10" y1="8" x2="10" y2="12" />
    <circle cx="10" cy="14" r="0.8" fill="currentColor" />
  </>
);

export const User = svg(
  <>
    <circle cx="10" cy="7" r="3" />
    <path d="M3 17 C 3 13.5, 6 11.5, 10 11.5 S 17 13.5, 17 17" />
  </>
);

export const Copy = svg(
  <>
    <rect x="6" y="6" width="10" height="11" rx="1" />
    <path d="M13 6 L 13 3.5 L 4 3.5 L 4 13" />
  </>
);

export const Pin = svg(
  <>
    <path d="M10 2.5 L 10 8 L 13 11 L 7 11 L 10 8" />
    <line x1="10" y1="11" x2="10" y2="17.5" />
  </>
);

export const Folder = svg(
  <path d="M3 6 L 3 15 C 3 15.8, 3.5 16.5, 4.5 16.5 L 15.5 16.5 C 16.5 16.5, 17 15.8, 17 15 L 17 8 C 17 7.2, 16.5 6.5, 15.5 6.5 L 9 6.5 L 7.5 5 L 4.5 5 C 3.5 5, 3 5.5, 3 6 Z" />
);

export const Reaction = svg(
  <path d="M10 2.5 L 11.5 7.5 L 17 8 L 12.5 11 L 14 16 L 10 13 L 6 16 L 7.5 11 L 3 8 L 8.5 7.5 Z" />
);

export const Dialogue = svg(
  <>
    <path d="M3 5.5 C 3 4.5, 3.8 4, 4.5 4 L 9.5 4 C 10.5 4, 11 4.8, 11 5.5 L 11 9 C 11 10, 10.5 10.5, 9.5 10.5 L 6 10.5 L 4 12 L 4 10.5 C 3.5 10.5, 3 10, 3 9 Z" />
    <path d="M9 9 L 9 8 C 9 7.2, 9.5 7, 10.2 7 L 15 7 C 16 7, 16.5 7.5, 16.5 8.3 L 16.5 12 C 16.5 13, 16 13.5, 15 13.5 L 13.5 13.5 L 15.5 16 L 15.5 13.5" />
  </>
);

export const Narration = svg(
  <>
    <path d="M4 3.5 L 4 16.5 L 9 14.5 L 14 16.5 L 14 3.5 L 9 5.5 Z" />
    <line x1="9" y1="5.5" x2="9" y2="14.5" />
  </>
);

export const Choice = svg(
  <>
    <line x1="10" y1="3" x2="10" y2="9" />
    <path d="M10 9 L 4 16" />
    <path d="M10 9 L 16 16" />
    <circle cx="10" cy="3" r="1.2" fill="currentColor" />
    <circle cx="4" cy="16" r="1.2" />
    <circle cx="16" cy="16" r="1.2" />
  </>
);

export const Transition = svg(
  <>
    <path d="M3 7 L 9 7 L 7 5" />
    <path d="M3 7 L 9 7 L 7 9" />
    <path d="M17 13 L 11 13 L 13 11" />
    <path d="M17 13 L 11 13 L 13 15" />
  </>
);

export const Silence = svg(
  <>
    <line x1="3" y1="10" x2="5" y2="10" />
    <line x1="8" y1="10" x2="10" y2="10" />
    <line x1="13" y1="10" x2="15" y2="10" />
    <line x1="17" y1="10" x2="17.5" y2="10" />
  </>
);

export const I: Record<string, React.FC<IconProps>> = {
  Dashboard,
  Timeline,
  Search,
  Conflict,
  Clips,
  Stats,
  Settings,
  Eye,
  Mic,
  Chat,
  Spike,
  SC,
  Download,
  Filter,
  Chevron,
  ChevronRight,
  ChevronLeft,
  Close,
  Play,
  Pause,
  Upload,
  Check,
  Cross,
  Edit,
  Skip,
  Alert,
  User,
  Copy,
  Pin,
  Folder,
  Reaction,
  Dialogue,
  Narration,
  Choice,
  Transition,
  Silence,
};

export default I;
