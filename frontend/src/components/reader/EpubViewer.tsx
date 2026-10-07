import React, { useEffect, useRef, useState, useCallback } from 'react';
import ePub, { Book, Rendition } from 'epubjs';
import {
  ReaderSettings,
  READER_THEMES,
  TOCItem,
  getFontFamilyCss,
} from '../../types/reader';
import { ChevronLeft, ChevronRight } from 'lucide-react';

export interface EpubSearchResult {
  cfi?: string;
  excerpt: string;
}

interface EpubViewerProps {
  url: string;
  settings: ReaderSettings;
  currentPage: number;
  totalPages: number;
  onPageChange: (page: number, total: number, percentage?: number) => void;
  onLoadTOC?: (toc: TOCItem[]) => void;
  onNavigateRef?: React.MutableRefObject<((target: string | number) => void) | null>;
  onSearchRef?: React.MutableRefObject<((query: string) => Promise<EpubSearchResult[]>) | null>;
}

export const EpubViewer: React.FC<EpubViewerProps> = ({
  url,
  settings,
  currentPage,
  totalPages,
  onPageChange,
  onLoadTOC,
  onNavigateRef,
  onSearchRef,
}) => {
  const viewerRef = useRef<HTMLDivElement>(null);
  const bookRef = useRef<Book | null>(null);
  const renditionRef = useRef<Rendition | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const currentTheme = READER_THEMES[settings.theme] || READER_THEMES.night;

  // Jump / Navigate ref
  const navigateTo = useCallback((target: string | number) => {
    if (!renditionRef.current) return;
    if (target === 'next') {
      renditionRef.current.next();
      return;
    }
    if (target === 'prev') {
      renditionRef.current.prev();
      return;
    }
    if (typeof target === 'string') {
      renditionRef.current.display(target);
    } else if (typeof target === 'number' && bookRef.current) {
      const cfi = bookRef.current.locations.cfiFromLocation(target);
      if (cfi) renditionRef.current.display(cfi);
    }
  }, []);

  useEffect(() => {
    if (onNavigateRef) {
      onNavigateRef.current = navigateTo;
    }
  }, [onNavigateRef, navigateTo]);

  // Search handler across EPUB spine
  const searchEpub = useCallback(
    async (query: string): Promise<EpubSearchResult[]> => {
      if (!bookRef.current || !query.trim()) return [];
      const results: EpubSearchResult[] = [];
      try {
        const spine = (bookRef.current as any).spine;
        if (!spine || !spine.spineItems) return [];
        for (const item of spine.spineItems) {
          await item.load(bookRef.current.load.bind(bookRef.current));
          const matches = item.find(query);
          item.unload();
          if (Array.isArray(matches)) {
            for (const m of matches) {
              results.push({ cfi: m.cfi, excerpt: m.excerpt || query });
            }
          }
        }
      } catch (e) {
        console.warn('EPUB search error:', e);
      }
      return results;
    },
    []
  );

  useEffect(() => {
    if (onSearchRef) {
      onSearchRef.current = searchEpub;
    }
  }, [onSearchRef, searchEpub]);

  // Apply theme & font & typography customization
  const applyStyles = useCallback(() => {
    if (!renditionRef.current) return;
    const rend = renditionRef.current;
    const fontCss = getFontFamilyCss(settings.fontFamily, settings.customFont);
    const letterSpacing = `${settings.letterSpacing ?? 0}px`;
    const paraSpacing = `${settings.paragraphSpacing ?? 16}px`;
    const align = settings.textAlign || 'justify';
    const marginPx = typeof settings.margin === 'number' ? settings.margin : 32;

    const themeRules = {
      body: {
        'background-color': `${currentTheme.bg} !important`,
        color: `${currentTheme.text} !important`,
        'font-family': `${fontCss} !important`,
        'font-size': `${settings.fontSize}px !important`,
        'line-height': `${settings.lineSpacing} !important`,
        'letter-spacing': `${letterSpacing} !important`,
        'text-align': `${align} !important`,
        '-webkit-font-smoothing': 'antialiased !important',
        'text-rendering': 'optimizeLegibility !important',
        overflowWrap: 'break-word !important',
        margin: '0 auto !important',
        padding: `24px ${marginPx}px 48px !important`,
      },
      p: {
        'line-height': `${settings.lineSpacing} !important`,
        'letter-spacing': `${letterSpacing} !important`,
        'text-align': `${align} !important`,
        'margin-bottom': `${paraSpacing} !important`,
        hyphens: 'auto !important',
        color: `${currentTheme.text} !important`,
      },
      'h1, h2, h3, h4, h5, h6': {
        color: `${currentTheme.text} !important`,
        'font-family': `${fontCss} !important`,
        'letter-spacing': `${letterSpacing} !important`,
      },
      a: {
        color: 'inherit !important',
        'text-decoration': 'underline !important',
      },
      img: {
        'max-width': '100% !important',
        height: 'auto !important',
      },
    };

    rend.themes.register('custom-aquile', themeRules);
    rend.themes.select('custom-aquile');
  }, [
    currentTheme,
    settings.fontFamily,
    settings.customFont,
    settings.fontSize,
    settings.lineSpacing,
    settings.letterSpacing,
    settings.paragraphSpacing,
    settings.textAlign,
    settings.margin,
  ]);

  // Initialize ePub
  useEffect(() => {
    if (!viewerRef.current) return;
    let isCancelled = false;
    setLoading(true);
    setError(null);

    viewerRef.current.innerHTML = '';
    const book = ePub(url);
    bookRef.current = book;

    const isDual = settings.spreadMode === 'dual' || settings.isTwoColumn;
    const rendition = book.renderTo(viewerRef.current, {
      width: '100%',
      height: '100%',
      flow: 'paginated',
      spread: isDual ? 'always' : 'none',
      minSpreadWidth: 768,
    });
    renditionRef.current = rendition;

    book.ready.catch((err) => {
      if (!isCancelled) {
        console.error('Failed to open EPUB:', err);
        setError('Failed to open EPUB document. The file may be invalid, unsupported, or corrupt.');
        setLoading(false);
      }
    });

    rendition.display().then(() => {
      if (isCancelled) return;
      setLoading(false);
      applyStyles();
    }).catch((err) => {
      if (!isCancelled) {
        console.error('Failed to display ePub rendition:', err);
        setError('Failed to display EPUB document.');
        setLoading(false);
      }
    });

    // Extract navigation & Table of Contents
    book.loaded.navigation.then((nav) => {
      if (isCancelled) return;
      if (onLoadTOC && nav && nav.toc) {
        const tocItems: TOCItem[] = nav.toc.map((t, idx) => ({
          id: t.id || `toc-${idx}`,
          label: t.label ? t.label.trim() : `Chapter ${idx + 1}`,
          href: t.href,
        }));
        onLoadTOC(tocItems);
      }
    });

    // Generate locations for accurate page calculation
    book.ready.then(() => {
      book.locations.generate(1600).then(() => {
        if (isCancelled) return;
        const total = book.locations.length();
        if (total > 0) {
          const initialP = currentPage && currentPage > 0 && currentPage <= total ? currentPage : 1;
          const pct = Math.round((initialP / total) * 100);
          onPageChange(initialP, total, pct);
        }
      });
    });

    // Relocated event
    rendition.on('relocated', (location: any) => {
      if (isCancelled || !location || !location.start) return;
      const cfi = location.start.cfi;
      const progress = book.locations.percentageFromCfi(cfi);
      const total = book.locations.length() || totalPages || 100;
      const rawPage = book.locations.locationFromCfi(cfi);
      const page = typeof rawPage === 'number' ? rawPage : (Number(rawPage) || currentPage || 1);
      const percentage = Math.round((progress || 0) * 100);
      onPageChange(page, total, percentage);
    });

    return () => {
      isCancelled = true;
      try {
        rendition.destroy();
        book.destroy();
      } catch {
        // ignore
      }
    };
  }, [url]);

  // Update styles whenever settings change
  useEffect(() => {
    applyStyles();
  }, [applyStyles]);

  // Handle two-column spread layout toggle & resize
  useEffect(() => {
    if (renditionRef.current) {
      const isDual = settings.spreadMode === 'dual' || settings.isTwoColumn;
      renditionRef.current.spread(isDual ? 'always' : 'none');
      if (viewerRef.current) {
        renditionRef.current.resize(
          viewerRef.current.clientWidth || window.innerWidth,
          viewerRef.current.clientHeight || window.innerHeight
        );
      }
    }
  }, [settings.spreadMode, settings.isTwoColumn]);

  // Keyboard navigation
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'ArrowRight' || e.key === 'PageDown' || e.key === ' ') {
        renditionRef.current?.next();
      } else if (e.key === 'ArrowLeft' || e.key === 'PageUp') {
        renditionRef.current?.prev();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  const handlePrev = () => renditionRef.current?.prev();
  const handleNext = () => renditionRef.current?.next();

  if (error) {
    return (
      <div
        className="flex flex-col items-center justify-center h-full w-full p-6 text-center select-none"
        style={{
          backgroundColor: currentTheme.bg,
          color: currentTheme.text,
        }}
      >
        <div className="text-red-400 font-medium mb-2">Error loading EPUB</div>
        <div className="text-xs opacity-70 max-w-md">{error}</div>
      </div>
    );
  }

  return (
    <div
      className="flex-1 w-full h-full relative overflow-hidden flex flex-col select-text"
      style={{
        backgroundColor: currentTheme.bg,
        color: currentTheme.text,
      }}
    >
      {loading && (
        <div className="absolute inset-0 z-20 flex flex-col items-center justify-center space-y-3 bg-inherit">
          <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
          <span className="text-[13px] text-neutral-400 font-sans tracking-wide">
            Opening book…
          </span>
        </div>
      )}

      {/* Main EPUB Reader Viewport */}
      <div className="flex-1 w-full h-full relative flex items-center justify-center">
        <div ref={viewerRef} className="w-full h-full" />

        {/* Floating Side Prev/Next Arrows */}
        <button
          onClick={handlePrev}
          className="absolute left-3 top-1/2 -translate-y-1/2 p-2 rounded-full bg-black/30 hover:bg-black/60 text-white/60 hover:text-white transition-all opacity-0 hover:opacity-100 focus:opacity-100 z-10"
          title="Previous Page (Left Arrow)"
        >
          <ChevronLeft size={24} />
        </button>
        <button
          onClick={handleNext}
          className="absolute right-3 top-1/2 -translate-y-1/2 p-2 rounded-full bg-black/30 hover:bg-black/60 text-white/60 hover:text-white transition-all opacity-0 hover:opacity-100 focus:opacity-100 z-10"
          title="Next Page (Right Arrow)"
        >
          <ChevronRight size={24} />
        </button>
      </div>
    </div>
  );
};
