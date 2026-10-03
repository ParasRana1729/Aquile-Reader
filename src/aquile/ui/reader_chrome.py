"""
Aquile-style reader chrome (clean-room re-implementation).

Covers UI_RESEARCH.md section 4 "Reader": dark top toolbar with white icons
(back, menu, TOC, bookmark left; search, read-aloud, text-settings, dictionary,
fullscreen right), footer status bar (left ``Chapter » Section``, center
``page/total``, right ``N.NN%``), and the dark display-settings popover
(text size, font style, 6 page themes, 3 page layouts, reset).

Only persists through the existing ``AppSettings`` fields
(theme/font_family/font_size/columns); the model itself is not changed.
New theme keys (white/silver/sepia/night/solarized/custom) are plain strings
and round-trip through the generic settings key/value store.
"""

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from typing import Callable, Dict, List, Optional

from ..domain.models import (
    ACCENT_THEMES,
    PAGE_THEME_LABELS,
    PAGE_THEMES,
    AppSettings,
    validate_accent_name,
    validate_page_theme,
)

# ---------------------------------------------------------------------------
# Shared choice tables (importable by tests/callers).
#
# WP-C: the page/accent theme vocabulary lives in ``domain.models`` (single
# source of truth); this module re-exports it so existing import sites keep
# working.
# ---------------------------------------------------------------------------

__all__ = [
    "FONT_CHOICES",
    "PAGE_THEMES",
    "PAGE_THEME_LABELS",
    "ACCENT_THEMES",
    "LAYOUT_COLUMNS",
    "LAYOUT_LABELS",
    "LAYOUT_TOOLTIPS",
    "FONT_SIZE_MIN",
    "FONT_SIZE_MAX",
    "ReaderToolbar",
    "ReaderStatusBar",
    "ReaderDisplayPopover",
]

#: Font families offered by the display popover (matches SettingsDialog list).
FONT_CHOICES: List[str] = [
    "Sans",
    "Serif",
    "Monospace",
    "Cantarell",
    "Noto Serif",
    "Liberation Serif",
]

# NOTE: PAGE_THEMES / PAGE_THEME_LABELS / ACCENT_THEMES are imported from
# domain.models above (single source of truth, WP-C).

#: Column counts persisted to ``AppSettings.columns`` (3 == book-spread).
LAYOUT_COLUMNS: List[int] = [1, 2, 3]
LAYOUT_LABELS: Dict[int, str] = {1: "Single", 2: "Two-column", 3: "Spread"}
LAYOUT_TOOLTIPS: Dict[int, str] = {
    1: "Single column",
    2: "Two columns",
    3: "Book spread",
}

FONT_SIZE_MIN = 12
FONT_SIZE_MAX = 32

#: Alternate callback-dict keys accepted for each toolbar button.
_CALLBACK_ALIASES: Dict[str, tuple] = {
    "back": ("back", "go_back"),
    "menu": ("menu",),
    "toc": ("toc", "contents", "table_of_contents"),
    "bookmark": ("bookmark", "add_bookmark"),
    "search": ("search", "find"),
    "read_aloud": ("read_aloud", "read-aloud", "readaloud", "tts"),
    "display_settings": (
        "display_settings",
        "display-settings",
        "text_settings",
        "text-settings",
        "settings",
    ),
    "dictionary": ("dictionary", "translate", "lookup"),
    "fullscreen": ("fullscreen", "full_screen", "full-screen"),
}


