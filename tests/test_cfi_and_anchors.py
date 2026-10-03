"""
Unit tests for EPUB Canonical Fragment Identifier (CFI) generation and anchor resolution.
Validates FR-10, NFR-01.
"""

import unittest
from src.aquile.reader.cfi import CFI

class TestCfiAndAnchors(unittest.TestCase):
    def test_cfi_generation_and_parsing(self):
        cfi_str = CFI.generate(chapter_index=1, start_offset=150, end_offset=280, chapter_id="chap2")
        self.assertEqual(cfi_str, "epubcfi(/6/4[chap2]!/4/2/1:150,280)")

        parsed = CFI.parse(cfi_str)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["chapter_index"], 1)
        self.assertEqual(parsed["chapter_id"], "chap2")
        self.assertEqual(parsed["start_offset"], 150)
        self.assertEqual(parsed["end_offset"], 280)

    def test_anchor_resolution_exact_and_fuzzy(self):
        text = "Aquile Reader brings elegant typography and two-column reading to Ubuntu."
        target = "two-column reading"
        start = text.index(target)
        end = start + len(target)

        # 1. Exact match
        res_exact = CFI.resolve_anchor(text, start, end, target)
        self.assertEqual(res_exact["status"], "exact_match")
        self.assertEqual(res_exact["text"], target)

        # 2. Shifted offset (simulating reflow or whitespace shift)
        shifted_start = start + 5
        shifted_end = end + 5
        res_fallback = CFI.resolve_anchor(text, shifted_start, shifted_end, target)
        self.assertEqual(res_fallback["status"], "relocated_match")
        self.assertEqual(res_fallback["start"], start)
        self.assertEqual(res_fallback["end"], end)

        # 3. Missing snippet
        res_missing = CFI.resolve_anchor(text, start, end, "completely non-existent phrase")
        self.assertEqual(res_missing["status"], "lost_anchor")

if __name__ == "__main__":
    unittest.main()
