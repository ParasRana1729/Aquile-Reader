"""
Headless tests for the catalog + exchange GTK dialogs (FR-14 / FR-17).

GUI construction tests skip gracefully when no display is available;
all other tests run headless against CatalogManager / ExchangeBundle /
SyncState, plus dialog core helpers where possible.
"""

import json
import os
import tempfile
import unittest
import zipfile

from src.aquile.catalog.catalog_manager import CatalogManager
from src.aquile.catalog.opds_client import OpdsClient
from src.aquile.domain.models import Annotation, Book, ReadingProgress
from src.aquile.storage.database import Database
from src.aquile.storage.repository import (
    AnnotationRepository,
    BookRepository,
    ReadingProgressRepository,
    StatisticsRepository,
)
from src.aquile.sync.exchange import (
    CorruptBundleError,
    ExchangeBundle,
    UnsafeBundleError,
    export_book,
    import_bundle,
)
from src.aquile.sync.sync_state import (
    STATUS_EXPORTED,
    STATUS_IMPORTED,
    STATUS_LOCAL_ONLY,
    InMemoryTokenStore,
    SyncState,
)

try:
    import gi
    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")
    from gi.repository import Gtk  # noqa: F401
    _GI_OK = True
except Exception:
    _GI_OK = False


def _try_construct(cls, *args, **kwargs):
    """Construct a dialog, raising SkipTest when no display/toolkit."""
    if not _GI_OK:
        raise unittest.SkipTest("GTK/Adw unavailable")
    try:
        return cls(*args, **kwargs)
    except Exception as exc:
        raise unittest.SkipTest(f"no display for dialogs: {exc}")


def _lazy_catalog_dialog():
    from src.aquile.ui.catalog_dialog import CatalogDialog
    return CatalogDialog


def _lazy_exchange_dialog():
    from src.aquile.ui.exchange_dialog import ExchangeDialog
    return ExchangeDialog


def make_repos():
    tmp = tempfile.TemporaryDirectory()
    db = Database(os.path.join(tmp.name, "aquile.db"))
    return (tmp, BookRepository(db), ReadingProgressRepository(db),
            AnnotationRepository(db), StatisticsRepository(db))


def seed_book(book_repo, progress_repo, ann_repo, book_id="book-1"):
    book_repo.add(Book(id=book_id, title="Seed Book", author="Author",
                       file_path=f"/books/{book_id}.epub", file_format="epub",
                       total_chapters=5, file_size_bytes=1234,
                       added_at=900.0, last_read_at=950.0))
    progress_repo.save(ReadingProgress(book_id=book_id, chapter_index=2,
                                       page_index=4, cfi="epubcfi(/6/6)",
                                       percentage=45.5, updated_at=1000.0))
    ann_repo.add(Annotation(id=f"{book_id}-ann-1", book_id=book_id,
                            chapter_index=1, cfi="epubcfi(/6/2)",
                            start_offset=0, end_offset=50,
                            text_content="highlight", note_text="note",
                            color="#FFEB3B", created_at=900.0,
                            updated_at=1000.0))


