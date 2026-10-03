#!/usr/bin/env python3
"""
Adversarial Stress Test Harness for Milestone M1 (Storage & Domain Models).
Tests:
1. Schema migration v1 -> v2 under heavy data loads and Unicode/boundary data.
2. StatisticsRepository boundary conditions (0.0s, negative, huge, fractional, missing end).
3. Concurrent multi-threaded sessions and lock contention under SQLite WAL mode.
4. Cascade deletion and relational integrity across books, sessions, and statistics.
5. Transaction rollback and atomic failure isolation.
"""

import os
import sys
import time
import uuid
import sqlite3
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta

# Ensure src is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.aquile.domain.models import (
    Book, ReadingProgress, Annotation, AppSettings,
    ReadingSession, BookStatistics, LibraryStatistics
)
from src.aquile.storage.database import Database, CURRENT_SCHEMA_VERSION
from src.aquile.storage.repository import (
    BookRepository, ReadingProgressRepository, AnnotationRepository,
    SettingsRepository, StatisticsRepository
)


def log_test(name: str):
    print(f"\n[RUNNING] {name}...")


def assert_true(cond: bool, msg: str = ""):
    if not cond:
        print(f"  FAILED: {msg}")
        raise AssertionError(msg)


def assert_equal(actual, expected, msg: str = ""):
    if actual != expected:
        err = f"Expected {expected!r}, got {actual!r}. {msg}"
        print(f"  FAILED: {err}")
        raise AssertionError(err)


def assert_almost_equal(actual, expected, places=2, msg: str = ""):
    if isinstance(places, str):
        msg = places
        places = 2
    diff = abs(actual - expected)
    tol = 10 ** (-places)
    if diff > tol:
        err = f"Expected {expected!r} ~= {actual!r} (diff={diff} > {tol}). {msg}"
        print(f"  FAILED: {err}")
        raise AssertionError(err)


# =========================================================================
# Vector 1: Schema Migration v1 -> v2 Stress Test
# =========================================================================
def test_vector_1_schema_migration():
    log_test("Vector 1.1: Heavy data v1 -> v2 schema migration")
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = os.path.join(tmp_dir, "heavy_v1.db")

        # 1. Create v1 database and populate with 500 books, 500 progress, 1500 annotations
        conn = sqlite3.connect(db_path)
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

        num_books = 300
        books_data = []
        progress_data = []
        ann_data = []
        for i in range(num_books):
            b_id = f"v1-book-{i:04d}"
            # Test Unicode, special chars, emojis in titles/authors
            title = f"Title #{i} — 📚 漢字 & Special <Chars> '{i}'"
            author = f"Author № {i} • René Descartes"
            path = f"/storage/books/book_{i}.epub"
            books_data.append((b_id, title, author, path, "epub", None, 10, 2048, 1000.0 + i, 1100.0 + i))
            progress_data.append((b_id, i % 10, i % 50, f"epubcfi(/{i}/2)", float(i % 100), 1100.0 + i))
            for a in range(3):
                ann_data.append((
                    f"ann-{i}-{a}", b_id, i % 10, f"epubcfi(/{i}/2/{a})",
                    a * 10, a * 10 + 9, f"Text {a} for book {i} 🔍", f"Note {a}", "#FFEB3B", 1050.0, 1050.0
                ))

        conn.executemany("INSERT INTO books VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", books_data)
        conn.executemany("INSERT INTO reading_progress VALUES (?, ?, ?, ?, ?, ?)", progress_data)
        conn.executemany("INSERT INTO annotations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", ann_data)
        conn.execute("INSERT INTO settings VALUES (?, ?)", ("theme", "dark"))
        conn.commit()
        conn.close()

        # Check PRAGMA integrity_check before migration
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("PRAGMA integrity_check;")
        check_before = cur.fetchone()[0]
        assert_equal(check_before, "ok", "Database integrity pre-migration")
        conn.close()

        # Migrate to v2 by instantiating Database
        t_start = time.perf_counter()
        db = Database(db_path)
        migration_duration = time.perf_counter() - t_start
        print(f"  Migrated {num_books} books, {len(ann_data)} annotations in {migration_duration:.4f}s")

        # Verify integrity post-migration
        with db.get_connection() as c:
            cur = c.cursor()
            cur.execute("PRAGMA integrity_check;")
            assert_equal(cur.fetchone()[0], "ok", "Database integrity post-migration")

            cur.execute("PRAGMA user_version;")
            assert_equal(cur.fetchone()[0], 2, "Schema version must be 2")

            # Check that all books, progress, annotations exist intact
            cur.execute("SELECT COUNT(*) FROM books;")
            assert_equal(cur.fetchone()[0], num_books, "Books count intact")

            cur.execute("SELECT COUNT(*) FROM reading_progress;")
            assert_equal(cur.fetchone()[0], num_books, "Progress count intact")

            cur.execute("SELECT COUNT(*) FROM annotations;")
            assert_equal(cur.fetchone()[0], len(ann_data), "Annotations count intact")

            # Verify spot check on Unicode title
            cur.execute("SELECT title, author FROM books WHERE id = 'v1-book-0042'")
            row = cur.fetchone()
            assert_equal(row["title"], "Title #42 — 📚 漢字 & Special <Chars> '42'", "Unicode title preserved")
            assert_equal(row["author"], "Author № 42 • René Descartes", "Unicode author preserved")

            # Verify newly created tables exist and are empty
            cur.execute("SELECT COUNT(*) FROM reading_sessions;")
            assert_equal(cur.fetchone()[0], 0, "reading_sessions initialized empty")
            cur.execute("SELECT COUNT(*) FROM reading_statistics;")
            assert_equal(cur.fetchone()[0], 0, "reading_statistics initialized empty")

    log_test("Vector 1.2: Idempotent migration")
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = os.path.join(tmp_dir, "idempotent.db")
        db1 = Database(db_path)
        # Open 10 consecutive times
        for _ in range(10):
            db = Database(db_path)
            with db.get_connection() as c:
                cur = c.cursor()
                cur.execute("PRAGMA user_version;")
                assert_equal(cur.fetchone()[0], 2)
        print("  Idempotence verified across 10 reopenings.")


