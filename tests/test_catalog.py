"""
Headless tests for WP-13 online catalogs (FR-14, FR-20, NFR-03..NFR-07).

No real network: all HTTP goes to an ephemeral localhost http.server and
file:// fixtures, or to monkeypatched urllib stubs.
"""

import http.server
import json
import os
import socket
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from unittest import mock

from src.aquile.catalog.opds_client import (
    CancelledError,
    NetworkError,
    OpdsClient,
    UnsupportedContentError,
)
from src.aquile.catalog.catalog_manager import (
    GUTENBERG_OPDS_URL,
    STANDARDEBOOKS_OPDS_URL,
    CatalogManager,
)

OPDS1_XML = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Test Catalog</title>
  <entry>
    <id>urn:gutenberg:1342</id>
    <title>Pride and Prejudice</title>
    <author><name>Jane Austen</name></author>
    <summary>A classic novel.</summary>
    <link rel="http://opds-spec.org/acquisition" href="/dl/pride.epub"
          type="application/epub+zip"/>
  </entry>
  <entry>
    <id>urn:gutenberg:11</id>
    <title>Alice's Adventures in Wonderland</title>
    <author><name>Lewis Carroll</name></author>
    <summary>Down the rabbit hole.</summary>
    <link rel="http://opds-spec.org/acquisition" href="/dl/alice.pdf"
          type="application/pdf"/>
  </entry>
  <entry>
    <id>urn:gutenberg:1661</id>
    <title>The Adventures of Sherlock Holmes</title>
    <author><name>Arthur Conan Doyle</name></author>
    <summary>Detective stories.</summary>
    <link rel="http://opds-spec.org/acquisition" href="/dl/sherlock.epub"
          type="application/epub+zip"/>
  </entry>
