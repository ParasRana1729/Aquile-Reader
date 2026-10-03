"""
Headless tests for the Aquile visual theme (B0 UI_RESEARCH sections 1, 6, 8).

- CSS class presence checks are pure file reads (fully headless).
- Widget tests construct StatisticsDialog (8 tile grid) and CollectionsView
  (groups/filter) and skip gracefully when no display is available.
"""

import os
import tempfile
import unittest

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..")
CSS_PATH = os.path.join(REPO_ROOT, "src", "aquile", "ui", "style.css")

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


def _can_show_gtk() -> bool:
    """True when GTK widgets can actually be instantiated (display present)."""
    if not HAS_GTK:
        return False
    try:
        from gi.repository import Gdk
        if Gdk.Display.get_default() is None:
            return False
        probe = Gtk.Label(label="probe")
        return probe is not None
    except Exception:
        return False


def _read_css() -> str:
    with open(CSS_PATH, "r", encoding="utf-8") as fh:
        return fh.read()


class TestAquileThemeCss(unittest.TestCase):
    """CSS contains the Aquile visual-theme classes (headless file checks)."""

    def test_css_accent_var(self):
        css = _read_css()
        self.assertIn("--aquile-accent", css)
        self.assertIn("#009688", css)

    def test_css_rail_classes(self):
        css = _read_css()
        self.assertIn(".aquile-rail", css)
        self.assertIn("#3A3A3A", css)
        self.assertIn(".rail-active", css)

    def test_css_cover_and_reader_chrome(self):
        css = _read_css()
        self.assertIn(".cover-card", css)
        self.assertIn(".reader-toolbar", css)
        self.assertIn(".reader-statusbar", css)

    def test_css_stat_tiles_and_collections(self):
        css = _read_css()
        self.assertIn(".stat-tile", css)
        self.assertIn(".stat-value", css)
        self.assertIn(".collections-group", css)
        self.assertIn("#3A3F4B", css)

    def test_css_page_themes_and_cream(self):
        css = _read_css()
        for theme in (
            ".page-theme-white",
            ".page-theme-silver",
            ".page-theme-sepia",
            ".page-theme-night",
            ".page-theme-solarized",
        ):
            self.assertIn(theme, css)
        # Sepia cream background support
        self.assertTrue("#F5EEDC" in css or "#f5eedc" in css.lower())


@unittest.skipUnless(HAS_GTK, "GTK4 / Libadwaita environment required")
class TestStatisticsTileGrid(unittest.TestCase):
    """Statistics dialog builds the B0 8-tile grid."""

    def setUp(self):
        if not _can_show_gtk():
            self.skipTest("no display available")
        from src.aquile.storage.database import Database
        from src.aquile.storage.repository import (
            BookRepository,
            ReadingProgressRepository,
            StatisticsRepository,
        )
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db = Database(os.path.join(self.temp_dir.name, "theme_stats.db"))
        self.book_repo = BookRepository(self.db)
        self.stats_repo = StatisticsRepository(self.db)
        self.progress_repo = ReadingProgressRepository(self.db)

    def tearDown(self):
        if hasattr(self, "temp_dir"):
            self.temp_dir.cleanup()

    def test_dialog_constructs_with_eight_tiles(self):
        from src.aquile.ui.statistics_dialog import StatisticsDialog
        dialog = StatisticsDialog(
            stats_repo=self.stats_repo,
            book_repo=self.book_repo,
            theme="dark",
        )
        self.assertEqual(dialog.get_title(), "Reading Statistics")
        tiles = getattr(dialog, "stat_tiles", None)
        self.assertIsNotNone(tiles)
        self.assertEqual(len(tiles), 8)
        expected = {
            "Number of books in library",
            "Number of books read",
            "Total reading hours",
            "Number of pages flipped",
            "Avg. reading hours per day",
            "Avg. reading time (sec) per page",
            "Reading speed (words per minute)",
            "Avg. number of pages flipped per hour",
        }
        self.assertEqual(set(tiles.keys()), expected)

    def test_tiles_reflect_library_data(self):
        from src.aquile.domain.models import (
            Book,
            ReadingProgress,
            ReadingSession,
        )
        from src.aquile.ui.statistics_dialog import StatisticsDialog
        from datetime import datetime, timezone
        self.book_repo.add(Book(id="t-1", title="T Book", file_format="epub"))
        self.progress_repo.save(ReadingProgress(book_id="t-1", percentage=100.0))
        now = datetime.now(timezone.utc)
        self.stats_repo.record_session(ReadingSession(
            id="ts-1", book_id="t-1", started_at=now, ended_at=now,
            duration_seconds=3600.0, active_seconds=3000.0, idle_seconds=600.0,
            words_read=25000, wpm=500.0,
        ))
        dialog = StatisticsDialog(
            stats_repo=self.stats_repo,
            book_repo=self.book_repo,
        )
        tiles = dialog.stat_tiles
        self.assertEqual(tiles["Number of books in library"].get_text(), "1")
        self.assertEqual(tiles["Number of books read"].get_text(), "1")
        # 25000 words / 250 wpp = 100 pages flipped
        self.assertEqual(tiles["Number of pages flipped"].get_text(), "100")
        self.assertEqual(
            tiles["Reading speed (words per minute)"].get_text(), "500"
        )