class ReaderToolbar(Gtk.Box):
    """Dark Aquile-style reader toolbar.

    Left: back, menu, TOC, bookmark. Right: search, read-aloud,
    text-settings (tT), dictionary, fullscreen.

    ``callbacks`` maps button names (``back``, ``menu``, ``toc``,
    ``bookmark``, ``search``, ``read_aloud``, ``display_settings``,
    ``dictionary``, ``fullscreen``) to callables. Each callback is
    invoked as ``cb(button)``; zero-argument callables are also accepted.
    Missing entries are no-ops.
    """

    LEFT_SPECS = (
        ("back", "go-previous-symbolic", "Back"),
        ("menu", "open-menu-symbolic", "Menu"),
        ("toc", "view-list-bullet-symbolic", "Table of Contents"),
        ("bookmark", "bookmark-new-symbolic", "Bookmark"),
    )
    RIGHT_SPECS = (
        ("search", "system-search-symbolic", "Search"),
        ("read_aloud", "audio-speakers-symbolic", "Read aloud"),
        ("display_settings", "font-x-generic-symbolic", "Text settings (tT)"),
        ("dictionary", "accessories-dictionary-symbolic", "Dictionary"),
        ("fullscreen", "view-fullscreen-symbolic", "Fullscreen"),
    )

    def __init__(self, callbacks: Optional[Dict[str, Callable]] = None) -> None:
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.add_css_class("reader-toolbar")
        self.callbacks: Dict[str, Callable] = dict(callbacks) if callbacks else {}

        self.left_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self.append(self.left_box)

        spacer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        spacer.set_hexpand(True)
        self.append(spacer)

        self.right_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self.append(self.right_box)

        self.buttons: Dict[str, Gtk.Button] = {}
        self.left_buttons: List[Gtk.Button] = []
        self.right_buttons: List[Gtk.Button] = []
        self.left_names: List[str] = []
        self.right_names: List[str] = []

        for name, icon, tooltip in self.LEFT_SPECS:
            btn = self._make_button(name, icon, tooltip)
            self.left_box.append(btn)
            self.left_buttons.append(btn)
            self.left_names.append(name)
        for name, icon, tooltip in self.RIGHT_SPECS:
            btn = self._make_button(name, icon, tooltip)
            self.right_box.append(btn)
            self.right_buttons.append(btn)
            self.right_names.append(name)

    # -- construction helpers ------------------------------------------------

    def _make_button(self, name: str, icon: str, tooltip: str) -> Gtk.Button:
        btn = Gtk.Button(icon_name=icon)
        btn.set_tooltip_text(tooltip)
        btn.connect("clicked", self._on_button_clicked, name)
        self.buttons[name] = btn
        return btn

    def _on_button_clicked(self, button: Gtk.Button, name: str) -> None:
        callback = None
        for alias in _CALLBACK_ALIASES.get(name, (name,)):
            candidate = self.callbacks.get(alias)
            if callable(candidate):
                callback = candidate
                break
        if callback is None:
            return
        try:
            callback(button)
        except TypeError:
            callback()

    # -- public API (for tests/callers) --------------------------------------

    def get_button(self, name: str) -> Optional[Gtk.Button]:
        """Returns the toolbar button for ``name``, or None."""
        return self.buttons.get(name)

    def button_count(self) -> int:
        """Total number of toolbar buttons (4 left + 5 right)."""
        return len(self.left_buttons) + len(self.right_buttons)


class ReaderStatusBar(Gtk.Box):
    """Footer status bar: left ``Chapter » Section``, center ``page/total``."""

    def __init__(self) -> None:
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.add_css_class("reader-statusbar")

        self.location_label = Gtk.Label(label="Chapter 1 » Section 1")
        self.location_label.set_halign(Gtk.Align.START)
        self.location_label.set_hexpand(True)
        self.location_label.set_ellipsize(True)
        self.append(self.location_label)

        self.page_label = Gtk.Label(label="1/1")
        self.page_label.set_halign(Gtk.Align.CENTER)
        self.append(self.page_label)

        self.percent_label = Gtk.Label(label="0.00%")
        self.percent_label.set_halign(Gtk.Align.END)
        self.append(self.percent_label)

    # -- setters ---------------------------------------------------------------

    def set_location(self, chapter: str, section: str) -> str:
        """Sets the left label; returns the rendered text."""
        chapter = str(chapter or "")
        section = str(section or "")
        text = f"{chapter} » {section}" if section else chapter
        self.location_label.set_label(text)
        return text

    def set_page(self, cur: int, total: int) -> str:
        """Sets the center label as ``cur/total``; returns the text."""
        text = f"{int(cur)}/{int(total)}"
        self.page_label.set_label(text)
        return text

    def set_percent(self, value: float) -> str:
        """Sets the right label as ``N.NN%``; returns the text."""
        text = f"{float(value):.2f}%"
        self.percent_label.set_label(text)
        return text

    # -- getters ---------------------------------------------------------------

    def get_location_text(self) -> str:
        return str(self.location_label.get_label())

    def get_page_text(self) -> str:
        return str(self.page_label.get_label())

    def get_percent_text(self) -> str:
        return str(self.percent_label.get_label())


