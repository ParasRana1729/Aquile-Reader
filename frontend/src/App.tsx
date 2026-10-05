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

  const handleOpenBook = async (bookId: string) => {
    setCurrentBookId(bookId);
    let book: BookWithProgress | undefined;
    try {
      const books = await fetchBooks();
      book = books.find((b) => b.id === bookId);
    } catch {
      // ignore
    }

    if (book) {
      setCurrentBook(book);
      setCurrentBookTitle(book.title);
      const fmt = (book.format || '').toUpperCase();
      if (fmt === 'EPUB') setCurrentBookFormat('EPUB');
      else if (fmt === 'CBZ' || fmt === 'CBR' || fmt === 'COMIC') setCurrentBookFormat('COMIC');
      else setCurrentBookFormat('PDF');
    } else {
      setCurrentBook(null);
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
    }
    setIsReading(true);
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

  if (isReading) {
    titleBarText = `${currentBookTitle} - Aquile Reader`;
    showBack = true;
  } else if (currentView !== 'home') {
    titleBarText = 'Aquile Reader';
    showBack = true;
  }

  return (
    <div className="flex flex-col h-screen w-screen overflow-hidden select-none font-sans relative">
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
              <div className="flex-1 h-full overflow-hidden">
                {currentView === 'home' && (
                  <HomeView
                    onOpenLibrary={() => setCurrentView('library')}
                    onOpenBook={handleOpenBook}
                  />
                )}
                {currentView === 'library' && (
                  <LibraryView
                    onOpenBook={handleOpenBook}
                    refreshTrigger={libraryRefreshKey}
                  />
                )}
                {currentView === 'annotations' && <AnnotationsView onOpenBook={handleOpenBook} />}
                {currentView === 'catalogs' && <CatalogsView />}
                {currentView === 'settings' && (
                  <SettingsView onBackToHome={() => setCurrentView('home')} />
                )}
                {currentView === 'insights' && <InsightsView />}
              </div>
            </div>
          </AcrylicCanvas>
        )}
      </div>

      {/* Global Windows Fluent Drag Overlay */}
      {isDragging && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/65 backdrop-blur-xl pointer-events-none transition-all duration-300">
          <div
            className="flex flex-col items-center justify-center gap-5 p-12 mx-8 max-w-lg w-full rounded-2xl border-2 border-dashed bg-[#1e1e1e]/90 shadow-2xl text-center"
            style={{ borderColor: currentTheme.accent }}
          >
            <div
              className="w-20 h-20 rounded-2xl flex items-center justify-center shadow-lg transition-transform duration-300 scale-105"
              style={{
                background: `linear-gradient(135deg, ${currentTheme.accent}33, ${currentTheme.accent}88)`,
              }}
            >
              <FolderDown size={42} className="text-white animate-bounce" />
            </div>

            <div className="space-y-2">
              <h3 className="text-xl font-bold text-white tracking-wide">
                Drop books to add to your library (.epub, .pdf, .cbz)
              </h3>
              <p className="text-[13px] text-neutral-300">
                Release to automatically extract metadata and add books to your library
              </p>
            </div>

            <div className="flex gap-2 pt-2">
              {['EPUB', 'PDF', 'CBZ', 'CBR'].map((fmt) => (
                <span
                  key={fmt}
                  className="px-2.5 py-1 text-[11px] font-semibold tracking-wider rounded-md bg-white/10 text-neutral-200 border border-white/10"
                >
                  {fmt}
                </span>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Fluent Notification Banner */}
      {notification && (
        <div className="fixed top-12 right-6 z-50 flex items-center gap-3 px-4 py-2.5 rounded-lg bg-[#202020]/95 backdrop-blur-xl border border-white/15 text-white shadow-2xl">
          <div
            className="w-2 h-2 rounded-full"
            style={{ backgroundColor: currentTheme.accent }}
          />
          <CheckCircle2 size={16} className="text-emerald-400 flex-shrink-0" />
          <span className="text-[13px] font-medium">{notification}</span>
          <button
            type="button"
            onClick={() => setNotification(null)}
            className="ml-2 text-neutral-400 hover:text-white p-0.5 rounded cursor-pointer"
          >
            <X size={14} />
          </button>
        </div>
      )}
    </div>
  );
};

export function App() {
  return (
    <ThemeProvider>
      <MainShell />
    </ThemeProvider>
  );
}

export default App;
