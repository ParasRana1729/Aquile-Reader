import React, { useState } from 'react';
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
import { fetchBooks } from './utils/ipc';
import { BookWithProgress } from './types/book';

const MainShell: React.FC = () => {
  const [currentView, setCurrentView] = useState<NavView>('home');
  const [isReading, setIsReading] = useState(false);
  const [currentBook, setCurrentBook] = useState<BookWithProgress | null>(null);
  const [currentBookTitle, setCurrentBookTitle] = useState('The Prince');
  const [currentBookId, setCurrentBookId] = useState('book-the-prince');
  const [currentBookFormat, setCurrentBookFormat] = useState<'PDF' | 'EPUB' | 'COMIC' | 'TEXT'>('PDF');

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
    <div className="flex flex-col h-screen w-screen overflow-hidden select-none font-sans">
      {/* Dynamic TitleBar */}
      <TitleBar
        title={titleBarText}
        showBack={showBack}
        onBack={handleBack}
      />

      {/* Main Client Area */}
      <div className="flex-1 flex overflow-hidden">
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
                  <LibraryView onOpenBook={handleOpenBook} />
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
