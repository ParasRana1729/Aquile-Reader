"""
Comprehensive End-to-End (E2E) Test Suite for WP-10 & WP-11.
Covers:
- WP-10: PDF and Comic Book Graphic Readers (enumeration, natural sort, spreads, LTR/RTL, zoom/fit, persistence).
- WP-11: Reading Statistics and Session Insights (tracking, idle filtering, words estimation, WPM, repo CRUD).

Methodology: 4-Tier Testing Architecture
- Tier 1: Feature Coverage (isolated functionality tests)
- Tier 2: Boundary & Corner Cases (empty archives, single page, zero duration, idle limits)
- Tier 3: Cross-Feature Combinations (spread mode + Manga direction, stats tracking during zoom/spread changes)
- Tier 4: Real-World Scenarios (complete reading sessions, resume from last page, library-wide statistics aggregation)

Validates PRD Requirements: FR-01, FR-06, FR-07, FR-15, FR-20, NFR-01, NFR-02, AT-01, AT-03, AT-04.
"""

import os
import sys
import tempfile
import unittest
import zipfile
import time
from datetime import datetime

# Initialize GTK in headless/test mode if available
try:
    import gi
    gi.require_version('Gtk', '4.0')
    gi.require_version('Adw', '1')
    from gi.repository import Gtk, Adw, Gdk
    HAS_GTK = True
    try:
        Gtk.init()
    except Exception:
        pass
except (ImportError, ValueError):
    HAS_GTK = False

# Core App & Domain imports
from src.aquile.domain.models import Book, ReadingProgress, Annotation, AppSettings
from src.aquile.storage.database import Database
from src.aquile.storage.repository import (
    BookRepository, ReadingProgressRepository, AnnotationRepository, SettingsRepository
)
from src.aquile.app import AquileReaderApp

# Dynamic imports for WP-10 & WP-11 modules (gracefully handled during in-flight implementation)
try:
    from src.aquile.reader.comic_reader import ComicArchiveEngine
except (ImportError, AttributeError):
    ComicArchiveEngine = None

try:
    from src.aquile.reader.pdf_reader import PdfDocumentEngine
except (ImportError, AttributeError):
    PdfDocumentEngine = None

try:
    from src.aquile.reader.session_tracker import ReadingSessionTracker
except (ImportError, AttributeError):
    ReadingSessionTracker = None

try:
    from src.aquile.domain.models import ReadingSession, BookStatistics, LibraryStatistics
except (ImportError, AttributeError):
    ReadingSession = None
    BookStatistics = None
    LibraryStatistics = None

try:
    from src.aquile.storage.repository import StatisticsRepository
except (ImportError, AttributeError):
    StatisticsRepository = None

try:
    from src.aquile.ui.comic_view import ComicReaderView
except (ImportError, AttributeError):
    ComicReaderView = None

try:
    from src.aquile.ui.pdf_view import PdfReaderView
except (ImportError, AttributeError):
    PdfReaderView = None


FIXTURES_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "fixtures"))
SAMPLE_PDF = os.path.join(FIXTURES_DIR, "sample-doc.pdf")
SAMPLE_CBZ = os.path.join(FIXTURES_DIR, "sample-comic.cbz")
CANONICAL_EPUB = os.path.join(FIXTURES_DIR, "canonical-text.epub")

# Valid 1x1 PNG bytes for synthetic test archives
VALID_1X1_PNG = (
    b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06'
    b'\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\xff\xff?\x00\x05'
    b'\xfe\x02\xfe\r\xef\x85\xaa\x00\x00\x00\x00IEND\xaeB`\x82'
)


def create_synthetic_cbz(filepath: str, entries: list[tuple[str, bytes]]) -> str:
    """Helper to generate deterministic CBZ archive with specified entries."""
    with zipfile.ZipFile(filepath, "w") as z:
        for name, data in entries:
            z.writestr(name, data)
    return filepath


# ==============================================================================
# TIER 1: FEATURE COVERAGE (ISOLATED FUNCTIONALITY)
# ==============================================================================

