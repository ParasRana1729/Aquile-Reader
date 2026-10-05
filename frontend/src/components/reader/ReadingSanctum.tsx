import React, { useRef, useEffect, useCallback, useState } from 'react';
import { PageBoundaryBadge } from './PageBoundaryBadge';
import {
  ReaderSettings,
  READER_THEMES,
  FONT_FAMILIES,
  Annotation,
} from '../../types/reader';
import { Highlighter, MessageSquare, Copy, Volume2 } from 'lucide-react';

interface ReadingSanctumProps {
  bookTitle?: string;
  settings: ReaderSettings;
  currentPage: number;
  totalPages: number;
  onPageChange: (page: number, total: number, percentage?: number) => void;
  onAddAnnotation?: (annotation: Omit<Annotation, 'id' | 'createdAt'>) => void;
  onJumpToPageRef?: React.MutableRefObject<((page: number) => void) | null>;
  searchQuery?: string;
  onSpeakText?: (text: string) => void;
}

interface ChapterPage {
  pageNumber: number;
  chapterTitle?: string;
  subTitle?: string;
  paragraphs: string[];
}

export const ReadingSanctum: React.FC<ReadingSanctumProps> = ({
  bookTitle = 'The Prince',
  settings,
  currentPage,
  totalPages,
  onPageChange,
  onAddAnnotation,
  onJumpToPageRef,
  searchQuery,
  onSpeakText,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const pageRefs = useRef<Map<number, HTMLElement>>(new Map());
  const [selectionPopup, setSelectionPopup] = useState<{
    visible: boolean;
    x: number;
    y: number;
    text: string;
    pageNum: number;
  }>({ visible: false, x: 0, y: 0, text: '', pageNum: 1 });

  const currentTheme = READER_THEMES[settings.theme] || READER_THEMES.night;
  const currentFont = FONT_FAMILIES[settings.fontFamily] || FONT_FAMILIES.serif;

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

  // Margin container widths
  const getMarginClass = () => {
    if (settings.isTwoColumn) {
      return settings.margin === 'compact'
        ? 'max-w-6xl px-4'
        : settings.margin === 'wide'
        ? 'max-w-7xl px-16'
        : 'max-w-7xl px-8';
    }
    return settings.margin === 'compact'
      ? 'max-w-2xl px-4'
      : settings.margin === 'wide'
      ? 'max-w-4xl px-12'
      : 'max-w-3xl px-6';
  };

  // The Prince page sequence matching Windows B0 (win_004 - win_014)
  const pagesData: ChapterPage[] = [
    {
      pageNumber: 22,
      paragraphs: [
        'DEDICATION. TO THE MAGNIFICENT LORENZO DI PIERO DE’ MEDICI.',
        'Those who strive to obtain the good graces of a prince are accustomed to come before him with such things as they hold most dear, or in which they see him take most delight: whence one often sees them presented with horses, arms, cloth of gold, precious stones, and similar ornaments worthy of their greatness.',
        'Desiring then to present myself to your Magnificence with some token of my devotion towards you, I have found nothing amongst my possessions the which I value or esteem so much as the knowledge of the actions of great men, acquired by long experience in contemporary affairs, and a continual study of antiquity.',
      ],
    },
    {
      pageNumber: 23,
      chapterTitle:
        'CHAPTER I. HOW MANY KINDS OF PRINCIPALITIES THERE ARE, AND BY WHAT MEANS THEY ARE ACQUIRED',
      paragraphs: [
        'All states, all powers, that have held and hold rule over men have been and are either republics or principalities.',
        'Principalities are either hereditary, in which the family has been long established; or they are new.',
        'The new are either entirely new, as was Milan to Francesco Sforza, or they are, as it were, members annexed to the hereditary state of the prince who has acquired them, as was the kingdom of Naples to that of the King of Spain.',
        'Such dominions thus acquired are either accustomed to live under a prince, or to live in freedom; and are acquired either by the arms of the prince himself, or of others, or else by fortune or by ability.',
      ],
    },
    {
      pageNumber: 24,
      chapterTitle: 'CHAPTER II. CONCERNING HEREDITARY PRINCIPALITIES',
      paragraphs: [
        'I will leave out all discussion on republics, inasmuch as in another place I have written of them at length, and will address myself only to principalities by filling in the outlines above mentioned, and will consider how such principalities may be governed and maintained.',
        'I say at once there are fewer difficulties in holding hereditary states, and those long accustomed to the family of their prince, than new ones; for it is sufficient only not to transgress the customs of his ancestors, and to deal prudently with circumstances as they arise.',
        'For this reason, if a prince is of ordinary ability he will always maintain his state, unless some extraordinary and excessive force should deprive him of it; and even if he should be so deprived, he will repossess it whenever the conqueror encounters any misfortune.',
      ],
    },
    {
      pageNumber: 25,
      paragraphs: [
        'We have in Italy, for example, the Duke of Ferrara, who could not have withstood the attacks of the Venetians in ’84, nor those of Pope Julius in ’10, unless he had been long established in his dominions.',
        'For the hereditary prince has less cause and less necessity to offend; hence it happens that he will be more loved; and unless extraordinary vices cause him to be hated, it is reasonable to expect that his subjects will be naturally well disposed towards him; and in the antiquity and duration of his rule the memories and motives that make for change are lost, for one change always leaves the toothing for another.',
      ],
    },
    {
      pageNumber: 26,
      chapterTitle: 'CHAPTER III. CONCERNING MIXED PRINCIPALITIES',
      paragraphs: [
        'But the difficulties occur in a new principality. And firstly, if it be not entirely new, but is, as it were, a member of a state which, taken collectively, may be called composite, the changes arise chiefly from an inherent difficulty which there is in all new principalities.',
        'This is that men change their rulers willingly, hoping to better themselves, and this hope induces them to take up arms against him who governs; but they are deceived, for they discover afterwards by experience that they have gone from bad to worse.',
        'This follows also on another ordinary and natural necessity, which always causes a new prince to burden those who have submitted to him with his soldiery and with infinite other hardships which he must put upon his new acquisition.',
        'In this way you have enemies in all those whom you have injured in seizing that principality, and you are not able to keep those friends who put you there because of your not being able to satisfy them in the way they expected, and you cannot take strong measures against them, feeling bound to them. For, although one may be very strong in armed forces, yet in entering a province one has always need of the goodwill of the natives.',
      ],
    },
    {
      pageNumber: 27,
      paragraphs: [
        'For these reasons Louis the Twelfth, King of France, quickly occupied Milan, and as quickly lost it; and to turn him out the first time it only needed Lodovico’s own forces; because those who had opened the gates to him, finding themselves deceived in their hopes of future benefit, would not endure the ill-treatment of the new prince.',
        'It is very true that, after acquiring rebellious provinces a second time, they are not so lightly lost afterwards, because the prince, with little reluctance, takes the opportunity of the rebellion to punish the delinquents, to clear out the suspects, and to strengthen himself in the weakest places.',
        'Thus to cause France to lose Milan the first time it was enough for the Duke Lodovico to raise insurrections on the borders; but to cause him to lose it a second time it was necessary to bring the whole world against him, and that his armies should be defeated and driven out of Italy; which followed from the causes above mentioned.',
      ],
    },
  ];

  // Continuous vertical scroll & Intersection Observer
  useEffect(() => {
    if (!containerRef.current) return;

    const handleScroll = () => {
      const container = containerRef.current;
      if (!container) return;
      const scrollPos = container.scrollTop;
      const scrollHeight = container.scrollHeight - container.clientHeight;
      const percentage = scrollHeight > 0 ? Math.round((scrollPos / scrollHeight) * 100) : 0;

      // Find visible page
      let closestPage = currentPage;
      let minDistance = Infinity;
      pageRefs.current.forEach((el, pNum) => {
        const rect = el.getBoundingClientRect();
        const dist = Math.abs(rect.top - 120);
        if (dist < minDistance) {
          minDistance = dist;
          closestPage = pNum;
        }
      });

      onPageChange(closestPage, totalPages, percentage);
    };

    const container = containerRef.current;
    container.addEventListener('scroll', handleScroll, { passive: true });
    return () => container.removeEventListener('scroll', handleScroll);
  }, [currentPage, totalPages, onPageChange]);

  // Handle text selection for interactive highlighting and notes
  const handleMouseUp = () => {
    const sel = window.getSelection();
    if (!sel || sel.isCollapsed || !sel.toString().trim()) {
      setSelectionPopup((prev) => (prev.visible ? { ...prev, visible: false } : prev));
      return;
    }

    const text = sel.toString().trim();
    const range = sel.getRangeAt(0);
    const rect = range.getBoundingClientRect();

    setSelectionPopup({
      visible: true,
      x: rect.left + rect.width / 2,
      y: rect.top - 10,
      text,
      pageNum: currentPage,
    });
  };

  const handleCreateHighlight = (color: string) => {
    if (onAddAnnotation && selectionPopup.text) {
      onAddAnnotation({
        page: selectionPopup.pageNum,
        text: selectionPopup.text,
        color,
      });
    }
    setSelectionPopup((prev) => ({ ...prev, visible: false }));
    window.getSelection()?.removeAllRanges();
  };

  return (
    <div
      ref={containerRef}
      onMouseUp={handleMouseUp}
      className="flex-1 w-full h-full overflow-y-auto overflow-x-hidden relative select-text transition-colors duration-200"
      style={{
        backgroundColor: currentTheme.bg,
        color: currentTheme.text,
      }}
    >
      {/* Floating Selection Tooltip */}
      {selectionPopup.visible && (
        <div
          className="fixed z-50 -translate-x-1/2 -translate-y-full mb-2 bg-[#222222]/95 backdrop-blur-md border border-white/15 shadow-2xl rounded-full px-3 py-1.5 flex items-center gap-2 text-white animate-in fade-in zoom-in-95 duration-150"
          style={{ left: `${selectionPopup.x}px`, top: `${selectionPopup.y}px` }}
          onMouseDown={(e) => e.stopPropagation()}
        >
          {/* Highlight Color Dots */}
          <div className="flex items-center gap-1.5 pr-2 border-r border-white/10">
            {['#d41b6c', '#b6c12c', '#00b294', '#ea7600'].map((col) => (
              <button
                key={col}
                onClick={() => handleCreateHighlight(col)}
                className="w-4 h-4 rounded-full border border-white/20 hover:scale-125 transition-transform"
                style={{ backgroundColor: col }}
                title="Highlight"
              />
            ))}
          </div>

          {/* Copy Button */}
          <button
            onClick={() => {
              navigator.clipboard.writeText(selectionPopup.text);
              setSelectionPopup((prev) => ({ ...prev, visible: false }));
            }}
            className="p-1 hover:bg-white/10 rounded transition-colors text-neutral-300 hover:text-white"
            title="Copy Text"
          >
            <Copy size={13} />
          </button>

          {/* Read Aloud Selected Text */}
          {onSpeakText && (
            <button
              onClick={() => {
                onSpeakText(selectionPopup.text);
                setSelectionPopup((prev) => ({ ...prev, visible: false }));
              }}
              className="p-1 hover:bg-white/10 rounded transition-colors text-neutral-300 hover:text-white"
              title="Speak Selection"
            >
              <Volume2 size={13} />
            </button>
          )}
        </div>
      )}

      {/* Main Reading Canvas Container */}
      <div className={`mx-auto py-16 transition-all duration-300 ${getMarginClass()}`}>
        {pagesData.map((page) => (
          <article
            key={page.pageNumber}
            ref={(el) => {
              if (el) pageRefs.current.set(page.pageNumber, el);
              else pageRefs.current.delete(page.pageNumber);
            }}
            data-page-number={page.pageNumber}
            className="w-full my-6 transition-all duration-200"
            style={{
              fontFamily: currentFont.cssFamily,
              fontSize: `${settings.fontSize}px`,
              lineHeight: `${settings.lineSpacing}`,
            }}
          >
            {/* Document Header (matching win_004 & win_005) */}
            <div className="flex items-center justify-between pb-6 select-none opacity-50 text-xs italic tracking-wider">
              <span>{bookTitle}</span>
              <span className="font-sans font-medium text-[11px] not-italic">
                Planet PDF
              </span>
            </div>

            {/* Chapter Title if present (matching win_004: CHAPTER I) */}
            {page.chapterTitle && (
              <h2
                className="text-center font-bold tracking-widest uppercase my-8 pt-4 pb-3 border-b transition-colors duration-200"
                style={{
                  fontSize: `${Math.round(settings.fontSize * 1.35)}px`,
                  borderColor: currentTheme.border,
                }}
              >
                {page.chapterTitle}
              </h2>
            )}

            {/* Paragraphs in 1-column or 2-column layout */}
            <div
              className={`space-y-6 ${
                settings.isTwoColumn ? 'columns-1 md:columns-2 gap-12' : ''
              }`}
            >
              {page.paragraphs.map((para, pIndex) => (
                <p
                  key={pIndex}
                  className="indent-8 text-justify transition-colors duration-200"
                  style={{
                    color: currentTheme.text,
                    fontSize: `${settings.fontSize}px`,
                    lineHeight: `${settings.lineSpacing}`,
                  }}
                >
                  {para}
                </p>
              ))}
            </div>

            {/* Centered Page Boundary Badging (*"23 of 239"*, *"26 of 239"*) flanked by subtle horizontal hairline rules */}
            <PageBoundaryBadge
              currentPage={page.pageNumber}
              totalPages={totalPages}
              theme={settings.theme}
            />
          </article>
        ))}
      </div>
    </div>
  );
};
