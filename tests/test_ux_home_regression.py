"""WP-A home regression: exact title cleanup, card sizes, import metadata rule.

D5: Home showed a giant tile with a raw filename. Pins the exact cleaned
title, card geometry, dc:title preference, and cover-file usage.
"""

import os
import struct
import tempfile
import unittest
import zipfile

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

from src.aquile.covers import clean_display_title
from src.aquile.ui.home_view import COVER_SIZE, COVER_SIZE_LARGE


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


def _png_bytes() -> bytes:
    import zlib

    def chunk(tag: bytes, payload: bytes) -> bytes:
        return struct.pack(">I", len(payload)) + tag + payload + struct.pack(
            ">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    raw = b"\x00\x00\x00\x00"
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def _make_epub(path: str, title=None, creator=None, with_cover: bool = False) -> None:
    """Build a minimal EPUB fixture readable by EpubParser."""
    dc_title = f"<dc:title>{title}</dc:title>" if title else ""
    dc_creator = f"<dc:creator>{creator}</dc:creator>" if creator else ""
    manifest_extra = ""
    if with_cover:
        manifest_extra = ('<item id="cover" href="cover.png" '
                          'media-type="image/png" properties="cover-image"/>')
    opf = f"""<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="uid">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    {dc_title}
    {dc_creator}
    <dc:identifier id="uid">test-id</dc:identifier>
    <dc:language>en</dc:language>
  </metadata>
  <manifest>
    <item id="ch1" href="ch1.xhtml" media-type="application/xhtml+xml"/>
    {manifest_extra}
  </manifest>
  <spine><itemref idref="ch1"/></spine>
</package>"""
    container = """<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles>
</container>"""
    ch1 = ("<?xml version='1.0'?><html xmlns='http://www.w3.org/1999/xhtml'>"
           "<head><title>C1</title></head><body><h1>Chapter 1</h1><p>Hello.</p></body></html>")
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        z.writestr("META-INF/container.xml", container)
        z.writestr("OEBPS/content.opf", opf)
        z.writestr("OEBPS/ch1.xhtml", ch1)
        if with_cover:
            z.writestr("OEBPS/cover.png", _png_bytes())


def _flow_children(flow):
    kids = []
    child = flow.get_first_child()
    while child is not None:
        kids.append(child)
        child = child.get_next_sibling()
    return kids


def _card_cover_size_request(card_button):
    """Return (w, h) size request of the cover widget inside a card."""
    frame = card_button.get_child()
    cover = frame.get_first_child()
    w, h = cover.get_size_request()
    return (w, h)


class _StubBookRepo:
    def __init__(self, books):
        self._books = list(books)

    def list_all(self):
        return list(self._books)


class _StubProgressRepo:
    def get(self, _book_id):
        return None


def _make_book(book_id, title="Title", author="Author", cover_path=None):
    from src.aquile.domain.models import Book
    book = Book(id=book_id, title=title, author=author,
                file_path=f"/books/{book_id}.epub", file_format="epub",
                total_chapters=3, file_size_bytes=512,
                added_at=1000.0, last_read_at=2000.0)
    book.cover_path = cover_path
    return book


class TestCleanTitle(unittest.TestCase):
    def test_exact_prince_title(self):
        self.assertEqual(
            clean_display_title("machiavelli-niccolo-the-prince-1985.epub"),
            "Machiavelli Niccolo The Prince 1985")


class TestCardSizes(unittest.TestCase):
    def test_first_card_is_large(self):
        _require_gtk(self)
        from src.aquile.ui.home_view import HomeView
        books = [_make_book("b0", title="B0"), _make_book("b1", title="B1")]
        home = _try_construct(HomeView, _StubBookRepo(books), _StubProgressRepo(),
                              lambda _b: None, lambda: None, lambda: None)
        home.refresh()
        kids = _flow_children(home.recent_flow)
        self.assertEqual(len(kids), 2)
        self.assertEqual(_card_cover_size_request(kids[0].get_child()), COVER_SIZE_LARGE)
        self.assertEqual(COVER_SIZE_LARGE, (184, 256))

    def test_rest_cards_are_standard(self):
        _require_gtk(self)
        from src.aquile.ui.home_view import HomeView
        books = [_make_book("b0", title="B0"), _make_book("b1", title="B1")]
        home = _try_construct(HomeView, _StubBookRepo(books), _StubProgressRepo(),
                              lambda _b: None, lambda: None, lambda: None)
        home.refresh()
        kids = _flow_children(home.recent_flow)
        self.assertEqual(_card_cover_size_request(kids[1].get_child()), COVER_SIZE)
        self.assertEqual(COVER_SIZE, (128, 180))


class TestImportMetadataRule(unittest.TestCase):
    def _make_repos(self, tmpdir):
        from src.aquile.storage.database import Database
        from src.aquile.storage.repository import (
            AnnotationRepository, BookRepository, ReadingProgressRepository)
        db = Database(os.path.join(tmpdir, "aquile.db"))
        return (BookRepository(db), ReadingProgressRepository(db),
                AnnotationRepository(db))

    def test_import_prefers_dctitle_over_filename(self):
        _require_gtk(self)
        from src.aquile.ui.library_view import LibraryView
        with tempfile.TemporaryDirectory() as tmp:
            epub_path = os.path.join(tmp, "machiavelli-niccolo-the-prince-1985.epub")
            _make_epub(epub_path, title="The Prince",
                       creator="Niccolo Machiavelli")
            book_repo, progress_repo, ann_repo = self._make_repos(tmp)
            opened = []
            view = _try_construct(
                LibraryView, book_repo, progress_repo, ann_repo, opened.append)
            view.import_file(epub_path)
            books = book_repo.list_all()
            self.assertEqual(len(books), 1)
            self.assertEqual(books[0].title, "The Prince")
            self.assertEqual(books[0].author, "Niccolo Machiavelli")

    def test_import_falls_back_to_cleaned_filename(self):
        _require_gtk(self)
        from src.aquile.ui.library_view import LibraryView
        with tempfile.TemporaryDirectory() as tmp:
            epub_path = os.path.join(tmp, "machiavelli-niccolo-the-prince-1985.epub")
            _make_epub(epub_path)  # no dc:title / dc:creator
            book_repo, progress_repo, ann_repo = self._make_repos(tmp)
            opened = []
            view = _try_construct(
                LibraryView, book_repo, progress_repo, ann_repo, opened.append)
            view.import_file(epub_path)
            books = book_repo.list_all()
            self.assertEqual(len(books), 1)
            self.assertEqual(books[0].title, "Machiavelli Niccolo The Prince 1985")


class TestCoverUsage(unittest.TestCase):
    def test_cover_file_used_when_present(self):
        _require_gtk(self)
        from src.aquile.ui.home_view import HomeView
        with tempfile.TemporaryDirectory() as tmp:
            cover = os.path.join(tmp, "cover.png")
            with open(cover, "wb") as fh:
                fh.write(_png_bytes())
            book = _make_book("c1", title="With Cover", cover_path=cover)
            home = _try_construct(HomeView, _StubBookRepo([book]),
                                  _StubProgressRepo(),
                                  lambda _b: None, lambda: None, lambda: None)
            home.refresh()
            kids = _flow_children(home.recent_flow)
            self.assertEqual(len(kids), 1)
            frame = kids[0].get_child().get_child()
            cover_widget = frame.get_first_child()
            self.assertIsInstance(cover_widget, Gtk.Picture)
            self.assertEqual(cover_widget.get_size_request(), COVER_SIZE_LARGE)

    def test_home_add_button_uses_shipped_icon(self):
        _require_gtk(self)
        from src.aquile.ui.home_view import HomeView
        from src.aquile.ui import icon_loader
        home = _try_construct(HomeView, _StubBookRepo([]), _StubProgressRepo(),
                              lambda _b: None, lambda: None, lambda: None)
        expected = icon_loader.path_for("plus")
        self.assertTrue(os.path.isfile(expected), f"missing: {expected}")
        actual = getattr(home.add_button, "_aquile_icon_path", None)
        self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
