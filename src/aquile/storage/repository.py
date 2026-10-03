"""
Repositories for Book, Progress, Annotation, and Settings persistence.
"""

import time
from datetime import datetime, timezone
from typing import List, Optional, Any
from ..domain.models import (
    Book, ReadingProgress, Annotation, AppSettings,
    ReadingSession, BookStatistics, LibraryStatistics
)
from .database import Database

class BookRepository:
    def __init__(self, db: Database):
        self.db = db

    def add(self, book: Book) -> Book:
        if not book.file_path:
            book.file_path = f"/books/{book.id}"
        with self.db.get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO books 
                (id, title, author, file_path, file_format, cover_path, total_chapters, file_size_bytes, added_at, last_read_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                book.id, book.title, book.author, book.file_path, book.file_format,
                book.cover_path, book.total_chapters, book.file_size_bytes, book.added_at, book.last_read_at
            ))
            conn.commit()
        return book

    def get_by_id(self, book_id: str) -> Optional[Book]:
        with self.db.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM books WHERE id = ?", (book_id,))
            row = cursor.fetchone()
            if row:
                return Book(**dict(row))
        return None

    def get_by_path(self, file_path: str) -> Optional[Book]:
        with self.db.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM books WHERE file_path = ?", (file_path,))
            row = cursor.fetchone()
            if row:
                return Book(**dict(row))
        return None

    def list_all(self) -> List[Book]:
        with self.db.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM books ORDER BY added_at DESC")
            return [Book(**dict(r)) for r in cursor.fetchall()]

    def delete(self, book_id: str) -> bool:
        with self.db.get_connection() as conn:
            cursor = conn.execute("DELETE FROM books WHERE id = ?", (book_id,))
            conn.commit()
            return cursor.rowcount > 0

    def update_last_read(self, book_id: str, timestamp: Optional[float] = None):
        ts = timestamp or time.time()
        with self.db.get_connection() as conn:
            conn.execute("UPDATE books SET last_read_at = ? WHERE id = ?", (ts, book_id))
            conn.commit()


class ReadingProgressRepository:
    def __init__(self, db: Database):
        self.db = db

    def save(self, progress: ReadingProgress):
        with self.db.get_connection() as conn:
            conn.execute("""
                INSERT INTO reading_progress (book_id, chapter_index, page_index, cfi, percentage, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(book_id) DO UPDATE SET
                    chapter_index = excluded.chapter_index,
                    page_index = excluded.page_index,
                    cfi = excluded.cfi,
                    percentage = excluded.percentage,
                    updated_at = excluded.updated_at
            """, (
                progress.book_id, progress.chapter_index, progress.page_index,
                progress.cfi, progress.percentage, progress.updated_at
            ))
            conn.commit()

    def get(self, book_id: str) -> Optional[ReadingProgress]:
        with self.db.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM reading_progress WHERE book_id = ?", (book_id,))
            row = cursor.fetchone()
            if row:
                return ReadingProgress(**dict(row))
        return None


class AnnotationRepository:
    def __init__(self, db: Database):
        self.db = db

    def add(self, annotation: Annotation) -> Annotation:
        with self.db.get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO annotations
                (id, book_id, chapter_index, cfi, start_offset, end_offset, text_content, note_text, color, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                annotation.id, annotation.book_id, annotation.chapter_index, annotation.cfi,
                annotation.start_offset, annotation.end_offset, annotation.text_content,
                annotation.note_text, annotation.color, annotation.created_at, annotation.updated_at
            ))
            conn.commit()
        return annotation

    def get_by_book(self, book_id: str) -> List[Annotation]:
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM annotations WHERE book_id = ? ORDER BY chapter_index, start_offset",
                (book_id,)
            )
            return [Annotation(**dict(r)) for r in cursor.fetchall()]

    def list_all(self) -> List[Annotation]:
        """Cross-book annotations for Collections view (FR-11)"""
        with self.db.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM annotations ORDER BY created_at DESC")
            return [Annotation(**dict(r)) for r in cursor.fetchall()]

    def delete(self, annotation_id: str) -> bool:
        with self.db.get_connection() as conn:
            cursor = conn.execute("DELETE FROM annotations WHERE id = ?", (annotation_id,))
            conn.commit()
            return cursor.rowcount > 0


