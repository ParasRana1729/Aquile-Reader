"""
Book details pane for Aquile Reader library view.

Clean-room re-implementation of the right details pane observed in
docs/reference/B0/UI_RESEARCH.md section 3 (Library):

  cover thumbnail, title, "by <author>", "Percentage read : N %",
  "Date added :", "Last read :", "Word count :", "Line count :",
  "Description :", "Language :", "Publisher :", "Genre :",
  "File path :"; buttons "Open Book", "Edit Book Info", "Close".

Only title/author are editable inline (saved via BookRepository);
all other metadata is display-only with human-readable dates.
"""

import os
from datetime import datetime
from typing import Any, Callable, Dict, Optional

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

try:
    from ..domain.models import Book
except (ImportError, ValueError):  # pragma: no cover - import fallback
    from aquile.domain.models import Book


def format_human_date(timestamp: Any) -> str:
    """Format an epoch timestamp for display; "Never" when unset."""
    if timestamp is None:
        return "Never"
    try:
        ts = float(timestamp)
    except (TypeError, ValueError):
        return "Never"
    if ts <= 0:
        return "Never"
    try:
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
    except (OSError, OverflowError, ValueError):
        return "Never"


def percentage_from(progress: Any) -> float:
    """Extract a percentage float from a dict, ReadingProgress, or number."""
    if progress is None:
        return 0.0
    if isinstance(progress, dict):
        try:
            return float(progress.get("percentage", 0.0) or 0.0)
        except (TypeError, ValueError):
            return 0.0
    if isinstance(progress, (int, float)):
        try:
            return float(progress)
        except (TypeError, ValueError):
            return 0.0
    if hasattr(progress, "percentage"):
        try:
            return float(getattr(progress, "percentage") or 0.0)
        except (TypeError, ValueError):
            return 0.0
    return 0.0


def _display_value(value: Any, empty: str = "—") -> str:
    if value is None:
        return empty
    if isinstance(value, str):
        text = value.strip()
        return text if text else empty
    return str(value)


