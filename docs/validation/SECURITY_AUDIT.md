# Security / Privacy Audit — Static Review (NFR-03 … NFR-07)

Date: 2026-10-03 (UTC) · Scope: `src/` static review only (no execution of network calls).
Method: `grep` over `src/` for credentials, logging, subprocess, pickle/eval/exec,
path traversal, and network calls; manual read of flagged files for verdicts.
Regression guard: `tests/test_security_audit.py` (re-greps the tree on each run).

## Summary verdicts

| NFR | Verdict | One-line basis |
|-----|---------|----------------|
| NFR-03 local-only | PASS | No telemetry/account; all network is explicit user-invoked (catalog discover/download, dictionary `allow_online`, TTS cloud opt-in). |
| NFR-04 disclosure + redaction | PASS | Destinations disclosed in module docstrings; logs carry only lengths/langs/counts, never credentials, paths, note content, or book text. |
| NFR-05 credential store + TLS | PASS | Tokens only via `sync/sync_state.py` `TokenStore` (Secret Service else memory); `SettingsRepository` stores theme/fonts only; TLS is stdlib `urllib` default (no `CERT_NONE`/`verify=False`); sign-out clears tokens. Minor note: plain `http` is accepted only for user-supplied custom OPDS feeds (defaults are `https`). |
| NFR-06 untrusted-input guards | PASS | Traversal blocks + size caps + filename sanitisation + dest confinement present in EPUB/comic/exchange/OPDS paths (refs below). |
| NFR-07 licenses | GAP | `src/aquile/app.py:59` declares `Gtk.License.MIT` but repo ships no `LICENSE`/`COPYING`/`NOTICE` text and no `debian/copyright`; dependency/security maintenance plan is still a future `docs/release/` item per `IMPLEMENTATION_PLAN.md`. No unlicensed-asset use was found in code; the gap is missing notice/plan artifacts. |

Violations found in `src/`: **none** (no fix required under the new-files-only rule).
Documentation gap: **NFR-07** (see above) — needs a `LICENSE` text, `debian/copyright`,
and the planned `docs/release/` notices/maintenance plan before release.

## Evidence

### 1. Credentials — stored only via `TokenStore`, never plaintext prefs

- `src/aquile/sync/sync_state.py:15-19` — docstring: Secret Service via `secretstorage`
  when available, else memory; "no plaintext secret is written to app preferences".
- `src/aquile/sync/sync_state.py:35-49` — `class TokenStore(abc.ABC)` with
  `get_token` / `set_token` / `clear` (explicit credential-store interface, NFR-05).
- `src/aquile/sync/sync_state.py:52-65` — `InMemoryTokenStore` (process memory; tests/safe fallback).
- `src/aquile/sync/sync_state.py:68-137` — `SecretServiceTokenStore` (freedesktop Secret
  Service, memory fallback; `get_token` at `:88-102`, `set_token` at `:104-121`,
  `clear` at `:123-137`).
- `src/aquile/sync/sync_state.py:187-197` — `sign_in_local` stores via
  `token_store.set_token`; `sign_out` calls `token_store.clear()` and drops
  `account_id`/`signed_in` while retaining local books/annotations.
- `src/aquile/ui/exchange_dialog.py:40-48` — default `InMemoryTokenStore`; `:203-204`
  sign-out docstring + `self.sync_state.sign_out(self.token_store)`.
- `src/aquile/storage/repository.py:136-164` — `SettingsRepository.load/save` persists
  only `theme`, `font_family`, `font_size`, `line_height`, `columns`, `margin_percent`.
  No `token`/`password`/`secret`/`credential` identifier appears in this file.
- Grep `credential|password|token|secret|api_key|passwd` over `src/` returns only the
  `TokenStore` machinery above plus OPDS *cancel-token* plumbing
  (`src/aquile/catalog/opds_client.py:42,81-103,486-686`, `src/aquile/ui/catalog_dialog.py:72,395-425`)
  and the comic natural-sort local `token` (`src/aquile/reader/comic_reader.py:233`)
  — none of which are stored secrets. No `api_key = "..."` / `password = "..."`
  hardcoded assignment exists.

### 2. Logging / print redaction — no book text, paths, or notes in diagnostics

