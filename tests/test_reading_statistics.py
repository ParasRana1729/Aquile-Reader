"""
Comprehensive Unit Tests for ReadingSessionTracker and StatisticsDialog (WP-11).
Tests cover:
- ReadingSessionTracker: session start/stop, active duration accumulation, idle filtering (120s text / 60s comics),
  word estimation across formats (EPUB, PDF, Comic), WPM computation with duration guard (<10s) and upper clamp (1200 WPM).
- StatisticsDialog: data binding for Library Overview and Book Insights, book selection switching,
  recent session history, and application theming (Light, Dark, Sepia).
"""

import os
import tempfile
import unittest
from datetime import datetime, timezone

# GTK and Libadwaita initialization
try:
    import gi
    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")
    from gi.repository import Gtk, Adw
    HAS_GTK = True
    try:
        Gtk.init()
    except Exception:
        pass
except (ImportError, ValueError):
    HAS_GTK = False

from src.aquile.domain.models import Book, ReadingProgress, ReadingSession, AppSettings
from src.aquile.storage.database import Database
from src.aquile.storage.repository import BookRepository, ReadingProgressRepository, StatisticsRepository
from src.aquile.reader.session_tracker import ReadingSessionTracker, estimate_words_for_page
from src.aquile.ui.statistics_dialog import StatisticsDialog, format_duration


