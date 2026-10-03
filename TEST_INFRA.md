# Aquile Reader — E2E Test Infrastructure & Methodology (WP-10 & WP-11)

## 1. Executive Summary & Architecture

This document defines the comprehensive end-to-end (E2E) testing infrastructure, architecture, and verification methodology for **Work Package 10 (WP-10: PDF and Comic Book Graphic Readers)** and **Work Package 11 (WP-11: Reading Statistics and Session Insights)** in Aquile Reader for Ubuntu Linux.

The testing infrastructure guarantees:
1. **Opaque-Box Verification**: Tests validate public interface contracts and observable behavior (return values, database states, UI properties, file system artifacts) rather than private implementation details.
2. **Deterministic & Hermetic Execution**: Each test runs with isolated temporary environments (ephemeral SQLite databases, scoped test archives, and isolated memory surfaces) with no shared mutable state.
3. **Four-Tier Testing Pyramid**: Rigorous progression from isolated unit contracts up to complete multi-format reading lifecycles.
4. **Zero Regression Baseline**: Full preservation of all pre-existing test suites (13 unit and integration tests) and parity spike verifications.

---

## 2. Four-Tier Testing Methodology

```
+--------------------------------------------------------------------------+
|                       TIER 4: REAL-WORLD SCENARIOS                       |
|   Complete reading sessions, resume from last page, multi-format import  |
+--------------------------------------------------------------------------+
|                  TIER 3: CROSS-FEATURE COMBINATIONS                      |
|   Spread mode + Manga RTL, display adjustments + stats tracking, WAL DB  |
+--------------------------------------------------------------------------+
|                  TIER 2: BOUNDARY & CORNER CASES                         |
|   Empty archives, single page, zero duration, exact idle thresholds      |
+--------------------------------------------------------------------------+
|                    TIER 1: FEATURE COVERAGE                              |
|   Natural sort, spread pairing, PDF zoom/fit math, WPM, repo CRUD        |
+--------------------------------------------------------------------------+
```

### Tier 1: Feature Coverage (Isolated Functionality)
Tests each core component against the formal interface contracts defined in `PROJECT.md`:
- **Comic Engine (`ComicArchiveEngine`)**:
  - Image file discovery filtering (`.png`, `.jpg`, `.jpeg`, `.webp`, `.gif`) and noise rejection (`__MACOSX/`, `.txt`).
  - Natural alphanumeric sorting: verifying `page2` sorts strictly before `page10`.
  - Single-page spread generation (`[[0], [1], [2], ...]`).
  - Double-page spread pairing with isolated cover: `[[0], [1, 2], [3, 4], ...]`.
  - Western (LTR) vs Manga (RTL) spread ordering: verifying RTL inverts reading pairs to `[[0], [2, 1], [4, 3], ...]`.
- **PDF Engine (`PdfDocumentEngine`)**:
  - Page count inspection and verification against document catalog.
  - Page point dimension extraction (`width`, `height` in points from MediaBox).
  - Zoom & Fit mathematical calculations:
    - Fit-to-Width: $\text{scale} = \frac{\text{viewport\_width}}{\text{page\_width}}$.
    - Fit-to-Page: $\text{scale} = \min\left(\frac{\text{viewport\_width}}{\text{page\_width}}, \frac{\text{viewport\_height}}{\text{page\_height}}\right)$.
- **Reading Session Tracker (`ReadingSessionTracker`)**:
  - Session initialization, active duration accumulation across activity ticks.
  - Idle period filtering: threshold partitioning between active reading and idle pauses (120s threshold for text/EPUB/PDF, 60s threshold for comics).
  - Words read accumulation and words-per-minute (WPM) calculation:
    $$\text{WPM} = \frac{\text{words\_read}}{\text{active\_duration\_seconds} / 60.0}$$
    with session minimums ($\ge 10\text{s}$) and noise clamping ($\le 1200\text{ WPM}$).
- **Statistics Repository (`StatisticsRepository`)**:
  - CRUD operations on `ReadingSession` domain records in SQLite WAL database.
  - Book statistics aggregation (`total_reading_seconds`, `active_reading_seconds`, `total_sessions`, `average_wpm`).
  - Library-wide statistics aggregation across all catalogued books.

