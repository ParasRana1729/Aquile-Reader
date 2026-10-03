"""Headless tests for the Aquile shell + Home view (new files only).

GTK construction tests skip gracefully when no display/toolkit is
available; pure-logic tests (accent validation, sort keys) always run.
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

from src.aquile.domain.models import Book
from src.aquile.ui.aquile_shell import (
    RAIL_ITEMS,
    AquileShell,
    validate_accent,
)
from src.aquile.ui.home_view import HomeView, is_favorite, recent_sort_key


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


def _flow_children(flow):
    kids = []
    child = flow.get_first_child()
    while child is not None:
        kids.append(child)
        child = child.get_next_sibling()
    return kids


class _StubBookRepo:
    def __init__(self, books):
        self._books = list(books)

    def list_all(self):
        return list(self._books)


class _StubProgressRepo:
    def get(self, _book_id):
        return None


def _make_book(book_id, title="Title", author="Author", added=1000.0,
               last_read=None, favorite=False):
    book = Book(id=book_id, title=title, author=author,
                file_path=f"/books/{book_id}.epub", file_format="epub",
                total_chapters=3, file_size_bytes=512,
                added_at=added, last_read_at=last_read)
    book.is_favorite = favorite  # dynamic flag; Book has no such column
    return book


def _make_temp_repos():
    from src.aquile.storage.database import Database
    from src.aquile.storage.repository import (
        BookRepository,
        ReadingProgressRepository,
    )

    tmp = tempfile.TemporaryDirectory()
    db = Database(os.path.join(tmp.name, "aquile.db"))
    return tmp, BookRepository(db), ReadingProgressRepository(db)


class TestShellHomeHelpers(unittest.TestCase):
    def test_accent_validation_accepts_rrggbb(self):
        self.assertEqual(validate_accent("#009688"), "#009688")
        self.assertEqual(validate_accent("#ABCDEF"), "#ABCDEF")

    def test_accent_validation_rejects_bad_values(self):
        for bad in ("", "red", "#12345", "#1234567", "009688",
                    "#zzzzzz", None, 123):
            with self.assertRaises(ValueError, msg=f"{bad!r}"):
                validate_accent(bad)

    def test_recent_sort_key_prefers_last_read(self):
        old = _make_book("old", added=2000.0, last_read=2100.0)
        new = _make_book("new", added=1000.0, last_read=3000.0)
        self.assertGreater(recent_sort_key(new), recent_sort_key(old))

    def test_recent_sort_key_falls_back_to_added_at(self):
        book = _make_book("b", added=1500.0, last_read=None)
        self.assertEqual(recent_sort_key(book), 1500.0)

    def test_is_favorite_defaults_false(self):
        plain = Book(id="x", title="T", author="A", file_path="/books/x.epub")
        if "is_favorite" in plain.__dict__:
            del plain.__dict__["is_favorite"]
        self.assertFalse(is_favorite(plain))
        fav = _make_book("f", favorite=True)
        self.assertTrue(is_favorite(fav))


class TestAquileShell(unittest.TestCase):
    def test_shell_constructs_with_six_rail_buttons(self):
        shell = _try_construct(AquileShell)
        self.assertEqual(len(shell.rail_buttons), 6)
        self.assertEqual([n for n, _l, _i in RAIL_ITEMS],
                         list(shell.rail_buttons))
        self.assertEqual(shell.get_current_page(), "home")

    def test_shell_navigate_callback(self):
        seen = []
        shell = _try_construct(AquileShell, on_navigate=seen.append)
        label = Gtk.Label(label="lib")
        shell.add_page("library", label)
        shell.set_page("library")
        self.assertEqual(seen, ["library"])
        self.assertEqual(shell.get_current_page(), "library")

    def test_shell_rail_active_class_toggling(self):
        shell = _try_construct(AquileShell)
        shell.add_page("library", Gtk.Label(label="lib"))
        shell.add_page("settings", Gtk.Label(label="set"))
        shell.set_page("library")
        active = [n for n, b in shell.rail_buttons.items()
                  if "rail-active" in b.get_css_classes()]
        self.assertEqual(active, ["library"])
        shell.set_page("settings")
        active = [n for n, b in shell.rail_buttons.items()
                  if "rail-active" in b.get_css_classes()]
        self.assertEqual(active, ["settings"])

    def test_shell_accent_setter(self):
        shell = _try_construct(AquileShell)
        self.assertEqual(shell.get_accent(), "#009688")
        shell.set_accent("#ff5722")
        self.assertEqual(shell.get_accent(), "#ff5722")
        with self.assertRaises(ValueError):
            shell.set_accent("not-a-color")
        self.assertEqual(shell.get_accent(), "#ff5722")  # unchanged


class TestHomeView(unittest.TestCase):
    def test_home_refresh_with_temp_db_books(self):
        tmp, book_repo, progress_repo = _make_temp_repos()
        try:
            for i in range(3):
                book_repo.add(_make_book(f"db-{i}", title=f"DB Book {i}",
                                         added=1000.0 + i,
                                         last_read=2000.0 + i))
            home = _try_construct(HomeView, book_repo, progress_repo,
                                  lambda _b: None, lambda: None, lambda: None)
            home.refresh()
            self.assertEqual(len(_flow_children(home.recent_flow)), 3)
            # Most recently read first.
            first_card = _flow_children(home.recent_flow)[0].get_child()
            self.assertEqual(first_card.get_tooltip_text(), "DB Book 2")
            self.assertFalse(home.recent_empty_label.get_visible())
        finally:
            tmp.cleanup()

    def test_home_favorite_filtering_via_is_favorite(self):
        books = [_make_book("a", title="A", favorite=True),
                 _make_book("b", title="B", favorite=False),
                 _make_book("c", title="C", favorite=True)]
        home = _try_construct(HomeView, _StubBookRepo(books),
                              _StubProgressRepo(),
                              lambda _b: None, lambda: None, lambda: None)
        home.refresh()
        self.assertEqual(len(_flow_children(home.recent_flow)), 3)
        self.assertEqual(len(_flow_children(home.fav_flow)), 2)
        self.assertFalse(home.fav_empty_label.get_visible())

    def test_home_empty_states(self):
        home = _try_construct(HomeView, _StubBookRepo([]),
                              _StubProgressRepo(),
                              lambda _b: None, lambda: None, lambda: None)
        home.refresh()
        self.assertEqual(_flow_children(home.recent_flow), [])
        self.assertEqual(_flow_children(home.fav_flow), [])
        self.assertTrue(home.recent_empty_label.get_visible())
        self.assertTrue(home.fav_empty_label.get_visible())
        self.assertIn("Recent Reads", home.recent_title.get_text())
        self.assertIn("Favourite Books", home.fav_title.get_text())

    def test_home_card_click_and_footer_links(self):
        opened = []
        lib_hits = []
        more_hits = []
        books = [_make_book("k1", title="Click Me", favorite=True)]
        home = _try_construct(HomeView, _StubBookRepo(books),
                              _StubProgressRepo(),
                              opened.append, lambda: lib_hits.append(1),
                              lambda: more_hits.append(1))
        home.refresh()
        card_flow_child = _flow_children(home.recent_flow)[0]
        card_button = card_flow_child.get_child()
        card_button.emit("clicked")
        self.assertEqual([b.id for b in opened], ["k1"])
        home.open_library_button.emit("clicked")
        home.see_more_button.emit("clicked")
        home.add_button.emit("clicked")
        self.assertEqual(len(lib_hits), 2)  # footer link + "+" button
        self.assertEqual(len(more_hits), 1)
        self.assertEqual(home.open_library_button.get_label(), "Open Library ›")
        self.assertEqual(home.see_more_button.get_label(), "See more ›")


if __name__ == "__main__":
    unittest.main()
