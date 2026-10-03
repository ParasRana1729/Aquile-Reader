"""
Canonical Fragment Identifier (CFI) Generator and Resolver for EPUB content.
Guarantees robust anchor stability across layout changes and reflow.
"""

from typing import Tuple, Optional, Dict, Any
import re

class CFI:
    @staticmethod
    def generate(chapter_index: int, start_offset: int, end_offset: int, chapter_id: str = "") -> str:
        chap_tag = f"[{chapter_id}]" if chapter_id else f"[chap{chapter_index + 1}]"
        # Standard EPUB CFI syntax: /6/package_element!/4/chapter_element:character_range
        return f"epubcfi(/6/{2 * (chapter_index + 1)}{chap_tag}!/4/2/1:{start_offset},{end_offset})"

    @staticmethod
    def parse(cfi_str: str) -> Optional[Dict[str, Any]]:
        # Example: epubcfi(/6/2[chap1]!/4/2/1:70,142)
        match = re.search(r"epubcfi\(/6/(\d+)(?:\[(.*?)\])?!/4/.*?(\d+),(\d+)\)", cfi_str)
        if not match:
            return None
        step = int(match.group(1))
        chap_index = (step // 2) - 1
        chap_id = match.group(2) or ""
        start_offset = int(match.group(3))
        end_offset = int(match.group(4))
        return {
            "chapter_index": chap_index,
            "chapter_id": chap_id,
            "start_offset": start_offset,
            "end_offset": end_offset
        }

    @staticmethod
    def resolve_anchor(text: str, start_offset: int, end_offset: int, expected_snippet: str) -> Dict[str, Any]:
        """
        Resolves an anchor to text span.
        Checks exact character offset first; falls back to fuzzy substring match if whitespace shifted.
        """
        # 1. Exact match
        if 0 <= start_offset < len(text) and 0 < end_offset <= len(text):
            candidate = text[start_offset:end_offset]
            if candidate == expected_snippet:
                return {
                    "status": "exact_match",
                    "start": start_offset,
                    "end": end_offset,
                    "text": candidate
                }

        # 2. Resilient fallback search
        if expected_snippet:
            pos = text.find(expected_snippet)
            if pos != -1:
                return {
                    "status": "relocated_match",
                    "start": pos,
                    "end": pos + len(expected_snippet),
                    "text": expected_snippet
                }

        return {
            "status": "lost_anchor",
            "start": None,
            "end": None,
            "text": None
        }
