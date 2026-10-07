import React, { useState } from 'react';
import { Annotation, ReadingTheme, READER_THEMES } from '../../types/reader';
import { X, NotebookPen, Trash2, Plus, MessageSquare } from 'lucide-react';
import { ACRYLIC_FILTER, ACRYLIC_OPACITY_PCT } from '../AcrylicCanvas';

interface AnnotationsDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  annotations: Annotation[];
  currentPage: number;
  onNavigateToPage: (page: number) => void;
  onAddAnnotation: (annotation: Omit<Annotation, 'id' | 'createdAt'>) => void;
  onRemoveAnnotation: (id: string) => void;
  theme?: ReadingTheme;
}

export const AnnotationsDrawer: React.FC<AnnotationsDrawerProps> = ({
  isOpen,
  onClose,
  annotations,
  currentPage,
  onNavigateToPage,
  onAddAnnotation,
  onRemoveAnnotation,
  theme = 'night',
}) => {
  const [newNoteText, setNewNoteText] = useState('');
  const [isAdding, setIsAdding] = useState(false);

  if (!isOpen) return null;

  const currentTheme = READER_THEMES[theme] || READER_THEMES.night;

  const handleSaveNote = () => {
    if (!newNoteText.trim()) return;
    onAddAnnotation({
      page: currentPage,
      text: `Note on page ${currentPage}`,
      note: newNoteText.trim(),
      color: '#d41b6c',
    });
    setNewNoteText('');
    setIsAdding(false);
  };

  return (
    <aside
      className="h-full w-[300px] max-w-[82vw] shrink-0 flex flex-col min-h-0 drawer-slide-in"
      style={{
        backgroundColor: `color-mix(in srgb, ${currentTheme.toolbarBg} ${ACRYLIC_OPACITY_PCT}%, transparent)`,
        backdropFilter: ACRYLIC_FILTER,
        WebkitBackdropFilter: ACRYLIC_FILTER,
        borderRight: `1px solid ${currentTheme.border}`,
        color: currentTheme.text,
      }}
      aria-label="Annotations and notes"
    >
      {/* Header — h-12 aligns with the 48px reader toolbar */}
      <div
        className="h-12 shrink-0 flex items-center justify-between pl-4 pr-2"
        style={{ borderBottom: `1px solid ${currentTheme.border}` }}
      >
        <div className="flex items-center gap-2 min-w-0">
          <NotebookPen size={14} style={{ color: currentTheme.muted }} />
          <span className="text-[13px] font-semibold tracking-wide truncate">Notes</span>
          <span
            className="text-[11px] px-1.5 py-px rounded-full font-mono tabular-nums"
            style={{ backgroundColor: currentTheme.isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.06)', color: currentTheme.muted }}
          >
            {annotations.length}
          </span>
        </div>
        <button
          onClick={onClose}
          className="p-1.5 rounded-md transition-colors duration-150 ease-out"
          style={{ color: currentTheme.muted }}
          onMouseEnter={(e) => {
            e.currentTarget.style.backgroundColor = currentTheme.isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.06)';
            e.currentTarget.style.color = currentTheme.text;
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.backgroundColor = 'transparent';
            e.currentTarget.style.color = currentTheme.muted;
          }}
          onFocus={(e) => {
            e.currentTarget.style.backgroundColor = currentTheme.isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.06)';
            e.currentTarget.style.color = currentTheme.text;
          }}
          onBlur={(e) => {
            e.currentTarget.style.backgroundColor = 'transparent';
            e.currentTarget.style.color = currentTheme.muted;
          }}
          title="Close notes"
          aria-label="Close notes"
        >
          <X size={15} />
        </button>
      </div>

      <div className="p-3 shrink-0" style={{ borderBottom: `1px solid ${currentTheme.border}` }}>
        {isAdding ? (
          <div className="space-y-2">
            <textarea
              value={newNoteText}
              onChange={(e) => setNewNoteText(e.target.value)}
              placeholder={`Note on page ${currentPage}…`}
              aria-label={`Note on page ${currentPage}`}
              rows={3}
              className="w-full text-[12px] p-2 rounded-lg resize-none"
              style={{ backgroundColor: currentTheme.isDark ? 'rgba(0,0,0,0.25)' : 'rgba(0,0,0,0.04)', border: `1px solid ${currentTheme.border}`, color: currentTheme.text }}
              autoFocus
            />
            <div className="flex justify-end gap-2">
              <button onClick={() => setIsAdding(false)} className="px-2.5 py-1 text-[12px] rounded-md transition-colors duration-150 ease-out hover:brightness-125" style={{ color: currentTheme.muted }}>
                Cancel
              </button>
              <button
                onClick={handleSaveNote}
                className="px-3 py-1 text-[12px] rounded-md text-white transition-all duration-150 ease-out hover:brightness-110"
                style={{ backgroundColor: '#d81b6c' }}
              >
                Save note
              </button>
            </div>
          </div>
        ) : (
          <button
            onClick={() => setIsAdding(true)}
            className="w-full h-8 px-3 rounded-lg text-[12px] font-medium flex items-center justify-center gap-2 transition-all duration-150 ease-out hover:brightness-110"
            style={{ backgroundColor: 'rgba(216,27,108,0.14)', color: '#e5488f', border: '1px solid rgba(216,27,108,0.35)' }}
          >
            <Plus size={14} />
            <span>Add note on p. {currentPage}</span>
          </button>
        )}
      </div>

      <div className="flex-1 overflow-y-auto p-2 space-y-1.5 min-h-0">
        {annotations.length === 0 ? (
          <div className="px-4 py-10 text-center text-[12px]" style={{ color: currentTheme.muted }}>
            No notes yet. Select text or add a note for this page.
          </div>
        ) : (
          annotations.map((a) => (
            <div
              key={a.id}
              className="p-2.5 rounded-lg text-[12px] flex items-start justify-between gap-2 group transition-all duration-150 ease-out hover:brightness-125 focus-within:brightness-125"
              style={{ backgroundColor: currentTheme.isDark ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.03)', border: `1px solid ${currentTheme.border}` }}
            >
              <div
                role="button"
                tabIndex={0}
                aria-label={`Go to note on page ${a.page}`}
                className="flex-1 cursor-pointer min-w-0 rounded focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-[var(--accent-color)]"
                onClick={() => {
                  if (a.page !== undefined) onNavigateToPage(a.page);
                  onClose();
                }}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    if (a.page !== undefined) onNavigateToPage(a.page);
                    onClose();
                  }
                }}
              >
                <div className="flex items-center gap-2 mb-1">
                  <span className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: a.color || '#d41b6c' }} />
                  <span className="font-semibold" style={{ color: currentTheme.text }}>Page {a.page}</span>
                  <span className="text-[10px] font-mono" style={{ color: currentTheme.muted }}>
                    {new Date(a.createdAt).toLocaleDateString()}
                  </span>
                </div>
                {a.text && (
                  <p className="text-[11px] italic mb-1 pl-2" style={{ color: currentTheme.muted, borderLeft: '2px solid rgba(216,27,108,0.4)' }}>
                    &ldquo;{a.text}&rdquo;
                  </p>
                )}
                {a.note && (
                  <div className="flex items-start gap-1.5 text-[11px] mt-1" style={{ color: currentTheme.text }}>
                    <MessageSquare size={11} className="mt-0.5 shrink-0 text-[#d81b6c]" />
                    <span>{a.note}</span>
                  </div>
                )}
              </div>
              <button
                onClick={() => onRemoveAnnotation(a.id)}
                className="p-1 rounded opacity-0 group-hover:opacity-100 group-focus-within:opacity-100 focus-visible:opacity-100 transition-all duration-150 ease-out hover:bg-white/10 shrink-0"
                style={{ color: currentTheme.muted }}
                title="Delete note"
                aria-label={`Delete note on page ${a.page}`}
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