</feed>
"""

OPDS2_DOC = {
    "metadata": {"title": "Test OPDS2 Catalog"},
    "publications": [
        {
            "metadata": {
                "title": "Moby Dick",
                "author": "Herman Melville",
                "identifier": "urn:opds2:moby",
            },
            "links": [
                {
                    "href": "/dl/moby.epub",
                    "rel": "http://opds-spec.org/acquisition",
                    "type": "application/epub+zip",
                }
            ],
        },
        {
            "metadata": {
                "title": "Frankenstein",
                "author": [{"name": "Mary Shelley"}],
                "identifier": "urn:opds2:frank",
            },
            "links": [
                {
                    "href": "/dl/frank.pdf",
                    "rel": "http://opds-spec.org/acquisition",
                    "type": "application/pdf",
                }
            ],
        },
    ],
}

FAKE_EPUB = b"PK\x03\x04" + b"fake-epub-content-" * 64
FAKE_PDF = b"%PDF-1.4 fake-pdf-content-" * 64


def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _start_server(routes):
    """routes: path -> (status, headers, body) or callable(path)->tuple. Returns (server, thread, base)."""
    state = {"hits": {}}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            path = self.path.split("?", 1)[0]
            state["hits"][path] = state["hits"].get(path, 0) + 1
            route = routes.get(path)
            if callable(route):
                status, headers, body = route(path, state["hits"][path])
            elif route is None:
                status, headers, body = (404, {"Content-Type": "text/plain"}, b"nope")
            else:
                status, headers, body = route
            self.send_response(status)
            for k, v in headers.items():
                self.send_header(k, v)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def log_message(self, *args):
            pass

    port = _free_port()
    server = http.server.HTTPServer(("127.0.0.1", port), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    server._test_state = state
    return server, thread, f"http://127.0.0.1:{port}"


class TestOpdsDiscovery(unittest.TestCase):
    def tearDown(self):
        for attr in ("_server",):
            srv = getattr(self, attr, None)
            if srv is not None:
                srv.shutdown()
                srv.server_close()

    def test_discover_opds1_atom_parses_entries(self):
        routes = {
            "/feed.xml": (
                200,
                {"Content-Type": "application/atom+xml"},
                OPDS1_XML.encode("utf-8"),
            )
        }
        self._server, _t, base = _start_server(routes)
        client = OpdsClient(timeout=5)
        entries = client.discover(base + "/feed.xml")
        self.assertEqual(len(entries), 3)
        self.assertEqual(entries[0]["title"], "Pride and Prejudice")
        self.assertEqual(entries[0]["author"], "Jane Austen")
        self.assertEqual(entries[0]["format"], "epub")
        self.assertTrue(entries[0]["acquisition_url"].endswith("/dl/pride.epub"))
        self.assertEqual(entries[1]["format"], "pdf")

    def test_discover_opds2_json_parses_publications(self):
        body = json.dumps(OPDS2_DOC).encode("utf-8")
        routes = {
            "/opds.json": (
                200,
                {"Content-Type": "application/opds+json"},
                body,
            )
        }
        self._server, _t, base = _start_server(routes)
        client = OpdsClient(timeout=5)
        entries = client.discover(base + "/opds.json")
        self.assertEqual(len(entries), 2)
        titles = {e["title"] for e in entries}
        self.assertIn("Moby Dick", titles)
        self.assertIn("Frankenstein", titles)
        moby = next(e for e in entries if e["title"] == "Moby Dick")
        self.assertEqual(moby["author"], "Herman Melville")
        self.assertEqual(moby["format"], "epub")

    def test_discover_file_fixture(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "feed.xml")
            with open(path, "w", encoding="utf-8") as f:
                f.write(OPDS1_XML)
            file_url = "file://" + path
            client = OpdsClient(timeout=5)
            entries = client.discover(file_url)
            self.assertEqual(len(entries), 3)

    def test_search_filters_cached_entries(self):
        routes = {
            "/feed.xml": (
                200,
                {"Content-Type": "application/atom+xml"},
                OPDS1_XML.encode("utf-8"),
            )
        }
        self._server, _t, base = _start_server(routes)
        client = OpdsClient(timeout=5)
        client.discover(base + "/feed.xml")
        hits = client.search("alice")
        self.assertEqual(len(hits), 1)
        self.assertIn("Alice", hits[0]["title"])
        hits = client.search("AUSTEN")
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["author"], "Jane Austen")
        self.assertEqual(len(client.search("")), 3)
        self.assertEqual(client.search("no-such-book-xyz"), [])

    def test_get_details_returns_entry_and_none(self):
        routes = {
            "/feed.xml": (
                200,
                {"Content-Type": "application/atom+xml"},
                OPDS1_XML.encode("utf-8"),
            )
        }
        self._server, _t, base = _start_server(routes)
        client = OpdsClient(timeout=5)
        client.discover(base + "/feed.xml")
        details = client.get_details("urn:gutenberg:1342")
        self.assertIsNotNone(details)
        self.assertEqual(details["title"], "Pride and Prejudice")
        self.assertIsNone(client.get_details("urn:unknown:0000"))

    def test_discover_offline_raises_network_error(self):
        client = OpdsClient(timeout=2)
        with mock.patch.object(
            urllib.request, "urlopen", side_effect=urllib.error.URLError("offline")
        ):
            with self.assertRaises(NetworkError):
                client.discover("http://127.0.0.1:9/feed.xml")

    def test_discover_404_raises_network_error(self):
        routes = {}
        self._server, _t, base = _start_server(routes)
        client = OpdsClient(timeout=5)
        with self.assertRaises(NetworkError):
            client.discover(base + "/missing.xml")


class TestOpdsDownload(unittest.TestCase):
    def tearDown(self):
        srv = getattr(self, "_server", None)
        if srv is not None:
            srv.shutdown()
            srv.server_close()

    def test_download_reports_progress_and_writes_file(self):
        routes = {
            "/dl/pride.epub": (
                200,
                {"Content-Type": "application/epub+zip"},
                FAKE_EPUB,
            )
        }
        self._server, _t, base = _start_server(routes)
        client = OpdsClient(timeout=5)
        entry = {
            "id": "urn:gutenberg:1342",
            "title": "Pride and Prejudice",
            "author": "Jane Austen",
            "acquisition_url": base + "/dl/pride.epub",
            "acquisition_type": "application/epub+zip",
            "format": "epub",
        }
        progress = []
        with tempfile.TemporaryDirectory() as tmp:
            out = client.download(
                entry, tmp, progress_cb=lambda d, t: progress.append((d, t))
            )
            self.assertTrue(os.path.isfile(out))
            self.assertTrue(out.endswith(".epub"))
            with open(out, "rb") as f:
                self.assertEqual(f.read(), FAKE_EPUB)
        self.assertTrue(len(progress) >= 1)
        self.assertEqual(progress[-1][0], len(FAKE_EPUB))

    def test_download_cancel_deletes_partial(self):
        big = b"PK\x03\x04" + b"x" * (256 * 1024)
        routes = {
            "/dl/big.epub": (
                200,
                {"Content-Type": "application/epub+zip"},
                big,
            )
        }
        self._server, _t, base = _start_server(routes)
        client = OpdsClient(timeout=5)
        entry = {
            "id": "big",
            "title": "Big Book",
            "acquisition_url": base + "/dl/big.epub",
            "acquisition_type": "application/epub+zip",
            "format": "epub",
        }
        token = {"cancelled": False}

        def progress(downloaded, total):
            token["cancelled"] = True

        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(CancelledError):
                client.download(entry, tmp, progress_cb=progress, cancel_token=token)
            leftovers = os.listdir(tmp)
            self.assertEqual(leftovers, [])

    def test_download_retries_transient_500_then_succeeds(self):
        calls = {"n": 0}

        def flaky(path, hit):
            calls["n"] += 1
            if calls["n"] == 1:
                return (500, {"Content-Type": "text/plain"}, b"boom")
            return (200, {"Content-Type": "application/epub+zip"}, FAKE_EPUB)

        routes = {"/dl/flaky.epub": flaky}
        self._server, _t, base = _start_server(routes)
        client = OpdsClient(timeout=5, max_retries=2)
        entry = {
            "id": "flaky",
            "title": "Flaky Book",
            "acquisition_url": base + "/dl/flaky.epub",
            "acquisition_type": "application/epub+zip",
            "format": "epub",
        }
        with tempfile.TemporaryDirectory() as tmp:
            out = client.download(entry, tmp)
            self.assertTrue(os.path.isfile(out))
        self.assertEqual(calls["n"], 2)

    def test_download_rejects_unsupported_content_type(self):
        routes = {
            "/dl/page": (
                200,
                {"Content-Type": "text/html"},
                b"<html><body>login wall</body></html>",
            )
        }
        self._server, _t, base = _start_server(routes)
        client = OpdsClient(timeout=5)
        entry = {
            "id": "html",
            "title": "HTML Page",
            "acquisition_url": base + "/dl/page",
            "acquisition_type": "text/html",
            "format": "unknown",
        }
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(UnsupportedContentError):
                client.download(entry, tmp)

    def test_download_rejects_oversize_via_content_length(self):
        routes = {
            "/dl/huge.epub": (
                200,
                {"Content-Type": "application/epub+zip"},
                FAKE_EPUB,
            )
        }
        self._server, _t, base = _start_server(routes)
        client = OpdsClient(timeout=5, max_download_bytes=10)
        entry = {
            "id": "huge",
            "title": "Huge Book",
            "acquisition_url": base + "/dl/huge.epub",
            "acquisition_type": "application/epub+zip",
            "format": "epub",
        }
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(UnsupportedContentError):
                client.download(entry, tmp)

    def test_sanitize_filename_blocks_traversal(self):
        nasty = "../../etc/passwd"
        safe = OpdsClient.sanitize_filename(nasty)
        self.assertNotIn("/", safe)
        self.assertNotIn("\\", safe)
        self.assertNotEqual(safe, "..")
        entry = {
            "id": "evil",
            "title": "../../../evil book <>:\"|?",
            "acquisition_url": "http://127.0.0.1:9/dl/evil.epub",
            "acquisition_type": "application/epub+zip",
            "format": "epub",
        }
        routes = {
            "/dl/evil.epub": (
                200,
                {"Content-Type": "application/epub+zip"},
                FAKE_EPUB,
            )
        }
        self._server, _t, base = _start_server(routes)
        entry["acquisition_url"] = base + "/dl/evil.epub"
        client = OpdsClient(timeout=5)
        with tempfile.TemporaryDirectory() as tmp:
            out = client.download(entry, tmp)
            self.assertTrue(os.path.abspath(out).startswith(os.path.abspath(tmp)))
            self.assertTrue(out.endswith(".epub"))
            self.assertNotIn("..", os.path.basename(out))

    def test_download_offline_raises_network_error(self):
        client = OpdsClient(timeout=2)
        entry = {
            "id": "x",
            "title": "X",
            "acquisition_url": "http://127.0.0.1:9/dl/x.epub",
            "acquisition_type": "application/epub+zip",
            "format": "epub",
        }
        with mock.patch.object(
            urllib.request, "urlopen", side_effect=urllib.error.URLError("offline")
        ):
            with tempfile.TemporaryDirectory() as tmp:
                with self.assertRaises(NetworkError):
                    client.download(entry, tmp)


class TestCatalogManager(unittest.TestCase):
    def test_defaults_include_gutenberg_and_standardebooks(self):
        mgr = CatalogManager(store={})
        feeds = mgr.list_feeds()
        urls = [f["url"] for f in feeds]
        self.assertIn(GUTENBERG_OPDS_URL, urls)
        self.assertIn(STANDARDEBOOKS_OPDS_URL, urls)

    def test_add_remove_and_persist_custom(self):
        store = {}
        mgr = CatalogManager(store=store)
        self.assertEqual(mgr.list_custom(), [])
        record = mgr.add_feed("https://example.org/opds", "Example Catalog")
        self.assertEqual(record["url"], "https://example.org/opds")
        self.assertEqual(len(mgr.list_custom()), 1)
        # Persisted via the injected dict store: a new manager sees it.
        mgr2 = CatalogManager(store=store)
        self.assertEqual(len(mgr2.list_custom()), 1)
        self.assertEqual(mgr2.list_custom()[0]["url"], "https://example.org/opds")
        self.assertTrue(mgr2.remove_feed(record["id"]))
        self.assertEqual(mgr2.list_custom(), [])
        self.assertFalse(mgr2.remove_feed(record["id"]))

    def test_add_rejects_invalid_and_duplicate(self):
        mgr = CatalogManager(store={})
        with self.assertRaises(ValueError):
            mgr.add_feed("not-a-url")
        with self.assertRaises(ValueError):
            mgr.add_feed("ftp://example.org/feed")
        mgr.add_feed("https://example.org/opds2", "Dup")
        with self.assertRaises(ValueError):
            mgr.add_feed("https://example.org/opds2", "Dup again")
        # Default URLs cannot be re-added or removed.
        with self.assertRaises(ValueError):
            mgr.add_feed(GUTENBERG_OPDS_URL, "Gutenberg dup")
        self.assertFalse(mgr.remove_feed("gutenberg"))


if __name__ == "__main__":
    unittest.main()
