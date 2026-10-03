"""Book cover storage: XDG-based cover cache for library/Home grids.

Covers are extracted from EPUB files at import time and stored under
``$XDG_DATA_HOME/aquile-reader/covers/<book_id>.<ext>``. Files are keyed by
stable book id and validated (image magic + size cap) before writing.
"""

import os
from typing import Optional

COVER_SIZE_LIMIT = 5 * 1024 * 1024  # 5 MiB

_MIME_EXT = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}

_MAGIC = {
    b"\xff\xd8\xff": ".jpg",
    b"\x89PNG\r\n\x1a\n": ".png",
    b"RIFF": None,  # webp needs further check
    b"GIF87a": ".gif",
    b"GIF89a": ".gif",
}


def get_covers_dir() -> str:
    """Return (creating) the user covers directory."""
    xdg = os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share"))
    path = os.path.join(xdg, "aquile-reader", "covers")
    os.makedirs(path, exist_ok=True)
    return path


def _sniff_extension(data: bytes, mime: str) -> Optional[str]:
    for magic, ext in _MAGIC.items():
        if data.startswith(magic):
            if magic == b"RIFF" and data[8:12] == b"WEBP":
                return ".webp"
            if ext is not None:
                return ext
    return _MIME_EXT.get(mime)


def save_cover(book_id: str, data: bytes, mime: str = "") -> Optional[str]:
    """Validate and persist cover bytes. Returns the path, or None."""
    if not book_id or not data:
        return None
    if len(data) > COVER_SIZE_LIMIT:
        return None
    ext = _sniff_extension(data[:16], mime or "")
    if ext is None:
        return None
    safe_id = "".join(c for c in str(book_id) if c.isalnum() or c in ("-", "_")) or "cover"
    path = os.path.join(get_covers_dir(), safe_id + ext)
    try:
        with open(path, "wb") as fh:
            fh.write(data)
    except OSError:
        return None
    return path


def clean_display_title(filename: str) -> str:
    """Turn a file stem like 'machiavelli-niccolo-the-prince-1985' into a title."""
    stem = os.path.splitext(os.path.basename(filename))[0]
    stem = stem.replace("_", " ").replace("-", " ").replace(".", " ")
    stem = " ".join(stem.split())
    if stem and stem == stem.lower():
        stem = stem.title()
    return stem or "Untitled"