# =========================================================================
# Vector 2: Boundary Durations and Values in StatisticsRepository
# =========================================================================
def test_vector_2_boundary_durations():
    log_test("Vector 2.1: Boundary durations (0.0s, negative, huge, fractional, None)")
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = os.path.join(tmp_dir, "boundary.db")
        db = Database(db_path)
        book_repo = BookRepository(db)
        stats_repo = StatisticsRepository(db)

        book = book_repo.add(Book(id="b-boundary", title="Boundary Book", file_format="epub"))

        # Test Case 2.1a: Zero duration session
        s_zero = ReadingSession(
            id="s-zero",
            book_id="b-boundary",
            started_at=datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc),
            ended_at=datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc),
            duration_seconds=0.0,
            active_seconds=0.0,
            idle_seconds=0.0,
            words_read=0,
            wpm=0.0
        )
        stats_repo.record_session(s_zero)
        bs = stats_repo.get_book_statistics("b-boundary")
        assert_equal(bs.total_sessions, 1)
        assert_equal(bs.total_reading_seconds, 0.0)
        assert_equal(bs.active_reading_seconds, 0.0)
        assert_equal(bs.estimated_words_read, 0)
        assert_equal(bs.average_wpm, 0.0, "Zero active time must not divide by zero")

        # Test Case 2.1b: Fractional sub-second durations
        s_frac = ReadingSession(
            id="s-frac",
            book_id="b-boundary",
            started_at=datetime(2026, 10, 1, 12, 5, tzinfo=timezone.utc),
            ended_at=datetime(2026, 10, 1, 12, 5, 0, 500000, tzinfo=timezone.utc),
            duration_seconds=0.5,
            active_seconds=0.4,
            idle_seconds=0.1,
            words_read=2,
            wpm=300.0
        )
        stats_repo.record_session(s_frac)
        bs = stats_repo.get_book_statistics("b-boundary")
        assert_equal(bs.total_sessions, 2)
        assert_almost_equal(bs.total_reading_seconds, 0.5)
        assert_almost_equal(bs.active_reading_seconds, 0.4)
        assert_equal(bs.estimated_words_read, 2)
        # 2 words / (0.4 / 60) = 2 / 0.006666 = 300.0 WPM
        assert_almost_equal(bs.average_wpm, 300.0, places=1)

        # Test Case 2.1c: Session with ended_at = None
        s_no_end = ReadingSession(
            id="s-no-end",
            book_id="b-boundary",
            started_at=datetime(2026, 10, 1, 12, 10, tzinfo=timezone.utc),
            ended_at=None,
            duration_seconds=60.0,
            active_seconds=50.0,
            idle_seconds=10.0,
            words_read=250,
            wpm=300.0
        )
        stats_repo.record_session(s_no_end)
        sessions = stats_repo.get_sessions_for_book("b-boundary")
        assert_equal(len(sessions), 3)
        retrieved_no_end = [s for s in sessions if s.id == "s-no-end"][0]
        assert_true(retrieved_no_end.ended_at is None, "ended_at None preserved")

        # Test Case 2.1d: Negative duration / words (graceful storage without crash)
        s_neg = ReadingSession(
            id="s-neg",
            book_id="b-boundary",
            started_at=datetime(2026, 10, 1, 12, 15, tzinfo=timezone.utc),
            ended_at=datetime(2026, 10, 1, 12, 16, tzinfo=timezone.utc),
            duration_seconds=-10.0,
            active_seconds=-5.0,
            idle_seconds=-5.0,
            words_read=-10,
            wpm=-60.0
        )
        stats_repo.record_session(s_neg)
        bs_neg = stats_repo.get_book_statistics("b-boundary")
        assert_equal(bs_neg.total_sessions, 4)
        print("  Handled zero, fractional, None end, and negative values safely.")

        # Test Case 2.1e: Huge numbers (astronomical durations and words)
        book_huge = book_repo.add(Book(id="b-huge", title="Huge Book", file_format="pdf"))
        s_huge = ReadingSession(
            id="s-huge",
            book_id="b-huge",
            started_at=datetime(2026, 10, 1, 13, 0, tzinfo=timezone.utc),
            ended_at=datetime(2026, 10, 1, 13, 1, tzinfo=timezone.utc),
            duration_seconds=1e8,       # 100 million seconds (~3.17 years)
            active_seconds=8e7,         # 80 million seconds
            idle_seconds=2e7,
            words_read=1000000000,      # 1 billion words
            wpm=750.0
        )
        stats_repo.record_session(s_huge)
        bs_huge = stats_repo.get_book_statistics("b-huge")
        assert_equal(bs_huge.total_sessions, 1)
        assert_almost_equal(bs_huge.total_reading_seconds, 1e8)
        assert_almost_equal(bs_huge.active_reading_seconds, 8e7)
        assert_equal(bs_huge.estimated_words_read, 1000000000)
        # 1e9 / (8e7 / 60) = 1e9 / 1333333.33 = 750.0 WPM
        assert_almost_equal(bs_huge.average_wpm, 750.0, places=1)
        print("  Handled 1 billion words and 1e8 seconds without integer/float overflow.")


