# Headless Performance Benchmarks (PF-01..PF-07 proxies)

> Headless proxies only — **not** GUI acceptance. Real acceptance requires
> AT-13 on the documented rig (4-core amd64, 8 GB RAM, SSD, 60 Hz) with
> ≥30 opens / 200 page changes and a matched-hardware B0 comparison.
> Raw JSON: `docs/validation/BENCHMARKS.json`. Harness: `scripts/benchmark.py`
> (stdlib-only: `time`, `statistics`, `tracemalloc`, `tempfile`, `sqlite3`
> via app repos, `zipfile`). Run: `python3 scripts/benchmark.py`.

## Measured run (2026-10-03)

Environment: CPython **3.14.4**, x86_64, Linux 7.0.0-38-generic,
16 CPUs (`os.cpu_count()`), repo-local temp SQLite DB, wall time **~652 ms**
(30 iterations per benchmark; well under the 60 s harness budget).
Fixture: `fixtures/canonical-text.epub` (3,897 bytes on disk, 7 text docs,
10,315 bytes uncompressed) — far below the PRD's up-to-10 MiB canonical EPUB,
so PF-02 headless numbers understate real open cost.

| ID | Target | Headless proxy result | Method | Verdict |
| --- | --- | --- | --- | --- |
| PF-01 | Cold launch to interactive library, p95 ≤ 3 s | **p95 ≈ 7.42 ms** (single cold `BookRepository.list_all()` on fresh temp DB with 1,000 rows; warm `list_all` p50 6.19 / p95 7.18 ms, n=30; 1,000-row insert 232.4 ms) | Temp-DB + 1,000 `BookRepository.add`, timed `list_all` | PASS (proxy) — excludes process start, GTK/Adw init, window present, cover decode |
| PF-02 | Open canonical EPUB to readable content, p95 ≤ 2 s | **p95 ≈ 0.43 ms** (p50 0.40 ms, n=30) | stdlib `zipfile` extraction of the 7 text members, no parse/layout/render | PASS (proxy) — no OPF/spine parse, pagination, font shaping, or first paint |
| PF-03 | Warm EPUB page turn, p95 ≤ 100 ms | **p95 ≈ 0.37 ms** (p50 0.034 ms, n=200 ticks; 27,874 words estimated total) | `estimate_words_for_page("epub", page)` + `ReadingSessionTracker.register_activity`/`tick` per turn over cycled fixture text | PASS (proxy) — no paginator, layout, image decode, or frame present |
| PF-04 | Library search/filter on 1,000 books, p95 ≤ 250 ms | **p95 ≈ 1.03 ms** (p50 0.98 ms, n=30 over 5 queries) | Python substring filter over `list_all()` snapshot (title/author/path) | PASS (proxy) — no GTK sort/filter model, live typing, or rendered list |
| PF-05 | Long imports/indexing/downloads: UI input ≤ 250 ms | **not measured** (`pass: null`) | No GUI event loop headless | NOT RUN — needs scripted import + input-latency probe under load (AT-13) |
| PF-06 | Memory ≤ 500 MiB idle / ≤ 750 MiB with EPUB (process-tree RSS) | **RSS 25.91 MiB, HWM 25.98 MiB; tracemalloc peak 2.53 MiB** | `/proc/self/status` VmRSS/VmHWM + `tracemalloc` around full harness | PASS (proxy) — single headless process only; GTK/Adw, WebKit/renderers, GPU, covers not loaded |
| PF-07 | Large PDFs/comics: lazy rendering, bounded cache; 1,000-page traversal | **not measured** (`pass: null`) | 200 regex/tracker ticks only; no renderer or cache accounting | NOT RUN — needs large PDF/comic fixtures, RSS-per-page curve, cache-eviction proof (AT-13) |

Budgets are checked by the harness but reported truthfully: PF-05 and PF-07
emit `pass: null`, and PF-01/PF-02/PF-03/PF-04/PF-06 passes are labelled
proxy-only in both the JSON and this table.

## Gaps to real-GUI measurement (AT-13)

1. No GTK 4/Adw startup, CSS/theme load, window present, or `interactive`
   definition (first input accepted) — PF-01 proxy is one SQLite query.
2. No EPUB parse → paginate → shape → paint pipeline; fixture is 3.9 KiB vs
   the up-to-10 MiB canonical EPUB — PF-02/PF-03 proxies miss layout and GPU.
3. Search proxy is a bulk substring scan, not keystroke-driven filtering of a
   rendered 1,000-row list — misses sort/filter-model and frame costs (PF-04).
4. No background-work + input-latency probe (cancellable import/index/download
   while measuring UI response) — PF-05 unmeasured.
5. Single-process RSS/HWM only, no process-tree accounting, no idle-library or
   EPUB-open steady-state GUI residency, no 1,000-page RSS growth curve or
   cache-boundedness evidence — PF-06 partial, PF-07 unmeasured.
6. No matched-hardware B0 regression comparison (20% rule), no 24-hour
   endurance run, no 30-open/200-page-change percentile sampling on the
   reference rig — required by PRD §8.2 / AT-13 before any pass claim counts
   as acceptance.
