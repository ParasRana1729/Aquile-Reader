import React, { useEffect, useState, useRef } from 'react';
import {
  Search,
  ArrowUpDown,
  Plus,
  CheckSquare,
  ChevronDown,
  LayoutGrid,
  List,
  Columns,
  Star,
  Trash2,
  BookOpen,
  X,
  FileText,
  Clock,
  HardDrive,
  FolderOpen,
  FolderSearch,
  CheckCircle2,
} from 'lucide-react';
import { useTheme } from '../context/ThemeContext';
import { BookWithProgress, ViewMode, SortOption } from '../types/book';
import {
  fetchBooks,
  importBook,
  importMultipleBooks,
  deleteBook,
  toggleFavorite,
  pickBookFile,
  pickBookFiles,
  pickFolder,
  scanDirectoryBooks,
} from '../utils/ipc';
import { ensureBookCover } from '../utils/pdfThumbnail';
import { ensureEpubCover } from '../utils/epubCover';

interface LibraryViewProps {
  onOpenBook: (bookId: string, book?: BookWithProgress) => void;
  refreshTrigger?: number;
}

export const LibraryView: React.FC<LibraryViewProps> = ({ onOpenBook, refreshTrigger }) => {
  const { currentTheme } = useTheme();
  const [books, setBooks] = useState<BookWithProgress[]>([]);
  const [loading, setLoading] = useState(true);
  const [collectionFilter, setCollectionFilter] = useState<'all' | 'favorites' | 'epub' | 'pdf' | 'cbz'>('all');
  const [isFilterDropdownOpen, setIsFilterDropdownOpen] = useState(false);
  const [sortOption, setSortOption] = useState<SortOption>('recent');
  const [isSortDropdownOpen, setIsSortDropdownOpen] = useState(false);
  const [viewMode, setViewMode] = useState<ViewMode>('grid');
  const [searchQuery, setSearchQuery] = useState('');
  const [isSearchOpen, setIsSearchOpen] = useState(false);
  const [selectedBook, setSelectedBook] = useState<BookWithProgress | null>(null);
  const [isInspectorOpen, setIsInspectorOpen] = useState(false);
  const [isScanning, setIsScanning] = useState(false);
  const [notification, setNotification] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const notificationTimer = useRef<number | null>(null);

  const showNotification = (msg: string) => {
    setNotification(msg);
    if (notificationTimer.current) {
      window.clearTimeout(notificationTimer.current);
    }
    notificationTimer.current = window.setTimeout(() => {
      setNotification(null);
    }, 4000);
  };

  const loadBooks = async () => {
    try {
      const data = await fetchBooks();
      setBooks(data);
      if (selectedBook) {
        const updated = data.find((b) => b.id === selectedBook.id);
        setSelectedBook(updated || null);
      }

      const applyCover = (bookId: string, coverUrl: string) => {
        setBooks((prev) =>
          prev.map((b) => (b.id === bookId ? { ...b, coverImage: coverUrl } : b))
        );
        setSelectedBook((prev) =>
          prev && prev.id === bookId ? { ...prev, coverImage: coverUrl } : prev
        );
      };
      data.forEach((book) => {
        const fmt = (book.format || '').toLowerCase();
        if (fmt === 'pdf') {
          ensureBookCover(book, applyCover);
        } else if (fmt === 'epub') {
          ensureEpubCover(book, applyCover);
        }
      });
    } catch (e) {
      console.error('Failed to load library books:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadBooks();
  }, [refreshTrigger]);

  const handleAddBook = async () => {
    const selectedPaths = await pickBookFiles();
    if (selectedPaths && selectedPaths.length > 0) {
      try {
        const imported = await importMultipleBooks(selectedPaths);
        await loadBooks();
        if (imported.length > 0) {
          setSelectedBook(imported[0]);
          setIsInspectorOpen(true);
        }
        showNotification(
          `Imported ${imported.length} book${imported.length === 1 ? '' : 's'} successfully`
        );
      } catch (e) {
        console.error('Book import failed:', e);
      }
    } else {
      fileInputRef.current?.click();
    }
  };

  const handleScanFolder = async () => {
    setIsScanning(true);
    try {
      let dirPath = await pickFolder();
      if (!dirPath) {
        const prompted = window.prompt('Enter folder path to scan for books (.epub, .pdf, .cbz):');
        if (prompted && prompted.trim()) {
          dirPath = prompted.trim();
        }
      }
      if (dirPath) {
        const foundFiles = await scanDirectoryBooks(dirPath);
        if (foundFiles.length === 0) {
          showNotification(`No books found in "${dirPath}"`);
        } else {
          const imported = await importMultipleBooks(foundFiles);
          await loadBooks();
          if (imported.length > 0) {
            setSelectedBook(imported[0]);
            setIsInspectorOpen(true);
          }
          showNotification(
            `Imported ${imported.length} book${imported.length === 1 ? '' : 's'} successfully`
          );
        }
      }
    } catch (err) {
      console.error('Folder scan failed:', err);
      showNotification('Failed to scan folder');
    } finally {
      setIsScanning(false);
    }
  };

  const handleFileInput = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    if (files.length > 0) {
      try {
        const paths = files.map((f) => (f as any).path || f.name);
        const imported = await importMultipleBooks(paths);
        await loadBooks();
        if (imported.length > 0) {
          setSelectedBook(imported[0]);
          setIsInspectorOpen(true);
        }
        showNotification(
          `Imported ${imported.length} book${imported.length === 1 ? '' : 's'} successfully`
        );
      } catch (err) {
        console.error('File import error:', err);
      }
    }
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const handleToggleFavorite = async (bookId: string, e?: React.MouseEvent) => {
    e?.stopPropagation();
    try {
      const isFav = await toggleFavorite(bookId);
      setBooks((prev) =>
        prev.map((b) => (b.id === bookId ? { ...b, isFavorite: isFav } : b))
      );
      if (selectedBook?.id === bookId) {
        setSelectedBook((prev) => (prev ? { ...prev, isFavorite: isFav } : null));
      }
    } catch (err) {
      console.error('Failed to toggle favorite:', err);
    }
  };

  const handleDeleteBook = async (bookId: string, e?: React.MouseEvent) => {
    e?.stopPropagation();
    if (window.confirm('Are you sure you want to remove this book from your library?')) {
      try {
        await deleteBook(bookId);
        setBooks((prev) => prev.filter((b) => b.id !== bookId));
        if (selectedBook?.id === bookId) {
          setSelectedBook(null);
          setIsInspectorOpen(false);
        }
      } catch (err) {
        console.error('Delete book failed:', err);
      }
    }
  };

  // Filter books
  let filteredBooks = books.filter((b) => {
    if (collectionFilter === 'favorites') return b.isFavorite;
    if (collectionFilter === 'epub') return b.format === 'epub';
    if (collectionFilter === 'pdf') return b.format === 'pdf';
    if (collectionFilter === 'cbz') return b.format === 'cbz' || b.format === 'cbr';
    return true;
  });

  // Search filter
  if (searchQuery.trim()) {
    const q = searchQuery.toLowerCase();
    filteredBooks = filteredBooks.filter(
      (b) =>
        b.title.toLowerCase().includes(q) ||
        (b.author && b.author.toLowerCase().includes(q))
    );
  }

  // Sort books
  filteredBooks.sort((a, b) => {
    if (sortOption === 'recent') {
      const dateA = a.lastReadDate || a.addedDate;
      const dateB = b.lastReadDate || b.addedDate;
      return dateB.localeCompare(dateA);
    }
    if (sortOption === 'title') {
      return a.title.localeCompare(b.title);
    }
    if (sortOption === 'author') {
      return (a.author || '').localeCompare(b.author || '');
    }
    return 0;
  });

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const filterLabels: Record<string, string> = {
    all: 'All Books',
    favorites: 'Favourites',
    epub: 'EPUB E-Books',
    pdf: 'PDF Documents',
    cbz: 'Comics & Manga',
  };

  return (
    <div className="flex h-full w-full select-none overflow-hidden relative text-white">
      {/* Hidden file input with multiple selection support */}
      <input
        type="file"
        ref={fileInputRef}
        onChange={handleFileInput}
        accept=".epub,.pdf,.cbz,.cbr"
        multiple
        className="hidden"
      />

      {/* Subtle Import Notification Banner */}
      {notification && (
        <div className="fixed top-12 right-8 z-50 flex items-center gap-3 px-4 py-2.5 rounded-lg bg-[#202020]/95 backdrop-blur-xl border border-white/15 text-white shadow-2xl transition-all">
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

      {/* Main Library Center Section */}
      <div className="flex-1 flex flex-col h-full overflow-hidden px-8 py-4">
        {/* Top Action Bar (Faithful to win_018) */}
        <div className="flex items-center justify-between pb-5 pt-1 border-b border-white/5 relative z-20">
          {/* Left: Collection Filter Dropdown */}
          <div className="relative">
            <button
              type="button"
              onClick={() => setIsFilterDropdownOpen(!isFilterDropdownOpen)}
              className="flex items-center gap-2 px-3 py-1.5 rounded-md hover:bg-white/10 text-[14px] font-medium text-white transition-colors cursor-pointer"
            >
              <span>{filterLabels[collectionFilter]}</span>
              <ChevronDown
                size={14}
                className={`text-neutral-400 transition-transform ${
                  isFilterDropdownOpen ? 'rotate-180' : ''
                }`}
              />
            </button>

            {isFilterDropdownOpen && (
              <div className="absolute left-0 mt-2 w-48 rounded-md bg-[#252525] border border-white/10 shadow-2xl py-1 z-30">
                {(['all', 'favorites', 'epub', 'pdf', 'cbz'] as const).map((key) => (
                  <button
                    key={key}
                    type="button"
                    onClick={() => {
                      setCollectionFilter(key);
                      setIsFilterDropdownOpen(false);
                    }}
                    className={`w-full text-left px-4 py-2 text-[13px] hover:bg-white/10 transition-colors flex items-center justify-between ${
                      collectionFilter === key
                        ? 'text-white font-medium bg-white/5'
                        : 'text-neutral-300'
                    }`}
                  >
                    <span>{filterLabels[key]}</span>
                    {collectionFilter === key && (
                      <span
                        className="w-1.5 h-1.5 rounded-full"
                        style={{ backgroundColor: currentTheme.accent }}
                      />
                    )}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Right Toolbar Controls */}
          <div className="flex items-center gap-1.5 text-neutral-300">
            {/* Search Input / Button */}
            {isSearchOpen ? (
              <div className="flex items-center bg-black/40 border border-white/20 rounded px-2.5 py-1 mr-2">
                <Search size={15} className="text-neutral-400 mr-2" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search books..."
                  className="bg-transparent border-none text-[13px] text-white focus:outline-none w-48"
                  autoFocus
                  onBlur={() => !searchQuery && setIsSearchOpen(false)}
                />
                {searchQuery && (
                  <button
                    type="button"
                    onClick={() => setSearchQuery('')}
                    className="text-neutral-400 hover:text-white"
                  >
                    <X size={14} />
                  </button>
                )}
              </div>
            ) : (
              <button
                type="button"
                onClick={() => setIsSearchOpen(true)}
                className="p-2 rounded hover:bg-white/10 hover:text-white transition-colors cursor-pointer"
                title="Search library"
              >
                <Search size={18} />
              </button>
            )}

            {/* View Mode Toggle */}
            <button
              type="button"
              onClick={() =>
                setViewMode((prev) =>
                  prev === 'grid' ? 'shelf' : prev === 'shelf' ? 'list' : 'grid'
                )
              }
              className="p-2 rounded hover:bg-white/10 hover:text-white transition-colors cursor-pointer"
              title={`View Mode: ${viewMode}`}
            >
              {viewMode === 'grid' && <LayoutGrid size={18} />}
              {viewMode === 'shelf' && <Columns size={18} />}
              {viewMode === 'list' && <List size={18} />}
            </button>

            {/* Sort Dropdown */}
            <div className="relative">
              <button
                type="button"
                onClick={() => setIsSortDropdownOpen(!isSortDropdownOpen)}
                className="p-2 rounded hover:bg-white/10 hover:text-white transition-colors cursor-pointer"
                title="Sort options"
              >
                <ArrowUpDown size={18} />
              </button>

              {isSortDropdownOpen && (
                <div className="absolute right-0 mt-2 w-40 rounded-md bg-[#252525] border border-white/10 shadow-2xl py-1 z-30">
                  {(['recent', 'title', 'author'] as const).map((opt) => (
                    <button
                      key={opt}
                      type="button"
                      onClick={() => {
                        setSortOption(opt);
                        setIsSortDropdownOpen(false);
                      }}
                      className={`w-full text-left px-4 py-2 text-[13px] hover:bg-white/10 transition-colors capitalize ${
                        sortOption === opt
                          ? 'text-white font-medium bg-white/5'
                          : 'text-neutral-300'
                      }`}
                    >
                      {opt === 'recent'
                        ? 'Recently Read'
                        : opt === 'title'
                        ? 'Title'
                        : 'Author'}
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Add Book Button */}
            <button
              type="button"
              onClick={handleAddBook}
              className="p-2 rounded hover:bg-white/10 hover:text-white transition-colors cursor-pointer"
              title="Add Book(s) to Library"
            >
              <Plus size={20} className="stroke-[2.5]" />
            </button>

            {/* Scan Folder Button */}
            <button
              type="button"
              onClick={handleScanFolder}
              disabled={isScanning}
              className={`p-2 rounded hover:bg-white/10 hover:text-white transition-colors cursor-pointer ${
                isScanning ? 'animate-pulse text-neutral-400' : ''
              }`}
              title="Scan Folder for Books"
            >
              <FolderSearch size={18} />
            </button>

            {/* Inspect / Select Mode Toggle */}
            <button
              type="button"
              onClick={() => {
                if (!selectedBook && filteredBooks.length > 0) {
                  setSelectedBook(filteredBooks[0]);
                }
                setIsInspectorOpen(!isInspectorOpen);
              }}
              className={`p-2 rounded hover:bg-white/10 hover:text-white transition-colors cursor-pointer ${
                isInspectorOpen ? 'text-white bg-white/10' : ''
              }`}
              title="Book Details Inspector"
            >
              <CheckSquare size={18} />
            </button>
          </div>
        </div>

        {/* Content Area: Grid / Shelf / List Matching win_019 */}
        <div className="flex-1 overflow-y-auto pt-6 pb-12">
          {filteredBooks.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-center p-8 text-neutral-400">
              <FolderOpen size={48} className="mb-4 opacity-40" />
              <p className="text-[14px] text-[#c8c8c8] font-medium">No books found</p>
              <p className="text-[13px] text-neutral-500 mt-1 max-w-sm">
                Add EPUB, PDF, or Comic archives via single/bulk file selection, drag-and-drop, or folder scanning.
              </p>
              <div className="flex items-center gap-3 mt-5">
                <button
                  type="button"
                  onClick={handleAddBook}
                  className="px-4 py-2 rounded-md bg-white/10 hover:bg-white/20 text-white text-[13px] font-medium transition-colors cursor-pointer"
                >
                  + Add Book
                </button>
                <button
                  type="button"
                  onClick={handleScanFolder}
                  className="px-4 py-2 rounded-md bg-white/5 hover:bg-white/10 text-neutral-300 hover:text-white text-[13px] font-medium border border-white/10 transition-colors cursor-pointer flex items-center gap-2"
                >
                  <FolderSearch size={14} />
                  Scan Folder
                </button>
              </div>
            </div>
          ) : viewMode === 'list' ? (
            /* List View */
            <div className="flex flex-col space-y-2">
              {filteredBooks.map((book) => (
                <div
                  key={book.id}
                  onClick={() => {
                    setSelectedBook(book);
                    setIsInspectorOpen(true);
                  }}
                  onDoubleClick={() => onOpenBook(book.id, book)}
                  className={`flex items-center justify-between p-3 rounded-lg border transition-all cursor-pointer ${
                    selectedBook?.id === book.id
                      ? 'bg-white/15 border-white/30'
                      : 'bg-white/5 border-white/10 hover:bg-white/10'
                  }`}
                >
                  <div className="flex items-center gap-4 min-w-0">
                    <div className="w-10 h-14 rounded overflow-hidden flex-shrink-0 bg-neutral-800 border border-white/10">
                      {book.coverImage ? (
                        <img
                          src={book.coverImage}
                          alt={book.title}
                          className="w-full h-full object-cover"
                        />
                      ) : (
                        <div className="w-full h-full flex items-center justify-center text-[10px] text-neutral-400 uppercase font-bold">
                          {book.format}
                        </div>
                      )}
                    </div>
                    <div className="min-w-0">
                      <div className="text-[14px] font-medium text-white truncate">
                        {book.title}
                      </div>
                      <div className="text-[12px] text-neutral-400 truncate">
                        {book.author || 'Unknown Author'}
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-6 text-[12px] text-neutral-400">
                    <span className="uppercase font-semibold px-2 py-0.5 rounded bg-white/5 text-[10px] text-neutral-300">
                      {book.format}
                    </span>
                    <span>{Math.round(book.percentage)}%</span>
                    <button
                      type="button"
                      onClick={(e) => handleToggleFavorite(book.id, e)}
                      className="hover:text-yellow-400 p-1"
                    >
                      <Star
                        size={16}
                        className={
                          book.isFavorite
                            ? 'fill-yellow-400 text-yellow-400'
                            : 'text-neutral-400'
                        }
                      />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            /* Grid & Shelf View (Faithful 1:1 match to win_019) */
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-8">
              {filteredBooks.map((book) => {
                const isSelected = selectedBook?.id === book.id;
                return (
                  <div
                    key={book.id}
                    onClick={() => {
                      setSelectedBook(book);
                      setIsInspectorOpen(true);
                    }}
                    onDoubleClick={() => onOpenBook(book.id, book)}
                    className="group flex flex-col items-center cursor-pointer transition-all duration-200"
                  >
                    {/* Book Cover Card */}
                    <div
                      className={`w-[145px] h-[210px] rounded-[6px] overflow-hidden relative transition-all duration-300 transform group-hover:scale-105 ring-1 ${
                        isSelected
                          ? 'ring-white/50 scale-105'
                          : 'ring-white/10'
                      }`}
                      style={{
                        boxShadow: isSelected
                          ? `0 0 24px rgba(255, 255, 255, 0.4), 0 8px 24px rgba(0, 0, 0, 0.6)`
                          : '0 8px 22px rgba(0, 0, 0, 0.5)',
                      }}
                    >
                      {book.coverImage ? (
                        <img
                          src={book.coverImage}
                          alt={book.title}
                          className="w-full h-full object-cover"
                        />
                      ) : (
                        <div className="w-full h-full bg-[#1e293b] p-3 flex flex-col justify-between text-white text-center">
                          <div className="pt-3">
                            <div className="text-[12px] font-bold leading-tight line-clamp-3">
                              {book.title}
                            </div>
                            <div className="text-[10px] text-neutral-400 mt-2 truncate">
                              {book.author}
                            </div>
                          </div>
                          <div className="text-[9px] uppercase font-bold text-neutral-400 pb-1">
                            {book.format}
                          </div>
                        </div>
                      )}

                      {/* Reading Progress Pill */}
                      {book.percentage > 0 && (
                        <div className="absolute bottom-2 right-2 px-2 py-0.5 rounded-full text-[11px] font-semibold tabular-nums bg-black/70 text-white backdrop-blur-sm">
                          {Math.round(book.percentage)}%
                        </div>
                      )}

                      {/* Favorite Star Badge */}
                      {book.isFavorite && (
                        <div
                          className="absolute top-2 right-2 p-1 rounded-full bg-black/60 backdrop-blur-sm"
                          title="Favourite"
                        >
                          <Star size={12} className="fill-yellow-400 text-yellow-400" />
                        </div>
                      )}

                      {/* Format Badge */}
                      <div className="absolute top-2 left-2 px-1.5 py-0.5 rounded text-[8px] font-bold uppercase tracking-wider bg-black/60 text-neutral-300 backdrop-blur-sm">
                        {book.format}
                      </div>
                    </div>

                    {/* Book Metadata Below Card */}
                    <div className="mt-3 text-center w-[145px]">
                      <div className="text-[13px] font-medium text-white truncate leading-snug">
                        {book.title}
                      </div>
                      <div className="text-[12px] text-neutral-400 truncate mt-0.5">
                        {book.author || 'Unknown Author'}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* ================= Collapsible Right Inspector Pane ================= */}
      {isInspectorOpen && selectedBook && (
        <aside className="w-80 h-full bg-[#1e1e1e]/90 backdrop-blur-2xl border-l border-white/10 flex flex-col z-30 transition-all shadow-2xl">
          {/* Header */}
          <div className="flex items-center justify-between p-4 border-b border-white/10">
            <h3 className="text-[14px] font-semibold text-white tracking-wide">
              Book Details
            </h3>
            <button
              type="button"
              onClick={() => setIsInspectorOpen(false)}
              className="p-1.5 rounded hover:bg-white/10 text-neutral-400 hover:text-white transition-colors cursor-pointer"
            >
              <X size={16} />
            </button>
          </div>

          {/* Inspector Body */}
          <div className="flex-1 overflow-y-auto p-5 space-y-6">
            {/* Cover Preview */}
            <div className="flex justify-center">
              <div
                className="w-[140px] h-[200px] rounded-lg overflow-hidden border border-white/20 relative"
                style={{ boxShadow: '0 8px 24px rgba(0, 0, 0, 0.5)' }}
              >
                {selectedBook.coverImage ? (
                  <img
                    src={selectedBook.coverImage}
                    alt={selectedBook.title}
                    className="w-full h-full object-cover"
                  />
                ) : (
                  <div className="w-full h-full bg-neutral-800 flex items-center justify-center text-neutral-400">
                    <FileText size={32} />
                  </div>
                )}
              </div>
            </div>

            {/* Title & Author */}
            <div className="text-center">
              <h2 className="text-[16px] font-bold text-white leading-tight">
                {selectedBook.title}
              </h2>
              <p className="text-[13px] text-neutral-400 mt-1">
                {selectedBook.author || 'Unknown Author'}
              </p>
            </div>

            {/* Primary Action Button */}
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => onOpenBook(selectedBook.id, selectedBook)}
                className="flex-1 flex items-center justify-center gap-2 py-2.5 px-4 rounded-md text-[13px] font-semibold text-white transition-all shadow cursor-pointer"
                style={{ backgroundColor: currentTheme.accent }}
              >
                <BookOpen size={16} />
                <span>Open in Reader</span>
              </button>

              <button
                type="button"
                onClick={() => handleToggleFavorite(selectedBook.id)}
                className={`p-2.5 rounded-md border transition-colors cursor-pointer ${
                  selectedBook.isFavorite
                    ? 'border-yellow-500/40 bg-yellow-500/10 text-yellow-400'
                    : 'border-white/15 hover:bg-white/10 text-neutral-300'
                }`}
                title="Toggle Favorite"
              >
                <Star
                  size={18}
                  className={selectedBook.isFavorite ? 'fill-current' : ''}
                />
              </button>
            </div>

            {/* Metadata Properties Table */}
            <div className="space-y-3 pt-2 text-[12.5px] border-t border-white/10">
              <div className="flex justify-between items-center text-neutral-400">
                <span className="flex items-center gap-1.5">
                  <FileText size={14} /> Format
                </span>
                <span className="text-white uppercase font-semibold">
                  {selectedBook.format}
                </span>
              </div>

              <div className="flex justify-between items-center text-neutral-400">
                <span className="flex items-center gap-1.5">
                  <Clock size={14} /> Progress
                </span>
                <span className="text-white font-medium">
                  {Math.round(selectedBook.percentage)}%
                </span>
              </div>

              <div className="flex justify-between items-center text-neutral-400">
                <span className="flex items-center gap-1.5">
                  <BookOpen size={14} /> Pages / Chapters
                </span>
                <span className="text-white">
                  {selectedBook.pageCount > 0
                    ? `${selectedBook.pageCount} pages`
                    : `${selectedBook.chapterCount} chapters`}
                </span>
              </div>

              <div className="flex justify-between items-center text-neutral-400">
                <span className="flex items-center gap-1.5">
                  <HardDrive size={14} /> File Size
                </span>
                <span className="text-white">
                  {formatFileSize(selectedBook.fileSize)}
                </span>
              </div>

              {selectedBook.lastReadDate && (
                <div className="flex justify-between items-center text-neutral-400">
                  <span>Last Read</span>
                  <span className="text-white text-[11.5px]">
                    {new Date(selectedBook.lastReadDate).toLocaleDateString()}
                  </span>
                </div>
              )}
            </div>

            {/* Danger Zone: Delete */}
            <div className="pt-4 border-t border-white/10">
              <button
                type="button"
                onClick={() => handleDeleteBook(selectedBook.id)}
                className="w-full flex items-center justify-center gap-2 py-2 px-3 rounded-md text-[12.5px] text-red-400 hover:text-red-300 hover:bg-red-500/10 border border-red-500/20 transition-colors cursor-pointer"
              >
                <Trash2 size={15} />
                <span>Delete from Library</span>
              </button>
            </div>
          </div>
        </aside>
      )}
    </div>
  );
};
