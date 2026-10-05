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

  return (
    <div
      className={`flex items-center justify-center my-8 py-4 w-full select-none ${className}`}
      data-page-badge={currentPage}
    >
      {/* Left Hairline Rule */}
      <div
        className="h-[1px] flex-1 max-w-[120px] transition-colors duration-200"
        style={{ backgroundColor: currentTheme.hairline }}
      />

      {/* Centered Italic Page Indicator Badge (matching win_005 - win_014: "23 of 239") */}
      <span
        className="px-5 text-[13px] italic font-serif tracking-wider transition-colors duration-200"
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

      {/* Right Hairline Rule */}
      <div
        className="h-[1px] flex-1 max-w-[120px] transition-colors duration-200"
        style={{ backgroundColor: currentTheme.hairline }}
      />
    </div>
  );
};
