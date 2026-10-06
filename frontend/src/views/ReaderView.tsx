import React, { useState, useRef, useEffect, useCallback } from 'react';
import {
  ReaderSettings,
  DEFAULT_READER_SETTINGS,
  ReaderMode,
  TOCItem,
  Bookmark,
  Annotation,
  READER_THEMES,
} from '../types/reader';
import { BookWithProgress } from '../types/book';
import {
  FloatingToolbar,
  ReadingSanctum,
  PdfViewer,
  EpubViewer,
  ComicViewer,
  TOCDrawer,
  BookmarksDrawer,
  AnnotationsDrawer,
  SearchOverlay,
  TTSBar,
  useReadingSession,
} from '../components/reader';
import {
  resolveBookContent,
  updateProgress as ipcUpdateProgress,
  fetchBookmarks,
  saveBookmark,
  removeBookmark,
  fetchAnnotations,
  saveAnnotation,
  removeAnnotation,
  recordReadingSession,
} from '../utils/ipc';
import { ttsEngine } from '../utils/tts';
import { PdfSearchResult } from '../components/reader/PdfViewer';
import { EpubSearchResult } from '../components/reader/EpubViewer';

interface ReaderViewProps {
  bookTitle?: string;
  bookId?: string;
  bookFormat?: 'PDF' | 'EPUB' | 'COMIC' | 'TEXT';
  bookPath?: string;
  book?: BookWithProgress | null;
  onBack: () => void;
}

interface GenericSearchResult {
  page?: number;
  cfi?: string;
  excerpt: string;
}

