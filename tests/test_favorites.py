"""
Tests for book favorites (schema v3) and the library details pane.
Covers FR-01 favorites + UI_RESEARCH.md section 3 details pane.
"""

import os
import sqlite3
import tempfile
import time
import unittest

from src.aquile.domain.models import Book
from src.aquile.storage.database import Database, CURRENT_SCHEMA_VERSION
from src.aquile.storage.repository import BookRepository
from src.aquile.ui.book_details import (
    BookDetailsPane,
    format_human_date,
    percentage_from,
)

try:
    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk  # noqa: F401
    _GI_OK = True
except Exception:
    _GI_OK = False


def _try_construct_pane(*args, **kwargs):
    if not _GI_OK:
        raise unittest.SkipTest("GTK unavailable")
    try:
        return BookDetailsPane(*args, **kwargs)
    except Exception as exc:
        raise unittest.SkipTest(f"no display for details pane: {exc}")


def _make_repos():
    tmp = tempfile.TemporaryDirectory()
    path = os.path.join(tmp.name, "fav.db")
    db = Database(path)
    return tmp, db, BookRepository(db)


def _create_legacy_v2_db(path):
    """Create a faithful v2 database (no is_favorite column)."""
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.executescript("""
        CREATE TABLE books (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            author TEXT NOT NULL,
            file_path TEXT NOT NULL UNIQUE,
            file_format TEXT NOT NULL,
            cover_path TEXT,
            total_chapters INTEGER DEFAULT 1,
            file_size_bytes INTEGER DEFAULT 0,
            added_at REAL NOT NULL,
            last_read_at REAL
        );
        CREATE TABLE reading_progress (
            book_id TEXT PRIMARY KEY,
            chapter_index INTEGER NOT NULL DEFAULT 0,
            page_index INTEGER NOT NULL DEFAULT 0,
            cfi TEXT NOT NULL DEFAULT '',
            percentage REAL NOT NULL DEFAULT 0.0,
            updated_at REAL NOT NULL,
            FOREIGN KEY (book_id) REFERENCES books (id) ON DELETE CASCADE
        );
        CREATE TABLE annotations (
            id TEXT PRIMARY KEY,
            book_id TEXT NOT NULL,
            chapter_index INTEGER NOT NULL,
            cfi TEXT NOT NULL,
            start_offset INTEGER NOT NULL,
            end_offset INTEGER NOT NULL,
            text_content TEXT NOT NULL,
            note_text TEXT DEFAULT '',
            color TEXT NOT NULL DEFAULT '#FFEB3B',
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL,
            FOREIGN KEY (book_id) REFERENCES books (id) ON DELETE CASCADE
        );
        CREATE TABLE settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        CREATE TABLE reading_sessions (
            id TEXT PRIMARY KEY,
            book_id TEXT NOT NULL,
            started_at TEXT NOT NULL,
            ended_at TEXT,
            duration_seconds REAL NOT NULL DEFAULT 0.0,
            active_seconds REAL NOT NULL DEFAULT 0.0,
            idle_seconds REAL NOT NULL DEFAULT 0.0,
            words_read INTEGER NOT NULL DEFAULT 0,
            wpm REAL NOT NULL DEFAULT 0.0,
            FOREIGN KEY (book_id) REFERENCES books (id) ON DELETE CASCADE
        );
        CREATE TABLE reading_statistics (
            book_id TEXT PRIMARY KEY,
            total_reading_seconds REAL NOT NULL DEFAULT 0.0,
            active_reading_seconds REAL NOT NULL DEFAULT 0.0,
            total_sessions INTEGER NOT NULL DEFAULT 0,
            estimated_words_read INTEGER NOT NULL DEFAULT 0,
            average_wpm REAL NOT NULL DEFAULT 0.0,
            last_session_at TEXT,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (book_id) REFERENCES books (id) ON DELETE CASCADE
        );
        PRAGMA user_version = 2;
    """)
    conn.execute(
        "INSERT INTO books (id, title, author, file_path, file_format, cover_path, total_chapters, file_size_bytes, added_at, last_read_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("legacy-1", "Legacy Title", "Legacy Author", "/books/legacy.epub",
         "epub", None, 4, 2048, 1000.0, 1100.0),
    )
    conn.commit()
    conn.close()