# =========================================================================
# Vector 3: Concurrency and Multi-threading Stress Test
# =========================================================================
def test_vector_3_concurrency():
    log_test("Vector 3.1: 30 concurrent threads recording sessions for the same book")
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = os.path.join(tmp_dir, "concurrent.db")
        db = Database(db_path)
        book_repo = BookRepository(db)
        book_repo.add(Book(id="concurrent-book", title="Concurrent Book", file_format="epub"))

        num_threads = 30
        errors = []

        def worker(thread_idx: int):
            try:
                # Each thread creates its own repository using the shared Database manager
                repo = StatisticsRepository(db)
                now = datetime.now(timezone.utc) + timedelta(seconds=thread_idx)
                session = ReadingSession(
                    id=f"sess-thread-{thread_idx}",
                    book_id="concurrent-book",
                    started_at=now,
                    ended_at=now + timedelta(seconds=60),
                    duration_seconds=60.0,
                    active_seconds=50.0,
                    idle_seconds=10.0,
                    words_read=200,
                    wpm=240.0
                )
                repo.record_session(session)
            except Exception as e:
                errors.append((thread_idx, str(e)))

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(num_threads)]
        t0 = time.perf_counter()
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        elapsed = time.perf_counter() - t0

        if errors:
            print(f"  Encountered {len(errors)} concurrency errors:")
            for tid, err in errors[:5]:
                print(f"    Thread {tid}: {err}")
            raise AssertionError(f"Concurrency failed with {len(errors)} errors")

        print(f"  30 concurrent threads completed in {elapsed:.3f}s with 0 errors.")

        # Check data integrity: exactly 30 sessions recorded
        stats_repo = StatisticsRepository(db)
        sessions = stats_repo.get_sessions_for_book("concurrent-book", limit=100)
        assert_equal(len(sessions), num_threads, "All concurrent sessions must be saved")

        book_stats = stats_repo.get_book_statistics("concurrent-book")
        assert_equal(book_stats.total_sessions, num_threads)
        assert_almost_equal(book_stats.total_reading_seconds, num_threads * 60.0)
        assert_almost_equal(book_stats.active_reading_seconds, num_threads * 50.0)
        assert_equal(book_stats.estimated_words_read, num_threads * 200)
        # avg WPM: (num_threads * 200) / ((num_threads * 50) / 60) = 200 / (50/60) = 240.0 WPM
        assert_almost_equal(book_stats.average_wpm, 240.0, places=1)
        print("  Aggregated statistics precisely match individual session sums.")

    log_test("Vector 3.2: Concurrent mixed reads and writes across multiple books")
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = os.path.join(tmp_dir, "mixed_concurrent.db")
        db = Database(db_path)
        book_repo = BookRepository(db)
        stats_repo = StatisticsRepository(db)

        # Prepopulate 5 books
        for b in range(5):
            book_repo.add(Book(id=f"book-{b}", title=f"Book {b}", file_format="epub"))

        num_tasks = 40
        read_results = []
        write_errors = []

        def reader_task(task_id: int):
            repo = StatisticsRepository(db)
            b_id = f"book-{task_id % 5}"
            # Perform various reads
            bs = repo.get_book_statistics(b_id)
            lib = repo.get_library_statistics()
            sess = repo.get_sessions_for_book(b_id, limit=10)
            read_results.append((task_id, bs.total_sessions, lib.total_books))

        def writer_task(task_id: int):
            repo = StatisticsRepository(db)
            b_id = f"book-{task_id % 5}"
            now = datetime.now(timezone.utc)
            s = ReadingSession(
                id=f"sess-mixed-{task_id}",
                book_id=b_id,
                started_at=now,
                ended_at=now + timedelta(seconds=30),
                duration_seconds=30.0,
                active_seconds=25.0,
                idle_seconds=5.0,
                words_read=100,
                wpm=240.0
            )
            try:
                repo.record_session(s)
            except Exception as e:
                write_errors.append((task_id, str(e)))

        with ThreadPoolExecutor(max_workers=12) as executor:
            futures = []
            for i in range(num_tasks):
                if i % 2 == 0:
                    futures.append(executor.submit(writer_task, i))
                else:
                    futures.append(executor.submit(reader_task, i))
            for f in as_completed(futures):
                f.result()

        assert_equal(len(write_errors), 0, "No errors during mixed concurrent read/write")
        print(f"  Mixed concurrent workload (20 writers, 20 readers) passed cleanly.")