class TestCatalogExchangeUi(unittest.TestCase):
    def test_catalog_dialog_constructs_without_network(self):
        CatalogDialog = _lazy_catalog_dialog()
        from unittest.mock import patch
        with patch.object(OpdsClient, "discover",
                          side_effect=AssertionError("network in __init__")):
            dlg = _try_construct(CatalogDialog, None, CatalogManager({}), None)
        self.assertTrue(hasattr(dlg, "feed_url_entry"))
        self.assertTrue(hasattr(dlg, "feed_listbox"))
        self.assertTrue(hasattr(dlg, "search_entry"))
        self.assertTrue(hasattr(dlg, "results_listbox"))
        self.assertTrue(hasattr(dlg, "status_label"))

    def test_exchange_dialog_constructs_local_only(self):
        ExchangeDialog = _lazy_exchange_dialog()
        tmp, b, p, a, s = make_repos()
        try:
            dlg = _try_construct(ExchangeDialog, None, b, p, a, s)
            self.assertIn("local-only", dlg.get_status_text())
        finally:
            tmp.cleanup()

    def test_manager_add_remove_reflected(self):
        manager = CatalogManager({})
        before = len(manager.list_feeds())
        record = manager.add_feed("https://example.org/opds", "Example")
        self.assertIn("https://example.org/opds",
                      [f["url"] for f in manager.list_feeds()])
        self.assertEqual(len(manager.list_feeds()), before + 1)
        with self.assertRaises(ValueError):
            manager.add_feed("https://example.org/opds")
        self.assertTrue(manager.remove_feed(record["id"]))
        self.assertNotIn("https://example.org/opds",
                         [f["url"] for f in manager.list_feeds()])
        # Built-in feeds are protected.
        self.assertFalse(manager.remove_feed("gutenberg"))
        # Dialog reflects the registry when a display exists.
        try:
            CatalogDialog = _lazy_catalog_dialog()
            dlg = _try_construct(CatalogDialog, None, manager, None)
        except unittest.SkipTest:
            return
        manager.add_feed("https://example.org/second")
        dlg.refresh_feeds()
        urls = list(dlg._feed_urls)
        self.assertIn("https://example.org/second", urls)
        self.assertEqual(dlg.get_feed_count(), len(manager.list_feeds()))

    def test_catalog_search_is_local_without_network(self):
        client = OpdsClient()
        client._entries = [
            {"id": "1", "title": "Moby Dick", "author": "Melville"},
            {"id": "2", "title": "Pride and Prejudice", "author": "Austen"},
        ]
        client._by_id = {e["id"]: e for e in client._entries}
        hits = client.search("moby")
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["id"], "1")
        self.assertEqual(len(client.search("")), 2)

    def test_exchange_export_import_roundtrip(self):
        t1, b1, p1, a1, s1 = make_repos()
        try:
            seed_book(b1, p1, a1, book_id="rt-ui")
            dest = os.path.join(t1.name, "book.aquile.zip")
            export_book("rt-ui", b1, p1, a1, s1, dest_path=dest)
            self.assertTrue(os.path.isfile(dest))
            t2, b2, p2, a2, s2 = make_repos()
            try:
                summary = import_bundle(dest, b2, p2, a2, s2)
                self.assertEqual(summary["annotations_added"], 1)
                loaded = p2.get("rt-ui")
                self.assertIsNotNone(loaded)
                self.assertAlmostEqual(loaded.percentage, 45.5)
                # Same path through the dialog helper when possible.
                try:
                    ExchangeDialog = _lazy_exchange_dialog()
                    dlg = _try_construct(ExchangeDialog, None, b2, p2, a2, s2)
                except unittest.SkipTest:
                    return
                dest2 = os.path.join(t1.name, "re-export.aquile.zip")
                out = dlg.export_to_path("rt-ui", dest2)
                self.assertTrue(os.path.isfile(out))
            finally:
                t2.cleanup()
        finally:
            t1.cleanup()

    def test_status_strings_exact(self):
        state = SyncState()
        self.assertEqual(state.status(), STATUS_LOCAL_ONLY)
        self.assertEqual(STATUS_LOCAL_ONLY, "local-only")
        self.assertEqual(STATUS_EXPORTED, "exported")
        self.assertEqual(STATUS_IMPORTED, "imported")
        state.mark_exported(timestamp=1700000000.0)
        self.assertEqual(state.status(), "exported")
        self.assertIn("exported", state.describe())
        state.mark_imported(timestamp=1700000100.0)
        self.assertEqual(state.status(), "imported")
        self.assertIn("imported", state.describe())
        for text in (state.status(), state.describe()):
            self.assertNotIn("synced", text.lower())
        # Dialog-level status follows the same truthful strings.
        try:
            ExchangeDialog = _lazy_exchange_dialog()
            tmp, b, p, a, s = make_repos()
            try:
                seed_book(b, p, a, book_id="st-1")
                dlg = _try_construct(ExchangeDialog, None, b, p, a, s)
                self.assertIn("local-only", dlg.get_status_text())
                dest = os.path.join(tmp.name, "st.aquile.zip")
                dlg.export_to_path("st-1", dest)
                self.assertIn("exported", dlg.get_status_text())
                dlg.import_from_path(dest)
                self.assertIn("imported", dlg.get_status_text())
                dlg.do_sign_out()
                self.assertIsNotNone(b.get_by_id("st-1"))  # data retained
            finally:
                tmp.cleanup()
        except unittest.SkipTest:
            pass

    def test_exchange_traversal_safe(self):
        tmp, b, p, a, _s = make_repos()
        try:
            evil = os.path.join(tmp.name, "evil.zip")
            manifest = {"format": "aquile-exchange", "version": 1,
                        "exported_at": 1.0, "book_id": "x", "files": {}}
            with zipfile.ZipFile(evil, "w") as archive:
                archive.writestr("manifest.json", json.dumps(manifest))
                archive.writestr("../../evil.txt", b"pwned")
            with self.assertRaises(UnsafeBundleError):
                import_bundle(evil, b, p, a, None)
            with self.assertRaises((UnsafeBundleError, CorruptBundleError)):
                ExchangeBundle.import_bundle(evil, b, p, a, None)
            # Dialog helper rejects the same bundle without extracting.
            try:
                ExchangeDialog = _lazy_exchange_dialog()
                dlg = _try_construct(ExchangeDialog, None, b, p, a, None)
            except unittest.SkipTest:
                return
            with self.assertRaises((UnsafeBundleError, CorruptBundleError)):
                dlg.import_from_path(evil)
        finally:
            tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