class SettingsRepository:
    def __init__(self, db: Database):
        self.db = db

    def load(self) -> AppSettings:
        settings = AppSettings()
        with self.db.get_connection() as conn:
            cursor = conn.execute("SELECT key, value FROM settings")
            rows = dict(cursor.fetchall())
            if "theme" in rows: settings.theme = rows["theme"]
            if "font_family" in rows: settings.font_family = rows["font_family"]
            if "font_size" in rows: settings.font_size = int(rows["font_size"])
            if "line_height" in rows: settings.line_height = float(rows["line_height"])
            if "columns" in rows: settings.columns = int(rows["columns"])
            if "margin_percent" in rows: settings.margin_percent = int(rows["margin_percent"])
        return settings

    def save(self, settings: AppSettings):
        with self.db.get_connection() as conn:
            items = [
                ("theme", settings.theme),
                ("font_family", settings.font_family),
                ("font_size", str(settings.font_size)),
                ("line_height", str(settings.line_height)),
                ("columns", str(settings.columns)),
                ("margin_percent", str(settings.margin_percent))
            ]
            conn.executemany("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", items)
            conn.commit()


def _parse_datetime(val: Any) -> Optional[datetime]:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val
    if isinstance(val, (int, float)):
        return datetime.fromtimestamp(val, tz=timezone.utc)
    if isinstance(val, str):
        try:
            return datetime.fromisoformat(val)
        except ValueError:
            try:
                return datetime.fromtimestamp(float(val), tz=timezone.utc)
            except ValueError:
                return None
    return None


