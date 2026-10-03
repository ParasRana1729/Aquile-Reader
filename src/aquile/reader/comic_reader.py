"""
Comic archive engine for Aquile Reader.
Handles CBR / CBZ extraction, alphanumeric natural sorting,
spread calculations (single-page, double-page Western LTR, Manga RTL inversion),
and image texture loading with resilient decoding fallback (FR-01, FR-06, FR-07, AT-04).
"""

import os
import re
import io
import zipfile
import ctypes
import ctypes.util
from typing import Optional, List


class ComicError(Exception):
    """Base exception for comic archive processing."""
    pass


class CorruptComicError(ComicError, ValueError):
    """Raised when an archive is corrupted, malformed, or cannot be parsed."""
    pass


class ComicSecurityError(ComicError, ValueError):
    """Raised when an archive entry attempts path traversal or unsafe file access."""
    pass


def _get_libarchive():
    """Locates and loads libarchive shared library via ctypes."""
    candidates = ["libarchive.so.13", "libarchive.so"]
    found = ctypes.util.find_library("archive")
    if found:
        candidates.append(found)

    for name in candidates:
        try:
            lib = ctypes.CDLL(name)
            lib.archive_read_new.restype = ctypes.c_void_p
            lib.archive_read_support_filter_all.argtypes = [ctypes.c_void_p]
            lib.archive_read_support_format_all.argtypes = [ctypes.c_void_p]
            lib.archive_read_open_filename.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_size_t]
            lib.archive_read_open_filename.restype = ctypes.c_int
            lib.archive_read_next_header.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
            lib.archive_read_next_header.restype = ctypes.c_int
            lib.archive_entry_pathname.argtypes = [ctypes.c_void_p]
            lib.archive_entry_pathname.restype = ctypes.c_char_p
            lib.archive_read_data.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t]
            lib.archive_read_data.restype = ctypes.c_ssize_t
            lib.archive_error_string.argtypes = [ctypes.c_void_p]
            lib.archive_error_string.restype = ctypes.c_char_p
            lib.archive_read_free.argtypes = [ctypes.c_void_p]
            lib.archive_read_free.restype = ctypes.c_int
            return lib
        except (OSError, AttributeError):
            continue
    return None


