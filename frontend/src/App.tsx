import React, { useState, useEffect, useRef } from 'react';
import { ThemeProvider, useTheme } from './context/ThemeContext';
import { TitleBar } from './components/TitleBar';
import { NavigationRail, NavView } from './components/NavigationRail';
import { AcrylicCanvas } from './components/AcrylicCanvas';
import { HomeView } from './views/HomeView';
import { LibraryView } from './views/LibraryView';
import { AnnotationsView } from './views/AnnotationsView';
import { CatalogsView } from './views/CatalogsView';
import { SettingsView } from './views/SettingsView';
import { InsightsView } from './views/InsightsView';
import { ReaderView } from './views/ReaderView';
import { fetchBooks, importMultipleBooks } from './utils/ipc';
import { ensureBookCover } from './utils/pdfThumbnail';
import { BookWithProgress } from './types/book';
import { FolderDown, CheckCircle2, X } from 'lucide-react';

const MainShell: React.FC = () => {
  const { currentTheme } = useTheme();
  const [currentView, setCurrentView] = useState<NavView>('home');
  const [isReading, setIsReading] = useState(false);
  const [currentBook, setCurrentBook] = useState<BookWithProgress | null>(null);
  const [currentBookTitle, setCurrentBookTitle] = useState('The Prince');
  const [currentBookId, setCurrentBookId] = useState('book-the-prince');
  const [currentBookFormat, setCurrentBookFormat] = useState<'PDF' | 'EPUB' | 'COMIC' | 'TEXT'>('PDF');

  // Drag-and-drop state & Library refresh key
  const [isDragging, setIsDragging] = useState(false);
  const [libraryRefreshKey, setLibraryRefreshKey] = useState(0);
  const [notification, setNotification] = useState<string | null>(null);
  const dragCounter = useRef(0);
  const notificationTimeoutRef = useRef<number | null>(null);

  const showNotification = (msg: string) => {
    setNotification(msg);
    if (notificationTimeoutRef.current) {
      window.clearTimeout(notificationTimeoutRef.current);
    }
    notificationTimeoutRef.current = window.setTimeout(() => {
      setNotification(null);
    }, 4000);
  };

  const handleOpenBook = (bookId: string, bookObj?: BookWithProgress) => {
    setCurrentBookId(bookId);

    const applyBook = (b: BookWithProgress) => {
      setCurrentBook(b);
      setCurrentBookTitle(b.title);
      const fmt = (b.format || '').toUpperCase();
      if (fmt === 'EPUB') setCurrentBookFormat('EPUB');
      else if (fmt === 'CBZ' || fmt === 'CBR' || fmt === 'COMIC') setCurrentBookFormat('COMIC');
      else setCurrentBookFormat('PDF');
    };

    if (bookObj) {
      applyBook(bookObj);
      setIsReading(true);
      return;
    }

    // Set fallback title immediately so transition is instant
    if (bookId.includes('the-prince')) {
      setCurrentBookTitle('The Prince');
      setCurrentBookFormat('PDF');
    } else if (bookId.includes('mans-search')) {
      setCurrentBookTitle("Man's Search For Meaning");
      setCurrentBookFormat('EPUB');
    } else if (bookId.includes('sherlock-holmes')) {
      setCurrentBookTitle('The Adventures of Sherlock Holmes');
      setCurrentBookFormat('EPUB');
    } else if (bookId.includes('quick-start')) {
      setCurrentBookTitle('Quick Start Guide');
      setCurrentBookFormat('EPUB');
    } else if (bookId.includes('comic')) {
      setCurrentBookTitle('Sample Comic Book');
      setCurrentBookFormat('COMIC');
    } else {
      setCurrentBookTitle('Book Title');
      setCurrentBookFormat('PDF');
    }
    setIsReading(true);

    fetchBooks().then((books) => {
      const found = books.find((b) => b.id === bookId);
      if (found) {
        applyBook(found);
      }
    }).catch(() => {});
  };

  const handleBack = () => {
    if (isReading) {
      setIsReading(false);
    } else if (currentView !== 'home') {
      setCurrentView('home');
    }
  };

  // Drag and drop processing helper
  const processImportedPaths = async (paths: string[]) => {
    const validExtensions = ['.epub', '.pdf', '.cbz', '.cbr'];
    const validPaths = paths.filter((p) => {
      const lower = p.toLowerCase();
      return validExtensions.some((ext) => lower.endsWith(ext));
    });

    if (validPaths.length > 0) {
      try {
        const imported = await importMultipleBooks(validPaths);
        imported.forEach((book) => {
          if ((book.format || '').toLowerCase() === 'pdf') {
            ensureBookCover(book, () => {
              setLibraryRefreshKey((prev) => prev + 1);
            });
          }
        });
        setLibraryRefreshKey((prev) => prev + 1);
        if (currentView !== 'library') {
          setCurrentView('library');
        }
        showNotification(
          `Imported ${imported.length} book${imported.length === 1 ? '' : 's'} successfully`
        );
      } catch (err) {
        console.error('Drag drop book import error:', err);
      }
    }
  };

  // Global HTML5 Drag & Drop listeners
  useEffect(() => {
    const handleDragEnter = (e: DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      dragCounter.current += 1;
      if (e.dataTransfer && e.dataTransfer.types.includes('Files')) {
        setIsDragging(true);
      }
    };

    const handleDragOver = (e: DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      if (e.dataTransfer) {
        e.dataTransfer.dropEffect = 'copy';
      }
      if (!isDragging) {
        setIsDragging(true);
      }
    };

    const handleDragLeave = (e: DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      dragCounter.current -= 1;
      if (dragCounter.current <= 0) {
        dragCounter.current = 0;
        setIsDragging(false);
      }
    };

    const handleDrop = async (e: DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      dragCounter.current = 0;
      setIsDragging(false);

      const files = Array.from(e.dataTransfer?.files || []);
      const paths = files.map((f) => (f as any).path || f.name).filter(Boolean);
      await processImportedPaths(paths);
    };

    window.addEventListener('dragenter', handleDragEnter);
    window.addEventListener('dragover', handleDragOver);
    window.addEventListener('dragleave', handleDragLeave);
    window.addEventListener('drop', handleDrop);

    return () => {
      window.removeEventListener('dragenter', handleDragEnter);
      window.removeEventListener('dragover', handleDragOver);
      window.removeEventListener('dragleave', handleDragLeave);
      window.removeEventListener('drop', handleDrop);
    };
  }, [isDragging, currentView]);

  // Tauri Native Drag-and-Drop listener (if available)
  useEffect(() => {
    let unlistenDrop: (() => void) | undefined;
    let unlistenEnter: (() => void) | undefined;
    let unlistenLeave: (() => void) | undefined;

    const setupTauriListener = async () => {
      try {
        const { listen, TauriEvent } = await import('@tauri-apps/api/event');
        unlistenEnter = await listen(TauriEvent.DRAG_ENTER, () => {
          setIsDragging(true);
        });
        unlistenLeave = await listen(TauriEvent.DRAG_LEAVE, () => {
          setIsDragging(false);
        });
        unlistenDrop = await listen<any>(TauriEvent.DRAG_DROP, async (event) => {
          setIsDragging(false);
          const rawPaths: string[] = event.payload?.paths || [];
          await processImportedPaths(rawPaths);
        });
      } catch {
        // Ignored outside Tauri
      }
    };

    setupTauriListener();

    return () => {
      unlistenEnter?.();
      unlistenLeave?.();
      unlistenDrop?.();
    };
  }, [currentView]);

  // Determine Titlebar text and back button status matching Windows B0
  let titleBarText = 'Aquile Reader';
  let showBack = false;
  const cleanBookTitle = (currentBookTitle || '').replace(/[\uFFFD\0]/g, '').trim();

  if (isReading) {
    titleBarText = `${cleanBookTitle || 'Book'} - Aquile Reader`;
    // In reading mode, ReaderView's FloatingToolbar provides the dedicated "Return to Library" back button.
    // Suppressing showBack on TitleBar prevents double back arrows from being stacked together.
    showBack = false;
  } else if (currentView !== 'home') {
    titleBarText = 'Aquile Reader';
    showBack = true;
  }

  return (
    <div className="flex flex-col h-screen w-screen overflow-hidden select-none font-sans relative bg-[#1f1f1f]">
      {/* Dynamic TitleBar */}
      <TitleBar
        title={titleBarText}
        showBack={showBack}
        onBack={handleBack}
      />

      {/* Main Client Area */}
      <div className="flex-1 flex overflow-hidden relative">
        {isReading ? (
          <ReaderView
            book={currentBook}
            bookTitle={currentBookTitle}
            bookId={currentBookId}
            bookFormat={currentBookFormat}
            bookPath={currentBook?.filePath}
            onBack={() => setIsReading(false)}
          />
        ) : (
          <AcrylicCanvas>
            <div className="flex h-full w-full overflow-hidden">
              {/* Left Navigation Rail (52px) */}
              <NavigationRail
                currentView={currentView}
                onSelectView={(v) => setCurrentView(v)}
              />

              {/* View Router */}
              <main className="flex-1 h-full overflow-hidden relative">
                {currentView === 'home' && (
                  <HomeView
                    key={libraryRefreshKey}
                    onOpenBook={handleOpenBook}
                    onOpenLibrary={() => setCurrentView('library')}
                  />
                )}
                {currentView === 'library' && (
                  <LibraryView
                    key={libraryRefreshKey}
                    onOpenBook={handleOpenBook}
                  />
                )}
                {currentView === 'catalogs' && <CatalogsView />}
                {currentView === 'annotations' && <AnnotationsView />}
                {currentView === 'insights' && <InsightsView />}
                {currentView === 'settings' && <SettingsView />}
              </main>
            </div>
          </AcrylicCanvas>
        )}
      </div>

      {/* Global Drag-and-Drop Active Overlay matching Fluent UI */}
      {isDragging && (
        <div className="absolute inset-0 z-50 bg-[#0078d4]/20 backdrop-blur-md border-2 border-dashed border-[#0078d4] flex flex-col items-center justify-center pointer-events-none transition-all duration-200">
          <div className="p-6 bg-[#1f1f1f]/90 rounded-2xl shadow-2xl border border-white/10 flex flex-col items-center gap-3">
            <FolderDown className="w-12 h-12 text-[#0078d4] animate-bounce" />
            <h3 className="text-base font-semibold text-white">Drop Books to Import</h3>
            <p className="text-xs text-neutral-400">Supports EPUB, PDF, CBZ, and CBR files</p>
          </div>
        </div>
      )}

      {/* Floating Status Notification Toast */}
      {notification && (
        <div className="fixed bottom-6 right-6 z-50 flex items-center gap-3 px-4 py-2.5 rounded-lg bg-[#2b2b2b] text-white border border-white/10 shadow-2xl text-xs font-medium animate-in slide-in-from-bottom-3 duration-200">
          <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
          <span>{notification}</span>
          <button
            onClick={() => setNotification(null)}
            className="ml-2 text-neutral-400 hover:text-white transition-colors"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}
    </div>
  );
};

export default function App() {
  return (
    <ThemeProvider>
      <MainShell />
    </ThemeProvider>
  );
}