class StatisticsRepository:
    def __init__(self, db: Database):
        self.db = db

    def record_session(self, session: ReadingSession) -> None:
        started_str = (
            session.started_at.isoformat()
            if isinstance(session.started_at, datetime)
            else str(session.started_at)
        )
        ended_str = (
            session.ended_at.isoformat()
            if isinstance(session.ended_at, datetime)
            else (str(session.ended_at) if session.ended_at is not None else None)
        )
        with self.db.get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO reading_sessions
                (id, book_id, started_at, ended_at, duration_seconds, active_seconds, idle_seconds, words_read, wpm)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session.id,
                session.book_id,
                started_str,
                ended_str,
                float(session.duration_seconds),
                float(session.active_seconds),
                float(session.idle_seconds),
                int(session.words_read),
                float(session.wpm),
            ))

            # Update aggregated reading_statistics cache for this book
            cursor = conn.execute("""
                SELECT
                    COUNT(*) as total_sessions,
                    COALESCE(SUM(duration_seconds), 0.0) as total_reading_seconds,
                    COALESCE(SUM(active_seconds), 0.0) as active_reading_seconds,
                    COALESCE(SUM(words_read), 0) as estimated_words_read,
                    COALESCE(AVG(wpm), 0.0) as avg_session_wpm,
                    MAX(started_at) as last_session_at
                FROM reading_sessions
                WHERE book_id = ?
            """, (session.book_id,))
            agg = cursor.fetchone()

            total_sessions = int(agg["total_sessions"]) if agg else 0
            total_duration = float(agg["total_reading_seconds"]) if agg else 0.0
            active_duration = float(agg["active_reading_seconds"]) if agg else 0.0
            total_words = int(agg["estimated_words_read"]) if agg else 0
            last_sess = agg["last_session_at"] if agg else started_str

            if active_duration > 0:
                avg_wpm = round(total_words / (active_duration / 60.0), 2)
            elif total_sessions > 0:
                avg_wpm = float(agg["avg_session_wpm"])
            else:
                avg_wpm = 0.0

            now_iso = datetime.now(timezone.utc).isoformat()
            conn.execute("""
                INSERT INTO reading_statistics
                (book_id, total_reading_seconds, active_reading_seconds, total_sessions, estimated_words_read, average_wpm, last_session_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(book_id) DO UPDATE SET
                    total_reading_seconds = excluded.total_reading_seconds,
                    active_reading_seconds = excluded.active_reading_seconds,
                    total_sessions = excluded.total_sessions,
                    estimated_words_read = excluded.estimated_words_read,
                    average_wpm = excluded.average_wpm,
                    last_session_at = excluded.last_session_at,
                    updated_at = excluded.updated_at
            """, (
                session.book_id,
                total_duration,
                active_duration,
                total_sessions,
                total_words,
                avg_wpm,
                last_sess,
                now_iso,
            ))
            conn.commit()

    def get_book_statistics(self, book_id: str) -> BookStatistics:
        with self.db.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM reading_statistics WHERE book_id = ?", (book_id,))
            row = cursor.fetchone()
            if row:
                last_session_at = _parse_datetime(row["last_session_at"])
                return BookStatistics(
                    book_id=row["book_id"],
                    total_reading_seconds=float(row["total_reading_seconds"]),
                    active_reading_seconds=float(row["active_reading_seconds"]),
                    total_sessions=int(row["total_sessions"]),
                    estimated_words_read=int(row["estimated_words_read"]),
                    average_wpm=float(row["average_wpm"]),
                    last_session_at=last_session_at,
                )

            # Fallback to computing directly from reading_sessions if reading_statistics not cached
            cursor = conn.execute("""
                SELECT
                    COUNT(*) as total_sessions,
                    COALESCE(SUM(duration_seconds), 0.0) as total_reading_seconds,
                    COALESCE(SUM(active_seconds), 0.0) as active_reading_seconds,
                    COALESCE(SUM(words_read), 0) as estimated_words_read,
                    COALESCE(AVG(wpm), 0.0) as avg_session_wpm,
                    MAX(started_at) as last_session_at
                FROM reading_sessions
                WHERE book_id = ?
            """, (book_id,))
            agg = cursor.fetchone()
            if agg and agg["total_sessions"] > 0:
                active_duration = float(agg["active_reading_seconds"])
                total_words = int(agg["estimated_words_read"])
                if active_duration > 0:
                    avg_wpm = round(total_words / (active_duration / 60.0), 2)
                else:
                    avg_wpm = float(agg["avg_session_wpm"])
                last_sess = _parse_datetime(agg["last_session_at"])
                return BookStatistics(
                    book_id=book_id,
                    total_reading_seconds=float(agg["total_reading_seconds"]),
                    active_reading_seconds=active_duration,
                    total_sessions=int(agg["total_sessions"]),
                    estimated_words_read=total_words,
                    average_wpm=avg_wpm,
                    last_session_at=last_sess,
                )

            return BookStatistics(
                book_id=book_id,
                total_reading_seconds=0.0,
                active_reading_seconds=0.0,
                total_sessions=0,
                estimated_words_read=0,
                average_wpm=0.0,
                last_session_at=None,
            )

    def get_library_statistics(self) -> LibraryStatistics:
        with self.db.get_connection() as conn:
            # Total books and format counts
            cursor = conn.execute("SELECT id, file_format FROM books")
            books = cursor.fetchall()
            total_books = len(books)

            format_counts: dict[str, int] = {}
            for b in books:
                fmt = b["file_format"] or "unknown"
                format_counts[fmt] = format_counts.get(fmt, 0) + 1

            # In progress vs completed
            cursor = conn.execute("""
                SELECT b.id, COALESCE(p.percentage, 0.0) as pct, COUNT(s.id) as session_count
                FROM books b
                LEFT JOIN reading_progress p ON b.id = p.book_id
                LEFT JOIN reading_sessions s ON b.id = s.book_id
                GROUP BY b.id
            """)
            books_in_progress = 0
            books_completed = 0
            for row in cursor.fetchall():
                pct = float(row["pct"])
                sc = int(row["session_count"])
                if pct >= 99.0:
                    books_completed += 1
                elif pct > 0.0 or sc > 0:
                    books_in_progress += 1

            # Aggregated session stats
            cursor = conn.execute("""
                SELECT
                    COALESCE(SUM(duration_seconds), 0.0) as total_duration,
                    COALESCE(SUM(active_seconds), 0.0) as total_active,
                    COALESCE(SUM(words_read), 0) as total_words,
                    COALESCE(AVG(wpm), 0.0) as avg_session_wpm,
                    COUNT(*) as session_count
                FROM reading_sessions
            """)
            sess_agg = cursor.fetchone()
            total_reading_seconds = float(sess_agg["total_duration"]) if sess_agg else 0.0
            active_reading_seconds = float(sess_agg["total_active"]) if sess_agg else 0.0
            total_words_read = int(sess_agg["total_words"]) if sess_agg else 0

            if active_reading_seconds > 0:
                average_wpm = round(total_words_read / (active_reading_seconds / 60.0), 2)
            elif sess_agg and sess_agg["session_count"] > 0:
                average_wpm = float(sess_agg["avg_session_wpm"])
            else:
                average_wpm = 0.0

            return LibraryStatistics(
                total_books=total_books,
                books_in_progress=books_in_progress,
                books_completed=books_completed,
                total_reading_seconds=total_reading_seconds,
                active_reading_seconds=active_reading_seconds,
                total_words_read=total_words_read,
                average_wpm=average_wpm,
                format_counts=format_counts,
            )

    def get_sessions_for_book(self, book_id: str, limit: int = 50) -> list[ReadingSession]:
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM reading_sessions WHERE book_id = ? ORDER BY started_at DESC LIMIT ?",
                (book_id, limit)
            )
            sessions: list[ReadingSession] = []
            for row in cursor.fetchall():
                started_at = _parse_datetime(row["started_at"]) or datetime.now(timezone.utc)
                ended_at = _parse_datetime(row["ended_at"])
                sessions.append(ReadingSession(
                    id=row["id"],
                    book_id=row["book_id"],
                    started_at=started_at,
                    ended_at=ended_at,
                    duration_seconds=float(row["duration_seconds"]),
                    active_seconds=float(row["active_seconds"]),
                    idle_seconds=float(row["idle_seconds"]),
                    words_read=int(row["words_read"]),
                    wpm=float(row["wpm"]),
                ))
            return sessions

