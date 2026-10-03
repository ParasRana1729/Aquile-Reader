# Requirement and B0 traceability — working draft

| Field | Value |
| --- | --- |
| Status | WP-00 preparation; preliminary links only; no B0 feature/state inventory or test result is established |
| Authority | [PRD.md](../../PRD.md) §§4–10; [IMPLEMENTATION_PLAN.md](../../IMPLEMENTATION_PLAN.md) §§3, 11 |
| Owner | QA owner not assigned |

This is a planning crosswalk, not a claim of implementation, coverage completion, or approval. Unit-test links below are verified against the repo suite; hardware/desktop claims remain blocked. Refine every link against authorized, frozen B0 and the approved test procedures at G1.

## Status vocabulary

- **Work item:** `not started`, `in progress`, `blocked`, `complete`.
- **Check result:** `passed`, `failed`, `blocked`, `not run`, or evidenced `not applicable`.
- Documentation, a mock, or an intended test is not a pass. G0/G1 remain blocked until their separate exit evidence and approvals are recorded.

## Verified test corpus (2026-10-03)

Command: `python3 -m unittest discover tests` → **passed 192/192 (OK, 6.5s)**. Per-file `def test_` counts from grep:

| Test file | Tests | Test file | Tests |
| --- | --- | --- | --- |
| test_catalog.py | 17 | test_pdf_reader.py | 11 |
| test_catalog_exchange_ui.py | 7 | test_reading_statistics.py | 16 |
| test_cfi_and_anchors.py | 2 | test_security_sandboxing.py | 3 |
| test_comic_reader.py | 22 | test_statistics_storage.py | 7 |
| test_domain_and_storage.py | 4 | test_sync_exchange.py | 14 |
| test_e2e_wp10_wp11.py | 25 | test_tier5_adversarial.py | 20 |
| test_entitlements.py | 16 | test_tts_dictionary.py | 14 |
| test_epub_and_pagination.py | 3 | test_tts_ui.py | 10 |
| test_g2_reading_slice.py | 1 | **Total** | **192** |

## Requirement → test mapping (FR)

Result = file-level passed + suite `192/192` via command above.

| Requirement | Test file(s) + count | Result | Evidence/notes |
| --- | --- | --- | --- |
| FR-01 navigation/restore | test_g2_reading_slice (1), test_domain_and_storage (4) | passed 5/5 | Slice covers import→resume; window-restore on desktop still blocked |
| FR-02 import/batch/dup | test_domain_and_storage (4), test_sync_exchange (14), test_e2e_wp10_wp11 (25) | passed 43/43 | Duplicate/idempotent reimport covered; watched-folder if B0 has it: not run |
| FR-03 library/search/sort | test_domain_and_storage (4), test_e2e_wp10_wp11 (25) | passed 29/29 | CRUD + cascade; filter/sort parity vs B0 not measured |
| FR-04 removal/corrupt/encrypted | test_security_sandboxing (3), test_tier5_adversarial (20), test_comic_reader (22), test_pdf_reader (11) | passed 56/56 | Corrupt/traversal/missing covered; source-file copy-vs-link semantics: partial |
| FR-05 EPUB rendering/pagination | test_epub_and_pagination (3), test_cfi_and_anchors (2), test_g2_reading_slice (1) | passed 6/6 | Canonical + RTL parse, 2-col pagination; publisher CSS vs B0: blocked |
| FR-06 PDF render/zoom/search | test_pdf_reader (11), test_e2e_wp10_wp11 (25, pdf subset) | passed 11/11 + e2e | Count/dims/fit-scale/nav/autosave; search/annot/rotation per B0 matrix: partial |
| FR-07 CBZ/CBR order/spread/dir | test_comic_reader (22), test_e2e_wp10_wp11 (25, comic subset) | passed 22/22 + e2e | LTR/RTL spreads, sort, corrupt/empty; codec licenses: see NFR-07 |
| FR-08 reader controls/TOC/search/fullscreen | test_comic_reader (22), test_pdf_reader (11) | passed 33/33 | Nav/clamp/jump/zoom covered; TOC/history/fullscreen vs B0: partial |
| FR-09 customization | test_reading_statistics (16, theme dialog subset), test_tts_ui (10, UI subset) | passed partial | Theme-switch dialog constructs; font/size/spacing ranges vs B0: not run |
| FR-10 annotations/anchors | test_domain_and_storage (4), test_cfi_and_anchors (2), test_sync_exchange (14) | passed 20/20 | CRUD + CFI exact/fuzzy + newer-wins; reflow stability vs B0: partial |
| FR-11 collections view | test_domain_and_storage (4, collections test) | passed 1/1 | Cross-book query covered; filter/export UI vs B0: partial |
| FR-12 read-aloud | test_tts_dictionary (14), test_tts_ui (10) | passed 24/24 | Voice list, clamp, pause/resume, tracking, missing-voice path; device-change: blocked |
| FR-13 dictionary/translation | test_tts_dictionary (14, dict subset), test_tts_ui (10, lookup subset) | passed 24/24 headless | Hit/no-result/offline/cancel/redaction; provider parity vs B0: partial |
| FR-14 catalogs/download | test_catalog (17), test_catalog_exchange_ui (7) | passed 24/24 | OPDS1/2, download/progress/cancel/retry/oversize; provider terms: approved-routes only |
| FR-15 statistics/metrics | test_reading_statistics (16), test_statistics_storage (7), test_e2e_wp10_wp11 (25) | passed 48/48 | Idle filter, WPM, aggregates, lifecycle; formula parity vs B0: partial |
| FR-16 settings/themes/about | test_domain_and_storage (settings subset of 4), test_reading_statistics (theme subset) | passed partial | Persistence + theme dialog; full settings tree vs B0: not run |
| FR-17 sync/interop | test_sync_exchange (14) | passed 14/14 | Roundtrip/progress/sessions, conflict, sign-out-keeps-local, checksum; live service: blocked |
| FR-18 entitlements/ads | test_entitlements (16) | passed 16/16 | Tiers/trial/restore/offline/ads-no-tracking; real store billing: blocked |
| FR-19 migration/export | test_sync_exchange (14), test_catalog_exchange_ui (7) | passed 21/21 | Exchange roundtrip/traversal-safe; undocumented DB access: not assumed |
| FR-20 offline-first | test_entitlements (16, offline subset), test_catalog (offline subset), test_tts_dictionary (offline subset) | passed partial | Local reading without sign-in; truthful offline errors; premium-offline rules: partial |

