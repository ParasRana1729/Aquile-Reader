import { BookWithProgress } from '../types/book';
import { Annotation, Bookmark, ReadingStats } from '../types/reader';

const isTauriEnv =
  typeof window !== 'undefined' &&
  ('__TAURI_INTERNALS__' in window || '__TAURI__' in window);

// Default mock books in case running outside Tauri
const FALLBACK_BOOKS: BookWithProgress[] = [
  {
    id: 'book-the-prince',
    title: 'The Prince',
    author: 'Nicolo Machiavelli',
    filePath: 'builtin://the-prince.pdf',
    format: 'pdf',
    coverImage: null,
    pageCount: 140,
    chapterCount: 26,
    fileSize: 1245184,
    isFavorite: false,
    addedDate: new Date().toISOString(),
    lastReadDate: new Date().toISOString(),
    percentage: 7.0,
    position: '{"page": 10}',
  },
  {
    id: 'book-mans-search',
    title: "Man's Search For Meaning",
    author: 'Viktor E. Frankl',
    filePath: 'builtin://mans-search.epub',
    format: 'epub',
    coverImage: null,
    pageCount: 200,
    chapterCount: 12,
    fileSize: 854200,
    isFavorite: false,
    addedDate: new Date().toISOString(),
    lastReadDate: new Date().toISOString(),
    percentage: 0.0,
    position: null,
  },
  {
    id: 'book-sherlock-holmes',
    title: 'The Adventures of Sherlock Holmes',
    author: 'Arthur Conan Doyle',
    filePath: 'builtin://sherlock-holmes.epub',
    format: 'epub',
    coverImage: null,
    pageCount: 307,
    chapterCount: 12,
    fileSize: 1560300,
    isFavorite: false,
    addedDate: new Date().toISOString(),
    lastReadDate: new Date().toISOString(),
    percentage: 0.0,
    position: null,
  },
  {
    id: 'book-quick-start',
    title: 'Quick Start Guide',
    author: 'Aquile Reader',
    filePath: 'builtin://quick-start-guide.epub',
    format: 'epub',
    coverImage: null,
    pageCount: 16,
    chapterCount: 4,
    fileSize: 452100,
    isFavorite: false,
    addedDate: new Date().toISOString(),
    lastReadDate: null,
    percentage: 0.0,
    position: null,
  },
];

let cachedMemoryBooks = [...FALLBACK_BOOKS];

export async function fetchBooks(): Promise<BookWithProgress[]> {
  if (isTauriEnv) {
    try {
      const { invoke } = await import('@tauri-apps/api/core');
      const books = await invoke<BookWithProgress[]>('list_books');
      return books;
    } catch (e) {
      console.warn('Tauri list_books failed, using fallback:', e);
    }
  }
  return [...cachedMemoryBooks];
}

export async function fetchRecentReads(limit: number = 4): Promise<BookWithProgress[]> {
  if (isTauriEnv) {
    try {
      const { invoke } = await import('@tauri-apps/api/core');
      const recents = await invoke<BookWithProgress[]>('get_recent_reads', { limit });
      return recents;
    } catch (e) {
      console.warn('Tauri get_recent_reads failed, using fallback:', e);
    }
  }
  return cachedMemoryBooks.slice(0, limit);
}

export async function importBook(filePath: string): Promise<BookWithProgress> {
  if (isTauriEnv) {
    const { invoke } = await import('@tauri-apps/api/core');
    return await invoke<BookWithProgress>('import_book', { filePath });
  }

  // Web fallback
  const filename = filePath.split('/').pop() || 'Imported Book';
  const newBook: BookWithProgress = {
    id: `book-${Date.now()}`,
    title: filename.replace(/\.[^/.]+$/, '').replace(/[-_]/g, ' '),
    author: 'Local File',
    filePath,
    format: (filePath.split('.').pop() || 'epub').toLowerCase(),
    coverImage: null,
    pageCount: 100,
    chapterCount: 5,
    fileSize: 1024000,
    isFavorite: false,
    addedDate: new Date().toISOString(),
    lastReadDate: null,
    percentage: 0,
    position: null,
  };
  cachedMemoryBooks.unshift(newBook);
  return newBook;
}

