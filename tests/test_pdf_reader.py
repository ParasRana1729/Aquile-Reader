"""
Comprehensive unit test suite for PDF document reader subsystem (WP-10 / M3).
Tests both PdfDocumentEngine (ctypes + CLI fallback) and PdfReaderView (GTK4 widget).
Covers:
- PDF document inspection: page count, dimensions, bounds checks.
- Dual-backend rendering: in-memory ctypes Poppler/Cairo and CLI pdftoppm/pdfinfo.
- Vector texture creation into Gdk.Texture.
- Zoom scale math: fit-to-width, fit-to-page, zero viewport protection, and clamping [0.25, 5.0].
- View navigation: next/previous, direct page jump, spin button synchronization.
- Progress durability: 5-second checkpoint persistence, percentage computation, and resume on reopen.
"""

import os
import io
import tempfile
import unittest
import time

try:
    import gi
    gi.require_version('Gtk', '4.0')
    gi.require_version('Adw', '1')
    gi.require_version('Gdk', '4.0')
    from gi.repository import Gtk, Adw, Gdk, GLib
    HAS_GTK = True
    try:
        Gtk.init()
    except Exception:
        pass
except (ImportError, ValueError):
    HAS_GTK = False

from PIL import Image

from src.aquile.domain.models import Book, ReadingProgress, AppSettings
from src.aquile.storage.database import Database
from src.aquile.storage.repository import (
    BookRepository, ReadingProgressRepository, SettingsRepository
)
from src.aquile.reader.pdf_reader import PdfDocumentEngine
from src.aquile.ui.pdf_view import PdfReaderView


FIXTURES_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "fixtures"))
SAMPLE_PDF = os.path.join(FIXTURES_DIR, "sample-doc.pdf")


