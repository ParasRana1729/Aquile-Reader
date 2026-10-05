export type ReadingTheme = 'night' | 'sepia' | 'white' | 'gray';
export type FontFamilyId = 'serif' | 'sans' | 'mono' | 'dyslexic';
export type MarginOption = 'compact' | 'normal' | 'wide';
export type ReaderMode = 'sanctum' | 'pdf' | 'epub' | 'comic';

export interface ReaderThemeConfig {
  id: ReadingTheme;
  name: string;
  bg: string;
  pageBg: string;
  text: string;
  muted: string;
  border: string;
  hairline: string;
  toolbarBg: string;
  isDark: boolean;
}

export const READER_THEMES: Record<ReadingTheme, ReaderThemeConfig> = {
  night: {
    id: 'night',
    name: 'Night',
    bg: '#262626',
    pageBg: '#262626',
    text: '#EAEAEA',
    muted: '#999999',
    border: 'rgba(255, 255, 255, 0.1)',
    hairline: 'rgba(255, 255, 255, 0.12)',
    toolbarBg: 'rgba(24, 24, 24, 0.75)',
    isDark: true,
  },
  sepia: {
    id: 'sepia',
    name: 'Sepia',
    bg: '#fbf0d9',
    pageBg: '#fbf0d9',
    text: '#5f4b32',
    muted: '#8a7358',
    border: 'rgba(95, 75, 50, 0.15)',
    hairline: 'rgba(95, 75, 50, 0.18)',
    toolbarBg: 'rgba(245, 233, 208, 0.85)',
    isDark: false,
  },
  white: {
    id: 'white',
    name: 'White',
    bg: '#ffffff',
    pageBg: '#ffffff',
    text: '#111111',
    muted: '#666666',
    border: 'rgba(0, 0, 0, 0.1)',
    hairline: 'rgba(0, 0, 0, 0.12)',
    toolbarBg: 'rgba(250, 250, 250, 0.85)',
    isDark: false,
  },
  gray: {
    id: 'gray',
    name: 'Gray',
    bg: '#333333',
    pageBg: '#333333',
    text: '#e0e0e0',
    muted: '#aaaaaa',
    border: 'rgba(255, 255, 255, 0.12)',
    hairline: 'rgba(255, 255, 255, 0.14)',
    toolbarBg: 'rgba(38, 38, 38, 0.8)',
    isDark: true,
  },
};

export interface FontFamilyConfig {
  id: FontFamilyId;
  name: string;
  cssFamily: string;
  description: string;
}

export const FONT_FAMILIES: Record<FontFamilyId, FontFamilyConfig> = {
  serif: {
    id: 'serif',
    name: 'Serif',
    cssFamily: "'Merriweather', 'Georgia', 'Liberation Serif', 'DejaVu Serif', serif",
    description: 'Merriweather / Georgia',
  },
  sans: {
    id: 'sans',
    name: 'Sans',
    cssFamily: "'Segoe UI', 'Inter', system-ui, -apple-system, sans-serif",
    description: 'Segoe UI / Inter',
  },
  mono: {
    id: 'mono',
    name: 'Monospace',
    cssFamily: "'JetBrains Mono', 'Consolas', 'AdwaitaMono Nerd Font', 'Liberation Mono', monospace",
    description: 'JetBrains / Consolas',
  },
  dyslexic: {
    id: 'dyslexic',
    name: 'Dyslexic',
    cssFamily: "'OpenDyslexic', 'Comic Sans MS', 'Chalkboard SE', cursive, sans-serif",
    description: 'High readability',
  },
};

export interface ReaderSettings {
  theme: ReadingTheme;
  fontSize: number; // 12 to 36 px
  lineSpacing: number; // 1.2 to 2.4
  fontFamily: FontFamilyId;
  isTwoColumn: boolean;
  margin: MarginOption;
  zoom: number; // 0.5 to 3.0
}

export const DEFAULT_READER_SETTINGS: ReaderSettings = {
  theme: 'night',
  fontSize: 18,
  lineSpacing: 1.6,
  fontFamily: 'serif',
  isTwoColumn: false,
  margin: 'normal',
  zoom: 1.0,
};

export interface TOCItem {
  id: string;
  label: string;
  href?: string;
  page?: number;
  subitems?: TOCItem[];
}

export interface Bookmark {
  id: string;
  bookId?: string;
  page: number;
  title: string;
  createdAt: number | string;
  excerpt?: string;
}

export interface Annotation {
  id: string;
  bookId?: string;
  bookTitle?: string;
  page?: number;
  text?: string;
  selectedText?: string;
  cfiRange?: string;
  note?: string;
  color: string;
  createdAt: number | string;
  updatedAt?: number | string;
}

export interface ReadingSessionStats {
  bookId: string;
  currentPage: number;
  totalPages: number;
  progressPercentage: number;
  activeReadingSeconds: number;
  wordsRead: number;
  readingSpeedWpm: number;
  lastCheckpoint: number;
}

export interface MonthlyStat {
  month: string;
  daysRead: number;
  readingTimeMinutes: number;
  pagesRead: number;
}

export interface ReadingStats {
  totalBooksRead: number;
  totalReadingTimeSeconds: number;
  totalWordsRead: number;
  totalDaysRead: number;
  currentStreakDays: number;
  recordStreakDays: number;
  avgReadingTimePerDayMinutes: number;
  avgSpeedWpm: number;
  monthlyStats: MonthlyStat[];
}
