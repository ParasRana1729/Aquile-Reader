import React, { useState, useEffect, useMemo } from 'react';
import {
  Highlighter,
  Search,
  Filter,
  Trash2,
  ExternalLink,
  Copy,
  Check,
  BookOpen,
  Calendar,
  Download,
} from 'lucide-react';
import { useTheme } from '../context/ThemeContext';
import { Annotation } from '../types/reader';
import { BookWithProgress } from '../types/book';
import { fetchAnnotations, removeAnnotation, fetchBooks } from '../utils/ipc';

interface AnnotationsViewProps {
  onOpenBook?: (bookId: string) => void;
}

export const AnnotationsView: React.FC<AnnotationsViewProps> = ({ onOpenBook }) => {
  const { currentTheme } = useTheme();
  const [annotations, setAnnotations] = useState<Annotation[]>([]);
  const [books, setBooks] = useState<BookWithProgress[]>([]);
  const [loading, setLoading] = useState(true);

  // Filters & Search
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedBookId, setSelectedBookId] = useState<string>('all');
  const [selectedType, setSelectedType] = useState<'all' | 'notes' | 'highlights'>('all');
  const [copiedId, setCopiedId] = useState<string | null>(null);

  // Load annotations and books
  const loadData = async () => {
    setLoading(true);
    try {
      const [anns, bks] = await Promise.all([fetchAnnotations(), fetchBooks()]);
      setAnnotations(anns);
      setBooks(bks);
    } catch (e) {
      console.warn('Failed to load annotations:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  // Filtered annotations
  const filteredAnnotations = useMemo(() => {
    return annotations.filter((ann) => {
      // Book filter
      if (selectedBookId !== 'all' && ann.bookId !== selectedBookId) {
        return false;
      }

      // Type filter
      if (selectedType === 'notes' && !ann.note?.trim()) {
        return false;
      }
      if (selectedType === 'highlights' && ann.note?.trim()) {
        return false;
      }

      // Search query
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const textMatch = (ann.selectedText || ann.text || '').toLowerCase().includes(q);
        const noteMatch = (ann.note || '').toLowerCase().includes(q);
        const bookMatch = (ann.bookTitle || '').toLowerCase().includes(q);
        return textMatch || noteMatch || bookMatch;
      }

      return true;
    });
  }, [annotations, selectedBookId, selectedType, searchQuery]);

  // Handle Delete
  const handleDelete = async (id: string) => {
    setAnnotations((prev) => prev.filter((a) => a.id !== id));
    await removeAnnotation(id);
  };

  // Handle Copy Quote
  const handleCopy = (id: string, text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  // Export Annotations to Markdown
  const handleExportMarkdown = () => {
    if (filteredAnnotations.length === 0) return;
    let md = '# Aquile Reader - Annotations & Notes\n\n';
    filteredAnnotations.forEach((ann, idx) => {
      md += `### ${idx + 1}. ${ann.bookTitle || 'Book'} (Page ${ann.page || 'N/A'})\n`;
      md += `> "${ann.selectedText || ann.text || ''}"\n\n`;
      if (ann.note) {
        md += `**Note:** ${ann.note}\n\n`;
      }
      md += `---\n\n`;
    });

    const blob = new Blob([md], { type: 'text/markdown;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `aquile-annotations-${new Date().toISOString().slice(0, 10)}.md`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="flex flex-col h-full w-full select-none overflow-hidden px-8 py-5">
      {/* Header bar matching Windows B0 */}
      <div className="flex flex-wrap items-center justify-between pb-5 border-b border-white/10 gap-4">
        <div className="flex items-center gap-3">
          <h1 className="text-[22px] font-semibold text-white tracking-tight">
            Annotations & Notes
          </h1>
          <span className="text-xs px-2.5 py-0.5 rounded-full bg-white/10 text-neutral-300 font-medium">
            {filteredAnnotations.length} {filteredAnnotations.length === 1 ? 'item' : 'items'}
          </span>
        </div>

        <div className="flex items-center gap-3 flex-wrap">
          {/* Search Input */}
          <div className="relative flex items-center">
            <Search size={15} className="absolute left-3 text-neutral-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search notes & highlights..."
              className="pl-9 pr-3 py-1.5 bg-[#252525] border border-white/10 rounded-lg text-xs text-white placeholder-neutral-500 focus:outline-hidden focus:border-primary w-56 transition-all"
            />
          </div>

          {/* Book Filter Dropdown */}
          <select
            value={selectedBookId}
            onChange={(e) => setSelectedBookId(e.target.value)}
            className="bg-[#252525] border border-white/10 rounded-lg text-xs text-neutral-200 px-3 py-1.5 focus:outline-hidden focus:border-primary transition-all cursor-pointer"
          >
            <option value="all">All Books</option>
            {books.map((b) => (
              <option key={b.id} value={b.id}>
                {b.title}
              </option>
            ))}
          </select>

          {/* Type Filter Pills */}
          <div className="flex items-center bg-[#252525] border border-white/10 rounded-lg p-0.5 text-xs">
            <button
              onClick={() => setSelectedType('all')}
              className={`px-3 py-1 rounded-md transition-colors ${
                selectedType === 'all'
                  ? 'bg-white/15 text-white font-medium'
                  : 'text-neutral-400 hover:text-white'
              }`}
            >
              All
            </button>
            <button
              onClick={() => setSelectedType('notes')}
              className={`px-3 py-1 rounded-md transition-colors ${
                selectedType === 'notes'
                  ? 'bg-white/15 text-white font-medium'
                  : 'text-neutral-400 hover:text-white'
              }`}
            >
              Notes
            </button>
            <button
              onClick={() => setSelectedType('highlights')}
              className={`px-3 py-1 rounded-md transition-colors ${
                selectedType === 'highlights'
                  ? 'bg-white/15 text-white font-medium'
                  : 'text-neutral-400 hover:text-white'
              }`}
            >
              Highlights
            </button>
          </div>

          {/* Export Button */}
          {filteredAnnotations.length > 0 && (
            <button
              onClick={handleExportMarkdown}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/10 hover:bg-white/15 text-neutral-200 hover:text-white text-xs transition-colors"
              title="Export visible annotations to Markdown"
            >
              <Download size={14} />
              <span>Export</span>
            </button>
          )}
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 overflow-y-auto py-6">
        {loading ? (
          <div className="flex flex-col items-center justify-center h-64 space-y-3">
            <div className="w-7 h-7 border-2 border-primary border-t-transparent rounded-full animate-spin" />
            <span className="text-xs text-neutral-400">Loading your annotations...</span>
          </div>
        ) : filteredAnnotations.length === 0 ? (
          <div className="flex flex-col items-center justify-center text-center py-20 text-neutral-400">
            <Highlighter
              size={48}
              className="mb-4 transition-colors opacity-60"
              style={{ color: currentTheme.accent }}
            />
            <h3 className="text-[17px] font-semibold text-white mb-1.5">
              {searchQuery || selectedBookId !== 'all' || selectedType !== 'all'
                ? 'No Matching Annotations'
                : 'No Annotations Yet'}
            </h3>
            <p className="text-[13px] max-w-sm text-neutral-400 mb-4">
              {searchQuery || selectedBookId !== 'all' || selectedType !== 'all'
                ? 'Try adjusting your search query or book filters to find what you are looking for.'
                : 'Highlights and margin notes you create while reading are saved and automatically organized here.'}
            </p>
            {(searchQuery || selectedBookId !== 'all' || selectedType !== 'all') && (
              <button
                onClick={() => {
                  setSearchQuery('');
                  setSelectedBookId('all');
                  setSelectedType('all');
                }}
                className="px-4 py-2 rounded-lg bg-white/10 hover:bg-white/15 text-xs text-white transition-colors"
              >
                Clear Filters
              </button>
            )}
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 pb-12">
            {filteredAnnotations.map((ann) => {
              const displayDate = ann.createdAt
                ? new Date(ann.createdAt).toLocaleDateString(undefined, {
                    month: 'short',
                    day: 'numeric',
                    year: 'numeric',
                  })
                : 'Recent';

              return (
                <div
                  key={ann.id}
                  className="flex flex-col justify-between p-4 rounded-xl bg-[#202020]/90 border border-white/10 hover:border-white/20 transition-all duration-200 group shadow-lg backdrop-blur-md"
                >
                  <div>
                    {/* Top Row: Book Badge + Page + Color Pill */}
                    <div className="flex items-center justify-between gap-2 mb-3">
                      <div className="flex items-center gap-1.5 min-w-0">
                        <BookOpen size={13} className="text-neutral-400 shrink-0" />
                        <span className="text-xs font-semibold text-neutral-200 truncate">
                          {ann.bookTitle || 'Book'}
                        </span>
                      </div>

                      <div className="flex items-center gap-2 shrink-0">
                        {ann.page !== undefined && (
                          <span className="text-[11px] font-mono px-2 py-0.5 rounded-md bg-white/10 text-neutral-300">
                            p. {ann.page}
                          </span>
                        )}
                        <span
                          className="w-3 h-3 rounded-full border border-white/20 shrink-0"
                          style={{ backgroundColor: ann.color || '#ffeb3b' }}
                          title={`Highlight color: ${ann.color}`}
                        />
                      </div>
                    </div>

                    {/* Highlighted Quote */}
                    <blockquote
                      className="text-xs text-neutral-100 pl-3 py-1 my-2 border-l-2 leading-relaxed italic select-text"
                      style={{ borderColor: ann.color || '#ffeb3b' }}
                    >
                      "{ann.selectedText || ann.text || ''}"
                    </blockquote>

                    {/* User Note (if any) */}
                    {ann.note && (
                      <div className="mt-3 p-2.5 rounded-lg bg-white/5 border border-white/5 text-xs text-neutral-200 leading-normal select-text">
                        <div className="text-[10px] uppercase font-semibold text-neutral-400 tracking-wider mb-1">
                          Note
                        </div>
                        {ann.note}
                      </div>
                    )}
                  </div>

                  {/* Bottom Footer Actions */}
                  <div className="flex items-center justify-between pt-3 mt-4 border-t border-white/5 text-[11px] text-neutral-400">
                    <span className="flex items-center gap-1">
                      <Calendar size={12} />
                      {displayDate}
                    </span>

                    <div className="flex items-center gap-1">
                      {/* Copy quote button */}
                      <button
                        onClick={() => handleCopy(ann.id, ann.selectedText || ann.text || '')}
                        className="p-1.5 rounded-md hover:bg-white/10 hover:text-white transition-colors"
                        title="Copy quote"
                      >
                        {copiedId === ann.id ? (
                          <Check size={13} className="text-green-400" />
                        ) : (
                          <Copy size={13} />
                        )}
                      </button>

                      {/* Jump to Reader */}
                      {onOpenBook && ann.bookId && (
                        <button
                          onClick={() => onOpenBook(ann.bookId!)}
                          className="p-1.5 rounded-md hover:bg-white/10 hover:text-white transition-colors"
                          title="Open book in reader"
                        >
                          <ExternalLink size={13} />
                        </button>
                      )}

                      {/* Delete annotation */}
                      <button
                        onClick={() => handleDelete(ann.id)}
                        className="p-1.5 rounded-md hover:bg-red-500/20 hover:text-red-400 transition-colors"
                        title="Delete annotation"
                      >
                        <Trash2 size={13} />
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};

export default AnnotationsView;
