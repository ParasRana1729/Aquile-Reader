# Project: Aquile Reader — WP-10 & WP-11 Incremental Feature Slice

## Architecture
Aquile Reader is a native Linux desktop e-book and document reader built with Python 3, GTK4, Libadwaita, and SQLite WAL storage.
The architecture follows clean separation of concerns:
- **Domain Layer (`src/aquile/domain/`)**: Immutable dataclasses representing core entities (`Book`, `ReadingProgress`, `Annotation`, `ReadingSession`, `BookStatistics`, `LibraryStatistics`).
- **Storage Layer (`src/aquile/storage/`)**: SQLite connection manager with WAL mode (`PRAGMA journal_mode = WAL; synchronous = NORMAL; foreign_keys = ON;`), schema version migrations, and repositories (`BookRepository`, `ProgressRepository`, `AnnotationRepository`, `SettingsRepository`, `StatisticsRepository`).
- **Reader Engines (`src/aquile/reader/`)**:
  - `EpubParser` & `ChapterPaginator`: Reflowable text reader.
  - `ComicArchiveEngine`: Comic archive reader (`.cbz` via `zipfile`, `.cbr` via `libarchive.so.13`/ctypes), natural alphanumeric sorting, single-page and double-page spread pairing (isolated cover, LTR Western vs RTL Manga pair inversion).
  - `PdfDocumentEngine`: Fixed-layout PDF document reader using in-memory `libpoppler-glib.so.8` + `libcairo.so.2` via `ctypes` (with `/usr/bin/pdftoppm` CLI fallback), page count, dimension extraction, and zoom/fit calculations (fit-to-width, fit-to-page, custom scale).
  - `ReadingSessionTracker`: Activity tracking engine monitoring active vs idle time (120s idle threshold for text, 60s for comics), words read estimation, and words-per-minute (WPM) calculation.
- **UI Layer (`src/aquile/ui/`)**:
  - `AquileReaderApp` (`src/aquile/app.py`): Root application orchestrating `Adw.ApplicationWindow`, theme manager, and `Gtk.Stack` switching between `"library"` and active reader views.
  - `LibraryView` (`src/aquile/ui/library_view.py`): Shelf grid of books, file import chooser (`.epub`, `.pdf`, `.cbz`, `.cbr`), statistics entry button.
  - `ReaderView` (`src/aquile/ui/reader_view.py`): EPUB two-column reading canvas.
  - `ComicReaderView` (`src/aquile/ui/comic_view.py`): Comic graphic canvas displaying single or double pages in `Gtk.Picture` with aspect ratio containment, spread controls, and LTR/RTL mode switching.
  - `PdfReaderView` (`src/aquile/ui/pdf_view.py`): PDF canvas displaying vector-rendered pages in `Gtk.Picture`, zoom/fit controls, and direct page jumping.
  - `StatisticsDialog` (`src/aquile/ui/statistics_dialog.py`): Libadwaita dialog with `Adw.ViewSwitcher` tabs ("Library Overview" and "Book Insights").