class ReaderDisplayPopover(Gtk.Popover):
    """Dark display-settings popover bound to ``AppSettings``.

    Text-size slider (12-32) <-> ``settings.font_size``; font-style
    dropdown <-> ``settings.font_family``; 6 theme buttons <->
    ``settings.theme``; 3 layout buttons <-> ``settings.columns``
    (3 == book-spread). Every change persists via ``settings_repo.save``
    and invokes ``on_changed(settings)``.
    """

    def __init__(
        self,
        settings: AppSettings,
        settings_repo,
        on_changed: Optional[Callable[[AppSettings], None]] = None,
        on_changed_callback: Optional[Callable[[AppSettings], None]] = None,
    ) -> None:
        super().__init__()
        self.add_css_class("reader-display-popover")

        self.settings = settings
        self.settings_repo = settings_repo
        self.on_changed = on_changed if on_changed is not None else on_changed_callback
        self._syncing = False

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        root.set_margin_start(16)
        root.set_margin_end(16)
        root.set_margin_top(16)
        root.set_margin_bottom(16)
        self.set_child(root)

        # -- text size: A- slider A+ --------------------------------------
        size_title = Gtk.Label(label="Text size")
        size_title.set_halign(Gtk.Align.START)
        root.append(size_title)

        size_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        root.append(size_row)

        self.size_dec_button = Gtk.Button(label="A-")
        self.size_dec_button.set_tooltip_text("Decrease text size")
        self.size_dec_button.connect("clicked", self._on_size_step, -1)
        size_row.append(self.size_dec_button)

        self.font_size_scale = Gtk.Scale.new_with_range(
            Gtk.Orientation.HORIZONTAL, FONT_SIZE_MIN, FONT_SIZE_MAX, 1
        )
        self.font_size_scale.set_value(float(self.settings.font_size))
        self.font_size_scale.set_draw_value(True)
        self.font_size_scale.set_hexpand(True)
        self.font_size_scale.set_tooltip_text("Text size")
        size_row.append(self.font_size_scale)

        self.size_inc_button = Gtk.Button(label="A+")
        self.size_inc_button.set_tooltip_text("Increase text size")
        self.size_inc_button.connect("clicked", self._on_size_step, 1)
        size_row.append(self.size_inc_button)

        self.font_size_scale.connect("value-changed", self._on_font_size_changed)

        # -- font style ------------------------------------------------------
        font_title = Gtk.Label(label="Font style")
        font_title.set_halign(Gtk.Align.START)
        root.append(font_title)

        self.font_dropdown = Gtk.DropDown.new_from_strings(FONT_CHOICES)
        self.font_dropdown.set_selected(self._font_index(self.settings.font_family))
        self.font_dropdown.set_tooltip_text("Font style")
        root.append(self.font_dropdown)
        self.font_dropdown.connect("notify::selected", self._on_font_changed)

        # -- page themes (6 buttons) -----------------------------------------
        theme_title = Gtk.Label(label="Page themes")
        theme_title.set_halign(Gtk.Align.START)
        root.append(theme_title)

        theme_grid = Gtk.Grid(column_spacing=8, row_spacing=8)
        root.append(theme_grid)
        self.theme_buttons: Dict[str, Gtk.ToggleButton] = {}
        for i, key in enumerate(PAGE_THEMES):
            btn = Gtk.ToggleButton(label=PAGE_THEME_LABELS[i])
            btn.set_tooltip_text(f"{PAGE_THEME_LABELS[i]} theme")
            btn.set_active(self.settings.theme == key)
            btn.connect("toggled", self._on_theme_toggled, key)
            self.theme_buttons[key] = btn
            theme_grid.attach(btn, i % 3, i // 3, 1, 1)

        # -- page layout (3 buttons) -------------------------------------------
        layout_title = Gtk.Label(label="Page layout")
        layout_title.set_halign(Gtk.Align.START)
        root.append(layout_title)

        layout_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        root.append(layout_row)
        self.layout_buttons: Dict[int, Gtk.ToggleButton] = {}
        for count in LAYOUT_COLUMNS:
            btn = Gtk.ToggleButton(label=LAYOUT_LABELS[count])
            btn.set_tooltip_text(LAYOUT_TOOLTIPS[count])
            btn.set_active(self.settings.columns == count)
            btn.connect("toggled", self._on_layout_toggled, count)
            self.layout_buttons[count] = btn
            layout_row.append(btn)

        # -- reset ---------------------------------------------------------------
        self.reset_button = Gtk.Button.new_from_icon_name("view-refresh-symbolic")
        self.reset_button.set_label("Reset")
        self.reset_button.set_tooltip_text("Reset to defaults")
        self.reset_button.connect("clicked", self.reset_to_defaults)
        root.append(self.reset_button)

    # -- internal helpers --------------------------------------------------------

    @staticmethod
    def _font_index(family: str) -> int:
        try:
            return FONT_CHOICES.index(str(family))
        except ValueError:
            return 0

    def _persist(self) -> None:
        if self.settings_repo is not None:
            self.settings_repo.save(self.settings)
        if self.on_changed is not None:
            self.on_changed(self.settings)

    def _refresh_widgets(self) -> None:
        """Syncs widget states from ``self.settings`` without persisting."""
        self._syncing = True
        try:
            self.font_size_scale.set_value(float(self.settings.font_size))
            self.font_dropdown.set_selected(self._font_index(self.settings.font_family))
            for key, btn in self.theme_buttons.items():
                btn.set_active(self.settings.theme == key)
            for count, btn in self.layout_buttons.items():
                btn.set_active(self.settings.columns == count)
        finally:
            self._syncing = False

    # -- signal handlers -----------------------------------------------------------

    def _on_size_step(self, _button: Gtk.Button, delta: int) -> None:
        try:
            current = int(self.font_size_scale.get_value())
        except Exception:
            current = int(self.settings.font_size)
        clamped = max(FONT_SIZE_MIN, min(FONT_SIZE_MAX, current + int(delta)))
        self.font_size_scale.set_value(float(clamped))

    def _on_font_size_changed(self, scale: Gtk.Scale) -> None:
        if self._syncing:
            return
        try:
            value = int(scale.get_value())
        except Exception:
            return
        value = max(FONT_SIZE_MIN, min(FONT_SIZE_MAX, value))
        self.settings.font_size = value
        self._persist()

    def _on_font_changed(self, dropdown: Gtk.DropDown, _pspec) -> None:
        if self._syncing:
            return
        try:
            index = int(dropdown.get_selected())
        except Exception:
            return
        if 0 <= index < len(FONT_CHOICES):
            self.settings.font_family = FONT_CHOICES[index]
            self._persist()

    def _on_theme_toggled(self, button: Gtk.ToggleButton, key: str) -> None:
        if self._syncing:
            return
        if button.get_active():
            self._syncing = True
            try:
                for other_key, other in self.theme_buttons.items():
                    if other_key != key and other.get_active():
                        other.set_active(False)
            finally:
                self._syncing = False
            self.settings.theme = key
            self._persist()
        elif self.settings.theme == key:
            # Keep exactly one theme selected: bounce back.
            self._syncing = True
            try:
                button.set_active(True)
            finally:
                self._syncing = False

    def _on_layout_toggled(self, button: Gtk.ToggleButton, count: int) -> None:
        if self._syncing:
            return
        if button.get_active():
            self._syncing = True
            try:
                for other_count, other in self.layout_buttons.items():
                    if other_count != count and other.get_active():
                        other.set_active(False)
            finally:
                self._syncing = False
            self.settings.columns = int(count)
            self._persist()
        elif self.settings.columns == int(count):
            self._syncing = True
            try:
                button.set_active(True)
            finally:
                self._syncing = False

    # -- public API ------------------------------------------------------------------

    def get_font_size(self) -> int:
        try:
            return int(self.font_size_scale.get_value())
        except Exception:
            return int(self.settings.font_size)

    def set_font_size(self, value: int) -> int:
        """Sets the text size (clamped 12-32), persisting the change."""
        clamped = max(FONT_SIZE_MIN, min(FONT_SIZE_MAX, int(value)))
        self.settings.font_size = clamped
        self._refresh_widgets()
        self._persist()
        return clamped

    def get_font_family(self) -> str:
        try:
            index = int(self.font_dropdown.get_selected())
            if 0 <= index < len(FONT_CHOICES):
                return FONT_CHOICES[index]
        except Exception:
            pass
        return str(self.settings.font_family)

    def set_font_family(self, family: str) -> str:
        """Sets the font family (must be in ``FONT_CHOICES``)."""
        if str(family) not in FONT_CHOICES:
            raise ValueError(f"unknown font family: {family!r}")
        self.settings.font_family = str(family)
        self._refresh_widgets()
        self._persist()
        return self.settings.font_family

    def get_theme(self) -> str:
        return str(self.settings.theme)

    def set_theme(self, key: str) -> str:
        """Selects a page theme (one of ``PAGE_THEMES``), persisting it."""
        self.settings.theme = validate_page_theme(key)
        self._refresh_widgets()
        self._persist()
        return self.settings.theme

    def get_accent(self) -> str:
        """Returns the accent-theme name (one of ``ACCENT_THEMES``)."""
        return str(getattr(self.settings, "accent", "turquoise"))

    def set_accent(self, name: str) -> str:
        """Selects an accent theme (one of ``ACCENT_THEMES``), persisting it."""
        self.settings.accent = validate_accent_name(name)
        self._persist()
        return self.settings.accent

    def get_columns(self) -> int:
        return int(self.settings.columns)

    def set_layout(self, count: int) -> int:
        """Selects a column layout (1/2/3, 3 == book-spread), persisting it."""
        if int(count) not in LAYOUT_COLUMNS:
            raise ValueError(f"unknown layout columns: {count!r}")
        self.settings.columns = int(count)
        self._refresh_widgets()
        self._persist()
        return self.settings.columns

    def reset_to_defaults(self, _button=None) -> AppSettings:
        """Restores ``AppSettings`` defaults, persisting and notifying."""
        self.settings = AppSettings()
        if self.settings_repo is not None:
            self.settings_repo.save(self.settings)
        self._refresh_widgets()
        if self.on_changed is not None:
            self.on_changed(self.settings)
        return self.settings
