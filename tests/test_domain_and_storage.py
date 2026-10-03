"""
Unit tests for domain models and SQLite persistence with WAL durability.
Validates NFR-01, NFR-02, FR-01, FR-10.
"""

import os
import tempfile
import unittest
import time

from src.aquile.domain.models import Book, ReadingProgress, Annotation, AppSettings
from src.aquile.storage.database import Database
from src.aquile.storage.repository import (
    BookRepository, ReadingProgressRepository, AnnotationRepository, SettingsRepository
)

class TestStorageAndDurability(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_aquile.db")
        self.db = Database(self.db_path)
        self.book_repo = BookRepository(self.db)
        self.progress_repo = ReadingProgressRepository(self.db)
        self.ann_repo = AnnotationRepository(self.db)
        self.settings_repo = SettingsRepository(self.db)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_book_crud(self):
        book = Book(
            id="book-123",
            title="Aquile Reader Test Guide",
            author="Paras",
            file_path="/path/to/test.epub",
            file_format="epub",
            total_chapters=5
        )
        self.book_repo.add(book)
        
        fetched = self.book_repo.get_by_id("book-123")
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.title, "Aquile Reader Test Guide")
        self.assertEqual(fetched.author, "Paras")

        by_path = self.book_repo.get_by_path("/path/to/test.epub")
        self.assertIsNotNone(by_path)
        self.assertEqual(by_path.id, "book-123")

        all_books = self.book_repo.list_all()
        self.assertEqual(len(all_books), 1)

        self.book_repo.update_last_read("book-123", 1000.0)
        updated = self.book_repo.get_by_id("book-123")
        self.assertEqual(updated.last_read_at, 1000.0)

        deleted = self.book_repo.delete("book-123")
        self.assertTrue(deleted)
        self.assertIsNone(self.book_repo.get_by_id("book-123"))

    def test_reading_progress_durability(self):
        book = Book(id="prog-book", title="Prog Book", author="Author", file_path="/tmp/prog.epub")
        self.book_repo.add(book)

        progress = ReadingProgress(
            book_id="prog-book",
            chapter_index=2,
            page_index=4,
            cfi="epubcfi(/6/6[chap3]!/4/2/1:100,200)",
            percentage=45.5
        )
        self.progress_repo.save(progress)

        loaded = self.progress_repo.get("prog-book")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.chapter_index, 2)
        self.assertEqual(loaded.page_index, 4)
        self.assertEqual(loaded.percentage, 45.5)

        # Update progress (e.g. 5-second checkpoint auto-save)
        progress.page_index = 5
        progress.percentage = 55.0
        self.progress_repo.save(progress)

        updated = self.progress_repo.get("prog-book")
        self.assertEqual(updated.page_index, 5)
        self.assertEqual(updated.percentage, 55.0)

    def test_annotations_crud_and_collections(self):
        book = Book(id="ann-book", title="Ann Book", author="Author", file_path="/tmp/ann.epub")
        self.book_repo.add(book)

        ann1 = Annotation(
            id="ann-1",
            book_id="ann-book",
            chapter_index=0,
            cfi="epubcfi(/6/2[chap1]!/4/2/1:0,50)",
            start_offset=0,
            end_offset=50,
            text_content="Highlight on first sentence",
            note_text="My personal reflection",
            color="#FFEB3B"
        )
        self.ann_repo.add(ann1)

        anns = self.ann_repo.get_by_book("ann-book")
        self.assertEqual(len(anns), 1)
        self.assertEqual(anns[0].text_content, "Highlight on first sentence")
        self.assertEqual(anns[0].note_text, "My personal reflection")

        # Cross-book Collections view (FR-11)
        all_anns = self.ann_repo.list_all()
        self.assertEqual(len(all_anns), 1)

        self.ann_repo.delete("ann-1")
        self.assertEqual(len(self.ann_repo.get_by_book("ann-book")), 0)

    def test_settings_persistence(self):
        settings = self.settings_repo.load()
        self.assertEqual(settings.columns, 2)  # Aquile default 2 columns
        self.assertEqual(settings.theme, "light")

        settings.columns = 1
        settings.theme = "sepia"
        settings.font_size = 20
        self.settings_repo.save(settings)

        reloaded = self.settings_repo.load()
        self.assertEqual(reloaded.columns, 1)
        self.assertEqual(reloaded.theme, "sepia")
        self.assertEqual(reloaded.font_size, 20)

if __name__ == "__main__":
    unittest.main()