export async function deleteBook(bookId: string): Promise<void> {
  if (isTauriEnv) {
    try {
      const { invoke } = await import('@tauri-apps/api/core');
      await invoke('delete_book', { bookId });
    } catch (e) {
      console.warn('Tauri delete_book failed:', e);
    }
  }
  cachedMemoryBooks = cachedMemoryBooks.filter((b) => b.id !== bookId);
}

export async function updateProgress(
  bookId: string,
  percentage: number,
  position?: string
): Promise<void> {
  if (isTauriEnv) {
    try {
      const { invoke } = await import('@tauri-apps/api/core');
      await invoke('update_progress', { bookId, percentage, position });
    } catch (e) {
      console.warn('Tauri update_progress failed:', e);
    }
  }

  const book = cachedMemoryBooks.find((b) => b.id === bookId);
  if (book) {
    book.percentage = percentage;
    book.position = position || null;
    book.lastReadDate = new Date().toISOString();
  }
}

export async function toggleFavorite(bookId: string): Promise<boolean> {
  if (isTauriEnv) {
    try {
      const { invoke } = await import('@tauri-apps/api/core');
      return await invoke<boolean>('toggle_favorite', { bookId });
    } catch (e) {
      console.warn('Tauri toggle_favorite failed:', e);
    }
  }

  const book = cachedMemoryBooks.find((b) => b.id === bookId);
  if (book) {
    book.isFavorite = !book.isFavorite;
    return book.isFavorite;
  }
  return false;
}

export async function pickBookFile(): Promise<string | null> {
  if (isTauriEnv) {
    try {
      const { open } = await import('@tauri-apps/plugin-dialog');
      const selected = await open({
        multiple: false,
        filters: [
          {
            name: 'Supported Books (*.epub, *.pdf, *.cbz, *.cbr)',
            extensions: ['epub', 'pdf', 'cbz', 'cbr'],
          },
        ],
      });
      if (typeof selected === 'string') {
        return selected;
      }
    } catch (e) {
      console.warn('Dialog open failed:', e);
    }
  }
  return null;
}

// ----------------- Book Binary / Object URL Resolution -----------------

export async function readBookBytes(filePath: string): Promise<Uint8Array | null> {
  if (isTauriEnv) {
    try {
      const { invoke } = await import('@tauri-apps/api/core');
      const bytes = await invoke<number[]>('read_book_bytes', { filePath });
      return new Uint8Array(bytes);
    } catch (e) {
      console.warn('Failed to read book bytes via Tauri IPC:', e);
    }
  }
  return null;
}

export async function resolveBookContent(book: {
  id: string;
  filePath: string;
  format: string;
}): Promise<string> {
  const fp = book.filePath || '';
  const fmt = (book.format || '').toLowerCase();

  // 1. Builtin fixtures mapping
  if (fp.startsWith('builtin://')) {
    if (fp.includes('prince') || fmt === 'pdf') {
      return '/fixtures/sample-doc.pdf';
    }
    if (fp.includes('comic') || fmt === 'cbz' || fmt === 'cbr') {
      return '/fixtures/sample-comic.cbz';
    }
    return '/fixtures/canonical-text.epub';
  }

  // 2. Direct HTTP/HTTPS or public relative URLs
  if (fp.startsWith('http://') || fp.startsWith('https://') || fp.startsWith('/fixtures/')) {
    return fp;
  }

  // 3. Native local file path in Tauri
  if (isTauriEnv) {
    const bytes = await readBookBytes(fp);
    if (bytes) {
      let mimeType = 'application/octet-stream';
      if (fmt === 'pdf' || fp.endsWith('.pdf')) {
        mimeType = 'application/pdf';
      } else if (fmt === 'epub' || fp.endsWith('.epub')) {
        mimeType = 'application/epub+zip';
      } else if (fmt === 'cbz' || fp.endsWith('.cbz') || fp.endsWith('.zip')) {
        mimeType = 'application/vnd.comicbook+zip';
      }
      const blob = new Blob([bytes.buffer as ArrayBuffer], { type: mimeType });
      return URL.createObjectURL(blob);
    }
  }

  // Fallback fixtures if file cannot be read
  if (fmt === 'pdf') return '/fixtures/sample-doc.pdf';
  if (fmt === 'cbz' || fmt === 'cbr') return '/fixtures/sample-comic.cbz';
  return '/fixtures/canonical-text.epub';
}

