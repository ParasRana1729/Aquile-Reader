"""
Library View for Aquile Reader on Ubuntu.
Manages local eBook collection, book importing, metadata display, and collections view (FR-01, FR-02, FR-11).
"""

import os
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, Gio, GLib
from typing import Callable, List, Optional
import time

from ..domain.models import Book, ReadingProgress, Annotation
from ..storage.repository import (
    BookRepository, ReadingProgressRepository, AnnotationRepository
)
from ..reader.epub_parser import EpubParser

class LibraryView(Gtk.Box):
    def __init__(self, book_repo: BookRepository, progress_repo: ReadingProgressRepository,
                 ann_repo: AnnotationRepository, on_open_book: Callable[[Book], None]):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.book_repo = book_repo
        self.progress_repo = progress_repo
        self.ann_repo = ann_repo
        self.on_open_book = on_open_book

        self.books: List[Book] = []
        self._build_ui()
        self.refresh_library()

    def _build_ui(self):
        # 1. HeaderBar
        self.header = Adw.HeaderBar()
        self.append(self.header)

        # Import Book Button (+)
        btn_import = Gtk.Button(icon_name="list-add-symbolic")
        btn_import.set_tooltip_text("Import eBook (EPUB, PDF, CBZ)")
        btn_import.connect("clicked", self._on_import_clicked)
        self.header.pack_start(btn_import)

        # Collections (Cross-Book Annotations) Button (FR-11)
        btn_collections = Gtk.Button(icon_name="emblem-favorite-symbolic")
        btn_collections.set_tooltip_text("Collections: All Highlights & Notes (FR-11)")
        btn_collections.connect("clicked", self._on_collections_clicked)
        self.header.pack_start(btn_collections)

        # Title
        self.title_widget = Adw.WindowTitle(title="Aquile Reader", subtitle="My Local Library")
        self.header.set_title_widget(self.title_widget)

        # Search Entry (FR-01)
        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_placeholder_text("Search books...")
        self.search_entry.set_hexpand(False)
        self.search_entry.connect("search-changed", self._on_search_changed)
        self.header.pack_end(self.search_entry)

        # 2. Scrolled Area for Books
        self.scrolled = Gtk.ScrolledWindow()
        self.scrolled.set_vexpand(True)
        self.append(self.scrolled)

        self.content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.content_box.set_margin_start(24)
        self.content_box.set_margin_end(24)
        self.content_box.set_margin_top(16)
        self.content_box.set_margin_bottom(16)
        self.scrolled.set_child(self.content_box)

        # Book ListBox
        self.list_box = Gtk.ListBox()
        self.list_box.set_selection_mode(Gtk.SelectionMode.NONE)
        self.list_box.add_css_class("boxed-list")
        self.content_box.append(self.list_box)

        # Empty State
        self.empty_status = Adw.StatusPage()
        self.empty_status.set_title("No Books in Library")
        self.empty_status.set_description("Import DRM-free EPUB, PDF, or Comic books to start reading offline.")
        self.empty_status.set_icon_name("book-open-symbolic")
        btn_empty_import = Gtk.Button(label="Import Book")
        btn_empty_import.add_css_class("suggested-action")
        btn_empty_import.add_css_class("pill")
        btn_empty_import.connect("clicked", self._on_import_clicked)
        self.empty_status.set_child(btn_empty_import)
        self.content_box.append(self.empty_status)

    def refresh_library(self, search_query: str = ""):
        self.books = self.book_repo.list_all()

        # Clear existing rows
        while child := self.list_box.get_first_child():
            self.list_box.remove(child)

        query = search_query.strip().lower()
        displayed_count = 0

        for book in self.books:
            if query and (query not in book.title.lower() and query not in book.author.lower()):
                continue

            row = self._create_book_row(book)
            self.list_box.append(row)
            displayed_count += 1

        if displayed_count == 0 and not query:
            self.empty_status.set_visible(True)
            self.list_box.set_visible(False)
        else:
            self.empty_status.set_visible(False)
            self.list_box.set_visible(True)

    def _create_book_row(self, book: Book) -> Gtk.ListBoxRow:
        row = Gtk.ListBoxRow()
        row_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        row_box.set_margin_start(16)
        row_box.set_margin_end(16)
        row_box.set_margin_top(12)
        row_box.set_margin_bottom(12)
        row.set_child(row_box)

        # Book Icon / Format Badge
        icon = Gtk.Image.new_from_icon_name("book-open-symbolic")
        icon.set_pixel_size(32)
        row_box.append(icon)

        # Book Info
        info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        info_box.set_hexpand(True)
        row_box.append(info_box)

        lbl_title = Gtk.Label(label=book.title)
        lbl_title.set_xalign(0)
        lbl_title.add_css_class("book-title")
        info_box.append(lbl_title)

        progress = self.progress_repo.get(book.id)
        prog_str = f"Progress: {progress.percentage:.0f}%" if progress else "Unread"
        lbl_sub = Gtk.Label(label=f"{book.author} • {book.file_format.upper()} • {prog_str}")
        lbl_sub.set_xalign(0)
        lbl_sub.add_css_class("book-author")
        info_box.append(lbl_sub)

        # Open Button
        btn_open = Gtk.Button(label="Read")
        btn_open.add_css_class("suggested-action")
        btn_open.connect("clicked", lambda b, bk=book: self.on_open_book(bk))
        row_box.append(btn_open)

        # Delete Button
        btn_del = Gtk.Button(icon_name="user-trash-symbolic")
        btn_del.set_tooltip_text("Remove from Library")
        btn_del.connect("clicked", lambda b, bid=book.id: self._on_delete_book(bid))
        row_box.append(btn_del)

        return row

    def _on_search_changed(self, entry):
        self.refresh_library(entry.get_text())

    def _on_import_clicked(self, button):
        # File dialog using Gtk.FileDialog in GTK4
        file_dialog = Gtk.FileDialog()
        file_dialog.set_title("Select eBook to Import")

        # Filters for EPUB, PDF, CBZ
        filter_all = Gtk.FileFilter()
        filter_all.set_name("All Supported eBooks (*.epub, *.pdf, *.cbz)")
        filter_all.add_pattern("*.epub")
        filter_all.add_pattern("*.pdf")
        filter_all.add_pattern("*.cbz")

        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(filter_all)
        file_dialog.set_filters(filters)

        def _on_file_selected(dialog, result):
            try:
                gfile = dialog.open_finish(result)
                if gfile:
                    self.import_file(gfile.get_path())
            except Exception as e:
                pass  # User cancelled or error

        file_dialog.open(self.get_root(), None, _on_file_selected)

    def import_file(self, file_path: str):
        if not file_path or not os.path.exists(file_path):
            return

        # Check if already imported
        existing = self.book_repo.get_by_path(file_path)
        if existing:
            self.on_open_book(existing)
            return

        ext = os.path.splitext(file_path)[1].lower().lstrip(".")
        title = os.path.splitext(os.path.basename(file_path))[0]
        author = "Unknown Author"
        total_chaps = 1

        if ext == "epub":
            try:
                parser = EpubParser(file_path)
                title = parser.title or title
                author = parser.author or author
                total_chaps = max(1, len(parser.chapters))
            except Exception:
                pass

        book = Book(
            title=title,
            author=author,
            file_path=file_path,
            file_format=ext,
            total_chapters=total_chaps,
            file_size_bytes=os.path.getsize(file_path),
            added_at=time.time()
        )
        self.book_repo.add(book)
        self.refresh_library()
        self.on_open_book(book)

    def _on_delete_book(self, book_id: str):
        self.book_repo.delete(book_id)
        self.refresh_library()

    def _on_collections_clicked(self, button):
        # Open Collections Window (FR-11)
        dialog = Adw.Window()
        dialog.set_transient_for(self.get_root())
        dialog.set_modal(True)
        dialog.set_title("Collections: Notes & Bookmarks")
        dialog.set_default_size(520, 500)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        dialog.set_content(box)

        header = Adw.HeaderBar()
        box.append(header)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        box.append(scrolled)

        all_anns = self.ann_repo.list_all()
        if not all_anns:
            status = Adw.StatusPage()
            status.set_title("No Annotations Yet")
            status.set_description("Highlights and notes created while reading will appear here across all your books.")
            status.set_icon_name("emblem-favorite-symbolic")
            scrolled.set_child(status)
        else:
            list_box = Gtk.ListBox()
            list_box.add_css_class("boxed-list")
            list_box.set_margin_start(16)
            list_box.set_margin_end(16)
            list_box.set_margin_top(16)
            list_box.set_margin_bottom(16)
            scrolled.set_child(list_box)

            for ann in all_anns:
                row = Adw.ActionRow()
                book = self.book_repo.get_by_id(ann.book_id)
                book_title = book.title if book else "Unknown Book"
                row.set_title(f'"{ann.text_content}"')
                subtitle = f"Book: {book_title}"
                if ann.note_text:
                    subtitle += f" • Note: {ann.note_text}"
                row.set_subtitle(subtitle)
                list_box.append(row)

        dialog.present()