class TestReadingSessionTracker(unittest.TestCase):
    """Unit tests for ReadingSessionTracker activity engine and metrics."""

    def test_default_idle_thresholds_by_format(self):
        """Text formats (epub, pdf) default to 120s; comic formats (cbz, cbr) default to 60s."""
        t_epub = ReadingSessionTracker("b-1", format="epub")
        self.assertEqual(t_epub.idle_threshold_seconds, 120.0)

        t_pdf = ReadingSessionTracker("b-2", format="pdf")
        self.assertEqual(t_pdf.idle_threshold_seconds, 120.0)

        t_cbz = ReadingSessionTracker("b-3", format="cbz")
        self.assertEqual(t_cbz.idle_threshold_seconds, 60.0)

        t_cbr = ReadingSessionTracker("b-4", format="cbr")
        self.assertEqual(t_cbr.idle_threshold_seconds, 60.0)

        t_comic = ReadingSessionTracker("b-5", format="comic")
        self.assertEqual(t_comic.idle_threshold_seconds, 60.0)

        # Explicit override
        t_custom = ReadingSessionTracker("b-6", format="epub", idle_threshold_seconds=45.0)
        self.assertEqual(t_custom.idle_threshold_seconds, 45.0)

    def test_active_duration_accumulation(self):
        """Regular ticks within threshold accumulate active reading duration."""
        tracker = ReadingSessionTracker("b-act", format="epub", idle_threshold_seconds=120.0)
        tracker.tick(now=1000.0)
        tracker.register_activity()
        tracker.tick(now=1015.0)
        tracker.register_activity()
        tracker.tick(now=1030.0)
        tracker.register_activity()
        tracker.tick(now=1045.0)

        session = tracker.end_session()
        self.assertEqual(session.book_id, "b-act")
        self.assertAlmostEqual(session.duration_seconds, 45.0)
        self.assertAlmostEqual(session.active_seconds, 45.0)
        self.assertEqual(session.idle_seconds, 0.0)

    def test_idle_filtering_text_format(self):
        """Text format filters pause > 120s into idle_seconds without adding to active_seconds."""
        tracker = ReadingSessionTracker("b-text-idle", format="epub", idle_threshold_seconds=120.0)
        tracker.tick(now=1000.0)
        tracker.register_activity()
        tracker.tick(now=1040.0)  # +40s active

        # User walks away for 160s (> 120s)
        tracker.tick(now=1200.0)

        session = tracker.end_session()
        self.assertAlmostEqual(session.active_seconds, 40.0)
        self.assertAlmostEqual(session.idle_seconds, 160.0)
        self.assertAlmostEqual(session.duration_seconds, 200.0)

    def test_idle_filtering_comic_format(self):
        """Comic format filters pause > 60s into idle_seconds."""
        tracker = ReadingSessionTracker("b-comic-idle", format="cbz", idle_threshold_seconds=60.0)
        tracker.tick(now=500.0)
        tracker.register_activity()
        tracker.tick(now=525.0)  # +25s active

        # Pause for 90s (> 60s)
        tracker.tick(now=615.0)

        session = tracker.end_session()
        self.assertAlmostEqual(session.active_seconds, 25.0)
        self.assertAlmostEqual(session.idle_seconds, 90.0)
        self.assertAlmostEqual(session.duration_seconds, 115.0)

    def test_idle_boundary_conditions(self):
        """Ticks exactly at threshold are active; ticks exceeding threshold become idle."""
        threshold = 60.0

        # Exactly at boundary
        t_bound = ReadingSessionTracker("b-bound", format="cbz", idle_threshold_seconds=threshold)
        t_bound.tick(now=1000.0)
        t_bound.register_activity()
        t_bound.tick(now=1000.0 + threshold)
        s_bound = t_bound.end_session()
        self.assertAlmostEqual(s_bound.active_seconds, threshold)
        self.assertEqual(s_bound.idle_seconds, 0.0)

        # Above boundary
        t_over = ReadingSessionTracker("b-over", format="cbz", idle_threshold_seconds=threshold)
        t_over.tick(now=1000.0)
        t_over.register_activity()
        t_over.tick(now=1000.0 + threshold + 10.0)  # 70s > 60s
        s_over = t_over.end_session()
        self.assertEqual(s_over.active_seconds, 0.0)
        self.assertAlmostEqual(s_over.idle_seconds, 70.0)

    def test_register_activity_resumes_active_reading(self):
        """Calling register_activity resets the idle timer and subsequent ticks are active."""
        tracker = ReadingSessionTracker("b-resume", format="epub", idle_threshold_seconds=120.0)
        tracker.tick(now=1000.0)
        tracker.register_activity()
        tracker.tick(now=1030.0)  # +30s active

        # Idle pause of 200s
        tracker.tick(now=1230.0)  # +200s idle

        # User interaction resumes
        tracker.register_activity()
        tracker.tick(now=1260.0)  # +30s active

        session = tracker.end_session()
        self.assertAlmostEqual(session.active_seconds, 60.0)
        self.assertAlmostEqual(session.idle_seconds, 200.0)
        self.assertAlmostEqual(session.duration_seconds, 260.0)

    def test_record_page_turn_words_and_activity(self):
        """record_page_turn increments words_read and resets activity timestamp."""
        tracker = ReadingSessionTracker("b-pages", format="epub", idle_threshold_seconds=120.0)
        tracker.tick(now=1000.0)
        tracker.record_page_turn(words_on_page=220)
        tracker.tick(now=1030.0)
        tracker.record_page_turn(words_on_page=180)
        tracker.tick(now=1060.0)

        session = tracker.end_session()
        self.assertEqual(session.words_read, 400)
        self.assertAlmostEqual(session.active_seconds, 60.0)
        self.assertEqual(session.idle_seconds, 0.0)

    def test_estimate_words_for_page(self):
        """Word estimation handles EPUB tokenization, PDF text/250wpp, and Comic 50wpp."""
        # 1. EPUB: tokenization of words and HTML cleanup
        epub_text = "<p>The quick brown fox jumps over the lazy dog.</p>"
        self.assertEqual(estimate_words_for_page("epub", epub_text), 9)
        self.assertEqual(estimate_words_for_page("epub", ""), 0)
        self.assertEqual(estimate_words_for_page("epub", None), 0)

        # Static method call on class
        self.assertEqual(ReadingSessionTracker.estimate_words_for_page("epub", "One two three"), 3)

        # 2. PDF: extracted text or 250 typographic default
        self.assertEqual(estimate_words_for_page("pdf", "Chapter 1: An introduction to Linux systems."), 7)
        self.assertEqual(estimate_words_for_page("pdf", None), 250)
        self.assertEqual(estimate_words_for_page("pdf", ""), 250)
        self.assertEqual(estimate_words_for_page("pdf", "   \n\t  "), 250)

        # 3. Comic (CBZ/CBR): 50 words default
        self.assertEqual(estimate_words_for_page("cbz", None), 50)
        self.assertEqual(estimate_words_for_page("cbz", "POW! BAM!"), 50)
        self.assertEqual(estimate_words_for_page("cbr", None), 50)
        self.assertEqual(estimate_words_for_page("comic", None), 50)

    def test_wpm_calculation_and_guards(self):
        """WPM computation includes >=10s active duration guard and 1200 WPM upper clamp."""
        # 1. Active duration < 10.0s guard: WPM must be 0.0
        t_short = ReadingSessionTracker("b-short", format="epub")
        t_short.tick(now=1000.0)
        t_short.record_page_turn(300)
        t_short.tick(now=1008.0)  # 8s active (< 10s)
        s_short = t_short.end_session()
        self.assertEqual(s_short.wpm, 0.0)

        # 2. Zero words read: WPM must be 0.0
        t_nowords = ReadingSessionTracker("b-nowords", format="epub")
        t_nowords.tick(now=1000.0)
        t_nowords.tick(now=1030.0)  # 30s active, 0 words
        s_nowords = t_nowords.end_session()
        self.assertEqual(s_nowords.wpm, 0.0)

        # 3. Normal reading speed: 450 words in 90 seconds (1.5 min) = 300.0 WPM
        t_normal = ReadingSessionTracker("b-norm", format="epub")
        t_normal.tick(now=1000.0)
        t_normal.record_page_turn(450)
        t_normal.tick(now=1090.0)  # 90s active
        s_normal = t_normal.end_session()
        self.assertAlmostEqual(s_normal.wpm, 300.0)

        # 4. Outlier skimming speed upper clamp: 3000 words in 30 seconds = 6000 WPM -> clamped to 1200 WPM
        t_fast = ReadingSessionTracker("b-fast", format="epub")
        t_fast.tick(now=1000.0)
        t_fast.record_page_turn(3000)
        t_fast.tick(now=1030.0)  # 30s active
        s_fast = t_fast.end_session()
        self.assertEqual(s_fast.wpm, 1200.0)

    def test_session_zero_duration_corner_case(self):
        """Zero duration session without ticking returns clean session without error."""
        tracker = ReadingSessionTracker("b-zero", format="pdf")
        session = tracker.end_session()
        self.assertEqual(session.duration_seconds, 0.0)
        self.assertEqual(session.active_seconds, 0.0)
        self.assertEqual(session.idle_seconds, 0.0)
        self.assertEqual(session.words_read, 0)
        self.assertEqual(session.wpm, 0.0)
        self.assertIsInstance(session.started_at, datetime)
        self.assertIsInstance(session.ended_at, datetime)