// ----------------- Annotations Operations -----------------

export async function fetchAnnotations(bookId?: string): Promise<Annotation[]> {
  if (isTauriEnv) {
    try {
      const { invoke } = await import('@tauri-apps/api/core');
      const res = await invoke<Annotation[]>('list_annotations', { bookId: bookId || null });
      return res.map((a) => ({
        ...a,
        text: a.selectedText || a.text || '',
        page: a.cfiRange && a.cfiRange.includes('page') ? JSON.parse(a.cfiRange).page : 1,
      }));
    } catch (e) {
      console.warn('fetchAnnotations failed:', e);
    }
  }

  // Fallback annotations
  const defaultAnnotations: Annotation[] = [
    {
      id: 'ann-seed-1',
      bookId: 'book-the-prince',
      bookTitle: 'The Prince',
      selectedText:
        'All states, all powers, that have held and hold rule over men have been and are either republics or principalities.',
      text: 'All states, all powers, that have held and hold rule over men have been and are either republics or principalities.',
      note: 'Crucial political dichotomy established in opening sentence.',
      color: '#d41b6c',
      page: 23,
      createdAt: Date.now() - 3600000,
    },
    {
      id: 'ann-seed-2',
      bookId: 'book-mans-search',
      bookTitle: "Man's Search For Meaning",
      selectedText: "Those who have a 'why' to live, can bear with almost any 'how'.",
      text: "Those who have a 'why' to live, can bear with almost any 'how'.",
      note: 'Core thesis of logotherapy.',
      color: '#ffeb3b',
      page: 15,
      createdAt: Date.now() - 7200000,
    },
  ];

  if (bookId) {
    return defaultAnnotations.filter((a) => a.bookId === bookId);
  }
  return defaultAnnotations;
}

export async function saveAnnotation(annotation: Annotation): Promise<void> {
  if (isTauriEnv) {
    try {
      const { invoke } = await import('@tauri-apps/api/core');
      await invoke('add_annotation', {
        annotation: {
          id: annotation.id,
          bookId: annotation.bookId || 'book-the-prince',
          cfiRange: annotation.cfiRange || JSON.stringify({ page: annotation.page || 1 }),
          selectedText: annotation.selectedText || annotation.text || '',
          note: annotation.note || null,
          color: annotation.color || '#ffeb3b',
          createdAt: typeof annotation.createdAt === 'number' ? new Date(annotation.createdAt).toISOString() : annotation.createdAt,
          updatedAt: new Date().toISOString(),
        },
      });
      return;
    } catch (e) {
      console.warn('saveAnnotation failed:', e);
    }
  }
}

export async function removeAnnotation(annotationId: string): Promise<void> {
  if (isTauriEnv) {
    try {
      const { invoke } = await import('@tauri-apps/api/core');
      await invoke('delete_annotation', { annotationId });
      return;
    } catch (e) {
      console.warn('removeAnnotation failed:', e);
    }
  }
}

// ----------------- Bookmarks Operations -----------------