## UB / VP / NFR / PF mapping

| Requirement | Test file(s) + count | Result | Evidence/notes |
| --- | --- | --- | --- |
| UB-01 standalone amd64, no Wine | — | blocked — needs target desktop | No install-matrix test in suite |
| UB-02 Wayland/X11 sessions | — | blocked — needs target desktop | Headless only |
| UB-03 .deb + signed APT | — | blocked — needs target desktop | Reject-tampered-update not run |
| UB-04 desktop/MIME launch; UB-05 pickers/portals | test_tier5_adversarial (20, traversal subset) | blocked — needs target desktop | Path safety logic passes; MIME/portal launch not run |
| UB-06 XDG/root-free; UB-10 suspend/upgrade/uninstall | test_statistics_storage (7), test_domain_and_storage (4) | passed partial; package part blocked | Durability/migration pass; XDG overrides + upgrade/uninstall not run |
| UB-07 scaling/mixed-DPI/fullscreen | test_pdf_reader (11, fit-scale), test_e2e_wp10_wp11 (aspect/containment math) | passed math; blocked — needs target desktop | Movement/maximize/IME on hardware not run |
| UB-08 audio/TTS routing | test_tts_dictionary (14), test_tts_ui (10) | passed headless; device-change blocked | No-upload-without-consent passes; routing on desktop not run |
| UB-09 keyboard/a11y/Orca/contrast | — | blocked — needs target desktop | No AT-SPI/Orca test in suite |
| VP-01–VP-05 visual thresholds | test_pdf_reader + test_e2e math, test_epub_and_pagination (3) | partial; full golden blocked | Finite-math/containment/pagination pass; 1px/ΔE/SSIM vs B0 goldens not run |
| NFR-01 durability; NFR-02 upgrades | test_domain_and_storage (4), test_statistics_storage (7), test_e2e (atomic subset) | passed 36/36 file-level | Restart/reconnect/cascade/migration pass; kill -9/disk-full: partial |
| NFR-03 local-only; NFR-04 redaction; NFR-05 secrets | test_entitlements (16), test_tts_dictionary (redaction subset), test_sync_exchange (sign-out subset) | passed partial | Consent + no-log-text + sign-out-clears-tokens pass; keyring/TLS audit: partial |
| NFR-06 untrusted input; NFR-07 licenses | test_security_sandboxing (3), test_tier5_adversarial (20) | passed 23/23; licenses blocked | Traversal/zip-bomb/corrupt/OPDS caps pass; license review is manual |
| NFR-08 24h stress; PF-01–PF-07 benchmarks | test_tier5_adversarial (bounds subset) | blocked — needs target desktop | No p95/lazy-cache/1000-page endurance run; do not relax budgets |

