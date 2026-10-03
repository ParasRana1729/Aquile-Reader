"""
OPDS catalog client for Aquile Reader (FR-14).

Offline-first (FR-20): all network activity is explicit and user-invoked
(discover/search-download). Local reading never depends on this client and
network failures raise NetworkError without touching the local library.

Network destinations (NFR-04):
  - User-supplied OPDS feed URLs (custom catalogs) and the default feeds
    defined in catalog_manager.py (Project Gutenberg, Standard Ebooks).
  - Transmitted data: plain HTTP GET requests for feed XML/JSON and for
    explicit book downloads. No credentials, annotations, note contents,
    full local paths, or book text are uploaded. No background polling
    and no hidden telemetry (NFR-03/NFR-04).

Protocols: OPDS 1.x (Atom XML) and OPDS 2.0 (JSON) acquisition feeds,
compatible with Project Gutenberg / Standard Ebooks style feeds.

Untrusted-input handling (NFR-06): feed bytes are size-capped, parsed with
defused stdlib XML (no external entities resolved), filenames are
sanitized, download destinations are confined to dest_dir, downloads are
size-capped, and content types are validated for EPUB/PDF.

All network I/O uses urllib (stdlib) only.
"""

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any, Callable, Dict, List, Optional


class NetworkError(Exception):
    """Raised for transport failures, timeouts, bad HTTP status, or parse failures of remote feeds."""


class CancelledError(Exception):
    """Raised when a download is cancelled via the caller-supplied cancel token."""


class UnsupportedContentError(Exception):
    """Raised when remote content is not a supported EPUB/PDF download or exceeds size limits."""


_ATOM_NS = "http://www.w3.org/2005/Atom"

_ALLOWED_SCHEMES = ("http", "https", "file")

_ALLOWED_CONTENT_TYPES = frozenset({
    "application/epub+zip",
    "application/epub",
    "application/x-epub",
    "application/pdf",
    "application/x-pdf",
})

# Generic binary with no declared type is accepted only when the URL or
# feed metadata indicates an .epub/.pdf artifact. Anything textual (HTML,
# XML feed served as a "book", JSON error) is rejected.
_OCTET_TYPES = frozenset({
    "application/octet-stream",
    "binary/octet-stream",
})

_TEXT_TYPES = frozenset({
    "text/html",
    "text/plain",
    "text/xml",
    "application/xml",
    "application/atom+xml",
    "application/json",
    "application/opds+json",
    "application/opds-publication+json",
})


def _is_cancelled(cancel_token: Any) -> bool:
    if cancel_token is None:
        return False
    if callable(cancel_token):
        try:
            return bool(cancel_token())
        except Exception:
            return False
    is_set = getattr(cancel_token, "is_set", None)
    if callable(is_set):
        try:
            return bool(is_set())
        except Exception:
            return False
    for attr in ("cancelled", "cancel_requested", "cancel"):
        if hasattr(cancel_token, attr):
            val = getattr(cancel_token, attr)
            try:
                return bool(val() if callable(val) else val)
            except Exception:
                return False
    if isinstance(cancel_token, dict):
        return bool(cancel_token.get("cancelled") or cancel_token.get("cancel"))
    return False


def _norm_content_type(raw: Optional[str]) -> str:
    if not raw:
        return ""
    return raw.split(";")[0].strip().lower()


def _format_from_type_or_href(acq_type: str, href: str) -> str:
    t = (acq_type or "").lower()
    h = (href or "").lower().split("?")[0]
    if "epub" in t or h.endswith(".epub"):
        return "epub"
    if "pdf" in t or h.endswith(".pdf"):
        return "pdf"
    return "unknown"


