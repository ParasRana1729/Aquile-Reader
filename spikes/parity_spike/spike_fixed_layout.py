#!/usr/bin/env python3
"""
spike_fixed_layout.py — Parity Spike: Fixed-Layout Formats (PDF and CBZ Comics).
Tests page enumeration, ordering (LTR vs RTL Manga), and spread modes.
Validates FR-06, FR-07, AT-04.
"""

import os
import zipfile
import re

class ComicArchiveEngine:
    SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}

    def __init__(self, cbz_path):
        self.cbz_path = cbz_path
        self.pages = []
        self._load_pages()

    def _load_pages(self):
        with zipfile.ZipFile(self.cbz_path, "r") as z:
            names = z.namelist()
            # Natural sort order for comic pages
            image_files = [
                n for n in names 
                if os.path.splitext(n)[1].lower() in self.SUPPORTED_EXTENSIONS
                and not n.startswith("__MACOSX/")
            ]
            self.pages = sorted(image_files, key=self._natural_key)

    @staticmethod
    def _natural_key(text):
        return [int(c) if c.isdigit() else c.lower() for c in re.split(r"(\d+)", text)]

    def get_spreads(self, reading_direction="ltr", mode="double"):
        """
        Calculates page spreads:
        - 'single': 1 page per view
        - 'double': 2 pages side-by-side (cover usually single, then pairs)
        - reading_direction: 'ltr' (Western) or 'rtl' (Manga)
        """
        if mode == "single":
            return [[p] for p in self.pages]

        # Double page mode: Cover alone, subsequent in pairs
        spreads = []
        if not self.pages:
            return spreads

        # Cover
        spreads.append([self.pages[0]])
        
        idx = 1
        while idx < len(self.pages):
            pair = self.pages[idx:idx+2]
            if reading_direction == "rtl" and len(pair) == 2:
                # In RTL (Manga), right page is read first (displayed on right)
                pair = [pair[1], pair[0]]
            spreads.append(pair)
            idx += 2

        return spreads

class MinimalPdfInspector:
    """
    Inspects PDF structure for page objects and media boxes without heavy external dependencies.
    """
    def __init__(self, pdf_path):
        self.pdf_path = pdf_path
        self.page_count = 0
        self._inspect()

    def _inspect(self):
        with open(self.pdf_path, "rb") as f:
            content = f.read().decode("latin1")
            # Count page objects: /Type /Page (excluding /Type /Pages)
            matches = re.findall(r"/Type\s*/Page\b", content)
            self.page_count = len(matches)

def test_fixed_layout():
    fixtures_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "fixtures"))
    cbz_path = os.path.join(fixtures_dir, "sample-comic.cbz")
    pdf_path = os.path.join(fixtures_dir, "sample-doc.pdf")

    # 1. Test CBZ Comic
    comic = ComicArchiveEngine(cbz_path)
    assert len(comic.pages) == 3, f"Expected 3 comic pages, found {len(comic.pages)}"
    
    ltr_spreads = comic.get_spreads(reading_direction="ltr", mode="double")
    # Expected: [ [cover], [page1, page2] ]
    assert len(ltr_spreads) == 2
    assert ltr_spreads[0] == ["001_cover.png"]
    assert ltr_spreads[1] == ["002_page1.png", "003_page2.png"]

    rtl_spreads = comic.get_spreads(reading_direction="rtl", mode="double")
    # In RTL: [ [cover], [page2, page1] ]
    assert rtl_spreads[1] == ["003_page2.png", "002_page1.png"], "RTL manga spread order failed!"

    # 2. Test PDF
    pdf = MinimalPdfInspector(pdf_path)
    assert pdf.page_count == 2, f"Expected 2 PDF pages, found {pdf.page_count}"

    return {
        "cbz_pages": len(comic.pages),
        "cbz_ltr_spreads": ltr_spreads,
        "cbz_rtl_spreads": rtl_spreads,
        "pdf_pages": pdf.page_count
    }

if __name__ == "__main__":
    res = test_fixed_layout()
    print("Fixed-Layout Formats Spike Passed:")
    print(f"  CBZ: {res['cbz_pages']} pages loaded, LTR/RTL spread calculation verified")
    print(f"  PDF: {res['pdf_pages']} pages indexed successfully")