export const ReaderView: React.FC<ReaderViewProps> = ({
  bookTitle = 'The Prince',
  bookId = 'book-the-prince',
  bookFormat = 'PDF',
  bookPath = '',
  book = null,
  onBack,
}) => {
  // Determine title and format from book prop if provided
  const effectiveTitle = (book?.title || bookTitle || '').replace(/[\uFFFD\0]/g, '').trim() || 'Book';
  const effectiveId = book?.id || bookId;
  const rawFormat = (book?.format || bookFormat).toUpperCase();
  const effectivePath = book?.filePath || bookPath;

  // Determine initial mode based on book format
  const initialMode: ReaderMode =
    rawFormat === 'EPUB'
      ? 'epub'
      : rawFormat === 'COMIC' || rawFormat === 'CBZ' || rawFormat === 'CBR'
      ? 'comic'
      : rawFormat === 'TEXT'
      ? 'sanctum'
      : 'pdf';

  const currentMode: ReaderMode = initialMode;
  const [resolvedUrl, setResolvedUrl] = useState<string>('');
  const [isResolving, setIsResolving] = useState<boolean>(true);
  const blobUrlRef = useRef<string | null>(null);

  // Settings & Appearance state management with localStorage persistence (per-book and global fallback)
  const [settings, setSettings] = useState<ReaderSettings>(() => {
    try {
      const bookSpecificKey = effectiveId ? `aquile_reader_settings_${effectiveId}` : null;
      const saved = (bookSpecificKey && localStorage.getItem(bookSpecificKey)) || localStorage.getItem('aquile_reader_settings');
      if (saved) {
        const parsed = JSON.parse(saved);
        // Normalize margin if string
        let marginVal = parsed.margin;
        if (typeof marginVal !== 'number') {
          marginVal = marginVal === 'compact' ? 20 : marginVal === 'wide' ? 64 : 36;
        }
        const spreadMode = parsed.spreadMode || (parsed.isTwoColumn ? 'dual' : 'single');
        const isTwoColumn = spreadMode === 'dual' || !!parsed.isTwoColumn;

        return {
          ...DEFAULT_READER_SETTINGS,
          ...parsed,
          margin: marginVal,
          spreadMode,
          isTwoColumn,
        };
      }
    } catch {
      // ignore
    }
    return DEFAULT_READER_SETTINGS;
  });

  const currentTheme = READER_THEMES[settings.theme] || READER_THEMES.night;

  // Table of Contents
  const [toc, setToc] = useState<TOCItem[]>([
    { id: 'ch-dedication', label: 'Dedication to Lorenzo De’ Medici', page: 22 },
    { id: 'ch-1', label: 'Chapter I. How Many Kinds of Principalities', page: 23 },
    { id: 'ch-2', label: 'Chapter II. Concerning Hereditary Principalities', page: 24 },
    { id: 'ch-3', label: 'Chapter III. Concerning Mixed Principalities', page: 26 },
    { id: 'ch-4', label: 'Chapter IV. Why Darius’ Kingdom Did Not Rebel', page: 28 },
    { id: 'ch-5', label: 'Chapter V. Governing Cities Accustomed to Freedom', page: 32 },
  ]);

  // Bookmarks & Annotations
  const [bookmarks, setBookmarks] = useState<Bookmark[]>([]);
  const [annotations, setAnnotations] = useState<Annotation[]>([]);

  // Drawer / Overlay Open States
  const [isTOCOpen, setIsTOCOpen] = useState(false);
  const [isBookmarksOpen, setIsBookmarksOpen] = useState(false);
  const [isAnnotationsOpen, setIsAnnotationsOpen] = useState(false);
  const [isSearchOpen, setIsSearchOpen] = useState(false);

  // Search Results State
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<GenericSearchResult[]>([]);
  const [matchIndex, setMatchIndex] = useState(0);

  // ReadAloud TTS State
  const [isReadingAloud, setIsReadingAloud] = useState(false);

  // Engine refs
  const jumpToPageRef = useRef<((page: number) => void) | null>(null);
  const pdfSearchRef = useRef<((query: string) => Promise<PdfSearchResult[]>) | null>(null);
  const epubSearchRef = useRef<((query: string) => Promise<EpubSearchResult[]>) | null>(null);
  const epubNavigateRef = useRef<((target: string | number) => void) | null>(null);

  // Session start time for tracking
  const sessionStartTimeRef = useRef<string>(new Date().toISOString());
  const lastRecordedSecondsRef = useRef<number>(0);

  // Synchronized state references for TTS callbacks
  const isReadingAloudRef = useRef(isReadingAloud);
  useEffect(() => {
    isReadingAloudRef.current = isReadingAloud;
  }, [isReadingAloud]);

  const currentModeRef = useRef(currentMode);
  useEffect(() => {
    currentModeRef.current = currentMode;
  }, [currentMode]);

  // Resolve binary content / blob URL
  useEffect(() => {
    let isCancelled = false;
    setIsResolving(true);

    resolveBookContent({
      id: effectiveId,
      filePath: effectivePath,
      format: rawFormat.toLowerCase(),
    }).then((url) => {
      if (isCancelled) return;
      if (blobUrlRef.current && blobUrlRef.current.startsWith('blob:')) {
        URL.revokeObjectURL(blobUrlRef.current);
      }
      blobUrlRef.current = url.startsWith('blob:') ? url : null;
      setResolvedUrl(url);
      setIsResolving(false);
    });

    return () => {
      isCancelled = true;
      if (blobUrlRef.current && blobUrlRef.current.startsWith('blob:')) {
        URL.revokeObjectURL(blobUrlRef.current);
        blobUrlRef.current = null;
      }
    };
  }, [effectiveId, effectivePath, rawFormat]);

  // Load Bookmarks & Annotations from SQLite
  useEffect(() => {
    let isMounted = true;
    fetchBookmarks(effectiveId).then((bms) => {
      if (isMounted) setBookmarks(bms);
    });
    fetchAnnotations(effectiveId).then((anns) => {
      if (isMounted) setAnnotations(anns);
    });
    return () => {
      isMounted = false;
    };
  }, [effectiveId]);

  // Reading Session Tracking
  let initialPageVal = 1;
  if (book?.position) {
    try {
      const parsedPos = JSON.parse(book.position);
      if (typeof parsedPos.page === 'number' && parsedPos.page > 0) {
        initialPageVal = parsedPos.page;
      }
    } catch {}
  }
  if (initialPageVal === 1 && book?.percentage && book.pageCount) {
    initialPageVal = Math.max(1, Math.round((book.percentage / 100) * book.pageCount));
  }
  const initialTotalPagesVal = book?.pageCount || (effectiveId.includes('prince') ? 140 : 200);

  const {
    currentPage,
    totalPages,
    readingSpeedWpm,
    activeReadingSeconds,
    wordsRead,
    updateProgress,
  } = useReadingSession({
    bookId: effectiveId,
    initialPage: initialPageVal,
    initialTotalPages: initialTotalPagesVal,
    totalWordsEstimate: book ? Math.max(5000, book.pageCount * 250) : 40000,
    onCheckpoint: (stats) => {
      ipcUpdateProgress(
        effectiveId,
        stats.progressPercentage,
        JSON.stringify({ page: stats.currentPage })
      );
    },
  });

  const currentPageRef = useRef(currentPage);
  useEffect(() => {
    currentPageRef.current = currentPage;
  }, [currentPage]);

  const totalPagesRef = useRef(totalPages);
  useEffect(() => {
    totalPagesRef.current = totalPages;
  }, [totalPages]);

  // Flush reading session and progress on unmount or navigation back
  useEffect(() => {
    return () => {
      const page = currentPageRef.current;
      const total = totalPagesRef.current;
      const pct = total > 0 ? Math.min(100, Math.max(0, Math.round((page / total) * 100))) : 0;
      ipcUpdateProgress(
        effectiveId,
        pct,
        JSON.stringify({ page })
      ).catch(() => {});

      const duration = activeReadingSeconds - lastRecordedSecondsRef.current;
      if (duration > 5) {
        recordReadingSession({
          id: `sess-${Date.now()}`,
          bookId: effectiveId,
          startTime: sessionStartTimeRef.current,
          endTime: new Date().toISOString(),
          durationSeconds: duration,
          wordsRead: Math.max(20, wordsRead),
        }).catch(() => {});
      }
    };
  }, [effectiveId, activeReadingSeconds, wordsRead]);

  // Persist settings & appearance changes
  const handleUpdateSettings = (updates: Partial<ReaderSettings>) => {
    setSettings((prev) => {
      const synched = { ...updates };
      if (updates.spreadMode !== undefined && updates.isTwoColumn === undefined) {
        synched.isTwoColumn = updates.spreadMode === 'dual';
      } else if (updates.isTwoColumn !== undefined && updates.spreadMode === undefined) {
        synched.spreadMode = updates.isTwoColumn ? 'dual' : 'single';
      }

      const next = { ...prev, ...synched };
      try {
        localStorage.setItem('aquile_reader_settings', JSON.stringify(next));
        if (effectiveId) {
          localStorage.setItem(`aquile_reader_settings_${effectiveId}`, JSON.stringify(next));
        }
      } catch {
        // ignore
      }
      return next;
    });
  };

  // Zoom handlers
  const handleZoomIn = () => {
    if (currentMode === 'sanctum') {
      handleUpdateSettings({ fontSize: Math.min(36, settings.fontSize + 1) });
    } else {
      handleUpdateSettings({ zoom: Math.min(2.5, +(settings.zoom + 0.15).toFixed(2)) });
    }
  };

  const handleZoomOut = () => {
    if (currentMode === 'sanctum') {
      handleUpdateSettings({ fontSize: Math.max(12, settings.fontSize - 1) });
    } else {
      handleUpdateSettings({ zoom: Math.max(0.6, +(settings.zoom - 0.15).toFixed(2)) });
    }
  };

  /**
   * Extract readable text of the current page / active spine item across engines
   */
  const extractCurrentPageText = useCallback(
    (pageNum: number, mode?: ReaderMode): string => {
      // 1. User manual selection has highest priority
      const selection = window.getSelection()?.toString().trim();
      if (selection) return selection;

      const activeMode = mode || currentModeRef.current;

      // 2. Sanctum Mode
      if (activeMode === 'sanctum') {
        const pageEl = document.querySelector(`article[data-page-number="${pageNum}"]`);
        if (pageEl) {
          const paragraphs = Array.from(pageEl.querySelectorAll('p'))
            .map((p) => p.textContent?.trim() || '')
            .filter(Boolean);
          if (paragraphs.length > 0) return paragraphs.join('\n\n');
          if (pageEl.textContent?.trim()) return pageEl.textContent.trim();
        }
        // Fallback to any article or sanctum page
        const anyArticle = document.querySelector('article');
        if (anyArticle?.textContent?.trim()) {
          return anyArticle.textContent.trim();
        }
      }

      // 3. PDF Mode
      if (activeMode === 'pdf') {
        const pageEl = document.querySelector(`div[data-page-number="${pageNum}"]`);
        if (pageEl) {
          const textLayer = pageEl.querySelector('.textLayer');
          const text = textLayer?.textContent?.trim() || pageEl.textContent?.trim();
          if (text) return text;
        }
      }

      // 4. EPUB Mode
      if (activeMode === 'epub') {
        const iframe = document.querySelector('iframe');
        if (iframe?.contentDocument?.body) {
          const iframeSelection = iframe.contentDocument.getSelection()?.toString().trim();
          if (iframeSelection) return iframeSelection;
          const bodyText =
            iframe.contentDocument.body.innerText?.trim() ||
            iframe.contentDocument.body.textContent?.trim();
          if (bodyText) return bodyText;
        }
      }

      // 5. Generic viewport fallback
      const mainEl = document.querySelector('main');
      if (mainEl?.innerText?.trim()) {
        const text = mainEl.innerText.trim();
        if (text.length > 20) return text;
      }

      return `${effectiveTitle}. Reading page ${pageNum} of ${totalPagesRef.current}.`;
    },
    [effectiveTitle]
  );

  // Auto-advance page when TTS narration finishes
  useEffect(() => {
    const unsubscribe = ttsEngine.onEnd(() => {
      if (!isReadingAloudRef.current) return;

      const cur = currentPageRef.current;
      const tot = totalPagesRef.current;
      const mode = currentModeRef.current;

      if (cur < tot) {
        const nextPage = cur + 1;

        if (mode === 'sanctum' || mode === 'pdf' || mode === 'comic') {
          if (jumpToPageRef.current) {
            jumpToPageRef.current(nextPage);
          }
          updateProgress(nextPage, tot);
        } else if (mode === 'epub') {
          if (epubNavigateRef.current) {
            epubNavigateRef.current('next');
          }
        }

        // Wait for page rendering to complete, then read the next page
        setTimeout(() => {
          if (isReadingAloudRef.current) {
            const nextText = extractCurrentPageText(nextPage, mode);
            ttsEngine.play(nextText);
          }
        }, 500);
      } else {
        // Reached the end of book
        setIsReadingAloud(false);
        ttsEngine.stop();
      }
    });

    return () => {
      unsubscribe();
    };
  }, [updateProgress, extractCurrentPageText]);

  // ReadAloud TTS Toggle
  const handleToggleReadAloud = () => {
    if (isReadingAloud) {
      ttsEngine.stop();
      setIsReadingAloud(false);
    } else {
      setIsReadingAloud(true);
      const text = extractCurrentPageText(currentPage);
      ttsEngine.play(text);
    }
  };

  const handleSpeakText = (text: string) => {
    setIsReadingAloud(true);
    ttsEngine.play(text);
  };

  // Ensure TTS is stopped on unmount
  useEffect(() => {
    return () => {
      ttsEngine.stop();
    };
  }, []);

  // Bookmark actions
  const handleAddBookmark = () => {
    const newBm: Bookmark = {
      id: `bm-${Date.now()}`,
      bookId: effectiveId,
      page: currentPage,
      title: `Page ${currentPage}`,
      createdAt: Date.now(),
      excerpt: `Bookmark at page ${currentPage} of ${effectiveTitle}`,
    };
    setBookmarks((prev) => [newBm, ...prev]);
    saveBookmark(newBm);
  };

  const handleRemoveBookmark = (id: string) => {
    setBookmarks((prev) => prev.filter((b) => b.id !== id));
    removeBookmark(id);
  };

  // Annotation actions
  const handleAddAnnotation = (ann: Omit<Annotation, 'id' | 'createdAt'>) => {
    const newAnn: Annotation = {
      ...ann,
      id: `ann-${Date.now()}`,
      bookId: effectiveId,
      createdAt: Date.now(),
    };
    setAnnotations((prev) => [newAnn, ...prev]);
    saveAnnotation(newAnn);
  };

  const handleRemoveAnnotation = (id: string) => {
    setAnnotations((prev) => prev.filter((a) => a.id !== id));
    removeAnnotation(id);
  };

  // Search actions
  const handleSearch = (query: string): number => {
    setSearchQuery(query);
    if (!query.trim()) {
      setSearchResults([]);
      setMatchIndex(0);
      return 0;
    }

    if (currentMode === 'pdf' && pdfSearchRef.current) {
      pdfSearchRef.current(query).then((matches) => {
        setSearchResults(matches);
        setMatchIndex(0);
        if (matches.length > 0 && jumpToPageRef.current) {
          jumpToPageRef.current(matches[0].page);
        }
      });
      return 1;
    }

    if (currentMode === 'epub' && epubSearchRef.current) {
      epubSearchRef.current(query).then((matches) => {
        setSearchResults(matches);
        setMatchIndex(0);
        if (matches.length > 0 && matches[0].cfi && epubNavigateRef.current) {
          epubNavigateRef.current(matches[0].cfi);
        }
      });
      return 1;
    }

    return 0;
  };

  const handleNextMatch = () => {
    if (searchResults.length === 0) return;
    const nextIdx = (matchIndex + 1) % searchResults.length;
    setMatchIndex(nextIdx);
    const match = searchResults[nextIdx];
    if (match.page && jumpToPageRef.current) {
      jumpToPageRef.current(match.page);
    } else if (match.cfi && epubNavigateRef.current) {
      epubNavigateRef.current(match.cfi);
    }
  };

  const handlePrevMatch = () => {
    if (searchResults.length === 0) return;
    const prevIdx = (matchIndex - 1 + searchResults.length) % searchResults.length;
    setMatchIndex(prevIdx);
    const match = searchResults[prevIdx];
    if (match.page && jumpToPageRef.current) {
      jumpToPageRef.current(match.page);
    } else if (match.cfi && epubNavigateRef.current) {
      epubNavigateRef.current(match.cfi);
    }
  };

  // Save progress immediately on back button
  const handleExitReader = useCallback(async () => {
    const page = currentPageRef.current;
    const total = totalPagesRef.current;
    const pct = total > 0 ? Math.min(100, Math.max(0, Math.round((page / total) * 100))) : 0;
    try {
      await ipcUpdateProgress(
        effectiveId,
        pct,
        JSON.stringify({ page })
      );
    } catch {}

    if (onBack) {
      onBack();
    }
  }, [effectiveId, onBack]);

  // Navigate to page / chapter
  const handleNavigateToPage = (pageNum: number) => {
    if (jumpToPageRef.current) {
      jumpToPageRef.current(pageNum);
    }
  };

  return (
    <div
      className="flex flex-col h-full w-full relative overflow-hidden select-text"
      style={{
        backgroundColor: currentTheme.bg,
        color: currentTheme.text,
      }}
    >
      {/* Top Persistent Toolbar */}
      <FloatingToolbar
        bookTitle={effectiveTitle}
        settings={settings}
        onUpdateSettings={handleUpdateSettings}
        onBack={handleExitReader}
        onToggleTOC={() => {
          setIsTOCOpen(!isTOCOpen);
          setIsBookmarksOpen(false);
          setIsAnnotationsOpen(false);
        }}
        onToggleBookmarks={() => {
          setIsBookmarksOpen(!isBookmarksOpen);
          setIsTOCOpen(false);
          setIsAnnotationsOpen(false);
        }}
        onToggleAnnotations={() => {
          setIsAnnotationsOpen(!isAnnotationsOpen);
          setIsTOCOpen(false);
          setIsBookmarksOpen(false);
        }}
        onToggleSearch={() => setIsSearchOpen(!isSearchOpen)}
        isTOCOpen={isTOCOpen}
        isBookmarksOpen={isBookmarksOpen}
        isAnnotationsOpen={isAnnotationsOpen}
        isSearchOpen={isSearchOpen}
        onToggleReadAloud={handleToggleReadAloud}
        isReadingAloud={isReadingAloud}
        onZoomIn={handleZoomIn}
        onZoomOut={handleZoomOut}

        currentPage={currentPage}
        totalPages={totalPages}
      />

      {/* Main Reader Content Area */}
      <main
        className="flex-1 w-full min-h-0 relative overflow-hidden flex flex-col"
        style={{
          backgroundColor: currentTheme.bg,
          color: currentTheme.text,
        }}
      >
        {isResolving ? (
          <div
            className="flex-1 w-full h-full flex flex-col items-center justify-center space-y-3"
            style={{
              backgroundColor: currentTheme.bg,
            }}
          >
            <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
            <span className="text-xs text-neutral-400 font-sans tracking-wide">
              Opening {effectiveTitle}...
            </span>
          </div>
        ) : (
          <>
            {currentMode === 'sanctum' && (
              <ReadingSanctum
                bookTitle={effectiveTitle}
                settings={settings}
                currentPage={currentPage}
                totalPages={totalPages}
                onPageChange={updateProgress}
                onAddAnnotation={handleAddAnnotation}
                onJumpToPageRef={jumpToPageRef}
                searchQuery={searchQuery}
                onSpeakText={handleSpeakText}
              />
            )}

            {currentMode === 'pdf' && (
              <PdfViewer
                url={resolvedUrl}
                settings={settings}
                currentPage={currentPage}
                onPageChange={updateProgress}
                onJumpToPageRef={jumpToPageRef}
                onSearchRef={pdfSearchRef}
                searchQuery={searchQuery}
              />
            )}

            {currentMode === 'epub' && (
              <EpubViewer
                url={resolvedUrl}
                settings={settings}
                currentPage={currentPage}
                totalPages={totalPages}
                onPageChange={updateProgress}
                onLoadTOC={(loadedToc) => setToc(loadedToc)}
                onNavigateRef={epubNavigateRef}
                onSearchRef={epubSearchRef}
              />
            )}

            {currentMode === 'comic' && (
              <ComicViewer
                url={resolvedUrl}
                settings={settings}
                currentPage={currentPage}
                onPageChange={updateProgress}
                onJumpToPageRef={jumpToPageRef}
              />
            )}
          </>
        )}
      </main>

      {/* Drawers */}
      <TOCDrawer
        isOpen={isTOCOpen}
        onClose={() => setIsTOCOpen(false)}
        toc={toc}
        currentPage={currentPage}
        onNavigate={(item) => {
          if (item.page !== undefined) {
            handleNavigateToPage(item.page);
          } else if (item.href && epubNavigateRef.current) {
            epubNavigateRef.current(item.href);
          }
        }}
        theme={settings.theme}
      />

      <BookmarksDrawer
        isOpen={isBookmarksOpen}
        onClose={() => setIsBookmarksOpen(false)}
        bookmarks={bookmarks}
        currentPage={currentPage}
        onNavigateToPage={handleNavigateToPage}
        onAddBookmark={handleAddBookmark}
        onRemoveBookmark={handleRemoveBookmark}
        theme={settings.theme}
      />

      <AnnotationsDrawer
        isOpen={isAnnotationsOpen}
        onClose={() => setIsAnnotationsOpen(false)}
        annotations={annotations}
        currentPage={currentPage}
        onNavigateToPage={handleNavigateToPage}
        onAddAnnotation={handleAddAnnotation}
        onRemoveAnnotation={handleRemoveAnnotation}
        theme={settings.theme}
      />

      {/* Search Overlay */}
      <SearchOverlay
        isOpen={isSearchOpen}
        onClose={() => setIsSearchOpen(false)}
        onSearch={handleSearch}
        onNextMatch={handleNextMatch}
        onPrevMatch={handlePrevMatch}
        matchIndex={matchIndex}
        matchCount={searchResults.length}
      />

      {/* Sleek Floating Text-To-Speech Bar */}
      <TTSBar
        isOpen={isReadingAloud}
        onClose={() => {
          setIsReadingAloud(false);
          ttsEngine.stop();
        }}
        currentPage={currentPage}
        totalPages={totalPages}
        theme={settings.theme}
        onPlayRequest={() => {
          const text = extractCurrentPageText(currentPage);
          ttsEngine.play(text);
        }}
      />
    </div>
  );
};

export default ReaderView;