### Tier 2: Boundary & Corner Cases (Edge Conditions)
Tests extreme inputs, empty containers, and mathematical boundary limits:
- **Empty Comic Archives**: Valid ZIP archives containing zero image entries (must return 0 pages and empty spread list without crashing).
- **Single-Page Comic Archives**: Archives containing only a cover image (double spread must produce `[[0]]` with no phantom paired spread).
- **Odd Number of Pages**: Archives with an odd page count (e.g., 3 pages total: isolated cover `[[0]]` followed by `[[1, 2]]`; or 4 pages total: `[[0]]`, `[[1, 2]]`, `[[3]]`).
- **Zero-Duration Reading Sessions**: Sessions ended immediately ($0\text{s}$ duration, zero words) must record $0.0\text{ WPM}$ without division-by-zero errors.
- **Exact Idle Boundary Transitions**: Activity ticks occurring precisely at $t = \text{threshold}$ (counted as active) versus $t = \text{threshold} + \epsilon$ (counted as idle).
- **Extreme PDF Viewport Dimensions**: Zero viewport width/height, fractional dimensions, and ultra-wide viewports ($8000 \times 600$ px).
- **Complex Alphanumeric Page Names**: Names with multiple numeric tokens (e.g. `chapter_1_page_2.png` vs `chapter_1_page_10.png` vs `chapter_2_page_1.png`).

### Tier 3: Cross-Feature Combinations (System Interactions)
Tests interactions between disparate subsystems:
- **Spread Mode $\times$ Manga Direction**: Toggling between single and double spreads dynamically while switching between Western LTR and Manga RTL.
- **Display Adjustments $\times$ Session Tracking**: Verifying that viewport resize and zoom adjustments register user interaction, keeping the session active without inflating word counts.
- **Multi-Format Library Statistics Aggregation**: Catalog containing mixed EPUB, PDF, and CBZ titles, each recording distinct session types, aggregating into unified `LibraryStatistics` with accurate `format_counts`.
- **Atomic Persistence**: Reading progress update and reading session recording executed in the same SQLite WAL database instance under concurrent read access.

### Tier 4: Real-World Scenarios (End-to-End Lifecycles)
Tests end-to-end user workflows matching production desktop operations:
- **Complete Reading Session Lifecycle**:
  1. Open book $\to$ start session.
  2. Advance 5 pages with periodic activity and page word allocations.
  3. Pause reading for 180 seconds (triggering idle detection).
  4. Resume reading for 3 more pages.
  5. Close book $\to$ verify session summary duration, active time, idle time, and WPM.
- **PDF E2E Import, Navigation, and Resumption**:
  1. User imports `sample-doc.pdf` into `LibraryView`.
  2. Application registers book in `BookRepository` with format `"pdf"`.
  3. User opens book $\to$ `PdfReaderView` activates.
  4. User navigates to Page 1 $\to$ triggers auto-save checkpoint.
  5. User closes reader $\to$ returns to library.
  6. User reopens book $\to$ verifies reading position resumes at Page 1.
- **CBZ E2E Import, Navigation, and Resumption**:
  1. User imports `sample-comic.cbz` into `LibraryView`.
  2. Application registers book with format `"cbz"`.
  3. User opens book $\to$ `ComicReaderView` activates.
  4. User navigates spread $\to$ checkpoint saved.
  5. User closes and reopens $\to$ verifies spread position resumes correctly.
- **Book Deletion Cascade Durability**:
  1. Record sessions and statistics for a book.
  2. Delete book from library.
  3. Verify foreign key `ON DELETE CASCADE` removes associated sessions and statistics records completely from SQLite WAL storage.

---

## 3. Test Fixture Management & Determinism

### Static Fixtures (`fixtures/`)
- `fixtures/sample-doc.pdf`: 2-page fixed-layout PDF document (612 $\times$ 792 pt, Helvetica typography).
- `fixtures/sample-comic.cbz`: Multi-page comic archive with cover and interior pages.
- `fixtures/canonical-text.epub`: Multi-chapter reflowable EPUB for cross-format integration tests.

### Dynamic Synthetic Fixtures
For edge cases (empty archives, single pages, custom natural sort sequences), tests programmatically generate temporary ZIP archives and PDF streams within Python `tempfile.TemporaryDirectory()`. All temporary artifacts are guaranteed to be cleaned up on test teardown.

