"""
Unit and integration tests for ComicArchiveEngine and ComicReaderView.
Validates FR-01, FR-06, FR-07, NFR-01, VP-01, AT-04.
"""

import os
import io
import time
import zipfile
import tempfile
import unittest

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Gdk", "4.0")
from gi.repository import Gtk, Adw, Gdk

# Initialize GTK in headless mode
try:
    Gtk.init()
except Exception:
    pass

from src.aquile.domain.models import Book, ReadingProgress, AppSettings
from src.aquile.storage.database import Database
from src.aquile.storage.repository import (
    BookRepository, ReadingProgressRepository, SettingsRepository
)
from src.aquile.reader.comic_reader import (
    ComicArchiveEngine, ComicError, CorruptComicError, ComicSecurityError
)
from src.aquile.ui.comic_view import ComicReaderView


FIXTURES_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "fixtures"))
SAMPLE_CBZ = os.path.join(FIXTURES_DIR, "sample-comic.cbz")

# Valid 1x1 RGBA PNG
VALID_1X1_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06"
    b"\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\xcf\xc0\xf0\x1f\x00\x05"
    b"\x00\x01\xff\x89\x99=\x1d\x00\x00\x00\x00IEND\xaeB`\x82"
)


def create_test_cbz(filepath: str, entries: list[tuple[str, bytes]]) -> str:
    """Helper to create a test CBZ archive with given entry filenames and byte contents."""
    with zipfile.ZipFile(filepath, "w") as z:
        for name, data in entries:
            z.writestr(name, data)
    return filepath


