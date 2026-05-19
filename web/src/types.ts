/* VN-Transcribe type definitions */

export type SceneType = 'dialogue' | 'narration' | 'choice' | 'transition' | 'reaction' | 'silence';
export type SpeakerGuess = 'streamer' | 'game_voice' | 'mixed' | 'unknown';
export type MatchStatus = 'consistent' | 'conflict' | 'readback_possible' | 'unverified' | 'not_applicable';
export type SourceType = 'ocr_asr' | 'ocr_only' | 'asr_only' | 'event_only' | 'none';
export type PageId = 'dashboard' | 'timeline' | 'search' | 'conflict' | 'clips' | 'stats' | 'settings';
export type AccentColor = 'gold' | 'brass' | 'copper' | 'verdigris';
export type ScenePalette = 'default' | 'muted' | 'vivid';
export type Density = 'comfortable' | 'compact';

export interface SegmentOcr {
  speaker: string | null;
  text: string;
}

export interface SegmentAsr {
  speaker: string | null;
  text: string;
}

export interface SegmentChat {
  count: number;
  rate: number;
  spike: boolean;
  sc: { user: string; amount: number }[];
}

export interface ScoreBreakdown {
  volume: number;
  laughter: number;
  keyword: number;
  chat: number;
  speech_rate: number;
  silence_burst: number;
}

export interface Segment {
  idx: number;
  start: number;
  end: number;
  scene: SceneType;
  score: number;
  ocr?: SegmentOcr;
  asr?: SegmentAsr;
  chat?: SegmentChat;
  merge: SourceType;
  status: MatchStatus;
  events?: string[];
  conflict_note?: string;
  breakdown?: ScoreBreakdown;
}

export interface Conflict {
  idx: number;
  segmentIdx: number;
  time: number;
  status: 'pending' | 'resolved';
  ocr: string;
  asr: string;
  diff: { pos: number; ocr: string; asr: string }[];
  suggestion: 'ocr' | 'asr' | 'manual';
  reason: string;
  confidence: number;
  resolution?: string;
}

export interface Clip {
  id: number;
  segIdx: number;
  start: number;
  end: number;
  score: number;
  scene: SceneType;
  title: string;
  quote: string;
  quoteJp: string;
  sc: number;
}

export interface Character {
  id: string;
  name: string;
  aliases: string[];
  color: string;
  lines: number;
  firstAt: number;
  lastAt: number;
}

export interface SceneTypeInfo {
  id: SceneType;
  label: string;
  jp: string;
  count: number;
  color: string;
}

export interface ChannelInfo {
  name: string;
  game: string;
  game_language: string;
  default_language: string;
  file: string;
  date: string;
}

export interface StatsInfo {
  totalSegments: number;
  duration: number;
  avgSegLen: number;
  conflicts: number;
  resolvedConflicts: number;
  highlights: number;
  characters: number;
  scDistinctUsers: number;
  scTotal: number;
  scoreHistogram: { range: string; count: number }[];
}

export interface NavItem {
  id: PageId;
  label: string;
  jp: string;
  icon: string;
  hot: string;
}

export interface TweakValues {
  accent: AccentColor;
  density: Density;
  showSidebarInfo: boolean;
  scenePalette: ScenePalette;
  monoFont: string;
  serifHeadings: boolean;
}

export interface SearchMode {
  id: string;
  label: string;
  jp: string;
  icon: string;
  placeholder: string;
}

export interface SearchResult {
  time: number;
  scene: SceneType;
  char: string;
  jp: string;
  asr: string;
  chat: number;
  score: number;
  spike?: boolean;
  conflict?: boolean;
}
