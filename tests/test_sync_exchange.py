"""
Headless tests for authorized local sync exchange (WP-14).
Validates FR-17, FR-19, NFR-01, NFR-02.
"""

import json
import os
import tempfile
import unittest
import zipfile
from datetime import datetime, timezone

from src.aquile.domain.models import Annotation, Book, ReadingProgress, ReadingSession
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
    ExchangeError,
    UnsafeBundleError,
    export_book,
    import_bundle,
)
from src.aquile.sync.sync_state import InMemoryTokenStore, SyncState


def make_repos():
    tmp = tempfile.TemporaryDirectory()
    db_path = os.path.join(tmp.name, "aquile.db")
    db = Database(db_path)
    return tmp, db, BookRepository(db), ReadingProgressRepository(db), \
        AnnotationRepository(db), StatisticsRepository(db)


def seed_book(book_repo, progress_repo, ann_repo, stats_repo=None,
              book_id="book-1", updated_progress_at=1000.0,
              ann_updated_at=1000.0, with_session=True):
    book = Book(id=book_id, title="Seed Book", author="Author",
                file_path=f"/books/{book_id}.epub", file_format="epub",
                total_chapters=5, file_size_bytes=1234,
                added_at=900.0, last_read_at=950.0)
    book_repo.add(book)
    progress = ReadingProgress(book_id=book_id, chapter_index=2, page_index=4,
                               cfi="epubcfi(/6/6)", percentage=45.5,
                               updated_at=updated_progress_at)
    progress_repo.save(progress)
    ann = Annotation(id=f"{book_id}-ann-1", book_id=book_id, chapter_index=1,
                     cfi="epubcfi(/6/2)", start_offset=0, end_offset=50,
                     text_content="highlight text", note_text="a note",
                     color="#FFEB3B", created_at=900.0, updated_at=ann_updated_at)
    ann_repo.add(ann)
    if with_session and stats_repo is not None:
        stats_repo.record_session(ReadingSession(
            id=f"{book_id}-sess-1", book_id=book_id,
            started_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            ended_at=datetime(2026, 1, 1, 0, 10, tzinfo=timezone.utc),
            duration_seconds=600.0, active_seconds=500.0, idle_seconds=100.0,
            words_read=1000, wpm=120.0))
    return book


