import React, { useState, useEffect, useRef } from 'react';
import {
  Menu,
  FileText,
  Bookmark,
  Search,
  Volume2,
  VolumeX,
  ZoomIn,
  ZoomOut,
  Columns,
  Maximize2,
  Minimize2,
  Type,
  BookOpen,
  ArrowLeft,
  ChevronDown,
} from 'lucide-react';
import { ReaderSettings, ReaderMode, ReadingTheme, READER_THEMES } from '../../types/reader';
import { AppearancePopover } from './AppearancePopover';

interface FloatingToolbarProps {
  bookTitle?: string;
  settings: ReaderSettings;
  onUpdateSettings: (updates: Partial<ReaderSettings>) => void;
  onBack?: () => void;
  // Drawers & Overlays
  onToggleTOC: () => void;
  onToggleBookmarks: () => void;
  onToggleAnnotations: () => void;
  onToggleSearch: () => void;
  isTOCOpen: boolean;
  isBookmarksOpen: boolean;
  isAnnotationsOpen: boolean;
  isSearchOpen: boolean;
  // ReadAloud TTS
  onToggleReadAloud: () => void;
  isReadingAloud: boolean;
  // Zoom
  onZoomIn: () => void;
  onZoomOut: () => void;
  // Mode selection
  currentMode: ReaderMode;
  onChangeMode: (mode: ReaderMode) => void;
  // Progress & Stats
  currentPage: number;
  totalPages: number;
  readingSpeedWpm?: number;
}

