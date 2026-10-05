import React from 'react';
import { Bookmark as BookmarkType, ReadingTheme, READER_THEMES } from '../../types/reader';
import { X, Bookmark, Trash2, Plus } from 'lucide-react';

interface BookmarksDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  bookmarks: BookmarkType[];
  currentPage: number;
  onNavigateToPage: (page: number) => void;
  onAddBookmark: () => void;
  onRemoveBookmark: (id: string) => void;
  theme?: ReadingTheme;
}

export const BookmarksDrawer: React.FC<BookmarksDrawerProps> = ({
  isOpen,
  onClose,
  bookmarks,
  currentPage,
  onNavigateToPage,
  onAddBookmark,
  onRemoveBookmark,
  theme = 'night',
}) => {
  if (!isOpen) return null;

  const currentTheme = READER_THEMES[theme] || READER_THEMES.night;
  const isDark = currentTheme.isDark;

  const isCurrentPageBookmarked = bookmarks.some((b) => b.page === currentPage);

  return (
    <div className="fixed inset-0 z-50 flex pointer-events-none">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/50 backdrop-blur-xs transition-opacity pointer-events-auto"
        onClick={onClose}
      />

      {/* Drawer */}
      <div
        className={`relative w-80 max-w-[85vw] h-full shadow-2xl flex flex-col pointer-events-auto transition-transform duration-300 ease-out z-10 border-r ${
          isDark
            ? 'bg-[#1e1e1e] text-neutral-100 border-white/10'
            : 'bg-[#fafafa] text-neutral-900 border-black/10'
        }`}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-inherit">
          <div className="flex items-center gap-2">
            <Bookmark size={16} className="text-primary" />
            <span className="text-sm font-semibold tracking-wide uppercase">Bookmarks</span>
            <span className="text-xs px-2 py-0.5 rounded-full bg-white/10 text-neutral-400">
              {bookmarks.length}
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

        {/* Add current page action */}
        <div className="p-3 border-b border-inherit">
          <button
            onClick={onAddBookmark}
            disabled={isCurrentPageBookmarked}
            className={`w-full py-2 px-3 rounded-lg text-xs font-medium flex items-center justify-center gap-2 transition-all ${
              isCurrentPageBookmarked
                ? 'bg-white/5 text-neutral-500 cursor-not-allowed'
                : 'bg-primary/20 text-primary hover:bg-primary/30 border border-primary/30'
            }`}
          >
            <Plus size={14} />
            <span>
              {isCurrentPageBookmarked ? `Page ${currentPage} already bookmarked` : `Bookmark Page ${currentPage}`}
            </span>
          </button>
        </div>

        {/* Bookmarks List */}
        <div className="flex-1 overflow-y-auto p-3 space-y-2">
          {bookmarks.length === 0 ? (
            <div className="p-6 text-center text-xs text-neutral-400">
              No bookmarks saved yet. Click the ribbon in the toolbar or above to bookmark this page.
            </div>
          ) : (
            bookmarks.map((b) => (
              <div
                key={b.id}
                className={`p-3 rounded-lg border text-xs flex items-start justify-between gap-2 group transition-colors ${
                  isDark ? 'bg-white/5 border-white/5 hover:border-white/20' : 'bg-black/5 border-black/5 hover:border-black/20'
                }`}
              >
                <div
                  className="flex-1 cursor-pointer"
                  onClick={() => {
                    onNavigateToPage(b.page);
                    onClose();
                  }}
                >
                  <div className="flex items-center gap-2 mb-1">
                    <Bookmark size={13} className="text-primary fill-primary/40" />
                    <span className="font-semibold text-white">Page {b.page}</span>
                    <span className="text-[10px] text-neutral-500">
                      {new Date(b.createdAt).toLocaleDateString()}
                    </span>
                  </div>
                  {b.excerpt && (
                    <p className="text-[11px] text-neutral-400 line-clamp-2 italic">
                      "{b.excerpt}"
                    </p>
                  )}
                </div>
                <button
                  onClick={() => onRemoveBookmark(b.id)}
                  className="p-1 rounded opacity-0 group-hover:opacity-100 hover:bg-red-500/20 text-neutral-400 hover:text-red-400 transition-all"
                  title="Remove Bookmark"
                >
                  <Trash2 size={13} />
                </button>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
};
