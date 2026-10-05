/**
 * Aquile Reader - Text-to-Speech (TTS) Engine & Web Speech API Wrapper
 *
 * Provides sentence segmentation, boundary word/sentence tracking,
 * playback controls (play/pause/resume/stop), sentence navigation,
 * rate/pitch/voice configuration, and event listeners.
 */

import { useState, useEffect, useCallback } from 'react';

export type TTSStatus = 'idle' | 'playing' | 'paused' | 'stopped';

export interface TTSBoundaryEvent {
  charIndex: number;
  charLength: number;
  word: string;
  sentenceIndex: number;
}

export interface TTSState {
  status: TTSStatus;
  sentences: string[];
  currentIndex: number;
  currentSentence: string;
  currentWord: string;
  charIndex: number;
  charLength: number;
  rate: number;
  pitch: number;
  voice: SpeechSynthesisVoice | null;
  voices: SpeechSynthesisVoice[];
  isAvailable: boolean;
}

// Fallback mock voices for SSR, initial loading, or platforms with delayed voice enumeration
export const FALLBACK_VOICES: Array<Partial<SpeechSynthesisVoice>> = [
  {
    name: 'Natural English (United States)',
    lang: 'en-US',
    default: true,
    localService: true,
    voiceURI: 'default-en-us',
  },
  {
    name: 'Natural English (Great Britain)',
    lang: 'en-GB',
    default: false,
    localService: true,
    voiceURI: 'default-en-gb',
  },
];

/**
 * Intelligent sentence segmentation.
 * Uses Intl.Segmenter where supported (Chrome 87+, Safari 14.1+, Firefox 125+),
 * with robust regex-based splitting fallback that respects abbreviations.
 */
export function segmentSentences(text: string): string[] {
  if (!text || !text.trim()) return [];

  const normalized = text
    .replace(/\r\n/g, '\n')
    .replace(/\t/g, ' ')
    .replace(/\u00A0/g, ' ')
    .trim();

  // Protect common honorifics & abbreviations so we don't break early
  const abbreviations = [
    'Mr',
    'Mrs',
    'Ms',
    'Dr',
    'Prof',
    'Gen',
    'Col',
    'St',
    'vs',
    'etc',
    'e.g',
    'i.e',
    'approx',
    'dept',
    'Jr',
    'Sr',
    'Capt',
    'Lt',
    'Sgt',
  ];

  let placeholderText = normalized;
  abbreviations.forEach((abbr, i) => {
    const regex = new RegExp(`\\b${abbr}\\.`, 'gi');
    placeholderText = placeholderText.replace(regex, `__ABBR_${i}__`);
  });

  const restore = (str: string): string => {
    let res = str;
    abbreviations.forEach((abbr, i) => {
      res = res.replace(new RegExp(`__ABBR_${i}__`, 'g'), `${abbr}.`);
    });
    return res.trim();
  };

  let rawSentences: string[] = [];

  // 1. Try native Intl.Segmenter with protected abbreviations
  if (typeof Intl !== 'undefined' && 'Segmenter' in Intl) {
    try {
      const segmenter = new (Intl as any).Segmenter('en', { granularity: 'sentence' });
      const rawSegments = Array.from(segmenter.segment(placeholderText)) as Array<{ segment: string }>;
      rawSentences = rawSegments
        .map((s) => restore(s.segment))
        .filter((s) => s.length > 0);
    } catch {
      // fallback to regex
    }
  }

  // 2. Fallback regex segmenter if Intl.Segmenter failed or empty
  if (rawSentences.length === 0) {
    const parts = placeholderText.split(/(?<=[.?!…]["'»”’]?)\s+(?=[A-Z0-9"“‘—])/);
    for (const part of parts) {
      const restored = restore(part);
      if (restored.length > 0) {
        rawSentences.push(restored);
      }
    }
  }

  return rawSentences.length > 0 ? rawSentences : [normalized];
}

export class TTSEngine {
  private status: TTSStatus = 'idle';
  private sentences: string[] = [];
  private currentIndex: number = 0;
  private currentWord: string = '';
  private currentCharIndex: number = 0;
  private currentCharLength: number = 0;

