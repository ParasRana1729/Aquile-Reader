"""
Tier 5 adversarial hardening tests (NFR-06, AT-02, FR-20).

Covers hostile/malformed inputs across archive handling, PDF parsing,
OPDS feeds, exchange bundles, TTS rates, dictionary queries, entitlements,
and concurrent storage writes.

Constraints: temp dirs only, stdlib only, deterministic, no network,
no audio hardware. Each test completes in well under 5 seconds.
"""

import hashlib
import json
import math
import os
import stat
import sys
import tempfile
import threading
import time
import unittest
import zipfile
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.aquile.reader.comic_reader import (
    ComicArchiveEngine,
    ComicSecurityError,
)
from src.aquile.reader.pdf_reader import PdfDocumentEngine
from src.aquile.catalog.opds_client import (
    NetworkError,
    OpdsClient,
    UnsupportedContentError,
)
from src.aquile.sync.exchange import (
    CorruptBundleError,
    ExchangeBundle,
    UnsafeBundleError,
)
from src.aquile.reader.tts_engine import TtsEngine
from src.aquile.reader.dictionary import (
    DictionaryService,
    InvalidQueryError,
)
from src.aquile.entitlements.tiers import EntitlementError, TierManager
from src.aquile.storage.database import Database
from src.aquile.storage.repository import StatisticsRepository
from src.aquile.domain.models import ReadingSession


def _make_cbz(path, entries):
    """Write a CBZ zip at path from {name: bytes} mapping."""
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as archive:
        for name, data in entries.items():
            archive.writestr(name, data)


