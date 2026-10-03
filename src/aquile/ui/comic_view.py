"""
Comic Reader View for Aquile Reader.
Displays comic pages in Gtk.Picture with aspect ratio preservation (Gtk.ContentFit.CONTAIN),
supporting single-page and double-page spread modes, Western (LTR) and Manga (RTL) reading directions,
page jumping, progress tracking, and 5-second checkpoint persistence (FR-01, FR-06, FR-07, NFR-01, VP-01).
"""

import time
from typing import Optional, Callable

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib, Gdk

from ..domain.models import Book, ReadingProgress, AppSettings
from ..storage.repository import (
    BookRepository, ReadingProgressRepository, SettingsRepository, AnnotationRepository
)
from ..reader.comic_reader import ComicArchiveEngine


class ComicReaderView(Gtk.Box):
    """
    GTK4 / Libadwaita view for reading CBZ and CBR comic book archives.
    Maintains aspect ratio containment and autosaves reading progress.
    """

    def __init__(
        self,
        book: Book,
        book_repo: BookRepository,
        progress_repo: ReadingProgressRepository,
        *args,
        settings_repo: Optional[SettingsRepository] = None,
        on_back_to_library: Optional[Callable[[], None]] = None,
        ann_repo: Optional[AnnotationRepository] = None,
        spread_mode: str = "double",
        reading_direction: str = "ltr",
        **kwargs
    ):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.book = book
        self.book_repo = book_repo
        self.progress_repo = progress_repo

        # Flexible positional arg handling for various application wiring signatures
        if len(args) == 1:
            if callable(args[0]):
                on_back_to_library = args[0]
            else:
                settings_repo = args[0]
        elif len(args) == 2:
            settings_repo = args[0]
            on_back_to_library = args[1]
        elif len(args) >= 3:
            ann_repo = args[0]
            settings_repo = args[1]
            on_back_to_library = args[2]

        self.settings_repo = settings_repo
        self.ann_repo = ann_repo
        self.on_back_to_library = on_back_to_library or (lambda: None)

        self.settings: AppSettings = (
            self.settings_repo.load()
            if self.settings_repo and hasattr(self.settings_repo, "load")
            else AppSettings()
        )

        self.spread_mode: str = spread_mode
        self.reading_direction: str = reading_direction
        self.current_page_idx: int = 0
        self.current_spread_idx: int = 0
        self.auto_save_source_id: Optional[int] = None

        # Initialize archive engine
        self.engine = ComicArchiveEngine(self.book.file_path)

        self._load_saved_progress()
        self._build_ui()
        self._apply_theme()
        self._update_spreads_and_render()
        self._start_autosave_timer()

    def _load_saved_progress(self):
        """Loads previous reading position from repository."""
        if not self.progress_repo or not hasattr(self.progress_repo, "get"):
            return
        progress = self.progress_repo.get(self.book.id)
        if progress:
            count = self.engine.get_page_count()
            if count > 0:
                self.current_page_idx = max(0, min(progress.page_index, count - 1))
            else:
                self.current_page_idx = 0

    def _build_ui(self):
        """Builds header, reading canvas with Gtk.Picture containment, and footer."""
        # 1. HeaderBar
        self.header = Adw.HeaderBar()
        self.append(self.header)

        btn_back = Gtk.Button(icon_name="go-previous-symbolic")
        btn_back.set_tooltip_text("Back to Library")
        btn_back.connect("clicked", self._on_back_clicked)
        self.header.pack_start(btn_back)

        # Spread mode toggle button (Single vs Double)
        self.btn_spread_mode = Gtk.Button(
            label="Double Spread" if self.spread_mode == "double" else "Single Page"
        )
        self.btn_spread_mode.set_tooltip_text("Toggle Single / Double Spread (FR-06)")
        self.btn_spread_mode.connect("clicked", lambda b: self.toggle_spread_mode())
        self.header.pack_start(self.btn_spread_mode)

        # Reading direction toggle button (LTR Western vs RTL Manga)
        self.btn_direction = Gtk.Button(
            label="Manga (RTL)" if self.reading_direction == "rtl" else "Western (LTR)"
        )
        self.btn_direction.set_tooltip_text("Toggle Reading Direction: Western (LTR) / Manga (RTL) (FR-07)")
        self.btn_direction.connect("clicked", lambda b: self.toggle_reading_direction())
        self.header.pack_start(self.btn_direction)

        # Title widget
        self.title_widget = Adw.WindowTitle(
            title=self.book.title,
            subtitle=self.book.author or "Comic Book"
        )
        self.header.set_title_widget(self.title_widget)

        # Page jump button
        self.btn_jump = Gtk.Button(icon_name="go-jump-symbolic")
        self.btn_jump.set_tooltip_text("Jump to Page")
        self.btn_jump.connect("clicked", self._show_jump_dialog)
        self.header.pack_end(self.btn_jump)

        # 2. Reading Canvas Box
        self.canvas_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        self.canvas_box.set_vexpand(True)
        self.canvas_box.set_hexpand(True)
        self.canvas_box.set_halign(Gtk.Align.CENTER)
        self.canvas_box.set_valign(Gtk.Align.CENTER)
        self.canvas_box.set_margin_start(16)
        self.canvas_box.set_margin_end(16)
        self.canvas_box.set_margin_top(12)
        self.canvas_box.set_margin_bottom(12)
        self.canvas_box.add_css_class("comic-reading-canvas")
        self.append(self.canvas_box)

        # Left Picture Container
        self.left_picture = Gtk.Picture()
        self.left_picture.set_content_fit(Gtk.ContentFit.CONTAIN)
        self.left_picture.set_can_shrink(True)
        self.left_picture.set_hexpand(True)
        self.left_picture.set_vexpand(True)
        self.left_picture.set_halign(Gtk.Align.CENTER)
        self.left_picture.set_valign(Gtk.Align.CENTER)
        self.canvas_box.append(self.left_picture)

        # Right Picture Container (for 2-page spread)
        self.right_picture = Gtk.Picture()
        self.right_picture.set_content_fit(Gtk.ContentFit.CONTAIN)
        self.right_picture.set_can_shrink(True)
        self.right_picture.set_hexpand(True)
        self.right_picture.set_vexpand(True)
        self.right_picture.set_halign(Gtk.Align.CENTER)
        self.right_picture.set_valign(Gtk.Align.CENTER)
        self.canvas_box.append(self.right_picture)

        # 3. Footer Bar (Progress & Navigation)
        self.footer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        self.footer.add_css_class("reader-progress-footer")
        self.append(self.footer)

        self.btn_prev = Gtk.Button(icon_name="go-previous-symbolic")
        self.btn_prev.set_tooltip_text("Previous Page (Left Arrow / Page Up)")
        self.btn_prev.connect("clicked", lambda b: self.prev_page())
        self.footer.append(self.btn_prev)

        self.page_label = Gtk.Label(label="Page 1 of 1 (0.0%)")
        self.page_label.add_css_class("reader-page-label")
        self.footer.append(self.page_label)

        self.progress_bar = Gtk.ProgressBar()
        self.progress_bar.set_hexpand(True)
        self.footer.append(self.progress_bar)

        self.btn_next = Gtk.Button(icon_name="go-next-symbolic")
        self.btn_next.set_tooltip_text("Next Page (Right Arrow / Page Down / Space)")
        self.btn_next.connect("clicked", lambda b: self.next_page())
        self.footer.append(self.btn_next)

        # 4. Keyboard Controller Event
        key_controller = Gtk.EventControllerKey()
        key_controller.connect("key-pressed", self._on_key_pressed)
        self.add_controller(key_controller)

    def _apply_theme(self):
        """Applies active application theme to root window."""
        root = self.get_root()
        if not root:
            return
        for theme_class in ["aquile-theme-light", "aquile-theme-dark", "aquile-theme-sepia"]:
            root.remove_css_class(theme_class)
        theme = getattr(self.settings, "theme", "light") if self.settings else "light"
        root.add_css_class(f"aquile-theme-{theme}")

    def _update_spreads_and_render(self):
        """Recalculates active spread based on mode and direction, and renders."""
        page_count = self.engine.get_page_count()
        if page_count == 0:
            self.current_page_idx = 0
            self.current_spread_idx = 0
            self._render_current_spread()
            return

        spreads = self.engine.get_spreads(mode=self.spread_mode, direction=self.reading_direction)
        found = False
        for idx, spread in enumerate(spreads):
            if self.current_page_idx in spread:
                self.current_spread_idx = idx
                found = True
                break
        if not found:
            self.current_spread_idx = 0
            if spreads and spreads[0]:
                self.current_page_idx = min(spreads[0])

        self._render_current_spread()

    def _render_current_spread(self):
        """Renders the pages in current spread to left and right Gtk.Picture widgets."""
        page_count = self.engine.get_page_count()
        if page_count == 0:
            self.left_picture.set_paintable(None)
            self.left_picture.set_visible(False)
            self.right_picture.set_paintable(None)
            self.right_picture.set_visible(False)
            self.page_label.set_text("Page 0 of 0 (0.0%)")
            self.progress_bar.set_fraction(0.0)
            self.btn_prev.set_sensitive(False)
            self.btn_next.set_sensitive(False)
            return

        spreads = self.engine.get_spreads(mode=self.spread_mode, direction=self.reading_direction)
        if not spreads:
            return

        self.current_spread_idx = max(0, min(self.current_spread_idx, len(spreads) - 1))
        current_spread = spreads[self.current_spread_idx]

        if len(current_spread) == 1:
            p0 = current_spread[0]
            tex0 = self.engine.get_page_texture(p0)
            self.left_picture.set_paintable(tex0)
            self.left_picture.set_visible(True)
            self.right_picture.set_paintable(None)
            self.right_picture.set_visible(False)
            page_text = f"Page {p0 + 1} of {page_count}"
        elif len(current_spread) >= 2:
            p0, p1 = current_spread[0], current_spread[1]
            tex0 = self.engine.get_page_texture(p0)
            tex1 = self.engine.get_page_texture(p1)
            self.left_picture.set_paintable(tex0)
            self.left_picture.set_visible(True)
            self.right_picture.set_paintable(tex1)
            self.right_picture.set_visible(True)
            min_p = min(p0, p1) + 1
            max_p = max(p0, p1) + 1
            page_text = f"Pages {min_p}–{max_p} of {page_count}"
        else:
            page_text = ""

        cur_p = self.current_page_idx + 1
        percentage = round((cur_p / page_count) * 100, 1)
        self.page_label.set_text(f"{page_text}  ({percentage}%)")
        self.progress_bar.set_fraction(min(1.0, max(0.0, cur_p / page_count)))

        self.btn_prev.set_sensitive(self.current_spread_idx > 0)
        self.btn_next.set_sensitive(self.current_spread_idx < len(spreads) - 1)

        if hasattr(self, "btn_spread_mode"):
            self.btn_spread_mode.set_label("Double Spread" if self.spread_mode == "double" else "Single Page")
        if hasattr(self, "btn_direction"):
            self.btn_direction.set_label("Manga (RTL)" if self.reading_direction == "rtl" else "Western (LTR)")

    def next_page(self):
        """Navigates to the next spread/page and updates position checkpoint."""
        page_count = self.engine.get_page_count()
        if page_count == 0:
            return
        spreads = self.engine.get_spreads(mode=self.spread_mode, direction=self.reading_direction)
        if self.current_spread_idx + 1 < len(spreads):
            self.current_spread_idx += 1
            next_spread = spreads[self.current_spread_idx]
            self.current_page_idx = min(next_spread)
            self._render_current_spread()
            self._save_checkpoint()

    def prev_page(self):
        """Navigates to the previous spread/page and updates position checkpoint."""
        page_count = self.engine.get_page_count()
        if page_count == 0:
            return
        spreads = self.engine.get_spreads(mode=self.spread_mode, direction=self.reading_direction)
        if self.current_spread_idx > 0:
            self.current_spread_idx -= 1
            prev_spread = spreads[self.current_spread_idx]
            self.current_page_idx = min(prev_spread)
            self._render_current_spread()
            self._save_checkpoint()

    def next_spread(self):
        """Alias for next_page."""
        self.next_page()

    def prev_spread(self):
        """Alias for prev_page."""
        self.prev_page()

    def jump_to_page(self, page_index: int):
        """Directly jumps to the designated page index."""
        page_count = self.engine.get_page_count()
        if page_count == 0:
            return
        self.current_page_idx = max(0, min(page_index, page_count - 1))
        spreads = self.engine.get_spreads(mode=self.spread_mode, direction=self.reading_direction)
        for idx, spread in enumerate(spreads):
            if self.current_page_idx in spread:
                self.current_spread_idx = idx
                break
        self._render_current_spread()
        self._save_checkpoint()

    def toggle_spread_mode(self):
        """Toggles between single-page mode and double-page spread mode."""
        new_mode = "single" if self.spread_mode == "double" else "double"
        self.set_spread_mode(new_mode)

    def set_spread_mode(self, mode: str):
        """Sets spread mode ('single' or 'double')."""
        mode = mode.lower()
        if mode not in ("single", "double"):
            raise ValueError(f"Invalid spread mode: {mode}")
        if self.spread_mode == mode:
            return
        self.spread_mode = mode
        self._update_spreads_and_render()

    def toggle_reading_direction(self):
        """Toggles reading direction between Western (LTR) and Manga (RTL)."""
        new_dir = "rtl" if self.reading_direction == "ltr" else "ltr"
        self.set_reading_direction(new_dir)

    def set_reading_direction(self, direction: str):
        """Sets reading direction ('ltr' or 'rtl')."""
        direction = direction.lower()
        if direction not in ("ltr", "rtl"):
            raise ValueError(f"Invalid reading direction: {direction}")
        if self.reading_direction == direction:
            return
        self.reading_direction = direction
        self._update_spreads_and_render()

    def _start_autosave_timer(self):
        """Starts 5-second periodic location checkpoint timer (NFR-01)."""
        interval_s = getattr(self.settings, "auto_save_interval", 5.0) if self.settings else 5.0
        interval_ms = int(interval_s * 1000)
        self.auto_save_source_id = GLib.timeout_add(interval_ms, self._on_periodic_autosave)

    def _on_periodic_autosave(self) -> bool:
        """Periodic timeout callback persisting current reading progress."""
        self._save_checkpoint()
        return True

    def _save_checkpoint(self):
        """Persists current reading progress into SQLite WAL database."""
        if not self.progress_repo or not self.book:
            return
        page_count = self.engine.get_page_count()
        if page_count == 0:
            return

        cur_p = self.current_page_idx + 1
        percentage = round((cur_p / page_count) * 100, 1) if page_count > 0 else 0.0

        prog = ReadingProgress(
            book_id=self.book.id,
            chapter_index=0,
            page_index=self.current_page_idx,
            cfi=f"comic/page/{self.current_page_idx}",
            percentage=percentage,
            updated_at=time.time()
        )
        self.progress_repo.save(prog)
        if self.book_repo and hasattr(self.book_repo, "update_last_read"):
            self.book_repo.update_last_read(self.book.id)

    def _on_key_pressed(self, controller, keyval, keycode, state):
        """Handles keyboard navigation events."""
        if keyval in (Gdk.KEY_Right, Gdk.KEY_Page_Down, Gdk.KEY_space):
            self.next_page()
            return True
        elif keyval in (Gdk.KEY_Left, Gdk.KEY_Page_Up):
            self.prev_page()
            return True
        elif keyval == Gdk.KEY_Home:
            self.jump_to_page(0)
            return True
        elif keyval == Gdk.KEY_End:
            self.jump_to_page(self.engine.get_page_count() - 1)
            return True
        return False

    def _show_jump_dialog(self, button=None):
        """Displays page jump popover."""
        page_count = self.engine.get_page_count()
        if page_count == 0:
            return

        popover = Gtk.Popover()
        popover.set_parent(self.btn_jump)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_start(12)
        box.set_margin_end(12)
        box.set_margin_top(12)
        box.set_margin_bottom(12)

        lbl = Gtk.Label(label=f"Go to Page (1..{page_count}):")
        box.append(lbl)

        entry = Gtk.Entry()
        entry.set_text(str(self.current_page_idx + 1))
        entry.set_activates_default(True)
        box.append(entry)

        btn_go = Gtk.Button(label="Go")
        btn_go.add_css_class("suggested-action")
        box.append(btn_go)

        def on_jump(*args):
            try:
                val = int(entry.get_text().strip())
                self.jump_to_page(val - 1)
                popover.popdown()
            except ValueError:
                pass

        btn_go.connect("clicked", on_jump)
        entry.connect("activate", on_jump)

        popover.set_child(box)
        popover.popup()

    def _on_back_clicked(self, button):
        """Orderly returns to library view."""
        self.cleanup()
        if self.on_back_to_library:
            self.on_back_to_library()

    def cleanup(self):
        """Orderly shutdown save on view destruction or exit (NFR-01)."""
        if self.auto_save_source_id:
            GLib.source_remove(self.auto_save_source_id)
            self.auto_save_source_id = None
        self._save_checkpoint()
        if hasattr(self.engine, "close"):
            self.engine.close()
