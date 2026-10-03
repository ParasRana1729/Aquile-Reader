"""Static security/privacy regression audit (NFR-03 … NFR-06).

Re-greps ``src/`` on every run and fails on regression. Evidence and
per-NFR verdicts live in ``docs/validation/SECURITY_AUDIT.md``.
"""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"


def iter_py_files():
    return sorted(SRC.rglob("*.py"))


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


class TestStaticSecurityAudit(unittest.TestCase):
    def test_no_pickle(self):
        """No pickle/marshal deserialisation anywhere in src/."""
        offenders = []
        for path in iter_py_files():
            text = read_text(path)
            if re.search(r"(?m)^\s*(import\s+pickle|from\s+pickle\s+import)", text):
                offenders.append(f"{path}: pickle import")
            if re.search(r"\bpickle\.(loads?|load|Unpickler)\b", text):
                offenders.append(f"{path}: pickle use")
            if re.search(r"(?m)^\s*(import\s+marshal|from\s+marshal\s+import)", text):
                offenders.append(f"{path}: marshal import")
            if re.search(r"\bmarshal\.(loads?|load)\b", text):
                offenders.append(f"{path}: marshal use")
            if re.search(r"\byaml\.load\s*\(", text):
                offenders.append(f"{path}: yaml.load use")
        self.assertEqual(offenders, [], f"deserialisation sinks found: {offenders}")

    def test_no_eval_or_exec_calls(self):
        """No bare eval(/exec( (sqlite executescript DDL is allowed)."""
        offenders = []
        for path in iter_py_files():
            for i, line in enumerate(read_text(path).splitlines(), 1):
                if re.search(r"(?<![\w.])eval\s*\(", line):
                    offenders.append(f"{path}:{i}: {line.strip()}")
                if re.search(r"(?<![\w.])exec\s*\(", line):
                    offenders.append(f"{path}:{i}: {line.strip()}")
        self.assertEqual(offenders, [], f"eval/exec calls found: {offenders}")

    def test_no_shell_true_or_os_system(self):
        """No shell=True and no os.system (subprocess list-args only)."""
        offenders = []
        for path in iter_py_files():
            for i, line in enumerate(read_text(path).splitlines(), 1):
                if re.search(r"\bshell\s*=\s*True\b", line):
                    offenders.append(f"{path}:{i}: {line.strip()}")
                if re.search(r"\bos\.system\s*\(", line):
                    offenders.append(f"{path}:{i}: {line.strip()}")
        self.assertEqual(offenders, [], f"shell execution found: {offenders}")

    def test_no_hardcoded_secrets(self):
        """No hardcoded api_key/password/passwd/client_secret assignments in src/."""
        pattern = re.compile(
            r"(?i)\b(api_key|apikey|password|passwd|client_secret)\s*[:=]\s*[\"'][^\"']+[\"']"
        )
        offenders = []
        for path in iter_py_files():
            for i, line in enumerate(read_text(path).splitlines(), 1):
                if pattern.search(line):
                    offenders.append(f"{path}:{i}: {line.strip()}")
        self.assertEqual(offenders, [], f"hardcoded secrets found: {offenders}")

    def test_traversal_guards_present(self):
        """Traversal guards present in comic_reader + exchange (and EPUB/OPDS)."""
        comic = read_text(SRC / "aquile/reader/comic_reader.py")
        self.assertIn("_is_path_traversal", comic)
        self.assertIn("ComicSecurityError", comic)
        self.assertRegex(comic, r"Path traversal detected in archive entry")

        exchange = read_text(SRC / "aquile/sync/exchange.py")
        self.assertIn("_is_safe_name", exchange)
        self.assertIn("UnsafeBundleError", exchange)
        self.assertRegex(exchange, r"if not _is_safe_name\(info\.filename\)")

        epub = read_text(SRC / "aquile/reader/epub_parser.py")
        self.assertIn("_validate_archive", epub)
        self.assertIn("normpath", epub)

        opds = read_text(SRC / "aquile/catalog/opds_client.py")
        self.assertIn("sanitize_filename", opds)
        self.assertIn("abspath", opds)
        self.assertRegex(opds, r"Unsafe download filename escapes destination")

    def test_network_timeouts_present(self):
        """Every urlopen in catalog/dictionary carries an explicit timeout."""
        for rel, minimum in (
            ("aquile/catalog/opds_client.py", 2),
            ("aquile/reader/dictionary.py", 1),
        ):
            text = read_text(SRC / rel)
            total = len(re.findall(r"urlopen\s*\(", text))
            with_timeout = len(
                re.findall(r"urlopen\s*\(.*?timeout\s*=", text, re.DOTALL)
            )
            self.assertGreaterEqual(total, minimum, f"{rel}: expected urlopen calls")
            self.assertEqual(
                with_timeout,
                total,
                f"{rel}: every urlopen must pass timeout "
                f"(total={total}, with_timeout={with_timeout})",
            )

    def test_tokenstore_used_no_creds_in_settings(self):
        """Credentials via TokenStore only; SettingsRepository holds UI prefs."""
        state = read_text(SRC / "aquile/sync/sync_state.py")
        for symbol in (
            "class TokenStore",
            "class InMemoryTokenStore",
            "class SecretServiceTokenStore",
            "def sign_out",
            "token_store.clear()",
        ):
            self.assertIn(symbol, state, f"sync_state.py missing {symbol!r}")
        self.assertIn("secretstorage", state)

        repo = read_text(SRC / "aquile/storage/repository.py")
        start = repo.index("class SettingsRepository")
        tail = repo[start:]
        nxt = tail.find("\nclass ", 1)
        block = tail[:nxt] if nxt != -1 else tail
        for secret_word in ("token", "password", "secret", "credential"):
            self.assertNotIn(
                secret_word,
                block.lower(),
                f"SettingsRepository must not persist {secret_word!r}",
            )
        for pref_key in ("theme", "font_family", "font_size"):
            self.assertIn(pref_key, block)

    def test_logging_redaction(self):
        """No note_text/text_content inside logging/print calls; lengths only."""
        offenders = []
        for path in iter_py_files():
            for i, line in enumerate(read_text(path).splitlines(), 1):
                if re.search(r"\blogger?\.|\blogging\.|\bprint\s*\(", line):
                    if "note_text" in line or "text_content" in line:
                        offenders.append(f"{path}:{i}: {line.strip()}")
        self.assertEqual(offenders, [], f"sensitive data in logging: {offenders}")

        tts = read_text(SRC / "aquile/reader/tts_engine.py")
        self.assertRegex(tts, r"chars=%d words=%d")
        dictionary = read_text(SRC / "aquile/reader/dictionary.py")
        self.assertRegex(dictionary, r"word_len=%d")

    def test_subprocess_list_args_only(self):
        """All subprocess.run calls use list argv (absolute binaries, no shell)."""
        for rel in ("aquile/reader/pdf_reader.py", "aquile/reader/tts_engine.py"):
            text = read_text(SRC / rel)
            runs = list(re.finditer(r"subprocess\.run\s*\(", text))
            self.assertGreater(len(runs), 0, f"{rel}: expected subprocess.run")
            for match in runs:
                window = text[match.end(): match.end() + 200]
                # Either an inline list literal or a `cmd` variable that is
                # assigned a list literal elsewhere in the same file.
                if re.match(r"^\s*\[", window):
                    continue
                if re.match(r"^\s*cmd\s*,", window):
                    self.assertRegex(
                        text,
                        r"(?m)^\s*cmd\s*=\s*\[",
                        f"{rel}: `cmd` argv must be a list literal",
                    )
                    continue
                if re.match(r"^\s*\[?path\s*\]\s*\+", window) or re.match(
                    r"^\s*\[path\]", window
                ):
                    continue
                self.fail(
                    f"{rel}: subprocess.run must take list argv, "
                    f"got: {window[:80]!r}"
                )
        pdf = read_text(SRC / "aquile/reader/pdf_reader.py")
        self.assertIn('"/usr/bin/pdfinfo"', pdf)
        self.assertIn('"/usr/bin/pdftoppm"', pdf)

    def test_network_stack_is_urllib_only(self):
        """Network I/O is stdlib urllib (request) in catalog/dictionary only."""
        offenders = []
        request_users = set()
        for path in iter_py_files():
            text = read_text(path)
            if re.search(r"(?m)^\s*(import\s+requests|from\s+requests\b)", text):
                offenders.append(f"{path}: requests import")
            if re.search(r"(?m)^\s*(import\s+http\.client|from\s+http\.client\b)", text):
                offenders.append(f"{path}: http.client import")
            if re.search(r"(?m)^\s*(import\s+socket\b|from\s+socket\b)", text):
                offenders.append(f"{path}: socket import")
            if "urllib.request" in text:
                request_users.add(path.relative_to(SRC).as_posix())
        self.assertEqual(offenders, [], f"non-urllib network stack: {offenders}")
        self.assertEqual(
            request_users,
            {"aquile/catalog/opds_client.py", "aquile/reader/dictionary.py"},
            f"urllib.request must stay confined, got: {sorted(request_users)}",
        )


if __name__ == "__main__":
    unittest.main()
