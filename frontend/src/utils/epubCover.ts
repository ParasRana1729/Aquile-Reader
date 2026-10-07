import JSZip from 'jszip';
import { BookWithProgress } from '../types/book';
import { resolveBookContent, updateBookCover } from './ipc';

const coverCache = new Map<string, Promise<string | null>>();

function hasRealCover(book: BookWithProgress): boolean {
  return !!(
    book.coverImage &&
    !book.coverImage.startsWith('data:image/svg+xml') &&
    !book.coverImage.includes('<svg')
  );
}

function opfDir(opfPath: string): string {
  const idx = opfPath.lastIndexOf('/');
  return idx >= 0 ? opfPath.slice(0, idx + 1) : '';
}

function normalizeZipPath(base: string, href: string): string {
  const clean = href.split('#')[0].split('?')[0];
  if (!clean || clean.startsWith('/')) return clean.replace(/^\//, '');
  const parts = (base + clean).split('/');
  const out: string[] = [];
  for (const part of parts) {
    if (part === '' || part === '.') continue;
    if (part === '..') out.pop();
    else out.push(part);
  }
  return out.join('/');
}

async function findCoverPath(zip: JSZip, opfPath: string, opfText: string): Promise<string | null> {
  const doc = new DOMParser().parseFromString(opfText, 'application/xml');
  if (doc.querySelector('parsererror')) return null;
  const dir = opfDir(opfPath);

  const manifestItems = Array.from(doc.querySelectorAll('manifest > item'));
  const hrefOf = (id: string | null | undefined): string | null => {
    if (!id) return null;
    const item = manifestItems.find((el) => el.getAttribute('id') === id);
    const href = item?.getAttribute('href');
    return href ? normalizeZipPath(dir, href) : null;
  };

  // 1. EPUB 2 style: <meta name="cover" content="<manifest-id>"/>
  const metaCover = doc.querySelector('meta[name="cover"]')?.getAttribute('content');
  const viaMeta = hrefOf(metaCover);
  if (viaMeta && zip.file(viaMeta)) return viaMeta;

  // 2. EPUB 3 style: manifest item with properties="cover-image"
  for (const el of manifestItems) {
    const props = el.getAttribute('properties') || '';
    if (props.split(/\s+/).includes('cover-image')) {
      const href = el.getAttribute('href');
      const path = href ? normalizeZipPath(dir, href) : null;
      if (path && zip.file(path)) return path;
    }
  }

  // 3. Filename heuristic: cover.* anywhere in the archive
  const imageExts = ['.jpg', '.jpeg', '.png', '.gif', '.webp'];
  const candidates = Object.keys(zip.files).filter(
    (p) => !zip.files[p].dir && imageExts.some((ext) => p.toLowerCase().endsWith(ext))
  );
  const byName = candidates.find((p) => /(^|\/)cover\.[a-z]+$/i.test(p));
  if (byName) return byName;

  // 4. First manifest image (often the cover)
  for (const el of manifestItems) {
    const mediaType = el.getAttribute('media-type') || '';
    if (mediaType.startsWith('image/')) {
      const href = el.getAttribute('href');
      const path = href ? normalizeZipPath(dir, href) : null;
      if (path && zip.file(path)) return path;
    }
  }
  return null;
}

/**
 * Ensure an EPUB book has a real cover image.
 * Extracts the packaged cover via JSZip, persists it to SQLite, and reports
 * back through onCoverUpdated — mirroring ensureBookCover for PDFs.
 */
export async function ensureEpubCover(
  book: BookWithProgress,
  onCoverUpdated?: (bookId: string, coverUrl: string) => void
): Promise<string | null> {
  const fmt = (book.format || '').toLowerCase();
  if (fmt !== 'epub') return book.coverImage ?? null;
  if (hasRealCover(book)) return book.coverImage ?? null;

  const cached = coverCache.get(book.id);
  if (cached) return cached;

  const task = (async (): Promise<string | null> => {
    let resolvedUrl = '';
    try {
      resolvedUrl = await resolveBookContent({
        id: book.id,
        filePath: book.filePath,
        format: book.format,
      });
      const res = await fetch(resolvedUrl);
      if (!res.ok) return book.coverImage ?? null;
      const buf = await res.arrayBuffer();
      const zip = await JSZip.loadAsync(buf);

      const containerFile = zip.file('META-INF/container.xml');
      if (!containerFile) return book.coverImage ?? null;
      const containerText = await containerFile.async('text');
      const containerDoc = new DOMParser().parseFromString(containerText, 'application/xml');
      const rootfile =
        containerDoc.querySelector('rootfile')?.getAttribute('full-path') || 'OEBPS/content.opf';

      const opfFile = zip.file(rootfile);
      if (!opfFile) return book.coverImage ?? null;
      const opfText = await opfFile.async('text');

      const coverPath = await findCoverPath(zip, rootfile, opfText);
      if (!coverPath) return book.coverImage ?? null;
      const coverFile = zip.file(coverPath);
      if (!coverFile) return book.coverImage ?? null;

      // Persist as a data URL (like the PDF path): blob: URLs die with the
      // session and must never be written to SQLite.
      const blob = await coverFile.async('blob');
      const coverUrl = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result as string);
        reader.onerror = () => reject(reader.error);
        reader.readAsDataURL(blob);
      });

      await updateBookCover(book.id, coverUrl);
      book.coverImage = coverUrl;
      onCoverUpdated?.(book.id, coverUrl);
      return coverUrl;
    } catch (err) {
      console.warn(`Failed to extract EPUB cover for book ${book.id}:`, err);
      return book.coverImage ?? null;
    } finally {
      if (resolvedUrl.startsWith('blob:')) URL.revokeObjectURL(resolvedUrl);
    }
  })();

  coverCache.set(book.id, task);
  return task;
}
