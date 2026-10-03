# TEST_READY — WP-10 & WP-11 E2E Testing Suite

## Status: READY
The End-to-End (E2E) testing infrastructure and test suite for **WP-10 (PDF & Comic Book Graphic Readers)** and **WP-11 (Reading Statistics & Session Insights)** are fully established and operational.

---

## 1. Test Suite Summary

- **Test Infrastructure Document**: `TEST_INFRA.md`
- **Automated Test Suite**: `tests/test_e2e_wp10_wp11.py`
- **Methodology**: 4-Tier Opaque-Box Verification (Feature Coverage, Boundaries & Corners, Cross-Feature Combinations, Real-World Scenarios)
- **Baseline Non-Regression**: 100% pass across all 13 existing unit and integration tests (`tests/test_cfi_and_anchors.py`, `tests/test_domain_and_storage.py`, `tests/test_epub_and_pagination.py`, `tests/test_g2_reading_slice.py`, `tests/test_security_sandboxing.py`).
- **Parity Spikes**: 5/5 spikes passing (`spikes/parity_spike/run_spike.py`).

---

## 2. Test Execution Commands

### Run Full Test Discovery (Baseline + E2E Suite)
```bash
python3 -m unittest discover tests -v
```

### Run Dedicated WP-10 & WP-11 E2E Suite
```bash
python3 -m unittest tests/test_e2e_wp10_wp11.py -v
```

### Run Parity Spike Suite
```bash
python3 spikes/parity_spike/run_spike.py
```

---

## 3. Four-Tier Coverage Matrix

