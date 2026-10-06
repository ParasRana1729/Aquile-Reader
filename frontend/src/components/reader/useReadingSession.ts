import { useState, useEffect, useRef, useCallback } from 'react';
import { ReadingSessionStats } from '../../types/reader';

interface UseReadingSessionProps {
  bookId: string;
  initialPage?: number;
  initialTotalPages?: number;
  totalWordsEstimate?: number;
  onCheckpoint?: (stats: ReadingSessionStats) => void;
}

export function useReadingSession({
  bookId,
  initialPage = 1,
  initialTotalPages = 100,
  totalWordsEstimate = 50000,
  onCheckpoint,
}: UseReadingSessionProps) {
  // Load previous progress from localStorage if available
  const storageKey = `aquile_reading_session_${bookId}`;
  const savedState = (() => {
    try {
      const data = localStorage.getItem(storageKey);
      if (data) return JSON.parse(data);
    } catch {
      // ignore
    }
    return null;
  })();

  const [currentPage, setCurrentPage] = useState<number>(savedState?.currentPage || initialPage);
  const [totalPages, setTotalPages] = useState<number>(savedState?.totalPages || initialTotalPages);
  const [progressPercentage, setProgressPercentage] = useState<number>(
    savedState?.progressPercentage || Math.round((initialPage / Math.max(1, initialTotalPages)) * 100)
  );
  const [activeReadingSeconds, setActiveReadingSeconds] = useState<number>(
    savedState?.activeReadingSeconds || 0
  );
  const [wordsRead, setWordsRead] = useState<number>(savedState?.wordsRead || 0);
  const [readingSpeedWpm, setReadingSpeedWpm] = useState<number>(
    savedState?.readingSpeedWpm || 220
  );

  const lastActivityTimestamp = useRef<number>(Date.now());
  const wordsPerPage = Math.max(150, Math.round(totalWordsEstimate / Math.max(1, totalPages)));

  // Record user activity
  const markActive = useCallback(() => {
    lastActivityTimestamp.current = Date.now();
  }, []);

  // Set up activity event listeners
  useEffect(() => {
    const handleActivity = () => markActive();
    window.addEventListener('mousemove', handleActivity, { passive: true });
    window.addEventListener('keydown', handleActivity, { passive: true });
    window.addEventListener('wheel', handleActivity, { passive: true });
    window.addEventListener('touchstart', handleActivity, { passive: true });

    return () => {
      window.removeEventListener('mousemove', handleActivity);
      window.removeEventListener('keydown', handleActivity);
      window.removeEventListener('wheel', handleActivity);
      window.removeEventListener('touchstart', handleActivity);
    };
  }, [markActive]);

  // Active time ticker: ticks every second if user was active within last 25 seconds and document is visible
  useEffect(() => {
    const interval = setInterval(() => {
      if (document.hidden) return;
      const isRecentlyActive = Date.now() - lastActivityTimestamp.current < 25000;
      if (isRecentlyActive) {
        setActiveReadingSeconds((sec) => {
          const nextSec = sec + 1;
          // Recalculate WPM if reading for more than 10 seconds
          if (nextSec > 10 && wordsRead > 50) {
            const calculatedWpm = Math.min(800, Math.max(60, Math.round((wordsRead / nextSec) * 60)));
            setReadingSpeedWpm(calculatedWpm);
          }
          return nextSec;
        });
      }
    }, 1000);

    return () => clearInterval(interval);
  }, [wordsRead]);

  const latestStatsRef = useRef<ReadingSessionStats>({
    bookId,
    currentPage,
    totalPages,
    progressPercentage,
    activeReadingSeconds,
    wordsRead,
    readingSpeedWpm,
    lastCheckpoint: Date.now(),
  });

  useEffect(() => {
    latestStatsRef.current = {
      bookId,
      currentPage,
      totalPages,
      progressPercentage,
      activeReadingSeconds,
      wordsRead,
      readingSpeedWpm,
      lastCheckpoint: Date.now(),
    };
  }, [bookId, currentPage, totalPages, progressPercentage, activeReadingSeconds, wordsRead, readingSpeedWpm]);

  // Update progress helper - persists immediately to localStorage and invokes onCheckpoint
  const updateProgress = useCallback(
    (page: number, total: number, customPercent?: number) => {
      setCurrentPage(page);
      setTotalPages(total);
      const pct = customPercent !== undefined ? customPercent : Math.round((page / Math.max(1, total)) * 100);
      const boundedPct = Math.min(100, Math.max(0, pct));
      setProgressPercentage(boundedPct);

      // Estimate words read up to this page
      const estimatedWords = Math.min(totalWordsEstimate, page * wordsPerPage);
      setWordsRead(estimatedWords);
      markActive();

      const newStats: ReadingSessionStats = {
        bookId,
        currentPage: page,
        totalPages: total,
        progressPercentage: boundedPct,
        activeReadingSeconds: latestStatsRef.current.activeReadingSeconds,
        wordsRead: estimatedWords,
        readingSpeedWpm: latestStatsRef.current.readingSpeedWpm,
        lastCheckpoint: Date.now(),
      };
      latestStatsRef.current = newStats;

      try {
        localStorage.setItem(storageKey, JSON.stringify(newStats));
      } catch {}

      if (onCheckpoint) {
        onCheckpoint(newStats);
      }
    },
    [bookId, storageKey, totalWordsEstimate, wordsPerPage, markActive, onCheckpoint]
  );

  // Checkpoint timer: periodic checkpoint and unmount flush
  useEffect(() => {
    const checkpointInterval = setInterval(() => {
      if (onCheckpoint && latestStatsRef.current) {
        onCheckpoint(latestStatsRef.current);
      }
    }, 5000);

    return () => {
      clearInterval(checkpointInterval);
      if (onCheckpoint && latestStatsRef.current) {
        onCheckpoint(latestStatsRef.current);
      }
    };
  }, [onCheckpoint]);

  return {
    currentPage,
    totalPages,
    progressPercentage,
    activeReadingSeconds,
    wordsRead,
    readingSpeedWpm,
    updateProgress,
    setCurrentPage,
    setTotalPages,
    markActive,
  };
}
