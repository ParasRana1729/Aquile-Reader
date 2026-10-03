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

from .domain.models import Book, AppSettings
from .storage.database import Database
from .storage.repository import (
    BookRepository, ReadingProgressRepository, AnnotationRepository, SettingsRepository
)
from .ui.library_view import LibraryView
from .ui.reader_view import ReaderView

class AquileReaderApp(Adw.Application):
    def __init__(self, db_path=None):
        super().__init__(
            application_id="org.antigravity.AquileReader",
            flags=Gio.ApplicationFlags.HANDLES_OPEN
        )
        self.db = Database(db_path)
        self.book_repo = BookRepository(self.db)
        self.progress_repo = ReadingProgressRepository(self.db)
        self.ann_repo = AnnotationRepository(self.db)
        self.settings_repo = SettingsRepository(self.db)

        self.window: Adw.ApplicationWindow = None
        self.nav_stack: Gtk.Stack = None
        self.library_view: LibraryView = None
        self.current_reader_view: ReaderView = None

    def do_startup(self):
        Adw.Application.do_startup(self)
        self._load_styles()

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
            on_open_book=self.open_book
        )
        self.nav_stack.add_named(self.library_view, "library")
        self.nav_stack.set_visible_child_name("library")

    def open_book(self, book: Book):
        if self.current_reader_view:
            self.current_reader_view.cleanup()
            self.nav_stack.remove(self.current_reader_view)
            self.current_reader_view = None

        self.current_reader_view = ReaderView(
            book, self.book_repo, self.progress_repo, self.ann_repo, self.settings_repo,
            on_back_to_library=self.show_library
        )
        self.nav_stack.add_named(self.current_reader_view, "reader")
        self.nav_stack.set_visible_child_name("reader")

    def show_library(self):
        if self.current_reader_view:
            self.current_reader_view.cleanup()
            self.nav_stack.remove(self.current_reader_view)
            self.current_reader_view = None

        self.library_view.refresh_library()
        self.nav_stack.set_visible_child_name("library")

    def _on_window_close(self, window) -> bool:
        if self.current_reader_view:
            self.current_reader_view.cleanup()
        return False  # Allow window destruction

def main():
    app = AquileReaderApp()
    return app.run(sys.argv)

if __name__ == "__main__":
    sys.exit(main())
