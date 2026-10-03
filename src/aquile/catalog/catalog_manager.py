"""
Custom catalog registry for Aquile Reader (FR-14).

Offline-first (FR-20): this registry is local-only state. Adding,
removing, or listing feeds never performs network I/O; fetching happens
only when the user explicitly opens/searches/downloads via OpdsClient.

Network destinations (NFR-04): the default feeds below plus any
user-added OPDS http(s) URLs. No telemetry is sent (NFR-03); the stored
record contains only the feed id, display name, and URL.

Persistence: CatalogManager accepts an injectable dict-like store
(SettingsRepository-compatible dict interface). Production wiring may
persist store["catalog_feeds"]; tests inject a plain dict.
"""

import re
import urllib.parse
from typing import Any, Dict, List, Optional

# Default open-protocol catalogs (OPDS). Documented network destinations.
GUTENBERG_OPDS_URL = "https://www.gutenberg.org/ebooks.opds/"
STANDARDEBOOKS_OPDS_URL = "https://standardebooks.org/opds"

DEFAULT_FEEDS: List[Dict[str, str]] = [
    {
        "id": "gutenberg",
        "name": "Project Gutenberg",
        "url": GUTENBERG_OPDS_URL,
    },
    {
        "id": "standardebooks",
        "name": "Standard Ebooks",
        "url": STANDARDEBOOKS_OPDS_URL,
    },
]

STORE_KEY = "catalog_feeds"


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return slug or "catalog"


class CatalogManager:
    """Manages default + user-added OPDS catalog feeds with local persistence."""

    def __init__(self, store: Optional[Any] = None):
        self._store: Any = store if store is not None else {}

    # -- persistence helpers -------------------------------------------

    def _load_custom(self) -> List[Dict[str, str]]:
        store = self._store
        raw: Any = []
        try:
            if hasattr(store, "get") and callable(getattr(store, "get")):
                raw = store.get(STORE_KEY, [])
            elif hasattr(store, "__getitem__"):
                raw = store[STORE_KEY]
        except (KeyError, AttributeError, TypeError):
            raw = []
        if not isinstance(raw, list):
            return []
        cleaned: List[Dict[str, str]] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            url = str(item.get("url", "") or "").strip()
            if not url:
                continue
            cleaned.append({
                "id": str(item.get("id", "") or _slugify(url)),
                "name": str(item.get("name", "") or url),
                "url": url,
            })
        return cleaned

    def _save_custom(self, feeds: List[Dict[str, str]]) -> None:
        store = self._store
        payload = [dict(f) for f in feeds]
        try:
            if hasattr(store, "__setitem__"):
                store[STORE_KEY] = payload
                return
            setter = getattr(store, "set", None)
            if callable(setter):
                setter(STORE_KEY, payload)
                return
        except (TypeError, AttributeError):
            pass
        # Non-persistable store: keep a local fallback copy.
        self._fallback = payload

    # -- public API -----------------------------------------------------

    def list_custom(self) -> List[Dict[str, str]]:
        if hasattr(self, "_fallback") and not self._persistable():
            return [dict(f) for f in self._fallback]
        return self._load_custom()

    def _persistable(self) -> bool:
        store = self._store
        return hasattr(store, "__setitem__") or callable(getattr(store, "set", None))

    def list_feeds(self) -> List[Dict[str, str]]:
        """Return default feeds followed by user-added feeds."""
        return [dict(f) for f in DEFAULT_FEEDS] + self.list_custom()

    def get_default_feeds(self) -> List[Dict[str, str]]:
        return [dict(f) for f in DEFAULT_FEEDS]

    def get_feed(self, feed_id_or_url: str) -> Optional[Dict[str, str]]:
        key = (feed_id_or_url or "").strip()
        for feed in self.list_feeds():
            if feed["id"] == key or feed["url"] == key:
                return dict(feed)
        return None

    def add_feed(self, url: str, name: str = "") -> Dict[str, str]:
        """Add a custom OPDS feed. Raises ValueError on invalid/duplicate URLs."""
        clean_url = (url or "").strip()
        if not clean_url:
            raise ValueError("Catalog URL must not be empty")
        parsed = urllib.parse.urlparse(clean_url)
        if parsed.scheme.lower() not in ("http", "https") or not parsed.netloc:
            raise ValueError(f"Catalog URL must be http(s): {clean_url!r}")
        existing = self.list_custom()
        for feed in existing + [dict(f) for f in DEFAULT_FEEDS]:
            if feed["url"] == clean_url:
                raise ValueError(f"Catalog already registered: {clean_url}")
        base = _slugify(name) if name.strip() else _slugify(parsed.netloc)
        taken = {f["id"] for f in existing} | {f["id"] for f in DEFAULT_FEEDS}
        feed_id = base
        suffix = 2
        while feed_id in taken:
            feed_id = f"{base}-{suffix}"
            suffix += 1
        record = {
            "id": feed_id,
            "name": name.strip() or parsed.netloc,
            "url": clean_url,
        }
        existing.append(record)
        self._save_custom(existing)
        return dict(record)

    def remove_feed(self, feed_id_or_url: str) -> bool:
        """Remove a custom feed by id or URL. Default feeds cannot be removed."""
        key = (feed_id_or_url or "").strip()
        if not key:
            return False
        for default in DEFAULT_FEEDS:
            if key in (default["id"], default["url"]):
                return False
        existing = self.list_custom()
        kept = [f for f in existing if f["id"] != key and f["url"] != key]
        if len(kept) == len(existing):
            return False
        self._save_custom(kept)
        return True

    def clear_custom(self) -> None:
        self._save_custom([])