class TestTier5Adversarial(unittest.TestCase):
    # -- comic archive bombs / traversal --------------------------------

    def test_zip_bomb_many_files_bounded(self):
        """1000 tiny entries must be handled without OOM or hang."""
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "many.cbz")
            with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as archive:
                for i in range(1000):
                    archive.writestr("page%04d.png" % i, b"x" * 64)
            start = time.time()
            engine = ComicArchiveEngine(path)
            try:
                self.assertEqual(engine.get_page_count(), 1000)
                # Spot-check a page reads back intact.
                self.assertEqual(engine.get_page_image_bytes(0), b"x" * 64)
            finally:
                engine.close()
            self.assertLess(time.time() - start, 5.0)

    def test_oversize_entry_bounded(self):
        """A single multi-MiB entry must be handled without OOM or hang."""
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "big.cbz")
            payload = b"ABCD" * (2 * 1024 * 1024)  # 8 MiB deterministic
            _make_cbz(path, {"big.png": payload})
            start = time.time()
            engine = ComicArchiveEngine(path)
            try:
                self.assertEqual(engine.get_page_count(), 1)
                self.assertEqual(engine.get_page_image_bytes(0), payload)
            finally:
                engine.close()
            self.assertLess(time.time() - start, 5.0)

    def test_traversal_dotdot_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "trav.cbz")
            _make_cbz(path, {"../evil.png": b"x" * 16})
            with self.assertRaises(ComicSecurityError):
                ComicArchiveEngine(path)

    def test_traversal_absolute_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "abs.cbz")
            _make_cbz(path, {"/tmp/evil.png": b"x" * 16})
            with self.assertRaises(ComicSecurityError):
                ComicArchiveEngine(path)

    def test_traversal_drive_letter_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            for variant in ("C:/evil.png", "C:\\evil.png"):
                path = os.path.join(tmp, "drive.cbz")
                _make_cbz(path, {variant: b"x" * 16})
                with self.assertRaises(ComicSecurityError, msg=variant):
                    ComicArchiveEngine(path)

    def test_symlink_entry_no_escape(self):
        """A symlink entry must not write outside the temp dir (in-memory only)."""
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "sym.cbz")
            link = zipfile.ZipInfo("link.png")
            link.create_system = 3  # Unix attributes follow.
            link.external_attr = (stat.S_IFLNK | 0o777) << 16
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("page0001.png", b"x" * 64)
                archive.writestr(link, "../../etc/passwd")
            before = set(os.listdir(tmp))
            engine = ComicArchiveEngine(path)
            try:
                self.assertIn("link.png", engine.list_page_entries())
                # Bytes stay in memory; nothing is extracted to disk.
                self.assertEqual(set(os.listdir(tmp)), before)
            finally:
                engine.close()

    # -- PDF hostile inputs / viewport math ------------------------------

    def test_corrupt_pdf_header_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "bad.pdf")
            with open(path, "wb") as handle:
                handle.write(b"NOT A PDF AT ALL \x00\x01\x02 garbage " * 20)
            with self.assertRaises((ValueError, RuntimeError)):
                PdfDocumentEngine(path)

    def test_empty_and_short_pdf_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            empty = os.path.join(tmp, "empty.pdf")
            open(empty, "wb").close()
            with self.assertRaises((ValueError, RuntimeError)):
                PdfDocumentEngine(empty)
            short = os.path.join(tmp, "short.pdf")
            with open(short, "wb") as handle:
                handle.write(b"%PDF-1.4\ntrailer<</Root>>")
            with self.assertRaises((ValueError, RuntimeError)):
                PdfDocumentEngine(short)

    def test_huge_viewport_math_finite(self):
        """Extreme viewport sizes must clamp without crash/inf/nan."""
        engine = PdfDocumentEngine.__new__(PdfDocumentEngine)
        engine._page_count = 1
        engine._dimensions_cache = {0: (612.0, 792.0)}
        for width, height in (
            (1e308, 1e308),
            (float("inf"), float("inf")),
            (1e308, 1.0),
            (1.0, 1e308),
        ):
            for mode in ("width", "page", "height"):
                scale = engine.calculate_fit_scale(0, width, height, mode)
                self.assertTrue(math.isfinite(scale), (width, height, mode))
                self.assertGreaterEqual(scale, 0.25)
                self.assertLessEqual(scale, 5.0)
        # Degenerate viewports return 0.0 safely (no ZeroDivisionError).
        self.assertEqual(engine.calculate_fit_scale(0, 0.0, 600.0, "width"), 0.0)
        self.assertEqual(engine.calculate_fit_scale(0, -10.0, 600.0, "page"), 0.0)

    # -- OPDS malicious feeds --------------------------------------------

    def test_opds_nested_entities_capped(self):
        """Billion-laughs-style nested entities must be rejected quickly."""
        with tempfile.TemporaryDirectory() as tmp:
            parts = ["<!ENTITY a0usi%sng '%s'>" % ("x", "x" * 40)]
            for i in range(1, 10):
                parts.append("<!ENTITY a%d>%s</!ENTITY>" % (i, "&a%d;" % (i - 1) * 5))
            xml = (
                "<?xml version='1.0'?><!DOCTYPE feed [%s]>"
                "<feed xmlns='http://www.w3.org/2005/Atom'>"
                "<title>&a9;</title></feed>" % "".join(parts)
            )
            path = os.path.join(tmp, "lol.xml")
            with open(path, "w") as handle:
                handle.write(xml)
            client = OpdsClient()
            start = time.time()
            with self.assertRaises((NetworkError, UnsupportedContentError)):
                client.discover("file://" + path)
            self.assertLess(time.time() - start, 5.0)

    def test_opds_oversize_feed_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "big.xml")
            with open(path, "w") as handle:
                handle.write(
                    "<feed xmlns='http://www.w3.org/2005/Atom'>"
                    "<title>T</title>" + "<entry/>" * 20000 + "</feed>"
                )
            client = OpdsClient(max_feed_bytes=1024)
            with self.assertRaises(UnsupportedContentError):
                client.discover("file://" + path)

    # -- exchange bundle integrity ---------------------------------------

    def _tampered_bundle(self, tmp):
        book = {"id": "b9", "title": "T"}
        book_bytes = json.dumps(book).encode("utf-8")
        manifest = {
            "format": "aquile-exchange",
            "version": 1,
            "exported_at": 1.0,
            "book_id": "b9",
            "files": {
                "book.json": "0" * 64,  # Wrong on purpose.
                "progress.json": hashlib.sha256(b"null").hexdigest(),
                "annotations.json": hashlib.sha256(b"[]").hexdigest(),
                "sessions.json": hashlib.sha256(b"[]").hexdigest(),
            },
        }
        path = os.path.join(tmp, "evil.zip")
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("manifest.json", json.dumps(manifest).encode("utf-8"))
            archive.writestr("book.json", book_bytes)
            archive.writestr("progress.json", b"null")
            archive.writestr("annotations.json", b"[]")
            archive.writestr("sessions.json", b"[]")
        return path

    def test_exchange_checksum_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._tampered_bundle(tmp)
            with self.assertRaises(CorruptBundleError) as ctx:
                ExchangeBundle.import_bundle(
                    path, object(), object(), object()
                )
            self.assertIn("checksum", str(ctx.exception).lower())

    def test_exchange_traversal_entry_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "trav.zip")
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("../evil.json", b"x")
            with self.assertRaises(UnsafeBundleError):
                ExchangeBundle.import_bundle(
                    path, object(), object(), object()
                )

    # -- TTS rate extremes ------------------------------------------------

    def test_tts_speed_extremes_clamped(self):
        engine = TtsEngine()
        self.assertEqual(engine.set_rate(0.01), 0.5)
        self.assertEqual(engine.set_rate(100.0), 2.0)
        self.assertEqual(engine.set_rate(float("-inf")), 0.5)
        self.assertEqual(engine.set_rate(float("inf")), 2.0)
        self.assertEqual(TtsEngine(rate=0.01).get_rate(), 0.5)
        self.assertEqual(TtsEngine(rate=100.0).get_rate(), 2.0)
        # NaN falls back to the default rate instead of poisoning state.
        self.assertEqual(TtsEngine(rate=float("nan")).get_rate(), 1.0)

    # -- dictionary hostile queries ---------------------------------------

    def test_dictionary_empty_input_rejected(self):
        service = DictionaryService()
        with self.assertRaises(InvalidQueryError):
            service.lookup("")

    def test_dictionary_whitespace_input_rejected(self):
        service = DictionaryService()
        with self.assertRaises(InvalidQueryError):
            service.lookup("   \t \n  ")

    def test_dictionary_huge_input_rejected(self):
        service = DictionaryService()
        start = time.time()
        with self.assertRaises(InvalidQueryError) as ctx:
            service.lookup("a" * (1024 * 1024))
        self.assertLess(time.time() - start, 5.0)
        # The megabyte of input must not be echoed into the error/log text.
        self.assertLess(len(str(ctx.exception)), 500)

    # -- entitlement hostile payloads -------------------------------------

    def test_entitlement_malformed_json_rejected(self):
        bad_payloads = [
            "{bad json",
            "",
            b"\xff\xfe not utf-8 \x00",
            "[1, 2, 3]",
            "42",
            '"just a string"',
            '{"tier": "gold", "issued_by": "local"}',
            '{"tier": "premium", "trial_days": -5, "issued_by": "local"}',
        ]
        for payload in bad_payloads:
            with self.subTest(payload=repr(payload)[:40]):
                with self.assertRaises(EntitlementError):
                    TierManager.restore(payload)

    def test_entitlement_foreign_issuer_rejected(self):
        for issuer in ("microsoft_store", "google_play", "apple_app_store", ""):
            payload = json.dumps({"tier": "premium", "issued_by": issuer})
            with self.subTest(issuer=issuer):
                with self.assertRaises(EntitlementError):
                    TierManager.restore(payload)
        # The locally issued round-trip still works.
        manager = TierManager.restore(TierManager(tier="premium").export_json())
        self.assertEqual(manager.tier, "premium")

    # -- concurrent storage writes -----------------------------------------

    def test_concurrent_wal_writes_safe(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Database(os.path.join(tmp, "concurrent.db"))
            with db.get_connection() as conn:
                conn.execute(
                    "INSERT INTO books (id, title, author, file_path, "
                    "file_format, added_at) VALUES (?, ?, ?, ?, ?, ?)",
                    ("b1", "T", "A", "/tmp/tier5.epub", "epub", 1.0),
                )
                conn.commit()
            repo = StatisticsRepository(db)
            errors = []

            def work(thread_id):
                try:
                    for i in range(25):
                        session = ReadingSession(
                            id="t%d-%d" % (thread_id, i),
                            book_id="b1",
                            started_at=datetime.now(timezone.utc),
                            duration_seconds=1.0,
                            active_seconds=1.0,
                            words_read=10,
                            wpm=100.0,
                        )
                        repo.record_session(session)
                except Exception as exc:  # pragma: no cover
                    errors.append(exc)

            threads = [threading.Thread(target=work, args=(t,)) for t in range(8)]
            start = time.time()
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            self.assertLess(time.time() - start, 30.0)
            self.assertEqual(errors, [])
            with db.get_connection() as conn:
                count = conn.execute(
                    "SELECT COUNT(*) AS c FROM reading_sessions"
                ).fetchone()["c"]
            self.assertEqual(count, 8 * 25)


if __name__ == "__main__":
    unittest.main()