# =========================================================================
# Vector 4: Cascade Deletion & Foreign Key Integrity
# =========================================================================
def test_vector_4_cascade_deletion():
    log_test("Vector 4.1: Cascade deletion of books with sessions, progress, annotations")
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = os.path.join(tmp_dir, "cascade.db")
        db = Database(db_path)
        book_repo = BookRepository(db)
        prog_repo = ReadingProgressRepository(db)
        ann_repo = AnnotationRepository(db)
        stats_repo = StatisticsRepository(db)

        # Create 5 books with full related records
        for i in range(5):
            b_id = f"cascade-book-{i}"
            book_repo.add(Book(id=b_id, title=f"Cascade Book {i}", file_format="epub"))
            prog_repo.save(ReadingProgress(book_id=b_id, percentage=50.0))
            ann_repo.add(Annotation(id=f"ann-{i}", book_id=b_id, text_content=f"Note {i}"))
            now = datetime.now(timezone.utc)
            for s in range(3):
                stats_repo.record_session(ReadingSession(
                    id=f"sess-{i}-{s}",
                    book_id=b_id,
                    started_at=now + timedelta(minutes=s),
                    ended_at=now + timedelta(minutes=s+1),
                    duration_seconds=60.0,
                    active_seconds=50.0,
                    idle_seconds=10.0,
                    words_read=200,
                    wpm=240.0
                ))

        # Check total books & sessions
        lib_stats = stats_repo.get_library_statistics()
        assert_equal(lib_stats.total_books, 5)
        assert_equal(lib_stats.books_in_progress, 5)
        assert_almost_equal(lib_stats.total_reading_seconds, 5 * 3 * 60.0)

        # Delete 2 books: cascade-book-1 and cascade-book-3
        del_1 = book_repo.delete("cascade-book-1")
        del_3 = book_repo.delete("cascade-book-3")
        assert_true(del_1, "delete book 1 returned True")
        assert_true(del_3, "delete book 3 returned True")

        # Verify raw tables for cascade-book-1
        with db.get_connection() as c:
            cur = c.cursor()
            for tbl in ["reading_sessions", "reading_statistics", "reading_progress", "annotations"]:
                cur.execute(f"SELECT COUNT(*) FROM {tbl} WHERE book_id = 'cascade-book-1'")
                count = cur.fetchone()[0]
                assert_equal(count, 0, f"Table {tbl} must have 0 rows for deleted book 1")

        # Verify repository methods for deleted books
        assert_equal(stats_repo.get_sessions_for_book("cascade-book-1"), [])
        bs_del = stats_repo.get_book_statistics("cascade-book-1")
        assert_equal(bs_del.total_sessions, 0)
        assert_equal(bs_del.total_reading_seconds, 0.0)

        # Verify surviving books remain intact
        for surviving in ["cascade-book-0", "cascade-book-2", "cascade-book-4"]:
            sess = stats_repo.get_sessions_for_book(surviving)
            assert_equal(len(sess), 3, f"{surviving} must have all 3 sessions")
            bs = stats_repo.get_book_statistics(surviving)
            assert_equal(bs.total_sessions, 3)
            assert_almost_equal(bs.total_reading_seconds, 180.0)

        # Verify library stats updated
        lib_stats_after = stats_repo.get_library_statistics()
        assert_equal(lib_stats_after.total_books, 3)
        assert_almost_equal(lib_stats_after.total_reading_seconds, 3 * 3 * 60.0)
        print("  Cascade deletion completely purged all child records without affecting sibling books.")

    log_test("Vector 4.2: Foreign key violation on non-existent book")
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = os.path.join(tmp_dir, "fk_violation.db")
        db = Database(db_path)
        stats_repo = StatisticsRepository(db)

        # Attempt to record session for a book that does NOT exist in books table
        now = datetime.now(timezone.utc)
        orphan_session = ReadingSession(
            id="orphan-sess",
            book_id="non-existent-book-id",
            started_at=now,
            ended_at=now + timedelta(minutes=5),
            duration_seconds=300.0,
            active_seconds=250.0,
            idle_seconds=50.0,
            words_read=1000,
            wpm=240.0
        )
        try:
            stats_repo.record_session(orphan_session)
            raise AssertionError("Recording session for non-existent book should have raised sqlite3.IntegrityError")
        except sqlite3.IntegrityError:
            print("  Correctly raised sqlite3.IntegrityError (foreign key constraint enforced).")


