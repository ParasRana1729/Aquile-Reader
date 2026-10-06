import * as pdfjsLib from 'pdfjs-dist';
import pdfWorker from 'pdfjs-dist/build/pdf.worker.min.mjs?url';
import { BookWithProgress } from '../types/book';
import { resolveBookContent, updateBookCover } from './ipc';

// Configure worker
if (pdfjsLib.GlobalWorkerOptions && !pdfjsLib.GlobalWorkerOptions.workerSrc) {
  pdfjsLib.GlobalWorkerOptions.workerSrc = pdfWorker;
}

// Concurrency queue to prevent multiple thumbnail extractions from choking the worker
let isProcessingQueue = false;
const thumbnailQueue: Array<() => Promise<void>> = [];

async function enqueueThumbnailTask(task: () => Promise<void>): Promise<void> {
  thumbnailQueue.push(task);
  if (isProcessingQueue) return;

  isProcessingQueue = true;
  while (thumbnailQueue.length > 0) {
    const next = thumbnailQueue.shift();
    if (next) {
      try {
        await next();
      } catch (e) {
        console.warn('Thumbnail generation task error:', e);
      }
    }
  }
  isProcessingQueue = false;
}

/**
 * Generate a thumbnail data URL (JPEG) from the first page of a PDF.
 * Immediately purges the canvas memory after generating the data URL.
 */
export async function generatePdfThumbnail(url: string, targetWidth = 320): Promise<string> {
  const loadingTask = pdfjsLib.getDocument({
    url,
    stopAtErrors: true,
  });

  let doc: pdfjsLib.PDFDocumentProxy | null = null;
  try {
    doc = await loadingTask.promise;
    const page = await doc.getPage(1);
    const unscaledViewport = page.getViewport({ scale: 1 });
    const scale = targetWidth / unscaledViewport.width;
    const viewport = page.getViewport({ scale });

    const canvas = document.createElement('canvas');
    canvas.width = Math.floor(viewport.width);
    canvas.height = Math.floor(viewport.height);

    const ctx = canvas.getContext('2d');
    if (!ctx) {
      throw new Error('Canvas 2d context unavailable');
    }

    await page.render({
      canvasContext: ctx,
      canvas: canvas,
      viewport: viewport,
    } as any).promise;

    const dataUrl = canvas.toDataURL('image/jpeg', 0.85);

    // Free backing store memory immediately
    canvas.width = 0;
    canvas.height = 0;
    ctx.clearRect(0, 0, 0, 0);

    return dataUrl;
  } finally {
    loadingTask.destroy();
  }
}

/**
 * Ensure a book has a high-quality raster thumbnail.
 * If the book is a PDF and has no cover or only a generic SVG placeholder,
 * generates a real thumbnail from page 1 and persists it to SQLite.
 */
export async function ensureBookCover(
  book: BookWithProgress,
  onCoverUpdated?: (bookId: string, coverUrl: string) => void
): Promise<string | null> {
  const fmt = (book.format || '').toLowerCase();
  if (fmt !== 'pdf') {
    return book.coverImage;
  }

  // If book already has a valid JPEG/PNG cover (not the generic SVG placeholder), return it
  if (
    book.coverImage &&
    !book.coverImage.startsWith('data:image/svg+xml') &&
    !book.coverImage.includes('<svg')
  ) {
    return book.coverImage;
  }

  return new Promise((resolve) => {
    enqueueThumbnailTask(async () => {
      let resolvedUrl = '';
      try {
        resolvedUrl = await resolveBookContent(book);
        const thumbnail = await generatePdfThumbnail(resolvedUrl);

        // Persist to SQLite and update memory model
        await updateBookCover(book.id, thumbnail);
        book.coverImage = thumbnail;

        if (onCoverUpdated) {
          onCoverUpdated(book.id, thumbnail);
        }
        resolve(thumbnail);
      } catch (err) {
        console.warn(`Failed to generate PDF thumbnail for book ${book.id}:`, err);
        resolve(book.coverImage);
      } finally {
        if (resolvedUrl && resolvedUrl.startsWith('blob:')) {
          URL.revokeObjectURL(resolvedUrl);
        }
      }
    });
  });
}
