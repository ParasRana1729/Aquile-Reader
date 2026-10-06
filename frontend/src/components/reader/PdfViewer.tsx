import React, { useEffect, useRef, useState, useCallback, useMemo } from 'react';
import * as pdfjsLib from 'pdfjs-dist';
import pdfWorker from 'pdfjs-dist/build/pdf.worker.min.mjs?url';
import 'pdfjs-dist/web/pdf_viewer.css';
import { PageBoundaryBadge } from './PageBoundaryBadge';
import { ReaderSettings, READER_THEMES } from '../../types/reader';

// Configure worker
if (pdfjsLib.GlobalWorkerOptions && !pdfjsLib.GlobalWorkerOptions.workerSrc) {
  pdfjsLib.GlobalWorkerOptions.workerSrc = pdfWorker;
}

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

const BUFFER_PAGES = 2; // Keep current visible pages +/- 2 pages in memory

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

  // Layout measurements
  const [containerWidth, setContainerWidth] = useState<number>(() => {
    if (typeof window !== 'undefined' && window.innerWidth > 0) {
      return window.innerWidth;
    }
    return 800;
  });

  // Virtualization window tracking
  const [visibleRange, setVisibleRange] = useState<{ min: number; max: number }>({ min: 1, max: 1 });
  const visiblePagesSet = useRef<Set<number>>(new Set([1]));

  // DOM node references
  const pageRefs = useRef<Map<number, HTMLDivElement>>(new Map());

  // Active rendering tasks and completed renders tracking
  const activeRenderTasks = useRef<Map<number, pdfjsLib.RenderTask>>(new Map());
  const renderedPages = useRef<Set<number>>(new Set());
  const renderQueueTimer = useRef<number | null>(null);

  const currentTheme = READER_THEMES[settings.theme] || READER_THEMES.night;
  const isDual = settings.spreadMode === 'dual' || settings.isTwoColumn;

  // Jump to specific page handler
  const jumpToPage = useCallback((pageNum: number) => {
    const el = pageRefs.current.get(pageNum);
    if (el) {
      el.scrollIntoView({ behavior: 'auto', block: 'start' });
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

  // Measure container width
  useEffect(() => {
    if (!containerRef.current) return;
    const updateWidth = () => {
      if (containerRef.current) {
        setContainerWidth(containerRef.current.clientWidth || 800);
      }
    };
    updateWidth();

    const resizeObserver = new ResizeObserver(updateWidth);
    resizeObserver.observe(containerRef.current);
    return () => resizeObserver.disconnect();
  }, []);

  // Compute standard page CSS dimensions
  const computedPageWidth = useMemo(() => {
    const availableWidth = isDual
      ? (containerWidth - 80) / 2
      : Math.min(containerWidth - 48, 860);
    return Math.max(280, Math.floor(availableWidth * settings.zoom));
  }, [containerWidth, isDual, settings.zoom]);

  // Load PDF Document & instantly initialize all pages with Page 1 aspect ratio
  useEffect(() => {
    let isCancelled = false;
    setLoading(true);
    setError(null);
    renderedPages.current.clear();

    // Cancel any previous tasks
    activeRenderTasks.current.forEach((task) => {
      try {
        task.cancel();
      } catch {}
    });
    activeRenderTasks.current.clear();

    const loadingTask = pdfjsLib.getDocument({ url });
    loadingTask.promise
      .then(async (doc) => {
        if (isCancelled) return;
        setPdfDoc(doc);
        const total = doc.numPages;
        onPageChange(1, total);

        // Fetch Page 1 to get baseline aspect ratio immediately (sub-50ms opening)
        const page1 = await doc.getPage(1);
        const vp1 = page1.getViewport({ scale: 1 });
        const defaultRatio = vp1.width / vp1.height;

        const pagesMeta: PageData[] = Array.from({ length: total }, (_, i) => ({
          pageNumber: i + 1,
          width: vp1.width,
          height: vp1.height,
          aspectRatio: defaultRatio,
        }));

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
      activeRenderTasks.current.forEach((task) => {
        try {
          task.cancel();
        } catch {}
      });
      activeRenderTasks.current.clear();
      loadingTask.destroy();
    };
  }, [url]);

  // Unload page canvas to reclaim GPU memory immediately
  const unloadPage = useCallback((pageNum: number) => {
    // 1. Cancel active render task if any
    const activeTask = activeRenderTasks.current.get(pageNum);
    if (activeTask) {
      try {
        activeTask.cancel();
      } catch {}
      activeRenderTasks.current.delete(pageNum);
    }

    // 2. Free canvas backing store from memory
    const pageDiv = pageRefs.current.get(pageNum);
    if (pageDiv) {
      const canvas = pageDiv.querySelector<HTMLCanvasElement>('canvas');
      if (canvas) {
        canvas.width = 0;
        canvas.height = 0;
        const ctx = canvas.getContext('2d');
        if (ctx) ctx.clearRect(0, 0, 0, 0);
      }
      const textLayerDiv = pageDiv.querySelector<HTMLDivElement>('.textLayer');
      if (textLayerDiv) {
        textLayerDiv.innerHTML = '';
      }
    }

    renderedPages.current.delete(pageNum);
  }, []);

  // Render a specific page canvas and text selection layer safely
  const renderPage = useCallback(
    async (pageNum: number) => {
      if (!pdfDoc) return;
      const pageDiv = pageRefs.current.get(pageNum);
      if (!pageDiv) return;

      const canvas = pageDiv.querySelector<HTMLCanvasElement>('canvas');
      const textLayerDiv = pageDiv.querySelector<HTMLDivElement>('.textLayer');
      if (!canvas || !textLayerDiv) return;

      // Cancel any ongoing render task for this page
      const existingTask = activeRenderTasks.current.get(pageNum);
      if (existingTask) {
        try {
          existingTask.cancel();
        } catch {}
        activeRenderTasks.current.delete(pageNum);
      }

      try {
        const page = await pdfDoc.getPage(pageNum);
        const unscaledViewport = page.getViewport({ scale: 1.0 });

        // Update aspect ratio if page differs from standard
        const actualRatio = unscaledViewport.width / unscaledViewport.height;

        const targetScale = computedPageWidth / unscaledViewport.width;
        const viewport = page.getViewport({ scale: targetScale });

        // Cap devicePixelRatio to 2 to prevent excessive GPU texture memory on 4K/HiDPI screens
        const pixelRatio = Math.min(window.devicePixelRatio || 1, 2);

        canvas.width = Math.floor(viewport.width * pixelRatio);
        canvas.height = Math.floor(viewport.height * pixelRatio);
        canvas.style.width = `${Math.floor(viewport.width)}px`;
        canvas.style.height = `${Math.floor(viewport.height)}px`;

        const ctx = canvas.getContext('2d', { alpha: false });
        if (!ctx) return;

        const renderContext = {
          canvasContext: ctx,
          canvas: canvas,
          viewport: viewport,
          transform: [pixelRatio, 0, 0, pixelRatio, 0, 0],
        };

        const renderTask = page.render(renderContext as any);
        activeRenderTasks.current.set(pageNum, renderTask);

        await renderTask.promise;
        activeRenderTasks.current.delete(pageNum);
        renderedPages.current.add(pageNum);

        // Render Text Layer
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
          // Non-fatal text layer warning
        }
      } catch (err: any) {
        if (err?.name === 'RenderingCancelledException') {
          return; // Normal cancellation during fast scroll
        }
        console.warn(`Render error on page ${pageNum}:`, err);
      }
    },
    [pdfDoc, computedPageWidth]
  );

  // Manage virtualization buffer window
  const updateVirtualizationWindow = useCallback(
    (minVisible: number, maxVisible: number) => {
      if (pages.length === 0) return;

      const bufferMin = Math.max(1, minVisible - BUFFER_PAGES);
      const bufferMax = Math.min(pages.length, maxVisible + BUFFER_PAGES);

      // Unload pages that are outside the buffer window
      renderedPages.current.forEach((renderedPageNum) => {
        if (renderedPageNum < bufferMin || renderedPageNum > bufferMax) {
          unloadPage(renderedPageNum);
        }
      });

      // Render pages that are within the buffer window
      for (let p = bufferMin; p <= bufferMax; p++) {
        if (!renderedPages.current.has(p) && !activeRenderTasks.current.has(p)) {
          renderPage(p);
        }
      }
    },
    [pages.length, unloadPage, renderPage]
  );

  // Intersection Observer for continuous vertical scroll & page tracking
  useEffect(() => {
    if (!containerRef.current || pages.length === 0) return;

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          const pageNum = Number(entry.target.getAttribute('data-page-number'));
          if (entry.isIntersecting) {
            visiblePagesSet.current.add(pageNum);
          } else {
            visiblePagesSet.current.delete(pageNum);
          }
        });

        if (visiblePagesSet.current.size > 0) {
          const sorted = Array.from(visiblePagesSet.current).sort((a, b) => a - b);
          const minVisible = sorted[0];
          const maxVisible = sorted[sorted.length - 1];

          setVisibleRange({ min: minVisible, max: maxVisible });
          onPageChange(minVisible, pages.length);

          // Debounce fast scrolling to avoid rendering intermediate pages
          if (renderQueueTimer.current) {
            window.clearTimeout(renderQueueTimer.current);
          }
          renderQueueTimer.current = window.setTimeout(() => {
            updateVirtualizationWindow(minVisible, maxVisible);
          }, 60);
        }
      },
      {
        root: containerRef.current,
        threshold: 0.1,
      }
    );

    pageRefs.current.forEach((el) => {
      if (el) observer.observe(el);
    });

    return () => {
      observer.disconnect();
      if (renderQueueTimer.current) {
        window.clearTimeout(renderQueueTimer.current);
      }
    };
  }, [pages, onPageChange, updateVirtualizationWindow]);

  // Re-render visible buffer on zoom, dual spread, or window resize changes
  useEffect(() => {
    renderedPages.current.clear();
    activeRenderTasks.current.forEach((task) => {
      try {
        task.cancel();
      } catch {}
    });
    activeRenderTasks.current.clear();

    const timer = setTimeout(() => {
      updateVirtualizationWindow(visibleRange.min, visibleRange.max);
    }, 80);

    return () => clearTimeout(timer);
  }, [settings.zoom, settings.spreadMode, settings.isTwoColumn, computedPageWidth, updateVirtualizationWindow, visibleRange.min, visibleRange.max]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      activeRenderTasks.current.forEach((task) => {
        try {
          task.cancel();
        } catch {}
      });
      activeRenderTasks.current.clear();
      renderedPages.current.clear();
    };
  }, []);

  if (loading) {
    return (
      <div
        className="flex flex-col items-center justify-center h-full w-full space-y-3"
        style={{
          backgroundColor: currentTheme.bg,
          color: currentTheme.text,
        }}
      >
        <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
        <span className="text-xs text-neutral-400 font-sans tracking-wide">
          Rendering PDF Sanctum...
        </span>
      </div>
    );
  }

  if (error) {
    return (
      <div
        className="flex flex-col items-center justify-center h-full w-full p-6 text-center select-none"
        style={{
          backgroundColor: currentTheme.bg,
          color: currentTheme.text,
        }}
      >
        <div className="text-red-400 font-medium mb-2">Failed to load PDF</div>
        <div className="text-xs opacity-70 max-w-md">{error}</div>
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
      {/* Two-page spread mode vs single column */}
      <div
        className={`mx-auto py-12 ${
          isDual
            ? 'grid grid-cols-2 gap-6 max-w-7xl px-6'
            : 'flex flex-col items-center max-w-4xl px-4'
        }`}
      >
        {pages.map((p) => {
          const pageHeight = Math.floor(computedPageWidth / p.aspectRatio);
          const isInBuffer =
            p.pageNumber >= visibleRange.min - BUFFER_PAGES &&
            p.pageNumber <= visibleRange.max + BUFFER_PAGES;

          return (
            <div
              key={p.pageNumber}
              ref={(el) => {
                if (el) pageRefs.current.set(p.pageNumber, el);
                else pageRefs.current.delete(p.pageNumber);
              }}
              data-page-number={p.pageNumber}
              className="w-full flex flex-col items-center my-4"
              style={{
                minHeight: `${pageHeight}px`,
              }}
            >
              {/* Page Canvas Container with fixed placeholder aspect ratio */}
              <div
                className="relative shadow-2xl overflow-hidden"
                style={{
                  width: `${computedPageWidth}px`,
                  minHeight: `${pageHeight}px`,
                  backgroundColor: currentTheme.pageBg,
                  boxShadow: currentTheme.isDark
                    ? '0 10px 30px rgba(0, 0, 0, 0.5)'
                    : '0 10px 25px rgba(0, 0, 0, 0.08)',
                }}
              >
                <canvas className="block" />
                <div className="textLayer absolute inset-0 select-text pointer-events-auto" />

                {/* Lightweight placeholder indicator when page is not yet rendered */}
                {!isInBuffer && (
                  <div className="absolute inset-0 flex flex-col items-center justify-center opacity-30 select-none pointer-events-none">
                    <span className="text-xs font-serif italic text-neutral-500">
                      Page {p.pageNumber}
                    </span>
                  </div>
                )}
              </div>

              {/* Continuous Page Boundary Badge */}
              <PageBoundaryBadge
                currentPage={p.pageNumber}
                totalPages={pages.length}
                theme={settings.theme}
              />
            </div>
          );
        })}
      </div>
    </div>
  );
};