class BookDetailsPane(Gtk.Box):
    """Vertical details pane for the selected library book."""

    def __init__(self, book_repo=None, book=None, progress_dict=None,
                 on_open: Optional[Callable] = None,
                 on_edit_info: Optional[Callable] = None,
                 on_close: Optional[Callable] = None):
        # Allow BookDetailsPane(book) positional convenience: if the first
        # positional looks like a Book (has title/file_path, no `add`),
        # treat it as the bound book rather than a repository.
        if book_repo is not None and book is None:
            if hasattr(book_repo, "title") and not hasattr(book_repo, "add"):
                book = book_repo
                book_repo = None
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.book_repo = book_repo
        self.book: Optional[Book] = None
        self.progress_dict: Any = None
        self.on_open: Optional[Callable] = None
        self.on_edit_info: Optional[Callable] = None
        self.on_close: Optional[Callable] = None
        self._build_ui()
        if book is not None or on_open is not None or on_edit_info is not None or on_close is not None:
            self.bind(book, progress_dict, on_open, on_edit_info, on_close)

    def _build_ui(self):
        self.set_margin_start(16)
        self.set_margin_end(16)
        self.set_margin_top(12)
        self.set_margin_bottom(12)

        self.cover_image = Gtk.Image.new_from_icon_name("x-office-document-symbolic")
        self.cover_image.set_pixel_size(96)
        self.append(self.cover_image)

        self.title_label = Gtk.Label()
        self.title_label.set_xalign(0)
        self.title_label.set_wrap(True)
        self.title_label.add_css_class("title-1")
        self.append(self.title_label)

        self.author_label = Gtk.Label()
        self.author_label.set_xalign(0)
        self.append(self.author_label)

        self.percentage_label = Gtk.Label()
        self.percentage_label.set_xalign(0)
        self.append(self.percentage_label)

        self.date_added_label = Gtk.Label()
        self.date_added_label.set_xalign(0)
        self.append(self.date_added_label)

        self.last_read_label = Gtk.Label()
        self.last_read_label.set_xalign(0)
        self.append(self.last_read_label)

        self.word_count_label = Gtk.Label()
        self.word_count_label.set_xalign(0)
        self.append(self.word_count_label)

        self.line_count_label = Gtk.Label()
        self.line_count_label.set_xalign(0)
        self.append(self.line_count_label)

        self.description_label = Gtk.Label()
        self.description_label.set_xalign(0)
        self.description_label.set_wrap(True)
        self.append(self.description_label)

        self.language_label = Gtk.Label()
        self.language_label.set_xalign(0)
        self.append(self.language_label)

        self.publisher_label = Gtk.Label()
        self.publisher_label.set_xalign(0)
        self.append(self.publisher_label)

        self.genre_label = Gtk.Label()
        self.genre_label.set_xalign(0)
        self.append(self.genre_label)

        self.file_path_label = Gtk.Label()
        self.file_path_label.set_xalign(0)
        self.file_path_label.set_wrap(True)
        self.file_path_label.set_selectable(True)
        self.append(self.file_path_label)

        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.append(button_box)

        self.btn_open = Gtk.Button(label="Open Book")
        self.btn_open.add_css_class("suggested-action")
        self.btn_open.connect("clicked", self._on_open_clicked)
        button_box.append(self.btn_open)

        self.btn_edit = Gtk.Button(label="Edit Book Info")
        self.btn_edit.connect("clicked", self._on_edit_clicked)
        button_box.append(self.btn_edit)

        self.btn_close = Gtk.Button(label="Close")
        self.btn_close.connect("clicked", self._on_close_clicked)
        button_box.append(self.btn_close)

    def bind(self, book, progress_dict=None, on_open=None,
             on_edit_info=None, on_close=None, book_repo=None):
        """Bind the pane to a book and its callbacks.

        Positional order matches the task spec:
        bind(book, progress_dict, on_open, on_edit_info, on_close).
        """
        if book_repo is not None:
            self.book_repo = book_repo
        self.book = book
        self.progress_dict = progress_dict
        if on_open is not None:
            self.on_open = on_open
        if on_edit_info is not None:
            self.on_edit_info = on_edit_info
        if on_close is not None:
            self.on_close = on_close
        self._update_labels()
        return self

    def _update_labels(self):
        book = self.book
        if book is None:
            self.title_label.set_text("No book selected")
            self.author_label.set_text("")
            self.percentage_label.set_text("Percentage read : —")
            self.date_added_label.set_text("Date added : —")
            self.last_read_label.set_text("Last read : Never")
            self.word_count_label.set_text("Word count : —")
            self.line_count_label.set_text("Line count : —")
            self.description_label.set_text("Description : —")
            self.language_label.set_text("Language : —")
            self.publisher_label.set_text("Publisher : —")
            self.genre_label.set_text("Genre : —")
            self.file_path_label.set_text("File path : —")
            return

        title = getattr(book, "title", "") or "Untitled"
        author = getattr(book, "author", "") or "Unknown Author"
        self.title_label.set_text(title)
        self.author_label.set_text(f"by {author}")

        pct = percentage_from(self.progress_dict)
        self.percentage_label.set_text(f"Percentage read : {pct:.0f} %")

        self.date_added_label.set_text(
            f"Date added : {format_human_date(getattr(book, 'added_at', None))}"
        )
        self.last_read_label.set_text(
            f"Last read : {format_human_date(getattr(book, 'last_read_at', None))}"
        )

        word_count = getattr(book, "word_count", None)
        if word_count is None:
            word_count = getattr(book, "wordcount", None)
        self.word_count_label.set_text(
            f"Word count : {_display_value(word_count)}"
        )

        line_count = getattr(book, "line_count", None)
        if line_count is None:
            line_count = getattr(book, "linecount", None)
        self.line_count_label.set_text(
            f"Line count : {_display_value(line_count)}"
        )

        description = getattr(book, "description", None)
        if description is None:
            description = getattr(book, "summary", None)
        self.description_label.set_text(
            f"Description : {_display_value(description)}"
        )

        language = getattr(book, "language", None)
        if language is None:
            language = getattr(book, "lang", None)
        self.language_label.set_text(f"Language : {_display_value(language)}")

        publisher = getattr(book, "publisher", None)
        self.publisher_label.set_text(f"Publisher : {_display_value(publisher)}")

        genre = getattr(book, "genre", None)
        if genre is None:
            genre = getattr(book, "category", None)
        self.genre_label.set_text(f"Genre : {_display_value(genre)}")

        self.file_path_label.set_text(
            f"File path : {_display_value(getattr(book, 'file_path', None), '')}"
        )

        cover_path = getattr(book, "cover_path", None)
        if cover_path and isinstance(cover_path, str) and os.path.exists(cover_path):
            try:
                self.cover_image.set_from_file(cover_path)
            except Exception:
                pass
        else:
            try:
                self.cover_image.set_from_icon_name("x-office-document-symbolic")
            except Exception:
                pass

    def get_displayed_fields(self) -> Dict[str, str]:
        """Return current label texts keyed by field (for tests/callers)."""
        return {
            "title": self.title_label.get_text(),
            "author": self.author_label.get_text(),
            "percentage": self.percentage_label.get_text(),
            "date_added": self.date_added_label.get_text(),
            "last_read": self.last_read_label.get_text(),
            "word_count": self.word_count_label.get_text(),
            "line_count": self.line_count_label.get_text(),
            "description": self.description_label.get_text(),
            "language": self.language_label.get_text(),
            "publisher": self.publisher_label.get_text(),
            "genre": self.genre_label.get_text(),
            "file_path": self.file_path_label.get_text(),
        }

    def save_edited_info(self, new_title: str, new_author: str):
        """Update title/author on the bound book and persist via book_repo."""
        if self.book is None:
            return None
        title = new_title.strip() if isinstance(new_title, str) else ""
        author = new_author.strip() if isinstance(new_author, str) else ""
        if title:
            self.book.title = title
        if author:
            self.book.author = author
        if self.book_repo is not None:
            try:
                self.book_repo.add(self.book)
            except Exception:
                pass
        self._update_labels()
        if self.on_edit_info is not None:
            try:
                self.on_edit_info(self.book)
            except Exception:
                pass
        return self.book

    def _on_open_clicked(self, _button):
        if self.on_open is not None and self.book is not None:
            try:
                self.on_open(self.book)
            except Exception:
                pass

    def _on_edit_clicked(self, _button):
        self.open_edit_dialog()

    def _on_close_clicked(self, _button):
        if self.on_close is not None:
            try:
                self.on_close()
            except Exception:
                pass

    def open_edit_dialog(self):
        """Open an inline title/author edit dialog; saves via book_repo."""
        if self.book is None:
            return None
        parent = None
        try:
            parent = self.get_root()
        except Exception:
            parent = None
        dialog = Gtk.Dialog(title="Edit Book Info", transient_for=parent, modal=True)
        dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("Save", Gtk.ResponseType.OK)
        dialog.set_default_response(Gtk.ResponseType.OK)

        content = dialog.get_content_area()
        content.set_spacing(8)
        content.set_margin_start(16)
        content.set_margin_end(16)
        content.set_margin_top(12)
        content.set_margin_bottom(12)

        title_entry = Gtk.Entry()
        title_entry.set_placeholder_text("Title")
        title_entry.set_text(self.book.title or "")
        content.append(Gtk.Label(label="Title:"))
        content.append(title_entry)

        author_entry = Gtk.Entry()
        author_entry.set_placeholder_text("Author")
        author_entry.set_text(self.book.author or "")
        content.append(Gtk.Label(label="Author:"))
        content.append(author_entry)

        # Keep references for tests.
        self._edit_dialog = dialog
        self._edit_title_entry = title_entry
        self._edit_author_entry = author_entry

        def _on_response(dlg, response_id):
            if response_id == Gtk.ResponseType.OK:
                self.save_edited_info(title_entry.get_text(), author_entry.get_text())
            try:
                dlg.close()
            except Exception:
                try:
                    dlg.destroy()
                except Exception:
                    pass

        dialog.connect("response", _on_response)
        try:
            dialog.present()
        except Exception:
            pass
        return dialog
