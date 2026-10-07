import React, { useState, useEffect } from 'react';
import { Search, X, ChevronUp, ChevronDown } from 'lucide-react';
import { READER_THEMES } from '../../types/reader';
import { ACRYLIC_FILTER, ACRYLIC_OPACITY_PCT } from '../AcrylicCanvas';

interface SearchOverlayProps {
  isOpen: boolean;
  onClose: () => void;
  onSearch: (query: string) => number; // returns match count
  onNextMatch: () => void;
  onPrevMatch: () => void;
  matchIndex: number;
  matchCount: number;
}

export const SearchOverlay: React.FC<SearchOverlayProps> = ({
  isOpen,
  onClose,
  onSearch,
  onNextMatch,
  onPrevMatch,
  matchIndex,
  matchCount,
}) => {
  const [query, setQuery] = useState('');

  useEffect(() => {
    if (query.trim()) {
      onSearch(query.trim());
    } else {
      onSearch('');
    }
  }, [query]);

  if (!isOpen) return null;

  // Shared acrylic surface: night toolbar token at theme opacity + identical
  // blur/saturation to every other reader overlay (Phase 4 §13).
  const surfaceBg = `color-mix(in srgb, ${READER_THEMES.night.toolbarBg} ${ACRYLIC_OPACITY_PCT}%, transparent)`;

  return (
    <div
      role="search"
      className="absolute top-12 right-20 z-50 flex items-center gap-2 acrylic-overlay overlay-rise border border-white/10 shadow-2xl rounded-xl px-3 py-2 text-white"
      style={{
        backgroundColor: surfaceBg,
        backdropFilter: ACRYLIC_FILTER,
        WebkitBackdropFilter: ACRYLIC_FILTER,
      }}
    >
      <Search size={14} className="text-neutral-400" aria-hidden="true" />
      <input
        type="text"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter') {
            if (e.shiftKey) onPrevMatch();
            else onNextMatch();
          } else if (e.key === 'Escape') {
            onClose();
          }
        }}
        placeholder="Find in book..."
        aria-label="Find in book"
        className="w-48 bg-transparent text-xs text-white placeholder-neutral-500 focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-[var(--accent-color)]"
        autoFocus
      />

      {query.trim() && (
        <span className="text-[11px] font-mono text-neutral-400 whitespace-nowrap px-1">
          {matchCount > 0 ? `${matchIndex + 1}/${matchCount}` : '0 results'}
        </span>
      )}

      <div className="flex items-center gap-0.5 border-l border-white/10 pl-1">
        <button
          onClick={onPrevMatch}
          disabled={matchCount === 0}
          className="p-1 rounded transition-colors duration-150 ease-out hover:bg-white/10 text-neutral-400 hover:text-white disabled:opacity-30 disabled:hover:bg-transparent"
          title="Previous match (Shift+Enter)"
          aria-label="Previous match (Shift+Enter)"
        >
          <ChevronUp size={14} />
        </button>
        <button
          onClick={onNextMatch}
          disabled={matchCount === 0}
          className="p-1 rounded transition-colors duration-150 ease-out hover:bg-white/10 text-neutral-400 hover:text-white disabled:opacity-30 disabled:hover:bg-transparent"
          title="Next match (Enter)"
          aria-label="Next match (Enter)"
        >
          <ChevronDown size={14} />
        </button>
      </div>

      <button
        onClick={onClose}
        className="p-1 rounded hover:bg-white/10 text-neutral-400 hover:text-white transition-colors duration-150 ease-out ml-1"
        title="Close search (Esc)"
        aria-label="Close search (Esc)"
      >
        <X size={14} />
      </button>
    </div>
  );
};
