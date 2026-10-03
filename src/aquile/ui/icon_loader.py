"""Shipped icon glyphs loaded by file path (WP-A / D1).

The user's icon theme may lack our symbolic names, which rendered rail
slots empty. These glyphs live under ``data/icons/*.svg`` and are loaded
by absolute file path, with zero dependence on ``Gtk.IconTheme``.

Logical names (rail + reader + extras) map onto the 8 shipped files;
reader names reuse the closest file as a placeholder so every name
resolves to a real file. Unknown names fall back to a labeled widget,
never an empty face.
"""

import os

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

_HERE = os.path.dirname(os.path.abspath(__file__))

#: Candidate directories holding the shipped ``*.svg`` glyphs, first hit wins:
#: repo checkout, system install, /usr/local install, tarball/AppImage layout,
#: plus $AQUILE_ICON_DIR override for tests and custom installs.
_CANDIDATES = [
    os.environ.get("AQUILE_ICON_DIR", ""),
    os.path.normpath(os.path.join(_HERE, "..", "..", "..", "data", "icons")),
    "/usr/share/aquile-reader/data/icons",
    "/usr/local/share/aquile-reader/data/icons",
    os.path.normpath(os.path.join(_HERE, "..", "..", "data", "icons")),
]


def find_icon_dir() -> str:
    """Return the first candidate icon directory that exists."""
    for candidate in _CANDIDATES:
        if candidate and os.path.isdir(candidate):
            return candidate
    return _CANDIDATES[1]


#: Absolute directory holding the shipped ``*.svg`` glyphs.
ICON_DIR = find_icon_dir()

#: Rail destinations in display order.
RAIL_NAMES = ("home", "library", "collections", "catalogs", "statistics", "settings")

#: Reader toolbar names (left 4 + right 5).
READER_NAMES = ("back", "menu", "toc", "bookmark", "search",
                "read_aloud", "display_settings", "dictionary", "fullscreen")

#: Logical name -> shipped SVG filename. Reader names reuse shipped files.
NAMES = {
    "home": "home.svg",
    "library": "library.svg",
    "collections": "collections.svg",
    "catalogs": "globe.svg",
    "statistics": "chart.svg",
    "settings": "gear.svg",
    "plus": "plus.svg",
    "add": "plus.svg",
    "star": "star.svg",
    "favorite": "star.svg",
    # Reader toolbar glyphs (white strokes for the dark reader toolbar).
    "back": "back.svg",
    "menu": "menu.svg",
    "toc": "toc.svg",
    "bookmark": "bookmark.svg",
    "search": "search.svg",
    "read_aloud": "speaker.svg",
    "display_settings": "textsize.svg",
    "dictionary": "dictionary.svg",
    "fullscreen": "fullscreen.svg",
}


def path_for(name: str):
    """Return the absolute SVG path for *name*, or None if unknown."""
    filename = NAMES.get(str(name or ""))
    if not filename:
        return None
    return os.path.join(ICON_DIR, filename)


#: Back-compat alias used by callers/tests.
def icon_path(name: str):
    """Alias for :func:`path_for`."""
    return path_for(name)


def load(name: str, size_px: int = 24) -> Gtk.Widget:
    """Load *name* as a ``Gtk.Image`` from its shipped SVG file.

    Never touches ``Gtk.IconTheme``. Unknown names or missing files
    fall back to a ``Gtk.Label`` carrying the name, so callers never
    render an empty face.
    """
    path = path_for(name)
    if path and os.path.isfile(path):
        try:
            image = Gtk.Image.new_from_file(path)
            try:
                image.set_pixel_size(int(size_px))
            except Exception:
                pass
            return image
        except Exception:
            pass
    label = Gtk.Label(label=str(name or "?"))
    try:
        label.set_tooltip_text(str(name or ""))
    except Exception:
        pass
    return label