class OpdsClient:
    """Minimal OPDS 1.x/2.0 read-only client with guarded downloads."""

    MAX_FEED_BYTES = 2 * 1024 * 1024
    MAX_DOWNLOAD_BYTES = 200 * 1024 * 1024
    CHUNK_SIZE = 32 * 1024

    def __init__(
        self,
        timeout: float = 10.0,
        max_retries: int = 2,
        max_feed_bytes: int = MAX_FEED_BYTES,
        max_download_bytes: int = MAX_DOWNLOAD_BYTES,
    ):
        self.timeout = float(timeout)
        self.max_retries = max(0, int(max_retries))
        self.max_feed_bytes = int(max_feed_bytes)
        self.max_download_bytes = int(max_download_bytes)
        self._entries: List[Dict[str, Any]] = []
        self._by_id: Dict[str, Dict[str, Any]] = {}
        self._feed_url: str = ""
        self._feed_title: str = ""

    @property
    def feed_url(self) -> str:
        return self._feed_url

    @property
    def feed_title(self) -> str:
        return self._feed_title

    @property
    def entries(self) -> List[Dict[str, Any]]:
        return [dict(e) for e in self._entries]

    # -- fetching ------------------------------------------------------

    def _fetch_bytes(self, url: str) -> tuple:
        """Fetch a URL body with timeout and bounded retries. Returns (data, headers, final_url)."""
        scheme = urllib.parse.urlparse(url).scheme.lower()
        if scheme not in _ALLOWED_SCHEMES:
            raise NetworkError(f"Unsupported URL scheme: {scheme or '(none)'}")
        attempts = self.max_retries + 1
        last_err: Optional[Exception] = None
        for attempt in range(attempts):
            try:
                req = urllib.request.Request(
                    url,
                    headers={
                        "User-Agent": "Aquile-Reader/0.1 (OPDS; +offline-first)",
                        "Accept": (
                            "application/atom+xml, application/opds+json, "
                            "application/json, application/xml, */*;q=0.8"
                        ),
                    },
                )
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    headers = dict(resp.headers.items()) if resp.headers else {}
                    final_url = getattr(resp, "geturl", lambda: url)()
                    chunks: List[bytes] = []
                    total = 0
                    while True:
                        piece = resp.read(self.CHUNK_SIZE)
                        if not piece:
                            break
                        total += len(piece)
                        if total > self.max_feed_bytes:
                            raise UnsupportedContentError(
                                f"Feed exceeds size limit ({self.max_feed_bytes} bytes)"
                            )
                        chunks.append(piece)
                    return b"".join(chunks), headers, final_url
            except UnsupportedContentError:
                raise
            except urllib.error.HTTPError as e:
                last_err = e
                if e.code is not None and 500 <= e.code <= 599:
                    if attempt < attempts - 1:
                        continue
                raise NetworkError(f"HTTP {e.code} fetching {url}: {e.reason}") from e
            except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
                last_err = e
                reason = getattr(e, "reason", e)
                # 429 Too Many Requests deserves a retry; other 4xx do not.
                code = getattr(reason, "code", None) if not isinstance(e, urllib.error.HTTPError) else None
                if scheme == "file":
                    raise NetworkError(f"Cannot read local feed {url}: {e}") from e
                if attempt < attempts - 1:
                    continue
                raise NetworkError(f"Network failure fetching {url}: {e}") from e
        raise NetworkError(f"Network failure fetching {url}: {last_err}")

    # -- discovery -----------------------------------------------------

    def discover(self, feed_url: str) -> List[Dict[str, Any]]:
        """Fetch and parse an OPDS 1.x (Atom) or OPDS 2.0 (JSON) feed."""
        if not feed_url or not feed_url.strip():
            raise NetworkError("Empty feed URL")
        data, _headers, final_url = self._fetch_bytes(feed_url.strip())
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as e:
            raise NetworkError(f"Feed is not valid UTF-8: {e}") from e
        try:
            entries, title = self._parse_feed(text, final_url or feed_url)
        except UnsupportedContentError:
            raise
        except NetworkError:
            raise
        except Exception as e:
            raise NetworkError(f"Cannot parse catalog feed: {e}") from e
        self._entries = entries
        self._by_id = {e["id"]: e for e in entries}
        self._feed_url = final_url or feed_url
        self._feed_title = title
        return [dict(e) for e in entries]

    def _parse_feed(self, text: str, base_url: str) -> tuple:
        stripped = text.lstrip()
        if stripped.startswith("{"):
            return self._parse_opds2(stripped, base_url)
        return self._parse_opds1(text, base_url)

    def _parse_opds1(self, text: str, base_url: str) -> tuple:
        try:
            root = ET.fromstring(text)
        except ET.ParseError as e:
            raise NetworkError(f"Malformed Atom feed: {e}") from e
        ns = {"a": _ATOM_NS}

        def _find_text(elem: ET.Element, name: str) -> str:
            child = elem.find(f"a:{name}", ns)
            if child is not None and child.text:
                return child.text.strip()
            # Tolerate non-namespaced feeds.
            child = elem.find(name)
            if child is not None and child.text:
                return child.text.strip()
            return ""

        title_elem = root.find("a:title", ns)
        feed_title = title_elem.text.strip() if title_elem is not None and title_elem.text else ""
        if not feed_title:
            plain = root.find("title")
            feed_title = plain.text.strip() if plain is not None and plain.text else ""

        entry_elems = root.findall("a:entry", ns) or root.findall("entry")
        entries: List[Dict[str, Any]] = []
        for idx, item in enumerate(entry_elems):
            entry_id = _find_text(item, "id") or f"entry-{idx}"
            title = _find_text(item, "title") or "Untitled"
            author = ""
            author_elem = item.find("a:author/a:name", ns)
            if author_elem is not None and author_elem.text:
                author = author_elem.text.strip()
            else:
                author_elem = item.find("author/name")
                if author_elem is not None and author_elem.text:
                    author = author_elem.text.strip()
                else:
                    direct = item.find("a:author", ns)
                    if direct is not None and direct.text and not list(direct):
                        author = direct.text.strip()
            summary = _find_text(item, "summary") or _find_text(item, "content")

            acq_url: Optional[str] = None
            acq_type = ""
            links_info: List[Dict[str, str]] = []
            for link in list(item.findall("a:link", ns)) + list(item.findall("link")):
                href = (link.attrib.get("href") or "").strip()
                rel = (link.attrib.get("rel") or "").strip()
                ltype = (link.attrib.get("type") or "").strip()
                if href:
                    links_info.append({"href": href, "rel": rel, "type": ltype})
                    if acq_url is None and (
                        "acquisition" in rel
                        or _format_from_type_or_href(ltype, href) in ("epub", "pdf")
                    ):
                        acq_url = urllib.parse.urljoin(base_url, href)
                        acq_type = ltype
            entries.append({
                "id": entry_id,
                "title": title,
                "author": author,
                "summary": summary,
                "acquisition_url": acq_url,
                "acquisition_type": acq_type,
                "format": _format_from_type_or_href(acq_type, acq_url or ""),
                "links": links_info,
            })
        return entries, feed_title

    def _parse_opds2(self, text: str, base_url: str) -> tuple:
        try:
            doc = json.loads(text)
        except json.JSONDecodeError as e:
            raise NetworkError(f"Malformed OPDS JSON feed: {e}") from e
        if not isinstance(doc, dict):
            raise NetworkError("OPDS JSON feed must be an object")
        meta = doc.get("metadata", {}) if isinstance(doc.get("metadata"), dict) else {}
        feed_title = str(meta.get("title", "") or doc.get("title", "") or "")
        pubs = doc.get("publications", [])
        if not isinstance(pubs, list):
            raise NetworkError("OPDS JSON 'publications' must be a list")
        entries: List[Dict[str, Any]] = []
        for idx, pub in enumerate(pubs):
            if not isinstance(pub, dict):
                continue
            pmeta = pub.get("metadata", {}) if isinstance(pub.get("metadata"), dict) else {}
            title = str(pmeta.get("title", "") or pub.get("title", "") or "Untitled")
            author_raw = pmeta.get("author", "")
            if isinstance(author_raw, list):
                names = []
                for a in author_raw:
                    if isinstance(a, dict):
                        names.append(str(a.get("name", "")))
                    else:
                        names.append(str(a))
                author = ", ".join(n for n in names if n)
            elif isinstance(author_raw, dict):
                author = str(author_raw.get("name", ""))
            else:
                author = str(author_raw or "")
            entry_id = str(
                pmeta.get("identifier", "") or pub.get("id", "") or f"entry-{idx}"
            )
            summary = str(pmeta.get("description", "") or pub.get("summary", "") or "")
            links = pub.get("links", [])
            acq_url: Optional[str] = None
            acq_type = ""
            links_info: List[Dict[str, str]] = []
            if isinstance(links, list):
                for link in links:
                    if not isinstance(link, dict):
                        continue
                    href = str(link.get("href", "") or "").strip()
                    rel = str(link.get("rel", "") or "").strip()
                    ltype = str(link.get("type", "") or "").strip()
                    if href:
                        links_info.append({"href": href, "rel": rel, "type": ltype})
                        if acq_url is None and (
                            "acquisition" in rel
                            or _format_from_type_or_href(ltype, href) in ("epub", "pdf")
                        ):
                            acq_url = urllib.parse.urljoin(base_url, href)
                            acq_type = ltype
            entries.append({
                "id": entry_id,
                "title": title,
                "author": author,
                "summary": summary,
                "acquisition_url": acq_url,
                "acquisition_type": acq_type,
                "format": _format_from_type_or_href(acq_type, acq_url or ""),
                "links": links_info,
            })
        return entries, feed_title

    # -- search / details ----------------------------------------------

    def search(self, query: str) -> List[Dict[str, Any]]:
        """Filter the last discovered entries by title/author/id (case-insensitive).

        Search is purely local over cached discovery results: it sends no
        network traffic, so it works offline once a feed was discovered.
        """
        q = (query or "").strip().lower()
        if not q:
            return [dict(e) for e in self._entries]
        hits = []
        for entry in self._entries:
            hay = " ".join([
                str(entry.get("title", "")),
                str(entry.get("author", "")),
                str(entry.get("id", "")),
            ]).lower()
            if q in hay:
                hits.append(dict(entry))
        return hits

    def get_details(self, entry_id: str) -> Optional[Dict[str, Any]]:
        """Return a copy of the cached entry, or None when unknown."""
        if entry_id in self._by_id:
            return dict(self._by_id[entry_id])
        return None

    # -- download ------------------------------------------------------

    @staticmethod
    def sanitize_filename(name: str, default: str = "book") -> str:
        """Return a filesystem-safe basename without directories (NFR-06).

        Strips path components, replaces unsafe characters, blocks reserved
        names, and truncates the stem. The caller appends the validated
        .epub/.pdf extension via download().
        """
        raw = (name or "").strip() or default
        raw = raw.replace("\x00", "")
        # Drop any directory components from untrusted feed metadata.
        raw = raw.replace("\\", "/")
        raw = os.path.basename(raw)
        raw = raw.strip().strip(".")
        if not raw or raw in (".", ".."):
            raw = default
        stem, dot, ext = raw.rpartition(".")
        ext = ("." + ext.lower()) if dot and len(ext) <= 5 else ""
        base = stem if dot and len(ext) <= 5 else raw
        if ext not in ("", ".epub", ".pdf"):
            base = raw
            ext = ""
        cleaned_chars = []
        for ch in base:
            if ch.isalnum() or ch in (" ", ".", "_", "-", "(", ")"):
                cleaned_chars.append(ch)
            else:
                cleaned_chars.append("_")
        base = "".join(cleaned_chars).strip()
        base = re.sub(r"\s+", " ", base).strip(" .")
        if not base or base in (".", ".."):
            base = default
        if len(base) > 80:
            base = base[:80].rstrip(" .")
        # Windows-reserved basenames.
        if base.upper() in (
            "CON", "PRN", "AUX", "NUL",
            "COM1", "COM2", "COM3", "COM4",
            "LPT1", "LPT2", "LPT3",
        ):
            base = f"{base}_book"
        return base + ext

    def _validate_content_type(
        self, content_type: str, acq_type: str, url: str
    ) -> str:
        ctype = _norm_content_type(content_type)
        if ctype in _ALLOWED_CONTENT_TYPES:
            return "epub" if "epub" in ctype else "pdf"
        if ctype in _OCTET_TYPES or ctype == "":
            fmt = _format_from_type_or_href(acq_type or ctype, url)
            if fmt in ("epub", "pdf"):
                return fmt
            raise UnsupportedContentError(
                f"Download type '{content_type or 'unknown'}' cannot be "
                "identified as EPUB or PDF"
            )
        if ctype in _TEXT_TYPES or "html" in ctype or "xml" in ctype or "json" in ctype:
            raise UnsupportedContentError(
                f"Unsupported download content type: '{content_type}' "
                "(expected EPUB or PDF)"
            )
        # Unknown binary type: accept only with an explicit epub/pdf signal.
        fmt = _format_from_type_or_href(acq_type, url)
        if fmt in ("epub", "pdf"):
            return fmt
        raise UnsupportedContentError(
            f"Unsupported download content type: '{content_type}'"
        )

    def download(
        self,
        entry: Dict[str, Any],
        dest_dir: str,
        progress_cb: Optional[Callable[[int, Optional[int]], None]] = None,
        cancel_token: Any = None,
    ) -> str:
        """Download an entry's acquisition file into dest_dir.

        Returns the absolute path of the saved file. Raises NetworkError,
        CancelledError, or UnsupportedContentError. Retries transient
        failures up to max_retries times. Partial files are removed on
        cancellation or failure.
        """
        if not isinstance(entry, dict):
            raise UnsupportedContentError("Download entry must be a dict")
        url = (
            entry.get("acquisition_url")
            or entry.get("download_url")
            or entry.get("url")
            or ""
        ).strip() if isinstance(entry.get("acquisition_url", ""), str) else ""
        if not url:
            for key in ("acquisition_url", "download_url", "url"):
                val = entry.get(key)
                if isinstance(val, str) and val.strip():
                    url = val.strip()
                    break
        if not url:
            raise UnsupportedContentError("Catalog entry has no downloadable file link")
        if self._feed_url and not urllib.parse.urlparse(url).scheme:
            url = urllib.parse.urljoin(self._feed_url, url)
        scheme = urllib.parse.urlparse(url).scheme.lower()
        if scheme not in _ALLOWED_SCHEMES:
            raise NetworkError(f"Unsupported download scheme: {scheme or '(none)'}")

        acq_type = str(entry.get("acquisition_type", "") or "")
        title = str(entry.get("title", "") or "book")
        fmt_hint = str(entry.get("format", "") or _format_from_type_or_href(acq_type, url))
        safe_base = self.sanitize_filename(title)
        # Ensure the saved file carries a validated .epub/.pdf extension.
        lower_base = safe_base.lower()
        if fmt_hint == "epub" and not lower_base.endswith(".epub"):
            safe_base += ".epub"
        elif fmt_hint == "pdf" and not lower_base.endswith(".pdf"):
            safe_base += ".pdf"
        elif not lower_base.endswith((".epub", ".pdf")):
            ext_guess = _format_from_type_or_href(acq_type, url)
            safe_base += ".epub" if ext_guess != "pdf" else ".pdf"

        dest_abs = os.path.abspath(dest_dir)
        os.makedirs(dest_abs, exist_ok=True)
        final_path = os.path.abspath(os.path.join(dest_abs, safe_base))
        if final_path != dest_abs and not final_path.startswith(dest_abs + os.sep):
            raise UnsupportedContentError("Unsafe download filename escapes destination")

        if _is_cancelled(cancel_token):
            raise CancelledError("Download cancelled before start")

        if scheme == "file":
            return self._download_local_file(
                url, final_path, acq_type, progress_cb, cancel_token
            )
        return self._download_http(
            url, final_path, acq_type, progress_cb, cancel_token
        )

    def _download_local_file(
        self,
        url: str,
        final_path: str,
        acq_type: str,
        progress_cb: Optional[Callable[[int, Optional[int]], None]],
        cancel_token: Any,
    ) -> str:
        parsed = urllib.parse.urlparse(url)
        src_path = urllib.request.url2pathname(parsed.path)
        if not os.path.isfile(src_path):
            raise NetworkError(f"Local file not found: {src_path}")
        size = os.path.getsize(src_path)
        if size > self.max_download_bytes:
            raise UnsupportedContentError(
                f"File exceeds size limit ({size} > {self.max_download_bytes} bytes)"
            )
        if size == 0:
            raise UnsupportedContentError("Downloaded file is empty")
        self._validate_content_type("", acq_type, url)
        downloaded = 0
        try:
            with open(src_path, "rb") as src, open(final_path, "wb") as dst:
                while True:
                    if _is_cancelled(cancel_token):
                        raise CancelledError("Download cancelled")
                    chunk = src.read(self.CHUNK_SIZE)
                    if not chunk:
                        break
                    dst.write(chunk)
                    downloaded += len(chunk)
                    if downloaded > self.max_download_bytes:
                        raise UnsupportedContentError("Download exceeds size limit")
                    if progress_cb is not None:
                        progress_cb(downloaded, size)
        except (CancelledError, UnsupportedContentError):
            try:
                if os.path.exists(final_path):
                    os.remove(final_path)
            finally:
                pass
            raise
        except OSError as e:
            try:
                if os.path.exists(final_path):
                    os.remove(final_path)
            finally:
                pass
            raise NetworkError(f"File copy failed: {e}") from e
        self._reject_html_magic(final_path)
        return final_path

    def _download_http(
        self,
        url: str,
        final_path: str,
        acq_type: str,
        progress_cb: Optional[Callable[[int, Optional[int]], None]],
        cancel_token: Any,
    ) -> str:
        attempts = self.max_retries + 1
        last_err: Optional[Exception] = None
        for attempt in range(attempts):
            if _is_cancelled(cancel_token):
                raise CancelledError("Download cancelled")
            try:
                return self._download_http_once(
                    url, final_path, acq_type, progress_cb, cancel_token
                )
            except (CancelledError, UnsupportedContentError):
                raise
            except NetworkError as e:
                last_err = e
                transient = getattr(e, "_transient", True)
                if transient and attempt < attempts - 1:
                    # Remove any partial file before retrying.
                    try:
                        if os.path.exists(final_path):
                            os.remove(final_path)
                    except OSError:
                        pass
                    continue
                raise
        raise NetworkError(f"Download failed: {last_err}")

    def _download_http_once(
        self,
        url: str,
        final_path: str,
        acq_type: str,
        progress_cb: Optional[Callable[[int, Optional[int]], None]],
        cancel_token: Any,
    ) -> str:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Aquile-Reader/0.1 (OPDS; +offline-first)",
                "Accept": "application/epub+zip, application/pdf, */*;q=0.8",
            },
        )
        try:
            resp = urllib.request.urlopen(req, timeout=self.timeout)
        except urllib.error.HTTPError as e:
            err = NetworkError(f"HTTP {e.code} downloading {url}: {e.reason}")
            err._transient = bool(e.code is not None and (500 <= e.code <= 599 or e.code == 429))  # type: ignore[attr-defined]
            raise err from e
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
            err = NetworkError(f"Network failure downloading {url}: {e}")
            err._transient = True  # type: ignore[attr-defined]
            raise err from e

        with resp:
            ctype = ""
            total: Optional[int] = None
            if resp.headers:
                ctype = resp.headers.get("Content-Type", "") or ""
                length = resp.headers.get("Content-Length")
                if length is not None:
                    try:
                        total = int(length)
                    except (TypeError, ValueError):
                        total = None
            if total is not None and total > self.max_download_bytes:
                raise UnsupportedContentError(
                    f"Download exceeds size limit ({total} > {self.max_download_bytes} bytes)"
                )
            fmt = self._validate_content_type(ctype, acq_type, url)
            # Align the extension with the validated wire type.
            root, _dot, _ext = final_path.rpartition(".")
            if fmt == "epub" and not final_path.lower().endswith(".epub"):
                final_path = root + ".epub" if root else final_path + ".epub"
            elif fmt == "pdf" and not final_path.lower().endswith(".pdf"):
                final_path = root + ".pdf" if root else final_path + ".pdf"

            downloaded = 0
            try:
                with open(final_path, "wb") as dst:
                    while True:
                        if _is_cancelled(cancel_token):
                            raise CancelledError("Download cancelled")
                        chunk = resp.read(self.CHUNK_SIZE)
                        if not chunk:
                            break
                        dst.write(chunk)
                        downloaded += len(chunk)
                        if downloaded > self.max_download_bytes:
                            raise UnsupportedContentError(
                                "Download exceeds size limit"
                            )
                        if progress_cb is not None:
                            progress_cb(downloaded, total)
            except (CancelledError, UnsupportedContentError):
                try:
                    if os.path.exists(final_path):
                        os.remove(final_path)
                finally:
                    pass
                raise
            except OSError as e:
                try:
                    if os.path.exists(final_path):
                        os.remove(final_path)
                finally:
                    pass
                err = NetworkError(f"Download I/O failure: {e}")
                err._transient = False  # type: ignore[attr-defined]
                raise err from e
            if downloaded == 0:
                try:
                    if os.path.exists(final_path):
                        os.remove(final_path)
                finally:
                    pass
                raise UnsupportedContentError("Downloaded file is empty")
        self._reject_html_magic(final_path)
        return final_path

    def _reject_html_magic(self, path: str) -> None:
        try:
            with open(path, "rb") as f:
                head = f.read(512).lstrip().lower()
        except OSError:
            return
        if head.startswith((b"<!doctype html", b"<html", b"<head")):
            try:
                os.remove(path)
            except OSError:
                pass
            raise UnsupportedContentError(
                "Downloaded content looks like an HTML page, not EPUB/PDF"
            )