- `src/aquile/reader/tts_engine.py:424-430` — `speak()` logs only
  `"tts speak started: chars=%d words=%d rate=%.2f cloud=%s"` (lengths, not text).
  All other `logger.debug` lines log counts/langs/engines/rates/indices
  (`:257`, `:267`, `:278`, `:314`, `:331`, `:351`, `:436`, `:447`, `:461-462`,
  `:479-480`, `:498-499`, `:541`). The utterance `content` is passed only to the
  audio backend `play(content, voice, rate)` at `:434`, never to the logger.
- `src/aquile/reader/dictionary.py:239-244` — lookup logs only
  `"word_len=%d lang=%s online=%s"`; `:246`, `:252-253`, `:264`, `:272`, `:287-291`,
  `:300`, `:325`, `:338`, `:342-353`, `:366`, `:398`, `:402` log `lang`/`defs`/
  `error type`/`source` only. Queried text is never logged (docstring `:198-199`).
- `src/aquile/storage/database.py:49,54,103` — only schema-version messages
  (`"Migrating database …"`, `"Initializing schema …"`); no row contents.
- `src/aquile/ui/dictionary_dialog.py:104,217-245` and
  `src/aquile/ui/tts_controls.py:136-316` — log method names, `lang`, failure markers;
  no `note_text`/`text_content`/paths.
- Grep `logging|logger|print\(` confirms the only `print(`-style output in scope is
  absent from `src/` (matches are `logger.*` calls listed above). A targeted scan for
  `note_text`/`text_content` inside any logging call returns zero hits.

### 3. Subprocess — list args only, no shell

- Grep `os\.system|subprocess|shell\s*=\s*True|pdftoppm` → only `subprocess` in two files,
  zero `os.system`, zero `shell=True`:
  - `src/aquile/reader/pdf_reader.py:19` (`import subprocess`) with call sites
    `:188-193` (`["/usr/bin/pdfinfo", self.file_path]`),
    `:262` (`["/usr/bin/pdfinfo", "-f", …, self.file_path]`),
    `:353` (`["/usr/bin/pdftoppm", "-png", …, self.file_path]`) — all absolute-binary
    list argv, `capture_output=True`, no `shell`.
  - `src/aquile/reader/tts_engine.py:11,124-140` — `_probe_command(binary, args)`
    resolves via `shutil.which(binary)` then `subprocess.run([path] + args,
    capture_output=True, text=True, timeout=2.0)`; callers pass static arg lists
    (`["--voices"]`, `["--list-synthesis-voices"]`, `["-L"]` at `:252-262`).
    Failures collapse to `None` (offline stub voices), no shell.
- The single `marshal`-mention in `src/` is an English comment
  (`src/aquile/ui/tts_controls.py:320` "marshals the label update") — not the
  `marshal` module. No `pickle` / bare `eval(` / `exec(` anywhere in `src/`
  (the only `exec*` hit is sqlite `conn.executescript("""CREATE TABLE …""")` with
  static DDL in `src/aquile/storage/database.py:55,104`).

### 4. Path traversal / decompression / injection guards (NFR-06)

- EPUB (`src/aquile/reader/epub_parser.py`):
  - `:20-22` `MAX_FILE_SIZE = 50 MiB`, `MAX_TOTAL_SIZE = 250 MiB`.
  - `:36-47` `_validate_archive` rejects `normpath` starting with `..`, absolute
    names, `../` sequences, oversized entries/total.
  - XML via stdlib `xml.etree.ElementTree` (`:8,65,80,168`); no external-entity
    resolution; chapter HTML is stripped (`:138-150` removes `script`/`style`).
- Comics (`src/aquile/reader/comic_reader.py`):
  - `:95-105` `_is_path_traversal` (absolute, drive-letter, `..` segment).
  - `:109-111` caps: 5000 entries / 1 GiB total / 200 MiB per entry.
  - `:128-137` zip path enforcement + entry/total caps; `:178-183` libarchive path
    enforcement + entry cap. No extraction to disk (in-memory `ZipFile.read`).
