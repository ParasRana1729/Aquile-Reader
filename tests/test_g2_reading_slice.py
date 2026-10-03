"""
Integration tests for the Gate G2 Internal Reading Slice.
Verifies the complete workflow:
Import eBook -> Library -> Open Reader -> Two-Column Pagination -> Navigate -> Annotate -> Auto-save -> Resume.
Validates FR-01, FR-05, FR-08, FR-10, FR-11, FR-20, NFR-01, UB-01, VP-01.
"""

import os
import tempfile
import unittest
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw

from src.aquile.app import AquileReaderApp
from src.aquile.domain.models import Book, Annotation
from src.aquile.reader.cfi import CFI

FIXTURES_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "fixtures"))

class TestG2ReadingSlice(unittest.TestCase):
    def setUp(self):
        Gtk.init()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "g2_test.db")
        self.app = AquileReaderApp(db_path=self.db_path)
        self.app.register()
        self.app.activate()

    def tearDown(self):
        if self.app.current_reader_view:
            self.app.current_reader_view.cleanup()
        self.temp_dir.cleanup()

    def test_complete_local_reading_slice(self):
        # 1. Import eBook into Library (FR-01)
        epub_file = os.path.join(FIXTURES_DIR, "canonical-text.epub")
        self.assertTrue(os.path.exists(epub_file))

        self.app.library_view.import_file(epub_file)
        books = self.app.book_repo.list_all()
        self.assertEqual(len(books), 1)
        book = books[0]
        self.assertEqual(book.title, "Canonical Text Fixture")
        self.assertEqual(book.author, "Test Fixture Author")
        self.assertEqual(book.file_format, "epub")

        # 2. Verify Reader View is active (FR-05, VP-01)
        self.assertIsNotNone(self.app.current_reader_view)
        reader = self.app.current_reader_view
        self.assertEqual(self.app.nav_stack.get_visible_child_name(), "reader")

        # 3. Verify Two-Column Layout (Signature Aquile Reader feature)
        self.assertEqual(reader.settings.columns, 2)
        self.assertIsNotNone(reader.paginator)
        cur_page = reader.paginator.get_page(reader.current_page_idx)
        self.assertEqual(cur_page.columns, 2)
        self.assertTrue(len(cur_page.left_column) > 0)

        # Switch to Chapter 2 (long chapter with two-column spread)
        reader._on_chapter_selected(2)
        chap2_page = reader.paginator.get_page(0)
        self.assertEqual(chap2_page.columns, 2)
        self.assertTrue(len(chap2_page.left_column) > 0)
        self.assertTrue(len(chap2_page.right_column) > 0)

        # 4. Navigate Pages
        initial_page = reader.current_page_idx
        reader.next_page()
        self.assertEqual(reader.current_page_idx, initial_page + 1)
        
        # 5. Add an Annotation / Bookmark (FR-10)
        sample_text = cur_page.left_column[:50]
        ann = Annotation(
            book_id=book.id,
            chapter_index=reader.current_chapter_idx,
            cfi=CFI.generate(reader.current_chapter_idx, 0, len(sample_text)),
            start_offset=0,
            end_offset=len(sample_text),
            text_content=sample_text,
            note_text="Important concept for review",
            color="#FFEB3B"
        )
        self.app.ann_repo.add(ann)

        # Verify annotation persistence in SQLite WAL
        saved_anns = self.app.ann_repo.get_by_book(book.id)
        self.assertEqual(len(saved_anns), 1)
        self.assertEqual(saved_anns[0].note_text, "Important concept for review")

        # Verify Collections Cross-Book View (FR-11)
        all_anns = self.app.ann_repo.list_all()
        self.assertEqual(len(all_anns), 1)

        # 6. Test Periodic Auto-save Checkpoint (NFR-01)
        reader._save_checkpoint()
        progress = self.app.progress_repo.get(book.id)
        self.assertIsNotNone(progress)
        self.assertEqual(progress.page_index, initial_page + 1)

        # 7. Close Reader and Return to Library (Orderly Shutdown)
        self.app.show_library()
        self.assertIsNone(self.app.current_reader_view)
        self.assertEqual(self.app.nav_stack.get_visible_child_name(), "library")

        # 8. Reopen Book and Verify Reading Resume
        self.app.open_book(book)
        resumed_reader = self.app.current_reader_view
        self.assertIsNotNone(resumed_reader)
        self.assertEqual(resumed_reader.current_page_idx, initial_page + 1)

if __name__ == "__main__":
    unittest.main()
