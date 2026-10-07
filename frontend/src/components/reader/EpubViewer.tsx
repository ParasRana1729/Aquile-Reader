import React, { useEffect, useRef, useState, useCallback } from 'react';
import {
  ReaderSettings,
  READER_THEMES,
  TOCItem,
  getFontFamilyCss,
  Annotation,
} from '../../types/reader';
import { getPageTransition, subscribePageTransition } from '../../utils/readerPrefs';
import { parseEpubToPages, EpubPage } from '../../utils/epubPaginator';
import { readBookBytes } from '../../utils/ipc';
import { ChevronLeft, ChevronRight, Copy, Highlighter, Volume2 } from 'lucide-react';

export interface EpubSearchResult {
  cfi?: string;
  excerpt: string;
  page?: number;
}

interface EpubViewerProps {
  url: string;
  bookTitle?: string;
  settings: ReaderSettings;
  currentPage: number;
  totalPages: number;
  onPageChange: (page: number, total: number, percentage?: number) => void;
  onLoadTOC?: (toc: TOCItem[]) => void;
  onNavigateRef?: React.MutableRefObject<((target: string | number) => void) | null>;
  onSearchRef?: React.MutableRefObject<((query: string) => Promise<EpubSearchResult[]>) | null>;
  onJumpToPageRef?: React.MutableRefObject<((page: number) => void) | null>;
  onAddAnnotation?: (annotation: Omit<Annotation, 'id' | 'createdAt'>) => void;
  onSpeakText?: (text: string) => void;
}