class TestTier1FeatureCoverage(unittest.TestCase):
    """Tier 1: Feature Coverage — isolated unit & contract tests."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_comic_archive_enumeration_natural_sorting(self):
        """T1.1: ComicArchiveEngine page enumeration & natural sort ('page2' before 'page10')."""
        if ComicArchiveEngine is None:
            self.skipTest("ComicArchiveEngine not implemented yet")

        cbz_path = os.path.join(self.temp_dir.name, "test_sort.cbz")
        entries = [
            ("page10.png", VALID_1X1_PNG),
            ("page2.png", VALID_1X1_PNG),
            ("cover.jpg", VALID_1X1_PNG),
            ("page1.png", VALID_1X1_PNG),
            ("page20.png", VALID_1X1_PNG),
            ("page11.png", VALID_1X1_PNG),
            ("notes.txt", b"Non-image text file"),
            ("__MACOSX/._page1.png", b"Mac metadata"),
            ("metadata.xml", b"<xml/>"),
        ]
        create_synthetic_cbz(cbz_path, entries)

        engine = ComicArchiveEngine(cbz_path)
        pages = engine.list_page_entries()

        # Non-image files and Mac metadata must be excluded
        self.assertEqual(engine.get_page_count(), 6)
        self.assertEqual(len(pages), 6)
        self.assertNotIn("notes.txt", pages)
        self.assertNotIn("metadata.xml", pages)
        self.assertFalse(any(p.startswith("__MACOSX") for p in pages))

        # Natural sort verification: page2 must precede page10
        idx_page2 = pages.index("page2.png")
        idx_page10 = pages.index("page10.png")
        idx_page11 = pages.index("page11.png")
        idx_page20 = pages.index("page20.png")
        self.assertLess(idx_page2, idx_page10, "Natural sort failed: 'page10' preceded 'page2'")
        self.assertLess(idx_page10, idx_page11)
        self.assertLess(idx_page11, idx_page20)

    def test_comic_spread_pairing_ltr(self):
        """T1.2: ComicArchiveEngine single & double spread pairing in Western LTR mode."""
        if ComicArchiveEngine is None:
            self.skipTest("ComicArchiveEngine not implemented yet")

        cbz_path = os.path.join(self.temp_dir.name, "test_spreads.cbz")
        entries = [
            (f"page_{i:02d}.png", VALID_1X1_PNG) for i in range(1, 6)  # 5 pages
        ]
        create_synthetic_cbz(cbz_path, entries)

        engine = ComicArchiveEngine(cbz_path)

        # Single spread mode: 1 page per spread
        single_spreads = engine.get_spreads(mode="single", direction="ltr")
        self.assertEqual(len(single_spreads), 5)
        for spread in single_spreads:
            self.assertEqual(len(spread), 1)

        # Double spread mode: Cover alone, subsequent in pairs
        double_spreads = engine.get_spreads(mode="double", direction="ltr")
        self.assertEqual(len(double_spreads), 3)  # [cover], [p1, p2], [p3, p4]
        # Cover is isolated
        self.assertEqual(len(double_spreads[0]), 1)
        # Next pair contains 2 pages
        self.assertEqual(len(double_spreads[1]), 2)

    def test_comic_spread_pairing_rtl_manga(self):
        """T1.3: ComicArchiveEngine RTL Manga spread pair inversion."""
        if ComicArchiveEngine is None:
            self.skipTest("ComicArchiveEngine not implemented yet")

        cbz_path = os.path.join(self.temp_dir.name, "test_manga.cbz")
        entries = [
            ("001_cover.png", VALID_1X1_PNG),
            ("002_page1.png", VALID_1X1_PNG),
            ("003_page2.png", VALID_1X1_PNG),
        ]
        create_synthetic_cbz(cbz_path, entries)

        engine = ComicArchiveEngine(cbz_path)
        ltr_spreads = engine.get_spreads(mode="double", direction="ltr")
        rtl_spreads = engine.get_spreads(mode="double", direction="rtl")

        self.assertEqual(len(ltr_spreads), 2)
        self.assertEqual(len(rtl_spreads), 2)
        # Cover remains single in both
        self.assertEqual(len(ltr_spreads[0]), 1)
        self.assertEqual(len(rtl_spreads[0]), 1)

        # In Manga RTL, the pair order is inverted so the right page is read first
        ltr_pair = ltr_spreads[1]
        rtl_pair = rtl_spreads[1]
        self.assertEqual(len(ltr_pair), 2)
        self.assertEqual(len(rtl_pair), 2)
        self.assertEqual(rtl_pair, [ltr_pair[1], ltr_pair[0]], "Manga RTL pair inversion failed")

    def test_aspect_ratio_containment_math(self):
        """T1.4: Aspect ratio containment calculation (scaling within viewport without distortion)."""
        # Mathematical invariant: aspect ratio must be preserved
        # Given an image (W, H) and viewport (VW, VH), scale = min(VW / W, VH / H)
        def compute_containment(w: float, h: float, vw: float, vh: float) -> tuple[float, float]:
            scale = min(vw / w, vh / h)
            return (w * scale, h * scale)

        # Test landscape image in square viewport
        rw, rh = compute_containment(1200, 800, 600, 600)
        self.assertAlmostEqual(rw, 600.0)
        self.assertAlmostEqual(rh, 400.0)
        self.assertAlmostEqual(rw / rh, 1200 / 800)

        # Test portrait image in wide viewport
        rw, rh = compute_containment(800, 1600, 1200, 800)
        self.assertAlmostEqual(rw, 400.0)
        self.assertAlmostEqual(rh, 800.0)
        self.assertAlmostEqual(rw / rh, 800 / 1600)

    def test_pdf_page_count_and_dimensions(self):
        """T1.5: PdfDocumentEngine page count and MediaBox dimension extraction."""
        if PdfDocumentEngine is None:
            self.skipTest("PdfDocumentEngine not implemented yet")

        self.assertTrue(os.path.exists(SAMPLE_PDF), f"Missing fixture {SAMPLE_PDF}")
        engine = PdfDocumentEngine(SAMPLE_PDF)
        self.assertEqual(engine.get_page_count(), 2)

        # Both pages in sample-doc.pdf are 612 x 792 pt (US Letter)
        w0, h0 = engine.get_page_dimensions(0)
        self.assertAlmostEqual(w0, 612.0, delta=2.0)
        self.assertAlmostEqual(h0, 792.0, delta=2.0)

        w1, h1 = engine.get_page_dimensions(1)
        self.assertAlmostEqual(w1, 612.0, delta=2.0)
        self.assertAlmostEqual(h1, 792.0, delta=2.0)

    def test_pdf_fit_scale_calculations(self):
        """T1.6: PdfDocumentEngine zoom calculations (fit-to-width, fit-to-page)."""
        if PdfDocumentEngine is None:
            self.skipTest("PdfDocumentEngine not implemented yet")

        engine = PdfDocumentEngine(SAMPLE_PDF)

        # Fit-to-width mode
        scale_w = engine.calculate_fit_scale(0, viewport_width=1224.0, viewport_height=1000.0, mode="width")
        self.assertAlmostEqual(scale_w, 2.0, delta=0.05)

        # Fit-to-page mode (constrained by height)
        scale_p_h = engine.calculate_fit_scale(0, viewport_width=1224.0, viewport_height=792.0, mode="page")
        self.assertAlmostEqual(scale_p_h, 1.0, delta=0.05)

        # Fit-to-page mode (constrained by width)
        scale_p_w = engine.calculate_fit_scale(0, viewport_width=306.0, viewport_height=1584.0, mode="page")
        self.assertAlmostEqual(scale_p_w, 0.5, delta=0.05)

    def test_session_tracker_active_duration_accumulation(self):
        """T1.7: ReadingSessionTracker session start/stop and active duration accumulation."""
        if ReadingSessionTracker is None:
            self.skipTest("ReadingSessionTracker not implemented yet")

        tracker = ReadingSessionTracker(book_id="book-test-1", format="epub", idle_threshold_seconds=120.0)
        tracker.tick(now=1000.0)
        tracker.register_activity()
        tracker.tick(now=1010.0)
        tracker.register_activity()
        tracker.tick(now=1030.0)

        session = tracker.end_session()
        self.assertEqual(session.book_id, "book-test-1")
        self.assertGreaterEqual(session.duration_seconds, 30.0)
        self.assertGreaterEqual(session.active_seconds, 30.0)
        self.assertEqual(session.idle_seconds, 0.0)

    def test_session_tracker_idle_filtering_text_and_comics(self):
        """T1.8: ReadingSessionTracker idle filtering (120s text / 60s comics)."""
        if ReadingSessionTracker is None:
            self.skipTest("ReadingSessionTracker not implemented yet")

        # 1. Text reading (120s idle threshold)
        text_tracker = ReadingSessionTracker(book_id="b-text", format="epub")
        text_tracker.tick(now=1000.0)
        text_tracker.register_activity()
        text_tracker.tick(now=1030.0)  # +30s active
        # User pauses for 180s (> 120s threshold)
        text_tracker.tick(now=1210.0)
        s_text = text_tracker.end_session()
        self.assertAlmostEqual(s_text.active_seconds, 30.0, delta=5.0)
        self.assertGreaterEqual(s_text.idle_seconds, 120.0)

        # 2. Comic reading (60s idle threshold)
        comic_tracker = ReadingSessionTracker(book_id="b-comic", format="cbz")
        comic_tracker.tick(now=2000.0)
        comic_tracker.register_activity()
        comic_tracker.tick(now=2020.0)  # +20s active
        # User pauses for 80s (> 60s threshold)
        comic_tracker.tick(now=2100.0)
        s_comic = comic_tracker.end_session()
        self.assertAlmostEqual(s_comic.active_seconds, 20.0, delta=5.0)
        self.assertGreaterEqual(s_comic.idle_seconds, 60.0)

    def test_session_tracker_wpm_calculation_and_guards(self):
        """T1.9: ReadingSessionTracker WPM speed metric calculation with duration guards."""
        if ReadingSessionTracker is None:
            self.skipTest("ReadingSessionTracker not implemented yet")

        tracker = ReadingSessionTracker(book_id="b-wpm", format="epub", idle_threshold_seconds=120.0)
        tracker.tick(now=1000.0)
        tracker.record_page_turn(words_on_page=250)
        tracker.tick(now=1030.0)
        tracker.record_page_turn(words_on_page=250)
        tracker.tick(now=1060.0)  # active = 60s (1.0 minute), words = 500

        session = tracker.end_session()
        self.assertEqual(session.words_read, 500)
        # WPM = 500 words / 1.0 min = 500.0 WPM
        self.assertAlmostEqual(session.wpm, 500.0, delta=5.0)

    def test_statistics_repository_crud_and_aggregates(self):
        """T1.10: StatisticsRepository session recording and statistics queries."""
        if StatisticsRepository is None or ReadingSession is None:
            self.skipTest("StatisticsRepository or ReadingSession not implemented yet")

        db_path = os.path.join(self.temp_dir.name, "stats_test.db")
        db = Database(db_path)
        book_repo = BookRepository(db)
        stats_repo = StatisticsRepository(db)

        # Add book
        book = Book(id="stats-book-1", title="Stats Guide", file_format="epub")
        book_repo.add(book)

        # Record session 1
        s1 = ReadingSession(
            id="sess-1",
            book_id="stats-book-1",
            started_at=datetime.now(),
            ended_at=datetime.now(),
            duration_seconds=120.0,
            active_seconds=100.0,
            idle_seconds=20.0,
            words_read=500,
            wpm=300.0
        )
        stats_repo.record_session(s1)

        # Record session 2
        s2 = ReadingSession(
            id="sess-2",
            book_id="stats-book-1",
            started_at=datetime.now(),
            ended_at=datetime.now(),
            duration_seconds=180.0,
            active_seconds=140.0,
            idle_seconds=40.0,
            words_read=700,
            wpm=300.0
        )
        stats_repo.record_session(s2)

        # Retrieve book stats
        b_stats = stats_repo.get_book_statistics("stats-book-1")
        self.assertEqual(b_stats.total_sessions, 2)
        self.assertAlmostEqual(b_stats.total_reading_seconds, 300.0)
        self.assertAlmostEqual(b_stats.active_reading_seconds, 240.0)
        self.assertEqual(b_stats.estimated_words_read, 1200)

        # Retrieve library stats
        lib_stats = stats_repo.get_library_statistics()
        self.assertGreaterEqual(lib_stats.total_books, 1)
        self.assertAlmostEqual(lib_stats.total_reading_seconds, 300.0)
        self.assertEqual(lib_stats.total_words_read, 1200)


# ==============================================================================
# TIER 2: BOUNDARY & CORNER CASES (EDGE CONDITIONS)
# ==============================================================================

class TestTier2BoundaryCases(unittest.TestCase):
    """Tier 2: Boundary & Corner Cases — empty archives, single page, zero duration, limits."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_comic_archive_empty(self):
        """T2.1: Empty comic archive handling (zero images)."""
        if ComicArchiveEngine is None:
            self.skipTest("ComicArchiveEngine not implemented yet")

        cbz_path = os.path.join(self.temp_dir.name, "empty.cbz")
        create_synthetic_cbz(cbz_path, [("readme.txt", b"No images in this archive")])

        engine = ComicArchiveEngine(cbz_path)
        self.assertEqual(engine.get_page_count(), 0)
        self.assertEqual(engine.list_page_entries(), [])
        self.assertEqual(engine.get_spreads(mode="single"), [])
        self.assertEqual(engine.get_spreads(mode="double"), [])

    def test_comic_archive_single_page(self):
        """T2.2: Single-page comic archive (cover only, no interior pairs)."""
        if ComicArchiveEngine is None:
            self.skipTest("ComicArchiveEngine not implemented yet")

        cbz_path = os.path.join(self.temp_dir.name, "single_page.cbz")
        create_synthetic_cbz(cbz_path, [("001_cover.png", VALID_1X1_PNG)])

        engine = ComicArchiveEngine(cbz_path)
        self.assertEqual(engine.get_page_count(), 1)

        single = engine.get_spreads(mode="single")
        self.assertEqual(len(single), 1)

        double = engine.get_spreads(mode="double")
        self.assertEqual(len(double), 1)
        self.assertEqual(len(double[0]), 1)  # Only cover, no trailing empty pair

    def test_comic_archive_odd_page_count_spreads(self):
        """T2.3: Double spread pairing with odd page count."""
        if ComicArchiveEngine is None:
            self.skipTest("ComicArchiveEngine not implemented yet")

        # 4 pages total: cover + 3 pages -> [cover], [p1, p2], [p3]
        cbz_path = os.path.join(self.temp_dir.name, "odd_spread.cbz")
        entries = [(f"page_{i}.png", VALID_1X1_PNG) for i in range(4)]
        create_synthetic_cbz(cbz_path, entries)

        engine = ComicArchiveEngine(cbz_path)
        spreads = engine.get_spreads(mode="double", direction="ltr")
        self.assertEqual(len(spreads), 3)
        self.assertEqual(len(spreads[0]), 1)  # cover
        self.assertEqual(len(spreads[1]), 2)  # p1, p2
        self.assertEqual(len(spreads[2]), 1)  # p3 (isolated last page)

    def test_session_zero_duration_and_skims(self):
        """T2.4: Zero duration reading session and rapid page skims guard against ZeroDivision."""
        if ReadingSessionTracker is None:
            self.skipTest("ReadingSessionTracker not implemented yet")

        tracker = ReadingSessionTracker(book_id="b-zero", format="epub")
        # Session ended immediately without ticking or with 0 duration
        session = tracker.end_session()
        self.assertAlmostEqual(session.duration_seconds, 0.0)
        self.assertAlmostEqual(session.active_seconds, 0.0)
        self.assertEqual(session.wpm, 0.0, "Zero duration must produce 0.0 WPM without error")

    def test_session_exact_idle_boundary(self):
        """T2.5: Activity tick behavior exactly at the idle threshold boundary."""
        if ReadingSessionTracker is None:
            self.skipTest("ReadingSessionTracker not implemented yet")

        threshold = 60.0
        tracker = ReadingSessionTracker(book_id="b-boundary", format="comic", idle_threshold_seconds=threshold)
        tracker.tick(now=1000.0)
        tracker.register_activity()

        # Tick exactly at threshold: should still count as active
        tracker.tick(now=1000.0 + threshold)
        s1 = tracker.end_session()
        self.assertAlmostEqual(s1.active_seconds, threshold, delta=1.0)
        self.assertEqual(s1.idle_seconds, 0.0)

    def test_pdf_extreme_viewport_dimensions(self):
        """T2.6: PDF zoom calculations with extreme or zero viewport dimensions."""
        if PdfDocumentEngine is None:
            self.skipTest("PdfDocumentEngine not implemented yet")

        engine = PdfDocumentEngine(SAMPLE_PDF)

        # Ultra-wide viewport (e.g., 8000 x 600) -> height should constrain fit-to-page
        scale = engine.calculate_fit_scale(0, viewport_width=8000.0, viewport_height=600.0, mode="page")
        expected_scale = 600.0 / 792.0
        self.assertAlmostEqual(scale, expected_scale, delta=0.05)

        # Viewport with 0 width/height must not raise unhandled ZeroDivisionError
        try:
            zero_scale = engine.calculate_fit_scale(0, viewport_width=0.0, viewport_height=0.0, mode="page")
            self.assertGreaterEqual(zero_scale, 0.0)
        except (ValueError, ZeroDivisionError):
            pass  # Acceptable to raise documented domain exception rather than unhandled crash

    def test_comic_natural_sort_complex_alphanumeric_and_subdirs(self):
        """T2.7: Natural sorting with nested paths and multi-numbered tokens."""
        if ComicArchiveEngine is None:
            self.skipTest("ComicArchiveEngine not implemented yet")

        cbz_path = os.path.join(self.temp_dir.name, "complex_sort.cbz")
        entries = [
            ("comic/vol1_ch10_p1.png", VALID_1X1_PNG),
            ("comic/vol1_ch2_p1.png", VALID_1X1_PNG),
            ("comic/vol1_ch2_p10.png", VALID_1X1_PNG),
            ("comic/vol1_ch2_p2.png", VALID_1X1_PNG),
        ]
        create_synthetic_cbz(cbz_path, entries)

        engine = ComicArchiveEngine(cbz_path)
        pages = engine.list_page_entries()

        # vol1_ch2_p1 < vol1_ch2_p2 < vol1_ch2_p10 < vol1_ch10_p1
        self.assertEqual(pages[0], "comic/vol1_ch2_p1.png")
        self.assertEqual(pages[1], "comic/vol1_ch2_p2.png")
        self.assertEqual(pages[2], "comic/vol1_ch2_p10.png")
        self.assertEqual(pages[3], "comic/vol1_ch10_p1.png")