@unittest.skipUnless(HAS_GTK, "GTK4 / Libadwaita environment required")
class TestCollectionsView(unittest.TestCase):
    """CollectionsView groups annotations per book with type filtering."""

    def setUp(self):
        if not _can_show_gtk():
            self.skipTest("no display available")
        from src.aquile.storage.database import Database
        from src.aquile.storage.repository import (
            AnnotationRepository,
            BookRepository,
            ReadingProgressRepository,
        )
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db = Database(os.path.join(self.temp_dir.name, "theme_coll.db"))
        self.book_repo = BookRepository(self.db)
        self.ann_repo = AnnotationRepository(self.db)
        self.progress_repo = ReadingProgressRepository(self.db)

    def tearDown(self):
        if hasattr(self, "temp_dir"):
            self.temp_dir.cleanup()

    def _seed(self):
        from src.aquile.domain.models import Annotation, Book
        self.book_repo.add(Book(id="c-1", title="Coll Book", author="Auth"))
        self.ann_repo.add(Annotation(
            id="a-hl", book_id="c-1", chapter_index=0, cfi="sec-1",
            text_content="a highlighted passage", color="#FFEB3B",
        ))
        self.ann_repo.add(Annotation(
            id="a-note", book_id="c-1", chapter_index=1, cfi="sec-2",
            text_content="noted passage", note_text="my note",
        ))
        self.ann_repo.add(Annotation(
            id="a-bm", book_id="c-1", chapter_index=2,
            text_content="", color="#4CAF50",
        ))

    def test_groups_and_filter(self):
        from src.aquile.ui.collections_view import CollectionsView
        self._seed()
        jumps = []
        view = CollectionsView(
            self.book_repo, self.ann_repo, self.progress_repo,
            on_jump_to_book=lambda b, a: jumps.append((b, a)),
        )
        self.assertEqual(len(view.get_groups()), 1)
        self.assertIn("c-1", view.get_groups())
        self.assertEqual(len(view.get_visible_rows()), 3)

        view.set_filter("Notes")
        self.assertEqual(len(view.get_visible_rows()), 1)
        view.set_filter("Highlights")
        self.assertEqual(len(view.get_visible_rows()), 1)
        view.set_filter("Bookmarks")
        self.assertEqual(len(view.get_visible_rows()), 1)
        view.set_filter("All")
        self.assertEqual(len(view.get_visible_rows()), 3)

    def test_favorites_filter_and_jump_callback(self):
        from src.aquile.ui.collections_view import CollectionsView
        self._seed()
        jumps = []
        view = CollectionsView(
            self.book_repo, self.ann_repo, self.progress_repo,
            on_jump_to_book=lambda b, a: jumps.append((b, a)),
        )
        # No book carries a favorite flag yet -> favorites-only shows nothing.
        view.set_show_favorites(True)
        self.assertEqual(len(view.get_groups()), 0)
        view.set_show_favorites(False)
        self.assertEqual(len(view.get_groups()), 1)

        book, ann, row = view.get_visible_rows()[0]
        row.emit("activated")
        self.assertEqual(len(jumps), 1)
        self.assertEqual(jumps[0][0].id, "c-1")
        self.assertEqual(jumps[0][1].id, ann.id)


if __name__ == "__main__":
    unittest.main()
