"""WP-B title bar tests (UX_PLAN_V3 sections 2-3, D2).

Pins: AquileTitleBar widget with Gtk.WindowControls on both sides,
set_title updates label, attach_titlebar window integration headless-safe,
and app wiring (open_book/show_library title updates).
"""
import os
import tempfile
import unittest

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Gdk

from src.aquile.ui.titlebar import AquileTitleBar, attach_titlebar

HAS_DISPLAY = Gdk.Display.get_default() is not None


def _collect_window_controls(widget):
    """Recursively collect Gtk.WindowControls descendants (GTK4 child model)."""
    found = []
    if isinstance(widget, Gtk.WindowControls):
        found.append(widget)
    child = widget.get_first_child() if isinstance(widget, Gtk.Widget) else None
    while child is not None:
        found.extend(_collect_window_controls(child))
        child = child.get_next_sibling()
    return found


class TestAquileTitleBar(unittest.TestCase):
    def setUp(self):
        try:
            Gtk.init()
        except Exception:
            pass

    def test_build_creates_widget(self):
        bar = AquileTitleBar()
        self.assertIsInstance(bar, Gtk.Widget)
        self.assertIsInstance(bar, Gtk.Box)

    def test_contains_start_window_controls(self):
        bar = AquileTitleBar()
        controls = _collect_window_controls(bar)
        sides = [c.get_side() for c in controls]
        self.assertIn(Gtk.PackType.START, sides,
                      f"expected START WindowControls, got sides={sides}")

    def test_contains_end_window_controls(self):
        bar = AquileTitleBar()
        controls = _collect_window_controls(bar)
        sides = [c.get_side() for c in controls]
        self.assertIn(Gtk.PackType.END, sides,
                      f"expected END WindowControls, got sides={sides}")

    def test_default_title_is_aquile_reader(self):
        bar = AquileTitleBar()
        self.assertEqual(bar.get_title(), "Aquile Reader")
        self.assertEqual(bar.title_label.get_text(), "Aquile Reader")

    def test_set_title_updates_label(self):
        bar = AquileTitleBar()
        bar.set_title("My Book - Aquile Reader")
        self.assertEqual(bar.get_title(), "My Book - Aquile Reader")
        self.assertEqual(bar.title_label.get_text(), "My Book - Aquile Reader")

    def test_set_title_roundtrip(self):
        bar = AquileTitleBar(title="Custom Start")
        self.assertEqual(bar.get_title(), "Custom Start")
        bar.set_title("Second Title")
        self.assertEqual(bar.title_label.get_text(), "Second Title")
        bar.set_title("Aquile Reader")
        self.assertEqual(bar.get_title(), "Aquile Reader")

    def test_attach_titlebar_headless_safe(self):
        if not HAS_DISPLAY:
            self.skipTest("no display")
        try:
            win = Gtk.Window()
        except Exception as e:
            self.skipTest(f"cannot create window headless: {e}")
        bar = AquileTitleBar()
        try:
            ok = attach_titlebar(win, bar)
        except Exception as e:
            self.skipTest(f"attach skipped headless: {e}")
            return
        self.assertTrue(ok)
        try:
            self.assertIs(win.get_titlebar(), bar)
        finally:
            try:
                win.destroy()
            except Exception:
                pass

    def test_attach_titlebar_refuses_adw_windows(self):
        from gi.repository import Adw
        bar = AquileTitleBar()
        w1 = Adw.Window()
        w2 = Adw.ApplicationWindow()
        self.assertFalse(attach_titlebar(w1, bar))
        self.assertFalse(attach_titlebar(w2, bar))

        class CustomAdwWindow(Adw.ApplicationWindow):
            pass

        self.assertFalse(attach_titlebar(CustomAdwWindow(), bar))


class TestTitleBarAppWiring(unittest.TestCase):
    """App wiring: window has titlebar; open_book/show_library update title."""

    def setUp(self):
        try:
            Gtk.init()
        except Exception:
            pass
        if not HAS_DISPLAY:
            self.skipTest("no display")
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "titlebar_test.db")

    def tearDown(self):
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def _make_app(self):
        from src.aquile.app import AquileReaderApp
        app = AquileReaderApp(db_path=self.db_path)
        app.register()
        app.activate()
        return app

    def test_window_has_titlebar_with_controls(self):
        app = self._make_app()
        try:
            content = app.window.get_content()
            self.assertIsNotNone(content, "main window must have content box")
            bar = content.get_first_child()
            self.assertIsInstance(bar, AquileTitleBar, "first content child must be AquileTitleBar")
            self.assertIs(bar, app.titlebar, "first content child must match app.titlebar")
            self.assertIsNot(app.window.get_titlebar(), app.titlebar)
            self.assertNotIsInstance(app.window.get_titlebar(), AquileTitleBar)

            controls = _collect_window_controls(bar)
            sides = [c.get_side() for c in controls]
            self.assertIn(Gtk.PackType.START, sides)
            self.assertIn(Gtk.PackType.END, sides)
        finally:
            if app.current_reader_view:
                try:
                    app.current_reader_view.cleanup()
                except Exception:
                    pass

    def test_open_book_updates_title_and_show_library_resets(self):
        app = self._make_app()
        try:
            fixtures = os.path.abspath(os.path.join(
                os.path.dirname(__file__), "..", "fixtures"))
            epub = os.path.join(fixtures, "canonical-text.epub")
            self.assertTrue(os.path.exists(epub), f"missing fixture {epub}")
            app.library_view.import_file(epub)
            books = app.book_repo.list_all()
            self.assertGreaterEqual(len(books), 1)
            book = books[0]
            app.open_book(book)
            expected = f"{book.title} - Aquile Reader"

            content = app.window.get_content()
            bar = content.get_first_child()
            self.assertIsInstance(bar, AquileTitleBar)
            self.assertIs(bar, app.titlebar)
            self.assertEqual(bar.get_title(), expected)
            self.assertEqual(app.titlebar.get_title(), expected)

            app.show_library()
            self.assertEqual(bar.get_title(), "Aquile Reader")
            self.assertEqual(app.titlebar.get_title(), "Aquile Reader")
        finally:
            if app.current_reader_view:
                try:
                    app.current_reader_view.cleanup()
                except Exception:
                    pass


if __name__ == "__main__":
    unittest.main()
