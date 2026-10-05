import React, { useState, useRef, useEffect } from 'react';
import {
  Play,
  Pause,
  Square,
  SkipBack,
  SkipForward,
  X,
  Volume2,
  Gauge,
  ChevronDown,
} from 'lucide-react';
import { useTTS } from '../../utils/tts';
import { ReadingTheme, READER_THEMES } from '../../types/reader';

export interface TTSBarProps {
  isOpen: boolean;
  onClose: () => void;
  currentPage?: number;
  totalPages?: number;
  theme?: ReadingTheme;
  onPlayRequest?: () => void;
}

const SPEED_OPTIONS = [0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0];

export const TTSBar: React.FC<TTSBarProps> = ({
  isOpen,
  onClose,
  currentPage,
  totalPages,
  theme = 'night',
  onPlayRequest,
}) => {
  const {
    status,
    sentences,
    currentIndex,
    currentSentence,
    currentWord,
    charIndex,
    charLength,
    rate,
    voice,
    voices,
    isAvailable,
    play,
    pause,
    resume,
    stop,
    nextSentence,
    prevSentence,
    setRate,
    setVoice,
  } = useTTS();

  const [isSpeedOpen, setIsSpeedOpen] = useState(false);
  const [isVoiceOpen, setIsVoiceOpen] = useState(false);
  const voiceDropdownRef = useRef<HTMLDivElement>(null);
  const speedDropdownRef = useRef<HTMLDivElement>(null);

  // Close dropdowns on outside click
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (
        voiceDropdownRef.current &&
        !voiceDropdownRef.current.contains(e.target as Node)
      ) {
        setIsVoiceOpen(false);
      }
      if (
        speedDropdownRef.current &&
        !speedDropdownRef.current.contains(e.target as Node)
      ) {
        setIsSpeedOpen(false);
      }
    };
    window.addEventListener('mousedown', handleClickOutside);
    return () => window.removeEventListener('mousedown', handleClickOutside);
  }, []);

  if (!isOpen) return null;

  const isDark = READER_THEMES[theme]?.isDark ?? true;
  const isPlaying = status === 'playing';
  const isPaused = status === 'paused';
  const totalSentences = sentences.length;
  const progressPercent =
    totalSentences > 0 ? Math.round(((currentIndex + 1) / totalSentences) * 100) : 0;

  const handlePlayToggle = () => {
    if (isPlaying) {
      pause();
    } else if (isPaused) {
      resume();
    } else {
      if (totalSentences > 0) {
        play();
      } else if (onPlayRequest) {
        onPlayRequest();
      }
    }
  };

  const handleStop = () => {
    stop();
  };

  const handleClose = () => {
    stop();
    onClose();
  };

  // Render current sentence with word-boundary highlight
  const renderSentenceSnippet = () => {
    if (!currentSentence) {
      return (
        <span className="italic opacity-50">
          Ready to narrate. Press play to begin voice reading.
        </span>
      );
    }

    if (!currentWord || charIndex < 0 || charIndex >= currentSentence.length) {
      return <span>{currentSentence}</span>;
    }

    const before = currentSentence.slice(0, charIndex);
    const length = charLength > 0 ? charLength : currentWord.length;
    const highlight = currentSentence.slice(charIndex, charIndex + length);
    const after = currentSentence.slice(charIndex + length);

    return (
      <span>
        {before}
        <mark className="bg-primary/30 text-white font-semibold rounded px-1 py-0.5 border border-primary/40 shadow-sm transition-all">
          {highlight || currentWord}
        </mark>
        {after}
      </span>
    );
  };

  return (
    <div
      className={`fixed bottom-6 left-1/2 -translate-x-1/2 z-50 w-[95%] max-w-2xl rounded-2xl shadow-2xl backdrop-blur-xl border transition-all duration-300 select-none animate-in fade-in slide-in-from-bottom-5 ${
        isDark
          ? 'bg-[#1e1e1e]/95 border-white/15 text-neutral-100 shadow-black/60'
          : 'bg-[#f5f5f5]/95 border-black/10 text-neutral-900 shadow-neutral-500/20'
      }`}
    >
      <div className="p-4 flex flex-col gap-3">
        {/* Top Header Row: Status, Sentence Tracker, and Close */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div
              className={`p-1.5 rounded-lg flex items-center justify-center transition-colors ${
                isPlaying
                  ? 'bg-primary text-white animate-pulse'
                  : 'bg-white/10 text-neutral-300'
              }`}
            >
              <Volume2 size={16} />
            </div>
            <div className="flex flex-col">
              <span className="text-xs font-semibold tracking-wider uppercase opacity-90">
                Voice Narration
              </span>
              <span className="text-[11px] opacity-60">
                {totalSentences > 0 ? (
                  <>
                    Sentence {currentIndex + 1} of {totalSentences}
                    {currentPage && totalPages ? ` · Page ${currentPage}` : ''}
                  </>
                ) : (
                  <>Ready to read {currentPage ? `page ${currentPage}` : 'page'}</>
                )}
              </span>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {!isAvailable && (
              <span className="text-[10px] text-amber-400 bg-amber-400/10 px-2 py-0.5 rounded border border-amber-400/20 font-medium">
                Speech API not available
              </span>
            )}
            <button
              onClick={handleClose}
              className="p-1.5 rounded-full hover:bg-white/10 transition-colors text-neutral-400 hover:text-white"
              title="Close Voice Narration"
            >
              <X size={16} />
            </button>
          </div>
        </div>

        {/* Text Snippet with Word Highlight */}
        <div
          className={`rounded-xl p-3 border text-xs sm:text-sm leading-relaxed max-h-20 overflow-y-auto select-text font-serif transition-colors ${
            isDark
              ? 'bg-black/35 border-white/10 text-neutral-200'
              : 'bg-white/70 border-black/10 text-neutral-800'
          }`}
        >
          {renderSentenceSnippet()}
        </div>

        {/* Mini Progress Bar */}
        <div className="w-full bg-white/10 h-1 rounded-full overflow-hidden">
          <div
            className="h-full bg-primary transition-all duration-300 ease-out"
            style={{ width: `${progressPercent}%` }}
          />
        </div>

        {/* Bottom Control Row */}
        <div className="flex items-center justify-between gap-2 pt-1">
          {/* Sentence Navigation & Playback */}
          <div className="flex items-center gap-2">
            {/* Skip Previous Sentence */}
            <button
              onClick={prevSentence}
              disabled={totalSentences === 0 || currentIndex === 0}
              className="p-2 rounded-lg hover:bg-white/10 disabled:opacity-30 disabled:pointer-events-none transition-colors"
              title="Previous Sentence"
            >
              <SkipBack size={18} />
            </button>

            {/* Play / Pause Toggle */}
            <button
              onClick={handlePlayToggle}
              className={`p-2.5 rounded-full font-medium transition-all shadow-md active:scale-95 ${
                isPlaying
                  ? 'bg-primary text-white shadow-primary/30 ring-2 ring-primary/40'
                  : 'bg-primary text-white hover:brightness-110 shadow-primary/20'
              }`}
              title={isPlaying ? 'Pause' : 'Play'}
            >
              {isPlaying ? <Pause size={18} /> : <Play size={18} className="translate-x-0.5" />}
            </button>

            {/* Stop */}
            <button
              onClick={handleStop}
              disabled={status === 'idle' || status === 'stopped'}
              className="p-2 rounded-lg hover:bg-white/10 disabled:opacity-30 disabled:pointer-events-none transition-colors"
              title="Stop Narration"
            >
              <Square size={16} />
            </button>

            {/* Skip Next Sentence */}
            <button
              onClick={nextSentence}
              disabled={totalSentences === 0 || currentIndex >= totalSentences - 1}
              className="p-2 rounded-lg hover:bg-white/10 disabled:opacity-30 disabled:pointer-events-none transition-colors"
              title="Next Sentence"
            >
              <SkipForward size={18} />
            </button>
          </div>

          {/* Settings: Voice & Speed Dropdowns */}
          <div className="flex items-center gap-2">
            {/* Voice Selector Dropdown */}
            <div className="relative" ref={voiceDropdownRef}>
              <button
                type="button"
                onClick={() => setIsVoiceOpen(!isVoiceOpen)}
                className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border text-xs max-w-[140px] sm:max-w-[200px] truncate transition-colors ${
                  isDark
                    ? 'bg-white/5 border-white/10 hover:bg-white/10 text-neutral-200'
                    : 'bg-black/5 border-black/10 hover:bg-black/10 text-neutral-800'
                }`}
                title={voice ? `${voice.name} (${voice.lang})` : 'Select Voice'}
              >
                <span className="truncate">
                  {voice ? voice.name.replace(/Microsoft |Google /g, '') : 'Default Voice'}
                </span>
                <ChevronDown size={12} className="opacity-60 flex-shrink-0" />
              </button>

              {isVoiceOpen && (
                <div
                  className={`absolute bottom-full right-0 mb-2 w-64 max-h-56 overflow-y-auto rounded-xl shadow-2xl border p-1 z-50 backdrop-blur-xl ${
                    isDark
                      ? 'bg-[#2b2b2b] border-white/15 text-neutral-200'
                      : 'bg-white border-black/15 text-neutral-800'
                  }`}
                >
                  <div className="px-2 py-1 text-[10px] font-semibold uppercase tracking-wider opacity-50">
                    Voice Selection
                  </div>
                  {voices.length === 0 ? (
                    <div className="px-2 py-2 text-xs opacity-60 italic">
                      No system voices detected
                    </div>
                  ) : (
                    voices.map((v) => {
                      const isSelected = voice?.voiceURI === v.voiceURI;
                      return (
                        <button
                          key={v.voiceURI || v.name}
                          onClick={() => {
                            setVoice(v);
                            setIsVoiceOpen(false);
                          }}
                          className={`w-full text-left px-2.5 py-1.5 rounded-lg text-xs transition-colors flex items-center justify-between ${
                            isSelected
                              ? 'bg-primary/20 text-primary font-medium'
                              : isDark
                              ? 'hover:bg-white/10'
                              : 'hover:bg-black/5'
                          }`}
                        >
                          <span className="truncate pr-2">
                            {v.name.replace(/Microsoft |Google /g, '')}
                          </span>
                          <span className="text-[10px] opacity-50 font-mono flex-shrink-0">
                            {v.lang}
                          </span>
                        </button>
                      );
                    })
                  )}
                </div>
              )}
            </div>

            {/* Speed Selector Dropdown */}
            <div className="relative" ref={speedDropdownRef}>
              <button
                type="button"
                onClick={() => setIsSpeedOpen(!isSpeedOpen)}
                className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border text-xs font-mono transition-colors ${
                  isDark
                    ? 'bg-white/5 border-white/10 hover:bg-white/10 text-neutral-200'
                    : 'bg-black/5 border-black/10 hover:bg-black/10 text-neutral-800'
                }`}
                title="Speaking Speed"
              >
                <Gauge size={13} className="text-primary flex-shrink-0" />
                <span>{rate}x</span>
                <ChevronDown size={11} className="opacity-60 flex-shrink-0" />
              </button>

              {isSpeedOpen && (
                <div
                  className={`absolute bottom-full right-0 mb-2 w-28 rounded-xl shadow-2xl border p-1 z-50 backdrop-blur-xl ${
                    isDark
                      ? 'bg-[#2b2b2b] border-white/15 text-neutral-200'
                      : 'bg-white border-black/15 text-neutral-800'
                  }`}
                >
                  <div className="px-2 py-1 text-[10px] font-semibold uppercase tracking-wider opacity-50 font-sans">
                    Speed
                  </div>
                  {SPEED_OPTIONS.map((speed) => {
                    const isSelected = rate === speed;
                    return (
                      <button
                        key={speed}
                        onClick={() => {
                          setRate(speed);
                          setIsSpeedOpen(false);
                        }}
                        className={`w-full text-left px-2.5 py-1.5 rounded-lg text-xs font-mono transition-colors flex items-center justify-between ${
                          isSelected
                            ? 'bg-primary/20 text-primary font-medium'
                            : isDark
                            ? 'hover:bg-white/10'
                            : 'hover:bg-black/5'
                        }`}
                      >
                        <span>{speed}x</span>
                        {isSelected && (
                          <span className="w-1.5 h-1.5 rounded-full bg-primary" />
                        )}
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
