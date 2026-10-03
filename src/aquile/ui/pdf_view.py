"""
PDF Reader View for Aquile Reader.
Implements fixed-layout document viewing with vector zoom, fit modes,
page navigation, and 5-second checkpoint persistence (WP-10 / FR-06 / FR-07 / NFR-01).
"""

import time
from typing import Optional, Callable, Any

try:
    import gi
    gi.require_version('Gtk', '4.0')
    gi.require_version('Adw', '1')
    gi.require_version('Gdk', '4.0')
    from gi.repository import Gtk, Adw, GLib, Gdk
    HAS_GTK = True
except (ImportError, ValueError):
    HAS_GTK = False

from ..domain.models import Book, ReadingProgress, AppSettings
from ..storage.repository import (
    BookRepository, ReadingProgressRepository, SettingsRepository, AnnotationRepository
)
from ..reader.pdf_reader import PdfDocumentEngine


class PdfReaderView(Gtk.Box):
    """
    GTK4 / Libadwaita view for rendering PDF documents.
    Embeds vector pages in a Gtk.Picture inside a Gtk.ScrolledWindow,
    providing page turning, direct jumping, zoom/fit controls, and durable progress persistence.
    """

    def __init__(
        self,
        book: Book,
        book_repo: BookRepository,
        progress_repo: ReadingProgressRepository,
        *args,
        **kwargs
    ):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.book = book
        self.book_repo = book_repo
        self.progress_repo = progress_repo

        # Extract optional repositories and callbacks flexibly
        self.settings_repo: Optional[SettingsRepository] = None
        self.ann_repo: Optional[AnnotationRepository] = None
        self.on_back_to_library: Optional[Callable[[], None]] = None

        for arg in args:
            if isinstance(arg, AnnotationRepository):
                self.ann_repo = arg
            elif isinstance(arg, SettingsRepository):
                self.settings_repo = arg
            elif callable(arg):
                self.on_back_to_library = arg

        if "settings_repo" in kwargs:
            self.settings_repo = kwargs["settings_repo"]
        if "ann_repo" in kwargs:
            self.ann_repo = kwargs["ann_repo"]
        if "on_back_to_library" in kwargs:
            self.on_back_to_library = kwargs["on_back_to_library"]

        # Engine & reading state
        self.engine = PdfDocumentEngine(self.book.file_path)
        self.total_pages = self.engine.get_page_count()
        self.current_page_idx: int = 0
        self.zoom_mode: str = "width"  # "width", "page", or "custom"
        self.zoom_scale: float = 1.0
        self.auto_save_source_id: Optional[int] = None
        self._updating_ui: bool = False

        self._load_saved_progress()
        self._build_ui()
        self._setup_key_controller()
        self._apply_theme()
        self._update_scale_for_mode()
        self._render_current_page()
        self._update_navigation_ui()
        self._start_autosave_timer()

    def _load_saved_progress(self):
        """Restore reading position from SQLite repository."""
        progress = self.progress_repo.get(self.book.id)
        if progress:
            self.current_page_idx = max(0, min(progress.page_index, max(0, self.total_pages - 1)))
        else:
            self.current_page_idx = 0

    def _build_ui(self):
        """Construct HeaderBar with navigation, zoom controls, and ScrolledWindow canvas."""
        # 1. HeaderBar
        self.header = Adw.HeaderBar()
        self.append(self.header)

        # Back to library button
        self.btn_back = Gtk.Button(icon_name="go-previous-symbolic")
        self.btn_back.set_tooltip_text("Back to Library")
        self.btn_back.connect("clicked", self._on_back_clicked)
        self.header.pack_start(self.btn_back)

        # Page navigation controls container
        nav_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        nav_box.set_margin_start(8)

        self.btn_prev = Gtk.Button(icon_name="pan-start-symbolic")
        self.btn_prev.set_tooltip_text("Previous Page (Left Arrow / Page Up)")
        self.btn_prev.connect("clicked", lambda b: self.prev_page())
        nav_box.append(self.btn_prev)

        # Spin button for direct page jumping (1-indexed for user display)
        max_page = max(1, self.total_pages)
        self.page_spin = Gtk.SpinButton.new_with_range(1, max_page, 1)
        self.page_spin.set_value(self.current_page_idx + 1)
        self.page_spin.set_tooltip_text("Jump to Page Number")
        self.page_spin.connect("value-changed", self._on_spin_value_changed)
        nav_box.append(self.page_spin)

        self.lbl_total_pages = Gtk.Label(label=f" / {self.total_pages}")
        self.lbl_total_pages.add_css_class("dim-label")
        nav_box.append(self.lbl_total_pages)

        self.btn_next = Gtk.Button(icon_name="pan-end-symbolic")
        self.btn_next.set_tooltip_text("Next Page (Right Arrow / Page Down / Space)")
        self.btn_next.connect("clicked", lambda b: self.next_page())
        nav_box.append(self.btn_next)

        self.header.pack_start(nav_box)

        # Window Title in center
        self.title_widget = Adw.WindowTitle(
            title=self.book.title,
            subtitle=f"Page {self.current_page_idx + 1} of {self.total_pages}"
        )
        self.header.set_title_widget(self.title_widget)

        # Zoom controls container (End pack)
        zoom_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)

        self.btn_fit_page = Gtk.Button(label="Fit Page")
        self.btn_fit_page.set_tooltip_text("Fit Entire Page in Viewport")
        self.btn_fit_page.connect("clicked", lambda b: self.fit_to_page())
        zoom_box.append(self.btn_fit_page)

        self.btn_fit_width = Gtk.Button(label="Fit Width")
        self.btn_fit_width.set_tooltip_text("Fit Page Width to Viewport")
        self.btn_fit_width.connect("clicked", lambda b: self.fit_to_width())
        zoom_box.append(self.btn_fit_width)

        self.btn_zoom_out = Gtk.Button(icon_name="zoom-out-symbolic")
        self.btn_zoom_out.set_tooltip_text("Zoom Out (-)")
        self.btn_zoom_out.connect("clicked", lambda b: self.zoom_out())
        zoom_box.append(self.btn_zoom_out)

        self.lbl_zoom = Gtk.Label(label="100%")
        self.lbl_zoom.set_width_chars(5)
        zoom_box.append(self.lbl_zoom)

        self.btn_zoom_in = Gtk.Button(icon_name="zoom-in-symbolic")
        self.btn_zoom_in.set_tooltip_text("Zoom In (+)")
        self.btn_zoom_in.connect("clicked", lambda b: self.zoom_in())
        zoom_box.append(self.btn_zoom_in)

        self.btn_reset_zoom = Gtk.Button(icon_name="zoom-original-symbolic")
        self.btn_reset_zoom.set_tooltip_text("Reset Zoom (100%)")
        self.btn_reset_zoom.connect("clicked", lambda b: self.reset_zoom())
        zoom_box.append(self.btn_reset_zoom)

        self.header.pack_end(zoom_box)

        # 2. ScrolledWindow Canvas
        self.scrolled_window = Gtk.ScrolledWindow()
        self.scrolled_window.set_vexpand(True)
        self.scrolled_window.set_hexpand(True)
        self.scrolled_window.add_css_class("reading-surface")

        # Container centering page horizontally with padding
        self.page_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.page_container.set_halign(Gtk.Align.CENTER)
        self.page_container.set_valign(Gtk.Align.START)
        self.page_container.set_margin_top(16)
        self.page_container.set_margin_bottom(16)
        self.page_container.set_margin_start(16)
        self.page_container.set_margin_end(16)

        self.picture = Gtk.Picture()
        self.picture.set_can_shrink(True)
        self.picture.add_css_class("card")
        self.page_container.append(self.picture)

        self.scrolled_window.set_child(self.page_container)
        self.append(self.scrolled_window)

    def _setup_key_controller(self):
        """Bind keyboard shortcuts for responsive page turning and zoom."""
        controller = Gtk.EventControllerKey()
        controller.connect("key-pressed", self._on_key_pressed)
        self.add_controller(controller)

    def _on_key_pressed(self, controller, keyval, keycode, state) -> bool:
        if keyval in (Gdk.KEY_Right, Gdk.KEY_Page_Down, Gdk.KEY_space):
            return self.next_page()
        elif keyval in (Gdk.KEY_Left, Gdk.KEY_Page_Up):
            return self.prev_page()
        elif keyval == Gdk.KEY_Home:
            self.go_to_page(0)
            return True
        elif keyval == Gdk.KEY_End:
            self.go_to_page(max(0, self.total_pages - 1))
            return True
        elif keyval in (Gdk.KEY_plus, Gdk.KEY_equal):
            self.zoom_in()
            return True
        elif keyval in (Gdk.KEY_minus, Gdk.KEY_underscore):
            self.zoom_out()
            return True
        elif keyval == Gdk.KEY_0:
            self.reset_zoom()
            return True
        return False

    def _get_viewport_dimensions(self) -> tuple[float, float]:
        """Calculates current viewport bounds with fallback for unrealized state."""
        vw = float(self.scrolled_window.get_width())
        vh = float(self.scrolled_window.get_height())
        if vw <= 10.0:
            vw = 800.0
        if vh <= 10.0:
            vh = 600.0
        return (max(100.0, vw - 32.0), max(100.0, vh - 32.0))

    def _update_scale_for_mode(self):
        """Recalculate zoom scale if currently in fit-to-width or fit-to-page mode."""
        if self.zoom_mode in ("width", "page") and self.total_pages > 0:
            vw, vh = self._get_viewport_dimensions()
            self.zoom_scale = self.engine.calculate_fit_scale(
                self.current_page_idx, vw, vh, self.zoom_mode
            )

    def _render_current_page(self):
        """Renders current PDF page at active zoom scale into Gtk.Picture."""
        if self.total_pages == 0:
            return
        try:
            texture = self.engine.render_page_texture(self.current_page_idx, scale=self.zoom_scale)
            self.picture.set_paintable(texture)
        except Exception as e:
            # Defensive logging / non-crashing display
            pass

    def _update_navigation_ui(self):
        """Sync header labels, spin button, and button sensitivity."""
        self._updating_ui = True
        try:
            self.title_widget.set_subtitle(f"Page {self.current_page_idx + 1} of {self.total_pages}")
            self.btn_prev.set_sensitive(self.current_page_idx > 0)
            self.btn_next.set_sensitive(self.current_page_idx < self.total_pages - 1)
            self.page_spin.set_value(self.current_page_idx + 1)
            self.lbl_zoom.set_text(f"{int(round(self.zoom_scale * 100))}%")
        finally:
            self._updating_ui = False

    def _on_spin_value_changed(self, spin: Gtk.SpinButton):
        if self._updating_ui:
            return
        target_page = int(spin.get_value()) - 1
        if target_page != self.current_page_idx:
            self.go_to_page(target_page)

    def next_page(self) -> bool:
        """Advance to next page."""
        if self.current_page_idx < self.total_pages - 1:
            self.go_to_page(self.current_page_idx + 1)
            return True
        return False

    def prev_page(self) -> bool:
        """Move back to previous page."""
        if self.current_page_idx > 0:
            self.go_to_page(self.current_page_idx - 1)
            return True
        return False

    def previous_page(self) -> bool:
        """Alias for prev_page."""
        return self.prev_page()

    def go_to_page(self, page_index: int):
        """Jump directly to the specified 0-indexed page."""
        target = max(0, min(page_index, max(0, self.total_pages - 1)))
        self.current_page_idx = target
        self._update_scale_for_mode()
        self._render_current_page()
        self._update_navigation_ui()
        self._save_checkpoint()

        # Scroll back to the top of the new page
        vadj = self.scrolled_window.get_vadjustment()
        if vadj:
            vadj.set_value(vadj.get_lower())

    def zoom_in(self, step: float = 0.25):
        """Increase zoom scale."""
        self.set_zoom_scale(self.zoom_scale + step)

    def zoom_out(self, step: float = 0.25):
        """Decrease zoom scale."""
        self.set_zoom_scale(self.zoom_scale - step)

    def reset_zoom(self):
        """Reset zoom to 100% (1.0)."""
        self.set_zoom_scale(1.0)

    def fit_to_width(self):
        """Set mode to fit-to-width and update rendering."""
        self.zoom_mode = "width"
        self._update_scale_for_mode()
        self._render_current_page()
        self._update_navigation_ui()

    def fit_to_page(self):
        """Set mode to fit-to-page and update rendering."""
        self.zoom_mode = "page"
        self._update_scale_for_mode()
        self._render_current_page()
        self._update_navigation_ui()

    def set_zoom_scale(self, scale: float):
        """Set explicit zoom scale factor clamped to [0.25, 5.0]."""
        self.zoom_mode = "custom"
        self.zoom_scale = max(0.25, min(5.0, float(scale)))
        self._render_current_page()
        self._update_navigation_ui()

    def _start_autosave_timer(self):
        """NFR-01: 5-second periodic reading progress checkpoint."""
        interval_seconds = 5.0
        if self.settings_repo:
            try:
                settings = self.settings_repo.load()
                if hasattr(settings, "auto_save_interval"):
                    interval_seconds = settings.auto_save_interval
            except Exception:
                pass
        interval_ms = int(interval_seconds * 1000)
        self.auto_save_source_id = GLib.timeout_add(interval_ms, self._on_periodic_autosave)

    def _on_periodic_autosave(self) -> bool:
        self._save_checkpoint()
        return True  # Keep timer running

    def _save_checkpoint(self):
        """Persist current page index and percentage to SQLite WAL database."""
        total = max(1, self.total_pages)
        percentage = round(((self.current_page_idx + 1) / total) * 100.0, 1)
        progress = ReadingProgress(
            book_id=self.book.id,
            chapter_index=0,
            page_index=self.current_page_idx,
            cfi=f"pdf/{self.current_page_idx}",
            percentage=percentage,
            updated_at=time.time()
        )
        self.progress_repo.save(progress)
        self.book_repo.update_last_read(self.book.id)

    def _apply_theme(self):
        """Ensure canvas adheres to active application theme."""
        theme_name = "light"
        if self.settings_repo:
            try:
                settings = self.settings_repo.load()
                if hasattr(settings, "theme") and settings.theme:
                    theme_name = settings.theme
            except Exception:
                pass

        root = self.get_root()
        if root:
            for cls_name in ["aquile-theme-light", "aquile-theme-dark", "aquile-theme-sepia"]:
                root.remove_css_class(cls_name)
            root.add_css_class(f"aquile-theme-{theme_name}")

    def _on_back_clicked(self, button=None):
        """Orderly transition back to library."""
        self.cleanup()
        if self.on_back_to_library:
            self.on_back_to_library()

    def cleanup(self):
        """Orderly view destruction and checkpoint flush (NFR-01)."""
        if self.auto_save_source_id:
            GLib.source_remove(self.auto_save_source_id)
            self.auto_save_source_id = None
        self._save_checkpoint()
        if hasattr(self, "engine") and self.engine:
            self.engine.close()