class TestComicArchiveEngine(unittest.TestCase):
    """Tests for ComicArchiveEngine archive handling, sorting, spreads, and textures."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_open_valid_fixture_cbz(self):
        """Engine opens fixtures/sample-comic.cbz and lists pages."""
        engine = ComicArchiveEngine(SAMPLE_CBZ)
        self.assertEqual(engine.get_page_count(), 3)
        pages = engine.list_page_entries()
        self.assertEqual(pages, ["001_cover.png", "002_page1.png", "003_page2.png"])

    def test_missing_file_raises_error(self):
        """Non-existent archive file raises FileNotFoundError."""
        missing = os.path.join(self.temp_dir.name, "nonexistent.cbz")
        with self.assertRaises(FileNotFoundError):
            ComicArchiveEngine(missing)

    def test_empty_file_raises_corrupt_error(self):
        """0-byte archive file raises CorruptComicError."""
        empty = os.path.join(self.temp_dir.name, "empty.cbz")
        with open(empty, "wb") as f:
            pass
        with self.assertRaises(CorruptComicError):
            ComicArchiveEngine(empty)

    def test_corrupt_zip_bytes_raise_corrupt_error(self):
        """Corrupt zip bytes raise CorruptComicError."""
        corrupt = os.path.join(self.temp_dir.name, "corrupt.cbz")
        with open(corrupt, "wb") as f:
            f.write(b"NOT A VALID ZIP ARCHIVE HEADER AT ALL")
        with self.assertRaises(CorruptComicError):
            ComicArchiveEngine(corrupt)

    def test_path_traversal_detection(self):
        """Archive containing path traversal entries raises ComicSecurityError."""
        malicious_cbz = os.path.join(self.temp_dir.name, "traversal.cbz")
        entries = [
            ("cover.png", VALID_1X1_PNG),
            ("../../etc/passwd", b"root:x:0:0::/root:/bin/bash"),
        ]
        create_test_cbz(malicious_cbz, entries)
        with self.assertRaises(ComicSecurityError) as ctx:
            ComicArchiveEngine(malicious_cbz)
        self.assertIn("path traversal", str(ctx.exception).lower())

    def test_natural_sorting_and_filtering(self):
        """Alphanumeric sorting correctly orders chapters and pages, ignoring non-images and macOS artifacts."""
        test_cbz = os.path.join(self.temp_dir.name, "sort_test.cbz")
        entries = [
            ("vol1_ch2_p10.png", VALID_1X1_PNG),
            ("vol1_ch2_p1.png", VALID_1X1_PNG),
            ("vol1_ch2_p2.png", VALID_1X1_PNG),
            ("vol1_ch10_p1.png", VALID_1X1_PNG),
            ("vol1_ch1_p1.png", VALID_1X1_PNG),
            ("readme.txt", b"Ignore this"),
            ("ComicInfo.xml", b"<xml/>"),
            ("__MACOSX/._vol1_ch1_p1.png", b"Mac artifact"),
            (".DS_Store", b"Apple desktop"),
            ("Thumbs.db", b"Windows thumbnail"),
        ]
        create_test_cbz(test_cbz, entries)

        engine = ComicArchiveEngine(test_cbz)
        pages = engine.list_page_entries()

        self.assertEqual(engine.get_page_count(), 5)
        expected_order = [
            "vol1_ch1_p1.png",
            "vol1_ch2_p1.png",
            "vol1_ch2_p2.png",
            "vol1_ch2_p10.png",
            "vol1_ch10_p1.png",
        ]
        self.assertEqual(pages, expected_order)

    def test_spread_calculations_single_mode(self):
        """Single spread mode maps each page to an isolated list regardless of direction."""
        test_cbz = os.path.join(self.temp_dir.name, "single_spreads.cbz")
        entries = [(f"p{i}.png", VALID_1X1_PNG) for i in range(4)]
        create_test_cbz(test_cbz, entries)

        engine = ComicArchiveEngine(test_cbz)
        ltr_single = engine.get_spreads(mode="single", direction="ltr")
        rtl_single = engine.get_spreads(mode="single", direction="rtl")

        self.assertEqual(ltr_single, [[0], [1], [2], [3]])
        self.assertEqual(rtl_single, [[0], [1], [2], [3]])

    def test_spread_calculations_double_mode_ltr(self):
        """Double spread mode in Western LTR isolates cover and pairs subsequent pages."""
        # Test odd count (5 pages): [0], [1, 2], [3, 4]
        cbz_5 = os.path.join(self.temp_dir.name, "ltr_5.cbz")
        create_test_cbz(cbz_5, [(f"p{i}.png", VALID_1X1_PNG) for i in range(5)])
        engine_5 = ComicArchiveEngine(cbz_5)
        self.assertEqual(engine_5.get_spreads(mode="double", direction="ltr"), [[0], [1, 2], [3, 4]])

        # Test even count (4 pages): [0], [1, 2], [3] (trailing single)
        cbz_4 = os.path.join(self.temp_dir.name, "ltr_4.cbz")
        create_test_cbz(cbz_4, [(f"p{i}.png", VALID_1X1_PNG) for i in range(4)])
        engine_4 = ComicArchiveEngine(cbz_4)
        self.assertEqual(engine_4.get_spreads(mode="double", direction="ltr"), [[0], [1, 2], [3]])

        # Test 1 page (cover only)
        cbz_1 = os.path.join(self.temp_dir.name, "ltr_1.cbz")
        create_test_cbz(cbz_1, [("cover.png", VALID_1X1_PNG)])
        engine_1 = ComicArchiveEngine(cbz_1)
        self.assertEqual(engine_1.get_spreads(mode="double", direction="ltr"), [[0]])

        # Test 0 pages
        cbz_0 = os.path.join(self.temp_dir.name, "ltr_0.cbz")
        create_test_cbz(cbz_0, [("notes.txt", b"No images")])
        engine_0 = ComicArchiveEngine(cbz_0)
        self.assertEqual(engine_0.get_spreads(mode="double", direction="ltr"), [])

    def test_spread_calculations_double_mode_rtl_manga(self):
        """Double spread mode in Manga RTL mode inverts pairs so earlier page is displayed on the right."""
        cbz_5 = os.path.join(self.temp_dir.name, "rtl_5.cbz")
        create_test_cbz(cbz_5, [(f"p{i}.png", VALID_1X1_PNG) for i in range(5)])
        engine = ComicArchiveEngine(cbz_5)

        rtl_spreads = engine.get_spreads(mode="double", direction="rtl")
        # Cover remains single [0]; pairs [1, 2] -> [2, 1] and [3, 4] -> [4, 3]
        self.assertEqual(rtl_spreads, [[0], [2, 1], [4, 3]])

    def test_get_page_image_bytes_and_index_bounds(self):
        """Retrieving page image bytes returns raw bytes and enforces bounds."""
        engine = ComicArchiveEngine(SAMPLE_CBZ)
        data = engine.get_page_image_bytes(0)
        self.assertIsInstance(data, bytes)
        self.assertGreater(len(data), 0)

        with self.assertRaises(IndexError):
            engine.get_page_image_bytes(-1)
        with self.assertRaises(IndexError):
            engine.get_page_image_bytes(99)

    def test_get_page_texture_and_decode_fallback(self):
        """get_page_texture returns valid Gdk.Texture, including graceful fallback on corrupt images."""
        engine = ComicArchiveEngine(SAMPLE_CBZ)
        tex = engine.get_page_texture(0)
        self.assertIsNotNone(tex)
        self.assertIsInstance(tex, Gdk.Texture)
        self.assertGreater(tex.get_width(), 0)
        self.assertGreater(tex.get_height(), 0)

        # Test corrupt image fallback
        corrupt_img_cbz = os.path.join(self.temp_dir.name, "corrupt_img.cbz")
        create_test_cbz(corrupt_img_cbz, [("corrupt_page.png", b"CORRUPTED PNG BYTES")])
        engine_corrupt = ComicArchiveEngine(corrupt_img_cbz)
        tex_fallback = engine_corrupt.get_page_texture(0)
        self.assertIsNotNone(tex_fallback)
        self.assertIsInstance(tex_fallback, Gdk.Texture)

    def test_context_manager_and_close(self):
        """Context manager support cleans up open archive handles."""
        with ComicArchiveEngine(SAMPLE_CBZ) as engine:
            self.assertEqual(engine.get_page_count(), 3)
        self.assertIsNone(engine._zip)

    def test_cbr_libarchive_fallback(self):
        """CBR extension archives load through libarchive or zip fallback."""
        cbr_path = os.path.join(self.temp_dir.name, "sample.cbr")
        create_test_cbz(cbr_path, [("page1.png", VALID_1X1_PNG), ("page2.png", VALID_1X1_PNG)])
        engine = ComicArchiveEngine(cbr_path)
        self.assertEqual(engine.get_page_count(), 2)
        self.assertEqual(len(engine.get_page_image_bytes(0)), len(VALID_1X1_PNG))


class TestComicReaderView(unittest.TestCase):
    """Tests for ComicReaderView UI behavior, aspect ratio containment, navigation, and persistence."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_comic.db")
        self.db = Database(self.db_path)
        self.book_repo = BookRepository(self.db)
        self.prog_repo = ReadingProgressRepository(self.db)
        self.settings_repo = SettingsRepository(self.db)

        self.cbz_path = os.path.join(self.temp_dir.name, "view_test.cbz")
        entries = [(f"page_{i:02d}.png", VALID_1X1_PNG) for i in range(1, 6)]  # 5 pages
        create_test_cbz(self.cbz_path, entries)

        self.book = Book(
            id="comic-book-1",
            title="Adventures of Aquile",
            author="Linux Team",
            file_path=self.cbz_path,
            file_format="cbz"
        )
        self.book_repo.add(self.book)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_view_initialization_and_aspect_ratio_containment(self):
        """ComicReaderView initializes with Gtk.Picture widgets having Gtk.ContentFit.CONTAIN and can_shrink=True."""
        view = ComicReaderView(
            self.book, self.book_repo, self.prog_repo, self.settings_repo
        )
        try:
            self.assertEqual(view.left_picture.get_content_fit(), Gtk.ContentFit.CONTAIN)
            self.assertEqual(view.right_picture.get_content_fit(), Gtk.ContentFit.CONTAIN)
            self.assertTrue(view.left_picture.get_can_shrink())
            self.assertTrue(view.right_picture.get_can_shrink())

            # Cover page (Spread 0) in double mode has left picture visible, right picture hidden
            self.assertTrue(view.left_picture.get_visible())
            self.assertFalse(view.right_picture.get_visible())
            self.assertEqual(view.current_page_idx, 0)
            self.assertEqual(view.current_spread_idx, 0)
            self.assertIn("Page 1 of 5", view.page_label.get_text())
        finally:
            view.cleanup()

    def test_page_navigation_and_clamping(self):
        """Navigating next and previous spreads updates pages, label, and clamping."""
        view = ComicReaderView(
            self.book, self.book_repo, self.prog_repo, self.settings_repo
        )
        try:
            # Spread 0: [0] -> next_page() -> Spread 1: [1, 2]
            view.next_page()
            self.assertEqual(view.current_spread_idx, 1)
            self.assertEqual(view.current_page_idx, 1)
            self.assertTrue(view.left_picture.get_visible())
            self.assertTrue(view.right_picture.get_visible())
            self.assertIn("Pages 2–3 of 5", view.page_label.get_text())

            # Spread 1 -> next_page() -> Spread 2: [3, 4]
            view.next_page()
            self.assertEqual(view.current_spread_idx, 2)
            self.assertEqual(view.current_page_idx, 3)
            self.assertIn("Pages 4–5 of 5", view.page_label.get_text())

            # Boundary clamp: next_page() at end does not advance further
            view.next_page()
            self.assertEqual(view.current_spread_idx, 2)

            # Prev page -> Spread 1
            view.prev_page()
            self.assertEqual(view.current_spread_idx, 1)
            self.assertEqual(view.current_page_idx, 1)

            # Prev page -> Spread 0 (Cover)
            view.prev_page()
            self.assertEqual(view.current_spread_idx, 0)
            self.assertEqual(view.current_page_idx, 0)

            # Boundary clamp: prev_page() at start does not underflow
            view.prev_page()
            self.assertEqual(view.current_spread_idx, 0)
        finally:
            view.cleanup()

    def test_direct_page_jumping(self):
        """jump_to_page directly jumps to page and selects the containing spread."""
        view = ComicReaderView(
            self.book, self.book_repo, self.prog_repo, self.settings_repo
        )
        try:
            # Jump to page 4 (0-based) -> Spread 2 ([3, 4])
            view.jump_to_page(4)
            self.assertEqual(view.current_page_idx, 4)
            self.assertEqual(view.current_spread_idx, 2)

            # Jump out of bounds -> clamped to last page
            view.jump_to_page(100)
            self.assertEqual(view.current_page_idx, 4)

            # Jump negative -> clamped to 0
            view.jump_to_page(-5)
            self.assertEqual(view.current_page_idx, 0)
            self.assertEqual(view.current_spread_idx, 0)
        finally:
            view.cleanup()

    def test_spread_mode_toggle(self):
        """Toggling between single-page and double-spread modes adjusts views dynamically."""
        view = ComicReaderView(
            self.book, self.book_repo, self.prog_repo, self.settings_repo
        )
        try:
            self.assertEqual(view.spread_mode, "double")

            # Jump to page 1
            view.jump_to_page(1)
            self.assertEqual(view.current_spread_idx, 1)  # [1, 2]

            # Toggle to single mode
            view.toggle_spread_mode()
            self.assertEqual(view.spread_mode, "single")
            self.assertEqual(view.current_page_idx, 1)
            self.assertEqual(view.current_spread_idx, 1)  # Spread 1 is [1]
            self.assertTrue(view.left_picture.get_visible())
            self.assertFalse(view.right_picture.get_visible())

            # Toggle back to double mode
            view.toggle_spread_mode()
            self.assertEqual(view.spread_mode, "double")
            self.assertEqual(view.current_spread_idx, 1)  # Spread 1 is [1, 2]
            self.assertTrue(view.left_picture.get_visible())
            self.assertTrue(view.right_picture.get_visible())
        finally:
            view.cleanup()

    def test_reading_direction_toggle(self):
        """Toggling reading direction between LTR and Manga RTL updates spread ordering."""
        view = ComicReaderView(
            self.book, self.book_repo, self.prog_repo, self.settings_repo
        )
        try:
            self.assertEqual(view.reading_direction, "ltr")
            view.jump_to_page(1)

            # Toggle to RTL (Manga)
            view.toggle_reading_direction()
            self.assertEqual(view.reading_direction, "rtl")
            spreads = view.engine.get_spreads(mode="double", direction="rtl")
            self.assertEqual(spreads[1], [2, 1])

            # Toggle back to LTR
            view.toggle_reading_direction()
            self.assertEqual(view.reading_direction, "ltr")
        finally:
            view.cleanup()

    def test_progress_persistence_and_resume(self):
        """Navigating pages persists progress to SQLite WAL DB, and reopening resumes from saved page."""
        view1 = ComicReaderView(
            self.book, self.book_repo, self.prog_repo, self.settings_repo
        )
        try:
            view1.next_page()  # Advances to spread 1 (page 1)
            view1._save_checkpoint()
        finally:
            view1.cleanup()

        progress = self.prog_repo.get(self.book.id)
        self.assertIsNotNone(progress)
        self.assertEqual(progress.page_index, 1)
        self.assertGreater(progress.percentage, 0.0)

        # Reopen with view2
        view2 = ComicReaderView(
            self.book, self.book_repo, self.prog_repo, self.settings_repo
        )
        try:
            self.assertEqual(view2.current_page_idx, 1)
            self.assertEqual(view2.current_spread_idx, 1)
            self.assertIn("Pages 2–3 of 5", view2.page_label.get_text())
        finally:
            view2.cleanup()

    def test_periodic_autosave_and_cleanup(self):
        """Autosave timer callback executes without error, and cleanup unregisters it."""
        view = ComicReaderView(
            self.book, self.book_repo, self.prog_repo, self.settings_repo
        )
        try:
            # Test periodic callback
            res = view._on_periodic_autosave()
            self.assertTrue(res)
            self.assertIsNotNone(view.auto_save_source_id)
        finally:
            view.cleanup()

        self.assertIsNone(view.auto_save_source_id)

    def test_empty_archive_view_handling(self):
        """ComicReaderView safely handles an empty archive without crashing."""
        empty_cbz = os.path.join(self.temp_dir.name, "empty_view.cbz")
        create_test_cbz(empty_cbz, [("readme.txt", b"No images")])
        empty_book = Book(
            id="empty-comic",
            title="Empty Comic",
            file_path=empty_cbz,
            file_format="cbz"
        )
        self.book_repo.add(empty_book)

        view = ComicReaderView(
            empty_book, self.book_repo, self.prog_repo, self.settings_repo
        )
        try:
            self.assertEqual(view.engine.get_page_count(), 0)
            self.assertIn("0 of 0", view.page_label.get_text())
            # Navigation does not throw
            view.next_page()
            view.prev_page()
            view.jump_to_page(0)
        finally:
            view.cleanup()

    def test_keyboard_navigation_handling(self):
        """Keyboard events (Right/Left arrows) trigger next/prev navigation."""
        view = ComicReaderView(
            self.book, self.book_repo, self.prog_repo, self.settings_repo
        )
        try:
            # Right arrow -> next_page
            handled = view._on_key_pressed(None, Gdk.KEY_Right, 0, 0)
            self.assertTrue(handled)
            self.assertEqual(view.current_spread_idx, 1)

            # Left arrow -> prev_page
            handled = view._on_key_pressed(None, Gdk.KEY_Left, 0, 0)
            self.assertTrue(handled)
            self.assertEqual(view.current_spread_idx, 0)

            # End -> jump to end
            handled = view._on_key_pressed(None, Gdk.KEY_End, 0, 0)
            self.assertTrue(handled)
            self.assertEqual(view.current_spread_idx, 2)

            # Home -> jump to start
            handled = view._on_key_pressed(None, Gdk.KEY_Home, 0, 0)
            self.assertTrue(handled)
            self.assertEqual(view.current_spread_idx, 0)
        finally:
            view.cleanup()


if __name__ == "__main__":
    unittest.main()
