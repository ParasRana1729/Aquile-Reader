export type ThemeId =
  | 'vine-yard'
  | 'dark-side'
  | 'fresh-berry'
  | 'pulpy-orange'
  | 'clear-sky'
  | 'flash'
  | 'turquoise'
  | 'green-apple';

export interface ColorTheme {
  id: ThemeId;
  name: string;
  titlebarBg: string;
  titlebarText: string;
  accent: string;
  accentHover: string;
  accentGlow: string;
  swatchOuter: string;
  swatchInner: string;
  isLight: boolean;
}

export const COLOR_THEMES: Record<ThemeId, ColorTheme> = {
  'vine-yard': {
    id: 'vine-yard',
    name: 'Vine Yard',
    titlebarBg: '#514f11',
    titlebarText: '#ffffff',
    accent: '#b6c12c',
    accentHover: '#c8d433',
    accentGlow: 'rgba(182, 193, 44, 0.35)',
    swatchOuter: '#362125',
    swatchInner: '#c6c927',
    isLight: false,
  },
  'dark-side': {
    id: 'dark-side',
    name: 'Dark Side',
    titlebarBg: '#680036',
    titlebarText: '#ffffff',
    accent: '#d41b6c',
    accentHover: '#eb227d',
    accentGlow: 'rgba(212, 27, 108, 0.4)',
    swatchOuter: '#3b0f27',
    swatchInner: '#d41b6c',
    isLight: false,
  },
  'fresh-berry': {
    id: 'fresh-berry',
    name: 'Fresh Berry',
    titlebarBg: '#c2c0df',
    titlebarText: '#18181b',
    accent: '#7265a8',
    accentHover: '#8473bb',
    accentGlow: 'rgba(114, 101, 168, 0.35)',
    swatchOuter: '#dbe5d8',
    swatchInner: '#6e73b8',
    isLight: true,
  },
  'pulpy-orange': {
    id: 'pulpy-orange',
    name: 'Pulpy Orange',
    titlebarBg: '#e26a2c',
    titlebarText: '#18181b',
    accent: '#ea7600',
    accentHover: '#ff8608',
    accentGlow: 'rgba(234, 118, 0, 0.35)',
    swatchOuter: '#faeedb',
    swatchInner: '#ea7600',
    isLight: true,
  },
  'clear-sky': {
    id: 'clear-sky',
    name: 'Clear sky',
    titlebarBg: '#8ecdf7',
    titlebarText: '#18181b',
    accent: '#0078d4',
    accentHover: '#1084d8',
    accentGlow: 'rgba(0, 120, 212, 0.35)',
    swatchOuter: '#edf5fb',
    swatchInner: '#3ca8f4',
    isLight: true,
  },
  'flash': {
    id: 'flash',
    name: 'Flash',
    titlebarBg: '#8c1818',
    titlebarText: '#ffffff',
    accent: '#e81123',
    accentHover: '#f02434',
    accentGlow: 'rgba(232, 17, 35, 0.4)',
    swatchOuter: '#640a0c',
    swatchInner: '#e85610',
    isLight: false,
  },
  'turquoise': {
    id: 'turquoise',
    name: 'Turquoise',
    titlebarBg: '#065e4f',
    titlebarText: '#ffffff',
    accent: '#00b294',
    accentHover: '#02c7a6',
    accentGlow: 'rgba(0, 178, 148, 0.35)',
    swatchOuter: '#063731',
    swatchInner: '#00b294',
    isLight: false,
  },
  'green-apple': {
    id: 'green-apple',
    name: 'Green Apple',
    titlebarBg: '#5d7c15',
    titlebarText: '#ffffff',
    accent: '#7462ba',
    accentHover: '#8672d3',
    accentGlow: 'rgba(116, 98, 186, 0.35)',
    swatchOuter: '#d0e68a',
    swatchInner: '#7462ba',
    isLight: false,
  },
};
