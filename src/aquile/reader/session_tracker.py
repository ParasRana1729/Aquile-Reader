"""
Reading session activity tracking engine for Aquile Reader.
Monitors active vs idle reading time, page-turn word accumulation, and WPM metrics (FR-15, NFR-01).
"""

import time
import uuid
import re
from datetime import datetime, timezone
from typing import Optional

try:
    from ..domain.models import ReadingSession
except (ImportError, ValueError):
    from aquile.domain.models import ReadingSession


def estimate_words_for_page(format: str, text_content: Optional[str] = None) -> int:
    """
    Estimate words read on a page turn based on document format and text content.
    - EPUB: exact word tokenization of text.
    - PDF: extracted text tokens if present, else 250 words per page typographic default.
    - Comic (CBZ/CBR): 50 words per page default.
    """
    fmt = (format or "").lower().strip()
    if fmt in ("cbz", "cbr", "comic"):
        return 50

    if fmt == "pdf":
        if text_content and text_content.strip():
            words = re.findall(r"\b\w+\b", text_content)
            return len(words) if len(words) > 0 else 250
        return 250

    if fmt == "epub":
        if text_content and text_content.strip():
            clean_text = re.sub(r"<[^>]+>", " ", text_content)
            words = re.findall(r"\b\w+\b", clean_text)
            return len(words)
        return 0

    # Fallback for other formats
    if text_content and text_content.strip():
        clean_text = re.sub(r"<[^>]+>", " ", text_content)
        words = re.findall(r"\b\w+\b", clean_text)
        return len(words)
    return 250


class ReadingSessionTracker:
    """
    Tracks an active reading session for a given book.
    Accumulates active duration and filters idle periods (120s for text, 60s for comics).
    """

    def __init__(
        self,
        book_id: str,
        format: str = "epub",
        idle_threshold_seconds: Optional[float] = None,
    ):
        self.book_id: str = book_id
        self.format: str = (format or "epub").lower().strip()

        if idle_threshold_seconds is not None:
            self.idle_threshold_seconds: float = float(idle_threshold_seconds)
        elif self.format in ("cbz", "cbr", "comic"):
            self.idle_threshold_seconds: float = 60.0
        else:
            self.idle_threshold_seconds: float = 120.0

        self.session_id: str = str(uuid.uuid4())
        self.started_at: datetime = datetime.now(timezone.utc)
        self.ended_at: Optional[datetime] = None

        self.active_seconds: float = 0.0
        self.idle_seconds: float = 0.0
        self.total_seconds: float = 0.0
        self.words_read: int = 0

        self._start_time: Optional[float] = None
        self._last_tick_time: Optional[float] = None
        self._last_activity_time: Optional[float] = None
        self._current_time: float = 0.0
        self._is_synthetic: bool = False
        self._is_ended: bool = False

    def register_activity(self, now: Optional[float] = None) -> None:
        """
        Resets the idle timer timestamp to the current time.
        """
        if now is not None:
            ts = float(now)
            self._current_time = ts
            self._is_synthetic = True
            self._last_activity_time = ts
            if self._start_time is None:
                self._start_time = ts
            if self._last_tick_time is None:
                self._last_tick_time = ts
        elif self._is_synthetic:
            self._last_activity_time = self._current_time
        else:
            ts = time.time()
            self._last_activity_time = ts
            self._current_time = ts
            if self._last_tick_time is None:
                self._start_time = ts
                self._last_tick_time = ts

    def tick(self, now: Optional[float] = None) -> None:
        """
        Periodic activity tick.
        Increments active_seconds if elapsed <= threshold, else increments idle_seconds.
        Increments total_seconds.
        """
        if now is not None:
            current_time = float(now)
            if not self._is_synthetic and self._last_tick_time is not None:
                self._start_time = current_time
                self._last_tick_time = current_time
                self._last_activity_time = current_time
                self._is_synthetic = True
                return
            self._is_synthetic = True
        else:
            current_time = time.time()

        self._current_time = current_time

        if self._last_tick_time is None:
            self._start_time = current_time
            self._last_tick_time = current_time
            if self._last_activity_time is None:
                self._last_activity_time = current_time
            return

        delta = max(0.0, current_time - self._last_tick_time)

        if self._last_activity_time is None:
            self._last_activity_time = current_time

        elapsed = current_time - self._last_activity_time

        if elapsed <= self.idle_threshold_seconds:
            self.active_seconds += delta
        else:
            self.idle_seconds += delta

        self.total_seconds += delta
        self._last_tick_time = current_time

    def record_page_turn(self, words_on_page: int) -> None:
        """
        Records a page turn and increments words_read.
        Resets the idle activity timer.
        """
        self.words_read += max(0, int(words_on_page))
        self.register_activity()

    @staticmethod
    def estimate_words_for_page(format: str, text_content: Optional[str] = None) -> int:
        """
        Exposes word estimation as a static method on the class.
        """
        return estimate_words_for_page(format, text_content)

    def end_session(self, now: Optional[float] = None) -> ReadingSession:
        """
        Finalizes the reading session and returns an immutable ReadingSession dataclass.
        Computes WPM with a >= 10s active duration guard and 1200 WPM upper clamp.
        """
        if now is not None:
            self.tick(now)

        if self.active_seconds >= 10.0 and self.words_read > 0:
            active_minutes = self.active_seconds / 60.0
            calculated_wpm = self.words_read / active_minutes
            wpm = min(1200.0, max(0.0, calculated_wpm))
            wpm = round(wpm, 2)
        else:
            wpm = 0.0

        if self._is_synthetic and self._current_time > 0:
            ended_at_dt = datetime.fromtimestamp(self._current_time, tz=timezone.utc)
            started_at_dt = (
                datetime.fromtimestamp(self._start_time, tz=timezone.utc)
                if self._start_time is not None and self._start_time > 0
                else self.started_at
            )
        else:
            started_at_dt = self.started_at
            ended_at_dt = datetime.now(timezone.utc)

        self.ended_at = ended_at_dt
        self._is_ended = True

        return ReadingSession(
            id=self.session_id,
            book_id=self.book_id,
            started_at=started_at_dt,
            ended_at=ended_at_dt,
            duration_seconds=float(self.total_seconds),
            active_seconds=float(self.active_seconds),
            idle_seconds=float(self.idle_seconds),
            words_read=int(self.words_read),
            wpm=float(wpm),
        )
