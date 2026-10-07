import JSZip from 'jszip';
import { TOCItem } from '../types/reader';

export interface EpubPage {
  pageNumber: number; // 1-based (1, 2, ... N)
  chapterTitle?: string;
  paragraphs: string[];
  images?: string[];
  anchorIds?: string[];
}

export interface ParsedEpubBook {
  title: string;
  author: string;
  pages: EpubPage[];
  toc: TOCItem[];
}

interface PaginationOptions {
  fontSize?: number;
  zoom?: number;
  bookTitle?: string;
}

function resolveZipPath(baseDir: string, relativePath: string): string {
  if (!baseDir) return relativePath.replace(/^\/+/, '');
  const combined = baseDir + relativePath;
  const parts = combined.split('/');
  const resolved: string[] = [];
  for (const part of parts) {
    if (part === '.' || part === '') continue;
    if (part === '..') {
      resolved.pop();
    } else {
      resolved.push(part);
    }
  }
  return resolved.join('/');
}

function decodeHtmlEntities(str: string): string {
  return str
    .replace(/&shy;/g, '')
    .replace(/\u00ad/g, '')
    .replace(/\u200b/g, '')
    .replace(/&nbsp;/g, ' ')
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&rsquo;/g, '’')
    .replace(/&lsquo;/g, '‘')
    .replace(/&rdquo;/g, '”')
    .replace(/&ldquo;/g, '“')
    .replace(/&mdash;/g, '—')
    .replace(/&ndash;/g, '–')
    .replace(/&#(\d+);/g, (_, dec) => String.fromCharCode(parseInt(dec, 10)))
    .replace(/&#x([0-9a-fA-F]+);/g, (_, hex) => String.fromCharCode(parseInt(hex, 16)));
}

const PRESERVE_COMPOUND_HYPHENS = new Set([
  'dark-eyed', 'dried-up', 'e-book', 'fifty-six', 'four-leaf', 'half-destroyed',
  'hundred-plus', 'modern-day', 'non-exclusive', 'non-transferable', 'on-screen',
  'one-tenth', 'sand-covered', 'self-awareness', 'sun-filled', 'thirty-eight',
  'well-heeled', 'chrome-plated', 'content-type', 'text-align', 'all-inclusive',
  'state-of-the-art', 'first-class', 'part-time', 'full-time'
]);

/**
 * Strips soft hyphens and heals artificial line-wrap hyphenation baked into OCR / EPUB text
 * (e.g. "con-sisted" -> "consisted", "im-petus" -> "impetus", "com-fortable" -> "comfortable").
 */
export function cleanPrintHyphens(text: string): string {
  if (!text) return '';
  const clean = text.replace(/[\u00ad\u200b]/g, '');

  return clean.replace(/\b([a-zA-Z]{2,})-([a-zA-Z]{2,})\b/g, (match, p1, p2) => {
    const lower = match.toLowerCase();
    if (PRESERVE_COMPOUND_HYPHENS.has(lower)) return match;

    // Preserve Title-Case / proper compounds like Al-Fayoum, Pan-American, Sonntag-Aktuell
    if (p1[0] === p1[0].toUpperCase() && p2[0] === p2[0].toUpperCase()) {
      return match;
    }
    // Preserve common hyphen prefixes
    const p1Lower = p1.toLowerCase();
    if (['al', 'pan', 'non', 'self', 'half', 'well', 'multi', 'cross', 'post', 'quasi', 'neo'].includes(p1Lower)) {
      return match;
    }
    // Preserve phrases with 'in', 'to', 'of', 'and' (e.g. 'Man-in', 'face-to')
    const p2Lower = p2.toLowerCase();
    if (['in', 'to', 'of', 'on', 'and', 'or', 'the'].includes(p2Lower)) {
      return match;
    }

    // Typical syllable breaks from print justification:
    // e.g. con-sisted, im-petus, com-fortable, penetra-tion, em-broidered, build-ing
    return p1 + p2;
  });
}

/**
 * Splits a very long paragraph into sentence-boundary chunks that fit nicely on a page.
 */
function makeSpacedRegex(text: string): RegExp | null {
  if (!text || text.length < 3) return null;
  const words = text.split(/\s+/).filter(Boolean);
  if (words.length === 0) return null;
  const wordPatterns = words.map((w) =>
    w
      .split('')
      .map((ch) => ch.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
      .join('\\s*')
  );
  return new RegExp('^\\s*' + wordPatterns.join('\\s+') + '\\s*', 'i');
}

function splitParagraphIntoChunks(paragraph: string, maxChunkLength: number): string[] {
  if (paragraph.length <= maxChunkLength) return [paragraph];
  
  const sentences = paragraph.match(/[^.!?]+[.!?]+(?:\s+|$)|[^.!?]+$/g) || [paragraph];
  const chunks: string[] = [];
  let currentChunk = '';

  for (const sentence of sentences) {
    if (currentChunk.length + sentence.length > maxChunkLength && currentChunk.trim().length > 0) {
      chunks.push(currentChunk.trim());
      currentChunk = sentence;
    } else {
      currentChunk += sentence;
    }
  }

  if (currentChunk.trim().length > 0) {
    chunks.push(currentChunk.trim());
  }

  return chunks;
}

/**
 * Clean room EPUB parser and paginator for native Aquile Reader.
 * Parses OPF, NCX, HTML chapters, suppresses inline print page number artifacts,
 * and splits content into authentic Aquile Reader pages.
 */
export async function parseEpubToPages(
  data: ArrayBuffer,
  options: PaginationOptions = {}
): Promise<ParsedEpubBook> {
  const zip = await JSZip.loadAsync(data);

  // 1. Locate package OPF file
  const containerXml = await zip.file('META-INF/container.xml')?.async('text');
  let opfPath = 'OEBPS/content.opf';
  if (containerXml) {
    const rootfileMatch = containerXml.match(/full-path=["']([^"']+)["']/i);
    if (rootfileMatch && rootfileMatch[1]) {
      opfPath = rootfileMatch[1];
    }
  }

  let opfFile = zip.file(opfPath);
  if (!opfFile) {
    // Search any .opf
    const opfEntries = zip.file(/\.opf$/i);
    if (opfEntries.length > 0) {
      opfPath = opfEntries[0].name;
      opfFile = opfEntries[0];
    }
  }

  if (!opfFile) {
    throw new Error('Invalid EPUB: package OPF file not found');
  }

  const opfDir = opfPath.includes('/') ? opfPath.substring(0, opfPath.lastIndexOf('/') + 1) : '';
  const opfText = await opfFile.async('text');

  // 2. Parse title and author metadata
  const titleMatch = opfText.match(/<dc:title[^>]*>([^<]+)<\/dc:title>/i);
  const bookTitle = titleMatch ? decodeHtmlEntities(titleMatch[1].trim()) : (options.bookTitle || 'Untitled Book');

  const authorMatch = opfText.match(/<dc:creator[^>]*>([^<]+)<\/dc:creator>/i);
  const author = authorMatch ? decodeHtmlEntities(authorMatch[1].trim()) : 'Unknown Author';

  // 3. Parse manifest
  const manifestMap = new Map<string, { href: string; mediaType: string }>();
  const itemRegex = /<item\s+[^>]*id=["']([^"']+)["'][^>]*href=["']([^"']+)["'][^>]*media-type=["']([^"']+)["'][^>]*\/?>|<item\s+[^>]*href=["']([^"']+)["'][^>]*id=["']([^"']+)["'][^>]*media-type=["']([^"']+)["'][^>]*\/?>/gi;
  let m;
  while ((m = itemRegex.exec(opfText)) !== null) {
    const id = m[1] || m[5];
    const href = m[2] || m[4];
    const mediaType = m[3] || m[6];
    if (id && href) {
      manifestMap.set(id, { href: resolveZipPath(opfDir, href), mediaType });
    }
  }

  // 4. Parse spine itemref order
  const spineItems: { idref: string; href: string }[] = [];
  const itemrefRegex = /<itemref\s+[^>]*idref=["']([^"']+)["'][^>]*\/?>/gi;
  let ir;
  while ((ir = itemrefRegex.exec(opfText)) !== null) {
    const idref = ir[1];
    const item = manifestMap.get(idref);
    if (item) {
      spineItems.push({ idref, href: item.href });
    }
  }

  // Fallback: if spine empty, take all xhtml/html items from manifest
  if (spineItems.length === 0) {
    manifestMap.forEach((val, key) => {
      if (val.mediaType.includes('html') || val.href.endsWith('.html') || val.href.endsWith('.xhtml')) {
        spineItems.push({ idref: key, href: val.href });
      }
    });
  }

  // 5. Extract chapters & paragraphs with running header / page number suppression
  const titleLower = bookTitle.toLowerCase();
  const authorLower = author.toLowerCase();
  const spacedTitleRegex = makeSpacedRegex(bookTitle);
  const spacedAuthorRegex = makeSpacedRegex(author);

  const rawChapters: {
    href: string;
    title?: string;
    paragraphs: { text: string; anchorId?: string; isHeading?: boolean }[];
  }[] = [];

  for (const item of spineItems) {
    const file = zip.file(item.href);
    if (!file) continue;

    const htmlContent = await file.async('text');
    let chapterTitle: string | undefined;

    // Check title in <title> or first <h1>
    const docTitleMatch = htmlContent.match(/<title[^>]*>([^<]+)<\/title>/i);
    if (docTitleMatch && docTitleMatch[1].trim()) {
      chapterTitle = decodeHtmlEntities(docTitleMatch[1].trim());
    }

    const paragraphs: { text: string; anchorId?: string; isHeading?: boolean }[] = [];

    // Parse HTML DOM in browser environment
    if (typeof DOMParser !== 'undefined') {
      const parser = new DOMParser();
      const doc = parser.parseFromString(htmlContent, 'text/html');

      // Strip script/style
      doc.querySelectorAll('script, style, noscript').forEach((el) => el.remove());

      // Suppress known inline page-number and running header elements:
      // Elements with epub:type="pagebreak", class containing pagebreak/page-number, etc.
      const pageArtifacts = doc.querySelectorAll(
        '[epub\\:type="pagebreak"], [role="doc-pagebreak"], .pagebreak, .page-break, .page-number, .pagenumber, .calibre_page'
      );
      pageArtifacts.forEach((el) => el.remove());

      // Strip inline child elements that are isolated print page numbers, e.g. <i class="calibre3">17</i>
      const inlineNumberTags = doc.querySelectorAll('i, span, em, b, small, sup, sub, a');
      inlineNumberTags.forEach((tag) => {
        const t = tag.textContent?.trim() || '';
        if (/^\d{1,5}$/.test(t)) {
          tag.remove();
        }
      });

      // Query body elements in document order
      const elements = doc.querySelectorAll('p, h1, h2, h3, h4, h5, h6, blockquote, div');
      for (let i = 0; i < elements.length; i++) {
        const el = elements[i];
        // Only leaf or direct container blocks
        if (el.querySelector('p, h1, h2, h3, h4, blockquote')) {
          continue;
        }

        // Check for attached anchor id before stripping text
        const anchor = el.querySelector('a[id], a[name]') || (el.id ? el : null);
        const anchorId = anchor ? anchor.getAttribute('id') || anchor.getAttribute('name') || undefined : undefined;

        const rawText = el.textContent || '';
        let cleanText = cleanPrintHyphens(decodeHtmlEntities(rawText)).replace(/\s+/g, ' ').trim();
        if (!cleanText) continue;

        // Check if this paragraph is ONLY a print page number (e.g. "22")
        if (/^\d{1,5}$/.test(cleanText)) {
          continue;
        }

        // Strip leading spaced title/author running headers if present (e.g. "P a u l o  C o e l h o")
        if (spacedTitleRegex) {
          cleanText = cleanText.replace(spacedTitleRegex, '').trim();
        }
        if (spacedAuthorRegex) {
          cleanText = cleanText.replace(spacedAuthorRegex, '').trim();
        }
        if (!cleanText) continue;
        if (/^\d{1,5}$/.test(cleanText)) continue;

        // Check if this paragraph is a Calibre / print running header matching title or author
        const cleanLower = cleanText.toLowerCase();
        if (
          (titleLower && cleanLower === titleLower) ||
          (authorLower && cleanLower === authorLower) ||
          cleanLower === 'the alchemist' ||
          cleanLower === 'paulo coelho' ||
          cleanLower === 'the prince'
        ) {
          continue;
        }

        const isHeading = ['H1', 'H2', 'H3', 'H4', 'H5', 'H6'].includes(el.tagName);
        paragraphs.push({ text: cleanText, anchorId, isHeading });
      }
    } else {
      // Regex parsing fallback
      const pRegex = /<p[^>]*>([\s\S]*?)<\/p>/gi;
      let pm;
      while ((pm = pRegex.exec(htmlContent)) !== null) {
        const inner = pm[1];
        const anchorMatch = inner.match(/<a\s+[^>]*id=["']([^"']+)["']/i);
        const textOnly = cleanPrintHyphens(decodeHtmlEntities(inner.replace(/<[^>]+>/g, ''))).replace(/\s+/g, ' ').trim();
        if (!textOnly) continue;
        if (/^\d{1,5}$/.test(textOnly)) continue;
        const lower = textOnly.toLowerCase();
        if (lower === titleLower || lower === authorLower) continue;

        paragraphs.push({
          text: textOnly,
          anchorId: anchorMatch ? anchorMatch[1] : undefined,
          isHeading: false,
        });
      }
    }

    // Heal broken paragraphs artificially split by print page breaks
    const healedParagraphs: { text: string; anchorId?: string; isHeading?: boolean }[] = [];
    for (const p of paragraphs) {
      if (p.isHeading) {
        healedParagraphs.push(p);
        continue;
      }
      if (healedParagraphs.length > 0) {
        const last = healedParagraphs[healedParagraphs.length - 1];
        if (!last.isHeading) {
          const lastText = last.text.trim();
          const currText = p.text.trim();
          const endsWithHyphen = /[a-zA-Z]-$/.test(lastText);
          const endsWithTerminal = /[.!?]["'”’]?$/.test(lastText) || /[:;]$/.test(lastText);
          const startsWithLower = /^[a-z]/.test(currText);

          if (endsWithHyphen || (!endsWithTerminal && startsWithLower)) {
            if (endsWithHyphen) {
              last.text = cleanPrintHyphens(lastText.slice(0, -1) + currText);
            } else {
              last.text = lastText + ' ' + currText;
            }
            continue;
          }
        }
      }
      healedParagraphs.push(p);
    }

    if (healedParagraphs.length > 0) {
      rawChapters.push({
        href: item.href,
        title: chapterTitle,
        paragraphs: healedParagraphs,
      });
    }
  }

  // 6. Paginate paragraphs into discrete pages
  const zoomFactor = typeof options.zoom === 'number' && options.zoom > 0 ? options.zoom : 1.0;
  const effectiveFontSize = Math.max(12, Math.min(48, Math.round((options.fontSize || 18) * zoomFactor)));
  
  // Base characters per page: roughly 1400 chars at 18px font size
  const targetCharsPerPage = Math.max(
    700,
    Math.min(2200, Math.round(1500 / ((effectiveFontSize / 18) ** 1.1)))
  );

  const pages: EpubPage[] = [];
  // Map of href#anchor or href -> target pageNumber
  const anchorToPage = new Map<string, number>();

  let currentPageNum = 1;

  for (const chapter of rawChapters) {
    let currentParas: string[] = [];
    let currentAnchorIds: string[] = [];
    let currentLength = 0;
    let pageHasChapterTitle = false;

    // Record chapter entry point to first page of this chapter
    anchorToPage.set(chapter.href, currentPageNum);

    for (let pIdx = 0; pIdx < chapter.paragraphs.length; pIdx++) {
      const p = chapter.paragraphs[pIdx];

      if (p.anchorId) {
        anchorToPage.set(`${chapter.href}#${p.anchorId}`, currentPageNum);
        currentAnchorIds.push(p.anchorId);
      }

      // If paragraph is extraordinarily long, chunk it by sentence
      const pChunks = splitParagraphIntoChunks(p.text, targetCharsPerPage);

      for (let cIdx = 0; cIdx < pChunks.length; cIdx++) {
        const chunk = pChunks[cIdx];
        const isHeader = p.isHeading && cIdx === 0;

        // If page has reached capacity, push page and start new one
        if (currentParas.length > 0 && currentLength + chunk.length > targetCharsPerPage) {
          pages.push({
            pageNumber: currentPageNum,
            chapterTitle: !pageHasChapterTitle ? chapter.title : undefined,
            paragraphs: currentParas,
            anchorIds: currentAnchorIds.length > 0 ? [...currentAnchorIds] : undefined,
          });

          currentPageNum++;
          currentParas = [];
          currentAnchorIds = [];
          currentLength = 0;
          pageHasChapterTitle = true;
        }

        currentParas.push(chunk);
        currentLength += chunk.length;
      }
    }

    // Flush remaining paragraphs in chapter
    if (currentParas.length > 0) {
      pages.push({
        pageNumber: currentPageNum,
        chapterTitle: !pageHasChapterTitle ? chapter.title : undefined,
        paragraphs: currentParas,
        anchorIds: currentAnchorIds.length > 0 ? [...currentAnchorIds] : undefined,
      });
      currentPageNum++;
    }
  }

  // Fallback: If no pages created, make one empty page
  if (pages.length === 0) {
    pages.push({
      pageNumber: 1,
      paragraphs: ['No content found in EPUB.'],
    });
  }

  // 7. Parse Table of Contents from NCX if present
  const toc: TOCItem[] = [];
  const ncxItem = Array.from(manifestMap.values()).find(
    (item) => item.mediaType.includes('ncx') || item.href.endsWith('.ncx')
  );

  if (ncxItem) {
    const ncxFile = zip.file(ncxItem.href);
    const ncxContent = (await ncxFile?.async('text')) || '';
    const ncxDir = ncxItem.href.includes('/') ? ncxItem.href.substring(0, ncxItem.href.lastIndexOf('/') + 1) : '';

    const re = /<navPoint[^>]*>[\s\S]*?<text>([^<]+)<\/text>[\s\S]*?<content\s+src=["']([^"']+)["'][\s\S]*?<\/navPoint>/gi;
    let nm;
    let idx = 1;
    while ((nm = re.exec(ncxContent)) !== null) {
      const label = decodeHtmlEntities(nm[1].trim());
      const rawSrc = nm[2].trim();
      const resolvedSrc = resolveZipPath(ncxDir, rawSrc);
      const filenameSrc = resolvedSrc.split('/').pop() || resolvedSrc;

      // Find matching page
      const page = anchorToPage.get(resolvedSrc) || anchorToPage.get(filenameSrc) || anchorToPage.get(resolvedSrc.split('#')[0]) || 1;

      // Exclude generic cover/titlepage if redundant
      if (/^cover\s*image$/i.test(label) || /^title\s*page$/i.test(label)) {
        // keep or include
      }

      toc.push({
        id: `toc-${idx++}`,
        label,
        href: resolvedSrc,
        page,
      });
    }
  }

  // If no TOC from NCX, generate from chapters
  if (toc.length === 0) {
    rawChapters.forEach((ch, idx) => {
      const page = anchorToPage.get(ch.href) || 1;
      toc.push({
        id: `toc-${idx + 1}`,
        label: ch.title || `Chapter ${idx + 1}`,
        href: ch.href,
        page,
      });
    });
  }

  return {
    title: bookTitle,
    author,
    pages,
    toc,
  };
}
