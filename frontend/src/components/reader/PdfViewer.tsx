import React, { useEffect, useRef, useState, useCallback } from 'react';
import * as pdfjsLib from 'pdfjs-dist';
import pdfWorker from 'pdfjs-dist/build/pdf.worker.min.mjs?url';
import 'pdfjs-dist/web/pdf_viewer.css';
import { PageBoundaryBadge } from './PageBoundaryBadge';
import { ReaderSettings, READER_THEMES } from '../../types/reader';

// Configure worker
pdfjsLib.GlobalWorkerOptions.workerSrc = pdfWorker;

export interface PdfSearchResult {
  page: number;
  excerpt: string;
}

interface PdfViewerProps {
  url: string;
  settings: ReaderSettings;
  currentPage: number;
  onPageChange: (page: number, total: number) => void;
  searchQuery?: string;
  onJumpToPageRef?: React.MutableRefObject<((page: number) => void) | null>;
  onSearchRef?: React.MutableRefObject<((query: string) => Promise<PdfSearchResult[]>) | null>;
}

interface PageData {
  pageNumber: number;
  width: number;
  height: number;
  aspectRatio: number;
}

export const PdfViewer: React.FC<PdfViewerProps> = ({
  url,
  settings,
  currentPage,
  onPageChange,
  searchQuery,
  onJumpToPageRef,
  onSearchRef,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [pdfDoc, setPdfDoc] = useState<pdfjsLib.PDFDocumentProxy | null>(null);
  const [pages, setPages] = useState<PageData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const pageRefs = useRef<Map<number, HTMLDivElement>>(new Map());
  const renderedPages = useRef<Set<number>>(new Set());

  const currentTheme = READER_THEMES[settings.theme] || READER_THEMES.night;
  const isDual = settings.spreadMode === 'dual' || settings.isTwoColumn;

  // Jump to specific page handler
  const jumpToPage = useCallback((pageNum: number) => {
    const el = pageRefs.current.get(pageNum);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }, []);

  useEffect(() => {
    if (onJumpToPageRef) {
      onJumpToPageRef.current = jumpToPage;
    }
  }, [onJumpToPageRef, jumpToPage]);

  // Search handler across PDF pages
  const searchPdf = useCallback(
    async (query: string): Promise<PdfSearchResult[]> => {
      if (!pdfDoc || !query.trim()) return [];
      const results: PdfSearchResult[] = [];
      const lowerQuery = query.toLowerCase();

      for (let i = 1; i <= pdfDoc.numPages; i++) {
        try {
          const page = await pdfDoc.getPage(i);
          const textContent = await page.getTextContent();
          const str = textContent.items
            .map((item: any) => ('str' in item ? item.str : ''))
            .join(' ');
          const lowerStr = str.toLowerCase();

          let idx = lowerStr.indexOf(lowerQuery);
          while (idx !== -1) {
            const start = Math.max(0, idx - 25);
            const end = Math.min(str.length, idx + query.length + 25);
            const snippet =
              (start > 0 ? '...' : '') +
              str.slice(start, end).trim() +
              (end < str.length ? '...' : '');
            results.push({ page: i, excerpt: snippet });
            idx = lowerStr.indexOf(lowerQuery, idx + lowerQuery.length);
          }
        } catch (e) {
          console.warn(`Search error on PDF page ${i}:`, e);
        }
      }
      return results;
    },
    [pdfDoc]
  );

  useEffect(() => {
    if (onSearchRef) {
      onSearchRef.current = searchPdf;
    }
  }, [onSearchRef, searchPdf]);

  // Load PDF Document
  useEffect(() => {
    let isCancelled = false;
    setLoading(true);
    setError(null);
    renderedPages.current.clear();

    const loadingTask = pdfjsLib.getDocument({ url });
    loadingTask.promise
      .then(async (doc) => {
        if (isCancelled) return;
        setPdfDoc(doc);
        const total = doc.numPages;
        onPageChange(1, total);

        // Retrieve dimensions for all pages
        const pagesMeta: PageData[] = [];
        for (let i = 1; i <= total; i++) {
          const page = await doc.getPage(i);
          const vp = page.getViewport({ scale: 1 });
          pagesMeta.push({
            pageNumber: i,
            width: vp.width,
            height: vp.height,
            aspectRatio: vp.width / vp.height,
          });
        }
        if (!isCancelled) {
          setPages(pagesMeta);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (!isCancelled) {
          console.error('Failed to load PDF:', err);
          setError(err.message || 'Could not load PDF document.');
          setLoading(false);
        }
      });

    return () => {
      isCancelled = true;
      loadingTask.destroy();
    };
  }, [url]);

  // Render a specific page canvas and text selection layer
  const renderPage = useCallback(
    async (pageNum: number, container: HTMLDivElement) => {
      if (!pdfDoc) return;

      const page = await pdfDoc.getPage(pageNum);
      const canvas = container.querySelector<HTMLCanvasElement>('canvas');
      const textLayerDiv = container.querySelector<HTMLDivElement>('.textLayer');
      if (!canvas || !textLayerDiv) return;

      const pixelRatio = window.devicePixelRatio || 1;
      const baseScale = settings.zoom;
      // Fit container width if responsive
      const containerWidth = container.clientWidth || 800;
      const unscaledViewport = page.getViewport({ scale: 1.0 });
      const targetScale = (containerWidth / unscaledViewport.width) * baseScale;

      const viewport = page.getViewport({ scale: targetScale });

      // Canvas dimensions for vector sharpness
      canvas.width = Math.floor(viewport.width * pixelRatio);
      canvas.height = Math.floor(viewport.height * pixelRatio);
      canvas.style.width = `${Math.floor(viewport.width)}px`;
      canvas.style.height = `${Math.floor(viewport.height)}px`;

      const ctx = canvas.getContext('2d');
      if (!ctx) return;

      const renderContext = {
        canvasContext: ctx,
        canvas: canvas,
        viewport: viewport,
        transform: [pixelRatio, 0, 0, pixelRatio, 0, 0],
      };

      await page.render(renderContext).promise;

      // Text Layer for selection and search
      textLayerDiv.innerHTML = '';
      textLayerDiv.style.width = `${Math.floor(viewport.width)}px`;
      textLayerDiv.style.height = `${Math.floor(viewport.height)}px`;
      textLayerDiv.style.setProperty('--scale-factor', `${targetScale}`);

      try {
        const textContent = await page.getTextContent();
        const textLayer = new pdfjsLib.TextLayer({
          textContentSource: textContent,
          container: textLayerDiv,
          viewport: viewport,
        });
        await textLayer.render();
      } catch (err) {
        console.warn('Text layer render warning:', err);
      }
    },
    [pdfDoc, settings.zoom]
  );

  // Intersection Observer for continuous vertical scroll & page tracking
  useEffect(() => {
    if (!containerRef.current || pages.length === 0) return;

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          const pageNum = Number(entry.target.getAttribute('data-page-number'));
          if (entry.isIntersecting) {
            onPageChange(pageNum, pages.length);
            // Render on visibility
            const pageDiv = entry.target as HTMLDivElement;
            if (!renderedPages.current.has(pageNum)) {
              renderedPages.current.add(pageNum);
              renderPage(pageNum, pageDiv);
            }
          }
        });
      },
      {
        root: containerRef.current,
        threshold: 0.25,
      }
    );

    pageRefs.current.forEach((el) => {
      if (el) observer.observe(el);
    });

    return () => observer.disconnect();
  }, [pages, onPageChange, renderPage]);

  // Re-render when zoom, spreadMode or isTwoColumn changes
  useEffect(() => {
    renderedPages.current.clear();
    const timer = setTimeout(() => {
      pageRefs.current.forEach((el, pageNum) => {
        if (el) {
          renderPage(pageNum, el);
        }
      });
    }, 60);
    return () => clearTimeout(timer);
  }, [settings.zoom, settings.spreadMode, settings.isTwoColumn, renderPage]);

  // Re-render on window resize to fit responsive container width
  useEffect(() => {
    let resizeTimer: any;
    const handleResize = () => {
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(() => {
        renderedPages.current.clear();
        pageRefs.current.forEach((el, pageNum) => {
          if (el) renderPage(pageNum, el);
        });
      }, 150);
    };
    window.addEventListener('resize', handleResize);
    return () => {
      window.removeEventListener('resize', handleResize);
      clearTimeout(resizeTimer);
    };
  }, [renderPage]);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-full w-full space-y-3">
        <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
        <span className="text-xs text-neutral-400 font-sans tracking-wide">
          Rendering PDF Sanctum...
        </span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-full w-full p-6 text-center">
        <div className="text-red-400 font-medium mb-2">Failed to load PDF</div>
        <div className="text-xs text-neutral-400 max-w-md">{error}</div>
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className="flex-1 w-full h-full overflow-y-auto overflow-x-hidden relative select-text"
      style={{
        backgroundColor: currentTheme.bg,
        color: currentTheme.text,
      }}
    >
      {/* Two-page spread mode: grid grid-cols-2 side-by-side vs single column */}
      <div
        className={`mx-auto py-12 transition-all duration-300 ${
          isDual
            ? 'grid grid-cols-2 gap-6 max-w-7xl px-6'
            : 'flex flex-col items-center max-w-4xl px-4'
        }`}
      >
        {pages.map((p) => (
          <div
            key={p.pageNumber}
            ref={(el) => {
              if (el) pageRefs.current.set(p.pageNumber, el);
              else pageRefs.current.delete(p.pageNumber);
            }}
            data-page-number={p.pageNumber}
            className="w-full flex flex-col items-center my-4"
          >
            {/* Page Canvas Container */}
            <div
              className="relative shadow-2xl transition-all duration-200"
              style={{
                backgroundColor: currentTheme.pageBg,
                boxShadow: currentTheme.isDark
                  ? '0 10px 30px rgba(0, 0, 0, 0.5)'
                  : '0 10px 25px rgba(0, 0, 0, 0.08)',
              }}
            >
              <canvas className="block" />
              <div className="textLayer absolute inset-0 select-text pointer-events-auto" />
            </div>

            {/* Continuous Page Boundary Badge */}
            <PageBoundaryBadge
              currentPage={p.pageNumber}
              totalPages={pages.length}
              theme={settings.theme}
            />
          </div>
        ))}
      </div>
    </div>
  );
};
