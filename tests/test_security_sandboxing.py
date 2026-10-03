"""
Unit tests for untrusted input handling and archive security defenses.
Validates NFR-06, AT-02.
"""

import os
import unittest
from src.aquile.reader.epub_parser import EpubParser, SecurityError, CorruptEpubError

FIXTURES_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "fixtures"))

class TestSecuritySandboxing(unittest.TestCase):
    def test_path_traversal_rejection(self):
        traversal_path = os.path.join(FIXTURES_DIR, "path-traversal.epub")
        with self.assertRaises(SecurityError) as ctx:
            EpubParser(traversal_path)
        self.assertIn("path traversal", str(ctx.exception).lower())

    def test_corrupt_archive_rejection(self):
        corrupt_path = os.path.join(FIXTURES_DIR, "malformed-archive.epub")
        with self.assertRaises(CorruptEpubError):
            EpubParser(corrupt_path)

    def test_missing_file_handling(self):
        missing_path = os.path.join(FIXTURES_DIR, "non_existent_file.epub")
        with self.assertRaises(FileNotFoundError):
            EpubParser(missing_path)

if __name__ == "__main__":
    unittest.main()