- Exchange bundles (`src/aquile/sync/exchange.py`):
  - `:46-47` `MAX_BUNDLE_UNCOMPRESSED_BYTES = 64 MiB`, `MAX_FILES_IN_BUNDLE = 16`.
  - `:78-96` `_is_safe_name` (absolute/drive/`..`/`~`/normpath-equality checks).
  - `:404-421` import enforces file count, total/entry size caps, `_is_safe_name`
    (traversal → `UnsafeBundleError`), manifest + per-file SHA-256 (`:439-446`),
    typed payload validation (`:455-462`); never claims upload (`:17-19`).
- OPDS downloads (`src/aquile/catalog/opds_client.py`):
  - `:126-128` `MAX_FEED_BYTES = 2 MiB`, `MAX_DOWNLOAD_BYTES = 200 MiB`.
  - `:411-452` `sanitize_filename` (basename, NUL/sep stripping, reserved names,
    length cap, `.epub`/`.pdf`-only extensions).
  - `:511-535` relative-URL join + scheme allowlist + `dest_abs` confinement
    (`final_path` must stay under `dest_dir`).
  - `:554-598`, `:600-723` size-capped streaming, partial-file cleanup, HTML-magic
    rejection (`:725-738`), content-type validation (`:454-479`).
- `open()` call sites are confined: `pdf_reader.py:202` (read own `file_path`),
  `exchange.py:105` (chunked hash read), `opds_client.py:570,684,727`
  (sanitised `final_path` / verified source). No `open()` joins an unsanitised
  `..` segment without a preceding guard.

### 5. Network — `urllib` only, every call carries a timeout

- `src/aquile/catalog/opds_client.py:24,30-32` — "All network I/O uses urllib (stdlib)
  only." Call sites: `:169-179` (`Request` + `urlopen(req, timeout=self.timeout)`
  in `_fetch_bytes`; default `timeout=10.0` at `:132,137`) and `:641-649`
  (`Request` + `urlopen(req, timeout=self.timeout)` in `_download_http_once`).
  No `requests` / `http.client` / raw `socket` imports.
- `src/aquile/reader/dictionary.py:11-13` — `urllib.parse/request/error` only;
  call site `:318-327` (`Request` with UA/Accept + `urlopen(request, timeout=timeout)`;
  default `DEFAULT_TIMEOUT = 5.0` at `:24`, plumbed via `:206-215,238,302-305`).
- `src/aquile/entitlements/tiers.py` and `src/aquile/entitlements/ads.py:1-16` —
  zero network I/O by construction (`ads.AdSlot.tracking_urls_fetched()` at
  `ads.py:112-115` returns `[]`).
- `src/aquile/sync/exchange.py`, `src/aquile/sync/sync_state.py` — local file exchange
  only; `SyncState.status()` never returns `"synced"`/`"uploaded"`
  (`sync_state.py:160-168`).
- TLS: all default/online endpoints are `https` (see table); `urllib` default SSL
  context is used — no `ssl._create_unverified_context`, `CERT_NONE`,
  `check_hostname=False`, or `verify=False` anywhere in `src/`.

## Network-destination table (NFR-04)

