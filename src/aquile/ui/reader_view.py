"""
Reader View for Aquile Reader.
Implements the signature two-column reading canvas, typography customization,
TOC navigation, durable annotations, and 5-second checkpoint persistence (FR-05, FR-08, FR-10, NFR-01, VP-01).
"""

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib, Gdk
import time
from typing import Optional, Callable

from ..domain.models import Book, ReadingProgress, Annotation, AppSettings
from ..storage.repository import (
    BookRepository, ReadingProgressRepository, AnnotationRepository, SettingsRepository
)
from ..reader.epub_parser import EpubParser
from ..reader.pagination import ChapterPaginator, PageView
from ..reader.cfi import CFI
from .settings_dialog import SettingsDialog
from .toc_dialog import TocDialog
from .annotation_dialog import AnnotationDialog

class ReaderView(Gtk.Box):
    def __init__(self, book: Book, book_repo: BookRepository, progress_repo: ReadingProgressRepository,
                 ann_repo: AnnotationRepository, settings_repo: SettingsRepository,
                 on_back_to_library: Callable[[], None]):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.book = book
        self.book_repo = book_repo
        self.progress_repo = progress_repo
        self.ann_repo = ann_repo
        self.settings_repo = settings_repo
        self.on_back_to_library = on_back_to_library

        self.settings: AppSettings = self.settings_repo.load()
        self.current_chapter_idx: int = 0
        self.current_page_idx: int = 0
        self.paginator: Optional[ChapterPaginator] = None
        self.auto_save_source_id: Optional[int] = None

        # Load EPUB
        self.parser = EpubParser(self.book.file_path)
        self._load_saved_progress()

        self._build_ui()
        self._apply_theme()
        self._paginate_and_display()
        self._start_autosave_timer()

    def _load_saved_progress(self):
        progress = self.progress_repo.get(self.book.id)
        if progress:
            self.current_chapter_idx = max(0, min(progress.chapter_index, len(self.parser.chapters) - 1))
            self.current_page_idx = progress.page_index

    def _build_ui(self):
        from .reader_chrome import ReaderToolbar, ReaderStatusBar, ReaderDisplayPopover

        # 1. Dark Aquile-style toolbar (B0: back/menu/TOC/bookmark left;
        #    search/read-aloud/text/dictionary/fullscreen right).
        self.toolbar = ReaderToolbar(callbacks={
            "back": self._on_back_clicked,
            "menu": self._on_toc_clicked,
            "toc": self._on_toc_clicked,
            "bookmark": self._on_add_annotation_clicked,
            "read_aloud": self._on_tts_clicked,
            "dictionary": self._on_dictionary_clicked,
            "fullscreen": self._on_fullscreen_clicked,
        })
        self.append(self.toolbar)

        self.display_popover = ReaderDisplayPopover(
            self.settings, self.settings_repo,
            on_changed=self._on_settings_updated,
        )
        self.display_popover.set_parent(self.toolbar.buttons["display_settings"])
        self.toolbar.callbacks["display_settings"] = lambda b: self.display_popover.popup()
        self.toolbar.callbacks["search"] = self._on_search_clicked

        # 2. Reading Canvas (Two-Column & Single-Column Container)
        self.reading_canvas = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=24)
        self.reading_canvas.set_vexpand(True)
        self.reading_canvas.set_hexpand(True)
        self.reading_canvas.set_margin_start(40)
        self.reading_canvas.set_margin_end(40)
        self.reading_canvas.set_margin_top(20)
        self.reading_canvas.set_margin_bottom(12)
        self.reading_canvas.add_css_class("reading-surface")
        self.append(self.reading_canvas)

        # Left Column View
        self.left_text_view = Gtk.TextView()
        self.left_text_view.set_editable(False)
        self.left_text_view.set_cursor_visible(False)
        self.left_text_view.set_wrap_mode(Gtk.WrapMode.WORD)
        self.left_text_view.set_hexpand(True)
        self.left_text_view.set_vexpand(True)
        self.left_text_view.add_css_class("reading-column")
        self.reading_canvas.append(self.left_text_view)

        # Column Separator Rule
        self.separator = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        self.separator.add_css_class("reading-column-separator")
        self.reading_canvas.append(self.separator)

        # Right Column View (Aquile Reader Two-Column Signature)
        self.right_text_view = Gtk.TextView()
        self.right_text_view.set_editable(False)
        self.right_text_view.set_cursor_visible(False)
        self.right_text_view.set_wrap_mode(Gtk.WrapMode.WORD)
        self.right_text_view.set_hexpand(True)
        self.right_text_view.set_vexpand(True)
        self.right_text_view.add_css_class("reading-column")
        self.reading_canvas.append(self.right_text_view)

        # 3. Aquile status bar: Chapter » Section | page/total | %.
        self.status_bar = ReaderStatusBar()
        self.append(self.status_bar)
        # Compat alias kept for external readers of page text.
        self.page_label = self.status_bar.page_label

        # 4. Keyboard Controller Event
        key_controller = Gtk.EventControllerKey()
        key_controller.connect("key-pressed", self._on_key_pressed)
        self.add_controller(key_controller)

    def _paginate_and_display(self):
        if not self.parser.chapters:
            return

        chapter = self.parser.chapters[self.current_chapter_idx]
        chapter_title = chapter.get("title", f"Chapter {self.current_chapter_idx + 1}")
        try:
            root = self.get_root()
            if root is not None and hasattr(root, "set_title"):
                root.set_title(f"{self.book.title} - Aquile Reader")
        except Exception:
            pass

        # Viewport dimensions approximation (1024x768 default if unallocated)
        w = self.reading_canvas.get_width()
        h = self.reading_canvas.get_height()
        vw = w if w > 200 else 1024
        vh = h if h > 200 else 768

        self.paginator = ChapterPaginator(
            chapter["clean_text"],
            viewport_width=vw,
            viewport_height=vh,
            columns=min(2, self.settings.columns),
            font_size=self.settings.font_size,
            line_height=self.settings.line_height
        )

        self.current_page_idx = min(self.current_page_idx, max(0, self.paginator.page_count - 1))
        self._display_current_page()

    def _display_current_page(self):
        if not self.paginator:
            return

        page: PageView = self.paginator.get_page(self.current_page_idx)

        # Update text views
        left_buf = self.left_text_view.get_buffer()
        left_buf.set_text(page.left_column)

        if self.settings.columns == 2 or self.settings.columns >= 3:
            self.separator.set_visible(True)
            self.right_text_view.set_visible(True)
            right_buf = self.right_text_view.get_buffer()
            right_buf.set_text(page.right_column)
        else:
            self.separator.set_visible(False)
            self.right_text_view.set_visible(False)

        # Update Aquile status bar: Chapter » Section | page/total | %.
        total_p = max(1, self.paginator.page_count)
        cur_p = self.current_page_idx + 1

        # Total progress across chapters
        total_chaps = len(self.parser.chapters)
        chap_frac = (self.current_chapter_idx + (cur_p / total_p)) / total_chaps if total_chaps else 0.0
        percentage = round(chap_frac * 100, 1)

        chapter = self.parser.chapters[self.current_chapter_idx]
        chapter_title = chapter.get("title", f"Chapter {self.current_chapter_idx + 1}")
        self.status_bar.set_location(chapter_title, f"Page {cur_p}")
        self.status_bar.set_page(cur_p, total_p)
        self.status_bar.set_percent(percentage)

    def next_page(self):
        if not self.paginator:
            return
        if self.current_page_idx + 1 < self.paginator.page_count:
            self.current_page_idx += 1
            self._display_current_page()
            self._save_checkpoint()
        elif self.current_chapter_idx + 1 < len(self.parser.chapters):
            self.current_chapter_idx += 1
            self.current_page_idx = 0
            self._paginate_and_display()
            self._save_checkpoint()

    def prev_page(self):
        if not self.paginator:
            return
        if self.current_page_idx > 0:
            self.current_page_idx -= 1
            self._display_current_page()
            self._save_checkpoint()
        elif self.current_chapter_idx > 0:
            self.current_chapter_idx -= 1
            # Go to last page of previous chapter
            self._paginate_and_display()
            self.current_page_idx = max(0, self.paginator.page_count - 1)
            self._display_current_page()
            self._save_checkpoint()

    def _on_key_pressed(self, controller, keyval, keycode, state):
        if keyval in (Gdk.KEY_Right, Gdk.KEY_Page_Down, Gdk.KEY_space):
            self.next_page()
            return True
        elif keyval in (Gdk.KEY_Left, Gdk.KEY_Page_Up):
            self.prev_page()
            return True
        return False

    def _start_autosave_timer(self):
        # NFR-01: 5-second bound periodic checkpoint
        interval_ms = int(self.settings.auto_save_interval * 1000)
        self.auto_save_source_id = GLib.timeout_add(interval_ms, self._on_periodic_autosave)

    def _on_periodic_autosave(self) -> bool:
        self._save_checkpoint()
        return True  # Keep recurring

    def _save_checkpoint(self):
        if not self.paginator:
            return
        total_chaps = len(self.parser.chapters)
        cur_p = self.current_page_idx + 1
        total_p = max(1, self.paginator.page_count)
        chap_frac = (self.current_chapter_idx + (cur_p / total_p)) / total_chaps if total_chaps else 0.0
        
        cfi_val = CFI.generate(self.current_chapter_idx, self.current_page_idx, self.current_page_idx)
        prog = ReadingProgress(
            book_id=self.book.id,
            chapter_index=self.current_chapter_idx,
            page_index=self.current_page_idx,
            cfi=cfi_val,
            percentage=round(chap_frac * 100, 1),
            updated_at=time.time()
        )
        self.progress_repo.save(prog)
        self.book_repo.update_last_read(self.book.id)

    # Maps every supported page-theme key (legacy + Aquile B0 set) to the
    # CSS classes in style.css. Unknown keys fall back to sepia-cream.
    PAGE_THEME_CLASSES = {
        "light": ("aquile-theme-light", "page-theme-white"),
        "white": ("aquile-theme-light", "page-theme-white"),
        "dark": ("aquile-theme-dark", "page-theme-night"),
        "night": ("aquile-theme-dark", "page-theme-night"),
        "sepia": ("aquile-theme-sepia", "page-theme-sepia"),
        "silver": ("aquile-theme-sepia", "page-theme-silver"),
        "solarized": ("aquile-theme-sepia", "page-theme-solarized"),
        "custom": ("aquile-theme-sepia", "page-theme-sepia"),
    }

    def _apply_theme(self):
        root = self.get_root()
        if not root:
            return
        known = ["aquile-theme-light", "aquile-theme-dark", "aquile-theme-sepia",
                 "page-theme-white", "page-theme-silver", "page-theme-sepia",
                 "page-theme-night", "page-theme-solarized"]
        for theme_class in known:
            root.remove_css_class(theme_class)
        for theme_class in self.PAGE_THEME_CLASSES.get(self.settings.theme, ("aquile-theme-sepia", "page-theme-sepia")):
            root.add_css_class(theme_class)
        margin_px = int(8 + (getattr(self.settings, "margin_percent", 5) or 5) * 6)
        self.reading_canvas.set_margin_start(margin_px)
        self.reading_canvas.set_margin_end(margin_px)

    def _on_settings_clicked(self, button):
        dialog = SettingsDialog(
            parent_window=self.get_root(),
            settings=self.settings,
            settings_repo=self.settings_repo,
            on_changed_callback=self._on_settings_updated
        )
        dialog.present()

    def _on_settings_updated(self, new_settings: AppSettings):
        self.settings = new_settings
        self._apply_theme()
        self._paginate_and_display()

    def _on_toc_clicked(self, button):
        dialog = TocDialog(
            parent_window=self.get_root(),
            toc_items=self.parser.toc_items,
            on_select_chapter=self._on_chapter_selected
        )
        dialog.present()

    def _on_chapter_selected(self, chapter_idx: int):
        self.current_chapter_idx = chapter_idx
        self.current_page_idx = 0
        self._paginate_and_display()
        self._save_checkpoint()

    def _on_add_annotation_clicked(self, button):
        # Extract current page sample text for the note
        page = self.paginator.get_page(self.current_page_idx) if self.paginator else None
        sample_snippet = (page.left_column[:100] + "...") if page and page.left_column else "Current Page Bookmark"

        def _on_save_annotation(note_text: str, color: str):
            ann = Annotation(
                book_id=self.book.id,
                chapter_index=self.current_chapter_idx,
                cfi=CFI.generate(self.current_chapter_idx, 0, len(sample_snippet)),
                start_offset=0,
                end_offset=len(sample_snippet),
                text_content=sample_snippet,
                note_text=note_text,
                color=color
            )
            self.ann_repo.add(ann)

        dialog = AnnotationDialog(
            parent_window=self.get_root(),
            selected_text=sample_snippet,
            on_save_callback=_on_save_annotation
        )
        dialog.present()

    def _on_tts_clicked(self, button):
        try:
            from .tts_controls import TtsBar
            from ..reader.tts_engine import TtsEngine
            engine = TtsEngine()
            bar = TtsBar(engine)
            bar.bind_text(lambda: (self.paginator.get_page(self.current_page_idx).left_column if self.paginator else ""))
            win = Adw.Window(transient_for=self.get_root(), modal=True, title="Read Aloud")
            win.set_default_size(420, 160)
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            box.append(bar)
            win.set_content(box)
            win.present()
        except Exception:
            pass

    def _on_dictionary_clicked(self, button):
        try:
            from .dictionary_dialog import DictionaryDialog
            from ..reader.dictionary import DictionaryService
            dialog = DictionaryDialog(self.get_root(), DictionaryService())
            dialog.present()
        except Exception:
            pass

    def _on_search_clicked(self, button):
        # In-book search is not implemented yet; keep the toolbar affordance
        # visible per B0 without side effects.
        return

    def _on_fullscreen_clicked(self, button):
        try:
            root = self.get_root()
            if root is None:
                return
            if getattr(self, "_fullscreen", False):
                root.unfullscreen()
                self._fullscreen = False
            else:
                root.fullscreen()
                self._fullscreen = True
        except Exception:
            pass

    def _on_back_clicked(self, button):
        self.cleanup()
        self.on_back_to_library()

    def cleanup(self):
        """Orderly shutdown save (NFR-01)."""
        if self.auto_save_source_id:
            GLib.source_remove(self.auto_save_source_id)
            self.auto_save_source_id = None
        self._save_checkpoint()
