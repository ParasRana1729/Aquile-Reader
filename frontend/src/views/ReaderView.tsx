import React, { useState, useRef, useEffect, useCallback } from 'react';
import {
  ReaderSettings,
  DEFAULT_READER_SETTINGS,
  ReaderMode,
  TOCItem,
  Bookmark,
  Annotation,
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
  const effectiveTitle = book?.title || bookTitle;
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

  const [currentMode, setCurrentMode] = useState<ReaderMode>(initialMode);
  const [resolvedUrl, setResolvedUrl] = useState<string>('');
  const [isResolving, setIsResolving] = useState<boolean>(true);
  const blobUrlRef = useRef<string | null>(null);

  // Settings
  const [settings, setSettings] = useState<ReaderSettings>(() => {
    try {
      const saved = localStorage.getItem('aquile_reader_settings');
      if (saved) return { ...DEFAULT_READER_SETTINGS, ...JSON.parse(saved) };
    } catch {
      // ignore
    }
    return DEFAULT_READER_SETTINGS;
  });

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
  const initialPageVal = book?.percentage ? Math.max(1, Math.round((book.percentage / 100) * (book.pageCount || 100))) : 1;
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

  // Flush reading session on unmount or navigation back
  useEffect(() => {
    return () => {
      const duration = activeReadingSeconds - lastRecordedSecondsRef.current;
      if (duration > 5) {
        recordReadingSession({
          id: `sess-${Date.now()}`,
          bookId: effectiveId,
          startTime: sessionStartTimeRef.current,
          endTime: new Date().toISOString(),
          durationSeconds: duration,
          wordsRead: Math.max(20, wordsRead),
        });
      }
    };
  }, [effectiveId, activeReadingSeconds, wordsRead]);

  // Persist settings changes
  const handleUpdateSettings = (updates: Partial<ReaderSettings>) => {
    setSettings((prev) => {
      const next = { ...prev, ...updates };
      try {
        localStorage.setItem('aquile_reader_settings', JSON.stringify(next));
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

  // ReadAloud TTS Implementation
  const handleToggleReadAloud = () => {
    if (!('speechSynthesis' in window)) {
      alert('Speech synthesis is not supported in this browser.');
      return;
    }

    if (isReadingAloud) {
      window.speechSynthesis.cancel();
      setIsReadingAloud(false);
    } else {
      const textToRead =
        window.getSelection()?.toString().trim() ||
        `${effectiveTitle}. Reading page ${currentPage} of ${totalPages}.`;

      const utterance = new SpeechSynthesisUtterance(textToRead);
      utterance.rate = 1.0;
      utterance.pitch = 1.0;
      utterance.onend = () => setIsReadingAloud(false);
      utterance.onerror = () => setIsReadingAloud(false);

      window.speechSynthesis.speak(utterance);
      setIsReadingAloud(true);
    }
  };

  const handleSpeakText = (text: string) => {
    if (!('speechSynthesis' in window)) return;
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.onend = () => setIsReadingAloud(false);
    utterance.onerror = () => setIsReadingAloud(false);
    window.speechSynthesis.speak(utterance);
    setIsReadingAloud(true);
  };

  useEffect(() => {
    return () => {
      if ('speechSynthesis' in window) {
        window.speechSynthesis.cancel();
      }
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

  // Navigate to page / chapter
  const handleNavigateToPage = (pageNum: number) => {
    if (jumpToPageRef.current) {
      jumpToPageRef.current(pageNum);
    }
  };

  return (
    <div className="flex flex-col h-full w-full relative overflow-hidden select-text">
      {/* Top Floating Overlay Toolbar */}
      <FloatingToolbar
        bookTitle={effectiveTitle}
        settings={settings}
        onUpdateSettings={handleUpdateSettings}
        onBack={onBack}
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
        currentMode={currentMode}
        onChangeMode={(m) => setCurrentMode(m)}
        currentPage={currentPage}
        totalPages={totalPages}
        readingSpeedWpm={readingSpeedWpm}
      />

      {/* Main Reader Content Area */}
      <main className="flex-1 w-full h-full relative overflow-hidden flex flex-col">
        {isResolving ? (
          <div className="flex flex-col items-center justify-center h-full w-full space-y-3">
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
    </div>
  );
};

export default ReaderView;