class TestSyncExchange(unittest.TestCase):
    def test_roundtrip_preserves_annotations(self):
        t1, _, b1, p1, a1, s1 = make_repos()
        try:
            seed_book(b1, p1, a1, s1, book_id="rt-ann")
            dest = os.path.join(t1.name, "bundle.zip")
            export_book("rt-ann", b1, p1, a1, s1, dest_path=dest)
            self.assertTrue(os.path.isfile(dest))
            t2, _, b2, p2, a2, s2 = make_repos()
            try:
                result = import_bundle(dest, b2, p2, a2, s2)
                self.assertEqual(result["annotations_added"], 1)
                anns = a2.get_by_book("rt-ann")
                self.assertEqual(len(anns), 1)
                self.assertEqual(anns[0].text_content, "highlight text")
                self.assertEqual(anns[0].note_text, "a note")
                self.assertEqual(anns[0].id, "rt-ann-ann-1")
            finally:
                t2.cleanup()
        finally:
            t1.cleanup()

    def test_roundtrip_preserves_progress(self):
        t1, _, b1, p1, a1, s1 = make_repos()
        try:
            seed_book(b1, p1, a1, s1, book_id="rt-prog")
            dest = os.path.join(t1.name, "b.zip")
            ExchangeBundle.export_book("rt-prog", b1, p1, a1, s1, dest_path=dest)
            t2, _, b2, p2, a2, s2 = make_repos()
            try:
                ExchangeBundle.import_bundle(dest, b2, p2, a2, s2)
                loaded = p2.get("rt-prog")
                self.assertIsNotNone(loaded)
                self.assertEqual(loaded.chapter_index, 2)
                self.assertEqual(loaded.page_index, 4)
                self.assertAlmostEqual(loaded.percentage, 45.5)
            finally:
                t2.cleanup()
        finally:
            t1.cleanup()

    def test_roundtrip_preserves_sessions(self):
        t1, _, b1, p1, a1, s1 = make_repos()
        try:
            seed_book(b1, p1, a1, s1, book_id="rt-sess")
            dest = os.path.join(t1.name, "b.zip")
            export_book("rt-sess", b1, p1, a1, s1, dest_path=dest)
            t2, _, b2, p2, a2, s2 = make_repos()
            try:
                result = import_bundle(dest, b2, p2, a2, s2)
                self.assertEqual(result["sessions_imported"], 1)
                sessions = s2.get_sessions_for_book("rt-sess")
                self.assertEqual(len(sessions), 1)
                self.assertEqual(sessions[0].id, "rt-sess-sess-1")
                self.assertEqual(sessions[0].words_read, 1000)
            finally:
                t2.cleanup()
        finally:
            t1.cleanup()

    def test_newer_incoming_annotation_wins(self):
        t1, _, b1, p1, a1, s1 = make_repos()
        try:
            seed_book(b1, p1, a1, s1, book_id="nb", ann_updated_at=2000.0)
            a1.add(Annotation(id="nb-ann-1", book_id="nb", chapter_index=1,
                              cfi="epubcfi(/6/2)", start_offset=0, end_offset=50,
                              text_content="newer text", note_text="newer note",
                              color="#FF0000", created_at=900.0, updated_at=2000.0))
            dest = os.path.join(t1.name, "b.zip")
            export_book("nb", b1, p1, a1, None, dest_path=dest)
            t2, _, b2, p2, a2, s2 = make_repos()
            try:
                seed_book(b2, p2, a2, None, book_id="nb", ann_updated_at=1000.0,
                          with_session=False)
                result = import_bundle(dest, b2, p2, a2, None)
                self.assertEqual(result["annotations_updated"], 1)
                anns = {a.id: a for a in a2.get_by_book("nb")}
                self.assertEqual(anns["nb-ann-1"].text_content, "newer text")
                self.assertEqual(anns["nb-ann-1"].note_text, "newer note")
            finally:
                t2.cleanup()
        finally:
            t1.cleanup()

    def test_older_import_does_not_clobber_newer_annotation(self):
        t1, _, b1, p1, a1, s1 = make_repos()
        try:
            seed_book(b1, p1, a1, None, book_id="ob", ann_updated_at=1000.0,
                      with_session=False)
            a1.add(Annotation(id="ob-ann-1", book_id="ob", chapter_index=1,
                              cfi="epubcfi(/6/2)", start_offset=0, end_offset=50,
                              text_content="old text", note_text="old",
                              color="#FFEB3B", created_at=900.0, updated_at=1000.0))
            dest = os.path.join(t1.name, "b.zip")
            export_book("ob", b1, p1, a1, None, dest_path=dest)
            t2, _, b2, p2, a2, _s2 = make_repos()
            try:
                seed_book(b2, p2, a2, None, book_id="ob", ann_updated_at=1000.0,
                          with_session=False)
                a2.add(Annotation(id="ob-ann-1", book_id="ob", chapter_index=1,
                                   cfi="epubcfi(/6/2)", start_offset=0, end_offset=50,
                                   text_content="local newer", note_text="keep me",
                                   color="#00FF00", created_at=900.0, updated_at=3000.0))
                result = import_bundle(dest, b2, p2, a2, None)
                self.assertGreaterEqual(result["annotations_skipped_older"], 1)
                self.assertEqual(result["annotations_updated"], 0)
                anns = {a.id: a for a in a2.get_by_book("ob")}
                self.assertEqual(anns["ob-ann-1"].text_content, "local newer")
                self.assertEqual(anns["ob-ann-1"].note_text, "keep me")
            finally:
                t2.cleanup()
        finally:
            t1.cleanup()

    def test_older_progress_does_not_clobber(self):
        t1, _, b1, p1, a1, _s1 = make_repos()
        try:
            seed_book(b1, p1, a1, None, book_id="op", updated_progress_at=1000.0,
                      with_session=False)
            dest = os.path.join(t1.name, "b.zip")
            export_book("op", b1, p1, a1, None, dest_path=dest)
            t2, _, b2, p2, a2, _s2 = make_repos()
            try:
                seed_book(b2, p2, a2, None, book_id="op", updated_progress_at=5000.0,
                          with_session=False)
                p2.save(ReadingProgress(book_id="op", chapter_index=9, page_index=9,
                                        cfi="local", percentage=99.0, updated_at=5000.0))
                result = import_bundle(dest, b2, p2, a2, None)
                self.assertTrue(result["progress_skipped_older"])
                self.assertFalse(result["progress_updated"])
                self.assertAlmostEqual(p2.get("op").percentage, 99.0)
            finally:
                t2.cleanup()
        finally:
            t1.cleanup()

    def test_newer_progress_wins(self):
        t1, _, b1, p1, a1, _s1 = make_repos()
        try:
            seed_book(b1, p1, a1, None, book_id="nprog", updated_progress_at=9000.0,
                      with_session=False)
            p1.save(ReadingProgress(book_id="nprog", chapter_index=7, page_index=7,
                                    cfi="new", percentage=80.0, updated_at=9000.0))
            dest = os.path.join(t1.name, "b.zip")
            export_book("nprog", b1, p1, a1, None, dest_path=dest)
            t2, _, b2, p2, a2, _s2 = make_repos()
            try:
                seed_book(b2, p2, a2, None, book_id="nprog", updated_progress_at=1000.0,
                          with_session=False)
                result = import_bundle(dest, b2, p2, a2, None)
                self.assertTrue(result["progress_updated"])
                self.assertAlmostEqual(p2.get("nprog").percentage, 80.0)
            finally:
                t2.cleanup()
        finally:
            t1.cleanup()

    def test_corrupt_zip_raises(self):
        tmp, _, b, p, a, _s = make_repos()
        try:
            bad = os.path.join(tmp.name, "bad.zip")
            with open(bad, "wb") as handle:
                handle.write(b"this is not a zip file at all")
            with self.assertRaises((CorruptBundleError, ExchangeError)):
                import_bundle(bad, b, p, a, None)
        finally:
            tmp.cleanup()

    def test_traversal_attack_blocked(self):
        tmp, _, b, p, a, _s = make_repos()
        try:
            evil = os.path.join(tmp.name, "evil.zip")
            manifest = {"format": "aquile-exchange", "version": 1,
                        "exported_at": 1.0, "book_id": "x", "files": {}}
            with zipfile.ZipFile(evil, "w") as archive:
                archive.writestr("manifest.json", json.dumps(manifest))
                archive.writestr("../../evil.txt", b"pwned")
            with self.assertRaises(UnsafeBundleError):
                import_bundle(evil, b, p, a, None)
            self.assertFalse(os.path.exists("/tmp/evil.txt"))
        finally:
            tmp.cleanup()

    def test_duplicate_reimport_is_idempotent(self):
        t1, _, b1, p1, a1, s1 = make_repos()
        try:
            seed_book(b1, p1, a1, s1, book_id="dup")
            dest = os.path.join(t1.name, "b.zip")
            export_book("dup", b1, p1, a1, s1, dest_path=dest)
            t2, _, b2, p2, a2, s2 = make_repos()
            try:
                first = import_bundle(dest, b2, p2, a2, s2)
                self.assertEqual(first["annotations_added"], 1)
                second = import_bundle(dest, b2, p2, a2, s2)
                self.assertEqual(second["annotations_added"], 0)
                self.assertEqual(second["sessions_imported"], 0)
                self.assertEqual(len(a2.get_by_book("dup")), 1)
                self.assertEqual(len(s2.get_sessions_for_book("dup")), 1)
            finally:
                t2.cleanup()
        finally:
            t1.cleanup()

    def test_duplicate_book_by_path_detected(self):
        t1, _, b1, p1, a1, _s1 = make_repos()
        try:
            seed_book(b1, p1, a1, None, book_id="orig-id", with_session=False)
            dest = os.path.join(t1.name, "b.zip")
            export_book("orig-id", b1, p1, a1, None, dest_path=dest)
            t2, _, b2, p2, a2, _s2 = make_repos()
            try:
                other = Book(id="other-id", title="Same File", author="Author",
                             file_path="/books/orig-id.epub", file_format="epub",
                             total_chapters=5, file_size_bytes=1234,
                             added_at=800.0, last_read_at=800.0)
                b2.add(other)
                result = import_bundle(dest, b2, p2, a2, None)
                self.assertTrue(result["book_duplicate"])
                self.assertFalse(result["book_created"])
                self.assertEqual(len(b2.list_all()), 1)
                self.assertEqual(result["book_id"], "other-id")
            finally:
                t2.cleanup()
        finally:
            t1.cleanup()

    def test_sign_out_clears_tokens_and_keeps_local_data(self):
        tmp, _, b, p, a, _s = make_repos()
        try:
            seed_book(b, p, a, None, book_id="so", with_session=False)
            store = InMemoryTokenStore()
            state = SyncState()
            state.sign_in_local("user-1", store, "secret-token")
            self.assertEqual(store.get_token("user-1"), "secret-token")
            self.assertTrue(state.signed_in)
            state.sign_out(store)
            self.assertIsNone(store.get_token("user-1"))
            self.assertFalse(state.signed_in)
            self.assertIsNone(state.account_id)
            # Local data retained (NFR-02).
            self.assertIsNotNone(b.get_by_id("so"))
            self.assertEqual(len(a.get_by_book("so")), 1)
        finally:
            tmp.cleanup()

    def test_status_truthfulness(self):
        state = SyncState()
        self.assertEqual(state.status(), "local-only")
        self.assertIn("local-only", state.describe())
        state.mark_local_change()
        state.mark_exported(timestamp=1700000000.0)
        self.assertEqual(state.status(), "exported")
        self.assertIn("exported", state.describe())
        state.mark_imported(timestamp=1700000100.0)
        self.assertEqual(state.status(), "imported")
        self.assertIn("imported", state.describe())
        for text in (state.describe(), state.status()):
            self.assertNotIn("synced", text.lower())
            self.assertNotIn("upload", text.lower())

    def test_tampered_checksum_rejected(self):
        t1, _, b1, p1, a1, _s1 = make_repos()
        try:
            seed_book(b1, p1, a1, None, book_id="chk", with_session=False)
            dest = os.path.join(t1.name, "b.zip")
            export_book("chk", b1, p1, a1, None, dest_path=dest)
            tampered = os.path.join(t1.name, "tampered.zip")
            with zipfile.ZipFile(dest, "r") as src:
                payloads = {n: src.read(n) for n in src.namelist()}
            payloads["annotations.json"] = b'[{"id": "forged"}]'
            with zipfile.ZipFile(tampered, "w", compression=zipfile.ZIP_DEFLATED) as out:
                for name, data in payloads.items():
                    out.writestr(name, data)
            t2, _, b2, p2, a2, _s2 = make_repos()
            try:
                with self.assertRaises(CorruptBundleError):
                    import_bundle(tampered, b2, p2, a2, None)
            finally:
                t2.cleanup()
        finally:
            t1.cleanup()


if __name__ == "__main__":
    unittest.main()
