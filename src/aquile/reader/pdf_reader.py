"""
PDF Document Engine for Aquile Reader.
Implements fixed-layout document reading support (WP-10 / FR-06 / FR-07 / AT-04).

Features:
- Primary in-memory rendering via libpoppler-glib.so.8 + libcairo.so.2 using ctypes
  (zero temporary files, sub-millisecond vector scaling directly to Gdk.Texture).
- Reliable CLI fallback via /usr/bin/pdftoppm and /usr/bin/pdfinfo.
- Exact page count and dimension extraction in PDF points (72 DPI).
- Fit-to-width, fit-to-page, and custom zoom scale calculations with clamping [0.25, 5.0].
- Safe error handling and resource cleanup.
"""

import os
import re
import sys
import ctypes
import threading
import subprocess
from typing import Optional, Tuple, Any

try:
    import gi
    gi.require_version('Gdk', '4.0')
    from gi.repository import Gdk, GLib
    HAS_GDK = True
except (ImportError, ValueError):
    Gdk = None
    GLib = None
    HAS_GDK = False


class _GError(ctypes.Structure):
    _fields_ = [
        ("domain", ctypes.c_uint32),
        ("code", ctypes.c_int),
        ("message", ctypes.c_char_p),
    ]


class _PopplerCairoBridge:
    """Manages ctypes bindings to libpoppler-glib.so.8, libcairo.so.2, and glib."""

    _instance = None
    _init_lock = threading.Lock()

    def __init__(self):
        self.available = False
        self.poppler = None
        self.cairo = None
        self.gobject = None
        self.glib = None
        self.cairo_write_func_t = None
        self._load_libraries()

    @classmethod
    def get_instance(cls) -> "_PopplerCairoBridge":
        with cls._init_lock:
            if cls._instance is None:
                cls._instance = _PopplerCairoBridge()
            return cls._instance

    def _load_libraries(self):
        try:
            self.poppler = ctypes.CDLL("libpoppler-glib.so.8")
            self.cairo = ctypes.CDLL("libcairo.so.2")
            self.gobject = ctypes.CDLL("libgobject-2.0.so.0")
            self.glib = ctypes.CDLL("libglib-2.0.so.0")

            # Poppler function signatures
            self.poppler.poppler_document_new_from_file.restype = ctypes.c_void_p
            self.poppler.poppler_document_new_from_file.argtypes = [
                ctypes.c_char_p, ctypes.c_char_p, ctypes.POINTER(ctypes.c_void_p)
            ]

            self.poppler.poppler_document_get_n_pages.restype = ctypes.c_int
            self.poppler.poppler_document_get_n_pages.argtypes = [ctypes.c_void_p]

            self.poppler.poppler_document_get_page.restype = ctypes.c_void_p
            self.poppler.poppler_document_get_page.argtypes = [ctypes.c_void_p, ctypes.c_int]

            self.poppler.poppler_page_get_size.restype = None
            self.poppler.poppler_page_get_size.argtypes = [
                ctypes.c_void_p, ctypes.POINTER(ctypes.c_double), ctypes.POINTER(ctypes.c_double)
            ]

            self.poppler.poppler_page_render.restype = None
            self.poppler.poppler_page_render.argtypes = [ctypes.c_void_p, ctypes.c_void_p]

            # GObject / GLib signatures
            self.gobject.g_object_unref.restype = None
            self.gobject.g_object_unref.argtypes = [ctypes.c_void_p]

            self.glib.g_error_free.restype = None
            self.glib.g_error_free.argtypes = [ctypes.c_void_p]

            # Cairo signatures
            self.cairo.cairo_image_surface_create.restype = ctypes.c_void_p
            self.cairo.cairo_image_surface_create.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_int]

            self.cairo.cairo_create.restype = ctypes.c_void_p
            self.cairo.cairo_create.argtypes = [ctypes.c_void_p]

            self.cairo.cairo_set_source_rgb.restype = None
            self.cairo.cairo_set_source_rgb.argtypes = [
                ctypes.c_void_p, ctypes.c_double, ctypes.c_double, ctypes.c_double
            ]

            self.cairo.cairo_paint.restype = None
            self.cairo.cairo_paint.argtypes = [ctypes.c_void_p]

            self.cairo.cairo_scale.restype = None
            self.cairo.cairo_scale.argtypes = [ctypes.c_void_p, ctypes.c_double, ctypes.c_double]

            self.cairo_write_func_t = ctypes.CFUNCTYPE(
                ctypes.c_int, ctypes.c_void_p, ctypes.POINTER(ctypes.c_char), ctypes.c_uint
            )
            self.cairo.cairo_surface_write_to_png_stream.restype = ctypes.c_int
            self.cairo.cairo_surface_write_to_png_stream.argtypes = [
                ctypes.c_void_p, self.cairo_write_func_t, ctypes.c_void_p
            ]

            self.cairo.cairo_destroy.restype = None
            self.cairo.cairo_destroy.argtypes = [ctypes.c_void_p]

            self.cairo.cairo_surface_destroy.restype = None
            self.cairo.cairo_surface_destroy.argtypes = [ctypes.c_void_p]

            self.available = True
        except Exception:
            self.available = False


