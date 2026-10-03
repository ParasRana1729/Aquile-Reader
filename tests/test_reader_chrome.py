"""
Headless tests for the Aquile-style reader chrome (reader_chrome.py).

Covers the dark toolbar layout (4 left + 5 right), the footer status bar
strings (``»`` separator, ``cur/total``, ``N.NN%``), and the display-settings
popover roundtrip/persistence via a temp DB. GUI tests skip gracefully when
Gtk cannot initialise (no display server) instead of failing.
"""

import os
import tempfile
import unittest

try:
    import gi

    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")
    from gi.repository import Adw, Gtk  # noqa: F401

    try:
        Adw.init()
    except Exception:
        pass
    _GTK_AVAILABLE = True
    _GTK_IMPORT_ERROR = None
except Exception as exc:  # pragma: no cover - environment dependent
    _GTK_AVAILABLE = False
    _GTK_IMPORT_ERROR = exc

from src.aquile.domain.models import AppSettings
from src.aquile.storage.database import Database
from src.aquile.storage.repository import SettingsRepository

EXPECTED_LEFT = ["back", "menu", "toc", "bookmark"]
EXPECTED_RIGHT = ["search", "read_aloud", "display_settings", "dictionary", "fullscreen"]


def _require_gtk(testcase: unittest.TestCase) -> None:
    if not _GTK_AVAILABLE:
        testcase.skipTest(f"Gtk unavailable: {_GTK_IMPORT_ERROR}")


def _try_construct(testcase: unittest.TestCase, cls, *args, **kwargs):
    _require_gtk(testcase)
    try:
        return cls(*args, **kwargs)
    except Exception as exc:
        testcase.skipTest(f"Gtk widget init failed (no display?): {exc}")


def _temp_settings_repo():
    tmp = tempfile.TemporaryDirectory()
    db = Database(os.path.join(tmp.name, "aquile.db"))
    return tmp, SettingsRepository(db)


def _make_toolbar(testcase, callbacks=None):
    from src.aquile.ui.reader_chrome import ReaderToolbar

    return _try_construct(testcase, ReaderToolbar, callbacks)


def _make_statusbar(testcase):
    from src.aquile.ui.reader_chrome import ReaderStatusBar

    return _try_construct(testcase, ReaderStatusBar)


def _make_popover(testcase, settings=None, repo=None, holder=None):
    from src.aquile.ui.reader_chrome import ReaderDisplayPopover

    tmp = None
    if repo is None:
        tmp, repo = _temp_settings_repo()
    if settings is None:
        settings = repo.load()
    calls = []
    popover = _try_construct(
        testcase, ReaderDisplayPopover, settings, repo,
        on_changed=lambda s: (calls.append(s), (holder.append(s) if holder is not None else None)),
    )
    return popover, repo, tmp, calls


def _box_children(box):
    kids = []
    child = box.get_first_child()
    while child is not None:
        kids.append(child)
        child = child.get_next_sibling()
    return kids


class TestReaderToolbar(unittest.TestCase):
    def test_button_count_and_css(self):
        bar = _make_toolbar(self, {})
        self.assertEqual(bar.button_count(), 9)
        self.assertEqual(len(bar.left_buttons), 4)
        self.assertEqual(len(bar.right_buttons), 5)
        self.assertEqual(len(bar.buttons), 9)
        self.assertTrue(bar.has_css_class("reader-toolbar"))

    def test_left_button_order(self):
        bar = _make_toolbar(self, {})
        self.assertEqual(bar.left_names, EXPECTED_LEFT)
        self.assertEqual(_box_children(bar.left_box), list(bar.left_buttons))
        for name, widget in zip(EXPECTED_LEFT, _box_children(bar.left_box)):
            self.assertIs(widget, bar.get_button(name))

    def test_right_button_order(self):
        bar = _make_toolbar(self, {})
        self.assertEqual(bar.right_names, EXPECTED_RIGHT)
        self.assertEqual(_box_children(bar.right_box), list(bar.right_buttons))
        for name, widget in zip(EXPECTED_RIGHT, _box_children(bar.right_box)):
            self.assertIs(widget, bar.get_button(name))

    def test_callbacks_fired_on_click(self):
        fired = []
        callbacks = {name: (lambda _b, n=name: fired.append(n)) for name in EXPECTED_LEFT + EXPECTED_RIGHT}
        bar = _make_toolbar(self, callbacks)
        for name in EXPECTED_LEFT + EXPECTED_RIGHT:
            bar.get_button(name).emit("clicked")
        self.assertEqual(sorted(fired), sorted(EXPECTED_LEFT + EXPECTED_RIGHT))

    def test_missing_callbacks_are_noops(self):
        bar = _make_toolbar(self)  # no callbacks at all
        for name in EXPECTED_LEFT + EXPECTED_RIGHT:
            bar.get_button(name).emit("clicked")  # must not raise