| Module | URL / host | Data sent | Consent gate |
|--------|-----------|-----------|--------------|
| `catalog/opds_client.py:160-213` `OpdsClient.discover` / `_fetch_bytes` | User-supplied OPDS feed URL, or defaults `https://www.gutenberg.org/ebooks.opds/` and `https://standardebooks.org/opds` (`catalog/catalog_manager.py:22-36`); redirects honoured via `geturl` | Plain HTTP `GET` for feed XML/JSON with `User-Agent: Aquile-Reader/0.1 (OPDS; +offline-first)` + `Accept` header. No credentials, annotations, note contents, local paths, or book text are uploaded (docstring `:8-14`) | Explicit user action (open/search catalog). `CatalogManager.add/remove/list` itself performs no I/O (`catalog_manager.py:4-15`). Custom URLs restricted to `http(s)` with netloc (`:121-128`); `OpdsClient` additionally allowlists `http/https/file` schemes (`opds_client.py:51,162-164,513-515`) |
| `catalog/opds_client.py:481-546,600-723` `OpdsClient.download*` | `acquisition_url` from the discovered feed entry (joined against feed URL; scheme re-validated) | Plain HTTP `GET` for the chosen EPUB/PDF artifact with `Accept: application/epub+zip, application/pdf, */*;q=0.8`. Saved under `dest_dir` with a sanitised name; content-type/size/HTML-magic validated | Explicit user download with progress/cancel token; offline reading never depends on it (docstring `:4-7`). `file://` acquisition URLs are copied locally via `_download_local_file` (`:548-598`), still size/type-checked |
| `reader/dictionary.py:304-327` `DictionaryService._fetch_online` | `https://{lang}.wiktionary.org/api/rest_v1/page/definition/{word}` (`lang` validated `^[a-z]{2,3}$` at `:312`) | `GET` with `User-Agent: Aquile-Reader/1.0 (Ubuntu; offline-first dictionary)` + `Accept: application/json`; URL path is `urllib.parse.quote(word)`. No annotation/note/book payload is sent | `allow_online=True` required (`lookup` `:221-228,270-273`); default is local-stub-only (`allow_online=False`), which sends nothing. Timeout + cooperative cancel token enforced |
| `reader/tts_engine.py:388-403` `TtsEngine.speak(use_cloud=…)` | None in this build (no cloud endpoint is contacted; synthesis is local `espeak-ng`/`spd-say` probes or stub voices) | N/A — utterance stays in-process (NullAudioBackend by default) | `use_cloud=True` without `set_cloud_consent(True)` raises `CloudVoiceConsentError` (`:402-403,37-41`); consent flag logged as boolean only (`:351`) |
| `sync/*`, `entitlements/*` | None (no host) | No bytes leave the machine: exchange bundles are local zip files; entitlement/ads state is local | Local-only by design (`sync_state.py:1-13`, `exchange.py:17-19`, `tiers.py:1-21`, `ads.py:1-16`) |

## Per-NFR verdicts (detail)

- **NFR-03 local-only — PASS.** Books/annotations/settings persist locally
  (SQLite via `storage/database.py`, `storage/repository.py`); ads are static
  placeholders (`entitlements/ads.py:78-115`); entitlements evaluate locally
  (`entitlements/tiers.py`); TTS/dictionary/catalog each default to offline and
  require explicit opt-in for any network step (see table). No background
  polling, telemetry import, or mandatory account exists in `src/`.
- **NFR-04 disclosure + redaction — PASS.** Destinations and sent-data documented
  in `opds_client.py:8-14`, `catalog_manager.py:8-10`, `dictionary.py:1-6,192-200`,
  `tts_engine.py:36-41,163-172,344-351`. Diagnostic output redacted as shown in
  §2 (lengths/langs/counts/error-type names only).
- **NFR-05 credential store + TLS — PASS.** Secret handling confined to
  `sync_state.py` `TokenStore` hierarchy with Secret Service-first semantics and
  memory fallback; preferences hold only UI settings. Authenticated TLS via stdlib
  defaults; no insecure-context override. Sign-out invalidates tokens
  (`sync_state.py:193-197`). Note (not a failure): custom OPDS feeds may use
  plain `http`, but only when the user explicitly registers such a URL; both
  shipped defaults are `https`.
- **NFR-06 untrusted-input guards — PASS.** Traversal, size-cap, filename, scheme,
  content-type, XML-entity (stdlib parser, no external resolution), and script-strip
  controls listed in §4 with `file:line` refs. Malicious-archive and bundle tests
  exist (`tests/test_security_sandboxing.py`, `tests/test_tier5_adversarial.py`,
  `tests/test_sync_exchange.py`, `tests/test_catalog.py`); the new static audit
  test pins the guards against regression.
- **NFR-07 licenses — GAP.** Missing shippable notices/plan (details in Summary).
  Recommend: add root `LICENSE` (matching `app.py:59` MIT declaration), add
  `debian/copyright`, and publish the `docs/release/` license-notice +
  dependency/security-maintenance plan already foreseen in
  `IMPLEMENTATION_PLAN.md:206,281` before claiming release readiness.

## Reproduction

```bash
# From the repository root:
grep -rn --include='*.py' -E 'credential|password|token|secret|api_key|passwd' src/ | head -n 100
grep -rn --include='*.py' -E 'os\.system|shell\s*=\s*True' src/; echo "expect: no hits"
grep -rn --include='*.py' -E 'pickle|eval\(|exec\(' src/; echo "expect: no hits (executescript DDL only)"
grep -rn --include='*.py' -E 'urllib|requests\.|http\.client|^import socket|from socket' src/
python3 -m unittest tests/test_security_audit.py -v
```