---

## 4. Test Verification & Execution Matrix

| Test Suite | File Path | Focus | Execution Command |
|------------|-----------|-------|-------------------|
| Baseline Unit & Integration | `tests/test_*.py` (existing) | CFI, EPUB, Storage, Security, G2 Slice | `python3 -m unittest discover tests` |
| WP-10 & WP-11 E2E Suite | `tests/test_e2e_wp10_wp11.py` | Tiers 1-4 for Comic, PDF, Stats, Lifecycle | `python3 -m unittest tests/test_e2e_wp10_wp11.py` |
| Parity Spikes | `spikes/parity_spike/run_spike.py` | Memory, Cairo, Poppler, A11y | `python3 spikes/parity_spike/run_spike.py` |

---

## 5. Traceability Matrix

| Requirement | PRD Clause | Test Identifier | Tier | Description |
|-------------|------------|-----------------|------|-------------|
| R1 (CBZ/CBR Reader) | FR-06, FR-07, AT-04 | `test_comic_archive_enumeration_natural_sorting` | Tier 1 | Natural sort order |
| R1 (CBZ/CBR Reader) | FR-06, FR-07, AT-04 | `test_comic_spread_pairing_ltr` | Tier 1 | Single/double spread pairing |
| R1 (CBZ/CBR Reader) | FR-06, FR-07, AT-04 | `test_comic_spread_pairing_rtl_manga` | Tier 1 | Manga RTL spread inversion |
| R1 (CBZ/CBR Reader) | FR-06, FR-07 | `test_comic_archive_empty` | Tier 2 | Empty archive boundary |
| R1 (CBZ/CBR Reader) | FR-06, FR-07 | `test_comic_archive_single_page` | Tier 2 | Single page boundary |
| R1 (CBZ/CBR Reader) | FR-06, FR-07 | `test_comic_spread_mode_direction_combination` | Tier 3 | Spread mode $\times$ direction |
| R1 (CBZ/CBR Reader) | FR-01, FR-06, NFR-01 | `test_e2e_cbz_import_navigate_resume` | Tier 4 | E2E import and reopen resume |
| R2 (PDF Reader) | FR-06, FR-07, AT-04 | `test_pdf_page_count_and_dimensions` | Tier 1 | Page count & MediaBox points |
| R2 (PDF Reader) | FR-06, FR-07 | `test_pdf_fit_scale_calculations` | Tier 1 | Fit-to-width and fit-to-page math |
| R2 (PDF Reader) | FR-06, FR-07 | `test_pdf_extreme_viewport_dimensions` | Tier 2 | Viewport boundary limits |
| R2 (PDF Reader) | FR-01, FR-06, NFR-01 | `test_e2e_pdf_import_navigate_resume` | Tier 4 | E2E import and reopen resume |
| R3 (Reading Stats) | FR-15, AT-01, AT-03 | `test_session_tracker_active_duration_accumulation` | Tier 1 | Active duration accumulation |
| R3 (Reading Stats) | FR-15, AT-01 | `test_session_tracker_idle_filtering_text_and_comics` | Tier 1 | 120s / 60s idle thresholding |
| R3 (Reading Stats) | FR-15, AT-01 | `test_session_tracker_wpm_calculation_and_guards` | Tier 1 | WPM speed math & guards |
| R3 (Reading Stats) | FR-15, AT-01 | `test_session_zero_duration_and_skims` | Tier 2 | Zero duration & rapid flips |
| R3 (Reading Stats) | FR-15, AT-01 | `test_session_exact_idle_boundary` | Tier 2 | Exact idle transition boundary |
| R3 (Reading Stats) | FR-15, AT-03 | `test_complete_reading_session_lifecycle` | Tier 4 | Full reading session lifecycle |
| R4 (Storage & App) | NFR-01, NFR-02, FR-20 | `test_statistics_repository_crud_and_aggregates` | Tier 1 | Schema v2 stats persistence |
| R4 (Storage & App) | NFR-01, NFR-02 | `test_library_statistics_multi_format_aggregation` | Tier 3 | Multi-format library stats |
| R4 (Storage & App) | NFR-01, NFR-02 | `test_library_sessions_cascade_on_book_deletion` | Tier 4 | Cascade deletion on book remove |
