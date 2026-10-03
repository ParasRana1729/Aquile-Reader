"""
Reading Statistics Dialog for Aquile Reader.
Displays Library Overview and Book Insights metrics using Adw.ViewSwitcher (FR-15, R3, R4).
"""

from typing import Optional, List, Dict, Any
from datetime import datetime

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw

try:
    from ..domain.models import Book, AppSettings, LibraryStatistics, BookStatistics, ReadingSession
    from ..storage.repository import StatisticsRepository, BookRepository
except (ImportError, ValueError):
    from aquile.domain.models import Book, AppSettings, LibraryStatistics, BookStatistics, ReadingSession
    from aquile.storage.repository import StatisticsRepository, BookRepository


def format_duration(seconds: float) -> str:
    """Format seconds into human-readable duration string."""
    if seconds <= 0:
        return "0s"
    total_sec = int(round(seconds))
    hours = total_sec // 3600
    minutes = (total_sec % 3600) // 60
    secs = total_sec % 60

    parts = []
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0 or hours > 0:
        parts.append(f"{minutes}m")
    if secs > 0 or not parts:
        parts.append(f"{secs}s")
    return " ".join(parts)


class StatisticsDialog(Adw.Window):
    """
    Dedicated modal dialog displaying library-wide reading statistics
    and per-book reading insights.
    """

    def __init__(
        self,
        parent_window=None,
        stats_repo: Optional[StatisticsRepository] = None,
        book_repo: Optional[BookRepository] = None,
        settings: Optional[AppSettings] = None,
        initial_book_id: Optional[str] = None,
        theme: Optional[str] = None,
        **kwargs,
    ):
        super().__init__()

        # Flexible argument handling (supports StatisticsDialog(stats_repo, book_repo))
        if isinstance(parent_window, StatisticsRepository):
            stats_repo = parent_window
            parent_window = None

        self.stats_repo = stats_repo
        self.book_repo = book_repo
        if self.book_repo is None and self.stats_repo is not None and hasattr(self.stats_repo, "db"):
            self.book_repo = BookRepository(self.stats_repo.db)

        self.settings = settings
        self.initial_book_id = initial_book_id
        self._theme = "light"

        # Window settings
        if parent_window is not None:
            try:
                self.set_transient_for(parent_window)
            except Exception:
                pass
        self.set_modal(True)
        self.set_title("Reading Statistics")
        self.set_default_size(580, 640)
        self.add_css_class("statistics-dialog")

        # Theme resolution
        if theme:
            self.set_theme(theme)
        elif self.settings and hasattr(self.settings, "theme"):
            self.set_theme(self.settings.theme)
        else:
            self.set_theme("light")

        # State storage
        self.all_books: List[Book] = []
        self.library_stats: LibraryStatistics = LibraryStatistics()
        self.selected_book: Optional[Book] = None
        self.selected_book_stats: Optional[BookStatistics] = None
        self.selected_book_sessions: List[ReadingSession] = []

        # Format rows tracker
        self._format_rows: List[Adw.ActionRow] = []
        self._session_rows: List[Adw.ActionRow] = []

        # Build UI layout
        self._build_ui()

        # Load initial data
        self.refresh()

    def set_theme(self, theme: str) -> None:
        """Apply active application theme class (aquile-theme-light, -dark, -sepia)."""
        theme_norm = (theme or "light").lower().strip()
        if theme_norm not in ("light", "dark", "sepia"):
            theme_norm = "light"
        self._theme = theme_norm

        for c in ("aquile-theme-light", "aquile-theme-dark", "aquile-theme-sepia"):
            self.remove_css_class(c)
        self.add_css_class(f"aquile-theme-{self._theme}")

    def get_theme(self) -> str:
        """Return the current theme name."""
        return self._theme

    def _build_ui(self) -> None:
        """Construct the ViewSwitcher header and two main tab pages."""
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(content_box)

        # HeaderBar with ViewSwitcher
        self.header = Adw.HeaderBar()
        content_box.append(self.header)

        # Main ViewStack
        self.view_stack = Adw.ViewStack()
        self.view_stack.set_vexpand(True)
        content_box.append(self.view_stack)

        # ViewSwitcher connected to ViewStack
        self.view_switcher = Adw.ViewSwitcher()
        self.view_switcher.set_stack(self.view_stack)
        self.view_switcher.set_policy(Adw.ViewSwitcherPolicy.WIDE)
        self.header.set_title_widget(self.view_switcher)

        # Tab 1: Library Overview
        self.overview_page = self._build_overview_tab()
        self.view_stack.add_titled(self.overview_page, "overview", "Library Overview")

        # Tab 2: Book Insights
        self.insights_page = self._build_insights_tab()
        self.view_stack.add_titled(self.insights_page, "insights", "Book Insights")

    def _build_overview_tab(self) -> Adw.PreferencesPage:
        """Construct the Library Overview tab page."""
        page = Adw.PreferencesPage()

        # Reading Time and Speed Group
        group_time = Adw.PreferencesGroup(title="Reading Time and Speed")
        page.add(group_time)

        self.row_total_reading_time = Adw.ActionRow(title="Total Reading Time")
        group_time.add(self.row_total_reading_time)

        self.row_active_reading_time = Adw.ActionRow(title="Active Reading Time")
        group_time.add(self.row_active_reading_time)

        self.row_total_words = Adw.ActionRow(title="Total Words Read")
        group_time.add(self.row_total_words)

        self.row_average_wpm = Adw.ActionRow(title="Average Reading Speed")
        group_time.add(self.row_average_wpm)

        # Library Completion Group
        group_books = Adw.PreferencesGroup(title="Library Completion")
        page.add(group_books)

        self.row_total_books = Adw.ActionRow(title="Total Books")
        group_books.add(self.row_total_books)

        self.row_books_in_progress = Adw.ActionRow(title="Books in Progress")
        group_books.add(self.row_books_in_progress)

        self.row_books_completed = Adw.ActionRow(title="Books Completed")
        group_books.add(self.row_books_completed)

        # Format Distribution Group
        self.group_formats = Adw.PreferencesGroup(title="Format Distribution")
        page.add(self.group_formats)

        return page

    def _build_insights_tab(self) -> Adw.PreferencesPage:
        """Construct the Book Insights tab page."""
        page = Adw.PreferencesPage()

        # Book Selection Group
        group_select = Adw.PreferencesGroup(title="Select Book")
        page.add(group_select)

        self.book_combo_row = Adw.ComboRow(title="Book")
        self.book_combo_row.connect("notify::selected", self._on_book_selection_changed)
        group_select.add(self.book_combo_row)

        # Selected Book Metrics Group
        group_metrics = Adw.PreferencesGroup(title="Book Metrics")
        page.add(group_metrics)

        self.row_book_total_time = Adw.ActionRow(title="Total Reading Time")
        group_metrics.add(self.row_book_total_time)

        self.row_book_active_time = Adw.ActionRow(title="Active Reading Time")
        group_metrics.add(self.row_book_active_time)

        self.row_book_sessions = Adw.ActionRow(title="Total Sessions")
        group_metrics.add(self.row_book_sessions)

        self.row_book_words = Adw.ActionRow(title="Estimated Words Read")
        group_metrics.add(self.row_book_words)

        self.row_book_wpm = Adw.ActionRow(title="Average Reading Speed")
        group_metrics.add(self.row_book_wpm)

        # Recent Sessions Group
        self.group_recent_sessions = Adw.PreferencesGroup(title="Recent Sessions")
        page.add(self.group_recent_sessions)

        return page

    def refresh(self) -> None:
        """Reload all statistics and books from repositories and update UI bindings."""
        if self.book_repo is not None:
            self.all_books = self.book_repo.list_all()
        else:
            self.all_books = []

        if self.stats_repo is not None:
            self.library_stats = self.stats_repo.get_library_statistics()
        else:
            self.library_stats = LibraryStatistics()

        # 1. Update Library Overview Tab
        self.row_total_reading_time.set_subtitle(format_duration(self.library_stats.total_reading_seconds))
        self.row_active_reading_time.set_subtitle(format_duration(self.library_stats.active_reading_seconds))
        self.row_total_words.set_subtitle(f"{self.library_stats.total_words_read:,} words")
        self.row_average_wpm.set_subtitle(f"{self.library_stats.average_wpm:.1f} WPM")

        self.row_total_books.set_subtitle(str(self.library_stats.total_books))
        self.row_books_in_progress.set_subtitle(str(self.library_stats.books_in_progress))
        self.row_books_completed.set_subtitle(str(self.library_stats.books_completed))

        # Clear and update format distribution rows
        for row in self._format_rows:
            self.group_formats.remove(row)
        self._format_rows.clear()

        if self.library_stats.format_counts:
            for fmt, count in sorted(self.library_stats.format_counts.items()):
                pct = (count / self.library_stats.total_books * 100.0) if self.library_stats.total_books > 0 else 0.0
                fmt_name = fmt.upper()
                row = Adw.ActionRow(title=f"{fmt_name} Books", subtitle=f"{count} book(s) ({pct:.0f}%)")
                self.group_formats.add(row)
                self._format_rows.append(row)
        else:
            row = Adw.ActionRow(title="No Books in Library", subtitle="Import EPUB, PDF, or Comic books to see format distribution")
            self.group_formats.add(row)
            self._format_rows.append(row)

        # 2. Update Book Insights Combo
        if self.all_books:
            titles = [f"{b.title} ({b.author})" if b.author and b.author != "Unknown Author" else b.title for b in self.all_books]
            model = Gtk.StringList.new(titles)
            self.book_combo_row.set_model(model)
            self.book_combo_row.set_sensitive(True)

            selected_idx = 0
            if self.initial_book_id:
                for i, b in enumerate(self.all_books):
                    if b.id == self.initial_book_id:
                        selected_idx = i
                        self.view_stack.set_visible_child_name("insights")
                        break

            self.book_combo_row.set_selected(selected_idx)
            self._update_book_insights_for_index(selected_idx)
        else:
            model = Gtk.StringList.new(["No books available"])
            self.book_combo_row.set_model(model)
            self.book_combo_row.set_sensitive(False)
            self._clear_book_insights()

    def _on_book_selection_changed(self, combo: Adw.ComboRow, _pspec) -> None:
        """Handler for book dropdown selection changed."""
        idx = combo.get_selected()
        self._update_book_insights_for_index(idx)

    def _update_book_insights_for_index(self, idx: int) -> None:
        """Load book-specific statistics and recent sessions for selected index."""
        if 0 <= idx < len(self.all_books):
            self.selected_book = self.all_books[idx]
            book_id = self.selected_book.id

            if self.stats_repo is not None:
                self.selected_book_stats = self.stats_repo.get_book_statistics(book_id)
                self.selected_book_sessions = self.stats_repo.get_sessions_for_book(book_id, limit=20)
            else:
                self.selected_book_stats = BookStatistics(book_id=book_id)
                self.selected_book_sessions = []

            # Update book metric rows
            self.row_book_total_time.set_subtitle(format_duration(self.selected_book_stats.total_reading_seconds))
            self.row_book_active_time.set_subtitle(format_duration(self.selected_book_stats.active_reading_seconds))
            self.row_book_sessions.set_subtitle(str(self.selected_book_stats.total_sessions))
            self.row_book_words.set_subtitle(f"{self.selected_book_stats.estimated_words_read:,} words")
            self.row_book_wpm.set_subtitle(f"{self.selected_book_stats.average_wpm:.1f} WPM")

            # Update recent sessions rows
            for row in self._session_rows:
                self.group_recent_sessions.remove(row)
            self._session_rows.clear()

            if self.selected_book_sessions:
                for sess in self.selected_book_sessions:
                    date_str = (
                        sess.started_at.strftime("%Y-%m-%d %H:%M")
                        if isinstance(sess.started_at, datetime)
                        else str(sess.started_at)[:16]
                    )
                    row = Adw.ActionRow(
                        title=f"Session at {date_str}",
                        subtitle=(
                            f"Duration: {format_duration(sess.duration_seconds)} "
                            f"(Active: {format_duration(sess.active_seconds)}) • "
                            f"{sess.words_read:,} words • {sess.wpm:.1f} WPM"
                        ),
                    )
                    self.group_recent_sessions.add(row)
                    self._session_rows.append(row)
            else:
                row = Adw.ActionRow(
                    title="No Sessions Recorded",
                    subtitle="Start reading this book to record reading sessions",
                )
                self.group_recent_sessions.add(row)
                self._session_rows.append(row)
        else:
            self._clear_book_insights()

    def _clear_book_insights(self) -> None:
        """Reset book insight rows when no book is selected."""
        self.selected_book = None
        self.selected_book_stats = None
        self.selected_book_sessions = []

        self.row_book_total_time.set_subtitle("0s")
        self.row_book_active_time.set_subtitle("0s")
        self.row_book_sessions.set_subtitle("0")
        self.row_book_words.set_subtitle("0 words")
        self.row_book_wpm.set_subtitle("0.0 WPM")

        for row in self._session_rows:
            self.group_recent_sessions.remove(row)
        self._session_rows.clear()

        row = Adw.ActionRow(
            title="No Book Selected",
            subtitle="Add and select a book to view insights",
        )
        self.group_recent_sessions.add(row)
        self._session_rows.append(row)

    def select_book(self, book_id: str) -> bool:
        """Programmatically select a book by its ID."""
        for idx, book in enumerate(self.all_books):
            if book.id == book_id:
                self.book_combo_row.set_selected(idx)
                self._update_book_insights_for_index(idx)
                return True
        return False

    def get_library_metrics(self) -> Dict[str, Any]:
        """Return the current bound library metrics dictionary."""
        return {
            "total_books": self.library_stats.total_books,
            "books_in_progress": self.library_stats.books_in_progress,
            "books_completed": self.library_stats.books_completed,
            "total_reading_seconds": self.library_stats.total_reading_seconds,
            "active_reading_seconds": self.library_stats.active_reading_seconds,
            "total_words_read": self.library_stats.total_words_read,
            "average_wpm": self.library_stats.average_wpm,
            "format_counts": dict(self.library_stats.format_counts),
        }

    def get_selected_book_metrics(self) -> Dict[str, Any]:
        """Return the current bound book metrics dictionary."""
        if not self.selected_book_stats:
            return {
                "book_id": None,
                "total_reading_seconds": 0.0,
                "active_reading_seconds": 0.0,
                "total_sessions": 0,
                "estimated_words_read": 0,
                "average_wpm": 0.0,
            }
        return {
            "book_id": self.selected_book_stats.book_id,
            "total_reading_seconds": self.selected_book_stats.total_reading_seconds,
            "active_reading_seconds": self.selected_book_stats.active_reading_seconds,
            "total_sessions": self.selected_book_stats.total_sessions,
            "estimated_words_read": self.selected_book_stats.estimated_words_read,
            "average_wpm": self.selected_book_stats.average_wpm,
        }

    def get_recent_sessions(self) -> List[ReadingSession]:
        """Return the list of recent sessions bound to the view."""
        return list(self.selected_book_sessions)