class TestPdfDocumentEngine(unittest.TestCase):
    """Unit tests for PdfDocumentEngine."""

    def setUp(self):
        self.assertTrue(os.path.exists(SAMPLE_PDF), f"Fixture not found at {SAMPLE_PDF}")

    def test_init_invalid_file(self):
        """Engine rejects missing and empty file paths with appropriate exceptions."""
        with self.assertRaises(ValueError):
            PdfDocumentEngine("")

        with self.assertRaises(FileNotFoundError):
            PdfDocumentEngine("/nonexistent/path/doc.pdf")

        # Corrupt file
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"not a valid pdf content")
            corrupt_path = f.name
        try:
            with self.assertRaises(Exception):
                PdfDocumentEngine(corrupt_path)
        finally:
            if os.path.exists(corrupt_path):
                os.unlink(corrupt_path)

    def test_page_count_and_dimensions_ctypes(self):
        """Engine correctly reports total pages and US Letter dimensions via ctypes backend."""
        with PdfDocumentEngine(SAMPLE_PDF, prefer_cli=False) as engine:
            self.assertEqual(engine.get_page_count(), 2)

            # Both pages are US Letter (612 x 792 pt)
            w0, h0 = engine.get_page_dimensions(0)
            self.assertAlmostEqual(w0, 612.0, delta=2.0)
            self.assertAlmostEqual(h0, 792.0, delta=2.0)

            w1, h1 = engine.get_page_dimensions(1)
            self.assertAlmostEqual(w1, 612.0, delta=2.0)
            self.assertAlmostEqual(h1, 792.0, delta=2.0)

            # Out of bounds indices
            with self.assertRaises(IndexError):
                engine.get_page_dimensions(-1)
            with self.assertRaises(IndexError):
                engine.get_page_dimensions(2)

    def test_page_count_and_dimensions_cli_fallback(self):
        """Engine correctly extracts page count and dimensions when forced to CLI backend."""
        with PdfDocumentEngine(SAMPLE_PDF, prefer_cli=True) as engine:
            self.assertEqual(engine.get_page_count(), 2)
            w0, h0 = engine.get_page_dimensions(0)
            self.assertAlmostEqual(w0, 612.0, delta=2.0)
            self.assertAlmostEqual(h0, 792.0, delta=2.0)

    def test_fit_scale_calculations(self):
        """Engine accurately calculates fit-to-width, fit-to-page, and zoom clamping."""
        with PdfDocumentEngine(SAMPLE_PDF) as engine:
            # Fit-to-width mode (1224 / 612 = 2.0)
            scale_w = engine.calculate_fit_scale(0, viewport_width=1224.0, viewport_height=1000.0, mode="width")
            self.assertAlmostEqual(scale_w, 2.0, delta=0.05)

            # Fit-to-page mode constrained by height (792 / 792 = 1.0)
            scale_p_h = engine.calculate_fit_scale(0, viewport_width=1224.0, viewport_height=792.0, mode="page")
            self.assertAlmostEqual(scale_p_h, 1.0, delta=0.05)

            # Fit-to-page mode constrained by width (306 / 612 = 0.5)
            scale_p_w = engine.calculate_fit_scale(0, viewport_width=306.0, viewport_height=1584.0, mode="page")
            self.assertAlmostEqual(scale_p_w, 0.5, delta=0.05)

            # Ultra-wide viewport constrained by height
            scale_wide = engine.calculate_fit_scale(0, viewport_width=8000.0, viewport_height=600.0, mode="page")
            self.assertAlmostEqual(scale_wide, 600.0 / 792.0, delta=0.05)

            # Zero and negative viewports safely return 0.0 without ZeroDivisionError
            scale_zero = engine.calculate_fit_scale(0, viewport_width=0.0, viewport_height=0.0, mode="page")
            self.assertGreaterEqual(scale_zero, 0.0)
            self.assertEqual(scale_zero, 0.0)

            scale_neg = engine.calculate_fit_scale(0, viewport_width=-100.0, viewport_height=500.0, mode="page")
            self.assertEqual(scale_neg, 0.0)

            # Zoom clamping limits [0.25, 5.0]
            scale_huge = engine.calculate_fit_scale(0, viewport_width=100000.0, viewport_height=100000.0, mode="width")
            self.assertAlmostEqual(scale_huge, 5.0, delta=0.01)

            scale_tiny = engine.calculate_fit_scale(0, viewport_width=10.0, viewport_height=10.0, mode="page")
            self.assertAlmostEqual(scale_tiny, 0.25, delta=0.01)

    def test_render_page_png_bytes_and_texture_ctypes(self):
        """In-memory ctypes renderer produces valid PNG bytes and crisp Gdk.Texture."""
        with PdfDocumentEngine(SAMPLE_PDF, prefer_cli=False) as engine:
            png_bytes = engine.render_page_png_bytes(0, scale=1.0)
            self.assertTrue(png_bytes.startswith(b"\x89PNG\r\n\x1a\n"))

            img = Image.open(io.BytesIO(png_bytes))
            self.assertEqual(img.size, (612, 792))

            # Half-scale
            png_half = engine.render_page_png_bytes(0, scale=0.5)
            img_half = Image.open(io.BytesIO(png_half))
            self.assertEqual(img_half.size, (306, 396))

            if HAS_GTK:
                tex = engine.render_page_texture(0, scale=1.0)
                self.assertIsNotNone(tex)
                self.assertEqual(tex.get_width(), 612)
                self.assertEqual(tex.get_height(), 792)

    def test_render_page_png_bytes_and_texture_cli(self):
        """CLI fallback renderer produces valid PNG bytes and crisp Gdk.Texture."""
        with PdfDocumentEngine(SAMPLE_PDF, prefer_cli=True) as engine:
            png_bytes = engine.render_page_png_bytes(1, scale=1.0)
            self.assertTrue(png_bytes.startswith(b"\x89PNG\r\n\x1a\n"))

            img = Image.open(io.BytesIO(png_bytes))
            self.assertEqual(img.size, (612, 792))

            if HAS_GTK:
                tex = engine.render_page_texture(1, scale=1.0)
                self.assertIsNotNone(tex)
                self.assertEqual(tex.get_width(), 612)
                self.assertEqual(tex.get_height(), 792)


