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
      className={`flex items-center justify-center my-10 md:my-12 px-6 w-full select-none ${className}`}
      data-page-badge={currentPage}
    >
      {/* Left Hairline Rule */}
      <div
        className="h-[1px] flex-1 max-w-[240px] transition-colors duration-200"
        style={{ backgroundColor: currentTheme.hairline }}
      />

      {/* Centered large serif-italic page indicator (native f_006/f_011: large "23 of 239") */}
      <span
        className="px-6 text-[26px] leading-[1.6] italic font-serif tracking-normal transition-colors duration-200 whitespace-nowrap"
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
        className="h-[1px] flex-1 max-w-[240px] transition-colors duration-200"
        style={{ backgroundColor: currentTheme.hairline }}
      />
    </div>
  );
};