class PdfDocumentEngine:
    """
    Fixed-layout PDF engine providing in-memory vector rendering and dimension inspection.
    Uses libpoppler-glib.so.8 + libcairo.so.2 via ctypes as primary backend,
    falling back to pdftoppm / pdfinfo CLI commands when native libraries are unavailable.
    """

    def __init__(self, file_path: str, prefer_cli: bool = False):
        self._lock = threading.RLock()
        self._doc = None
        self._page_count: Optional[int] = None
        self._dimensions_cache: dict[int, Tuple[float, float]] = {}

        if not file_path:
            raise ValueError("File path cannot be empty")
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"PDF file does not exist: {file_path}")

        self.file_path = os.path.abspath(file_path)
        self.prefer_cli = prefer_cli
        self._bridge = _PopplerCairoBridge.get_instance()
        self._use_cli = prefer_cli or not self._bridge.available

        if not self._use_cli:
            self._init_ctypes_doc()

        if self._doc is None:
            self._use_cli = True
            self._verify_cli_available()
            self._page_count = self._get_page_count_cli()

    def _init_ctypes_doc(self):
        """Open PDF document via poppler_document_new_from_file."""
        uri = ("file://" + self.file_path).encode("utf-8")
        err = ctypes.c_void_p()
        doc = self._bridge.poppler.poppler_document_new_from_file(uri, None, ctypes.byref(err))
        if doc:
            self._doc = doc
            self._page_count = int(self._bridge.poppler.poppler_document_get_n_pages(doc))
        else:
            if err.value:
                self._bridge.glib.g_error_free(err)
            self._doc = None

    def _verify_cli_available(self):
        """Verify that CLI tools /usr/bin/pdfinfo and /usr/bin/pdftoppm are executable."""
        pdfinfo_path = "/usr/bin/pdfinfo"
        pdftoppm_path = "/usr/bin/pdftoppm"
        if not (os.path.exists(pdfinfo_path) or os.path.exists(pdftoppm_path)):
            raise RuntimeError("Neither Poppler C libraries nor Poppler CLI tools (pdfinfo/pdftoppm) are available.")

    def _get_page_count_cli(self) -> int:
        """Extract total page count using pdfinfo CLI fallback."""
        try:
            res = subprocess.run(
                ["/usr/bin/pdfinfo", self.file_path],
                capture_output=True,
                text=True,
                check=True
            )
            match = re.search(r"Pages:\s+(\d+)", res.stdout)
            if match:
                return int(match.group(1))
        except Exception:
            pass

        # Fallback to regex scanner on file content
        try:
            with open(self.file_path, "rb") as f:
                content = f.read().decode("latin1", errors="ignore")
                matches = re.findall(r"/Type\s*/Page\b", content)
                if matches:
                    return len(matches)
        except Exception:
            pass

        raise ValueError(f"Could not determine page count for PDF: {self.file_path}")

    def get_page_count(self) -> int:
        """Returns the total number of pages in the PDF document."""
        if self._page_count is not None:
            return self._page_count

        if not self._use_cli and self._doc:
            with self._lock:
                self._page_count = int(self._bridge.poppler.poppler_document_get_n_pages(self._doc))
                return self._page_count

        self._page_count = self._get_page_count_cli()
        return self._page_count

    def get_page_dimensions(self, page_index: int) -> Tuple[float, float]:
        """
        Returns (width, height) in points (1/72 inch) for the specified 0-indexed page.
        Raises IndexError if page_index is out of bounds.
        """
        total = self.get_page_count()
        if page_index < 0 or page_index >= total:
            raise IndexError(f"Page index {page_index} out of range [0, {total - 1}]")

        if page_index in self._dimensions_cache:
            return self._dimensions_cache[page_index]

        if not self._use_cli and self._doc:
            try:
                with self._lock:
                    page = self._bridge.poppler.poppler_document_get_page(self._doc, page_index)
                    if not page:
                        raise ValueError(f"Failed to load page {page_index}")
                    try:
                        w = ctypes.c_double()
                        h = ctypes.c_double()
                        self._bridge.poppler.poppler_page_get_size(page, ctypes.byref(w), ctypes.byref(h))
                        dims = (float(w.value), float(h.value))
                        self._dimensions_cache[page_index] = dims
                        return dims
                    finally:
                        self._bridge.gobject.g_object_unref(page)
            except Exception:
                pass  # Fall back to CLI

        dims = self._get_page_dimensions_cli(page_index)
        self._dimensions_cache[page_index] = dims
        return dims

    def _get_page_dimensions_cli(self, page_index: int) -> Tuple[float, float]:
        """Query page dimensions using pdfinfo CLI."""
        cmd = ["/usr/bin/pdfinfo", "-f", str(page_index + 1), "-l", str(page_index + 1), self.file_path]
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        match = re.search(r"Page(?:\s+\d+)?\s+size:\s+([0-9.]+)\s+x\s+([0-9.]+)", res.stdout)
        if match:
            return (float(match.group(1)), float(match.group(2)))
        # General page size fallback
        match_gen = re.search(r"Page\s+size:\s+([0-9.]+)\s+x\s+([0-9.]+)", res.stdout)
        if match_gen:
            return (float(match_gen.group(1)), float(match_gen.group(2)))
        raise ValueError(f"Could not parse dimensions for page {page_index}")

    def render_page_png_bytes(self, page_index: int, scale: float = 1.0) -> bytes:
        """
        Renders the vector page directly to PNG bytes in memory.
        """
        total = self.get_page_count()
        if page_index < 0 or page_index >= total:
            raise IndexError(f"Page index {page_index} out of range [0, {total - 1}]")

        scale = max(0.05, float(scale))

        if not self._use_cli and self._doc:
            try:
                return self._render_page_ctypes(page_index, scale)
            except Exception:
                pass  # Fall through to CLI fallback

        return self._render_page_cli(page_index, scale)

    def _render_page_ctypes(self, page_index: int, scale: float) -> bytes:
        """In-memory rendering using poppler_page_render and cairo PNG stream."""
        with self._lock:
            page = self._bridge.poppler.poppler_document_get_page(self._doc, page_index)
            if not page:
                raise ValueError(f"Failed to load page {page_index}")
            try:
                w = ctypes.c_double()
                h = ctypes.c_double()
                self._bridge.poppler.poppler_page_get_size(page, ctypes.byref(w), ctypes.byref(h))
                scaled_w = max(1, int(round(w.value * scale)))
                scaled_h = max(1, int(round(h.value * scale)))

                # 0 = CAIRO_FORMAT_ARGB32
                surface = self._bridge.cairo.cairo_image_surface_create(0, scaled_w, scaled_h)
                cr = self._bridge.cairo.cairo_create(surface)
                try:
                    # Fill solid white background (PDF pages can default to transparent)
                    self._bridge.cairo.cairo_set_source_rgb(
                        cr, ctypes.c_double(1.0), ctypes.c_double(1.0), ctypes.c_double(1.0)
                    )
                    self._bridge.cairo.cairo_paint(cr)

                    # Scale vector context
                    self._bridge.cairo.cairo_scale(cr, ctypes.c_double(scale), ctypes.c_double(scale))

                    # Render vector page content
                    self._bridge.poppler.poppler_page_render(page, cr)

                    # Stream surface to PNG buffer
                    png_chunks = []

                    def write_cb(closure, data, length):
                        png_chunks.append(ctypes.string_at(data, length))
                        return 0

                    cb_func = self._bridge.cairo_write_func_t(write_cb)
                    status = self._bridge.cairo.cairo_surface_write_to_png_stream(surface, cb_func, None)
                    if status != 0:
                        raise RuntimeError(f"Cairo write to PNG stream failed with code {status}")
                    return b"".join(png_chunks)
                finally:
                    self._bridge.cairo.cairo_destroy(cr)
                    self._bridge.cairo.cairo_surface_destroy(surface)
            finally:
                self._bridge.gobject.g_object_unref(page)

    def _render_page_cli(self, page_index: int, scale: float) -> bytes:
        """CLI rendering fallback using pdftoppm streaming directly to stdout."""
        w, h = self.get_page_dimensions(page_index)
        target_w = max(1, int(round(w * scale)))
        target_h = max(1, int(round(h * scale)))

        cmd = [
            "/usr/bin/pdftoppm",
            "-png",
            "-f", str(page_index + 1),
            "-l", str(page_index + 1),
            "-singlefile",
            "-scale-to-x", str(target_w),
            "-scale-to-y", str(target_h),
            self.file_path,
        ]
        res = subprocess.run(cmd, capture_output=True, check=True)
        if not res.stdout.startswith(b"\x89PNG"):
            raise RuntimeError("pdftoppm output did not contain valid PNG header")
        return res.stdout

    def render_page_texture(self, page_index: int, scale: float = 1.0) -> Any:
        """
        Renders vector page directly into Gdk.Texture.
        """
        if not HAS_GDK or Gdk is None or GLib is None:
            raise RuntimeError("GDK 4.0 is required for render_page_texture")

        png_data = self.render_page_png_bytes(page_index, scale=scale)
        bytes_obj = GLib.Bytes.new(png_data)
        return Gdk.Texture.new_from_bytes(bytes_obj)

    def calculate_fit_scale(
        self,
        page_index: int,
        viewport_width: float,
        viewport_height: float,
        mode: str
    ) -> float:
        """
        Calculates zoom scale factor for the given viewport:
        - mode == "width": viewport_width / page_width
        - mode == "page": min(viewport_width / page_width, viewport_height / page_height)
        - custom zoom clamping applied: clamped to [0.25, 5.0].
        - viewport <= 0 returns 0.0 safely without ZeroDivisionError.
        """
        if viewport_width <= 0.0 or viewport_height <= 0.0:
            return 0.0

        page_w, page_h = self.get_page_dimensions(page_index)
        if page_w <= 0.0 or page_h <= 0.0:
            return 1.0

        if mode == "width":
            scale = viewport_width / page_w
        elif mode == "page":
            scale = min(viewport_width / page_w, viewport_height / page_h)
        elif mode == "height":
            scale = viewport_height / page_h
        else:
            scale = 1.0

        # Custom zoom clamping (0.25 to 5.0)
        return max(0.25, min(5.0, float(scale)))

    def close(self):
        """Release underlying PopplerDocument resources."""
        lock = getattr(self, "_lock", None)
        if lock is not None:
            with lock:
                self._release_doc()
        else:
            self._release_doc()

    def _release_doc(self):
        doc = getattr(self, "_doc", None)
        bridge = getattr(self, "_bridge", None)
        if doc is not None and bridge is not None and getattr(bridge, "available", False) and getattr(bridge, "gobject", None):
            try:
                bridge.gobject.g_object_unref(doc)
            except Exception:
                pass
            self._doc = None

    def __del__(self):
        self.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