class TestPdfReaderView(unittest.TestCase):
    """Unit tests for PdfReaderView UI widget and progress persistence."""

    def setUp(self):
        if not HAS_GTK:
            self.skipTest("GTK4 / Libadwaita environment not available")

        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_pdf.db")
        self.db = Database(self.db_path)
        self.book_repo = BookRepository(self.db)
        self.progress_repo = ReadingProgressRepository(self.db)
        self.settings_repo = SettingsRepository(self.db)

        self.book = Book(
            id="book-pdf-001",
            title="Sample PDF Document",
            author="Test Author",
            file_path=SAMPLE_PDF,
            file_format="pdf"
        )
        self.book_repo.add(self.book)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_view_initialization_and_rendering(self):
        """PdfReaderView loads document, initializes header, and renders page 0."""
        view = PdfReaderView(self.book, self.book_repo, self.progress_repo, self.settings_repo)
        try:
            self.assertEqual(view.total_pages, 2)
            self.assertEqual(view.current_page_idx, 0)
            self.assertIsNotNone(view.picture.get_paintable())
            self.assertEqual(view.title_widget.get_title(), self.book.title)
            self.assertIn("Page 1 of 2", view.title_widget.get_subtitle())
        finally:
            view.cleanup()

    def test_page_navigation_and_clamping(self):
        """PdfReaderView navigation methods advance pages and respect boundaries."""
        view = PdfReaderView(self.book, self.book_repo, self.progress_repo, self.settings_repo)
        try:
            self.assertEqual(view.current_page_idx, 0)

            # Move to page 1
            advanced = view.next_page()
            self.assertTrue(advanced)
            self.assertEqual(view.current_page_idx, 1)

            # Attempt to advance past last page
            advanced_again = view.next_page()
            self.assertFalse(advanced_again)
            self.assertEqual(view.current_page_idx, 1)

            # Move back to page 0
            retreated = view.prev_page()
            self.assertTrue(retreated)
            self.assertEqual(view.current_page_idx, 0)

            # Attempt to move before page 0
            retreated_again = view.prev_page()
            self.assertFalse(retreated_again)
            self.assertEqual(view.current_page_idx, 0)

            # Direct jumping
            view.go_to_page(1)
            self.assertEqual(view.current_page_idx, 1)

            # Direct jump clamping
            view.go_to_page(999)
            self.assertEqual(view.current_page_idx, 1)
            view.go_to_page(-50)
            self.assertEqual(view.current_page_idx, 0)
        finally:
            view.cleanup()

    def test_zoom_controls(self):
        """PdfReaderView zoom controls adjust zoom scale and respect bounds."""
        view = PdfReaderView(self.book, self.book_repo, self.progress_repo, self.settings_repo)
        try:
            view.reset_zoom()
            self.assertAlmostEqual(view.zoom_scale, 1.0)
            self.assertEqual(view.zoom_mode, "custom")

            # Zoom in
            view.zoom_in(0.5)
            self.assertAlmostEqual(view.zoom_scale, 1.5)

            # Zoom out
            view.zoom_out(0.25)
            self.assertAlmostEqual(view.zoom_scale, 1.25)

            # Fit modes
            view.fit_to_width()
            self.assertEqual(view.zoom_mode, "width")
            self.assertGreater(view.zoom_scale, 0.0)

            view.fit_to_page()
            self.assertEqual(view.zoom_mode, "page")
            self.assertGreater(view.zoom_scale, 0.0)

            # Scale clamping
            view.set_zoom_scale(10.0)
            self.assertAlmostEqual(view.zoom_scale, 5.0)

            view.set_zoom_scale(0.01)
            self.assertAlmostEqual(view.zoom_scale, 0.25)
        finally:
            view.cleanup()

    def test_progress_persistence_and_resume(self):
        """Reading progress persists to SQLite and accurately resumes upon reopening."""
        view = PdfReaderView(self.book, self.book_repo, self.progress_repo, self.settings_repo)
        try:
            view.go_to_page(1)
            view._save_checkpoint()

            progress = self.progress_repo.get(self.book.id)
            self.assertIsNotNone(progress)
            self.assertEqual(progress.page_index, 1)
            self.assertAlmostEqual(progress.percentage, 100.0)
        finally:
            view.cleanup()

        # Reopen PDF book in a new view
        resumed_view = PdfReaderView(self.book, self.book_repo, self.progress_repo, self.settings_repo)
        try:
            self.assertEqual(resumed_view.current_page_idx, 1)
            self.assertIn("Page 2 of 2", resumed_view.title_widget.get_subtitle())
        finally:
            resumed_view.cleanup()

    def test_periodic_autosave_and_cleanup(self):
        """Periodic autosave callback triggers save without error and cleanup clears timer."""
        view = PdfReaderView(self.book, self.book_repo, self.progress_repo, self.settings_repo)
        try:
            self.assertIsNotNone(view.auto_save_source_id)
            result = view._on_periodic_autosave()
            self.assertTrue(result)

            # Check that last read timestamp was updated in book_repo
            updated_book = self.book_repo.get_by_id(self.book.id)
            self.assertIsNotNone(updated_book.last_read_at)
        finally:
            view.cleanup()
            self.assertIsNone(view.auto_save_source_id)


if __name__ == "__main__":
    unittest.main()
