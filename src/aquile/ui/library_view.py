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
    BookRepository, ReadingProgressRepository, AnnotationRepository,
    StatisticsRepository, SettingsRepository
)
from ..reader.epub_parser import EpubParser
from .statistics_dialog import StatisticsDialog

class LibraryView(Gtk.Box):
    def __init__(self, book_repo: BookRepository, progress_repo: ReadingProgressRepository,
                 ann_repo: AnnotationRepository, on_open_book: Callable[[Book], None],
                 stats_repo: Optional[StatisticsRepository] = None,
                 settings_repo: Optional[SettingsRepository] = None,
                 on_show_statistics: Optional[Callable[[Optional[str]], None]] = None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.book_repo = book_repo
        self.progress_repo = progress_repo
        self.ann_repo = ann_repo
        self.on_open_book = on_open_book
        self.stats_repo = stats_repo
        self.settings_repo = settings_repo
        self.on_show_statistics = on_show_statistics

        self.books: List[Book] = []
        self.sort_key: str = "recent"
        self.format_filter: str = "all"
        self._build_ui()
        self.refresh_library()

    def _build_ui(self):
        # 1. HeaderBar
        self.header = Adw.HeaderBar()
        self.append(self.header)

        # Import Book Button (+)
        btn_import = Gtk.Button(icon_name="list-add-symbolic")
        btn_import.set_tooltip_text("Import eBook (EPUB, PDF, CBZ, CBR)")
        btn_import.connect("clicked", self._on_import_clicked)
        self.header.pack_start(btn_import)

        # Collections (Cross-Book Annotations) Button (FR-11)
        btn_collections = Gtk.Button(icon_name="emblem-favorite-symbolic")
        btn_collections.set_tooltip_text("Collections: All Highlights & Notes (FR-11)")
        btn_collections.connect("clicked", self._on_collections_clicked)
        self.header.pack_start(btn_collections)

        # Reading Statistics Button (FR-15)
        btn_stats = Gtk.Button(icon_name="utilities-system-monitor-symbolic")
        btn_stats.set_tooltip_text("Reading Statistics & Insights (FR-15)")
        btn_stats.connect("clicked", lambda b: self._on_statistics_clicked())
        self.header.pack_start(btn_stats)

        # Catalogs Button (FR-14, WP-13)
        btn_catalog = Gtk.Button(icon_name="globe-symbolic")
        btn_catalog.set_tooltip_text("Book Catalogs — OPDS discovery & download (FR-14)")
        btn_catalog.connect("clicked", self._on_catalog_clicked)
        self.header.pack_start(btn_catalog)

        # Sync/Exchange Button (FR-17/FR-19, WP-14)
        btn_exchange = Gtk.Button(icon_name="folder-saved-search-symbolic")
        btn_exchange.set_tooltip_text("Sync & Migration — export/import reading data (FR-17/FR-19)")
        btn_exchange.connect("clicked", self._on_exchange_clicked)
        self.header.pack_start(btn_exchange)

        # Title
        self.title_widget = Adw.WindowTitle(title="Aquile Reader", subtitle="My Local Library")
        self.header.set_title_widget(self.title_widget)

        # Search Entry (FR-01)
        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_placeholder_text("Search books...")
        self.search_entry.set_hexpand(False)
        self.search_entry.connect("search-changed", self._on_search_changed)
        self.header.pack_end(self.search_entry)

        # Sort selector (FR-03: sort choices/direction)
        self.sort_combo = Gtk.DropDown.new_from_strings(["Recent", "Title A–Z", "Author A–Z"])
        self.sort_combo.set_tooltip_text("Sort library")
        self.sort_combo.connect("notify::selected", self._on_sort_changed)
        self.header.pack_end(self.sort_combo)

        # Format filter (FR-03: filters)
        self.format_combo = Gtk.DropDown.new_from_strings(["All formats", "EPUB", "PDF", "CBZ/CBR"])
        self.format_combo.set_tooltip_text("Filter by format")
        self.format_combo.connect("notify::selected", self._on_format_changed)
        self.header.pack_end(self.format_combo)

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
        self.empty_status.set_icon_name("x-office-document-symbolic")
        btn_empty_import = Gtk.Button(label="Import Book")
        btn_empty_import.add_css_class("suggested-action")
        btn_empty_import.add_css_class("pill")
        btn_empty_import.connect("clicked", self._on_import_clicked)
        self.empty_status.set_child(btn_empty_import)
        self.content_box.append(self.empty_status)

    def refresh_library(self, search_query: str = ""):
        self.books = self.book_repo.list_all()

        # Apply sort (FR-03)
        if self.sort_key == "title":
            self.books.sort(key=lambda b: b.title.lower())
        elif self.sort_key == "author":
            self.books.sort(key=lambda b: (b.author.lower(), b.title.lower()))
        # "recent" keeps repository ORDER BY added_at DESC

        # Clear existing rows
        while child := self.list_box.get_first_child():
            self.list_box.remove(child)

        query = search_query.strip().lower()
        displayed_count = 0

        for book in self.books:
            if query and (query not in book.title.lower() and query not in book.author.lower()):
                continue
            if self.format_filter != "all":
                fmt = (book.file_format or "").lower()
                if self.format_filter == "epub" and fmt != "epub":
                    continue
                if self.format_filter == "pdf" and fmt != "pdf":
                    continue
                if self.format_filter == "comic" and fmt not in ("cbz", "cbr", "comic"):
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
        row.set_activatable(True)
        row.connect("activate", lambda r, bk=book: self._on_show_details(bk))
        row_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        row_box.set_margin_start(16)
        row_box.set_margin_end(16)
        row_box.set_margin_top(12)
        row_box.set_margin_bottom(12)
        row.set_child(row_box)

        # Book Icon / Format Badge
        icon = Gtk.Image.new_from_icon_name("x-office-document-symbolic")
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
        size_str = f"{book.file_size_bytes // 1024} KB" if book.file_size_bytes else "size unknown"
        lbl_sub = Gtk.Label(label=f"{book.author} • {book.file_format.upper()} • {prog_str} • {book.total_chapters} ch • {size_str}")
        lbl_sub.set_xalign(0)
        lbl_sub.add_css_class("book-author")
        info_box.append(lbl_sub)

        # Favourite toggle (starred = B0 Favourites filter)
        fav_icon = "starred-symbolic" if getattr(book, "is_favorite", False) else "non-starred-symbolic"
        btn_fav = Gtk.Button(icon_name=fav_icon)
        btn_fav.set_tooltip_text("Toggle Favourite")
        btn_fav.connect("clicked", lambda b, bid=book.id: self._on_toggle_favorite(bid))
        row_box.append(btn_fav)

        # Reading Insights Button (FR-15)
        btn_stat = Gtk.Button(icon_name="utilities-system-monitor-symbolic")
        btn_stat.set_tooltip_text("Reading Insights")
        btn_stat.connect("clicked", lambda b, bid=book.id: self._on_statistics_clicked(initial_book_id=bid))
        row_box.append(btn_stat)

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

    def _on_sort_changed(self, dropdown, _):
        self.sort_key = ["recent", "title", "author"][dropdown.get_selected()]
        self.refresh_library(self.search_entry.get_text())

    def _on_format_changed(self, dropdown, _):
        self.format_filter = ["all", "epub", "pdf", "comic"][dropdown.get_selected()]
        self.refresh_library(self.search_entry.get_text())

    def _on_import_clicked(self, button):
        # File dialog using Gtk.FileDialog in GTK4
        file_dialog = Gtk.FileDialog()
        file_dialog.set_title("Select eBook to Import")

        # Filters for EPUB, PDF, CBZ, CBR
        filter_all = Gtk.FileFilter()
        filter_all.set_name("All Supported eBooks (*.epub, *.pdf, *.cbz, *.cbr)")
        filter_all.add_pattern("*.epub")
        filter_all.add_pattern("*.pdf")
        filter_all.add_pattern("*.cbz")
        filter_all.add_pattern("*.cbr")

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

        from ..covers import save_cover, clean_display_title

        ext = os.path.splitext(file_path)[1].lower().lstrip(".")
        title = clean_display_title(file_path)
        author = "Unknown Author"
        total_chaps = 1
        cover_path = None
        cover_data = None
        cover_mime = ""

        if ext == "epub":
            try:
                parser = EpubParser(file_path)
                if parser.title and parser.title != "Untitled":
                    title = parser.title
                if parser.author and parser.author != "Unknown Author":
                    author = parser.author
                total_chaps = max(1, len(parser.chapters))
                cover_data = parser.cover_data
                cover_mime = parser.cover_mime or ""
            except Exception:
                pass
        elif ext in ("cbz", "cbr"):
            try:
                from ..reader.comic_reader import ComicArchiveEngine
                engine = ComicArchiveEngine(file_path)
                total_chaps = max(1, engine.get_page_count())
                engine.close()
            except Exception:
                pass
        elif ext == "pdf":
            try:
                from ..reader.pdf_reader import PdfDocumentEngine
                engine = PdfDocumentEngine(file_path)
                total_chaps = max(1, engine.get_page_count())
                engine.close()
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
        if cover_data is not None:
            saved = save_cover(book.id, cover_data, cover_mime)
            if saved:
                book.cover_path = saved
        self.book_repo.add(book)
        self.refresh_library()
        self.on_open_book(book)

    def start_cover_backfill(self):
        """Fill missing EPUB covers one book per idle tick (bounded)."""
        try:
            pending = [b for b in (self.book_repo.list_all() or [])
                       if (b.file_format or "").lower() == "epub" and not b.cover_path]
        except Exception:
            return
        state = {"queue": pending}

        def _step():
            queue = state["queue"]
            if not queue:
                return False
            book = queue.pop(0)
            try:
                if book.cover_path or not book.file_path or not os.path.exists(book.file_path):
                    return True
                parser = EpubParser(book.file_path)
                if parser.cover_data:
                    from ..covers import save_cover
                    saved = save_cover(book.id, parser.cover_data, parser.cover_mime or "")
                    if saved:
                        book.cover_path = saved
                        self.book_repo.add(book)
            except Exception:
                pass
            if not queue:
                try:
                    self.refresh_library(self.search_entry.get_text())
                except Exception:
                    pass
                return False
            return True

        try:
            from gi.repository import GLib
            GLib.idle_add(_step)
        except Exception:
            pass

    def _on_catalog_clicked(self, button):
        try:
            from .catalog_dialog import CatalogDialog
            from ..catalog.catalog_manager import CatalogManager
            dialog = CatalogDialog(self.get_root(), CatalogManager(), self.import_file)
            dialog.present()
        except Exception:
            pass

    def _on_exchange_clicked(self, button):
        try:
            from .exchange_dialog import ExchangeDialog
            dialog = ExchangeDialog(self.get_root(), self.book_repo, self.progress_repo, self.ann_repo)
            dialog.present()
        except Exception:
            pass

    def _on_toggle_favorite(self, book_id: str):
        try:
            book = self.book_repo.get_by_id(book_id)
            if book is None:
                return
            self.book_repo.set_favorite(book_id, not getattr(book, "is_favorite", False))
        except Exception:
            pass
        self.refresh_library(self.search_entry.get_text())

    def _on_show_details(self, book: Book):
        try:
            from .book_details import BookDetailsPane
            dialog = Adw.Window(transient_for=self.get_root(), modal=True,
                                title=f"{book.title} — Details")
            dialog.set_default_size(480, 640)
            progress = self.progress_repo.get(book.id)
            prog = {"percentage": progress.percentage if progress else 0.0}
            pane = BookDetailsPane()
            pane.bind(book, prog,
                      on_open=lambda bk: (dialog.close(), self.on_open_book(bk)),
                      on_close=lambda: dialog.close(),
                      book_repo=self.book_repo)
            dialog.set_content(pane)
            dialog.present()
        except Exception:
            self.on_open_book(book)

    def _on_statistics_clicked(self, initial_book_id: Optional[str] = None):
        if self.on_show_statistics:
            self.on_show_statistics(initial_book_id)
            return
        if not self.stats_repo:
            return
        parent = self.get_root()
        settings = self.settings_repo.load() if self.settings_repo else None
        dialog = StatisticsDialog(
            parent_window=parent,
            stats_repo=self.stats_repo,
            book_repo=self.book_repo,
            settings=settings,
            initial_book_id=initial_book_id
        )
        dialog.present()

    def _on_delete_book(self, book_id: str):
        dialog = Adw.MessageDialog(transient_for=self.get_root(), heading="Remove from library?",
                                   body="The library entry and its reading data will be removed. The source file on disk is kept.")
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("remove", "Remove")
        dialog.set_response_appearance("remove", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.connect("response", lambda d, r: self._confirm_delete(r, book_id))
        dialog.present()

    def _confirm_delete(self, response: str, book_id: str):
        if response == "remove":
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

        search = Gtk.SearchEntry(placeholder_text="Search annotations...")
        search.set_margin_start(16)
        search.set_margin_end(16)
        search.set_margin_top(8)
        box.append(search)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        box.append(scrolled)

        list_box = Gtk.ListBox()
        list_box.add_css_class("boxed-list")
        list_box.set_margin_start(16)
        list_box.set_margin_end(16)
        list_box.set_margin_top(8)
        list_box.set_margin_bottom(16)

        def populate(query: str = ""):
            while child := list_box.get_first_child():
                list_box.remove(child)
            q = query.strip().lower()
            shown = 0
            for ann in self.ann_repo.list_all():
                book = self.book_repo.get_by_id(ann.book_id)
                book_title = book.title if book else "Unknown Book"
                hay = f"{ann.text_content} {ann.note_text} {book_title}".lower()
                if q and q not in hay:
                    continue
                row = Adw.ActionRow(activatable=True)
                row.set_title(f'"{ann.text_content[:120]}"')
                subtitle = f"Book: {book_title}"
                if ann.note_text:
                    subtitle += f" • Note: {ann.note_text[:80]}"
                row.set_subtitle(subtitle)
                row.add_suffix(Gtk.Image.new_from_icon_name("go-next-symbolic"))
                row.connect("activated", lambda r, b=book: self._on_collection_jump(dialog, b))
                btn_del = Gtk.Button(icon_name="user-trash-symbolic")
                btn_del.set_tooltip_text("Delete annotation")
                btn_del.connect("clicked", lambda b, aid=ann.id: (self.ann_repo.delete(aid), populate(search.get_text())))
                row.add_suffix(btn_del)
                list_box.append(row)
                shown += 1
            if shown == 0:
                status = Adw.StatusPage()
                status.set_title("No Annotations Yet" if not q else "No matches")
                status.set_description("Highlights and notes created while reading will appear here across all your books.")
                status.set_icon_name("emblem-favorite-symbolic")
                scrolled.set_child(status)
            else:
                scrolled.set_child(list_box)

        search.connect("search-changed", lambda e: populate(e.get_text()))
        populate()

        dialog.present()

    def _on_collection_jump(self, dialog, book):
        if book is None:
            return
        dialog.close()
        self.on_open_book(book)
