"""
Repositories for Book, Progress, Annotation, and Settings persistence.
"""

import time
from typing import List, Optional
from ..domain.models import Book, ReadingProgress, Annotation, AppSettings
from .database import Database

class BookRepository:
    def __init__(self, db: Database):
        self.db = db

    def add(self, book: Book) -> Book:
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
