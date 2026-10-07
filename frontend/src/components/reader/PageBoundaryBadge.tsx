import React from 'react';
import { ReadingTheme, READER_THEMES } from '../../types/reader';

interface PageBoundaryBadgeProps {
  currentPage: number;
  totalPages: number;
  theme?: ReadingTheme;
  customText?: string;
  className?: string;
}

export const PageBoundaryBadge: React.FC<PageBoundaryBadgeProps> = ({
  currentPage,
  totalPages,
  theme = 'night',
  customText,
  className = '',
}) => {
  const currentTheme = READER_THEMES[theme] || READER_THEMES.night;

  // Native Windows Aquile Reader (frames f_006/f_011): the page indicator is
  // not an inline label after the text. It is a complete standalone page that
  // separates one content page from the next — an otherwise empty page with
  // "N of M" centered, closed by a full-width divider rule above the next
  // page's running header.
  return (
    <div
      className={`w-full select-none flex flex-col ${className}`}
      data-page-badge={currentPage}
      style={{ backgroundColor: currentTheme.bg, minHeight: '72vh' }}
    >
      {/* Empty page body with centered serif-italic page indicator */}
      <div className="flex-1 flex items-center justify-center px-6 py-24">
        <span
          className="text-[30px] leading-[1.6] italic font-serif tracking-normal whitespace-nowrap"
          style={{ color: currentTheme.muted }}
        >
          {customText || (
            <>
              <span>{currentPage}</span>{' '}
              <em className="font-serif">of</em>{' '}
              <span>{totalPages}</span>
            </>
          )}
        </span>
      </div>

      {/* Full-width divider rule separating from the next content page */}
      <div
        className="w-full shrink-0"
        style={{ backgroundColor: currentTheme.hairline, height: '4px' }}
      />
    </div>
  );
};
