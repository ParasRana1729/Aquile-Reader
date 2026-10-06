import React, { useEffect, useState, useRef } from 'react';
import { useTheme } from '../context/ThemeContext';
import { Plus, Megaphone, Smartphone, Star, ChevronRight } from 'lucide-react';
import { BookWithProgress } from '../types/book';
import { fetchBooks, fetchRecentReads, importBook, pickBookFile } from '../utils/ipc';
import { ensureBookCover } from '../utils/pdfThumbnail';

interface HomeViewProps {
  onOpenLibrary: () => void;
  onOpenBook: (bookId: string, book?: BookWithProgress) => void;
}

export const HomeView: React.FC<HomeViewProps> = ({ onOpenLibrary, onOpenBook }) => {
  const { currentTheme } = useTheme();
  const [books, setBooks] = useState<BookWithProgress[]>([]);
  const [recentReads, setRecentReads] = useState<BookWithProgress[]>([]);
  const [loading, setLoading] = useState(true);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const loadData = async () => {
    try {
      const [allBooks, recents] = await Promise.all([
        fetchBooks(),
        fetchRecentReads(4),
      ]);
      setBooks(allBooks);
      setRecentReads(recents);

      allBooks.forEach((book) => {
        if ((book.format || '').toLowerCase() === 'pdf') {
          ensureBookCover(book, (bookId, coverUrl) => {
            setBooks((prev) =>
              prev.map((b) => (b.id === bookId ? { ...b, coverImage: coverUrl } : b))
            );
            setRecentReads((prev) =>
              prev.map((b) => (b.id === bookId ? { ...b, coverImage: coverUrl } : b))
            );
          });
        }
      });
    } catch (e) {
      console.error('Failed to load books for Home view:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleAddBook = async () => {
    const selectedPath = await pickBookFile();
    if (selectedPath) {
      try {
        await importBook(selectedPath);
        await loadData();
      } catch (e) {
        console.error('Import failed:', e);
      }
    } else {
      // Browser fallback
      fileInputRef.current?.click();
    }
  };

  const handleFileInputChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      try {
        await importBook(file.name);
        await loadData();
      } catch (err) {
        console.error('Web import failed:', err);
      }
    }
  };

  // Divide books into sections
  const heroBook = recentReads[0] || books[0];
  const secondaryRecents = recentReads.slice(1, 3);
  const favoriteBooks = books.filter((b) => b.isFavorite);
  const recentlyAdded = books.slice(0, 4);

  return (
    <div className="flex flex-col h-full w-full select-none overflow-y-auto px-10 py-5 text-white">
      <input
        type="file"
        ref={fileInputRef}
        onChange={handleFileInputChange}
        accept=".epub,.pdf,.cbz,.cbr"
        className="hidden"
      />

      {/* Top Header Command Strip (matching win_001) */}
      <div className="flex items-center justify-between pb-7 pt-1">
        <div className="flex items-center gap-5 text-neutral-400">
          <button
            type="button"
            className="hover:text-white transition-colors p-1.5 rounded hover:bg-white/5"
            title="Announcements"
          >
            <Megaphone size={19} />
          </button>
          <button
            type="button"
            className="hover:text-white transition-colors p-1.5 rounded hover:bg-white/5 text-[#8ecdf7]"
            title="Connected Device"
          >
            <Smartphone size={19} />
          </button>
        </div>

        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={handleAddBook}
            className="flex items-center justify-center p-2 rounded-full hover:bg-white/10 text-white transition-colors"
            title="Add Book"
          >
            <Plus size={24} className="stroke-[2.5]" />
          </button>
        </div>
      </div>

      {/* Main 2-Column Grid (matching win_001) */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-16 w-full max-w-[1440px]">
        {/* ================= LEFT COLUMN: Recent Reads ================= */}
        <section className="flex flex-col">
          <div className="flex items-center justify-between mb-7">
            <h2 className="text-[22px] font-normal text-white tracking-tight">
              Recent Reads
            </h2>
            <button
              onClick={onOpenLibrary}
              className="flex items-center text-[13px] text-neutral-300 hover:text-white transition-colors group cursor-pointer"
            >
              <span>Open Library</span>
              <ChevronRight
                size={16}
                className="ml-0.5 group-hover:translate-x-0.5 transition-transform"
              />
            </button>
          </div>

          <div className="flex gap-7 items-start">
            {/* Featured Hero Book Card with Luminous Halo Glow */}
            {heroBook && (
              <div
                onClick={() => onOpenBook(heroBook.id, heroBook)}
                className="relative cursor-pointer group rounded-[6px] overflow-hidden transition-all duration-300 transform hover:scale-[1.02] flex-shrink-0"
                style={{
                  boxShadow: `0 0 28px rgba(255, 255, 255, 0.28), 0 8px 30px rgba(0, 0, 0, 0.65)`,
                }}
              >
                <div className="w-[230px] h-[340px] bg-white rounded-[6px] overflow-hidden border border-white/20 relative flex flex-col justify-between">
                  {heroBook.coverImage ? (
                    <img
                      src={heroBook.coverImage}
                      alt={heroBook.title}
                      className="w-full h-full object-cover"
                    />
                  ) : (
                    <div className="h-full w-full p-6 flex flex-col justify-between text-neutral-900 bg-white">
                      <div className="text-center pt-8">
                        <h3 className="font-serif font-bold text-[19px] tracking-wide text-neutral-900">
                          {heroBook.title}
                        </h3>
                        {heroBook.author && (
                          <p className="font-serif italic text-[12px] text-neutral-600 mt-2">
                            {heroBook.author}
                          </p>
                        )}
                      </div>
                      <div className="pb-4 text-center">
                        <div className="inline-block px-3 py-1 font-sans font-black text-[18px] text-[#2c3882] tracking-tighter">
                          Planet <span className="text-[#e26a2c]">PDF</span>
                        </div>
                        <div className="text-[8.5px] text-neutral-500 mt-2 leading-tight">
                          This eBook was designed and published by Planet PDF.
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Optional progress indicator pill */}
                  {heroBook.percentage > 0 && (
                    <div className="absolute bottom-2 right-2 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-black/70 text-white backdrop-blur-sm">
                      {Math.round(heroBook.percentage)}%
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Stacked Secondary Book Covers */}
            <div className="flex flex-col gap-6">
              {secondaryRecents.map((book) => (
                <div
                  key={book.id}
                  onClick={() => onOpenBook(book.id, book)}
                  className="w-[125px] h-[160px] rounded-[5px] overflow-hidden cursor-pointer hover:scale-105 transition-all duration-200 border border-white/15 relative"
                  style={{
                    boxShadow: '0 4px 18px rgba(0, 0, 0, 0.45)',
                  }}
                >
                  {book.coverImage ? (
                    <img
                      src={book.coverImage}
                      alt={book.title}
                      className="w-full h-full object-cover"
                    />
                  ) : (
                    <div className="w-full h-full bg-[#1e293b] p-3 flex flex-col justify-between text-white">
                      <div className="text-center pt-2">
                        <div className="text-[10px] font-serif uppercase tracking-wider font-semibold line-clamp-3">
                          {book.title}
                        </div>
                        <div className="text-[8px] text-neutral-400 mt-1 truncate">
                          {book.author}
                        </div>
                      </div>
                      <div className="text-[7px] text-neutral-400 uppercase text-center">
                        {book.format}
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ================= RIGHT COLUMN: Favourite Books & Recently Added ================= */}
        <section className="flex flex-col space-y-12">
          {/* Top Section: Favourite Books */}
          <div>
            <div className="flex items-center justify-between mb-5">
              <h2 className="text-[22px] font-normal text-white tracking-tight">
                Favourite Books
              </h2>
              <button
                onClick={onOpenLibrary}
                className="flex items-center text-[13px] text-neutral-300 hover:text-white transition-colors group cursor-pointer"
              >
                <span>See more</span>
                <ChevronRight
                  size={16}
                  className="ml-0.5 group-hover:translate-x-0.5 transition-transform"
                />
              </button>
            </div>

            {favoriteBooks.length === 0 ? (
              /* Glowing Star Empty State (Faithful 1:1 match to win_001) */
              <div className="h-44 rounded-lg flex flex-col items-center justify-center text-center p-6">
                <Star
                  size={42}
                  className="mb-4 transition-colors duration-300 fill-current"
                  style={{
                    color: currentTheme.accent,
                    filter: `drop-shadow(0 0 16px ${currentTheme.accentGlow}) drop-shadow(0 0 6px ${currentTheme.accent})`,
                  }}
                />
                <p className="text-[14px] text-neutral-300 font-normal">
                  Your favourite books would appear here
                </p>
              </div>
            ) : (
              /* Favorite Books Row */
              <div className="flex gap-5 overflow-x-auto pb-2">
                {favoriteBooks.map((book) => (
                  <div
                    key={book.id}
                    onClick={() => onOpenBook(book.id)}
                    className="w-[115px] h-[160px] rounded-[5px] overflow-hidden cursor-pointer hover:scale-105 transition-all duration-200 border border-white/15 flex-shrink-0"
                    style={{ boxShadow: '0 4px 16px rgba(0, 0, 0, 0.4)' }}
                  >
                    {book.coverImage ? (
                      <img
                        src={book.coverImage}
                        alt={book.title}
                        className="w-full h-full object-cover"
                      />
                    ) : (
                      <div className="w-full h-full bg-[#1e293b] p-2 flex flex-col justify-between text-white text-center">
                        <div className="text-[10px] font-serif font-bold line-clamp-2 mt-2">
                          {book.title}
                        </div>
                        <div className="text-[8px] text-neutral-400">{book.author}</div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Bottom Section: Recently Added Books */}
          <div>
            <div className="flex items-center justify-between mb-5">
              <h2 className="text-[22px] font-normal text-white tracking-tight">
                Recently Added Books
              </h2>
              <button
                onClick={onOpenLibrary}
                className="flex items-center text-[13px] text-neutral-300 hover:text-white transition-colors group cursor-pointer"
              >
                <span>See more</span>
                <ChevronRight
                  size={16}
                  className="ml-0.5 group-hover:translate-x-0.5 transition-transform"
                />
              </button>
            </div>

            <div className="flex gap-5 overflow-x-auto pb-2">
              {recentlyAdded.map((book) => (
                <div
                  key={book.id}
                  onClick={() => onOpenBook(book.id)}
                  className="w-[125px] h-[175px] rounded-[5px] overflow-hidden cursor-pointer hover:scale-105 transition-all duration-200 border border-white/20 flex-shrink-0 relative group"
                  style={{
                    boxShadow: '0 0 16px rgba(255, 255, 255, 0.16), 0 4px 14px rgba(0, 0, 0, 0.45)',
                  }}
                >
                  {book.coverImage ? (
                    <img
                      src={book.coverImage}
                      alt={book.title}
                      className="w-full h-full object-cover"
                    />
                  ) : (
                    <div className="w-full h-full bg-white p-3 flex flex-col justify-between text-neutral-900">
                      <div className="text-center pt-2">
                        <div className="font-serif font-bold text-[11px] text-neutral-900 leading-tight">
                          {book.title}
                        </div>
                        <div className="text-[8px] text-neutral-500 mt-1">
                          {book.author}
                        </div>
                      </div>
                      <div className="text-[9px] font-bold text-[#2c3882] text-center pb-1">
                        Planet <span className="text-[#e26a2c]">PDF</span>
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </section>
      </div>
    </div>
  );
};