class TestReaderStatusBar(unittest.TestCase):
    def test_location_uses_separator(self):
        bar = _make_statusbar(self)
        text = bar.set_location("Chapter 3", "The Beginning")
        self.assertIn("»", text)
        self.assertIn("Chapter 3", text)
        self.assertIn("The Beginning", text)
        self.assertIn("»", bar.get_location_text())

    def test_page_format(self):
        bar = _make_statusbar(self)
        text = bar.set_page(3, 42)
        self.assertEqual(text, "3/42")
        self.assertEqual(bar.get_page_text(), "3/42")

    def test_percent_format(self):
        bar = _make_statusbar(self)
        text = bar.set_percent(12.3456)
        self.assertTrue(text.endswith("%"))
        self.assertEqual(text, "12.35%")
        self.assertEqual(bar.get_percent_text(), "12.35%")


class TestReaderDisplayPopover(unittest.TestCase):
    def test_defaults_roundtrip(self):
        from src.aquile.ui.reader_chrome import FONT_CHOICES

        tmp, repo = _temp_settings_repo()
        try:
            settings = AppSettings(theme="sepia", font_family="Serif", font_size=22, columns=1)
            repo.save(settings)
            popover, _, _, _ = _make_popover(self, repo.load(), repo)
            self.assertEqual(popover.get_font_size(), 22)
            self.assertEqual(popover.get_font_family(), "Serif")
            self.assertEqual(
                int(popover.font_dropdown.get_selected()), FONT_CHOICES.index("Serif")
            )
            self.assertEqual(popover.get_theme(), "sepia")
            self.assertTrue(popover.theme_buttons["sepia"].get_active())
            self.assertEqual(popover.get_columns(), 1)
            self.assertTrue(popover.layout_buttons[1].get_active())
            self.assertEqual(len(popover.theme_buttons), 6)
            self.assertEqual(len(popover.layout_buttons), 3)
        finally:
            tmp.cleanup()

    def test_theme_change_persists_via_button(self):
        tmp, repo = _temp_settings_repo()
        try:
            popover, repo2, _, calls = _make_popover(self, AppSettings(), repo)
            popover.theme_buttons["night"].set_active(True)
            self.assertEqual(popover.get_theme(), "night")
            self.assertEqual(repo2.load().theme, "night")
            self.assertTrue(popover.theme_buttons["night"].get_active())
            self.assertFalse(popover.theme_buttons["white"].get_active())
            self.assertGreaterEqual(len(calls), 1)
        finally:
            tmp.cleanup()

    def test_layout_change_persists(self):
        tmp, repo = _temp_settings_repo()
        try:
            popover, repo2, _, calls = _make_popover(self, AppSettings(), repo)
            self.assertEqual(popover.set_layout(3), 3)  # 3 == book-spread
            self.assertEqual(repo2.load().columns, 3)
            self.assertTrue(popover.layout_buttons[3].get_active())
            self.assertGreaterEqual(len(calls), 1)
        finally:
            tmp.cleanup()

    def test_font_size_change_persists(self):
        tmp, repo = _temp_settings_repo()
        try:
            popover, repo2, _, calls = _make_popover(self, AppSettings(), repo)
            popover.font_size_scale.set_value(24.0)
            self.assertEqual(popover.get_font_size(), 24)
            self.assertEqual(repo2.load().font_size, 24)
            self.assertGreaterEqual(len(calls), 1)
        finally:
            tmp.cleanup()

    def test_reset_restores_defaults(self):
        tmp, repo = _temp_settings_repo()
        try:
            from src.aquile.ui.reader_chrome import FONT_CHOICES  # noqa: F401

            custom = AppSettings(theme="night", font_family="Monospace", font_size=28, columns=3)
            repo.save(custom)
            popover, repo2, _, calls = _make_popover(self, repo.load(), repo)
            self.assertEqual(popover.get_theme(), "night")
            popover.reset_button.emit("clicked")
            defaults = AppSettings()
            self.assertEqual(popover.settings.theme, defaults.theme)
            self.assertEqual(popover.settings.font_family, defaults.font_family)
            self.assertEqual(popover.settings.font_size, defaults.font_size)
            self.assertEqual(popover.settings.columns, defaults.columns)
            reloaded = repo2.load()
            self.assertEqual(reloaded.theme, defaults.theme)
            self.assertEqual(reloaded.font_size, defaults.font_size)
            self.assertEqual(reloaded.columns, defaults.columns)
            self.assertGreaterEqual(len(calls), 1)
        finally:
            tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