| Tier | Test Method | Target Component / Interface | Verification Objective | Mapped PRD Requirement |
|------|-------------|------------------------------|------------------------|------------------------|
| **Tier 1** | `test_comic_archive_enumeration_natural_sorting` | `ComicArchiveEngine.list_page_entries` | Rejects non-images & `__MACOSX`, sorts naturally (`page2` before `page10`) | FR-06, FR-07, AT-04 |
| **Tier 1** | `test_comic_spread_pairing_ltr` | `ComicArchiveEngine.get_spreads(mode, direction)` | Single-page spread vs double-page spread with isolated cover (Western LTR) | FR-06, FR-07, AT-04 |
| **Tier 1** | `test_comic_spread_pairing_rtl_manga` | `ComicArchiveEngine.get_spreads(mode="double", direction="rtl")` | Inverts interior page pairs for Manga RTL reading | FR-06, FR-07, AT-04 |
| **Tier 1** | `test_aspect_ratio_containment_math` | Aspect ratio scaling formula | Preserves exact aspect ratio when fitting into viewport (`CONTAIN`) | FR-06, VP-01 |
| **Tier 1** | `test_pdf_page_count_and_dimensions` | `PdfDocumentEngine.get_page_dimensions` | Page count (2 pages) and MediaBox points (612 $\times$ 792 pt) | FR-06, FR-07, AT-04 |
| **Tier 1** | `test_pdf_fit_scale_calculations` | `PdfDocumentEngine.calculate_fit_scale` | Exact fit-to-width and fit-to-page zoom factor calculations | FR-06, FR-07 |
| **Tier 1** | `test_session_tracker_active_duration_accumulation` | `ReadingSessionTracker.tick` & `register_activity` | Duration accumulation during active reading interactions | FR-15, AT-01, AT-03 |
| **Tier 1** | `test_session_tracker_idle_filtering_text_and_comics` | `ReadingSessionTracker.tick` (idle gap) | Idle filtering threshold: 120s for reflow/text, 60s for comics | FR-15, AT-01 |
| **Tier 1** | `test_session_tracker_wpm_calculation_and_guards` | `ReadingSessionTracker.end_session` | WPM speed metric calculation with duration guard and outlier clamp | FR-15, AT-01 |
| **Tier 1** | `test_statistics_repository_crud_and_aggregates` | `StatisticsRepository` | Persistence of `ReadingSession`, aggregation into `BookStatistics` & `LibraryStatistics` | FR-15, NFR-01, NFR-02 |
| **Tier 2** | `test_comic_archive_empty` | `ComicArchiveEngine` | Zero image archive returns 0 pages and empty spread list | FR-06, NFR-06 |
| **Tier 2** | `test_comic_archive_single_page` | `ComicArchiveEngine` | Single page archive isolates cover without phantom pairs | FR-06 |
| **Tier 2** | `test_comic_archive_odd_page_count_spreads` | `ComicArchiveEngine` | Odd page counts correctly isolate cover and final single page | FR-06 |
| **Tier 2** | `test_session_zero_duration_and_skims` | `ReadingSessionTracker` | Zero duration session yields 0.0 WPM without `ZeroDivisionError` | FR-15 |
| **Tier 2** | `test_session_exact_idle_boundary` | `ReadingSessionTracker` | Activity tick at exactly $t = \text{threshold}$ vs $t = \text{threshold} + \epsilon$ | FR-15 |
| **Tier 2** | `test_pdf_extreme_viewport_dimensions` | `PdfDocumentEngine` | Zero, negative, and ultra-wide viewports handled gracefully | FR-06 |
| **Tier 2** | `test_comic_natural_sort_complex_alphanumeric_and_subdirs` | `ComicArchiveEngine` | Multi-token numerical sorting (`ch_2_p_10` vs `ch_10_p_1`) in nested folders | FR-06 |
| **Tier 3** | `test_comic_spread_mode_direction_combination` | `ComicArchiveEngine` | Dynamic toggling between single/double and LTR/RTL on same instance | FR-06, FR-07 |
| **Tier 3** | `test_stats_tracking_during_display_adjustments` | `ReadingSessionTracker` | Viewport zoom/spread changes maintain active session without inflating word counts | FR-15 |
| **Tier 3** | `test_library_statistics_multi_format_aggregation` | `StatisticsRepository` | Aggregates sessions across mixed formats (`epub`, `pdf`, `cbz`) into unified `LibraryStatistics` | FR-15, FR-20 |
| **Tier 3** | `test_progress_and_session_atomic_persistence` | `ReadingProgressRepository` + `StatisticsRepository` | Atomic updates to reading location and session history under SQLite WAL mode | NFR-01, NFR-02 |
| **Tier 4** | `test_complete_reading_session_lifecycle` | `ReadingSessionTracker` $\to$ `StatisticsRepository` | End-to-end reading session lifecycle: start, 3 pages, pause, resume 2 pages, end, verify | FR-15, AT-01, AT-03 |
| **Tier 4** | `test_e2e_pdf_import_navigate_resume` | `AquileReaderApp` $\to$ `LibraryView` $\to$ `PdfReaderView` | E2E import of `sample-doc.pdf`, page navigation, auto-save checkpoint, close, reopen & resume | FR-01, FR-06, NFR-01 |
| **Tier 4** | `test_e2e_cbz_import_navigate_resume` | `AquileReaderApp` $\to$ `LibraryView` $\to$ `ComicReaderView` | E2E import of `sample-comic.cbz`, spread navigation, auto-save checkpoint, close, reopen & resume | FR-01, FR-06, NFR-01 |
| **Tier 4** | `test_library_sessions_cascade_on_book_deletion` | `BookRepository.delete` | Foreign key `ON DELETE CASCADE` removes all associated sessions and statistics records | NFR-02, FR-20 |

---

## 4. Progressive Testability & Readiness

The test suite incorporates progressive testability:
- **Active Tests (Passed Immediately)**: Tests for completed components (e.g., aspect ratio mathematics, `StatisticsRepository` CRUD, SQLite WAL durability, cascade deletions, and all 13 baseline unit/integration tests) execute and pass now.
- **Progressive Test Hooks**: Tests for pending milestones (M2 `ComicArchiveEngine`, M3 `PdfDocumentEngine`, M4 `ReadingSessionTracker`, and M5 polymorphic reader view routing) automatically skip with explicit descriptors until the implementing worker delivers the module. As workers finish M2, M3, M4, and M5, running `python3 -m unittest discover tests` will seamlessly promote the corresponding tests to active execution without any changes to the test harness.
