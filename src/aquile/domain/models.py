"""
Domain models for Aquile Reader.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import time
import uuid

@dataclass
class Book:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = "Untitled"
    author: str = "Unknown Author"
    file_path: str = ""
    file_format: str = "epub"  # 'epub', 'pdf', 'cbz'
    cover_path: Optional[str] = None
    total_chapters: int = 1
    file_size_bytes: int = 0
    added_at: float = field(default_factory=time.time)
    last_read_at: Optional[float] = None
    is_favorite: bool = False

@dataclass
class ReadingProgress:
    book_id: str
    chapter_index: int = 0
    page_index: int = 0
    cfi: str = ""
    percentage: float = 0.0
    updated_at: float = field(default_factory=time.time)

@dataclass
class Annotation:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    book_id: str = ""
    chapter_index: int = 0
    cfi: str = ""
    start_offset: int = 0
    end_offset: int = 0
    text_content: str = ""
    note_text: str = ""
    color: str = "#FFEB3B"  # Default yellow highlight
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

@dataclass
class AppSettings:
    theme: str = "light"  # 'light', 'dark', 'sepia'
    font_family: str = "Sans"
    font_size: int = 16
    line_height: float = 1.6
    columns: int = 2      # Aquile Reader default: 2 columns
    margin_percent: int = 5
    auto_save_interval: float = 5.0  # NFR-01: 5-second location persistence bound

@dataclass(frozen=True)
class ReadingSession:
    id: str
    book_id: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    duration_seconds: float = 0.0
    active_seconds: float = 0.0
    idle_seconds: float = 0.0
    words_read: int = 0
    wpm: float = 0.0

@dataclass(frozen=True)
class BookStatistics:
    book_id: str
    total_reading_seconds: float = 0.0
    active_reading_seconds: float = 0.0
    total_sessions: int = 0
    estimated_words_read: int = 0
    average_wpm: float = 0.0
    last_session_at: Optional[datetime] = None

@dataclass(frozen=True)
class LibraryStatistics:
    total_books: int = 0
    books_in_progress: int = 0
    books_completed: int = 0
    total_reading_seconds: float = 0.0
    active_reading_seconds: float = 0.0
    total_words_read: int = 0
    average_wpm: float = 0.0
    format_counts: dict[str, int] = field(default_factory=dict)

