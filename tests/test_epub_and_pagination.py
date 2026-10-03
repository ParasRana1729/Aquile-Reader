"""
Unit tests for EPUB parser and multi-column pagination engine.
Validates FR-05, FR-08, VP-01, VP-02.
"""

import os
import unittest
from src.aquile.reader.epub_parser import EpubParser
from src.aquile.reader.pagination import ChapterPaginator

FIXTURES_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "fixtures"))

class TestEpubAndPagination(unittest.TestCase):
    def test_parse_canonical_epub(self):
        epub_path = os.path.join(FIXTURES_DIR, "canonical-text.epub")
        parser = EpubParser(epub_path)
        self.assertEqual(parser.title, "Canonical Text Fixture")
        self.assertEqual(parser.author, "Test Fixture Author")
        self.assertEqual(len(parser.chapters), 3)
        self.assertEqual(parser.chapters[0]["title"], "Chapter 1: The Beginning of Reading")
        self.assertTrue(len(parser.chapters[0]["clean_text"]) > 100)
        self.assertTrue(len(parser.toc_items) >= 3)

    def test_parse_multilingual_rtl_epub(self):
        epub_path = os.path.join(FIXTURES_DIR, "multilingual-rtl.epub")
        parser = EpubParser(epub_path)
        self.assertEqual(parser.title, "Multilingual RTL Fixture")
        self.assertEqual(len(parser.chapters), 1)
        # Check Arabic and Hebrew substrings present
        content = parser.chapters[0]["clean_text"]
        self.assertIn("العربية", content)
        self.assertIn("בעברית", content)

    def test_two_column_pagination(self):
        epub_path = os.path.join(FIXTURES_DIR, "canonical-text.epub")
        parser = EpubParser(epub_path)
        # Use chapter 3 which has 24 paragraphs
        chap3_text = parser.chapters[2]["clean_text"]

        # Viewport: 1024x768, 2 columns
        paginator = ChapterPaginator(chap3_text, 1024, 768, columns=2, font_size=16)
        self.assertTrue(paginator.page_count > 1)
        
        page0 = paginator.get_page(0)
        self.assertEqual(page0.columns, 2)
        self.assertTrue(len(page0.left_column) > 0)
        self.assertTrue(len(page0.right_column) > 0)

    def test_parse_missing_metadata_coverless_epub(self):
        epub_path = os.path.join(FIXTURES_DIR, "missing-metadata-coverless.epub")
        self.assertTrue(os.path.exists(epub_path), "missing-metadata-coverless.epub must exist")
        parser = EpubParser(epub_path)
        self.assertEqual(parser.title, "Untitled")
        self.assertEqual(parser.author, "Unknown Author")
        self.assertIsNone(parser.cover_data)
        self.assertEqual(len(parser.chapters), 2)
        self.assertEqual(parser.chapters[0]["title"], "Chapter 1: Headless Content")
        self.assertTrue(len(parser.chapters[0]["clean_text"]) > 50)
        # Verify pagination works on headless fixture
        paginator = ChapterPaginator(parser.chapters[0]["clean_text"], 1024, 768, columns=2, font_size=16)
        self.assertGreaterEqual(paginator.page_count, 1)

if __name__ == "__main__":
    unittest.main()
