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
  const isCurrentPageBookmarked = bookmarks.some((b) => b.page === currentPage);

  return (
    <aside
      className="h-full w-[300px] max-w-[82vw] shrink-0 flex flex-col min-h-0"
      style={{
        backgroundColor: currentTheme.toolbarBg,
        borderRight: `1px solid ${currentTheme.border}`,
        color: currentTheme.text,
      }}
      aria-label="Bookmarks"
    >
      <div
        className="h-11 shrink-0 flex items-center justify-between pl-4 pr-2"
        style={{ borderBottom: `1px solid ${currentTheme.border}` }}
      >
        <div className="flex items-center gap-2 min-w-0">
          <Bookmark size={14} style={{ color: currentTheme.muted }} />
          <span className="text-[12px] font-semibold tracking-wide truncate">Bookmarks</span>
          <span
            className="text-[11px] px-1.5 py-px rounded-full font-mono tabular-nums"
            style={{ backgroundColor: currentTheme.isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.06)', color: currentTheme.muted }}
          >
            {bookmarks.length}
          </span>
        </div>
        <button
          onClick={onClose}
          className="p-1.5 rounded-md transition-colors"
          style={{ color: currentTheme.muted }}
          title="Close bookmarks"
        >
          <X size={15} />
        </button>
      </div>

      <div className="p-3 shrink-0" style={{ borderBottom: `1px solid ${currentTheme.border}` }}>
        <button
          onClick={onAddBookmark}
          disabled={isCurrentPageBookmarked}
          className="w-full h-8 px-3 rounded-lg text-[12px] font-medium flex items-center justify-center gap-2 transition-all"
          style={
            isCurrentPageBookmarked
              ? { backgroundColor: 'transparent', color: currentTheme.muted, border: `1px solid ${currentTheme.border}`, opacity: 0.6, cursor: 'not-allowed' }
              : { backgroundColor: 'rgba(216,27,108,0.14)', color: '#e5488f', border: '1px solid rgba(216,27,108,0.35)' }
          }
        >
          <Plus size={14} />
          <span>{isCurrentPageBookmarked ? `Page ${currentPage} bookmarked` : `Bookmark page ${currentPage}`}</span>
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-2 space-y-1.5 min-h-0">
        {bookmarks.length === 0 ? (
          <div className="px-4 py-10 text-center text-[12px]" style={{ color: currentTheme.muted }}>
            No bookmarks yet. Bookmark this page to jump back here later.
          </div>
        ) : (
          bookmarks.map((b) => (
            <div
              key={b.id}
              className="p-2.5 rounded-lg text-[12px] flex items-start justify-between gap-2 group transition-colors"
              style={{ backgroundColor: currentTheme.isDark ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.03)', border: `1px solid ${currentTheme.border}` }}
            >
              <div
                className="flex-1 cursor-pointer min-w-0"
                onClick={() => {
                  onNavigateToPage(b.page);
                  onClose();
                }}
              >
                <div className="flex items-center gap-2 mb-0.5">
                  <Bookmark size={12} className="text-[#d81b6c] shrink-0" />
                  <span className="font-semibold" style={{ color: currentTheme.text }}>Page {b.page}</span>
                  <span className="text-[10px] font-mono" style={{ color: currentTheme.muted }}>
                    {new Date(b.createdAt).toLocaleDateString()}
                  </span>
                </div>
                {b.excerpt && (
                  <p className="text-[11px] line-clamp-2 italic" style={{ color: currentTheme.muted }}>
                    &ldquo;{b.excerpt}&rdquo;
                  </p>
                )}
              </div>
              <button
                onClick={() => onRemoveBookmark(b.id)}
                className="p-1 rounded opacity-0 group-hover:opacity-100 transition-all shrink-0"
                style={{ color: currentTheme.muted }}
                title="Remove bookmark"
              >
                <Trash2 size={13} />
              </button>
            </div>
          ))
        )}
      </div>
    </aside>
  );
};
