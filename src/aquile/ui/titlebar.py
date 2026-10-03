"""WP-B slim custom title bar + translucency helpers (UX_PLAN_V3 D2/D4).

Clean-room implementation: horizontal bar with Gtk.WindowControls on both
sides and a centered title label. Transparency model: percent 0=solid
(opaque) .. 100=fully transparent chrome; alpha = 1 - p/100, clamped.
"""

import gi

gi.require_version('Gtk', '4.0')
from gi.repository import Gtk

DEFAULT_TITLE = "Aquile Reader"


def transparency_to_alpha(percent) -> float:
    """Convert transparency percent (0..100) to opacity alpha (1..0).

    0 -> 1.0 (solid/opaque), 100 -> 0.0 (fully transparent chrome).
    Out-of-range inputs are clamped; non-numeric inputs default to 0.
    """
    try:
        p = float(percent)
    except (TypeError, ValueError):
        p = 0.0
    if p < 0.0:
        p = 0.0
    if p > 100.0:
        p = 100.0
    return 1.0 - (p / 100.0)


def apply_transparency(target, percent) -> float:
    """Apply transparency percent to a widget (or CSS provider target).

    Returns the clamped alpha. Widgets get set_opacity(alpha); anything
    with a set_opacity method is honored; Gtk.CssProvider targets reload a
    minimal opacity snippet (best-effort, never raises).
    """
    alpha = transparency_to_alpha(percent)
    try:
        if isinstance(target, Gtk.Widget):
            target.set_opacity(alpha)
        elif isinstance(target, Gtk.CssProvider):
            try:
                target.load_from_data(f"* {{ opacity: {alpha:.3f}; }}".encode())
            except Exception:
                pass
        else:
            setter = getattr(target, "set_opacity", None)
            if callable(setter):
                setter(alpha)
    except Exception:
        pass
    return alpha


class AquileTitleBar(Gtk.Box):
    """Slim custom title bar: WindowControls (start+end) + centered label."""

    def __init__(self, title: str = DEFAULT_TITLE):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.add_css_class("aquile-titlebar")
        self._title = title if title else DEFAULT_TITLE

        self.controls_start = Gtk.WindowControls.new(Gtk.PackType.START)
        self.append(self.controls_start)

        self.title_label = Gtk.Label()
        self.title_label.set_text(self._title)
        self.title_label.set_hexpand(True)
        self.title_label.set_halign(Gtk.Align.CENTER)
        self.title_label.add_css_class("aquile-title-label")
        self.append(self.title_label)

        self.controls_end = Gtk.WindowControls.new(Gtk.PackType.END)
        self.append(self.controls_end)

    def set_title(self, title: str) -> None:
        self._title = title if title else DEFAULT_TITLE
        self.title_label.set_text(self._title)

    def get_title(self) -> str:
        return self._title


def attach_titlebar(window, titlebar) -> bool:
    """Attach titlebar to window via set_titlebar. Returns True on success."""
    try:
        window.set_titlebar(titlebar)
        return True
    except Exception:
        return False
