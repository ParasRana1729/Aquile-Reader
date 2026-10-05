import React, { useState } from 'react';
import { Annotation, ReadingTheme, READER_THEMES } from '../../types/reader';
import { X, FileText, Trash2, Plus, MessageSquare } from 'lucide-react';

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
  const isDark = currentTheme.isDark;

  const handleSaveNote = () => {
    if (!newNoteText.trim()) return;
    onAddAnnotation({
      page: currentPage,
      text: `Note on Page ${currentPage}`,
      note: newNoteText.trim(),
      color: '#d41b6c',
    });
    setNewNoteText('');
    setIsAdding(false);
  };

  return (
    <div className="fixed inset-0 z-50 flex pointer-events-none">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/50 backdrop-blur-xs transition-opacity pointer-events-auto"
        onClick={onClose}
      />

      {/* Drawer */}
      <div
        className={`relative w-84 max-w-[85vw] h-full shadow-2xl flex flex-col pointer-events-auto transition-transform duration-300 ease-out z-10 border-r ${
          isDark
            ? 'bg-[#1e1e1e] text-neutral-100 border-white/10'
            : 'bg-[#fafafa] text-neutral-900 border-black/10'
        }`}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-inherit">
          <div className="flex items-center gap-2">
            <FileText size={16} className="text-primary" />
            <span className="text-sm font-semibold tracking-wide uppercase">Annotations & Notes</span>
            <span className="text-xs px-2 py-0.5 rounded-full bg-white/10 text-neutral-400">
              {annotations.length}
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

        {/* Quick Add Note Area */}
        <div className="p-3 border-b border-inherit">
          {isAdding ? (
            <div className="space-y-2">
              <textarea
                value={newNoteText}
                onChange={(e) => setNewNoteText(e.target.value)}
                placeholder={`Type your note for page ${currentPage}...`}
                rows={3}
                className="w-full text-xs p-2 rounded-lg bg-black/30 border border-white/10 text-white placeholder-neutral-500 focus:outline-hidden focus:border-primary resize-none"
                autoFocus
              />
              <div className="flex justify-end gap-2">
                <button
                  onClick={() => setIsAdding(false)}
                  className="px-2.5 py-1 text-xs text-neutral-400 hover:text-white"
                >
                  Cancel
                </button>
                <button
                  onClick={handleSaveNote}
                  className="px-3 py-1 text-xs bg-primary text-white rounded-md hover:bg-primary/80"
                >
                  Save Note
                </button>
              </div>
            </div>
          ) : (
            <button
              onClick={() => setIsAdding(true)}
              className="w-full py-2 px-3 rounded-lg text-xs font-medium flex items-center justify-center gap-2 bg-primary/20 text-primary hover:bg-primary/30 border border-primary/30 transition-all"
            >
              <Plus size={14} />
              <span>Add Note on Page {currentPage}</span>
            </button>
          )}
        </div>

        {/* Annotations List */}
        <div className="flex-1 overflow-y-auto p-3 space-y-2">
          {annotations.length === 0 ? (
            <div className="p-6 text-center text-xs text-neutral-400">
              No annotations or notes taken yet.
            </div>
          ) : (
            annotations.map((a) => (
              <div
                key={a.id}
                className={`p-3 rounded-lg border text-xs flex items-start justify-between gap-2 group transition-colors ${
                  isDark ? 'bg-white/5 border-white/5 hover:border-white/20' : 'bg-black/5 border-black/5 hover:border-black/20'
                }`}
              >
                <div
                  className="flex-1 cursor-pointer"
                  onClick={() => {
                    if (a.page !== undefined) onNavigateToPage(a.page);
                    onClose();
                  }}
                >
                  <div className="flex items-center gap-2 mb-1">
                    <span
                      className="w-2 h-2 rounded-full flex-shrink-0"
                      style={{ backgroundColor: a.color || '#d41b6c' }}
                    />
                    <span className="font-semibold text-white">Page {a.page}</span>
                    <span className="text-[10px] text-neutral-500">
                      {new Date(a.createdAt).toLocaleDateString()}
                    </span>
                  </div>
                  {a.text && (
                    <p className="text-[11px] text-neutral-300 font-serif italic mb-1 border-l-2 border-primary/40 pl-2">
                      "{a.text}"
                    </p>
                  )}
                  {a.note && (
                    <div className="flex items-start gap-1.5 text-[11px] text-neutral-400 mt-1">
                      <MessageSquare size={11} className="mt-0.5 flex-shrink-0 text-primary" />
                      <span>{a.note}</span>
                    </div>
                  )}
                </div>
                <button
                  onClick={() => onRemoveAnnotation(a.id)}
                  className="p-1 rounded opacity-0 group-hover:opacity-100 hover:bg-red-500/20 text-neutral-400 hover:text-red-400 transition-all"
                  title="Delete Annotation"
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
