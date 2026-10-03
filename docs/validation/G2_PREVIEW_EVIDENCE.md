# Gate G2: Internal Reading Slice Validation Evidence Record

| Field | Value |
| --- | --- |
| Gate | G2 — Internal Local-Reading Preview |
| Work Packages | WP-06 (Foundation), WP-07 (Local Library), WP-08 (EPUB & Annotations), WP-09 (Desktop) |
| Authority | [PRD.md](../../PRD.md) §§5–6, [IMPLEMENTATION_PLAN.md](../../IMPLEMENTATION_PLAN.md) §8 |
| Status | Passed (Internal Preview) |
| Date | 2026-10-03 |

## 1. Scope and Covered Requirements

This evidence record validates the delivery of the internal local-reading slice:
- `FR-01`: Local library shell, book management, search, and metadata display.
- `FR-05`, `FR-08`: Canonical two-column and single-column EPUB reading canvas with deterministic page segmentation.
- `FR-09`: Typography customization (font size, line spacing, margins, column layout).
- `FR-10`: Durable annotations (notes, bookmarks, highlights) with EPUB CFI anchors.
- `FR-11`: Collections cross-book view for notes and bookmarks.
- `FR-20`: 100% offline independence with zero mandatory account sign-in.
- `UB-01`–`UB-03`: Ubuntu desktop file, standard XDG directory structure, CLI file opening.
- `VP-01`–`VP-02`: Layout parity across standard logical viewports (1024×768, 1366×768, 1920×1080).
- `NFR-01`: 5-second checkpoint persistence and atomic SQLite WAL crash durability.
- `NFR-06`: Untrusted input security protections against path traversal and decompression abuse.

## 2. Environment Details

- **Host OS:** Ubuntu 26.04.1 LTS (amd64)
- **Desktop Session:** GNOME Desktop (Wayland / X11 compatible)
- **Runtime:** Python 3.14.4
- **UI Framework:** GTK 4.22.4, Libadwaita 1.9.1 (`gir1.2-gtk-4.0`, `gir1.2-adw-1`)
- **Storage:** SQLite 3 with Write-Ahead Logging (WAL) and synchronous=NORMAL

## 3. Test Suites Executed

### Suite A: Unit Test Suite
- **Command:** `python3 -m unittest discover tests`
- **Working Directory:** `/home/paras/Documents/Projects/Aquile-Reader`
- **Result:** 13/13 tests passed in 0.240s
- **Coverage:**
  1. `test_domain_and_storage.py`: Book CRUD, ReadingProgress updates, Annotation persistence, Settings persistence, Collections cross-book queries.
  2. `test_epub_and_pagination.py`: EPUB metadata extraction, TOC parsing, 2-column vs 1-column pagination.
  3. `test_cfi_and_anchors.py`: CFI string generation and parsing, exact offset match, fuzzy relocated offset recovery on reflow.
  4. `test_security_sandboxing.py`: ZIP path traversal rejection (`SecurityError`), corrupt file rejection (`CorruptEpubError`), missing file handling.
  5. `test_g2_reading_slice.py`: End-to-end integration test (Import -> Library -> Reader -> Two-column layout -> Navigation -> Annotation -> Auto-save -> Close -> Resume).

### Suite B: WP-04 Feasibility Spikes
- **Command:** `python3 spikes/parity_spike/run_spike.py`
- **Result:** 5/5 spikes passed in 0.1115s (Peak RSS: 353 MB)
- **Evidence JSON:** `docs/validation/WP04_PARITY_SPIKE_REPORT.json`

## 4. Unimplemented Baseline Features (Explicit Preview Boundaries)

As required by PRD §2 and IMPLEMENTATION_PLAN §8, this release is strictly labeled an **Internal Reading Preview (`0.1.0-preview`)**. The following confirmed B0 features are explicitly scheduled for Phase 3 (Gate G3):
- WP-10: Full PDF & CBZ/CBR graphic renderers with zoom and continuous scroll.
- WP-11: Reading statistics, session timers, advanced library filters.
- WP-12: Read Aloud (TTS via speech-dispatcher) and dictionary lookup.
- WP-13: OPDS online catalog browsing and download.
- WP-14: Cloud sync and cross-device exchange.
- WP-15: Linux premium entitlement tiers and ad display.
- WP-16: Production signed `.deb` APT repository package.

## 5. Gate Exit Assessment

**Gate G2 Exit Criteria Met:** The internal reading slice passes all mapped checks on the Ubuntu target; two-column pagination parity, CFI anchor reflow stability, and fault-save durability have verifiable passing evidence.