export async function fetchBookmarks(bookId: string): Promise<Bookmark[]> {
  if (isTauriEnv) {
    try {
      const { invoke } = await import('@tauri-apps/api/core');
      return await invoke<Bookmark[]>('list_bookmarks', { bookId });
    } catch (e) {
      console.warn('fetchBookmarks failed:', e);
    }
  }

  // Fallback bookmarks
  return [
    {
      id: 'bm-seed-1',
      bookId,
      page: 23,
      title: 'Chapter I Overview',
      excerpt: 'All states, all powers, that have held and hold rule over men...',
      createdAt: Date.now() - 86400000,
    },
  ];
}

export async function saveBookmark(bookmark: Bookmark): Promise<void> {
  if (isTauriEnv) {
    try {
      const { invoke } = await import('@tauri-apps/api/core');
      await invoke('add_bookmark', {
        bookmark: {
          id: bookmark.id,
          bookId: bookmark.bookId || 'book-the-prince',
          page: bookmark.page,
          title: bookmark.title,
          excerpt: bookmark.excerpt || null,
          createdAt: typeof bookmark.createdAt === 'number' ? new Date(bookmark.createdAt).toISOString() : bookmark.createdAt,
        },
      });
      return;
    } catch (e) {
      console.warn('saveBookmark failed:', e);
    }
  }
}

export async function removeBookmark(bookmarkId: string): Promise<void> {
  if (isTauriEnv) {
    try {
      const { invoke } = await import('@tauri-apps/api/core');
      await invoke('delete_bookmark', { bookmarkId });
      return;
    } catch (e) {
      console.warn('removeBookmark failed:', e);
    }
  }
}

// ----------------- Reading Sessions & Insights -----------------

export async function recordReadingSession(session: {
  id: string;
  bookId: string;
  startTime: string;
  endTime?: string | null;
  durationSeconds: number;
  wordsRead: number;
}): Promise<void> {
  if (isTauriEnv) {
    try {
      const { invoke } = await import('@tauri-apps/api/core');
      await invoke('record_reading_session', { session });
      return;
    } catch (e) {
      console.warn('recordReadingSession failed:', e);
    }
  }
}

export async function fetchReadingStats(): Promise<ReadingStats> {
  if (isTauriEnv) {
    try {
      const { invoke } = await import('@tauri-apps/api/core');
      return await invoke<ReadingStats>('get_reading_stats');
    } catch (e) {
      console.warn('fetchReadingStats failed:', e);
    }
  }

  // Fallback mock stats
  return {
    totalBooksRead: 4,
    totalReadingTimeSeconds: 5400,
    totalWordsRead: 14200,
    totalDaysRead: 3,
    currentStreakDays: 3,
    recordStreakDays: 7,
    avgReadingTimePerDayMinutes: 30,
    avgSpeedWpm: 245,
    monthlyStats: [
      { month: 'Jan', daysRead: 0, readingTimeMinutes: 0, pagesRead: 0 },
      { month: 'Feb', daysRead: 0, readingTimeMinutes: 0, pagesRead: 0 },
      { month: 'Mar', daysRead: 0, readingTimeMinutes: 0, pagesRead: 0 },
      { month: 'Apr', daysRead: 0, readingTimeMinutes: 0, pagesRead: 0 },
      { month: 'May', daysRead: 0, readingTimeMinutes: 0, pagesRead: 0 },
      { month: 'Jun', daysRead: 0, readingTimeMinutes: 0, pagesRead: 0 },
      { month: 'Jul', daysRead: 0, readingTimeMinutes: 0, pagesRead: 0 },
      { month: 'Aug', daysRead: 0, readingTimeMinutes: 0, pagesRead: 0 },
      { month: 'Sep', daysRead: 2, readingTimeMinutes: 45, pagesRead: 32 },
      { month: 'Oct', daysRead: 3, readingTimeMinutes: 90, pagesRead: 64 },
      { month: 'Nov', daysRead: 0, readingTimeMinutes: 0, pagesRead: 0 },
      { month: 'Dec', daysRead: 0, readingTimeMinutes: 0, pagesRead: 0 },
    ],
  };
}
