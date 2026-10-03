#!/usr/bin/env python3
"""
spike_epub_pagination.py — Parity Spike: EPUB Parsing and Deterministic Pagination Algorithm.
Tests one-column and two-column pagination calculations across viewport dimensions.
Validates VP-01, VP-02, FR-05, FR-08.
"""

import os
import zipfile
import xml.etree.ElementTree as ET
import re

class EpubParser:
    def __init__(self, epub_path):
        self.epub_path = epub_path
        self.spine_items = []
        self.manifest = {}
        self.chapters = []
        self._parse()

    def _parse(self):
        with zipfile.ZipFile(self.epub_path, "r") as z:
            # Read container.xml
            container_xml = z.read("META-INF/container.xml").decode("utf-8")
            root = ET.fromstring(container_xml)
            ns = {"c": "urn:oasis:names:tc:opendocument:xmlns:container"}
            rootfile = root.find(".//c:rootfile", ns)
            opf_path = rootfile.attrib["full-path"]
            opf_dir = os.path.dirname(opf_path)

            # Read OPF
            opf_xml = z.read(opf_path).decode("utf-8")
            opf_root = ET.fromstring(opf_xml)
            ns_opf = {"opf": "http://www.idpf.org/2007/opf"}

            for item in opf_root.findall(".//opf:item", ns_opf):
                item_id = item.attrib["id"]
                href = item.attrib["href"]
                self.manifest[item_id] = os.path.normpath(os.path.join(opf_dir, href))

            spine = opf_root.find(".//opf:spine", ns_opf)
            for itemref in spine.findall(".//opf:itemref", ns_opf):
                idref = itemref.attrib["idref"]
                if idref in self.manifest:
                    self.spine_items.append(self.manifest[idref])

            for path in self.spine_items:
                content = z.read(path).decode("utf-8")
                self.chapters.append({"path": path, "content": content})

class PaginationEngine:
    """
    Simulates deterministic column & page layout calculations based on logical viewport geometry,
    font size, line-height, and column configuration.
    """
    def __init__(self, viewport_width, viewport_height, columns=1, font_size=16, line_height=1.5):
        self.viewport_width = viewport_width
        self.viewport_height = viewport_height
        self.columns = columns
        self.font_size = font_size
        self.line_height = line_height

    def paginate_text(self, text):
        # Character-based layout estimation:
        # Average character width approx 0.55 * font_size for proportional fonts
        avg_char_width = self.font_size * 0.55
        line_height_px = self.font_size * self.line_height
        
        # Usable dimensions considering margins (5% on each side)
        usable_width = self.viewport_width * 0.90
        usable_height = self.viewport_height * 0.88
        
        column_width = (usable_width - ((self.columns - 1) * 32)) / self.columns
        chars_per_line = max(20, int(column_width / avg_char_width))
        lines_per_column = max(5, int(usable_height / line_height_px))
        chars_per_column = chars_per_line * lines_per_column
        chars_per_page = chars_per_column * self.columns

        words = text.split()
        pages = []
        current_page = []
        current_len = 0

        for word in words:
            word_len = len(word) + 1
            if current_len + word_len > chars_per_page and current_page:
                pages.append(" ".join(current_page))
                current_page = [word]
                current_len = word_len
            else:
                current_page.append(word)
                current_len += word_len

        if current_page:
            pages.append(" ".join(current_page))

        return {
            "columns": self.columns,
            "viewport": (self.viewport_width, self.viewport_height),
            "font_size": self.font_size,
            "chars_per_line": chars_per_line,
            "lines_per_column": lines_per_column,
            "page_count": len(pages),
            "pages": pages
        }

def test_epub_pagination():
    fixtures_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "fixtures"))
    epub_path = os.path.join(fixtures_dir, "canonical-text.epub")
    assert os.path.isfile(epub_path), f"Missing fixture: {epub_path}"

    parser = EpubParser(epub_path)
    assert len(parser.chapters) == 3, f"Expected 3 chapters, found {len(parser.chapters)}"

    # Strip HTML tags for pagination text extraction
    text_content = ""
    for chap in parser.chapters:
        clean = re.sub(r"<[^>]+>", " ", chap["content"])
        text_content += " " + clean

    # Viewports from PRD §4.1: 1024x768, 1366x768, 1920x1080
    viewports = [(1024, 768), (1366, 768), (1920, 1080)]
    results = []

    for vw, vh in viewports:
        # 1-column layout
        eng_1col = PaginationEngine(vw, vh, columns=1, font_size=16)
        res_1col = eng_1col.paginate_text(text_content)
        
        # 2-column layout (Aquile Reader signature feature)
        eng_2col = PaginationEngine(vw, vh, columns=2, font_size=16)
        res_2col = eng_2col.paginate_text(text_content)

        assert res_1col["page_count"] > 0
        assert res_2col["page_count"] > 0
        # In a 2-column spread on the same viewport, each page displays double the columns, so page_count should be <= 1-column page_count
        assert res_2col["page_count"] <= res_1col["page_count"], "2-column mode should yield fewer or equal pages than 1-column mode"
        
        results.append({
            "viewport": f"{vw}x{vh}",
            "1_column_pages": res_1col["page_count"],
            "2_column_pages": res_2col["page_count"],
            "chars_per_line_1col": res_1col["chars_per_line"],
            "chars_per_line_2col": res_2col["chars_per_line"]
        })

    return results

if __name__ == "__main__":
    out = test_epub_pagination()
    print("EPUB Pagination Spike Passed:")
    for r in out:
        print(f"  Viewport {r['viewport']}: 1-col={r['1_column_pages']} pages, 2-col={r['2_column_pages']} pages (line widths: {r['chars_per_line_1col']} vs {r['chars_per_line_2col']} chars)")
