import React, { useEffect, useMemo, useRef, useState } from 'react';
import { TOCItem, ReadingTheme, READER_THEMES } from '../../types/reader';
import { X, List, Search } from 'lucide-react';

interface TOCDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  toc: TOCItem[];
  currentPage: number;
  totalPages?: number;
  onNavigate: (target: TOCItem) => void;
  theme?: ReadingTheme;
}

function flattenToc(items: TOCItem[], depth = 0): Array<TOCItem & { depth: number; index: number }> {
  const out: Array<TOCItem & { depth: number; index: number }> = [];
  let counter = 0;
  const walk = (list: TOCItem[], d: number) => {
    for (const item of list) {
      counter += 1;
      out.push({ ...item, depth: d, index: counter });
      if (item.subitems && item.subitems.length > 0) walk(item.subitems, d + 1);
    }
  };
  walk(items, depth);
  return out;
}

export const TOCDrawer: React.FC<TOCDrawerProps> = ({
  isOpen,
  onClose,
  toc,
  currentPage,
  totalPages = 0,
  onNavigate,
  theme = 'night',
}) => {
  const [filter, setFilter] = useState('');
  const listRef = useRef<HTMLDivElement>(null);
  const activeRef = useRef<HTMLButtonElement>(null);

  const currentTheme = READER_THEMES[theme] || READER_THEMES.night;

  const flat = useMemo(() => flattenToc(toc), [toc]);

  const activeId = useMemo(() => {
    let best: string | null = null;
    for (const item of flat) {
      if (item.page !== undefined && item.page <= currentPage) {
        best = item.id;
      }
    }
    return best;
  }, [flat, currentPage]);

  const visible = useMemo(() => {
    const q = filter.trim().toLowerCase();
    if (!q) return flat;
    return flat.filter((i) => i.label.toLowerCase().includes(q));
  }, [flat, filter]);

  useEffect(() => {
    if (isOpen && activeRef.current) {
      activeRef.current.scrollIntoView({ block: 'nearest' });
    }
  }, [isOpen, activeId]);

  if (!isOpen) return null;

  const progressPct =
    totalPages > 0 ? Math.min(100, Math.max(0, Math.round((currentPage / totalPages) * 100))) : 0;

  return (
    <aside
      className="h-full w-[300px] max-w-[82vw] shrink-0 flex flex-col min-h-0"
      style={{
        backgroundColor: currentTheme.toolbarBg,
        borderRight: `1px solid ${currentTheme.border}`,
        color: currentTheme.text,
      }}
      aria-label="Table of contents"
    >
      {/* Header — same density as the reader toolbar */}
      <div
        className="h-12 shrink-0 flex items-center justify-between pl-4 pr-2"
        style={{ borderBottom: `1px solid ${currentTheme.border}` }}
      >
        <div className="flex items-center gap-2 min-w-0">
          <List size={15} style={{ color: currentTheme.muted }} />
          <span className="text-[13px] font-semibold tracking-wide truncate">Contents</span>
          <span
            className="text-[11px] px-1.5 py-px rounded-full font-mono tabular-nums"
            style={{ backgroundColor: currentTheme.isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.06)', color: currentTheme.muted }}
          >
            {flat.length}
          </span>
        </div>
        <button
          onClick={onClose}
          className="p-1.5 rounded-md transition-colors"
          style={{ color: currentTheme.muted }}
          onMouseEnter={(e) => {
            e.currentTarget.style.backgroundColor = currentTheme.isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.06)';
            e.currentTarget.style.color = currentTheme.text;
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.backgroundColor = 'transparent';
            e.currentTarget.style.color = currentTheme.muted;
          }}
          title="Close contents"
        >
          <X size={15} />
        </button>
      </div>

      {/* Filter — themed, quiet */}
      {flat.length > 4 && (
        <div className="px-3 py-2 shrink-0" style={{ borderBottom: `1px solid ${currentTheme.border}` }}>
          <div
            className="flex items-center gap-2 px-2.5 h-8 rounded-lg"
            style={{
              backgroundColor: currentTheme.isDark ? 'rgba(0,0,0,0.25)' : 'rgba(0,0,0,0.04)',
              border: `1px solid ${currentTheme.border}`,
            }}
          >
            <Search size={13} style={{ color: currentTheme.muted }} className="shrink-0" />
            <input
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              placeholder="Filter chapters…"
              className="flex-1 bg-transparent text-[13px] focus:outline-none min-w-0"
              style={{ color: currentTheme.text }}
            />
            {filter && (
              <button
                onClick={() => setFilter('')}
                style={{ color: currentTheme.muted }}
                title="Clear filter"
              >
                <X size={13} />
              </button>
            )}
          </div>
        </div>
      )}

      {/* Chapters */}
      <div ref={listRef} className="flex-1 overflow-y-auto py-1.5 px-1.5 min-h-0">
        {visible.length === 0 ? (
          <div className="px-4 py-10 text-center text-[13px]" style={{ color: currentTheme.muted }}>
            {flat.length === 0
              ? 'No chapters or landmarks in this document.'
              : `No chapters match “${filter.trim()}”.`}
          </div>
        ) : (
          visible.map((item) => {
            const isActive = item.id === activeId;
            return (
              <button
                key={item.id || `${item.index}`}
                ref={isActive ? activeRef : undefined}
                onClick={() => {
                  onNavigate(item);
                  onClose();
                }}
                title={item.label}
                className="w-full text-left rounded-md flex items-center gap-2 pl-2 pr-2.5 transition-colors"
                style={{
                  paddingTop: 7,
                  paddingBottom: 7,
                  paddingLeft: 8 + item.depth * 14,
                  backgroundColor: isActive
                    ? currentTheme.isDark
                      ? 'rgba(216,27,108,0.16)'
                      : 'rgba(216,27,108,0.10)'
                    : 'transparent',
                  boxShadow: isActive ? `inset 2px 0 0 0 #d81b6c` : 'none',
                }}
                onMouseEnter={(e) => {
                  if (!isActive) {
                    e.currentTarget.style.backgroundColor = currentTheme.isDark
                      ? 'rgba(255,255,255,0.05)'
                      : 'rgba(0,0,0,0.04)';
                  }
                }}
                onMouseLeave={(e) => {
                  if (!isActive) e.currentTarget.style.backgroundColor = 'transparent';
                }}
              >
                <span
                  className="font-mono tabular-nums shrink-0"
                  style={{ fontSize: 11, width: 24, color: currentTheme.muted }}
                >
                  {String(item.index).padStart(2, '0')}
                </span>
                <span
                  className="flex-1 truncate"
                  style={{
                    fontSize: 13,
                    color: isActive ? currentTheme.text : currentTheme.isDark ? '#cfcfcf' : '#3a3a3a',
                    fontWeight: isActive ? 600 : 400,
                    lineHeight: 1.45,
                  }}
                >
                  {item.label}
                </span>
                {item.page !== undefined && (
                  <span
                    className="font-mono tabular-nums shrink-0"
                    style={{ fontSize: 11, color: currentTheme.muted }}
                  >
                    {item.page}
                  </span>
                )}
              </button>
            );
          })
        )}
      </div>

      {/* Footer — reading position, same tokens as toolbar center stats */}
      {totalPages > 0 && (
        <div className="shrink-0 px-4 pt-2.5 pb-3" style={{ borderTop: `1px solid ${currentTheme.border}` }}>
          <div
            className="h-[3px] rounded-full overflow-hidden mb-1.5"
            style={{ backgroundColor: currentTheme.isDark ? 'rgba(255,255,255,0.10)' : 'rgba(0,0,0,0.08)' }}
          >
            <div className="h-full rounded-full bg-[#d81b6c] transition-all" style={{ width: `${progressPct}%` }} />
          </div>
          <div
            className="flex items-center justify-between font-mono tabular-nums"
            style={{ fontSize: 11, color: currentTheme.muted }}
          >
            <span>
              p. {currentPage} / {totalPages}
            </span>
            <span>{progressPct}%</span>
          </div>
        </div>
      )}
    </aside>
  );
};
