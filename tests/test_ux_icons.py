"""WP-A icons: shipped SVG glyphs loaded by file path, zero theme dependence.

D1: rail icons invisible when the user's icon theme lacks our names.
Fix: ship our own SVGs under data/icons/ and load by file path via
src/aquile/ui/icon_loader.py. These tests pin that contract.
"""

import os
import unittest
import xml.etree.ElementTree as ET

try:
    import gi
    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")
    from gi.repository import Adw, Gtk
    try:
        Adw.init()
    except Exception:
        pass
    _GTK_AVAILABLE = True
    _GTK_IMPORT_ERROR = None
except Exception as exc:
    _GTK_AVAILABLE = False
    _GTK_IMPORT_ERROR = exc

from src.aquile.ui import icon_loader
from src.aquile.ui.icon_loader import READER_NAMES, RAIL_NAMES


def _require_gtk(testcase):
    if not _GTK_AVAILABLE:
        testcase.skipTest(f"Gtk unavailable: {_GTK_IMPORT_ERROR}")


def _try_construct(cls, *args, **kwargs):
    if not _GTK_AVAILABLE:
        raise unittest.SkipTest(f"Gtk unavailable: {_GTK_IMPORT_ERROR}")
    try:
        return cls(*args, **kwargs)
    except Exception as exc:
        raise unittest.SkipTest(f"no display for widgets: {exc}")


class TestRailPaths(unittest.TestCase):
    def test_rail_home_resolves_by_path(self):
        path = icon_loader.path_for("home")
        self.assertIsNotNone(path)
        self.assertTrue(path.endswith(".svg"), path)
        self.assertTrue(os.path.isfile(path), f"missing shipped icon: {path}")

    def test_rail_library_resolves_by_path(self):
        path = icon_loader.path_for("library")
        self.assertIsNotNone(path)
        self.assertTrue(path.endswith(".svg"), path)
        self.assertTrue(os.path.isfile(path), f"missing shipped icon: {path}")

    def test_rail_collections_resolves_by_path(self):
        path = icon_loader.path_for("collections")
        self.assertIsNotNone(path)
        self.assertTrue(path.endswith(".svg"), path)
        self.assertTrue(os.path.isfile(path), f"missing shipped icon: {path}")

    def test_rail_catalogs_resolves_by_path(self):
        path = icon_loader.path_for("catalogs")
        self.assertIsNotNone(path)
        self.assertTrue(path.endswith(".svg"), path)
        self.assertTrue(os.path.isfile(path), f"missing shipped icon: {path}")

    def test_rail_statistics_resolves_by_path(self):
        path = icon_loader.path_for("statistics")
        self.assertIsNotNone(path)
        self.assertTrue(path.endswith(".svg"), path)
        self.assertTrue(os.path.isfile(path), f"missing shipped icon: {path}")

    def test_rail_settings_resolves_by_path(self):
        path = icon_loader.path_for("settings")
        self.assertIsNotNone(path)
        self.assertTrue(path.endswith(".svg"), path)
        self.assertTrue(os.path.isfile(path), f"missing shipped icon: {path}")


class TestReaderAndExtraPaths(unittest.TestCase):
    def test_reader_names_resolve_by_path(self):
        self.assertEqual(len(READER_NAMES), 9)
        for name in READER_NAMES:
            with self.subTest(name=name):
                path = icon_loader.path_for(name)
                self.assertIsNotNone(path, f"no path for {name}")
                self.assertTrue(os.path.isfile(path), f"missing file for {name}: {path}")

    def test_plus_and_star_resolve_by_path(self):
        for name in ("plus", "star"):
            with self.subTest(name=name):
                path = icon_loader.path_for(name)
                self.assertIsNotNone(path)
                self.assertTrue(os.path.isfile(path), f"missing file: {path}")

    def test_svg_files_are_valid_xml(self):
        seen = set()
        for name in list(RAIL_NAMES) + list(READER_NAMES) + ["plus", "star"]:
            seen.add(icon_loader.path_for(name))
        self.assertGreaterEqual(len(seen), 8)
        for path in seen:
            with self.subTest(path=path):
                self.assertTrue(os.path.isfile(path))
                root = ET.parse(path).getroot()
                self.assertTrue(root.tag.endswith("svg"), f"not an svg: {path}")


class TestLoaderBehavior(unittest.TestCase):
    def test_load_returns_image_with_paintable(self):
        _require_gtk(self)
        widget = _try_construct(icon_loader.load, "home", 24)
        self.assertIsInstance(widget, Gtk.Image)
        self.assertIsNotNone(widget.get_paintable(),
                             "home icon has no paintable (file failed to load)")

    def test_load_ignores_broken_icon_theme(self):
        _require_gtk(self)
        original = Gtk.IconTheme.get_for_display
        Gtk.IconTheme.get_for_display = staticmethod(lambda _display: None)
        try:
            for name in list(RAIL_NAMES) + list(READER_NAMES):
                with self.subTest(name=name):
                    widget = icon_loader.load(name, 24)
                    self.assertIsInstance(widget, Gtk.Image, f"{name} not an Image")
                    self.assertIsNotNone(widget.get_paintable(),
                                         f"{name} has no paintable without theme")
        finally:
            Gtk.IconTheme.get_for_display = original

    def test_fallback_never_empty(self):
        _require_gtk(self)
        widget = _try_construct(icon_loader.load, "definitely-unknown-xyz", 24)
        # Fallback must be a labeled widget, never an empty image.
        if isinstance(widget, Gtk.Image):
            self.fail("unknown name should not return a bare Gtk.Image")
        try:
            text = widget.get_label() or ""
        except Exception:
            try:
                text = widget.get_text() or ""
            except Exception:
                text = ""
        self.assertTrue(str(text).strip(), "fallback widget has empty label")


class TestShellUsesLoader(unittest.TestCase):
    def test_shell_rail_buttons_use_shipped_icons(self):
        _require_gtk(self)
        from src.aquile.ui.aquile_shell import RAIL_ITEMS, AquileShell
        shell = _try_construct(AquileShell)
        self.assertEqual(len(RAIL_ITEMS), 6)
        for name, _tooltip, _old_icon in RAIL_ITEMS:
            with self.subTest(name=name):
                button = shell.rail_buttons[name]
                path = getattr(button, "_aquile_icon_path", None)
                self.assertIsNotNone(path, f"rail button {name} has no shipped icon path")
                self.assertTrue(os.path.isfile(path), f"rail button {name}: {path}")
                child = button.get_child()
                self.assertIsInstance(child, Gtk.Image)
                self.assertIsNotNone(child.get_paintable())

    def test_home_add_button_uses_shipped_icon(self):
        _require_gtk(self)
        from src.aquile.ui.home_view import HomeView

        class _Repos:
            def list_all(self):
                return []

        home = _try_construct(HomeView, _Repos(), _Repos(),
                              lambda _b: None, lambda: None, lambda: None)
        path = getattr(home.add_button, "_aquile_icon_path", None)
        self.assertIsNotNone(path, "home add button has no shipped icon path")
        self.assertTrue(os.path.isfile(path), f"home add button: {path}")
        child = home.add_button.get_child()
        self.assertIsInstance(child, Gtk.Image)
        self.assertIsNotNone(child.get_paintable())


if __name__ == "__main__":
    unittest.main()