class ComicArchiveEngine:
    """
    Archive engine for CBZ and CBR comic book formats.
    Provides page enumeration, natural alphanumeric ordering, spread pairing,
    and image bytes / Gdk.Texture extraction.
    """

    SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".avif", ".tiff", ".tif"}

    # Guaranteed valid 1x1 RGBA PNG bytes for resilient decode fallback
    _FALLBACK_PNG = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06"
        b"\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\xcf\xc0\xf0\x1f\x00\x05"
        b"\x00\x01\xff\x89\x99=\x1d\x00\x00\x00\x00IEND\xaeB`\x82"
    )

    def __init__(self, file_path: str):
        self.backend: str = "zip"
        self._zip: Optional[zipfile.ZipFile] = None
        self._raw_entries: List[str] = []
        self.pages: List[str] = []
        self._image_cache: dict[int, bytes] = {}

        self.file_path = str(file_path)
        if not os.path.exists(self.file_path):
            raise FileNotFoundError(f"Comic archive not found: {self.file_path}")
        if not os.path.isfile(self.file_path):
            raise ValueError(f"Path is not a regular file: {self.file_path}")

        self._open_archive()
        self._load_and_sort_pages()

    @staticmethod
    def _is_path_traversal(name: str) -> bool:
        """Checks whether an archive entry path attempts directory traversal."""
        if name.startswith("/") or name.startswith("\\"):
            return True
        if len(name) > 1 and name[1] == ":":
            return True
        parts = re.split(r"[\\/]+", name)
        if ".." in parts:
            return True
        return False

    def _open_archive(self):
        """Opens the archive file using zipfile (CBZ) or libarchive (CBR/fallback)."""
        if os.path.getsize(self.file_path) == 0:
            raise CorruptComicError(f"Corrupt or empty comic archive: {self.file_path}")

        lower_path = self.file_path.lower()
        is_zip = zipfile.is_zipfile(self.file_path)

        if is_zip:
            try:
                self._zip = zipfile.ZipFile(self.file_path, "r")
                self.backend = "zip"
                for info in self._zip.infolist():
                    name = info.filename
                    if self._is_path_traversal(name):
                        raise ComicSecurityError(f"Path traversal detected in archive entry: {name}")
                    self._raw_entries.append(name)
            except (zipfile.BadZipFile, zipfile.LargeZipFile) as e:
                raise CorruptComicError(f"Corrupt or invalid zip archive: {e}") from e
        elif lower_path.endswith(".cbr") or lower_path.endswith(".rar"):
            self._open_via_libarchive()
        else:
            # Try libarchive as fallback for non-standard extensions
            try:
                self._open_via_libarchive()
            except ComicSecurityError:
                raise
            except Exception as e:
                raise CorruptComicError(f"Unsupported or corrupt comic archive: {e}") from e

    def _open_via_libarchive(self):
        """Reads archive entry list via libarchive C library."""
        lib = _get_libarchive()
        if not lib:
            raise CorruptComicError("libarchive is not available on this system to open CBR archive")

        a = lib.archive_read_new()
        lib.archive_read_support_filter_all(a)
        lib.archive_read_support_format_all(a)

        ret = lib.archive_read_open_filename(a, self.file_path.encode("utf-8"), 65536)
        if ret != 0:
            err = lib.archive_error_string(a)
            err_msg = err.decode("utf-8", "replace") if err else "Archive open error"
            lib.archive_read_free(a)
            raise CorruptComicError(f"Corrupt or invalid archive: {err_msg}")

        entry = ctypes.c_void_p()
        raw_entries: List[str] = []
        try:
            while True:
                r = lib.archive_read_next_header(a, ctypes.byref(entry))
                if r != 0:
                    break
                pathname = lib.archive_entry_pathname(entry)
                if pathname:
                    name = pathname.decode("utf-8", "replace")
                    if self._is_path_traversal(name):
                        raise ComicSecurityError(f"Path traversal detected in archive entry: {name}")
                    raw_entries.append(name)
        finally:
            lib.archive_read_free(a)

        self.backend = "libarchive"
        self._raw_entries = raw_entries

    def _read_libarchive_entry(self, target_entry: str) -> bytes:
        """Extracts bytes of a single entry from a libarchive-backed archive."""
        lib = _get_libarchive()
        if not lib:
            raise CorruptComicError("libarchive is not available")

        a = lib.archive_read_new()
        lib.archive_read_support_filter_all(a)
        lib.archive_read_support_format_all(a)

        ret = lib.archive_read_open_filename(a, self.file_path.encode("utf-8"), 65536)
        if ret != 0:
            lib.archive_read_free(a)
            raise CorruptComicError(f"Failed opening archive for reading entry: {target_entry}")

        entry = ctypes.c_void_p()
        data = None
        try:
            while True:
                r = lib.archive_read_next_header(a, ctypes.byref(entry))
                if r != 0:
                    break
                pathname = lib.archive_entry_pathname(entry)
                if pathname and pathname.decode("utf-8", "replace") == target_entry:
                    chunks = []
                    buf = ctypes.create_string_buffer(65536)
                    while True:
                        n = lib.archive_read_data(a, buf, 65536)
                        if n <= 0:
                            break
                        chunks.append(buf.raw[:n])
                    data = b"".join(chunks)
                    break
        finally:
            lib.archive_read_free(a)

        if data is None:
            raise KeyError(f"Entry {target_entry} not found in archive")
        return data

    @staticmethod
    def _natural_key(name: str):
        """Produces natural sorting keys ('page2' before 'page10')."""
        return [int(token) if token.isdigit() else token.lower() for token in re.split(r"(\d+)", name)]

    def _load_and_sort_pages(self):
        """Filters non-image entries and applies natural sorting."""
        valid_entries = []
        for entry in self._raw_entries:
            if entry.endswith("/"):
                continue
            if entry.startswith("__MACOSX/") or os.path.basename(entry).startswith("._"):
                continue
            base = os.path.basename(entry)
            if base.startswith(".") or base.lower() == "thumbs.db":
                continue
            ext = os.path.splitext(entry)[1].lower()
            if ext in self.SUPPORTED_EXTENSIONS:
                valid_entries.append(entry)

        self.pages = sorted(valid_entries, key=self._natural_key)

    def list_page_entries(self) -> List[str]:
        """Returns the naturally sorted list of image entry filenames."""
        return list(self.pages)

    def get_page_count(self) -> int:
        """Returns the total number of comic pages."""
        return len(self.pages)

    def get_spreads(self, mode: str = "single", direction: str = "ltr", **kwargs) -> List[List[int]]:
        """
        Calculates page spreads:
        - mode 'single': [[0], [1], [2], ...]
        - mode 'double': Cover isolated as [[0]], subsequent in pairs [[1, 2], [3, 4], ...]
        - direction 'rtl' (Manga): double pairs are inverted [[2, 1], [4, 3], ...] so earlier page is on right.
        - Odd trailing page is handled as single spread.
        """
        if "reading_direction" in kwargs and kwargs["reading_direction"]:
            direction = kwargs["reading_direction"]

        mode = mode.lower()
        direction = direction.lower()
        count = len(self.pages)

        if count == 0:
            return []

        if mode == "single":
            return [[i] for i in range(count)]

        if mode == "double":
            spreads: List[List[int]] = []
            # Cover (page 0) isolated as single spread
            spreads.append([0])

            idx = 1
            while idx < count:
                if idx + 1 < count:
                    pair = [idx, idx + 1]
                    if direction == "rtl":
                        pair = [pair[1], pair[0]]
                    spreads.append(pair)
                    idx += 2
                else:
                    # Trailing odd page as single spread
                    spreads.append([idx])
                    idx += 1
            return spreads

        raise ValueError(f"Unsupported spread mode: {mode}")

    def get_page_image_bytes(self, page_index: int) -> bytes:
        """Retrieves raw image bytes for the specified page index."""
        if page_index < 0 or page_index >= len(self.pages):
            raise IndexError(f"Page index {page_index} out of range (0..{len(self.pages) - 1})")

        if page_index in self._image_cache:
            return self._image_cache[page_index]

        entry = self.pages[page_index]
        if self.backend == "zip":
            if self._zip is None:
                self._zip = zipfile.ZipFile(self.file_path, "r")
            try:
                data = self._zip.read(entry)
            except Exception as e:
                raise CorruptComicError(f"Failed reading entry {entry}: {e}") from e
        elif self.backend == "libarchive":
            data = self._read_libarchive_entry(entry)
        else:
            raise CorruptComicError(f"Unsupported backend: {self.backend}")

        self._image_cache[page_index] = data
        return data

    @classmethod
    def _create_texture_from_bytes(cls, data: bytes):
        """Creates a Gdk.Texture from image bytes with resilient decode fallback."""
        try:
            import gi
            gi.require_version("Gdk", "4.0")
            from gi.repository import Gdk, GLib
        except (ImportError, ValueError):
            return None

        try:
            glib_bytes = GLib.Bytes.new(data)
            return Gdk.Texture.new_from_bytes(glib_bytes)
        except Exception:
            # Graceful fallback 1: Convert via PIL into standard PNG bytes
            try:
                from PIL import Image
                img = Image.open(io.BytesIO(data))
                out = io.BytesIO()
                img.save(out, format="PNG")
                glib_bytes = GLib.Bytes.new(out.getvalue())
                return Gdk.Texture.new_from_bytes(glib_bytes)
            except Exception:
                # Graceful fallback 2: Guaranteed decodable 1x1 placeholder texture
                glib_bytes = GLib.Bytes.new(cls._FALLBACK_PNG)
                return Gdk.Texture.new_from_bytes(glib_bytes)

    def get_page_texture(self, page_index: int):
        """Loads and returns the page as a Gdk.Texture with graceful fallback."""
        data = self.get_page_image_bytes(page_index)
        return self._create_texture_from_bytes(data)

    def close(self):
        """Releases open file handles and caches."""
        if getattr(self, "_zip", None) is not None:
            try:
                self._zip.close()
            except Exception:
                pass
            self._zip = None
        if hasattr(self, "_image_cache"):
            self._image_cache.clear()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def __del__(self):
        self.close()