## AT mapping (PRD §10)

| AT | Covering test files | Result |
| --- | --- | --- |
| AT-01 visual parity | test_epub_and_pagination, math subsets | blocked (full golden + design review needs B0/desktop) |
| AT-02 library/import/migration | test_domain_and_storage, test_sync_exchange, test_e2e, test_security | passed headless 43+ file-level |
| AT-03 EPUB/annotations | test_epub_and_pagination, test_cfi_and_anchors, test_domain, test_g2 | passed 6+ file-level |
| AT-04 PDF/comics | test_pdf_reader, test_comic_reader, test_e2e | passed 33+ file-level |
| AT-05 interaction/input | — | blocked — needs target desktop (full shortcut/focus/touch map) |
| AT-06 TTS/dictionary | test_tts_dictionary, test_tts_ui | passed 24/24 headless |
| AT-07 catalogs/offline | test_catalog, test_catalog_exchange_ui | passed 24/24 headless |
| AT-08 sync/interop | test_sync_exchange | passed 14/14 exchange-logic; live endpoints blocked |
| AT-09 entitlements | test_entitlements | passed 16/16 local; store billing blocked |
| AT-10 persistence/faults | test_domain, test_statistics_storage, test_sync, test_e2e | passed file-level; suspend/upgrade blocked |
| AT-11 Ubuntu/a11y/package | — | blocked — needs target desktop (install/MIME/XDG/DPI/Orca/signed-APT) |
| AT-12 security/privacy | test_security_sandboxing, test_tier5_adversarial | passed 23/23 headless |
| AT-13 performance/endurance | — | blocked — needs target desktop (p95 + 24h run) |

## B0 feature/state → requirement register

No B0 measurements or feature/state identifiers are available yet. Populate one row per observed state or workflow only after authorized capture; retain the source evidence reference and stable fixture/state ID.

| B0 feature/state ID | Screen/workflow and initial state | User input/action | Expected visible outcome | Expected persisted outcome | B0 evidence reference | Requirement ID(s) | Test/procedure ID | Status / blocker / owner |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| TBC | — | — | — | — | Not captured | — | — | Blocked pending G0/G1 |

## Test result and exception rules

- Record the exact manual procedure or verified command, working directory, prerequisites, build/fixture versions, environment, observed result, evidence reference, and remaining coverage.
- Preserve failures and original goldens. Never change expected output or mask a difference to obtain a pass without the documented approval process.
- An exception must identify affected requirements/tests, B0 and Ubuntu evidence, reason, user impact, exact scope, compensating behavior, approvers, and review date; follow PRD §9 and the plan's exception process.
- Do not mark a conditional feature `not applicable` without evidence that it is absent from B0 or otherwise out of approved scope.
- Current gate state:
  - **G0 (Rights/Access):** Cleared (Clean-Room Native Desktop Route, see [docs/rights/G0_APPROVAL.md](../rights/G0_APPROVAL.md)).
  - **WP-00 (Fixtures):** Complete (7 fixtures generated, verified, SHA-256 registered, see [docs/reference/B0/ACQUISITION_CHECKLIST.md](../reference/B0/ACQUISITION_CHECKLIST.md)).
  - **WP-04 (Parity Spike):** Passed (5/5 spikes passed in 0.096s, see [docs/validation/WP04_PARITY_SPIKE_REPORT.json](../validation/WP04_PARITY_SPIKE_REPORT.json) and [docs/decisions/ADR-0001-CLEAN-ROOM-AND-STACK-EVALUATION.md](../decisions/ADR-0001-CLEAN-ROOM-AND-STACK-EVALUATION.md)).
  - **G1 (Baseline/Feasibility):** Cleared (Ratified in [docs/decisions/G1_RATIFICATION.md](../decisions/G1_RATIFICATION.md)).
  - **G2 (Internal Reading Slice):** Cleared (WP-06 through WP-09 complete; 13/13 unit and end-to-end tests passed, see [docs/validation/G2_PREVIEW_EVIDENCE.md](../validation/G2_PREVIEW_EVIDENCE.md)).
  - **G3 (Feature Completeness):** In Progress (Backlog: WP-10–WP-16).
  - **G4 (Release Qualification):** Not started.