  private rate: number = 1.0;
  private pitch: number = 1.0;
  private selectedVoice: SpeechSynthesisVoice | null = null;
  private voices: SpeechSynthesisVoice[] = [];

  private activeUtterance: SpeechSynthesisUtterance | null = null;
  private heartbeatTimer: ReturnType<typeof setInterval> | null = null;

  private stateListeners: Set<(state: TTSState) => void> = new Set();
  private boundaryListeners: Set<(event: TTSBoundaryEvent) => void> = new Set();
  private endListeners: Set<() => void> = new Set();

  constructor() {
    this.initVoices();
  }

  private isSpeechAvailable(): boolean {
    return typeof window !== 'undefined' && 'speechSynthesis' in window;
  }

  private initVoices(): void {
    if (!this.isSpeechAvailable()) return;

    const load = () => {
      try {
        const available = window.speechSynthesis.getVoices();
        if (available && available.length > 0) {
          this.voices = available;
          if (!this.selectedVoice) {
            // Prefer an English voice or the system default
            this.selectedVoice =
              available.find((v) => v.default && v.lang.startsWith('en')) ||
              available.find((v) => v.lang.startsWith('en')) ||
              available.find((v) => v.default) ||
              available[0];
          }
          this.notifyState();
        }
      } catch (err) {
        console.warn('TTS: Voice enumeration error', err);
      }
    };

    load();

    if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
      if (window.speechSynthesis.onvoiceschanged !== undefined) {
        window.speechSynthesis.onvoiceschanged = load;
      }
    }
  }

  public getVoices(): SpeechSynthesisVoice[] {
    if (this.voices.length > 0) return this.voices;
    if (this.isSpeechAvailable()) {
      const v = window.speechSynthesis.getVoices();
      if (v && v.length > 0) {
        this.voices = v;
        return v;
      }
    }
    // Return mock voices if browser voices haven't loaded yet
    return (FALLBACK_VOICES as unknown) as SpeechSynthesisVoice[];
  }

  public getState(): TTSState {
    return {
      status: this.status,
      sentences: this.sentences,
      currentIndex: this.currentIndex,
      currentSentence: this.sentences[this.currentIndex] || '',
      currentWord: this.currentWord,
      charIndex: this.currentCharIndex,
      charLength: this.currentCharLength,
      rate: this.rate,
      pitch: this.pitch,
      voice: this.selectedVoice,
      voices: this.getVoices(),
      isAvailable: this.isSpeechAvailable(),
    };
  }

  private notifyState(): void {
    const state = this.getState();
    for (const listener of this.stateListeners) {
      listener(state);
    }
  }

  private startHeartbeat(): void {
    this.stopHeartbeat();
    if (!this.isSpeechAvailable()) return;

    // Chrome bug: SpeechSynthesis pauses silently on longer texts without heartbeat
    this.heartbeatTimer = setInterval(() => {
      if (this.status === 'playing' && window.speechSynthesis.speaking) {
        window.speechSynthesis.pause();
        window.speechSynthesis.resume();
      }
    }, 10000);
  }

  private stopHeartbeat(): void {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }

  /**
   * Load text and split into sentences without immediately playing.
   */
  public loadText(text: string, startIndex: number = 0): void {
    this.stop();
    this.sentences = segmentSentences(text);
    this.currentIndex = Math.max(0, Math.min(startIndex, this.sentences.length - 1));
    this.currentWord = '';
    this.currentCharIndex = 0;
    this.currentCharLength = 0;
    this.status = 'idle';
    this.notifyState();
  }

  /**
   * Start playback from current sentence or provide new text.
   */
  public play(text?: string, startIndex?: number): void {
    if (!this.isSpeechAvailable()) {
      console.warn('TTS: Speech synthesis is not supported on this platform.');
      return;
    }

    if (text !== undefined) {
      this.sentences = segmentSentences(text);
      this.currentIndex = startIndex !== undefined ? Math.max(0, startIndex) : 0;
    } else if (startIndex !== undefined) {
      this.currentIndex = Math.max(0, Math.min(startIndex, this.sentences.length - 1));
    }

    if (this.sentences.length === 0) {
      this.status = 'idle';
      this.notifyState();
      return;
    }

    if (this.status === 'paused' && text === undefined && startIndex === undefined) {
      this.resume();
      return;
    }

    this.status = 'playing';
    this.speakCurrentSentence();
  }

  private speakCurrentSentence(): void {
    if (!this.isSpeechAvailable()) return;

    window.speechSynthesis.cancel();
    this.stopHeartbeat();

    if (this.currentIndex < 0 || this.currentIndex >= this.sentences.length) {
      this.status = 'idle';
      this.currentWord = '';
      this.notifyState();
      for (const cb of this.endListeners) {
        cb();
      }
      return;
    }

    const sentenceText = this.sentences[this.currentIndex];
    this.currentCharIndex = 0;
    this.currentCharLength = 0;
    this.currentWord = '';

    const utterance = new SpeechSynthesisUtterance(sentenceText);
    this.activeUtterance = utterance;

    utterance.rate = this.rate;
    utterance.pitch = this.pitch;
    if (this.selectedVoice) {
      utterance.voice = this.selectedVoice;
    }

    // Boundary event listener for word-by-word tracking
    utterance.onboundary = (e: SpeechSynthesisEvent) => {
      if (this.status !== 'playing') return;

      const charIdx = e.charIndex;
      let charLen = e.charLength || 0;
      let word = '';

      if (charLen > 0) {
        word = sentenceText.substring(charIdx, charIdx + charLen);
      } else {
        const remaining = sentenceText.slice(charIdx);
        const match = remaining.match(/^[\w’']+/);
        word = match ? match[0] : '';
        charLen = word.length;
      }

      this.currentCharIndex = charIdx;
      this.currentCharLength = charLen;
      this.currentWord = word.trim();

      const event: TTSBoundaryEvent = {
        charIndex: charIdx,
        charLength: charLen,
        word: this.currentWord,
        sentenceIndex: this.currentIndex,
      };

      for (const bl of this.boundaryListeners) {
        bl(event);
      }
      this.notifyState();
    };

    utterance.onend = () => {
      if (this.status !== 'playing') return;

      // Move to next sentence
      if (this.currentIndex < this.sentences.length - 1) {
        this.currentIndex++;
        this.speakCurrentSentence();
      } else {
        // Finished all sentences in this block
        this.status = 'idle';
        this.currentWord = '';
        this.notifyState();
        for (const cb of this.endListeners) {
          cb();
        }
      }
    };

    utterance.onerror = (e: SpeechSynthesisErrorEvent) => {
      // Interrupted/canceled is expected when changing tracks
      if (e.error === 'interrupted' || e.error === 'canceled') {
        return;
      }
      console.warn('TTS SpeechSynthesis error:', e.error);
      this.status = 'idle';
      this.notifyState();
    };

    this.startHeartbeat();
    window.speechSynthesis.speak(utterance);
    this.notifyState();
  }

  public pause(): void {
    if (!this.isSpeechAvailable()) return;
    if (this.status === 'playing') {
      window.speechSynthesis.pause();
      this.status = 'paused';
      this.stopHeartbeat();
      this.notifyState();
    }
  }

  public resume(): void {
    if (!this.isSpeechAvailable()) return;
    if (this.status === 'paused') {
      this.status = 'playing';
      if (window.speechSynthesis.paused) {
        window.speechSynthesis.resume();
        this.startHeartbeat();
        this.notifyState();
      } else {
        // If synthesis dropped utterance while paused, restart sentence
        this.speakCurrentSentence();
      }
    } else if (this.status === 'idle' || this.status === 'stopped') {
      this.play();
    }
  }

  public stop(): void {
    if (!this.isSpeechAvailable()) return;
    window.speechSynthesis.cancel();
    this.stopHeartbeat();
    this.status = 'stopped';
    this.currentWord = '';
    this.currentCharIndex = 0;
    this.currentCharLength = 0;
    this.activeUtterance = null;
    this.notifyState();
  }

  public nextSentence(): void {
    if (this.sentences.length === 0) return;
    if (this.currentIndex < this.sentences.length - 1) {
      this.currentIndex++;
      if (this.status === 'playing') {
        this.speakCurrentSentence();
      } else {
        this.currentWord = '';
        this.currentCharIndex = 0;
        this.notifyState();
      }
    } else {
      this.stop();
      for (const cb of this.endListeners) {
        cb();
      }
    }
  }

  public prevSentence(): void {
    if (this.sentences.length === 0) return;
    if (this.currentIndex > 0) {
      this.currentIndex--;
      if (this.status === 'playing') {
        this.speakCurrentSentence();
      } else {
        this.currentWord = '';
        this.currentCharIndex = 0;
        this.notifyState();
      }
    } else {
      // Replay first sentence from beginning
      if (this.status === 'playing') {
        this.speakCurrentSentence();
      }
    }
  }

  public jumpToSentence(index: number): void {
    if (index >= 0 && index < this.sentences.length) {
      this.currentIndex = index;
      if (this.status === 'playing') {
        this.speakCurrentSentence();
      } else {
        this.currentWord = '';
        this.currentCharIndex = 0;
        this.notifyState();
      }
    }
  }

  public setRate(rate: number): void {
    const clamped = Math.max(0.5, Math.min(2.5, rate));
    this.rate = clamped;
    if (this.status === 'playing') {
      // Smoothly replay sentence with new rate
      this.speakCurrentSentence();
    } else {
      this.notifyState();
    }
  }

  public setPitch(pitch: number): void {
    const clamped = Math.max(0.5, Math.min(2.0, pitch));
    this.pitch = clamped;
    if (this.status === 'playing') {
      this.speakCurrentSentence();
    } else {
      this.notifyState();
    }
  }

  public setVoice(voice: SpeechSynthesisVoice | string): void {
    if (typeof voice === 'string') {
      const found = this.voices.find((v) => v.voiceURI === voice || v.name === voice);
      if (found) this.selectedVoice = found;
    } else {
      this.selectedVoice = voice;
    }

    if (this.status === 'playing') {
      this.speakCurrentSentence();
    } else {
      this.notifyState();
    }
  }

  public subscribe(listener: (state: TTSState) => void): () => void {
    this.stateListeners.add(listener);
    listener(this.getState());
    return () => {
      this.stateListeners.delete(listener);
    };
  }

  public onBoundary(listener: (event: TTSBoundaryEvent) => void): () => void {
    this.boundaryListeners.add(listener);
    return () => {
      this.boundaryListeners.delete(listener);
    };
  }

  public onEnd(listener: () => void): () => void {
    this.endListeners.add(listener);
    return () => {
      this.endListeners.delete(listener);
    };
  }
}

// Global singleton instance for reader sessions
export const ttsEngine = new TTSEngine();

/**
 * Custom React Hook for reading & controlling TTS
 */
export function useTTS() {
  const [state, setState] = useState<TTSState>(() => ttsEngine.getState());

  useEffect(() => {
    const unsubscribe = ttsEngine.subscribe((next) => {
      setState(next);
    });
    return () => {
      unsubscribe();
    };
  }, []);

  const play = useCallback((text?: string, startIndex?: number) => {
    ttsEngine.play(text, startIndex);
  }, []);

  const pause = useCallback(() => {
    ttsEngine.pause();
  }, []);

  const resume = useCallback(() => {
    ttsEngine.resume();
  }, []);

  const stop = useCallback(() => {
    ttsEngine.stop();
  }, []);

  const nextSentence = useCallback(() => {
    ttsEngine.nextSentence();
  }, []);

  const prevSentence = useCallback(() => {
    ttsEngine.prevSentence();
  }, []);

  const jumpToSentence = useCallback((index: number) => {
    ttsEngine.jumpToSentence(index);
  }, []);

  const setRate = useCallback((rate: number) => {
    ttsEngine.setRate(rate);
  }, []);

  const setPitch = useCallback((pitch: number) => {
    ttsEngine.setPitch(pitch);
  }, []);

  const setVoice = useCallback((voice: SpeechSynthesisVoice | string) => {
    ttsEngine.setVoice(voice);
  }, []);

  const loadText = useCallback((text: string, startIndex?: number) => {
    ttsEngine.loadText(text, startIndex);
  }, []);

  return {
    ...state,
    play,
    pause,
    resume,
    stop,
    nextSentence,
    prevSentence,
    jumpToSentence,
    setRate,
    setPitch,
    setVoice,
    loadText,
    segmentSentences,
  };
}
