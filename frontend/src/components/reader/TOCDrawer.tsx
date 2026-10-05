import React from 'react';
import { TOCItem, ReadingTheme, READER_THEMES } from '../../types/reader';
import { X, ChevronRight, Bookmark } from 'lucide-react';

interface TOCDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  toc: TOCItem[];
  currentPage: number;
  onNavigate: (target: TOCItem) => void;
  theme?: ReadingTheme;
}

export const TOCDrawer: React.FC<TOCDrawerProps> = ({
  isOpen,
  onClose,
  toc,
  currentPage,
  onNavigate,
  theme = 'night',
}) => {
  if (!isOpen) return null;

  const currentTheme = READER_THEMES[theme] || READER_THEMES.night;
  const isDark = currentTheme.isDark;

  return (
    <div className="fixed inset-0 z-50 flex pointer-events-none">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/50 backdrop-blur-xs transition-opacity pointer-events-auto"
        onClick={onClose}
      />

      {/* Drawer Container */}
      <div
        className={`relative w-80 max-w-[85vw] h-full shadow-2xl flex flex-col pointer-events-auto transition-transform duration-300 ease-out z-10 border-r ${
          isDark
            ? 'bg-[#1e1e1e] text-neutral-100 border-white/10'
            : 'bg-[#fafafa] text-neutral-900 border-black/10'
        }`}
      >
        {/* Drawer Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-inherit">
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold tracking-wide uppercase">Table of Contents</span>
            <span className="text-xs px-2 py-0.5 rounded-full bg-white/10 text-neutral-400">
              {toc.length}
            </span>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-md hover:bg-white/10 transition-colors text-neutral-400 hover:text-white"
            title="Close"
          >
            <X size={16} />
          </button>
        </div>

        {/* Chapters List */}
        <div className="flex-1 overflow-y-auto p-3 space-y-1">
          {toc.length === 0 ? (
            <div className="p-6 text-center text-xs text-neutral-400">
              No chapters or landmarks available in this document.
            </div>
          ) : (
            toc.map((item, index) => {
              const isCurrent =
                item.page !== undefined
                  ? item.page === currentPage
                  : false;

              return (
                <button
                  key={item.id || index}
                  onClick={() => {
                    onNavigate(item);
                    onClose();
                  }}
                  className={`w-full text-left px-3 py-2.5 rounded-lg text-xs flex items-center justify-between transition-colors ${
                    isCurrent
                      ? 'bg-primary/20 text-primary font-medium border border-primary/30'
                      : isDark
                      ? 'hover:bg-white/5 text-neutral-300 hover:text-white'
                      : 'hover:bg-black/5 text-neutral-700 hover:text-black'
                  }`}
                >
                  <div className="flex items-center gap-2.5 truncate mr-2">
                    <span className="text-[10px] text-neutral-500 font-mono w-5">
                      {index + 1}
                    </span>
                    <span className="truncate">{item.label}</span>
                  </div>
                  {item.page !== undefined && (
                    <span className="text-[10px] text-neutral-500 font-mono flex-shrink-0">
                      p. {item.page}
                    </span>
                  )}
                </button>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
};
