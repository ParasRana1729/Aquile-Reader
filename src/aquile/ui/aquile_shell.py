"""Aquile-style app shell: dark left icon rail + content stack.

Clean-room re-implementation of the layout/behavior notes in
``docs/reference/B0/UI_RESEARCH.md`` §1 (App shell):

- Narrow dark icon rail on the left (~56px, ``#3A3A3A``-class) with one
  icon button per top-level destination.
- The selected rail item carries an accent highlight (``.rail-active``);
  the accent defaults to teal ``#009688`` and is theme-settable.
- A content area holds one page widget per destination.

This widget is navigation chrome only: it owns no library, reader, sync,
or settings business logic. Pages are plain widgets registered with
:meth:`add_page`; hosts switch them with :meth:`set_page`.
"""

import re

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, Gtk

from .icon_loader import load as _load_icon, path_for as _icon_path_for

#: Default teal accent seen on the reference Home/rail screenshots.
DEFAULT_ACCENT = "#009688"

#: Rail destinations in display order: (page name, tooltip, icon name).
#: Icons are Adwaita symbolic names; a missing icon degrades to an empty
#: button face rather than an error, so these are presentation hints only.
RAIL_ITEMS = (
    ("home", "Home", "go-home-symbolic"),
    ("library", "Library", "emblem-documents-symbolic"),
    ("collections", "Collections", "document-edit-symbolic"),
    ("catalogs", "Catalogs", "web-browser-symbolic"),
    ("statistics", "Statistics", "utilities-system-monitor-symbolic"),
    ("settings", "Settings", "emblem-system-symbolic"),
)

_RAIL_NAMES = frozenset(name for name, _label, _icon in RAIL_ITEMS)

_HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")


def validate_accent(hex_color: str) -> str:
    """Validate a ``#rrggbb`` accent string, returning it unchanged.

    Raises :exc:`ValueError` for anything else so callers fail fast
    instead of injecting bad CSS.
    """
    if not isinstance(hex_color, str) or not _HEX_COLOR.match(hex_color):
        raise ValueError(f"accent must be a #rrggbb hex string, got {hex_color!r}")
    return hex_color


class AquileShell(Gtk.Box):
    """Horizontal shell: left icon rail + content stack.

    :param on_navigate: optional ``callback(page_name)`` invoked every
        time :meth:`set_page` switches the selected destination.
    """

    def __init__(self, on_navigate=None):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL)
        self.on_navigate = on_navigate
        self._accent = DEFAULT_ACCENT
        self._current = None
        self._pages = {}
        self.rail_buttons = {}
        self._css_provider = Gtk.CssProvider()
        self._build_ui()
        self._current = "home"  # initial selection; no on_navigate yet
        self._highlight("home")

    # -- construction -------------------------------------------------
    def _build_ui(self):
        self.rail = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.rail.add_css_class("aquile-rail")
        self.rail.set_size_request(56, -1)
        for name, tooltip, icon_name in RAIL_ITEMS:
            button = Gtk.Button()
            button.set_tooltip_text(tooltip)
            button.add_css_class("rail-button")
            try:
                button.set_child(_load_icon(name, 24))
            except Exception:
                pass
            try:
                button._aquile_icon_path = _icon_path_for(name)  # noqa: SLF001
            except Exception:
                button._aquile_icon_path = None  # noqa: SLF001
            button.connect("clicked", self._on_rail_clicked, name)
            self.rail.append(button)
            self.rail_buttons[name] = button
        self.append(self.rail)

        self.stack = Gtk.Stack()
        self.stack.set_hexpand(True)
        self.stack.set_vexpand(True)
        self.append(self.stack)

    # -- pages --------------------------------------------------------
    #: Content pages that are not rail destinations (e.g. the active reader).
    AUX_PAGES = frozenset({"reader"})

    def add_page(self, name: str, widget: Gtk.Widget) -> None:
        """Register *widget* as the content for destination *name*.

        Rail destinations plus ``"reader"`` are accepted; anything else
        raises :exc:`KeyError`. Pages are added with their name so
        ``Gtk.Stack.get_visible_child_name()`` keeps working.
        """
        if name not in _RAIL_NAMES and name not in self.AUX_PAGES:
            raise KeyError(f"unknown shell page: {name!r}")
        old = self._pages.get(name)
        if old is not None and old is not widget and old.get_parent() is self.stack:
            self.stack.remove(old)
        self._pages[name] = widget
        if widget.get_parent() is not self.stack:
            self.stack.add_named(widget, name)
        if name == self._current:
            self.stack.set_visible_child_name(name)

    def set_page(self, name: str) -> None:
        """Select destination *name*: highlight rail, swap page, notify."""
        if name not in _RAIL_NAMES and name not in self.AUX_PAGES:
            raise KeyError(f"unknown shell page: {name!r}")
        self._current = name
        self._highlight(name)
        if name in self._pages:
            self.stack.set_visible_child_name(name)
        if self.on_navigate is not None:
            self.on_navigate(name)

    def get_current_page(self):
        """Return the selected destination name (``'home'`` initially)."""
        return self._current

    # -- appearance ---------------------------------------------------
    def set_accent(self, hex_color: str) -> None:
        """Set the theme accent used for the ``.rail-active`` highlight."""
        validate_accent(hex_color)
        self._accent = hex_color
        self._css_provider.load_from_data(
            f".aquile-rail .rail-active {{ background: {hex_color}; }}".encode()
        )
        try:
            display = Gdk.Display.get_default()
            if display is not None:
                Gtk.StyleContext.add_provider_for_display(
                    display,
                    self._css_provider,
                    Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
                )
        except Exception:
            pass  # headless / no display: accent is stored regardless

    def get_accent(self) -> str:
        """Return the current accent ``#rrggbb`` string."""
        return self._accent

    # -- internals ----------------------------------------------------
    def _highlight(self, name: str) -> None:
        for key, button in self.rail_buttons.items():
            if key == name:
                button.add_css_class("rail-active")
            else:
                button.remove_css_class("rail-active")

    def _on_rail_clicked(self, _button, name: str) -> None:
        self.set_page(name)