# =========================================================================
# Vector 5: Transaction Rollbacks and Atomicity Isolation
# =========================================================================
def test_vector_5_transaction_rollbacks():
    log_test("Vector 5.1: Transaction rollback on failure during multi-statement operations")
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = os.path.join(tmp_dir, "rollback.db")
        db = Database(db_path)
        book_repo = BookRepository(db)
        stats_repo = StatisticsRepository(db)

        book_repo.add(Book(id="rb-book", title="Rollback Book", file_format="epub"))

        # 1. Successful session
        now = datetime.now(timezone.utc)
        s1 = ReadingSession(
            id="s1-ok", book_id="rb-book", started_at=now, ended_at=now + timedelta(minutes=5),
            duration_seconds=300.0, active_seconds=250.0, idle_seconds=50.0,
            words_read=1000, wpm=240.0
        )
        stats_repo.record_session(s1)

        # 2. Simulate transaction failure: insert into reading_sessions, then fail before reading_statistics update
        class SimulatedCrash(Exception):
            pass

        try:
            with db.get_connection() as conn:
                conn.execute("""
                    INSERT INTO reading_sessions
                    (id, book_id, started_at, ended_at, duration_seconds, active_seconds, idle_seconds, words_read, wpm)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, ("s2-crash", "rb-book", now.isoformat(), now.isoformat(), 999.0, 999.0, 0.0, 5000, 300.0))
                # Now raise exception before commit
                raise SimulatedCrash("Process crashed before commit")
        except SimulatedCrash:
            pass

        # Verify that "s2-crash" was NOT persisted (atomic rollback on close/exception)
        sessions = stats_repo.get_sessions_for_book("rb-book")
        assert_equal(len(sessions), 1, "Only the committed session must exist")
        assert_equal(sessions[0].id, "s1-ok")

        stats = stats_repo.get_book_statistics("rb-book")
        assert_equal(stats.total_sessions, 1)
        assert_almost_equal(stats.total_reading_seconds, 300.0)
        print("  Uncommitted changes cleanly rolled back on exception.")

    log_test("Vector 5.2: Explicit rollback in connection context")
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = os.path.join(tmp_dir, "explicit_rollback.db")
        db = Database(db_path)
        book_repo = BookRepository(db)
        book_repo.add(Book(id="exp-book", title="Explicit Rollback", file_format="epub"))

        with db.get_connection() as conn:
            conn.execute("INSERT INTO books (id, title, author, file_path, file_format, added_at) VALUES (?, ?, ?, ?, ?, ?)",
                         ("temp-book", "Temp", "Temp", "/tmp/path", "epub", 123.0))
            conn.rollback()

        # Check that temp-book does not exist
        assert_true(book_repo.get_by_id("temp-book") is None, "Explicit rollback succeeded")
        print("  Explicit conn.rollback() successfully reverted pending modifications.")


# =========================================================================
# Vector 6: Idempotent Session Updates & Replacement
# =========================================================================
def test_vector_6_idempotent_session_updates():
    log_test("Vector 6: Idempotent session updates (INSERT OR REPLACE) without double-counting")
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = os.path.join(tmp_dir, "idempotent_sess.db")
        db = Database(db_path)
        book_repo = BookRepository(db)
        stats_repo = StatisticsRepository(db)

        book_repo.add(Book(id="idem-book", title="Idempotent Book", file_format="epub"))
        now = datetime.now(timezone.utc)

        # Record initial session
        s1 = ReadingSession(
            id="fixed-sess-id",
            book_id="idem-book",
            started_at=now,
            ended_at=now + timedelta(minutes=10),
            duration_seconds=600.0,
            active_seconds=500.0,
            idle_seconds=100.0,
            words_read=2500,
            wpm=300.0
        )
        stats_repo.record_session(s1)

        bs1 = stats_repo.get_book_statistics("idem-book")
        assert_equal(bs1.total_sessions, 1)
        assert_almost_equal(bs1.total_reading_seconds, 600.0)
        assert_equal(bs1.estimated_words_read, 2500)

        # Re-record with updated duration and words (e.g. session checkpointing)
        s1_updated = ReadingSession(
            id="fixed-sess-id",
            book_id="idem-book",
            started_at=now,
            ended_at=now + timedelta(minutes=15),
            duration_seconds=900.0,
            active_seconds=750.0,
            idle_seconds=150.0,
            words_read=3750,
            wpm=300.0
        )
        stats_repo.record_session(s1_updated)

        # Verify it did NOT create a second session or double-count
        sessions = stats_repo.get_sessions_for_book("idem-book")
        assert_equal(len(sessions), 1, "Session count must remain 1 after replacement")
        assert_equal(sessions[0].duration_seconds, 900.0)

        bs2 = stats_repo.get_book_statistics("idem-book")
        assert_equal(bs2.total_sessions, 1, "total_sessions must remain 1")
        assert_almost_equal(bs2.total_reading_seconds, 900.0, "total_reading_seconds updated")
        assert_almost_equal(bs2.active_reading_seconds, 750.0, "active_reading_seconds updated")
        assert_equal(bs2.estimated_words_read, 3750, "estimated_words_read updated")
        print("  Idempotent update cleanly replaced row and updated aggregated statistics without double-counting.")


# =========================================================================
# Vector 7: Cache Invalidation & Dynamic Fallback
# =========================================================================
def test_vector_7_cache_fallback():
    log_test("Vector 7: Cache invalidation & dynamic fallback in get_book_statistics")
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = os.path.join(tmp_dir, "cache_fallback.db")
        db = Database(db_path)
        book_repo = BookRepository(db)
        stats_repo = StatisticsRepository(db)

        book_repo.add(Book(id="cache-book", title="Cache Book", file_format="epub"))
        now = datetime.now(timezone.utc)

        # Record 2 sessions
        stats_repo.record_session(ReadingSession(
            id="cs-1", book_id="cache-book", started_at=now, ended_at=now,
            duration_seconds=300.0, active_seconds=200.0, idle_seconds=100.0,
            words_read=1000, wpm=300.0
        ))
        stats_repo.record_session(ReadingSession(
            id="cs-2", book_id="cache-book", started_at=now + timedelta(hours=1), ended_at=now + timedelta(hours=1),
            duration_seconds=600.0, active_seconds=400.0, idle_seconds=200.0,
            words_read=2000, wpm=300.0
        ))

        # Intentionally DELETE the cached row from reading_statistics
        with db.get_connection() as conn:
            conn.execute("DELETE FROM reading_statistics WHERE book_id = 'cache-book'")
            conn.commit()

        # Call get_book_statistics: fallback must dynamically query reading_sessions
        bs_fallback = stats_repo.get_book_statistics("cache-book")
        assert_equal(bs_fallback.book_id, "cache-book")
        assert_equal(bs_fallback.total_sessions, 2)
        assert_almost_equal(bs_fallback.total_reading_seconds, 900.0)
        assert_almost_equal(bs_fallback.active_reading_seconds, 600.0)
        assert_equal(bs_fallback.estimated_words_read, 3000)
        # 3000 words / (600s / 60s) = 3000 / 10 = 300.0 WPM
        assert_almost_equal(bs_fallback.average_wpm, 300.0, places=1)
        assert_true(bs_fallback.last_session_at is not None)
        print("  Fallback dynamically computed accurate statistics when cache was missing.")


# =========================================================================
# Vector 8: Datetime Resilience & Corrupted Date Handling
# =========================================================================
def test_vector_8_datetime_resilience():
    log_test("Vector 8: Datetime parsing resilience (mixed formats, corrupted strings, timestamps)")
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = os.path.join(tmp_dir, "datetime.db")
        db = Database(db_path)
        book_repo = BookRepository(db)
        stats_repo = StatisticsRepository(db)

        book_repo.add(Book(id="dt-book", title="Datetime Book", file_format="epub"))

        # Raw inserts with various started_at formats
        with db.get_connection() as conn:
            # 1. ISO string with tz
            conn.execute("""
                INSERT INTO reading_sessions (id, book_id, started_at, ended_at, duration_seconds, active_seconds, idle_seconds, words_read, wpm)
                VALUES ('dt-1', 'dt-book', '2026-10-01T12:00:00+00:00', '2026-10-01T12:10:00+00:00', 600, 500, 100, 2000, 240)
            """)
            # 2. Float epoch timestamp
            conn.execute("""
                INSERT INTO reading_sessions (id, book_id, started_at, ended_at, duration_seconds, active_seconds, idle_seconds, words_read, wpm)
                VALUES ('dt-2', 'dt-book', '1790856000.0', '1790856600.0', 600, 500, 100, 2000, 240)
            """)
            # 3. Corrupted non-date string
            conn.execute("""
                INSERT INTO reading_sessions (id, book_id, started_at, ended_at, duration_seconds, active_seconds, idle_seconds, words_read, wpm)
                VALUES ('dt-3', 'dt-book', 'corrupted-date-string', NULL, 600, 500, 100, 2000, 240)
            """)
            conn.commit()

        # Retrieve sessions: none should raise an unhandled exception
        sessions = stats_repo.get_sessions_for_book("dt-book")
        assert_equal(len(sessions), 3)
        for s in sessions:
            assert_true(isinstance(s.started_at, datetime), f"started_at must be parsed to datetime: {s.id}")

        bs = stats_repo.get_book_statistics("dt-book")
        assert_equal(bs.total_sessions, 3)
        print("  Resilient datetime parsing handled ISO, epoch, and corrupted strings without crash.")


# =========================================================================
# Vector 9: Multi-Process Concurrency
# =========================================================================
def _mp_worker(db_path: str, proc_id: int, num_sessions: int):
    # Separate process with separate Database instance
    db = Database(db_path)
    repo = StatisticsRepository(db)
    for s_idx in range(num_sessions):
        now = datetime.now(timezone.utc)
        sess = ReadingSession(
            id=f"mp-sess-{proc_id}-{s_idx}",
            book_id="mp-book",
            started_at=now,
            ended_at=now + timedelta(seconds=10),
            duration_seconds=10.0,
            active_seconds=8.0,
            idle_seconds=2.0,
            words_read=40,
            wpm=300.0
        )
        repo.record_session(sess)


def test_vector_9_multiprocess_concurrency():
    log_test("Vector 9: Multi-process concurrency (independent Python processes)")
    import multiprocessing
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = os.path.join(tmp_dir, "multiprocess.db")
        db = Database(db_path)
        book_repo = BookRepository(db)
        book_repo.add(Book(id="mp-book", title="MultiProcess Book", file_format="epub"))

        num_procs = 4
        sessions_per_proc = 10
        processes = [
            multiprocessing.Process(target=_mp_worker, args=(db_path, p, sessions_per_proc))
            for p in range(num_procs)
        ]

        t0 = time.perf_counter()
        for p in processes:
            p.start()
        for p in processes:
            p.join(timeout=10.0)
            assert_equal(p.exitcode, 0, f"Process {p.pid} must exit cleanly")
        elapsed = time.perf_counter() - t0

        stats_repo = StatisticsRepository(db)
        expected_total = num_procs * sessions_per_proc
        sessions = stats_repo.get_sessions_for_book("mp-book", limit=100)
        assert_equal(len(sessions), expected_total, "All multi-process sessions recorded")

        bs = stats_repo.get_book_statistics("mp-book")
        assert_equal(bs.total_sessions, expected_total)
        assert_almost_equal(bs.total_reading_seconds, expected_total * 10.0)
        assert_almost_equal(bs.active_reading_seconds, expected_total * 8.0)
        assert_equal(bs.estimated_words_read, expected_total * 40)
        print(f"  {num_procs} processes wrote {expected_total} sessions in {elapsed:.3f}s with 0 errors.")


# =========================================================================
# Vector 10: Performance Scaling & Query Latency
# =========================================================================
def test_vector_10_performance_scaling():
    log_test("Vector 10: Performance scaling with 1,000 sessions on a single book")
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = os.path.join(tmp_dir, "perf.db")
        db = Database(db_path)
        book_repo = BookRepository(db)
        stats_repo = StatisticsRepository(db)

        book_repo.add(Book(id="perf-book", title="Perf Book", file_format="epub"))

        # Batch insert 1,000 sessions directly to measure retrieval and query speed
        base_time = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
        items = []
        for i in range(1000):
            t = base_time + timedelta(minutes=i * 15)
            items.append((
                f"perf-s-{i:04d}", "perf-book", t.isoformat(), (t + timedelta(minutes=10)).isoformat(),
                600.0, 500.0, 100.0, 2000, 240.0
            ))

        with db.get_connection() as conn:
            conn.executemany("""
                INSERT INTO reading_sessions
                (id, book_id, started_at, ended_at, duration_seconds, active_seconds, idle_seconds, words_read, wpm)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, items)
            conn.commit()

        # Benchmark get_sessions_for_book (paginated top 50)
        t_start = time.perf_counter()
        top_50 = stats_repo.get_sessions_for_book("perf-book", limit=50)
        top_50_time = time.perf_counter() - t_start
        assert_equal(len(top_50), 50)
        # Verify ordering: most recent first
        assert_equal(top_50[0].id, "perf-s-0999")
        print(f"  get_sessions_for_book(limit=50) across 1,000 sessions took {top_50_time*1000:.2f}ms (target < 10ms)")
        assert_true(top_50_time < 0.05, "Top 50 pagination must take < 50ms")

        # Benchmark get_book_statistics (fallback dynamic aggregation over 1,000 rows)
        t_start = time.perf_counter()
        bs = stats_repo.get_book_statistics("perf-book")
        agg_time = time.perf_counter() - t_start
        assert_equal(bs.total_sessions, 1000)
        assert_almost_equal(bs.total_reading_seconds, 600000.0)
        print(f"  Dynamic aggregation over 1,000 sessions took {agg_time*1000:.2f}ms (target < 10ms)")
        assert_true(agg_time < 0.05, "Aggregation must take < 50ms")


# =========================================================================
# Main Runner
# =========================================================================
def run_all_stress_tests():
    print("=" * 70)
    print("  MILESTONE M1 EMPIRICAL CHALLENGE — ADVERSARIAL STRESS TEST HARNESS")
    print("=" * 70)

    start_time = time.perf_counter()

    test_vector_1_schema_migration()
    test_vector_2_boundary_durations()
    test_vector_3_concurrency()
    test_vector_4_cascade_deletion()
    test_vector_5_transaction_rollbacks()
    test_vector_6_idempotent_session_updates()
    test_vector_7_cache_fallback()
    test_vector_8_datetime_resilience()
    test_vector_9_multiprocess_concurrency()
    test_vector_10_performance_scaling()

    total_time = time.perf_counter() - start_time
    print("\n" + "=" * 70)
    print(f"  ALL 10 STRESS TEST VECTORS PASSED in {total_time:.3f}s")
    print("=" * 70)
    return True


if __name__ == "__main__":
    try:
        success = run_all_stress_tests()
        sys.exit(0 if success else 1)
    except Exception as exc:
        print(f"\n[FATAL STRESS TEST FAILURE] {exc}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

