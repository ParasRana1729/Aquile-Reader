"""Tests for cover storage and filename title cleanup (Home grid fixes)."""

import os
import tempfile
import unittest

from src.aquile.covers import save_cover, clean_display_title, get_covers_dir


def _png_bytes() -> bytes:
    # Minimal 1x1 PNG (valid magic + IHDR + IDAT).
    import zlib
    import struct

    def chunk(tag: bytes, payload: bytes) -> bytes:
        return struct.pack(">I", len(payload)) + tag + payload + struct.pack(
            ">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    raw = b"\x00\x00\x00\x00"
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


class TestCovers(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_xdg = os.environ.get("XDG_DATA_HOME")
        os.environ["XDG_DATA_HOME"] = self.tmp.name

    def tearDown(self):
        if self.old_xdg is None:
            os.environ.pop("XDG_DATA_HOME", None)
        else:
            os.environ["XDG_DATA_HOME"] = self.old_xdg
        self.tmp.cleanup()

    def test_save_valid_png(self):
        path = save_cover("book-1", _png_bytes(), "image/png")
        self.assertIsNotNone(path)
        self.assertTrue(os.path.isfile(path))
        self.assertTrue(path.endswith(".png"))

    def test_reject_non_image(self):
        self.assertIsNone(save_cover("book-2", b"not an image at all", "text/plain"))

    def test_reject_oversize(self):
        big = b"\x89PNG\r\n\x1a\n" + b"\x00" * (6 * 1024 * 1024)
        self.assertIsNone(save_cover("book-3", big, "image/png"))

    def test_reject_empty(self):
        self.assertIsNone(save_cover("book-4", b"", "image/png"))
        self.assertIsNone(save_cover("", _png_bytes(), "image/png"))

    def test_covers_dir_under_xdg(self):
        d = get_covers_dir()
        self.assertTrue(d.startswith(self.tmp.name))
        self.assertTrue(os.path.isdir(d))


class TestCleanTitle(unittest.TestCase):
    def test_dashes_to_title(self):
        self.assertEqual(
            clean_display_title("machiavelli-niccolo-the-prince-1985.epub"),
            "Machiavelli Niccolo The Prince 1985")

    def test_underscores_and_dots(self):
        self.assertEqual(
            clean_display_title("/books/the_great.gatsby.epub"), "The Great Gatsby")

    def test_already_titled_kept(self):
        self.assertEqual(
            clean_display_title("A Scandal in Bohemia.epub"), "A Scandal in Bohemia")


if __name__ == "__main__":
    unittest.main()
