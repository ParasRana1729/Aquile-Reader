import React, { useEffect, useState, useRef, useCallback } from 'react';
import JSZip from 'jszip';
import { PageBoundaryBadge } from './PageBoundaryBadge';
import { ReaderSettings, READER_THEMES } from '../../types/reader';
import { ZoomIn, ZoomOut, RotateCcw } from 'lucide-react';

interface ComicPage {
  index: number;
  filename: string;
  url: string;
}

interface ComicViewerProps {
  url?: string;
  pages?: string[]; // direct image URLs
  settings: ReaderSettings;
  currentPage: number;
  onPageChange: (page: number, total: number) => void;
  onJumpToPageRef?: React.MutableRefObject<((page: number) => void) | null>;
}

export const ComicViewer: React.FC<ComicViewerProps> = ({
  url = '/fixtures/sample-comic.cbz',
  pages: directPages,
  settings,
  currentPage,
  onPageChange,
  onJumpToPageRef,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [comicPages, setComicPages] = useState<ComicPage[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [zoomLevel, setZoomLevel] = useState<number>(settings.zoom || 1.0);

  const currentTheme = READER_THEMES[settings.theme] || READER_THEMES.night;
  const isDual = settings.spreadMode === 'dual' || settings.isTwoColumn;
  const pageRefs = useRef<Map<number, HTMLDivElement>>(new Map());

  // Jump to specific page
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

  // Load and extract CBZ or use direct pages
  useEffect(() => {
    let isCancelled = false;
    setLoading(true);
    setError(null);

    const loadComic = async () => {
      try {
        if (directPages && directPages.length > 0) {
          const list: ComicPage[] = directPages.map((pUrl, idx) => ({
            index: idx + 1,
            filename: `page_${idx + 1}.png`,
            url: pUrl,
          }));
          if (!isCancelled) {
            setComicPages(list);
            onPageChange(1, list.length);
            setLoading(false);
          }
          return;
        }

        // Fetch CBZ archive
        const response = await fetch(url);
        if (!response.ok) {
          throw new Error(`Failed to fetch comic archive (${response.status})`);
        }
        const arrayBuffer = await response.arrayBuffer();
        const zip = await JSZip.loadAsync(arrayBuffer);

        const imageFiles: { name: string; file: JSZip.JSZipObject }[] = [];
        zip.forEach((relativePath, zipEntry) => {
          if (!zipEntry.dir && /\.(png|jpe?g|webp|gif|avif)$/i.test(relativePath)) {
            // Ignore macOS metadata
            if (!relativePath.includes('__MACOSX') && !relativePath.startsWith('.')) {
              imageFiles.push({ name: relativePath, file: zipEntry });
            }
          }
        });

        // Natural sort by file name so 001_cover.png comes before 002_page1.png
        imageFiles.sort((a, b) =>
          a.name.localeCompare(b.name, undefined, { numeric: true, sensitivity: 'base' })
        );

        if (imageFiles.length === 0) {
          // Generate sample SVG comic pages if archive had no images
          const fallbackPages: ComicPage[] = Array.from({ length: 12 }, (_, i) => {
            const pageNum = i + 1;
            const svg = `
              <svg xmlns="http://www.w3.org/2000/svg" width="800" height="1200" viewBox="0 0 800 1200">
                <rect width="800" height="1200" fill="${pageNum === 1 ? '#1a1024' : '#1e1e24'}" stroke="#333" stroke-width="2"/>
                <circle cx="400" cy="400" r="180" fill="${pageNum === 1 ? '#d41b6c' : '#334155'}" opacity="0.3"/>
                <text x="400" y="380" fill="#eaeaea" font-size="42" font-family="sans-serif" font-weight="bold" text-anchor="middle">
                  ${pageNum === 1 ? 'AQUILE COMIC: COVER' : `PANEL SPREAD #${pageNum}`}
                </text>
                <text x="400" y="440" fill="#94a3b8" font-size="24" font-family="sans-serif" text-anchor="middle">
                  ${pageNum === 1 ? 'Volume I - Issue #1' : `Scene Act ${pageNum} - Illustrated Sequence`}
                </text>
                <rect x="100" y="550" width="600" height="480" rx="8" fill="#111116" stroke="#444" stroke-width="2"/>
                <text x="400" y="800" fill="#64748b" font-size="28" font-family="monospace" text-anchor="middle">
                  Graphic Novel Page ${pageNum}
                </text>
                <text x="400" y="1120" fill="#a1a1aa" font-size="18" font-family="serif" font-style="italic" text-anchor="middle">
                  ${pageNum} of 12
                </text>
              </svg>
            `;
            const blob = new Blob([svg], { type: 'image/svg+xml' });
            return {
              index: pageNum,
              filename: `mock_page_${pageNum}.svg`,
              url: URL.createObjectURL(blob),
            };
          });

          if (!isCancelled) {
            setComicPages(fallbackPages);
            onPageChange(1, fallbackPages.length);
            setLoading(false);
          }
          return;
        }

        // Convert files to Object URLs
        const loadedList: ComicPage[] = await Promise.all(
          imageFiles.map(async (entry, index) => {
            const blob = await entry.file.async('blob');
            const blobUrl = URL.createObjectURL(blob);
            return {
              index: index + 1,
              filename: entry.name,
              url: blobUrl,
            };
          })
        );

        if (!isCancelled) {
          setComicPages(loadedList);
          onPageChange(1, loadedList.length);
          setLoading(false);
        }
      } catch (err: any) {
        console.error('Failed to unpack comic:', err);
        if (!isCancelled) {
          setError(err.message || 'Failed to open comic book.');
          setLoading(false);
        }
      }
    };

    loadComic();

    return () => {
      isCancelled = true;
    };
  }, [url, directPages]);

  // Clean up object URLs on unmount
  useEffect(() => {
    return () => {
      comicPages.forEach((p) => {
        if (p.url.startsWith('blob:')) {
          URL.revokeObjectURL(p.url);
        }
      });
    };
  }, [comicPages]);

  // Compute spreads with COVER ISOLATION:
  // Spread 0: [Page 1] (Single isolated cover!)
  // Spread 1: [Page 2, Page 3]
  // Spread 2: [Page 4, Page 5] ...
  const spreads: ComicPage[][] = React.useMemo(() => {
    if (comicPages.length === 0) return [];
    if (!isDual) {
      // 1-column mode: each page is its own spread
      return comicPages.map((p) => [p]);
    }

    const list: ComicPage[][] = [];
    // Page 1 is isolated cover
    list.push([comicPages[0]]);

    // Subsequent pages paired in twos
    for (let i = 1; i < comicPages.length; i += 2) {
      if (i + 1 < comicPages.length) {
        list.push([comicPages[i], comicPages[i + 1]]);
      } else {
        list.push([comicPages[i]]);
      }
    }
    return list;
  }, [comicPages, isDual]);

  // Intersection observer for continuous scroll
  useEffect(() => {
    if (!containerRef.current || comicPages.length === 0) return;

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            const pageNum = Number(entry.target.getAttribute('data-comic-page'));
            if (pageNum) {
              onPageChange(pageNum, comicPages.length);
            }
          }
        });
      },
      {
        root: containerRef.current,
        threshold: 0.3,
      }
    );

    pageRefs.current.forEach((el) => {
      if (el) observer.observe(el);
    });

    return () => observer.disconnect();
  }, [comicPages, onPageChange]);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-full w-full space-y-3">
        <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
        <span className="text-xs text-neutral-400 font-sans tracking-wide">
          Extracting Comic Book Frames...
        </span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-full w-full p-6 text-center">
        <div className="text-red-400 font-medium mb-2">Error Loading Comic</div>
        <div className="text-xs text-neutral-400 max-w-md">{error}</div>
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className="flex-1 w-full h-full overflow-y-auto overflow-x-hidden relative select-none"
      style={{
        backgroundColor: currentTheme.bg,
        color: currentTheme.text,
      }}
    >
      {/* Zoom and layout overlay indicator */}
      <div className="fixed bottom-6 right-6 z-30 flex items-center gap-1.5 bg-black/60 backdrop-blur-md border border-white/10 px-3 py-1.5 rounded-full shadow-lg text-xs text-white">
        <button
          onClick={() => setZoomLevel((z) => Math.max(0.6, z - 0.15))}
          className="p-1 hover:bg-white/10 rounded-full transition-colors"
          title="Zoom Out"
        >
          <ZoomOut size={14} />
        </button>
        <span className="font-mono text-[11px] px-1">{Math.round(zoomLevel * 100)}%</span>
        <button
          onClick={() => setZoomLevel((z) => Math.min(2.5, z + 0.15))}
          className="p-1 hover:bg-white/10 rounded-full transition-colors"
          title="Zoom In"
        >
          <ZoomIn size={14} />
        </button>
        <button
          onClick={() => setZoomLevel(1.0)}
          className="p-1 hover:bg-white/10 rounded-full transition-colors ml-1 text-neutral-400 hover:text-white"
          title="Reset Zoom"
        >
          <RotateCcw size={13} />
        </button>
      </div>

      {/* Main Comic Spreads Canvas */}
      <div className="py-12 px-4 flex flex-col items-center justify-center min-h-full">
        {spreads.map((spread, sIndex) => {
          const isCover = sIndex === 0;
          const pageNumbersText =
            spread.length === 1
              ? `${spread[0].index} of ${comicPages.length}`
              : `${spread[0].index}-${spread[1].index} of ${comicPages.length}`;

          return (
            <div
              key={sIndex}
              className="flex flex-col items-center my-6 max-w-full transition-transform duration-200"
              style={{
                transform: `scale(${zoomLevel})`,
                transformOrigin: 'top center',
              }}
            >
              {/* Spread container: single page for cover, side-by-side for spread */}
              <div
                className={`flex items-center justify-center gap-2 shadow-2xl rounded-sm overflow-hidden bg-black/40 border border-white/10 p-1 ${
                  isCover || spread.length === 1
                    ? 'max-w-2xl'
                    : 'max-w-6xl'
                }`}
              >
                {spread.map((page) => (
                  <div
                    key={page.index}
                    ref={(el) => {
                      if (el) pageRefs.current.set(page.index, el);
                      else pageRefs.current.delete(page.index);
                    }}
                    data-comic-page={page.index}
                    className="relative flex-1 flex items-center justify-center"
                  >
                    <img
                      src={page.url}
                      alt={`Page ${page.index}`}
                      className="max-h-[85vh] w-auto object-contain block select-none pointer-events-none"
                      loading="lazy"
                    />
                    {isCover && (
                      <div className="absolute top-3 left-3 px-2 py-0.5 rounded bg-primary/80 backdrop-blur-xs text-[10px] uppercase font-bold tracking-wider text-white shadow-sm">
                        Cover
                      </div>
                    )}
                  </div>
                ))}
              </div>

              {/* Page Boundary Badge */}
              <PageBoundaryBadge
                currentPage={spread[0].index}
                totalPages={comicPages.length}
                theme={settings.theme}
                customText={pageNumbersText}
              />
            </div>
          );
        })}
      </div>
    </div>
  );
};