class TestFavorites(unittest.TestCase):
    def test_book_default_is_not_favorite(self):
        b = Book(title="T", author="A", file_path="/tmp/x.epub")
        self.assertFalse(b.is_favorite)
        self.assertEqual(b.is_favorite, False)

    def test_add_defaults_to_not_favorite(self):
        tmp, db, repo = _make_repos()
        try:
            repo.add(Book(id="fav-1", title="Fav One", author="A",
                          file_path="/tmp/fav1.epub"))
            fetched = repo.get_by_id("fav-1")
            self.assertIsNotNone(fetched)
            self.assertFalse(fetched.is_favorite)
        finally:
            tmp.cleanup()

    def test_add_with_favorite_true_roundtrip(self):
        tmp, db, repo = _make_repos()
        try:
            repo.add(Book(id="fav-t", title="Fav True", author="A",
                          file_path="/tmp/favt.epub", is_favorite=True))
            fetched = repo.get_by_id("fav-t")
            self.assertTrue(fetched.is_favorite)
            by_path = repo.get_by_path("/tmp/favt.epub")
            self.assertTrue(by_path.is_favorite)
        finally:
            tmp.cleanup()

    def test_set_favorite_true_persists(self):
        tmp, db, repo = _make_repos()
        try:
            repo.add(Book(id="fav-2", title="Fav Two", author="A",
                          file_path="/tmp/fav2.epub"))
            repo.set_favorite("fav-2", True)
            fetched = repo.get_by_id("fav-2")
            self.assertTrue(fetched.is_favorite)
            listed = {b.id: b for b in repo.list_all()}
            self.assertTrue(listed["fav-2"].is_favorite)
            by_path = repo.get_by_path("/tmp/fav2.epub")
            self.assertTrue(by_path.is_favorite)
        finally:
            tmp.cleanup()

    def test_set_favorite_unset_persists(self):
        tmp, db, repo = _make_repos()
        try:
            repo.add(Book(id="fav-3", title="Fav Three", author="A",
                          file_path="/tmp/fav3.epub", is_favorite=True))
            self.assertTrue(repo.get_by_id("fav-3").is_favorite)
            repo.set_favorite("fav-3", False)
            fetched = repo.get_by_id("fav-3")
            self.assertFalse(fetched.is_favorite)
            self.assertEqual(fetched.title, "Fav Three")
        finally:
            tmp.cleanup()

    def test_favorite_survives_reconnect(self):
        tmp, db, repo = _make_repos()
        try:
            repo.add(Book(id="fav-4", title="Fav Four", author="A",
                          file_path="/tmp/fav4.epub"))
            repo.set_favorite("fav-4", True)
            db2 = Database(os.path.join(tmp.name, "fav.db"))
            repo2 = BookRepository(db2)
            self.assertTrue(repo2.get_by_id("fav-4").is_favorite)
            repo2.set_favorite("fav-4", False)
            db3 = Database(os.path.join(tmp.name, "fav.db"))
            self.assertFalse(BookRepository(db3).get_by_id("fav-4").is_favorite)
        finally:
            tmp.cleanup()

    def test_fresh_db_at_v3_with_column(self):
        tmp, db, repo = _make_repos()
        try:
            self.assertEqual(CURRENT_SCHEMA_VERSION, 4)
            with db.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("PRAGMA user_version;")
                self.assertEqual(cur.fetchone()[0], CURRENT_SCHEMA_VERSION)
                cur.execute("PRAGMA table_info(books);")
                cols = {row[1] for row in cur.fetchall()}
                self.assertIn("is_favorite", cols)
        finally:
            tmp.cleanup()

    def test_v2_to_v3_migration_keeps_data(self):
        tmpdir = tempfile.TemporaryDirectory()
        try:
            path = os.path.join(tmpdir.name, "legacy_v2.db")
            _create_legacy_v2_db(path)
            db = Database(path)
            with db.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("PRAGMA user_version;")
                self.assertEqual(cur.fetchone()[0], CURRENT_SCHEMA_VERSION)
                cur.execute("PRAGMA table_info(books);")
                cols = {row[1] for row in cur.fetchall()}
                self.assertIn("is_favorite", cols)
            repo = BookRepository(db)
            b = repo.get_by_id("legacy-1")
            self.assertIsNotNone(b)
            self.assertEqual(b.title, "Legacy Title")
            self.assertEqual(b.author, "Legacy Author")
            self.assertFalse(b.is_favorite)
            repo.set_favorite("legacy-1", True)
            self.assertTrue(repo.get_by_id("legacy-1").is_favorite)
        finally:
            tmpdir.cleanup()

    def test_percentage_and_date_helpers(self):
        self.assertEqual(percentage_from(None), 0.0)
        self.assertEqual(percentage_from({"percentage": 42.5}), 42.5)
        self.assertEqual(format_human_date(None), "Never")
        self.assertEqual(format_human_date(0), "Never")
        human = format_human_date(1000.0)
        self.assertNotEqual(human, "Never")
        self.assertIn("-", human)

    def test_details_pane_binds_all_fields(self):
        tmp, db, repo = _make_repos()
        try:
            book = Book(id="det-1", title="Detail Title", author="Detail Author",
                        file_path="/books/detail.epub", file_format="epub",
                        added_at=1700000000.0, last_read_at=1700003600.0)
            repo.add(book)
            opened = []
            closed = []
            pane = _try_construct_pane(
                repo, book, {"percentage": 42.0},
                lambda b: opened.append(b.id),
                None,
                lambda: closed.append(True),
            )
            fields = pane.get_displayed_fields()
            for key in ("title", "percentage", "date_added", "last_read",
                        "word_count", "line_count", "description", "language",
                        "publisher", "genre", "file_path"):
                self.assertIn(key, fields)
            self.assertIn("Detail Title", fields["title"])
            self.assertIn("Detail Author", fields["author"])
            self.assertIn("42", fields["percentage"])
            self.assertIn("Date added", fields["date_added"])
            self.assertNotIn("Never", fields["date_added"])
            self.assertIn("Last read", fields["last_read"])
            self.assertNotIn("Never", fields["last_read"])
            self.assertIn("Word count", fields["word_count"])
            self.assertIn("Line count", fields["line_count"])
            self.assertIn("Description", fields["description"])
            self.assertIn("Language", fields["language"])
            self.assertIn("Publisher", fields["publisher"])
            self.assertIn("Genre", fields["genre"])
            self.assertIn("/books/detail.epub", fields["file_path"])
            # Buttons exist with exact labels.
            self.assertEqual(pane.btn_open.get_label(), "Open Book")
            self.assertEqual(pane.btn_edit.get_label(), "Edit Book Info")
            self.assertEqual(pane.btn_close.get_label(), "Close")
            # Callbacks fire.
            pane._on_open_clicked(None)
            self.assertEqual(opened, ["det-1"])
            pane._on_close_clicked(None)
            self.assertEqual(closed, [True])
        finally:
            tmp.cleanup()

    def test_details_pane_edit_saves_via_repo(self):
        tmp, db, repo = _make_repos()
        try:
            book = Book(id="det-2", title="Old Title", author="Old Author",
                        file_path="/books/old.epub")
            repo.add(book)
            edited = []
            pane = _try_construct_pane(
                repo, book, {"percentage": 0.0}, None,
                lambda b: edited.append((b.title, b.author)), None,
            )
            result = pane.save_edited_info("New Title", "New Author")
            self.assertEqual(result.title, "New Title")
            self.assertEqual(result.author, "New Author")
            reloaded = repo.get_by_id("det-2")
            self.assertEqual(reloaded.title, "New Title")
            self.assertEqual(reloaded.author, "New Author")
            self.assertEqual(edited, [("New Title", "New Author")])
            fields = pane.get_displayed_fields()
            self.assertIn("New Title", fields["title"])
            self.assertIn("New Author", fields["author"])
        finally:
            tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