## Code Layout
- `src/aquile/domain/models.py`: Domain dataclasses (`ReadingSession`, `BookStatistics`, `LibraryStatistics`).
- `src/aquile/storage/database.py`: Schema v2 migration (`reading_sessions`, `reading_statistics`).
- `src/aquile/storage/repository.py`: `StatisticsRepository` implementing session recording and statistics queries.
- `src/aquile/reader/comic_reader.py`: `ComicArchiveEngine` handling CBZ/CBR extraction, natural sort, and spread logic.
- `src/aquile/reader/pdf_reader.py`: `PdfDocumentEngine` handling Poppler ctypes/CLI rendering, dimensions, zoom/fit math.
- `src/aquile/reader/session_tracker.py`: `ReadingSessionTracker` tracking duration, idle filtering, words, and WPM.
- `src/aquile/ui/comic_view.py`: `ComicReaderView` GTK4 widget.
- `src/aquile/ui/pdf_view.py`: `PdfReaderView` GTK4 widget.
- `src/aquile/ui/statistics_dialog.py`: `StatisticsDialog` Libadwaita dialog.
- `src/aquile/ui/library_view.py`: Multi-format import and stats button integration.
- `src/aquile/app.py`: Polymorphic reader routing in `open_book()`.
- `scripts/generate_fixtures.py`: Fixture generator with valid PNG CRC repair for `fixtures/sample-comic.cbz`.
- `tests/`: Automated unit, integration, and E2E test suites.

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Schema v2 Migration | Add `reading_sessions` and `reading_statistics` tables to SQLite WAL DB | M1 | R4, survey |
| 2 | Statistics Domain Models | Add `ReadingSession`, `BookStatistics`, `LibraryStatistics` dataclasses | M1 | R3, survey |
| 3 | Statistics Storage Repository | `StatisticsRepository` for saving sessions and aggregating reading stats | M1 | R3, R4 |
| 4 | Fixture CRC Repair | Repair invalid PNG CRC in `sample-comic.cbz` fixture via `generate_fixtures.py` | M1 | survey |
| 5 | Comic Archive Extraction | Open `.cbz` via `zipfile` and `.cbr` via `libarchive`/fallback | M2 | R1 |
| 6 | Comic Natural Page Sorting | Natural alphanumeric sort (`page2` before `page10`) | M2 | R1 |
| 7 | Comic Spread Pairing | Single-page mode and double-page spread mode with isolated cover | M2 | R1 |
| 8 | Comic Reading Direction | Selectable Left-to-Right (Western) and Right-to-Left (Manga) spread inversion | M2 | R1 |
| 9 | Comic UI & Aspect Ratio | `ComicReaderView` using `Gtk.Picture` preserving aspect ratio (`CONTAIN`) | M2 | R1 |
| 10 | Comic Reading Progress | Periodic 5-second checkpoint and navigation progress saving | M2 | R1, R4 |
| 11 | PDF Page Rendering | In-memory `libpoppler-glib.so.8` + `libcairo.so.2` ctypes with `pdftoppm` fallback | M3 | R2 |
| 12 | PDF Page Navigation | Next/previous page navigation and direct page jumping | M3 | R2 |
| 13 | PDF Zoom & Fit Modes | Fit-to-width, fit-to-page, and custom scale calculations | M3 | R2 |
| 14 | PDF UI & Aspect Ratio | `PdfReaderView` using `Gtk.Picture` with vector-crisp scaling | M3 | R2 |
| 15 | PDF Reading Progress | Periodic 5-second checkpoint and position saving | M3 | R2, R4 |
| 16 | Session Activity Tracking | Active reading duration accumulation with idle filtering (120s text / 60s comics) | M4 | R3 |
| 17 | Words Read Estimation | EPUB tokenization, PDF text stream/250wpp, Comics 50wpp/PPM estimation | M4 | R3 |
| 18 | WPM Speed Metric | WPM calculation with duration minimums and outlier clamping | M4 | R3 |
| 19 | Statistics Dialog UI | `StatisticsDialog` with Library Overview and Book Insights tabs | M4 | R3, R4 |
| 20 | Theme Sync for Statistics | Ensure Statistics view respects Light, Dark, Sepia themes | M4 | R4 |
| 21 | Multi-Format Library Support | Import, display, and open `.pdf`, `.cbz`, `.cbr` in `LibraryView` | M5 | R4 |
| 22 | Polymorphic Reader Dispatch | `AquileReaderApp.open_book()` routes to appropriate reader view by format | M5 | R4 |
| 23 | E2E Test Suite | Comprehensive opaque-box test suite across Tiers 1-4 | M-TEST | Acceptance Criteria |
| 24 | Baseline Non-Regression | Ensure all 13 existing tests continue to pass with 0 regressions | M-FINAL | Acceptance Criteria |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M-TEST | E2E Testing Suite | Test infrastructure and comprehensive Tiers 1-4 test cases | none | DONE (TEST_READY.md published, 25 tests created) |
| M1 | Storage & Domain Models | Schema v2 migration, models, `StatisticsRepository`, fixture repair | none | DONE (Gate passed, 6/6 unanimous approvals) |
| M2 | Comic Reader Engine & View | `ComicArchiveEngine`, `ComicReaderView`, natural sort, spreads, LTR/RTL | M1 | PLANNED |
| M3 | PDF Reader Engine & View | `PdfDocumentEngine`, `PdfReaderView`, poppler ctypes/CLI, zoom/fit math | M1 | PLANNED |
| M4 | Reading Statistics & Dialog | `ReadingSessionTracker`, WPM math, `StatisticsDialog` UI & theming | M1 | PLANNED |
| M5 | Application Integration | `app.py` routing, `LibraryView` multi-format imports, stats button | M2, M3, M4 | PLANNED |
| M-FINAL | Final Verification & Hardening | Phase 1: 100% E2E test pass (Tiers 1-4); Phase 2: Tier 5 adversarial hardening | M5, M-TEST | PLANNED |