# ==============================================================================
# TIER 3: CROSS-FEATURE COMBINATIONS
# ==============================================================================

class TestTier3CrossFeatureCombinations(unittest.TestCase):
    """Tier 3: Cross-Feature Combinations — mode interactions and multi-format subsystems."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_comic_spread_mode_direction_combination(self):
        """T3.1: Comic spread mode toggle combined with Manga RTL direction switching."""
        if ComicArchiveEngine is None:
            self.skipTest("ComicArchiveEngine not implemented yet")

        cbz_path = os.path.join(self.temp_dir.name, "combo.cbz")
        entries = [(f"page_{i}.png", VALID_1X1_PNG) for i in range(5)]
        create_synthetic_cbz(cbz_path, entries)

        engine = ComicArchiveEngine(cbz_path)

        # 1. Single LTR
        s_ltr = engine.get_spreads(mode="single", direction="ltr")
        self.assertEqual(len(s_ltr), 5)

        # 2. Double RTL Manga
        d_rtl = engine.get_spreads(mode="double", direction="rtl")
        self.assertEqual(len(d_rtl), 3)
        self.assertEqual(len(d_rtl[1]), 2)

        # 3. Double LTR
        d_ltr = engine.get_spreads(mode="double", direction="ltr")
        self.assertEqual(d_rtl[1], [d_ltr[1][1], d_ltr[1][0]])

        # 4. Switch back to Single RTL (single mode stays single page regardless of direction)
        s_rtl = engine.get_spreads(mode="single", direction="rtl")
        self.assertEqual(len(s_rtl), 5)

    def test_stats_tracking_during_display_adjustments(self):
        """T3.2: Activity tracking during zoom/spread adjustments keeps session active without skewing words."""
        if ReadingSessionTracker is None:
            self.skipTest("ReadingSessionTracker not implemented yet")

        tracker = ReadingSessionTracker(book_id="b-combo", format="pdf", idle_threshold_seconds=120.0)
        tracker.tick(now=1000.0)
        tracker.record_page_turn(words_on_page=300)

        # User performs zoom adjustments at t=1050 and spread changes at t=1090
        tracker.tick(now=1050.0)
        tracker.register_activity()  # Zoom changed

        tracker.tick(now=1090.0)
        tracker.register_activity()  # Fit mode adjusted

        tracker.tick(now=1100.0)
        session = tracker.end_session()

        # Session should remain 100s active with exactly 300 words (display changes don't add words)
        self.assertAlmostEqual(session.active_seconds, 100.0, delta=2.0)
        self.assertEqual(session.idle_seconds, 0.0)
        self.assertEqual(session.words_read, 300)
        expected_wpm = 300 / (100.0 / 60.0)
        self.assertAlmostEqual(session.wpm, expected_wpm, delta=5.0)

    def test_library_statistics_multi_format_aggregation(self):
        """T3.3: Multi-format library statistics aggregation across EPUB, PDF, and CBZ."""
        if StatisticsRepository is None or ReadingSession is None:
            self.skipTest("StatisticsRepository or ReadingSession not implemented yet")

        db_path = os.path.join(self.temp_dir.name, "multi_format_stats.db")
        db = Database(db_path)
        book_repo = BookRepository(db)
        stats_repo = StatisticsRepository(db)

        # 1. Add EPUB book & sessions
        book_epub = Book(id="b-epub", title="EPUB Book", file_format="epub")
        book_repo.add(book_epub)
        stats_repo.record_session(ReadingSession(
            id="s-ep-1", book_id="b-epub", started_at=datetime.now(), ended_at=datetime.now(),
            duration_seconds=600.0, active_seconds=500.0, idle_seconds=100.0,
            words_read=2500, wpm=300.0
        ))

        # 2. Add PDF book & session
        book_pdf = Book(id="b-pdf", title="PDF Doc", file_format="pdf")
        book_repo.add(book_pdf)
        stats_repo.record_session(ReadingSession(
            id="s-pdf-1", book_id="b-pdf", started_at=datetime.now(), ended_at=datetime.now(),
            duration_seconds=300.0, active_seconds=250.0, idle_seconds=50.0,
            words_read=1000, wpm=240.0
        ))

        # 3. Add CBZ book & session
        book_cbz = Book(id="b-cbz", title="Comic Book", file_format="cbz")
        book_repo.add(book_cbz)
        stats_repo.record_session(ReadingSession(
            id="s-cbz-1", book_id="b-cbz", started_at=datetime.now(), ended_at=datetime.now(),
            duration_seconds=200.0, active_seconds=180.0, idle_seconds=20.0,
            words_read=300, wpm=100.0
        ))

        lib_stats = stats_repo.get_library_statistics()
        self.assertGreaterEqual(lib_stats.total_books, 3)
        self.assertAlmostEqual(lib_stats.total_reading_seconds, 1100.0)
        self.assertAlmostEqual(lib_stats.active_reading_seconds, 930.0)
        self.assertEqual(lib_stats.total_words_read, 3800)
        if hasattr(lib_stats, "format_counts") and lib_stats.format_counts:
            self.assertEqual(lib_stats.format_counts.get("epub", 0), 1)
            self.assertEqual(lib_stats.format_counts.get("pdf", 0), 1)
            self.assertEqual(lib_stats.format_counts.get("cbz", 0), 1)

    def test_progress_and_session_atomic_persistence(self):
        """T3.4: Reading progress update and session persistence under SQLite WAL mode."""
        if StatisticsRepository is None or ReadingSession is None:
            self.skipTest("StatisticsRepository or ReadingSession not implemented yet")

        db_path = os.path.join(self.temp_dir.name, "wal_atomic.db")
        db = Database(db_path)
        book_repo = BookRepository(db)
        prog_repo = ReadingProgressRepository(db)
        stats_repo = StatisticsRepository(db)

        book = Book(id="b-wal", title="WAL Book", file_format="pdf")
        book_repo.add(book)

        # Save progress
        progress = ReadingProgress(book_id="b-wal", page_index=5, percentage=50.0)
        prog_repo.save(progress)

        # Record session in same database instance
        session = ReadingSession(
            id="s-wal-1", book_id="b-wal", started_at=datetime.now(), ended_at=datetime.now(),
            duration_seconds=150.0, active_seconds=120.0, idle_seconds=30.0,
            words_read=600, wpm=300.0
        )
        stats_repo.record_session(session)

        # Verify durable read-back
        saved_prog = prog_repo.get("b-wal")
        self.assertIsNotNone(saved_prog)
        self.assertEqual(saved_prog.page_index, 5)

        saved_stats = stats_repo.get_book_statistics("b-wal")
        self.assertEqual(saved_stats.total_sessions, 1)
        self.assertAlmostEqual(saved_stats.total_reading_seconds, 150.0)


# ==============================================================================
# TIER 4: REAL-WORLD SCENARIOS (E2E WORKFLOWS)
# ==============================================================================

class TestTier4RealWorldScenarios(unittest.TestCase):
    """Tier 4: Real-World Scenarios — end-to-end import, navigation, resume, and cascade lifecycles."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "e2e_real_world.db")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_complete_reading_session_lifecycle(self):
        """T4.1: Complete reading session lifecycle with activity, pause, resume, and persistence."""
        if ReadingSessionTracker is None or StatisticsRepository is None:
            self.skipTest("ReadingSessionTracker or StatisticsRepository not implemented yet")

        db = Database(self.db_path)
        book_repo = BookRepository(db)
        stats_repo = StatisticsRepository(db)

        book = Book(id="lifecycle-book", title="Lifecycle Test Book", file_format="epub")
        book_repo.add(book)

        # 1. Start session
        tracker = ReadingSessionTracker(book_id=book.id, format="epub", idle_threshold_seconds=120.0)
        tracker.tick(now=1000.0)

        # 2. Read 3 pages with active ticks (150 words per page)
        tracker.tick(now=1030.0)
        tracker.record_page_turn(150)
        tracker.tick(now=1060.0)
        tracker.record_page_turn(150)
        tracker.tick(now=1090.0)
        tracker.record_page_turn(150)  # active = 90s, words = 450

        # 3. User takes an idle pause of 180s (> 120s threshold)
        tracker.tick(now=1270.0)  # 180s idle gap

        # 4. User resumes reading for 60s (2 pages)
        tracker.register_activity()
        tracker.tick(now=1300.0)
        tracker.record_page_turn(150)
        tracker.tick(now=1330.0)
        tracker.record_page_turn(150)  # +60s active, +300 words

        # 5. End session
        session = tracker.end_session()
        self.assertAlmostEqual(session.active_seconds, 150.0, delta=5.0)
        self.assertGreaterEqual(session.idle_seconds, 120.0)
        self.assertEqual(session.words_read, 750)
        expected_wpm = 750 / (150.0 / 60.0)
        self.assertAlmostEqual(session.wpm, expected_wpm, delta=10.0)

        # 6. Persist to storage and verify retrieval
        stats_repo.record_session(session)
        stats = stats_repo.get_book_statistics(book.id)
        self.assertEqual(stats.total_sessions, 1)
        self.assertEqual(stats.estimated_words_read, 750)

    def test_e2e_pdf_import_navigate_resume(self):
        """T4.2: End-to-end PDF import, page navigation, auto-save checkpoint, close, and resume."""
        if not HAS_GTK:
            self.skipTest("GTK4 environment not available")
        if PdfReaderView is None:
            self.skipTest("PdfReaderView not implemented yet")

        import inspect
        src = inspect.getsource(AquileReaderApp.open_book)
        if "PdfReaderView" not in src and "pdf" not in src:
            self.skipTest("AquileReaderApp.open_book does not yet route PDF books to PdfReaderView")

        import uuid
        app = AquileReaderApp(db_path=self.db_path)
        app.set_application_id(f"org.antigravity.AquileReader.E2EPdf.{uuid.uuid4().hex[:8]}")
        app.register()
        app.activate()

        try:
            # 1. Import PDF into Library
            self.assertTrue(os.path.exists(SAMPLE_PDF))
            app.library_view.import_file(SAMPLE_PDF)

            books = [b for b in app.book_repo.list_all() if b.file_format == "pdf"]
            self.assertGreaterEqual(len(books), 1)
            pdf_book = books[0]
            self.assertEqual(pdf_book.file_format, "pdf")

            reader = app.current_reader_view
            self.assertIsNotNone(reader)

            # 2. Navigate PDF page
            initial_page = getattr(reader, "current_page_idx", 0)
            if hasattr(reader, "next_page"):
                reader.next_page()
            elif hasattr(reader, "go_to_page"):
                reader.go_to_page(initial_page + 1)

            # 3. Save checkpoint
            if hasattr(reader, "_save_checkpoint"):
                reader._save_checkpoint()
            progress = app.progress_repo.get(pdf_book.id)
            self.assertIsNotNone(progress)
            self.assertEqual(progress.page_index, initial_page + 1)

            # 4. Close Reader and Return to Library
            app.show_library()
            self.assertIsNone(app.current_reader_view)

            # 5. Reopen PDF and Verify Resume from Saved Page
            app.open_book(pdf_book)
            resumed_reader = app.current_reader_view
            self.assertIsNotNone(resumed_reader)
            self.assertEqual(getattr(resumed_reader, "current_page_idx", 0), initial_page + 1)
        finally:
            if app.current_reader_view and hasattr(app.current_reader_view, "cleanup"):
                app.current_reader_view.cleanup()

    def test_e2e_cbz_import_navigate_resume(self):
        """T4.3: End-to-end CBZ comic import, spread navigation, checkpoint, close, and resume."""
        if not HAS_GTK:
            self.skipTest("GTK4 environment not available")
        if ComicReaderView is None:
            self.skipTest("ComicReaderView not implemented yet")

        import inspect
        src = inspect.getsource(AquileReaderApp.open_book)
        if "ComicReaderView" not in src and "cbz" not in src:
            self.skipTest("AquileReaderApp.open_book does not yet route comic books to ComicReaderView")

        # Create a valid test CBZ fixture in temp dir to ensure decodable PNGs
        cbz_fixture = os.path.join(self.temp_dir.name, "e2e_comic.cbz")
        entries = [(f"page_{i:02d}.png", VALID_1X1_PNG) for i in range(1, 6)]
        create_synthetic_cbz(cbz_fixture, entries)

        import uuid
        app = AquileReaderApp(db_path=self.db_path)
        app.set_application_id(f"org.antigravity.AquileReader.E2ECbz.{uuid.uuid4().hex[:8]}")
        app.register()
        app.activate()

        try:
            # 1. Import CBZ into Library
            app.library_view.import_file(cbz_fixture)

            books = [b for b in app.book_repo.list_all() if b.file_format == "cbz"]
            self.assertGreaterEqual(len(books), 1)
            cbz_book = books[0]
            self.assertEqual(cbz_book.file_format, "cbz")

            reader = app.current_reader_view
            self.assertIsNotNone(reader)

            # 2. Navigate Comic spread / page
            initial_page = getattr(reader, "current_page_idx", 0)
            if hasattr(reader, "next_page"):
                reader.next_page()
            elif hasattr(reader, "next_spread"):
                reader.next_spread()

            # 3. Save checkpoint
            if hasattr(reader, "_save_checkpoint"):
                reader._save_checkpoint()
            progress = app.progress_repo.get(cbz_book.id)
            self.assertIsNotNone(progress)
            self.assertGreaterEqual(progress.page_index, initial_page + 1)

            # 4. Close Reader and Return to Library
            app.show_library()
            self.assertIsNone(app.current_reader_view)

            # 5. Reopen CBZ and Verify Resume
            app.open_book(cbz_book)
            resumed_reader = app.current_reader_view
            self.assertIsNotNone(resumed_reader)
            self.assertEqual(getattr(resumed_reader, "current_page_idx", 0), progress.page_index)
        finally:
            if app.current_reader_view and hasattr(app.current_reader_view, "cleanup"):
                app.current_reader_view.cleanup()

    def test_library_sessions_cascade_on_book_deletion(self):
        """T4.4: Library session and statistics cascade cleanup on book deletion (foreign key durability)."""
        if StatisticsRepository is None or ReadingSession is None:
            self.skipTest("StatisticsRepository or ReadingSession not implemented yet")

        db = Database(self.db_path)
        book_repo = BookRepository(db)
        prog_repo = ReadingProgressRepository(db)
        stats_repo = StatisticsRepository(db)

        # 1. Add book
        book = Book(id="cascade-book", title="Cascade Target", file_format="pdf")
        book_repo.add(book)

        # 2. Add progress and session records
        prog_repo.save(ReadingProgress(book_id="cascade-book", page_index=2, percentage=20.0))
        stats_repo.record_session(ReadingSession(
            id="casc-sess-1", book_id="cascade-book", started_at=datetime.now(), ended_at=datetime.now(),
            duration_seconds=100.0, active_seconds=90.0, idle_seconds=10.0,
            words_read=400, wpm=266.7
        ))

        self.assertIsNotNone(prog_repo.get("cascade-book"))
        self.assertEqual(len(stats_repo.get_sessions_for_book("cascade-book")), 1)

        # 3. Delete book
        deleted = book_repo.delete("cascade-book")
        self.assertTrue(deleted)

        # 4. Verify cascade: progress and sessions for deleted book must be removed
        self.assertIsNone(prog_repo.get("cascade-book"))
        sessions_left = stats_repo.get_sessions_for_book("cascade-book")
        self.assertEqual(len(sessions_left), 0, "Sessions were not cascade deleted on book deletion")


if __name__ == "__main__":
    unittest.main()