export const FloatingToolbar: React.FC<FloatingToolbarProps> = ({
  bookTitle = 'The Prince',
  settings,
  onUpdateSettings,
  onBack,
  onToggleTOC,
  onToggleBookmarks,
  onToggleAnnotations,
  onToggleSearch,
  isTOCOpen,
  isBookmarksOpen,
  isAnnotationsOpen,
  isSearchOpen,
  onToggleReadAloud,
  isReadingAloud,
  onZoomIn,
  onZoomOut,
  currentMode,
  onChangeMode,
  currentPage,
  totalPages,
  readingSpeedWpm = 220,
}) => {
  const [isVisible, setIsVisible] = useState(true);
  const [isAppearanceOpen, setIsAppearanceOpen] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [isModeDropdownOpen, setIsModeDropdownOpen] = useState(false);
  const hideTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const currentTheme = READER_THEMES[settings.theme] || READER_THEMES.night;
  const isDark = currentTheme.isDark;

  // Auto-hiding logic: reveal on top-screen hover, auto-hide when idle
  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (e.clientY <= 65) {
        setIsVisible(true);
        if (hideTimerRef.current) clearTimeout(hideTimerRef.current);
      } else {
        // If no modal/popover is open, schedule auto-hide
        if (
          !isAppearanceOpen &&
          !isSearchOpen &&
          !isTOCOpen &&
          !isBookmarksOpen &&
          !isAnnotationsOpen &&
          !isModeDropdownOpen
        ) {
          if (hideTimerRef.current) clearTimeout(hideTimerRef.current);
          hideTimerRef.current = setTimeout(() => {
            setIsVisible(false);
          }, 3000);
        }
      }
    };

    window.addEventListener('mousemove', handleMouseMove);
    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      if (hideTimerRef.current) clearTimeout(hideTimerRef.current);
    };
  }, [
    isAppearanceOpen,
    isSearchOpen,
    isTOCOpen,
    isBookmarksOpen,
    isAnnotationsOpen,
    isModeDropdownOpen,
  ]);

  // Keep toolbar visible if any popover is active
  useEffect(() => {
    if (
      isAppearanceOpen ||
      isSearchOpen ||
      isTOCOpen ||
      isBookmarksOpen ||
      isAnnotationsOpen ||
      isModeDropdownOpen
    ) {
      setIsVisible(true);
      if (hideTimerRef.current) clearTimeout(hideTimerRef.current);
    }
  }, [
    isAppearanceOpen,
    isSearchOpen,
    isTOCOpen,
    isBookmarksOpen,
    isAnnotationsOpen,
    isModeDropdownOpen,
  ]);

  // Fullscreen listener
  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(!!document.fullscreenElement);
    };
    document.addEventListener('fullscreenchange', handleFullscreenChange);
    return () => document.removeEventListener('fullscreenchange', handleFullscreenChange);
  }, []);

  const handleToggleFullscreen = () => {
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen().catch(() => {});
    } else {
      document.exitFullscreen().catch(() => {});
    }
  };

  const buttonClass = (isActive = false) => `
    p-1.5 rounded transition-all duration-150 flex items-center justify-center
    ${
      isActive
        ? 'bg-primary/25 text-white ring-1 ring-primary/40'
        : isDark
        ? 'text-neutral-300 hover:text-white hover:bg-white/10'
        : 'text-neutral-700 hover:text-black hover:bg-black/10'
    }
  `;

  return (
    <nav
      aria-label="Reader Navigation"
      className={`fixed top-0 left-0 right-0 z-40 transition-transform duration-300 ease-out ${
        isVisible ? 'translate-y-0 opacity-100' : '-translate-y-full opacity-0 pointer-events-none'
      }`}
      onMouseEnter={() => {
        setIsVisible(true);
        if (hideTimerRef.current) clearTimeout(hideTimerRef.current);
      }}
    >
      <div
        className="h-11 w-full flex items-center justify-between px-3 md:px-5 border-b backdrop-blur-md shadow-lg select-none"
        style={{
          backgroundColor: currentTheme.toolbarBg,
          borderColor: currentTheme.border,
          color: currentTheme.text,
        }}
      >
        {/* Left Toolbar Controls (matching win_004) */}
        <div className="flex items-center gap-1">
          {onBack && (
            <button
              type="button"
              onClick={onBack}
              className={buttonClass()}
              title="Return to Library"
            >
              <ArrowLeft size={16} />
            </button>
          )}

          {/* Table of Contents */}
          <button
            type="button"
            onClick={onToggleTOC}
            className={buttonClass(isTOCOpen)}
            title="Table of Contents (☰)"
          >
            <Menu size={16} />
          </button>

          {/* Annotations & Notes */}
          <button
            type="button"
            onClick={onToggleAnnotations}
            className={buttonClass(isAnnotationsOpen)}
            title="Annotations & Notes (📝)"
          >
            <FileText size={16} />
          </button>

          {/* Bookmarks */}
          <button
            type="button"
            onClick={onToggleBookmarks}
            className={buttonClass(isBookmarksOpen)}
            title="Bookmarks (🔖)"
          >
            <Bookmark size={16} />
          </button>

          {/* Engine / Document Mode Switcher */}
          <div className="relative ml-2">
            <button
              onClick={() => setIsModeDropdownOpen(!isModeDropdownOpen)}
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-medium border transition-colors ${
                isDark
                  ? 'bg-white/5 border-white/10 hover:bg-white/10 text-neutral-200'
                  : 'bg-black/5 border-black/10 hover:bg-black/10 text-neutral-800'
              }`}
              title="Reader Engine Mode"
            >
              <BookOpen size={13} className="text-primary" />
              <span className="capitalize">{currentMode}</span>
              <ChevronDown size={11} className="opacity-60" />
            </button>

            {isModeDropdownOpen && (
              <div
                className={`absolute top-full left-0 mt-1 w-36 rounded-lg shadow-xl border p-1 z-50 backdrop-blur-xl ${
                  isDark ? 'bg-[#2b2b2b] border-white/10 text-neutral-200' : 'bg-white border-black/10 text-neutral-800'
                }`}
              >
                {(['sanctum', 'pdf', 'epub', 'comic'] as ReaderMode[]).map((mode) => (
                  <button
                    key={mode}
                    onClick={() => {
                      onChangeMode(mode);
                      setIsModeDropdownOpen(false);
                    }}
                    className={`w-full text-left px-2.5 py-1.5 rounded text-xs capitalize transition-colors flex items-center justify-between ${
                      currentMode === mode
                        ? 'bg-primary/20 text-primary font-medium'
                        : isDark
                        ? 'hover:bg-white/5'
                        : 'hover:bg-black/5'
                    }`}
                  >
                    <span>{mode === 'sanctum' ? 'Sanctum (Text)' : mode.toUpperCase()}</span>
                    {currentMode === mode && <span className="w-1.5 h-1.5 rounded-full bg-primary" />}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Center Title & Quick Stats */}
        <div className="hidden md:flex items-center gap-3 text-xs opacity-75 font-serif truncate max-w-sm">
          <span className="truncate italic">{bookTitle}</span>
          <span className="text-[11px] opacity-60 font-sans">
            {currentPage} of {totalPages}
          </span>
          {readingSpeedWpm > 0 && (
            <span className="text-[10px] opacity-40 font-mono tracking-tight hidden lg:inline">
              ~{readingSpeedWpm} WPM
            </span>
          )}
        </div>

        {/* Right Toolbar Controls (matching win_004) */}
        <div className="flex items-center gap-1.5">
          {/* Search */}
          <button
            type="button"
            onClick={onToggleSearch}
            className={buttonClass(isSearchOpen)}
            title="Search in Book (🔍)"
          >
            <Search size={16} />
          </button>

          <div className="h-4 w-[1px] bg-white/10 mx-0.5" />

          {/* ReadAloud TTS */}
          <button
            type="button"
            onClick={onToggleReadAloud}
            className={buttonClass(isReadingAloud)}
            title={isReadingAloud ? 'Stop ReadAloud TTS' : 'Start ReadAloud TTS (<⊝>)'}
          >
            {isReadingAloud ? (
              <VolumeX size={16} className="text-red-400 animate-pulse" />
            ) : (
              <Volume2 size={16} />
            )}
          </button>

          {/* Zoom Out */}
          <button
            type="button"
            onClick={onZoomOut}
            className={buttonClass()}
            title="Zoom Out (🔍-)"
          >
            <ZoomOut size={16} />
          </button>

          {/* Zoom In */}
          <button
            type="button"
            onClick={onZoomIn}
            className={buttonClass()}
            title="Zoom In (🔍+)"
          >
            <ZoomIn size={16} />
          </button>

          {/* Column Toggle (1 vs 2 cols) */}
          <button
            type="button"
            onClick={() => onUpdateSettings({ isTwoColumn: !settings.isTwoColumn })}
            className={buttonClass(settings.isTwoColumn)}
            title={settings.isTwoColumn ? 'Switch to 1-Column' : 'Switch to 2-Column Spread (📖)'}
          >
            <Columns size={16} />
          </button>

          {/* Font & Appearance Settings */}
          <button
            type="button"
            onClick={() => setIsAppearanceOpen(!isAppearanceOpen)}
            className={buttonClass(isAppearanceOpen)}
            title="Appearance & Typography Settings (Aa)"
          >
            <Type size={16} />
          </button>

          <div className="h-4 w-[1px] bg-white/10 mx-0.5" />

          {/* Fullscreen */}
          <button
            type="button"
            onClick={handleToggleFullscreen}
            className={buttonClass(isFullscreen)}
            title="Toggle Fullscreen (⤢)"
          >
            {isFullscreen ? <Minimize2 size={16} /> : <Maximize2 size={16} />}
          </button>
        </div>
      </div>

      {/* Appearance Popover */}
      {isAppearanceOpen && (
        <AppearancePopover
          settings={settings}
          onUpdateSettings={onUpdateSettings}
          onClose={() => setIsAppearanceOpen(false)}
        />
      )}
    </nav>
  );
};
