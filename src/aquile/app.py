"""
Aquile Reader Application for Ubuntu.
Coordinates application lifecycle, themes, database, and navigation (UB-01, UB-02, NFR-01).
"""

import os
import sys
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, Gio, Gdk

from typing import Optional, Union
import uuid
from .domain.models import Book, AppSettings
from .storage.database import Database
from .storage.repository import (
    BookRepository, ReadingProgressRepository, AnnotationRepository, SettingsRepository,
    StatisticsRepository
)
from .reader.session_tracker import ReadingSessionTracker
from .ui.library_view import LibraryView
from .ui.reader_view import ReaderView
from .ui.comic_view import ComicReaderView
from .ui.pdf_view import PdfReaderView
from .ui.statistics_dialog import StatisticsDialog

class AquileReaderApp(Adw.Application):
    def __init__(self, db_path=None, app_id=None):
        chosen_id = app_id or f"org.antigravity.AquileReader_{uuid.uuid4().hex[:8]}"
        super().__init__(
            application_id=chosen_id,
            flags=Gio.ApplicationFlags.HANDLES_OPEN | Gio.ApplicationFlags.NON_UNIQUE
        )
        self.db = Database(db_path)
        self.book_repo = BookRepository(self.db)
        self.progress_repo = ReadingProgressRepository(self.db)
        self.ann_repo = AnnotationRepository(self.db)
        self.settings_repo = SettingsRepository(self.db)
        self.stats_repo = StatisticsRepository(self.db)
        self.active_session_tracker: Optional[ReadingSessionTracker] = None

        self.window: Adw.ApplicationWindow = None
        self.nav_stack: Gtk.Stack = None
        self.library_view: LibraryView = None
        self.current_reader_view: Optional[Union[ReaderView, ComicReaderView, PdfReaderView]] = None

    def do_startup(self):
        Adw.Application.do_startup(self)
        self._load_styles()
        about_action = Gio.SimpleAction.new("about", None)
        about_action.connect("activate", self._on_about)
        self.add_action(about_action)

    def _on_about(self, *args):
        about = Adw.AboutWindow(transient_for=self.window, application_name="Aquile Reader",
                                application_icon="book-open-symbolic", version="0.2.0-preview",
                                comments="Native Ubuntu eBook reader (EPUB, PDF, CBZ/CBR) — offline-first clean-room port.",
                                website="https://www.aquilereader.in/", license_type=Gtk.License.MIT)
        about.present()

    def _load_styles(self):
        css_provider = Gtk.CssProvider()
        css_path = os.path.join(os.path.dirname(__file__), "ui", "style.css")
        if os.path.exists(css_path):
            css_provider.load_from_path(css_path)
            display = Gdk.Display.get_default()
            if display:
                Gtk.StyleContext.add_provider_for_display(
                    display, css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
                )

    def do_activate(self):
        Adw.Application.do_activate(self)
        if not self.window:
            self._create_main_window()
        self.window.present()

    def do_open(self, files, hint):
        self.do_activate()
        for f in files:
            path = f.get_path()
            if path and os.path.exists(path):
                self.library_view.import_file(path)
                break

    def _create_main_window(self):
        self.window = Adw.ApplicationWindow(application=self)
        self.window.set_title("Aquile Reader")
        self.window.set_default_size(1180, 780)

        # Connect orderly close persistence
        self.window.connect("close-request", self._on_window_close)

        self.nav_stack = Gtk.Stack()
        self.nav_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.window.set_content(self.nav_stack)

        self.library_view = LibraryView(
            self.book_repo, self.progress_repo, self.ann_repo,
            on_open_book=self.open_book,
            stats_repo=self.stats_repo,
            settings_repo=self.settings_repo,
            on_show_statistics=self.show_statistics
        )
        self.nav_stack.add_named(self.library_view, "library")
        self.nav_stack.set_visible_child_name("library")

    def show_statistics(self, book_id: Optional[str] = None):
        settings = self.settings_repo.load() if self.settings_repo else None
        dialog = StatisticsDialog(
            parent_window=self.window,
            stats_repo=self.stats_repo,
            book_repo=self.book_repo,
            settings=settings,
            initial_book_id=book_id
        )
        dialog.present()

    def _flush_active_session(self):
        if self.active_session_tracker:
            try:
                session = self.active_session_tracker.end_session()
                if session.duration_seconds > 0 or session.words_read > 0 or session.active_seconds > 0:
                    self.stats_repo.record_session(session)
            except Exception:
                pass
            self.active_session_tracker = None

    def open_book(self, book: Book):
        self._flush_active_session()
        try:
            self.book_repo.update_last_read(book.id)
        except Exception:
            pass
        if self.current_reader_view:
            self.current_reader_view.cleanup()
            self.nav_stack.remove(self.current_reader_view)
            self.current_reader_view = None

        fmt = (book.file_format or "").lower().strip()
        if fmt in ("cbz", "cbr", "comic"):
            self.current_reader_view = ComicReaderView(
                book,
                self.book_repo,
                self.progress_repo,
                ann_repo=self.ann_repo,
                settings_repo=self.settings_repo,
                on_back_to_library=self.show_library
            )
        elif fmt == "pdf":
            self.current_reader_view = PdfReaderView(
                book,
                self.book_repo,
                self.progress_repo,
                ann_repo=self.ann_repo,
                settings_repo=self.settings_repo,
                on_back_to_library=self.show_library
            )
        else:
            self.current_reader_view = ReaderView(
                book,
                self.book_repo,
                self.progress_repo,
                self.ann_repo,
                self.settings_repo,
                on_back_to_library=self.show_library
            )

        self._start_reading_session(book)

        self.nav_stack.add_named(self.current_reader_view, "reader")
        self.nav_stack.set_visible_child_name("reader")

    def _start_reading_session(self, book: Book):
        fmt = (book.file_format or "epub").lower().strip()
        tracker = ReadingSessionTracker(book.id, format=fmt)
        tracker.register_activity()
        self.active_session_tracker = tracker

        reader = self.current_reader_view
        if not reader:
            return

        orig_next = getattr(reader, "next_page", None)
        if callable(orig_next):
            def wrapped_next(*args, **kwargs):
                res = orig_next(*args, **kwargs)
                if self.active_session_tracker:
                    words = ReadingSessionTracker.estimate_words_for_page(fmt)
                    self.active_session_tracker.record_page_turn(words)
                return res
            reader.next_page = wrapped_next

        orig_prev = getattr(reader, "prev_page", None)
        if callable(orig_prev):
            def wrapped_prev(*args, **kwargs):
                res = orig_prev(*args, **kwargs)
                if self.active_session_tracker:
                    words = ReadingSessionTracker.estimate_words_for_page(fmt)
                    self.active_session_tracker.record_page_turn(words)
                return res
            reader.prev_page = wrapped_prev

        orig_autosave = getattr(reader, "_on_periodic_autosave", None)
        if callable(orig_autosave):
            def wrapped_autosave(*args, **kwargs):
                if self.active_session_tracker:
                    self.active_session_tracker.tick()
                return orig_autosave(*args, **kwargs)
            reader._on_periodic_autosave = wrapped_autosave

    def show_library(self):
        self._flush_active_session()
        if self.current_reader_view:
            self.current_reader_view.cleanup()
            self.nav_stack.remove(self.current_reader_view)
            self.current_reader_view = None

        self.library_view.refresh_library()
        self.nav_stack.set_visible_child_name("library")

    def _on_window_close(self, window) -> bool:
        self._flush_active_session()
        if self.current_reader_view:
            self.current_reader_view.cleanup()
        return False  # Allow window destruction

def main():
    app = AquileReaderApp()
    return app.run(sys.argv)

if __name__ == "__main__":
    sys.exit(main())
