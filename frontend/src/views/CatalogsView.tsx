import React, { useState, useMemo } from 'react';
import { useTheme } from '../context/ThemeContext';
import { importBook } from '../utils/ipc';
import {
  Search,
  Download,
  Plus,
  ArrowLeft,
  ArrowRight,
  RotateCw,
  Home,
  Info,
  Check,
  BookOpen,
  X,
  ExternalLink,
  Layers,
  Sparkles,
  FileCheck,
  Clock,
  ChevronRight,
} from 'lucide-react';

interface CatalogBook {
  id: string;
  title: string;
  author: string;
  year: string;
  downloads: string;
  genre: string;
  language: string;
  fileSize: string;
  description: string;
  coverBg: string;
  coverAccent: string;
  chapters?: string[];
  format: string;
}

interface CatalogSite {
  id: string;
  name: string;
  description: string;
  url: string;
  iconBg: string;
  iconType: 'gutenberg' | 'standard' | 'feedbooks' | 'custom';
  books: CatalogBook[];
}

interface DownloadItem {
  id: string;
  bookTitle: string;
  author: string;
  catalogName: string;
  progress: number;
  status: 'downloading' | 'completed' | 'failed';
  downloadDate: string;
}

export const CatalogsView: React.FC = () => {
  const { currentTheme } = useTheme();

  // Initial Pre-configured Catalogs
  const [catalogs, setCatalogs] = useState<CatalogSite[]>([
    {
      id: 'gutenberg',
      name: 'Gutenberg',
      description: 'Over 70,000 free eBooks including the world’s greatest classic literature.',
      url: 'https://m.gutenberg.org/ebooks.opds/',
      iconBg: '#c32026',
      iconType: 'gutenberg',
      books: [
        {
          id: 'gut-1',
          title: 'Pride and Prejudice',
          author: 'Jane Austen',
          year: '1813',
          downloads: '68,240',
          genre: 'Classic Fiction',
          language: 'English',
          fileSize: '780 KB',
          description:
            'A romantic novel of manners written by Jane Austen in 1813. The story follows the character development of Elizabeth Bennet, the dynamic protagonist of the book.',
          coverBg: '#2a1a1f',
          coverAccent: '#d46a84',
          format: 'EPUB',
          chapters: ['Chapter 1 - Longbourn Estate', 'Chapter 2 - Netherfield Park', 'Chapter 3 - The Assembly Ball', 'Chapter 4 - Jane and Elizabeth'],
        },
        {
          id: 'gut-2',
          title: 'Frankenstein',
          author: 'Mary Wollstonecraft Shelley',
          year: '1818',
          downloads: '54,120',
          genre: 'Gothic Horror',
          language: 'English',
          fileSize: '540 KB',
          description:
            'Frankenstein; or, The Modern Prometheus is an 1818 novel written by English author Mary Shelley that tells the story of Victor Frankenstein, a young scientist who creates a sapient creature in an unorthodox scientific experiment.',
          coverBg: '#13221c',
          coverAccent: '#48a87b',
          format: 'EPUB',
          chapters: ['Letter 1 - Archangel', 'Letter 2 - St. Petersburgh', 'Chapter 1 - Geneva Childhood', 'Chapter 2 - Natural Philosophy'],
        },
        {
          id: 'gut-3',
          title: 'The Great Gatsby',
          author: 'F. Scott Fitzgerald',
          year: '1925',
          downloads: '49,800',
          genre: 'American Literature',
          language: 'English',
          fileSize: '420 KB',
          description:
            'The Great Gatsby is a 1925 novel by American writer F. Scott Fitzgerald. Set in the Jazz Age on Long Island, near New York City, the novel depicts first-person narrator Nick Carraway\'s interactions with mysterious millionaire Jay Gatsby.',
          coverBg: '#101d2d',
          coverAccent: '#d6a03e',
          format: 'EPUB',
          chapters: ['Chapter 1 - West Egg', 'Chapter 2 - Valley of Ashes', 'Chapter 3 - Gatsby\'s Party', 'Chapter 4 - Drive to the City'],
        },
        {
          id: 'gut-4',
          title: 'The Picture of Dorian Gray',
          author: 'Oscar Wilde',
          year: '1890',
          downloads: '42,300',
          genre: 'Philosophical Fiction',
          language: 'English',
          fileSize: '610 KB',
          description:
            'The Picture of Dorian Gray is a philosophical novel by Oscar Wilde. A decadent young man trades his soul for eternal youth and beauty, while a hidden portrait bears the sins and aging of his life.',
          coverBg: '#2b1b11',
          coverAccent: '#c78440',
          format: 'EPUB',
          chapters: ['Chapter 1 - Basil\'s Studio', 'Chapter 2 - The Sitting', 'Chapter 3 - Lord Henry', 'Chapter 4 - Sybil Vane'],
        },
        {
          id: 'gut-5',
          title: 'A Tale of Two Cities',
          author: 'Charles Dickens',
          year: '1859',
          downloads: '38,950',
          genre: 'Historical Fiction',
          language: 'English',
          fileSize: '890 KB',
          description:
            'A Tale of Two Cities is an 1859 historical novel by Charles Dickens, set in London and Paris before and during the French Revolution.',
          coverBg: '#1c1c24',
          coverAccent: '#8a7db3',
          format: 'EPUB',
          chapters: ['Book the First: Recalled to Life', 'The Period', 'The Mail', 'The Night Shadows'],
        },
        {
          id: 'gut-6',
          title: 'Alice\'s Adventures in Wonderland',
          author: 'Lewis Carroll',
          year: '1865',
          downloads: '36,400',
          genre: 'Fantasy',
          language: 'English',
          fileSize: '350 KB',
          description:
            'An 1865 English novel by Lewis Carroll. It tells of a young girl named Alice, who falls through a rabbit hole into a subterranean fantasy world populated by peculiar, anthropomorphic creatures.',
          coverBg: '#21152a',
          coverAccent: '#a463ce',
          format: 'EPUB',
          chapters: ['Chapter 1 - Down the Rabbit-Hole', 'Chapter 2 - The Pool of Tears', 'Chapter 3 - A Caucus-Race and a Long Tale'],
        },
      ],
    },
    {
      id: 'standard',
      name: 'Standard Ebooks',
      description: 'Free, carefully formatted digital books with modern typography and open public domain.',
      url: 'https://standardebooks.org/opds/all',
      iconBg: '#354359',
      iconType: 'standard',
      books: [
        {
          id: 'se-1',
          title: 'The Count of Monte Cristo',
          author: 'Alexandre Dumas',
          year: '1844',
          downloads: '32,100',
          genre: 'Adventure Classic',
          language: 'English',
          fileSize: '1.9 MB',
          description:
            'The Count of Monte Cristo is an adventure novel by Alexandre Dumas. It is one of the author\'s most popular works, along with The Three Musketeers.',
          coverBg: '#1e2430',
          coverAccent: '#4c8ee8',
          format: 'EPUB 3',
          chapters: ['Chapter 1 - Marseilles: The Arrival', 'Chapter 2 - Father and Son', 'Chapter 3 - The Catalans'],
        },
        {
          id: 'se-2',
          title: 'Meditations',
          author: 'Marcus Aurelius',
          year: '180 AD',
          downloads: '45,600',
          genre: 'Philosophy',
          language: 'English',
          fileSize: '480 KB',
          description:
            'Meditations is a series of personal writings by Marcus Aurelius, Roman Emperor from AD 161 to 180, recording his private notes to himself and ideas on Stoic philosophy.',
          coverBg: '#26221c',
          coverAccent: '#c99e52',
          format: 'EPUB 3',
          chapters: ['Book 1 - Debts and Lessons', 'Book 2 - On the River Gran', 'Book 3 - In Carnuntum'],
        },
        {
          id: 'se-3',
          title: 'Crime and Punishment',
          author: 'Fyodor Dostoevsky',
          year: '1866',
          downloads: '41,200',
          genre: 'Psychological Drama',
          language: 'English',
          fileSize: '1.1 MB',
          description:
            'Crime and Punishment follows the mental anguish and moral dilemmas of Rodion Raskolnikov, an impoverished ex-student in Saint Petersburg who plans to kill an unscrupulous pawnbroker.',
          coverBg: '#201a1c',
          coverAccent: '#c7445a',
          format: 'EPUB 3',
          chapters: ['Part 1: Chapter 1', 'Part 1: Chapter 2', 'Part 1: Chapter 3'],
        },
        {
          id: 'se-4',
          title: 'The Metamorphosis',
          author: 'Franz Kafka',
          year: '1915',
          downloads: '37,800',
          genre: 'Absurdist Fiction',
          language: 'English',
          fileSize: '290 KB',
          description:
            'The Metamorphosis tells the story of salesman Gregor Samsa, who wakes one morning to find himself inexplicably transformed into a huge insect.',
          coverBg: '#1b2320',
          coverAccent: '#42a884',
          format: 'EPUB 3',
          chapters: ['Chapter 1 - The Transformation', 'Chapter 2 - Family Life', 'Chapter 3 - The End'],
        },
      ],
    },
    {
      id: 'feedbooks',
      name: 'Feedbooks',
      description: 'Public domain masterworks and self-published releases carefully curated for e-readers.',
      url: 'https://www.feedbooks.com/publicdomain/catalog.atom',
      iconBg: '#1e488f',
      iconType: 'feedbooks',
      books: [
        {
          id: 'fb-1',
          title: 'The Art of War',
          author: 'Sun Tzu',
          year: '5th C. BC',
          downloads: '29,400',
          genre: 'Philosophy & Strategy',
          language: 'English',
          fileSize: '310 KB',
          description:
            'The Art of War is an ancient Chinese military treatise dating from the Late Spring and Autumn Period. The work is attributed to the ancient Chinese military strategist Sun Tzu.',
          coverBg: '#2d1818',
          coverAccent: '#d84848',
          format: 'EPUB',
          chapters: ['I. Laying Plans', 'II. Waging War', 'III. Attack by Stratagem', 'IV. Tactical Dispositions'],
        },
        {
          id: 'fb-2',
          title: 'Twenty Thousand Leagues Under the Sea',
          author: 'Jules Verne',
          year: '1870',
          downloads: '24,800',
          genre: 'Science Fiction',
          language: 'English',
          fileSize: '950 KB',
          description:
            'Twenty Thousand Leagues Under the Sea tells the story of Captain Nemo and his submarine, the Nautilus, as seen from the perspective of Professor Pierre Aronnax.',
          coverBg: '#11222e',
          coverAccent: '#2ca4d8',
          format: 'EPUB',
          chapters: ['Part 1: A Shifting Reef', 'Part 1: The Pros and Cons', 'Part 1: As Monsieur Pleases'],
        },
        {
          id: 'fb-3',
          title: 'The Time Machine',
          author: 'H. G. Wells',
          year: '1895',
          downloads: '28,100',
          genre: 'Science Fiction',
          language: 'English',
          fileSize: '340 KB',
          description:
            'The Time Machine is a post-apocalyptic science fiction novella by H. G. Wells, published in 1895. The work is generally credited with the popularization of the concept of time travel using a vehicle.',
          coverBg: '#231e2d',
          coverAccent: '#8b5ce6',
          format: 'EPUB',
          chapters: ['Chapter 1 - Introduction', 'Chapter 2 - The Machine', 'Chapter 3 - The Time Traveller Returns'],
        },
      ],
    },
  ]);

  const [selectedCatalogId, setSelectedCatalogId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedGenre, setSelectedGenre] = useState<string>('All');
  const [selectedBook, setSelectedBook] = useState<CatalogBook | null>(null);

  // Downloads Queue State
  const [downloads, setDownloads] = useState<DownloadItem[]>([]);
  const [isDownloadsOpen, setIsDownloadsOpen] = useState(false);
  const [isCatalogInfoOpen, setIsCatalogInfoOpen] = useState(false);
  const [isAddCatalogOpen, setIsAddCatalogOpen] = useState(false);

  // New catalog form state
  const [newCatName, setNewCatName] = useState('');
  const [newCatUrl, setNewCatUrl] = useState('');

  const activeCatalog = catalogs.find((c) => c.id === selectedCatalogId) || null;

  // Filter books based on search query and genre
  const filteredBooks = useMemo(() => {
    if (!activeCatalog) return [];
    return activeCatalog.books.filter((book) => {
      const matchesSearch =
        searchQuery.trim() === '' ||
        book.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
        book.author.toLowerCase().includes(searchQuery.toLowerCase()) ||
        book.genre.toLowerCase().includes(searchQuery.toLowerCase());

      const matchesGenre =
        selectedGenre === 'All' || book.genre.toLowerCase().includes(selectedGenre.toLowerCase());

      return matchesSearch && matchesGenre;
    });
  }, [activeCatalog, searchQuery, selectedGenre]);

  // Handle Download Book
  const handleDownloadBook = async (book: CatalogBook) => {
    // Check if already downloading or downloaded
    const existing = downloads.find((d) => d.id === book.id);
    if (existing && existing.status === 'completed') return;

    const downloadEntry: DownloadItem = {
      id: book.id,
      bookTitle: book.title,
      author: book.author,
      catalogName: activeCatalog ? activeCatalog.name : 'OPDS',
      progress: 0,
      status: 'downloading',
      downloadDate: 'Just now',
    };

    setDownloads((prev) => [downloadEntry, ...prev.filter((d) => d.id !== book.id)]);

    // Simulate progressive download
    let cur = 15;
    const interval = setInterval(() => {
      cur += 25;
      if (cur >= 100) {
        clearInterval(interval);
        setDownloads((prev) =>
          prev.map((d) =>
            d.id === book.id
              ? { ...d, progress: 100, status: 'completed' }
              : d
          )
        );
        // Register in local library so it appears in Home & Library
        importBook(`${book.title.toLowerCase().replace(/\s+/g, '-')}.epub`).catch(console.error);
      } else {
        setDownloads((prev) =>
          prev.map((d) =>
            d.id === book.id ? { ...d, progress: cur } : d
          )
        );
      }
    }, 250);
  };

  const handleAddCatalogSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newCatName.trim() || !newCatUrl.trim()) return;

    const newCat: CatalogSite = {
      id: `custom-${Date.now()}`,
      name: newCatName.trim(),
      description: 'Custom user-defined OPDS Catalog feed.',
      url: newCatUrl.trim(),
      iconBg: '#444448',
      iconType: 'custom',
      books: [
        {
          id: `book-${Date.now()}-1`,
          title: 'Custom Feed Sample Book',
          author: 'Public Domain',
          year: '2024',
          downloads: '1,200',
          genre: 'General',
          language: 'English',
          fileSize: '512 KB',
          description: 'Sample book retrieved from custom OPDS catalog endpoint.',
          coverBg: '#222226',
          coverAccent: currentTheme.accent,
          format: 'EPUB',
        },
      ],
    };

    setCatalogs((prev) => [...prev, newCat]);
    setSelectedCatalogId(newCat.id);
    setNewCatName('');
    setNewCatUrl('');
    setIsAddCatalogOpen(false);
  };

  const completedDownloadsCount = downloads.filter((d) => d.status === 'completed').length;
  const activeDownloadsCount = downloads.filter((d) => d.status === 'downloading').length;

  return (
    <div className="flex h-full w-full select-none overflow-hidden relative">
      {/* ============================================================ */}
      {/* LEFT CATALOG SELECTOR (MATCHING win_022)                     */}
      {/* ============================================================ */}
      <div className="w-64 h-full flex flex-col border-r border-white/5 bg-black/25 backdrop-blur-md flex-shrink-0">
        {/* Top Header bar with + button matching win_022 */}
        <div className="h-12 border-b border-white/5 flex items-center justify-between px-3">
          <div className="flex items-center gap-2">
            <span className="text-[14px] font-semibold text-white tracking-tight">
              Catalogs
            </span>
          </div>
          <button
            type="button"
            onClick={() => setIsAddCatalogOpen(true)}
            className="w-8 h-8 rounded flex items-center justify-center text-neutral-300 hover:text-white hover:bg-white/10 transition-colors"
            title="Add OPDS Catalog"
          >
            <Plus size={18} />
          </button>
        </div>

        {/* Catalog List matching win_022 */}
        <div className="flex-1 overflow-y-auto p-2 space-y-1">
          {catalogs.map((catalog) => {
            const isSelected = selectedCatalogId === catalog.id;

            return (
              <button
                key={catalog.id}
                onClick={() => setSelectedCatalogId(catalog.id)}
                className={`w-full flex items-center gap-3 p-2.5 rounded-lg text-left transition-all ${
                  isSelected
                    ? 'bg-white/10 text-white shadow-sm'
                    : 'text-neutral-300 hover:bg-white/5 hover:text-white'
                }`}
              >
                {/* Authentic Catalog Badge Icon matching win_022 */}
                <div
                  className="w-10 h-10 rounded-lg flex items-center justify-center shrink-0 shadow"
                  style={{ backgroundColor: catalog.iconBg }}
                >
                  {catalog.iconType === 'gutenberg' && (
                    <svg className="w-6 h-6 fill-white" viewBox="0 0 24 24">
                      {/* Stylized Gutenberg G */}
                      <path d="M12 2L4 7v10l8 5 8-5V7l-8-5zm0 3.2L18 8.8v6.4L12 18.8l-6-3.6V8.8l6-3.6zm-1 4.3v4.5h2v-2.2h1.5v-1.8H13V9.5h-2z" />
                    </svg>
                  )}
                  {catalog.iconType === 'standard' && (
                    <div className="flex flex-col items-center justify-center text-white">
                      <div className="text-[12px] font-serif font-bold tracking-widest leading-none">
                        SE
                      </div>
                      <div className="w-4 h-0.5 bg-white/60 rounded-full mt-0.5" />
                    </div>
                  )}
                  {catalog.iconType === 'feedbooks' && (
                    <BookOpen size={20} className="text-white" />
                  )}
                  {catalog.iconType === 'custom' && (
                    <Layers size={20} className="text-white" />
                  )}
                </div>

                <div className="min-w-0 flex-1">
                  <div className="text-[13px] font-medium text-white truncate">
                    {catalog.name}
                  </div>
                  <div className="text-[11px] text-neutral-400 truncate mt-0.5">
                    {catalog.books.length} books available
                  </div>
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* ============================================================ */}
      {/* RIGHT DETAIL PANE (MATCHING win_022 & win_023)              */}
      {/* ============================================================ */}
      <div className="flex-1 h-full flex flex-col overflow-hidden bg-transparent">
        {/* Top Action Toolbar matching win_022 */}
        <div className="h-12 border-b border-white/5 px-4 flex items-center justify-between bg-black/10 backdrop-blur-sm">
          {/* Left Actions */}
          <div className="flex items-center gap-1">
            {/* Downloads queue button with badge */}
            <button
              type="button"
              onClick={() => setIsDownloadsOpen(true)}
              className="relative p-2 rounded text-neutral-300 hover:text-white hover:bg-white/10 transition-colors"
              title="Downloads Queue"
            >
              <Download size={18} />
              {(activeDownloadsCount > 0 || completedDownloadsCount > 0) && (
                <span
                  className="absolute top-1 right-1 w-4 h-4 rounded-full text-[10px] font-bold text-white flex items-center justify-center shadow"
                  style={{ backgroundColor: currentTheme.accent }}
                >
                  {activeDownloadsCount > 0 ? activeDownloadsCount : completedDownloadsCount}
                </span>
              )}
            </button>

            {/* Info button */}
            <button
              type="button"
              onClick={() => {
                if (activeCatalog) setIsCatalogInfoOpen(true);
              }}
              disabled={!activeCatalog}
              className="p-2 rounded text-neutral-300 hover:text-white hover:bg-white/10 transition-colors disabled:opacity-30"
              title="Catalog Information"
            >
              <Info size={18} />
            </button>
          </div>

          {/* Right Navigation Actions matching win_022 */}
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={() => {
                setSearchQuery('');
                setSelectedGenre('All');
              }}
              className="p-2 rounded text-neutral-300 hover:text-white hover:bg-white/10 transition-colors"
              title="Catalog Home"
            >
              <Home size={18} />
            </button>

            <button
              type="button"
              onClick={() => {
                // Refresh animation trigger
                const b = activeCatalog;
                if (b) {
                  setSelectedCatalogId(null);
                  setTimeout(() => setSelectedCatalogId(b.id), 50);
                }
              }}
              className="p-2 rounded text-neutral-300 hover:text-white hover:bg-white/10 transition-colors"
              title="Refresh"
            >
              <RotateCw size={17} />
            </button>

            <button
              type="button"
              onClick={() => setSelectedCatalogId(null)}
              className="p-2 rounded text-neutral-300 hover:text-white hover:bg-white/10 transition-colors"
              title="Back"
            >
              <ArrowLeft size={18} />
            </button>

            <button
              type="button"
              disabled
              className="p-2 rounded text-neutral-500 cursor-not-allowed"
              title="Forward"
            >
              <ArrowRight size={18} />
            </button>
          </div>
        </div>

        {/* Content Body Area */}
        <div className="flex-1 overflow-y-auto">
          {!activeCatalog ? (
            /* Empty State Matching win_022 exact text */
            <div className="h-full w-full flex items-center justify-center select-none text-neutral-300 text-[14px]">
              Select the site to start downloading eBooks
            </div>
          ) : (
            /* Active Catalog Explorer */
            <div className="p-8 space-y-6 max-w-6xl mx-auto">
              {/* Catalog Title & Search Header */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-white/5">
                <div>
                  <h1 className="text-[22px] font-semibold text-white tracking-tight">
                    {activeCatalog.name}
                  </h1>
                  <p className="text-[12px] text-neutral-400 mt-0.5">
                    {activeCatalog.description}
                  </p>
                </div>

                {/* Search Bar */}
                <div className="relative w-full sm:w-72">
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder={`Search ${activeCatalog.name}...`}
                    className="w-full bg-black/40 border border-white/10 rounded-lg pl-9 pr-4 py-1.5 text-[13px] text-white focus:outline-none focus:border-neutral-400 transition-colors"
                  />
                  <Search size={15} className="absolute left-3 top-2.5 text-neutral-400 pointer-events-none" />
                  {searchQuery && (
                    <button
                      type="button"
                      onClick={() => setSearchQuery('')}
                      className="absolute right-2.5 top-2.5 text-neutral-400 hover:text-white"
                    >
                      <X size={14} />
                    </button>
                  )}
                </div>
              </div>

              {/* Genre Filter Chips */}
              <div className="flex flex-wrap gap-2 pt-1">
                {[
                  'All',
                  'Classic Fiction',
                  'Philosophy',
                  'Gothic Horror',
                  'Adventure',
                  'Science Fiction',
                  'American Literature',
                ].map((genre) => {
                  const isActive = selectedGenre === genre;
                  return (
                    <button
                      key={genre}
                      type="button"
                      onClick={() => setSelectedGenre(genre)}
                      className={`px-3 py-1 rounded-full text-[12px] font-medium transition-all ${
                        isActive
                          ? 'text-white shadow-sm'
                          : 'bg-white/5 text-neutral-400 hover:bg-white/10 hover:text-neutral-200'
                      }`}
                      style={{
                        backgroundColor: isActive ? currentTheme.accent : undefined,
                      }}
                    >
                      {genre}
                    </button>
                  );
                })}
              </div>

              {/* Catalog Books Grid */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5 pt-2">
                {filteredBooks.map((book) => {
                  const downloadStatus = downloads.find((d) => d.id === book.id);
                  const isCompleted = downloadStatus?.status === 'completed';
                  const isDownloading = downloadStatus?.status === 'downloading';

                  return (
                    <div
                      key={book.id}
                      onClick={() => setSelectedBook(book)}
                      className="bg-[#1c1c1f]/90 border border-white/5 hover:border-white/20 rounded-xl p-4 flex flex-col justify-between cursor-pointer transition-all duration-200 hover:-translate-y-1 shadow-md group"
                    >
                      <div>
                        {/* Book Cover Preview Tile */}
                        <div
                          className="w-full h-44 rounded-lg flex flex-col justify-between p-4 relative overflow-hidden shadow-inner mb-3.5"
                          style={{ backgroundColor: book.coverBg }}
                        >
                          {/* Accent Spine Line */}
                          <div
                            className="absolute left-0 top-0 bottom-0 w-1.5"
                            style={{ backgroundColor: book.coverAccent }}
                          />

                          <div className="space-y-1 pl-2">
                            <span
                              className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full inline-block"
                              style={{
                                backgroundColor: `${book.coverAccent}30`,
                                color: book.coverAccent,
                              }}
                            >
                              {book.format}
                            </span>
                            <h3 className="text-[15px] font-semibold text-white leading-tight font-serif pt-1 line-clamp-3">
                              {book.title}
                            </h3>
                          </div>

                          <div className="pl-2">
                            <div className="text-[12px] text-neutral-300 font-medium">
                              {book.author}
                            </div>
                            <div className="text-[10px] text-neutral-400">
                              {book.year}
                            </div>
                          </div>
                        </div>

                        {/* Title and Author in card */}
                        <h4 className="text-[14px] font-medium text-white line-clamp-1 group-hover:text-white">
                          {book.title}
                        </h4>
                        <p className="text-[12px] text-neutral-400 line-clamp-1 mt-0.5">
                          {book.author}
                        </p>

                        <p className="text-[11px] text-neutral-400 line-clamp-2 mt-2 leading-relaxed">
                          {book.description}
                        </p>
                      </div>

                      {/* Card Footer with Download Action */}
                      <div className="pt-4 mt-3 border-t border-white/5 flex items-center justify-between">
                        <span className="text-[11px] text-neutral-400">
                          {book.fileSize}
                        </span>

                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDownloadBook(book);
                          }}
                          disabled={isDownloading}
                          className="px-3 py-1.5 rounded text-[12px] font-medium transition-all flex items-center gap-1.5 shadow"
                          style={{
                            backgroundColor: isCompleted
                              ? '#22c55e'
                              : isDownloading
                              ? '#404044'
                              : currentTheme.accent,
                            color: '#ffffff',
                          }}
                        >
                          {isCompleted ? (
                            <>
                              <Check size={13} />
                              <span>In Library</span>
                            </>
                          ) : isDownloading ? (
                            <>
                              <Clock size={13} className="animate-spin" />
                              <span>{downloadStatus?.progress}%</span>
                            </>
                          ) : (
                            <>
                              <Download size={13} />
                              <span>Download</span>
                            </>
                          )}
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>

              {filteredBooks.length === 0 && (
                <div className="py-16 text-center text-neutral-400 text-[14px]">
                  No books found matching "{searchQuery}".
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* ============================================================ */}
      {/* BOOK DETAILS MODAL / INSPECTOR                               */}
      {/* ============================================================ */}
      {selectedBook && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-[#1e1e22] border border-white/15 rounded-2xl max-w-2xl w-full p-6 shadow-2xl relative space-y-6">
            <button
              type="button"
              onClick={() => setSelectedBook(null)}
              className="absolute right-5 top-5 p-2 rounded-full text-neutral-400 hover:text-white hover:bg-white/10 transition-colors"
            >
              <X size={18} />
            </button>

            <div className="flex flex-col sm:flex-row gap-6">
              {/* High-Res Book Cover Preview */}
              <div
                className="w-44 h-60 rounded-xl shrink-0 flex flex-col justify-between p-4 shadow-lg relative overflow-hidden"
                style={{ backgroundColor: selectedBook.coverBg }}
              >
                <div
                  className="absolute left-0 top-0 bottom-0 w-2"
                  style={{ backgroundColor: selectedBook.coverAccent }}
                />
                <div className="pl-3">
                  <span
                    className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full inline-block"
                    style={{
                      backgroundColor: `${selectedBook.coverAccent}30`,
                      color: selectedBook.coverAccent,
                    }}
                  >
                    {selectedBook.format}
                  </span>
                  <h2 className="text-[17px] font-semibold text-white leading-tight font-serif mt-2">
                    {selectedBook.title}
                  </h2>
                </div>
                <div className="pl-3">
                  <div className="text-[13px] text-neutral-200 font-medium font-serif">
                    {selectedBook.author}
                  </div>
                  <div className="text-[11px] text-neutral-400">
                    {selectedBook.year}
                  </div>
                </div>
              </div>

              {/* Book Metadata & Synopsis */}
              <div className="flex-1 space-y-3">
                <div>
                  <h2 className="text-[20px] font-semibold text-white">
                    {selectedBook.title}
                  </h2>
                  <div className="text-[14px] text-neutral-300 mt-0.5">
                    by <span className="text-white font-medium">{selectedBook.author}</span>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-2 text-[12px] py-1 border-y border-white/10">
                  <div>
                    <span className="text-neutral-400">Genre: </span>
                    <span className="text-white">{selectedBook.genre}</span>
                  </div>
                  <div>
                    <span className="text-neutral-400">Language: </span>
                    <span className="text-white">{selectedBook.language}</span>
                  </div>
                  <div>
                    <span className="text-neutral-400">Downloads: </span>
                    <span className="text-white">{selectedBook.downloads}</span>
                  </div>
                  <div>
                    <span className="text-neutral-400">File size: </span>
                    <span className="text-white">{selectedBook.fileSize}</span>
                  </div>
                </div>

                <div className="text-[13px] text-neutral-300 leading-relaxed max-h-36 overflow-y-auto pr-1">
                  {selectedBook.description}
                </div>

                {/* Chapter list preview */}
                {selectedBook.chapters && (
                  <div className="pt-2">
                    <span className="text-[11px] font-medium text-neutral-400 uppercase tracking-wider">
                      Contents Preview:
                    </span>
                    <div className="mt-1 space-y-0.5 text-[11px] text-neutral-300">
                      {selectedBook.chapters.map((ch, i) => (
                        <div key={i} className="truncate">• {ch}</div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Action Bar */}
            <div className="flex justify-between items-center pt-4 border-t border-white/10">
              <span className="text-[12px] text-neutral-400">
                Public Domain • Open License
              </span>

              <div className="flex gap-3">
                <button
                  type="button"
                  onClick={() => setSelectedBook(null)}
                  className="px-4 py-2 rounded text-[13px] text-neutral-300 hover:bg-white/10"
                >
                  Close
                </button>

                <button
                  type="button"
                  onClick={() => handleDownloadBook(selectedBook)}
                  className="px-6 py-2 rounded text-[13px] font-medium text-white shadow-lg flex items-center gap-2"
                  style={{ backgroundColor: currentTheme.accent }}
                >
                  <Download size={15} />
                  <span>Download to Library</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ============================================================ */}
      {/* DOWNLOADS DRAWER / MODAL (CLICKING ↓ ICON)                  */}
      {/* ============================================================ */}
      {isDownloadsOpen && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex justify-end">
          <div className="w-96 h-full bg-[#1c1c1f] border-l border-white/10 p-6 flex flex-col justify-between shadow-2xl">
            <div className="space-y-4">
              <div className="flex items-center justify-between pb-3 border-b border-white/10">
                <div className="flex items-center gap-2">
                  <Download size={18} style={{ color: currentTheme.accent }} />
                  <h3 className="text-[16px] font-semibold text-white">
                    Downloads ({downloads.length})
                  </h3>
                </div>
                <button
                  type="button"
                  onClick={() => setIsDownloadsOpen(false)}
                  className="p-1.5 text-neutral-400 hover:text-white"
                >
                  <X size={18} />
                </button>
              </div>

              {downloads.length === 0 ? (
                <div className="py-12 text-center text-[13px] text-neutral-400">
                  No downloads yet. Browse catalogs and click "Download" on any book!
                </div>
              ) : (
                <div className="space-y-3 overflow-y-auto max-h-[75vh]">
                  {downloads.map((item) => (
                    <div
                      key={item.id}
                      className="p-3 rounded-lg bg-black/30 border border-white/5 space-y-2"
                    >
                      <div className="flex justify-between items-start">
                        <div>
                          <div className="text-[13px] font-medium text-white line-clamp-1">
                            {item.bookTitle}
                          </div>
                          <div className="text-[11px] text-neutral-400">
                            {item.author} • {item.catalogName}
                          </div>
                        </div>
                        {item.status === 'completed' && (
                          <span className="text-[11px] text-emerald-400 font-medium flex items-center gap-1">
                            <Check size={12} />
                            <span>Done</span>
                          </span>
                        )}
                      </div>

                      {item.status === 'downloading' && (
                        <div className="space-y-1">
                          <div className="w-full bg-neutral-700 h-1.5 rounded-full overflow-hidden">
                            <div
                              className="h-full transition-all duration-200"
                              style={{
                                width: `${item.progress}%`,
                                backgroundColor: currentTheme.accent,
                              }}
                            />
                          </div>
                          <div className="text-[10px] text-neutral-400 text-right">
                            {item.progress}%
                          </div>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>

            <button
              type="button"
              onClick={() => setIsDownloadsOpen(false)}
              className="w-full py-2 rounded bg-white/10 hover:bg-white/15 text-white text-[13px] font-medium transition-colors"
            >
              Close
            </button>
          </div>
        </div>
      )}

      {/* ============================================================ */}
      {/* CATALOG INFO MODAL                                           */}
      {/* ============================================================ */}
      {isCatalogInfoOpen && activeCatalog && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-[#1e1e20] border border-white/15 rounded-xl p-6 max-w-md w-full shadow-2xl space-y-4">
            <h3 className="text-[16px] font-semibold text-white">
              Catalog Information
            </h3>
            <div className="space-y-2 text-[13px] text-neutral-300">
              <div>
                <span className="text-neutral-400">Name: </span>
                <span className="text-white font-medium">{activeCatalog.name}</span>
              </div>
              <div>
                <span className="text-neutral-400">OPDS Feed URL: </span>
                <div className="font-mono text-[11px] text-neutral-300 bg-black/40 p-2 rounded mt-1 break-all">
                  {activeCatalog.url}
                </div>
              </div>
              <div className="pt-1">
                <span className="text-neutral-400">Description: </span>
                <p className="text-[12px] text-neutral-300 mt-1">
                  {activeCatalog.description}
                </p>
              </div>
            </div>
            <div className="flex justify-end pt-2">
              <button
                type="button"
                onClick={() => setIsCatalogInfoOpen(false)}
                className="px-4 py-1.5 rounded text-[13px] text-white font-medium"
                style={{ backgroundColor: currentTheme.accent }}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ============================================================ */}
      {/* ADD OPDS CATALOG MODAL                                       */}
      {/* ============================================================ */}
      {isAddCatalogOpen && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <form
            onSubmit={handleAddCatalogSubmit}
            className="bg-[#1e1e20] border border-white/15 rounded-xl p-6 max-w-md w-full shadow-2xl space-y-4"
          >
            <h3 className="text-[16px] font-semibold text-white">
              Add OPDS Catalog
            </h3>
            <p className="text-[12px] text-neutral-400">
              Enter the name and OPDS / Atom XML feed URL of the book repository:
            </p>
            <div className="space-y-3">
              <div>
                <label className="text-[12px] text-neutral-300 font-medium">Catalog Name</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. My Calibre Library"
                  value={newCatName}
                  onChange={(e) => setNewCatName(e.target.value)}
                  className="w-full mt-1 bg-black/40 border border-white/15 rounded px-3 py-1.5 text-[13px] text-white focus:outline-none focus:border-neutral-400"
                />
              </div>
              <div>
                <label className="text-[12px] text-neutral-300 font-medium">Feed URL</label>
                <input
                  type="url"
                  required
                  placeholder="http://192.168.1.100:8080/opds"
                  value={newCatUrl}
                  onChange={(e) => setNewCatUrl(e.target.value)}
                  className="w-full mt-1 bg-black/40 border border-white/15 rounded px-3 py-1.5 text-[13px] text-white focus:outline-none focus:border-neutral-400 font-mono"
                />
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-3">
              <button
                type="button"
                onClick={() => setIsAddCatalogOpen(false)}
                className="px-3 py-1.5 rounded text-[13px] text-neutral-300 hover:bg-white/10"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="px-4 py-1.5 rounded text-[13px] text-white font-medium shadow"
                style={{ backgroundColor: currentTheme.accent }}
              >
                Add Catalog
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
};

export default CatalogsView;