## Interface Contracts

### Domain Models (`src/aquile/domain/models.py`)
```python
@dataclass(frozen=True)
class ReadingSession:
    id: str
    book_id: str
    started_at: datetime
    ended_at: Optional[datetime]
    duration_seconds: float
    active_seconds: float
    idle_seconds: float
    words_read: int
    wpm: float

@dataclass(frozen=True)
class BookStatistics:
    book_id: str
    total_reading_seconds: float
    active_reading_seconds: float
    total_sessions: int
    estimated_words_read: int
    average_wpm: float
    last_session_at: Optional[datetime]

@dataclass(frozen=True)
class LibraryStatistics:
    total_books: int
    books_in_progress: int
    books_completed: int
    total_reading_seconds: float
    active_reading_seconds: float
    total_words_read: int
    average_wpm: float
    format_counts: dict[str, int]
```

### Storage Interface (`src/aquile/storage/repository.py:StatisticsRepository`)
```python
class StatisticsRepository:
    def __init__(self, db: Database): ...
    def record_session(self, session: ReadingSession) -> None: ...
    def get_book_statistics(self, book_id: str) -> BookStatistics: ...
    def get_library_statistics(self) -> LibraryStatistics: ...
    def get_sessions_for_book(self, book_id: str, limit: int = 50) -> list[ReadingSession]: ...
```

### Comic Engine Interface (`src/aquile/reader/comic_reader.py`)
```python
class ComicArchiveEngine:
    def __init__(self, file_path: str): ...
    def list_page_entries(self) -> list[str]: ...  # naturally sorted
    def get_page_count(self) -> int: ...
    def get_spreads(self, mode: str = "single", direction: str = "ltr") -> list[list[int]]: ...
    def get_page_image_bytes(self, page_index: int) -> bytes: ...
    def get_page_texture(self, page_index: int) -> Gdk.Texture: ...
```

### PDF Engine Interface (`src/aquile/reader/pdf_reader.py`)
```python
class PdfDocumentEngine:
    def __init__(self, file_path: str): ...
    def get_page_count(self) -> int: ...
    def get_page_dimensions(self, page_index: int) -> tuple[float, float]: ... # width, height in points
    def render_page_texture(self, page_index: int, scale: float = 1.0) -> Gdk.Texture: ...
    def calculate_fit_scale(self, page_index: int, viewport_width: float, viewport_height: float, mode: str) -> float: ... # mode: "width" | "page"
```

### Session Tracker Interface (`src/aquile/reader/session_tracker.py`)
```python
class ReadingSessionTracker:
    def __init__(self, book_id: str, format: str, idle_threshold_seconds: Optional[float] = None): ...
    def register_activity(self) -> None: ...
    def tick(self, now: Optional[float] = None) -> None: ...
    def record_page_turn(self, words_on_page: int) -> None: ...
    def end_session(self) -> ReadingSession: ...
```
