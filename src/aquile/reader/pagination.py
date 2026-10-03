"""
Deterministic Two-Column and One-Column Pagination Engine for Aquile Reader.
Implements layout geometry, multi-column segmentation, and reading location calculations.
"""

from typing import List, Dict, Any, Tuple
import math

class PageView:
    def __init__(self, page_index: int, total_pages: int, columns: int, left_column: str, right_column: str = ""):
        self.page_index = page_index
        self.total_pages = total_pages
        self.columns = columns
        self.left_column = left_column
        self.right_column = right_column

class ChapterPaginator:
    def __init__(self, text: str, viewport_width: int, viewport_height: int, columns: int = 2, font_size: int = 16, line_height: float = 1.6):
        self.raw_text = text
        self.viewport_width = viewport_width
        self.viewport_height = viewport_height
        self.columns = columns
        self.font_size = font_size
        self.line_height = line_height
        self.pages: List[PageView] = []
        self._paginate()

    def _paginate(self):
        avg_char_width = self.font_size * 0.55
        line_height_px = self.font_size * self.line_height

        # 5% margin on each side, header/footer spacing
        usable_width = self.viewport_width * 0.90
        usable_height = self.viewport_height * 0.85

        gutter_width = 36 if self.columns > 1 else 0
        column_width = (usable_width - ((self.columns - 1) * gutter_width)) / self.columns

        chars_per_line = max(25, int(column_width / avg_char_width))
        lines_per_col = max(5, int(usable_height / line_height_px))
        chars_per_column = chars_per_line * lines_per_col

        paragraphs = self.raw_text.split("\n\n")
        column_blocks: List[str] = []
        current_col_paras: List[str] = []
        current_col_len = 0

        for para in paragraphs:
            para_len = len(para)
            if current_col_len + para_len > chars_per_column and current_col_paras:
                column_blocks.append("\n\n".join(current_col_paras))
                current_col_paras = [para]
                current_col_len = para_len
            else:
                current_col_paras.append(para)
                current_col_len += para_len + 2

        if current_col_paras:
            column_blocks.append("\n\n".join(current_col_paras))

        if not column_blocks:
            column_blocks = [""]

        # Group columns into pages
        self.pages = []
        if self.columns == 2:
            page_idx = 0
            for i in range(0, len(column_blocks), 2):
                left = column_blocks[i]
                right = column_blocks[i + 1] if i + 1 < len(column_blocks) else ""
                self.pages.append(PageView(page_idx, 0, 2, left, right))
                page_idx += 1
        else:
            for idx, col in enumerate(column_blocks):
                self.pages.append(PageView(idx, len(column_blocks), 1, col, ""))

        total_pages = len(self.pages)
        for p in self.pages:
            p.total_pages = total_pages

    def get_page(self, page_index: int) -> PageView:
        if not self.pages:
            return PageView(0, 1, self.columns, "")
        idx = max(0, min(page_index, len(self.pages) - 1))
        return self.pages[idx]

    @property
    def page_count(self) -> int:
        return len(self.pages)