export const EpubViewer: React.FC<EpubViewerProps> = ({
  url,
  bookTitle: propBookTitle,
  settings,
  currentPage,
  totalPages,
  onPageChange,
  onLoadTOC,
  onNavigateRef,
  onSearchRef,
  onJumpToPageRef,
  onAddAnnotation,
  onSpeakText,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const pageRefs = useRef<Map<number, HTMLElement>>(new Map());
  const initialPageRef = useRef(currentPage || 1);
  const isNavigatingRef = useRef(false);
  const navTimerRef = useRef<number | null>(null);

  const [pages, setPages] = useState<EpubPage[]>([]);
  const [metaTitle, setMetaTitle] = useState(propBookTitle || 'Book');
  const [metaAuthor, setMetaAuthor] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Transition animation state
  const [turnStyle, setTurnStyle] = useState(getPageTransition());
  const [animClass, setAnimClass] = useState('');

  // Selection tooltip state
  const [selectionRange, setSelectionRange] = useState<{
    text: string;
    rect: DOMRect;
  } | null>(null);

  useEffect(() => {
    return subscribePageTransition((style) => {
      setTurnStyle(style);
    });
  }, []);

  useEffect(() => {
    return () => {
      if (navTimerRef.current !== null) {
        window.clearTimeout(navTimerRef.current);
      }
    };
  }, []);

  const currentTheme = READER_THEMES[settings.theme] || READER_THEMES.night;
  const zoomFactor = typeof settings.zoom === 'number' && settings.zoom > 0 ? settings.zoom : 1.0;
  const effectiveFontSize = Math.max(10, Math.min(60, Math.round((settings.fontSize || 18) * zoomFactor)));
  const effectiveLineSpacing = settings.lineSpacing || 1.6;
  const effectiveParaSpacing = Math.round((settings.paragraphSpacing ?? 16) * zoomFactor);
  const fontCss = getFontFamilyCss(settings.fontFamily, settings.customFont);
  const letterSpacing = `${settings.letterSpacing ?? 0}px`;
  const align = settings.textAlign || 'justify';
  const marginPx = typeof settings.margin === 'number' ? settings.margin : 32;
  const pagePadX = Math.max(24, marginPx);
  const pageShadow = currentTheme.isDark
    ? '0 1px 3px rgba(0,0,0,0.45), 0 8px 24px rgba(0,0,0,0.28)'
    : '0 1px 2px rgba(0,0,0,0.10), 0 8px 24px rgba(0,0,0,0.14)';

  // Jump to specific page
  const jumpToPage = useCallback(
    (targetPage: number) => {
      if (!pages.length) return;
      const target = Math.max(1, Math.min(targetPage, pages.length));
      const el = pageRefs.current.get(target);
      if (el && containerRef.current) {
        isNavigatingRef.current = true;
        if (navTimerRef.current !== null) {
          window.clearTimeout(navTimerRef.current);
        }

        if (turnStyle === 'Slide') {
          setAnimClass('transition-transform duration-300 ease-out');
        } else if (turnStyle === 'Fade') {
          setAnimClass('transition-opacity duration-300 ease-in-out opacity-40');
          setTimeout(() => setAnimClass('transition-opacity duration-300 ease-in-out opacity-100'), 50);
        }

        el.scrollIntoView({ behavior: 'smooth', block: 'start' });

        const pct = Math.round(((target - 1) / pages.length) * 100);
        onPageChange(target, pages.length, pct);

        navTimerRef.current = window.setTimeout(() => {
          isNavigatingRef.current = false;
          setAnimClass('');
        }, 600);
      }
    },
    [pages.length, onPageChange, turnStyle]
  );

  useEffect(() => {
    if (onJumpToPageRef) {
      onJumpToPageRef.current = jumpToPage;
    }
  }, [onJumpToPageRef, jumpToPage]);

  // Navigate ref handler (target can be 'next', 'prev', number, or string)
  const navigateTo = useCallback(
    (target: string | number) => {
      if (target === 'next') {
        jumpToPage(currentPage + 1);
      } else if (target === 'prev') {
        jumpToPage(currentPage - 1);
      } else if (typeof target === 'number') {
        jumpToPage(target);
      } else if (typeof target === 'string') {
        const pageNum = parseInt(target, 10);
        if (!isNaN(pageNum)) {
          jumpToPage(pageNum);
        }
      }
    },
    [currentPage, jumpToPage]
  );

  useEffect(() => {
    if (onNavigateRef) {
      onNavigateRef.current = navigateTo;
    }
  }, [onNavigateRef, navigateTo]);

  // Search handler ref
  const searchInEpub = useCallback(
    async (query: string): Promise<EpubSearchResult[]> => {
      if (!query || !query.trim() || !pages.length) return [];
      const qLower = query.toLowerCase().trim();
      const results: EpubSearchResult[] = [];

      for (const page of pages) {
        for (const para of page.paragraphs) {
          const idx = para.toLowerCase().indexOf(qLower);
          if (idx !== -1) {
            const start = Math.max(0, idx - 40);
            const end = Math.min(para.length, idx + query.length + 40);
            const snippet = (start > 0 ? '…' : '') + para.substring(start, end).trim() + (end < para.length ? '…' : '');
            results.push({
              excerpt: snippet,
              page: page.pageNumber,
            });
            if (results.length >= 50) break;
          }
        }
        if (results.length >= 50) break;
      }

      return results;
    },
    [pages]
  );

  useEffect(() => {
    if (onSearchRef) {
      onSearchRef.current = searchInEpub;
    }
  }, [onSearchRef, searchInEpub]);

  // Load and parse EPUB book
  useEffect(() => {
    let isCancelled = false;
    setLoading(true);
    setError(null);

    async function loadBook() {
      try {
        let arrayBuffer: ArrayBuffer;
        if (url.startsWith('blob:') || url.startsWith('http')) {
          const resp = await fetch(url);
          arrayBuffer = await resp.arrayBuffer();
        } else {
          const bytes = await readBookBytes(url);
          if (!bytes) {
            throw new Error('Unable to read book bytes');
          }
          arrayBuffer = bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength) as ArrayBuffer;
        }

        if (isCancelled) return;

        const parsed = await parseEpubToPages(arrayBuffer, {
          fontSize: settings.fontSize,
          zoom: settings.zoom,
          bookTitle: propBookTitle,
        });

        if (isCancelled) return;

        setPages(parsed.pages);
        if (parsed.title) setMetaTitle(parsed.title);
        if (parsed.author) setMetaAuthor(parsed.author);

        if (onLoadTOC && parsed.toc.length > 0) {
          onLoadTOC(parsed.toc);
        }

        // Notify parent of total pages
        const startPage = Math.min(Math.max(1, initialPageRef.current), parsed.pages.length);
        const initialPct = Math.round(((startPage - 1) / parsed.pages.length) * 100);
        onPageChange(startPage, parsed.pages.length, initialPct);

        setLoading(false);

        // Scroll to initial page after rendering
        setTimeout(() => {
          if (!isCancelled && containerRef.current) {
            const targetEl = pageRefs.current.get(startPage);
            if (targetEl) {
              targetEl.scrollIntoView({ behavior: 'auto', block: 'start' });
            }
          }
        }, 80);
      } catch (err: unknown) {
        if (!isCancelled) {
          console.error('[EpubViewer] Failed to load EPUB:', err);
          setError(err instanceof Error ? err.message : 'Failed to parse EPUB file');
          setLoading(false);
        }
      }
    }

    loadBook();

    return () => {
      isCancelled = true;
    };
  }, [url, propBookTitle]);

  // Track active page during continuous vertical scrolling
  const handleScroll = useCallback(() => {
    if (isNavigatingRef.current || !containerRef.current || !pages.length) return;
    const container = containerRef.current;
    const containerRect = container.getBoundingClientRect();
    const focalY = containerRect.top + Math.min(container.clientHeight * 0.35, 260);

    let activePage = currentPage;
    let foundFocal = false;
    let maxVisibleHeight = -1;
    let fallbackPage = currentPage;

    pages.forEach((page) => {
      const el = pageRefs.current.get(page.pageNumber);
      if (!el) return;
      const rect = el.getBoundingClientRect();

      // 1. Focal reading line check: user's gaze is primarily reading near the upper third
      if (rect.top <= focalY && rect.bottom > focalY) {
        activePage = page.pageNumber;
        foundFocal = true;
      }

      // 2. Track page with maximum visible overlap in container
      const visibleTop = Math.max(containerRect.top, rect.top);
      const visibleBottom = Math.min(containerRect.bottom, rect.bottom);
      const visibleHeight = Math.max(0, visibleBottom - visibleTop);
      if (visibleHeight > maxVisibleHeight) {
        maxVisibleHeight = visibleHeight;
        fallbackPage = page.pageNumber;
      }
    });

    const targetPage = foundFocal ? activePage : fallbackPage;
    if (targetPage !== currentPage) {
      const pct = Math.round(((targetPage - 1) / pages.length) * 100);
      onPageChange(targetPage, pages.length, pct);
    }
  }, [pages, currentPage, onPageChange]);

  // Keyboard navigation
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) {
        return;
      }
      if (e.key === 'ArrowRight' || e.key === 'PageDown' || (e.key === ' ' && !e.shiftKey)) {
        e.preventDefault();
        jumpToPage(currentPage + 1);
      } else if (e.key === 'ArrowLeft' || e.key === 'PageUp' || (e.key === ' ' && e.shiftKey)) {
        e.preventDefault();
        jumpToPage(currentPage - 1);
      } else if (e.key === 'Home') {
        e.preventDefault();
        jumpToPage(1);
      } else if (e.key === 'End') {
        e.preventDefault();
        jumpToPage(pages.length);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [currentPage, jumpToPage, pages.length]);

  // Handle text selection for interactive highlighting and notes
  const handleMouseUp = () => {
    const sel = window.getSelection();
    if (!sel || sel.isCollapsed || !sel.toString().trim()) {
      setSelectionRange(null);
      return;
    }

    const text = sel.toString().trim();
    if (text.length > 0) {
      const range = sel.getRangeAt(0);
      const rect = range.getBoundingClientRect();
      setSelectionRange({ text, rect });
    }
  };

  const handleCopySelection = () => {
    if (selectionRange?.text) {
      navigator.clipboard.writeText(selectionRange.text);
      setSelectionRange(null);
    }
  };

  const handleSpeakSelection = () => {
    if (selectionRange?.text && onSpeakText) {
      onSpeakText(selectionRange.text);
      setSelectionRange(null);
    }
  };

  const handleHighlight = (color: string) => {
    if (selectionRange?.text && onAddAnnotation) {
      onAddAnnotation({
        bookId: '',
        bookTitle: metaTitle,
        page: currentPage,
        text: selectionRange.text,
        selectedText: selectionRange.text,
        color,
      });
      setSelectionRange(null);
    }
  };

  // Loading state
  if (loading) {
    return (
      <div
        className="w-full h-full flex flex-col items-center justify-center transition-colors duration-200"
        style={{ backgroundColor: currentTheme.bg, color: currentTheme.text }}
      >
        <div className="flex flex-col items-center gap-4">
          <div className="w-10 h-10 border-4 border-t-transparent rounded-full animate-spin border-[#0078d4]" />
          <span className="text-sm font-sans tracking-wide opacity-75">
            Opening book...
          </span>
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div
        className="w-full h-full flex flex-col items-center justify-center p-8 transition-colors duration-200"
        style={{ backgroundColor: currentTheme.bg, color: currentTheme.text }}
      >
        <div className="max-w-md p-6 bg-red-500/10 border border-red-500/20 rounded-xl text-center space-y-4">
          <p className="font-semibold text-red-400">Failed to load EPUB book</p>
          <p className="text-xs opacity-75 break-words">{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      onScroll={handleScroll}
      onMouseUp={handleMouseUp}
      className={`w-full h-full overflow-y-auto overflow-x-hidden relative select-text scroll-smooth ${animClass}`}
      style={{
        backgroundColor: currentTheme.canvasBg,
        color: currentTheme.text,
      }}
    >
      {/* Edge page-turn zones matching native Windows Aquile Reader */}
      <button
        type="button"
        aria-label="Previous Page"
        onClick={() => jumpToPage(currentPage - 1)}
        className="fixed left-0 top-14 bottom-12 w-[8%] max-w-[80px] z-20 opacity-0 hover:opacity-100 transition-opacity duration-150 flex items-center justify-start pl-2 pointer-events-auto cursor-pointer group"
      >
        <div className="w-9 h-9 rounded-full bg-black/40 backdrop-blur-md flex items-center justify-center text-white/90 shadow-md group-hover:scale-105 transition-transform">
          <ChevronLeft className="w-5 h-5" />
        </div>
      </button>

      <button
        type="button"
        aria-label="Next Page"
        onClick={() => jumpToPage(currentPage + 1)}
        className="fixed right-0 top-14 bottom-12 w-[8%] max-w-[80px] z-20 opacity-0 hover:opacity-100 transition-opacity duration-150 flex items-center justify-end pr-2 pointer-events-auto cursor-pointer group"
      >
        <div className="w-9 h-9 rounded-full bg-black/40 backdrop-blur-md flex items-center justify-center text-white/90 shadow-md group-hover:scale-105 transition-transform">
          <ChevronRight className="w-5 h-5" />
        </div>
      </button>

      {/* Main Reading Canvas: every page is its own bordered sheet on the themed backdrop
          (native Windows Aquile Reader, frame f_011). */}
      <div
        className={`mx-auto w-full px-4 py-6 flex flex-col gap-4 ${
          settings.isTwoColumn ? 'max-w-6xl' : 'max-w-3xl'
        }`}
      >
        {pages.map((page) => (
          <article
            key={page.pageNumber}
            ref={(el) => {
              if (el) pageRefs.current.set(page.pageNumber, el);
              else pageRefs.current.delete(page.pageNumber);
            }}
            data-page-number={page.pageNumber}
            className="relative w-full flex flex-col transition-colors duration-200"
            style={{
              fontFamily: fontCss,
              backgroundColor: currentTheme.pageBg,
              color: currentTheme.text,
              border: `1px solid ${currentTheme.pageBorder}`,
              borderRadius: '2px',
              boxShadow: pageShadow,
              minHeight: 'max(88vh, 880px)',
              padding: `40px ${pagePadX}px 28px`,
              scrollMarginTop: '16px',
            }}
          >
            <div className="flex-1">
            {/* Running Document Header matching native Windows Aquile Reader */}
            <div className="flex items-center justify-between pb-6 select-none opacity-50 text-xs italic tracking-wider">
              <span>{metaTitle}</span>
              <span className="font-sans font-medium text-[11px] not-italic">
                {metaAuthor || 'Aquile Reader'}
              </span>
            </div>

            {/* Chapter Header if start of chapter */}
            {page.chapterTitle && (
              <h2 className="text-xl md:text-2xl font-bold mb-8 tracking-tight opacity-90 border-b pb-3 border-inherit">
                {page.chapterTitle}
              </h2>
            )}

            {/* Page Paragraphs formatted with typography preferences */}
            <div
              className={`leading-relaxed select-text space-y-4 ${
                settings.isTwoColumn ? 'columns-2 gap-8' : ''
              }`}
              style={{
                fontSize: `${effectiveFontSize}px`,
                lineHeight: effectiveLineSpacing,
                letterSpacing,
                textAlign: align,
              }}
            >
              {page.paragraphs.map((para, pIdx) => (
                <p
                  key={pIdx}
                  id={page.anchorIds?.[pIdx]}
                  className="hyphens-auto"
                  style={{
                    marginBottom: `${effectiveParaSpacing}px`,
                  }}
                >
                  {para}
                </p>
              ))}
            </div>
            </div>

            {/* Running Document Footer: authentic page number badge */}
            <div className="mt-8 pt-4 border-t border-inherit/20 flex items-center justify-between text-xs select-none opacity-60">
              <span className="italic font-serif">
                {metaTitle}
              </span>
              <span className="font-mono text-[11px] px-2 py-0.5 rounded bg-black/10 dark:bg-white/10">
                {page.pageNumber} of {pages.length}
              </span>
            </div>
          </article>
        ))}
      </div>

      {/* Floating Selection Tooltip for Highlighting / Copying / TTS */}
      {selectionRange && (
        <div
          className="fixed z-50 flex items-center gap-1.5 p-1.5 bg-neutral-900/90 text-white rounded-lg shadow-xl backdrop-blur-md border border-white/20 -translate-x-1/2 -translate-y-full mb-2 animate-in fade-in zoom-in-95 duration-100"
          style={{
            left: `${selectionRange.rect.left + selectionRange.rect.width / 2}px`,
            top: `${selectionRange.rect.top - 8}px`,
          }}
          onClick={(e) => e.stopPropagation()}
        >
          <button
            type="button"
            onClick={handleCopySelection}
            className="p-1.5 hover:bg-white/20 rounded transition-colors"
            title="Copy Text"
          >
            <Copy className="w-4 h-4" />
          </button>
          {onSpeakText && (
            <button
              type="button"
              onClick={handleSpeakSelection}
              className="p-1.5 hover:bg-white/20 rounded transition-colors"
              title="Read Aloud"
            >
              <Volume2 className="w-4 h-4" />
            </button>
          )}
          {onAddAnnotation && (
            <div className="flex items-center gap-1 pl-1 border-l border-white/20">
              {['#ffeb3b', '#a5d6a7', '#90caf9', '#f48fb1'].map((color) => (
                <button
                  key={color}
                  type="button"
                  onClick={() => handleHighlight(color)}
                  className="w-5 h-5 rounded-full border border-black/30 hover:scale-110 transition-transform"
                  style={{ backgroundColor: color }}
                  title="Highlight"
                />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
