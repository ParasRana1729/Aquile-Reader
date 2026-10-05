import React, { createContext, useContext, useEffect, useState } from 'react';
import { COLOR_THEMES, ColorTheme, ThemeId } from '../types/theme';

interface ThemeContextType {
  currentTheme: ColorTheme;
  themeId: ThemeId;
  setTheme: (id: ThemeId) => void;
  isTransparent: boolean;
  setIsTransparent: (val: boolean) => void;
  transparencyOpacity: number;
  setTransparencyOpacity: (val: number) => void;
  wallpaperIndex: number;
  setWallpaperIndex: (idx: number) => void;
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

export const ThemeProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [themeId, setThemeIdState] = useState<ThemeId>(() => {
    const saved = localStorage.getItem('aquile_theme_id');
    return (saved && saved in COLOR_THEMES) ? (saved as ThemeId) : 'dark-side';
  });

  const [isTransparent, setIsTransparentState] = useState<boolean>(() => {
    const saved = localStorage.getItem('aquile_transparent_bg');
    return saved !== null ? saved === 'true' : true;
  });

  const [transparencyOpacity, setTransparencyOpacityState] = useState<number>(() => {
    const saved = localStorage.getItem('aquile_bg_opacity');
    return saved ? Number(saved) : 85;
  });

  const [wallpaperIndex, setWallpaperIndex] = useState<number>(0);

  const currentTheme = COLOR_THEMES[themeId] || COLOR_THEMES['dark-side'];

  const setTheme = (id: ThemeId) => {
    if (COLOR_THEMES[id]) {
      setThemeIdState(id);
      localStorage.setItem('aquile_theme_id', id);
    }
  };

  const setIsTransparent = (val: boolean) => {
    setIsTransparentState(val);
    localStorage.setItem('aquile_transparent_bg', String(val));
  };

  const setTransparencyOpacity = (val: number) => {
    const clamped = Math.max(10, Math.min(100, val));
    setTransparencyOpacityState(clamped);
    localStorage.setItem('aquile_bg_opacity', String(clamped));
  };

  useEffect(() => {
    const root = document.documentElement;
    root.style.setProperty('--accent-color', currentTheme.accent);
    root.style.setProperty('--accent-hover', currentTheme.accentHover);
    root.style.setProperty('--accent-glow', currentTheme.accentGlow);
    root.style.setProperty('--titlebar-bg', currentTheme.titlebarBg);
    root.style.setProperty('--titlebar-text', currentTheme.titlebarText);
    root.style.setProperty(
      '--acrylic-opacity',
      isTransparent ? String(transparencyOpacity / 100) : '1.0'
    );
  }, [currentTheme, isTransparent, transparencyOpacity]);

  return (
    <ThemeContext.Provider
      value={{
        currentTheme,
        themeId,
        setTheme,
        isTransparent,
        setIsTransparent,
        transparencyOpacity,
        setTransparencyOpacity,
        wallpaperIndex,
        setWallpaperIndex,
      }}
    >
      {children}
    </ThemeContext.Provider>
  );
};

export const useTheme = (): ThemeContextType => {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error('useTheme must be used within a ThemeProvider');
  }
  return context;
};
