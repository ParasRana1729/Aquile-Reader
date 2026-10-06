import React, { useState, useEffect } from 'react';
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
import { ReaderSettings, ReaderMode, READER_THEMES } from '../../types/reader';
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
  const [isAppearanceOpen, setIsAppearanceOpen] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [isModeDropdownOpen, setIsModeDropdownOpen] = useState(false);

  const cleanBookTitle = (bookTitle || '').replace(/[\uFFFD\0]/g, '').trim();
  const currentTheme = READER_THEMES[settings.theme] || READER_THEMES.night;
  const isDark = currentTheme.isDark;
  const isDualSpread = settings.spreadMode === 'dual' || settings.isTwoColumn;

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
      aria-label="Reader Options Toolbar"
      className="w-full flex-shrink-0 z-40 select-none relative"
      style={{
        backgroundColor: currentTheme.toolbarBg || '#2e2f34',
        borderBottom: `1px solid ${currentTheme.border || '#333338'}`,
        color: currentTheme.text || '#ffffff',
      }}
    >
      <div className="h-11 w-full flex items-center justify-between px-3 md:px-5">
        {/* Left Toolbar Controls (TOC, Notes, Bookmarks, Engine) */}
        <div className="flex items-center gap-1.5">
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
          <div className="relative ml-1.5">
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

        {/* Center Quick Stats (Matching Windows native reader clean layout) */}
        <div className="hidden md:flex items-center gap-3 text-xs opacity-80 font-sans select-none antialiased">
          {cleanBookTitle && (
            <span className="truncate max-w-[260px] font-normal opacity-70 hidden xl:inline" title={cleanBookTitle}>
              {cleanBookTitle}
            </span>
          )}
          {totalPages > 0 && (
            <span className="text-[12px] opacity-75 font-normal">
              {currentPage} of {totalPages}
            </span>
          )}
          {readingSpeedWpm > 0 && (
            <span className="text-[11px] opacity-50 font-sans tracking-tight hidden lg:inline">
              ~{readingSpeedWpm} WPM
            </span>
          )}
        </div>

        {/* Right Toolbar Controls (Search, TTS, Zoom, Spread, Appearance, Fullscreen) */}
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
            title={isReadingAloud ? 'Stop ReadAloud TTS' : 'Start ReadAloud TTS (🔊)'}
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

          {/* Spread Mode Toggle (Single Column vs 2-Column Spread) */}
          <button
            type="button"
            onClick={() => {
              const nextVal = !isDualSpread;
              onUpdateSettings({
                isTwoColumn: nextVal,
                spreadMode: nextVal ? 'dual' : 'single',
              });
            }}
            className={buttonClass(isDualSpread)}
            title={isDualSpread ? 'Switch to Single Column' : 'Switch to Two-Page Spread (📖)'}
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