@unittest.skipUnless(HAS_GTK, "GTK4 / Libadwaita environment required for dialog tests")
class TestStatisticsDialogDataBinding(unittest.TestCase):
    """Unit tests for StatisticsDialog UI components, data binding, and theme sync."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_stats_ui.db")
        self.db = Database(self.db_path)
        self.book_repo = BookRepository(self.db)
        self.progress_repo = ReadingProgressRepository(self.db)
        self.stats_repo = StatisticsRepository(self.db)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_format_duration_helper(self):
        """format_duration handles zero, seconds, minutes, and hours accurately."""
        self.assertEqual(format_duration(0), "0s")
        self.assertEqual(format_duration(-10), "0s")
        self.assertEqual(format_duration(42), "42s")
        self.assertEqual(format_duration(135), "2m 15s")
        self.assertEqual(format_duration(3600), "1h 0m")
        self.assertEqual(format_duration(3665), "1h 1m 5s")
        self.assertEqual(format_duration(7320), "2h 2m")

    def test_dialog_empty_library(self):
        """Dialog initializes with zero states and empty messages when library is empty."""
        dialog = StatisticsDialog(
            stats_repo=self.stats_repo,
            book_repo=self.book_repo,
            theme="light",
        )
        self.assertEqual(dialog.get_title(), "Reading Statistics")
        self.assertEqual(dialog.get_theme(), "light")
        self.assertTrue(dialog.has_css_class("aquile-theme-light"))

        metrics = dialog.get_library_metrics()
        self.assertEqual(metrics["total_books"], 0)
        self.assertEqual(metrics["books_in_progress"], 0)
        self.assertEqual(metrics["books_completed"], 0)
        self.assertEqual(metrics["total_reading_seconds"], 0.0)
        self.assertEqual(metrics["active_reading_seconds"], 0.0)
        self.assertEqual(metrics["total_words_read"], 0)
        self.assertEqual(metrics["average_wpm"], 0.0)
        self.assertEqual(metrics["format_counts"], {})

        # Subtitle verification
        self.assertEqual(dialog.row_total_books.get_subtitle(), "0")
        self.assertEqual(dialog.row_total_reading_time.get_subtitle(), "0s")
        self.assertEqual(dialog.row_total_words.get_subtitle(), "0 words")

        # Book insights empty verification
        book_metrics = dialog.get_selected_book_metrics()
        self.assertIsNone(book_metrics["book_id"])
        self.assertEqual(book_metrics["total_reading_seconds"], 0.0)
        self.assertEqual(len(dialog.get_recent_sessions()), 0)

    def test_dialog_library_overview_data_binding(self):
        """Populated library statistics correctly bind to the Library Overview UI tab."""
        # 1. Add books across multiple formats
        b1 = Book(id="bk-epub", title="EPUB Novel", author="Author A", file_format="epub")
        b2 = Book(id="bk-pdf", title="Technical Manual", author="Author B", file_format="pdf")
        b3 = Book(id="bk-cbz", title="Hero Comic", author="Artist C", file_format="cbz")
        self.book_repo.add(b1)
        self.book_repo.add(b2)
        self.book_repo.add(b3)

        # 2. Add progress (b1 completed, b2 in progress)
        self.progress_repo.save(ReadingProgress(book_id="bk-epub", percentage=100.0))
        self.progress_repo.save(ReadingProgress(book_id="bk-pdf", percentage=45.0))

        # 3. Record reading sessions
        now = datetime.now(timezone.utc)
        self.stats_repo.record_session(ReadingSession(
            id="s1", book_id="bk-epub", started_at=now, ended_at=now,
            duration_seconds=600.0, active_seconds=500.0, idle_seconds=100.0,
            words_read=2500, wpm=300.0
        ))
        self.stats_repo.record_session(ReadingSession(
            id="s2", book_id="bk-pdf", started_at=now, ended_at=now,
            duration_seconds=300.0, active_seconds=250.0, idle_seconds=50.0,
            words_read=1000, wpm=240.0
        ))

        dialog = StatisticsDialog(
            stats_repo=self.stats_repo,
            book_repo=self.book_repo,
            theme="dark",
        )

        metrics = dialog.get_library_metrics()
        self.assertEqual(metrics["total_books"], 3)
        self.assertEqual(metrics["books_completed"], 1)
        self.assertEqual(metrics["books_in_progress"], 1)
        self.assertAlmostEqual(metrics["total_reading_seconds"], 900.0)
        self.assertAlmostEqual(metrics["active_reading_seconds"], 750.0)
        self.assertEqual(metrics["total_words_read"], 3500)
        # Average WPM = 3500 / (750 / 60) = 280.0
        self.assertAlmostEqual(metrics["average_wpm"], 280.0, delta=1.0)
        self.assertEqual(metrics["format_counts"], {"epub": 1, "pdf": 1, "cbz": 1})

        # Verify UI rows match formatted data
        self.assertEqual(dialog.row_total_books.get_subtitle(), "3")
        self.assertEqual(dialog.row_books_completed.get_subtitle(), "1")
        self.assertEqual(dialog.row_books_in_progress.get_subtitle(), "1")
        self.assertEqual(dialog.row_total_reading_time.get_subtitle(), format_duration(900.0))
        self.assertEqual(dialog.row_active_reading_time.get_subtitle(), format_duration(750.0))
        self.assertEqual(dialog.row_total_words.get_subtitle(), "3,500 words")

        # Format distribution rows
        self.assertEqual(len(dialog._format_rows), 3)

    def test_dialog_book_insights_selection_and_sessions(self):
        """Selecting different books updates Book Insights metrics and session history."""
        b1 = Book(id="b-1", title="First Book", author="Writer One", file_format="epub")
        b2 = Book(id="b-2", title="Second Book", author="Writer Two", file_format="pdf")
        self.book_repo.add(b1)
        self.book_repo.add(b2)

        from datetime import timedelta
        now = datetime.now(timezone.utc)
        # 2 sessions for b1
        self.stats_repo.record_session(ReadingSession(
            id="sess-b1-1", book_id="b-1", started_at=now, ended_at=now + timedelta(seconds=400),
            duration_seconds=400.0, active_seconds=300.0, idle_seconds=100.0,
            words_read=1500, wpm=300.0
        ))
        self.stats_repo.record_session(ReadingSession(
            id="sess-b1-2", book_id="b-1", started_at=now + timedelta(seconds=600), ended_at=now + timedelta(seconds=800),
            duration_seconds=200.0, active_seconds=180.0, idle_seconds=20.0,
            words_read=900, wpm=300.0
        ))

        # 1 session for b2
        self.stats_repo.record_session(ReadingSession(
            id="sess-b2-1", book_id="b-2", started_at=now, ended_at=now,
            duration_seconds=120.0, active_seconds=100.0, idle_seconds=20.0,
            words_read=400, wpm=240.0
        ))

        dialog = StatisticsDialog(
            stats_repo=self.stats_repo,
            book_repo=self.book_repo,
        )

        # 1. Select b-1
        self.assertTrue(dialog.select_book("b-1"))
        b1_metrics = dialog.get_selected_book_metrics()
        self.assertEqual(b1_metrics["book_id"], "b-1")
        self.assertEqual(b1_metrics["total_sessions"], 2)
        self.assertAlmostEqual(b1_metrics["total_reading_seconds"], 600.0)
        self.assertAlmostEqual(b1_metrics["active_reading_seconds"], 480.0)
        self.assertEqual(b1_metrics["estimated_words_read"], 2400)
        self.assertAlmostEqual(b1_metrics["average_wpm"], 300.0)

        # Recent sessions for b-1
        sessions_b1 = dialog.get_recent_sessions()
        self.assertEqual(len(sessions_b1), 2)
        self.assertEqual(sessions_b1[0].id, "sess-b1-2")

        # 2. Switch to b-2
        self.assertTrue(dialog.select_book("b-2"))
        b2_metrics = dialog.get_selected_book_metrics()
        self.assertEqual(b2_metrics["book_id"], "b-2")
        self.assertEqual(b2_metrics["total_sessions"], 1)
        self.assertAlmostEqual(b2_metrics["total_reading_seconds"], 120.0)
        self.assertAlmostEqual(b2_metrics["active_reading_seconds"], 100.0)
        self.assertEqual(b2_metrics["estimated_words_read"], 400)

        sessions_b2 = dialog.get_recent_sessions()
        self.assertEqual(len(sessions_b2), 1)
        self.assertEqual(sessions_b2[0].id, "sess-b2-1")

    def test_dialog_initial_book_routing(self):
        """Passing initial_book_id automatically opens and focuses that book in Book Insights."""
        b1 = Book(id="b-initial", title="Initial Targeted Book", file_format="epub")
        self.book_repo.add(b1)

        dialog = StatisticsDialog(
            stats_repo=self.stats_repo,
            book_repo=self.book_repo,
            initial_book_id="b-initial",
        )

        self.assertEqual(dialog.view_stack.get_visible_child_name(), "insights")
        self.assertEqual(dialog.selected_book.id, "b-initial")

    def test_dialog_theme_switching(self):
        """Theme switcher applies matching CSS classes for Light, Dark, and Sepia."""
        settings = AppSettings(theme="sepia")
        dialog = StatisticsDialog(
            stats_repo=self.stats_repo,
            book_repo=self.book_repo,
            settings=settings,
        )

        # Starts with sepia
        self.assertEqual(dialog.get_theme(), "sepia")
        self.assertTrue(dialog.has_css_class("aquile-theme-sepia"))
        self.assertFalse(dialog.has_css_class("aquile-theme-light"))

        # Switch to dark
        dialog.set_theme("dark")
        self.assertEqual(dialog.get_theme(), "dark")
        self.assertTrue(dialog.has_css_class("aquile-theme-dark"))
        self.assertFalse(dialog.has_css_class("aquile-theme-sepia"))

        # Switch to light
        dialog.set_theme("light")
        self.assertEqual(dialog.get_theme(), "light")
        self.assertTrue(dialog.has_css_class("aquile-theme-light"))
        self.assertFalse(dialog.has_css_class("aquile-theme-dark"))


if __name__ == "__main__":
    unittest.main()
