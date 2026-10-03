"""
Domain models for Aquile Reader.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import re
import time
import uuid

# ---------------------------------------------------------------------------
# Shared theme vocabulary (WP-C single source of truth).
#
# Both the Settings dialog and the reader display popover import these
# names; nothing theme-related is duplicated in UI modules.
# ---------------------------------------------------------------------------

#: Page-theme keys persisted to ``AppSettings.theme`` (labels Title Case).
PAGE_THEMES: list[str] = ["white", "silver", "sepia", "night", "solarized", "custom"]
PAGE_THEME_LABELS: list[str] = ["White", "Silver", "Sepia", "Night", "Solarized", "Custom"]

#: Accent (color-theme) name -> ``#rrggbb`` hex map.
ACCENT_THEMES: dict[str, str] = {
    "turquoise": "#009688",
    "vineyard": "#7B1E3B",
    "darkside": "#37474F",
    "clearsky": "#29B6F6",
    "pulpyorange": "#F4511E",
}
ACCENT_LABELS: dict[str, str] = {
    "turquoise": "Turquoise",
    "vineyard": "Vineyard",
    "darkside": "Darkside",
    "clearsky": "Clear Sky",
    "pulpyorange": "Pulpy Orange",
}

_HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")


def validate_page_theme(key: str) -> str:
    """Return ``key`` if it is a known page theme, else raise ValueError."""
    if str(key) not in PAGE_THEMES:
        raise ValueError(f"unknown page theme: {key!r}")
    return str(key)


def validate_accent_hex(hex_color: str) -> str:
    """Return ``hex_color`` if it is a ``#rrggbb`` string, else raise."""
    if not isinstance(hex_color, str) or not _HEX_COLOR.match(hex_color):
        raise ValueError(f"accent must be a #rrggbb hex string, got {hex_color!r}")
    return hex_color


def validate_accent_name(name: str) -> str:
    """Return accent ``name`` if known, else raise ValueError."""
    if str(name) not in ACCENT_THEMES:
        raise ValueError(f"unknown accent theme: {name!r}")
    return str(name)


def accent_hex_for(name: str) -> str:
    """Return the ``#rrggbb`` hex for accent ``name`` (raises if unknown)."""
    return validate_accent_hex(ACCENT_THEMES[validate_accent_name(name)])


def clamp_transparency(value) -> int:
    """Clamp a transparency percent to the 0..100 range (WP-B slider bounds)."""
    try:
        number = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, min(100, number))

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
    accent: str = "turquoise"  # accent-theme name, see ACCENT_THEMES (WP-C)
    transparency: int = 0  # chrome transparency 0..100, see clamp_transparency

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

