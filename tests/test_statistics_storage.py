"""
Unit tests for reading statistics storage and SQLite schema v2 migration.
Validates R3, R4, NFR-01, NFR-02, and FR-15.
"""

import os
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone, timedelta

from src.aquile.domain.models import (
    Book, ReadingProgress, Annotation, AppSettings,
    ReadingSession, BookStatistics, LibraryStatistics
)
from src.aquile.storage.database import Database, CURRENT_SCHEMA_VERSION
from src.aquile.storage.repository import (
    BookRepository, ReadingProgressRepository, AnnotationRepository,
    SettingsRepository, StatisticsRepository
)


class TestStatisticsStorage(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_stats.db")
        self.db = Database(self.db_path)
        self.book_repo = BookRepository(self.db)
        self.progress_repo = ReadingProgressRepository(self.db)
        self.ann_repo = AnnotationRepository(self.db)
        self.settings_repo = SettingsRepository(self.db)
        self.stats_repo = StatisticsRepository(self.db)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_fresh_database_initialization_to_v2(self):
        """Verify that a brand new database initializes directly to the current schema with WAL mode."""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA user_version;")
            version = cursor.fetchone()[0]
            self.assertEqual(version, CURRENT_SCHEMA_VERSION)
            self.assertEqual(CURRENT_SCHEMA_VERSION, 3)

            cursor.execute("PRAGMA journal_mode;")
            journal_mode = cursor.fetchone()[0].lower()
            self.assertEqual(journal_mode, "wal")

            cursor.execute("PRAGMA foreign_keys;")
            foreign_keys = cursor.fetchone()[0]
            self.assertEqual(foreign_keys, 1)

            # Check that all tables exist
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = {row[0] for row in cursor.fetchall()}
            expected_tables = {
                "books", "reading_progress", "annotations", "settings",
                "reading_sessions", "reading_statistics"
            }
            self.assertTrue(expected_tables.issubset(tables))

            # Check indices exist
            cursor.execute("SELECT name FROM sqlite_master WHERE type='index';")
            indices = {row[0] for row in cursor.fetchall()}
            self.assertIn("idx_reading_sessions_book_id", indices)
            self.assertIn("idx_reading_sessions_started_at", indices)
            self.assertIn("idx_reading_sessions_book_started", indices)
            self.assertIn("idx_reading_statistics_book_id", indices)

    def test_schema_migration_v1_to_v2(self):
        """Verify seamless migration from schema v1 to v2 while preserving all existing data."""
        migration_db_path = os.path.join(self.temp_dir.name, "legacy_v1.db")

        # Create pure v1 database manually
        conn = sqlite3.connect(migration_db_path)
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA foreign_keys = ON;")
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

            PRAGMA user_version = 1;
        """)
        # Insert pre-existing v1 data
        conn.execute(
            "INSERT INTO books VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("v1-book", "Legacy v1 Title", "Legacy Author", "/path/legacy.epub", "epub", None, 3, 1024, 1000.0, 1050.0)
        )
        conn.execute(
            "INSERT INTO reading_progress VALUES (?, ?, ?, ?, ?, ?)",
            ("v1-book", 1, 5, "epubcfi(/6/2)", 42.0, 1050.0)
        )
        conn.execute(
            "INSERT INTO annotations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("ann-v1", "v1-book", 1, "epubcfi(/6/2)", 0, 10, "Highlight", "Note", "#FFEB3B", 1000.0, 1000.0)
        )
        conn.execute("INSERT INTO settings VALUES (?, ?)", ("theme", "sepia"))
        conn.commit()
        conn.close()

        # Instantiate Database manager on legacy file — triggers migration to current version
        legacy_db = Database(migration_db_path)

        with legacy_db.get_connection() as c:
            cur = c.cursor()
            cur.execute("PRAGMA user_version;")
            self.assertEqual(cur.fetchone()[0], CURRENT_SCHEMA_VERSION)

            # Verify tables exist
            cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = {row[0] for row in cur.fetchall()}
            self.assertIn("reading_sessions", tables)
            self.assertIn("reading_statistics", tables)

            # Verify existing data is preserved intact
            book_r = BookRepository(legacy_db)
            b = book_r.get_by_id("v1-book")
            self.assertIsNotNone(b)
            self.assertEqual(b.title, "Legacy v1 Title")
            self.assertEqual(b.author, "Legacy Author")

            prog_r = ReadingProgressRepository(legacy_db)
            p = prog_r.get("v1-book")
            self.assertIsNotNone(p)
            self.assertEqual(p.percentage, 42.0)

            ann_r = AnnotationRepository(legacy_db)
            anns = ann_r.get_by_book("v1-book")
            self.assertEqual(len(anns), 1)
            self.assertEqual(anns[0].text_content, "Highlight")

            sett_r = SettingsRepository(legacy_db)
            s = sett_r.load()
            self.assertEqual(s.theme, "sepia")

    def test_record_session_and_get_sessions(self):
        """Verify recording sessions and retrieving session history per book with correct ordering and limits."""
        book = Book(id="stats-book-1", title="Session Testing", file_format="epub")
        self.book_repo.add(book)

        base_time = datetime(2026, 10, 1, 10, 0, 0, tzinfo=timezone.utc)
        sess1 = ReadingSession(
            id="sess-001",
            book_id="stats-book-1",
            started_at=base_time,
            ended_at=base_time + timedelta(minutes=10),
            duration_seconds=600.0,
            active_seconds=500.0,
            idle_seconds=100.0,
            words_read=2500,
            wpm=300.0
        )
        sess2 = ReadingSession(
            id="sess-002",
            book_id="stats-book-1",
            started_at=base_time + timedelta(hours=2),
            ended_at=base_time + timedelta(hours=2, minutes=5),
            duration_seconds=300.0,
            active_seconds=240.0,
            idle_seconds=60.0,
            words_read=1200,
            wpm=300.0
        )
        sess3 = ReadingSession(
            id="sess-003",
            book_id="stats-book-1",
            started_at=base_time + timedelta(hours=4),
            ended_at=base_time + timedelta(hours=4, minutes=15),
            duration_seconds=900.0,
            active_seconds=800.0,
            idle_seconds=100.0,
            words_read=4000,
            wpm=300.0
        )

        self.stats_repo.record_session(sess1)
        self.stats_repo.record_session(sess2)
        self.stats_repo.record_session(sess3)

        sessions = self.stats_repo.get_sessions_for_book("stats-book-1")
        self.assertEqual(len(sessions), 3)

        # Ordering: most recent session first
        self.assertEqual(sessions[0].id, "sess-003")
        self.assertEqual(sessions[1].id, "sess-002")
        self.assertEqual(sessions[2].id, "sess-001")

        # Verify session fields
        self.assertEqual(sessions[0].duration_seconds, 900.0)
        self.assertEqual(sessions[0].active_seconds, 800.0)
        self.assertEqual(sessions[0].idle_seconds, 100.0)
        self.assertEqual(sessions[0].words_read, 4000)
        self.assertEqual(sessions[0].wpm, 300.0)
        self.assertIsInstance(sessions[0].started_at, datetime)
        self.assertIsInstance(sessions[0].ended_at, datetime)

        # Limit parameter handling
        limited = self.stats_repo.get_sessions_for_book("stats-book-1", limit=2)
        self.assertEqual(len(limited), 2)
        self.assertEqual(limited[0].id, "sess-003")
        self.assertEqual(limited[1].id, "sess-002")

        # Non-existent book
        empty = self.stats_repo.get_sessions_for_book("non-existent-book")
        self.assertEqual(empty, [])

    def test_book_statistics_calculation(self):
        """Verify aggregated book statistics computation, WPM calculation, and empty book behavior."""
        book = Book(id="calc-book", title="Calculations Book", file_format="pdf")
        self.book_repo.add(book)

        # Before any sessions recorded
        initial_stats = self.stats_repo.get_book_statistics("calc-book")
        self.assertEqual(initial_stats.book_id, "calc-book")
        self.assertEqual(initial_stats.total_reading_seconds, 0.0)
        self.assertEqual(initial_stats.active_reading_seconds, 0.0)
        self.assertEqual(initial_stats.total_sessions, 0)
        self.assertEqual(initial_stats.estimated_words_read, 0)
        self.assertEqual(initial_stats.average_wpm, 0.0)
        self.assertIsNone(initial_stats.last_session_at)

        # First session: 600s duration, 500s active, 2500 words
        t1 = datetime(2026, 10, 2, 14, 0, tzinfo=timezone.utc)
        self.stats_repo.record_session(ReadingSession(
            id="s1",
            book_id="calc-book",
            started_at=t1,
            ended_at=t1 + timedelta(minutes=10),
            duration_seconds=600.0,
            active_seconds=500.0,
            idle_seconds=100.0,
            words_read=2500,
            wpm=300.0
        ))

        stats1 = self.stats_repo.get_book_statistics("calc-book")
        self.assertEqual(stats1.total_sessions, 1)
        self.assertAlmostEqual(stats1.total_reading_seconds, 600.0)
        self.assertAlmostEqual(stats1.active_reading_seconds, 500.0)
        self.assertEqual(stats1.estimated_words_read, 2500)
        # 2500 words / (500s / 60s) = 2500 / 8.3333 = 300.0 WPM
        self.assertAlmostEqual(stats1.average_wpm, 300.0, places=1)
        self.assertIsNotNone(stats1.last_session_at)

        # Second session: 300s duration, 250s active, 1000 words
        t2 = datetime(2026, 10, 2, 16, 0, tzinfo=timezone.utc)
        self.stats_repo.record_session(ReadingSession(
            id="s2",
            book_id="calc-book",
            started_at=t2,
            ended_at=t2 + timedelta(minutes=5),
            duration_seconds=300.0,
            active_seconds=250.0,
            idle_seconds=50.0,
            words_read=1000,
            wpm=240.0
        ))

        stats2 = self.stats_repo.get_book_statistics("calc-book")
        self.assertEqual(stats2.total_sessions, 2)
        self.assertAlmostEqual(stats2.total_reading_seconds, 900.0)
        self.assertAlmostEqual(stats2.active_reading_seconds, 750.0)
        self.assertEqual(stats2.estimated_words_read, 3500)
        # 3500 words / (750s / 60s) = 3500 / 12.5 = 280.0 WPM
        self.assertAlmostEqual(stats2.average_wpm, 280.0, places=1)

    def test_library_statistics_calculation(self):
        """Verify cross-library metrics: completed/in-progress books, format distribution, and aggregate WPM."""
        # Clean library start
        empty_lib = self.stats_repo.get_library_statistics()
        self.assertEqual(empty_lib.total_books, 0)
        self.assertEqual(empty_lib.books_in_progress, 0)
        self.assertEqual(empty_lib.books_completed, 0)
        self.assertEqual(empty_lib.total_reading_seconds, 0.0)
        self.assertEqual(empty_lib.format_counts, {})

        # Add 3 books with distinct formats
        b_epub = self.book_repo.add(Book(id="b-epub", title="EPUB", file_format="epub"))
        b_pdf = self.book_repo.add(Book(id="b-pdf", title="PDF", file_format="pdf"))
        b_cbz = self.book_repo.add(Book(id="b-cbz", title="CBZ", file_format="cbz"))

        # Progress tracking:
        # b_epub is 100% completed
        self.progress_repo.save(ReadingProgress(book_id="b-epub", percentage=100.0))
        # b_pdf is 45% in progress
        self.progress_repo.save(ReadingProgress(book_id="b-pdf", percentage=45.0))
        # b_cbz is 0% (unread)
        self.progress_repo.save(ReadingProgress(book_id="b-cbz", percentage=0.0))

        # Record sessions for b_epub and b_pdf
        now = datetime.now(timezone.utc)
        self.stats_repo.record_session(ReadingSession(
            id="s-ep", book_id="b-epub", started_at=now, ended_at=now,
            duration_seconds=600.0, active_seconds=500.0, idle_seconds=100.0,
            words_read=2500, wpm=300.0
        ))
        self.stats_repo.record_session(ReadingSession(
            id="s-pdf", book_id="b-pdf", started_at=now, ended_at=now,
            duration_seconds=400.0, active_seconds=300.0, idle_seconds=100.0,
            words_read=1500, wpm=300.0
        ))

        lib_stats = self.stats_repo.get_library_statistics()
        self.assertEqual(lib_stats.total_books, 3)
        self.assertEqual(lib_stats.books_completed, 1)
        self.assertEqual(lib_stats.books_in_progress, 1)
        self.assertEqual(lib_stats.format_counts, {"epub": 1, "pdf": 1, "cbz": 1})
        self.assertAlmostEqual(lib_stats.total_reading_seconds, 1000.0)
        self.assertAlmostEqual(lib_stats.active_reading_seconds, 800.0)
        self.assertEqual(lib_stats.total_words_read, 4000)
        # 4000 words / (800s / 60s) = 4000 / 13.333 = 300.0 WPM
        self.assertAlmostEqual(lib_stats.average_wpm, 300.0, places=1)

    def test_cascade_deletion(self):
        """Verify that deleting a book cascades to purge all its reading sessions and cached statistics."""
        book_a = self.book_repo.add(Book(id="book-a", title="Book A", file_format="epub"))
        book_b = self.book_repo.add(Book(id="book-b", title="Book B", file_format="pdf"))

        now = datetime.now(timezone.utc)
        self.stats_repo.record_session(ReadingSession(
            id="sess-a1", book_id="book-a", started_at=now, ended_at=now,
            duration_seconds=300.0, active_seconds=250.0, idle_seconds=50.0,
            words_read=1000, wpm=240.0
        ))
        self.stats_repo.record_session(ReadingSession(
            id="sess-b1", book_id="book-b", started_at=now, ended_at=now,
            duration_seconds=500.0, active_seconds=400.0, idle_seconds=100.0,
            words_read=2000, wpm=300.0
        ))

        # Verify both books have sessions and statistics
        self.assertEqual(len(self.stats_repo.get_sessions_for_book("book-a")), 1)
        self.assertEqual(len(self.stats_repo.get_sessions_for_book("book-b")), 1)
        self.assertEqual(self.stats_repo.get_book_statistics("book-a").total_sessions, 1)
        self.assertEqual(self.stats_repo.get_book_statistics("book-b").total_sessions, 1)

        # Delete Book A
        deleted = self.book_repo.delete("book-a")
        self.assertTrue(deleted)
        self.assertIsNone(self.book_repo.get_by_id("book-a"))

        # Verify Book A's sessions are completely purged via cascade
        self.assertEqual(self.stats_repo.get_sessions_for_book("book-a"), [])
        stats_a = self.stats_repo.get_book_statistics("book-a")
        self.assertEqual(stats_a.total_sessions, 0)
        self.assertEqual(stats_a.total_reading_seconds, 0.0)

        # Verify direct DB query confirms 0 rows for book-a
        with self.db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM reading_sessions WHERE book_id = 'book-a'")
            self.assertEqual(cur.fetchone()[0], 0)
            cur.execute("SELECT COUNT(*) FROM reading_statistics WHERE book_id = 'book-a'")
            self.assertEqual(cur.fetchone()[0], 0)

        # Verify Book B's sessions and statistics remain completely untouched
        self.assertEqual(len(self.stats_repo.get_sessions_for_book("book-b")), 1)
        stats_b = self.stats_repo.get_book_statistics("book-b")
        self.assertEqual(stats_b.total_sessions, 1)
        self.assertAlmostEqual(stats_b.total_reading_seconds, 500.0)

        # Verify library statistics accurately reflect remaining books only
        lib_stats = self.stats_repo.get_library_statistics()
        self.assertEqual(lib_stats.total_books, 1)
        self.assertAlmostEqual(lib_stats.total_reading_seconds, 500.0)
        self.assertEqual(lib_stats.total_words_read, 2000)

    def test_durability_across_reconnect(self):
        """Verify that sessions and statistics survive connection close and reload from disk."""
        book = self.book_repo.add(Book(id="durable-book", title="Durable", file_format="epub"))
        now = datetime(2026, 10, 3, 8, 30, tzinfo=timezone.utc)
        self.stats_repo.record_session(ReadingSession(
            id="durable-sess", book_id="durable-book", started_at=now, ended_at=now + timedelta(minutes=5),
            duration_seconds=300.0, active_seconds=270.0, idle_seconds=30.0,
            words_read=1350, wpm=300.0
        ))

        # Reopen with brand new Database instance pointing to same file
        new_db = Database(self.db_path)
        new_stats_repo = StatisticsRepository(new_db)

        sessions = new_stats_repo.get_sessions_for_book("durable-book")
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0].id, "durable-sess")
        self.assertEqual(sessions[0].words_read, 1350)

        stats = new_stats_repo.get_book_statistics("durable-book")
        self.assertEqual(stats.total_sessions, 1)
        self.assertAlmostEqual(stats.total_reading_seconds, 300.0)
        self.assertAlmostEqual(stats.average_wpm, 300.0, places=1)


if __name__ == "__main__":
    unittest.main()
