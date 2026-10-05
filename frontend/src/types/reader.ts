export type ReadingTheme = 'night' | 'sepia' | 'white' | 'gray';
export type FontFamilyId =
  | 'inter'
  | 'merriweather'
  | 'georgia'
  | 'jetbrains'
  | 'bookerly'
  | 'literata'
  | 'system'
  | 'dyslexic'
  | 'serif'
  | 'sans'
  | 'mono';
export type MarginOption = 'compact' | 'normal' | 'wide' | number;
export type ReaderMode = 'sanctum' | 'pdf' | 'epub' | 'comic';
export type SpreadMode = 'single' | 'dual';
export type TextAlignment = 'left' | 'justify' | 'center';

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
  inter: {
    id: 'inter',
    name: 'Inter',
    cssFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
    description: 'Clean modern sans',
  },
  merriweather: {
    id: 'merriweather',
    name: 'Merriweather',
    cssFamily: "'Merriweather', Georgia, serif",
    description: 'Designed for screens',
  },
  georgia: {
    id: 'georgia',
    name: 'Georgia',
    cssFamily: "'Georgia', 'Times New Roman', serif",
    description: 'Classic editorial serif',
  },
  jetbrains: {
    id: 'jetbrains',
    name: 'JetBrains Mono',
    cssFamily: "'JetBrains Mono', 'Fira Code', Menlo, Consolas, monospace",
    description: 'Developer monospace',
  },
  bookerly: {
    id: 'bookerly',
    name: 'Bookerly',
    cssFamily: "'Bookerly', 'Merriweather', Georgia, serif",
    description: 'Warm literary serif',
  },
  literata: {
    id: 'literata',
    name: 'Literata',
    cssFamily: "'Literata', Georgia, serif",
    description: 'Digital book serif',
  },
  system: {
    id: 'system',
    name: 'System',
    cssFamily: "system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif",
    description: 'Native OS font',
  },
  dyslexic: {
    id: 'dyslexic',
    name: 'OpenDyslexic',
    cssFamily: "'OpenDyslexic', 'Comic Sans MS', cursive, sans-serif",
    description: 'High readability',
  },
  // Backward compatibility aliases
  serif: {
    id: 'serif',
    name: 'Serif',
    cssFamily: "'Merriweather', 'Georgia', serif",
    description: 'Merriweather / Georgia',
  },
  sans: {
    id: 'sans',
    name: 'Sans',
    cssFamily: "'Inter', -apple-system, BlinkMacSystemFont, system-ui, sans-serif",
    description: 'Segoe UI / Inter',
  },
  mono: {
    id: 'mono',
    name: 'Monospace',
    cssFamily: "'JetBrains Mono', 'Consolas', monospace",
    description: 'JetBrains / Consolas',
  },
};

export interface ReaderAppearance {
  theme: ReadingTheme;
  fontSize: number; // 12 to 36 px
  lineSpacing: number; // 1.2 to 2.4
  fontFamily: FontFamilyId | string;
  spreadMode: SpreadMode; // 'single' | 'dual'
  letterSpacing: number; // e.g. -0.5 to 3 px
  paragraphSpacing: number; // e.g. 0 to 24 px
  textAlign: TextAlignment; // 'left' | 'justify' | 'center'
  margin: number; // 16 to 120 px
  customFont?: string;
}

export interface ReaderSettings extends ReaderAppearance {
  isTwoColumn: boolean; // Synced with spreadMode === 'dual'
  zoom: number; // 0.5 to 3.0
}

export const DEFAULT_READER_APPEARANCE: ReaderAppearance = {
  theme: 'night',
  fontSize: 18,
  lineSpacing: 1.6,
  fontFamily: 'merriweather',
  spreadMode: 'single',
  letterSpacing: 0,
  paragraphSpacing: 16,
  textAlign: 'justify',
  margin: 36,
  customFont: '',
};

export const DEFAULT_READER_SETTINGS: ReaderSettings = {
  ...DEFAULT_READER_APPEARANCE,
  isTwoColumn: false,
  zoom: 1.0,
};

export function getFontFamilyCss(fontFamily?: string, customFont?: string): string {
  if (customFont && customFont.trim().length > 0) {
    return `"${customFont.trim()}", system-ui, -apple-system, sans-serif`;
  }
  if (!fontFamily) return FONT_FAMILIES.merriweather.cssFamily;
  const match = FONT_FAMILIES[fontFamily as FontFamilyId];
  if (match) return match.cssFamily;
  return fontFamily;
}

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
