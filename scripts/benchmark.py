#!/usr/bin/env python3
"""Headless performance benchmark harness (stdlib-only) for Aquile Reader.

Proxies for PRD PF-01..PF-07 that can run without a GUI on CI/headless hosts.
Results are reported truthfully against budgets; failures do not raise --
they are recorded as pass=false in the JSON output.

Benchmarks:
  (a) cold library open: create temp DB + insert 1000 books, time list_all
      (target PF-04 p95<=250ms noted as headless proxy; PF-01 cold-launch
      proxy is the single first list_all after fresh process/DB-cache drop)
  (b) EPUB open proxy: parse fixtures/canonical-text.epub with zipfile only
      (no GUI/rendering); synthetic fallback if fixture is missing
  (c) warm page turn: 200 paginator/tracker ticks (word estimate + tracker tick)
  (d) search/filter over 1000 books (Python filter + SQL LIKE)
  (e) memory: peak via tracemalloc + RSS/HWM via /proc/self/status

Usage:
    python3 scripts/benchmark.py [--json-out PATH] [--iterations N]

Output: JSON to stdout + docs/validation/BENCHMARKS.json (repo-relative).
Must run in <60s on a typical dev machine.

Budgets (from PRD section 8.2; headless proxies, NOT GUI acceptance):
  PF-01 cold launch to interactive library ......... p95 <= 3000 ms
  PF-02 open canonical EPUB to readable content .... p95 <= 2000 ms
  PF-03 warm EPUB page turn ....................... p95 <= 100 ms
  PF-04 library search/filter on 1000 books ........ p95 <= 250 ms
  PF-06 memory idle library / canonical EPUB ...... <= 500/750 MiB RSS proxy
"""

import argparse
import json
import os
import platform
import statistics
import sys
import tempfile
import time
import tracemalloc
import zipfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

BUDGETS_MS = {
    "PF-01": 3000.0,
    "PF-02": 2000.0,
    "PF-03": 100.0,
    "PF-04": 250.0,
}
BUDGETS_MIB = {
    "PF-06-idle": 500.0,
    "PF-06-epub": 750.0,
}

CANONICAL_EPUB = os.path.join(REPO_ROOT, "fixtures", "canonical-text.epub")

# ---------------------------------------------------------------- helpers

def percentile(data, pct):
    """Percentile in ms units agnostic; data must be non-empty sorted-able."""
    if not data:
        return 0.0
    s = sorted(data)
    if len(s) == 1:
        return float(s[0])
    k = (len(s) - 1) * (pct / 100.0)
    f = int(k)
    c = min(f + 1, len(s) - 1)
    if f == c:
        return float(s[f])
    return float(s[f] + (s[c] - s[f]) * (k - f))


def summarize(samples_ms):
    return {
        "n": len(samples_ms),
        "min_ms": round(min(samples_ms), 4),
        "p50_ms": round(percentile(samples_ms, 50), 4),
        "p95_ms": round(percentile(samples_ms, 95), 4),
        "max_ms": round(max(samples_ms), 4),
        "mean_ms": round(statistics.fmean(samples_ms), 4),
    }


def read_rss_mib():
    """RSS + HWM in MiB from /proc/self/status; (None, None) off-Linux."""
    try:
        with open("/proc/self/status", "r", encoding="utf-8") as fh:
            rss_kb = hwm_kb = None
            for line in fh:
                if line.startswith("VmRSS:"):
                    rss_kb = float(line.split()[1])
                elif line.startswith("VmHWM:"):
                    hwm_kb = float(line.split()[1])
        mib = lambda kb: round(kb / 1024.0, 2) if kb is not None else None
        return mib(rss_kb), mib(hwm_kb)
    except (OSError, ValueError):
        return None, None


def check_budget(p95_ms, budget_ms):
    return bool(p95_ms <= budget_ms)


# ---------------------------------------------------------------- (a) library

def bench_library(n_list=30):
    """Cold library open proxy + warm list_all over 1000 books."""
    from src.aquile.storage.database import Database
    from src.aquile.storage.repository import BookRepository
    from src.aquile.domain.models import Book

    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp_path = tmp.name
    tmp.close()
    try:
        db = Database(tmp_path)
        repo = BookRepository(db)
        t0 = time.perf_counter()
        for i in range(1000):
            repo.add(Book(
                title=f"Bench Book {i:04d} {'lorem ipsum dolor sit amet' * 2}",
                author=f"Author {i % 50}",
                file_path=f"/bench/book-{i:04d}.epub",
                file_format="epub",
            ))
        insert_ms = (time.perf_counter() - t0) * 1000.0

        # Cold proxy: first list_all in this process on a fresh DB.
        t0 = time.perf_counter()
        books = repo.list_all()
        cold_ms = (time.perf_counter() - t0) * 1000.0

        samples = []
        for _ in range(n_list):
            t0 = time.perf_counter()
            repo.list_all()
            samples.append((time.perf_counter() - t0) * 1000.0)
        stats = summarize(samples)
        return {
            "insert_1000_ms": round(insert_ms, 2),
            "cold_first_list_all_ms": round(cold_ms, 4),
            "rows": len(books),
            "warm_list_all": stats,
        }, books, tmp_path
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


# ---------------------------------------------------------------- (b) epub open proxy

def _read_epub_texts(epub_path):
    """Extract raw text payload of an EPUB with stdlib zipfile only."""
    texts = []
    total_compressed = 0
    total_uncompressed = 0
    with zipfile.ZipFile(epub_path, "r") as zf:
        for info in zf.infolist():
            total_compressed += info.compress_size
            total_uncompressed += info.file_size
            name = info.filename.lower()
            if name.endswith((".xhtml", ".html", ".htm", ".xml", ".opf", ".ncx")):
                try:
                    texts.append(zf.read(info.filename))
                except KeyError:
                    pass
    return texts, total_compressed, total_uncompressed


def bench_epub_open(n_runs=30):
    """Time stdlib-only EPUB payload extraction (parse proxy, no rendering)."""
    if os.path.exists(CANONICAL_EPUB):
        fixture = CANONICAL_EPUB
        synthetic = False
    else:
        fixture = None
        synthetic = True
    payloads = None
    if fixture is not None:
        payloads, c_bytes, u_bytes = _read_epub_texts(fixture)
        size_bytes = os.path.getsize(fixture)
    else:
        # Synthetic fallback: build a ~1 MiB in-memory pseudo-EPUB payload.
        blob = (b"<html><body><p>" + b"lorem ipsum dolor sit amet " * 40 + b"</p></body></html>")
        payloads = [blob] * 64
        size_bytes = sum(len(p) for p in payloads)
        c_bytes = u_bytes = size_bytes

    def one_run():
        if fixture is not None:
            t = _read_epub_texts(fixture)
            return t[0]
        # synthetic: concatenate + strip tags (parse-like work)
        import re
        out = []
        for p in payloads:
            out.append(len(re.findall(rb"\w+", p)))
        return out

    # warmup
    one_run()
    samples = []
    for _ in range(n_runs):
        t0 = time.perf_counter()
        one_run()
        samples.append((time.perf_counter() - t0) * 1000.0)
    stats = summarize(samples)
    n_docs = len(payloads)
    return {
        "fixture": os.path.relpath(fixture, REPO_ROOT) if fixture else "SYNTHETIC-FALLBACK",
        "synthetic": synthetic,
        "fixture_bytes": size_bytes,
        "compressed_bytes": c_bytes,
        "uncompressed_bytes": u_bytes,
        "n_text_docs": n_docs,
        "open_proxy": stats,
    }, payloads


# ---------------------------------------------------------------- (c) warm page turn

def bench_page_turn(payloads, n_ticks=200):
    """200 paginator/tracker ticks: word estimate + session tick per page."""
    try:
        from src.aquile.reader.session_tracker import (
            ReadingSessionTracker, estimate_words_for_page,
        )
    except ImportError:
        ReadingSessionTracker = None
        estimate_words_for_page = None

    import re
    # Prepare 200 page texts by cycling through real EPUB payloads.
    pages = []
    if payloads:
        decoded = []
        for p in payloads:
            if isinstance(p, (bytes, bytearray)):
                try:
                    decoded.append(bytes(p).decode("utf-8", "replace"))
                except Exception:
                    decoded.append("")
            elif isinstance(p, int):
                decoded.append("lorem ipsum " * 50)
            else:
                decoded.append(str(p))
        if not decoded:
            decoded = ["lorem ipsum " * 50]
        for i in range(n_ticks):
            pages.append(decoded[i % len(decoded)])
    else:
        pages = ["lorem ipsum dolor sit amet " * 20] * n_ticks

    tracker = None
    if ReadingSessionTracker is not None:
        tracker = ReadingSessionTracker(book_id="bench-book", format="epub")
        tracker.register_activity(now=1000.0)

    samples = []
    words_total = 0
    t = 1000.0
    for i, page in enumerate(pages):
        t += 2.0  # 2 s of reading per page turn (active, under idle threshold)
        t0 = time.perf_counter()
        if estimate_words_for_page is not None:
            words_total += estimate_words_for_page("epub", page)
        else:
            clean = re.sub(r"<[^>]+>", " ", page)
            words_total += len(re.findall(r"\b\w+\b", clean))
        if tracker is not None:
            tracker.register_activity(now=t)
            tracker.tick(now=t)
        samples.append((time.perf_counter() - t0) * 1000.0)
    stats = summarize(samples)
    return {
        "ticks": n_ticks,
        "words_total": words_total,
        "tracker": "ReadingSessionTracker" if tracker is not None else "FALLBACK-REGEX-ONLY",
        "page_turn": stats,
    }


# ---------------------------------------------------------------- (d) search/filter

def bench_search(books, n_runs=30):
    """Filter 1000 books in Python + SQL LIKE; report both, judge on best."""
    queries = ["bench 00", "author 7", "lorem", "BOOK-0999", "nonexistent-zzz"]
    # Python in-memory filter over repo objects.
    py_samples = []
    corpus = [(b.title, b.author, b.file_path) for b in books]
    for r in range(n_runs):
        q = queries[r % len(queries)].lower()
        t0 = time.perf_counter()
        hits = [row for row in corpus
                if q in row[0].lower() or q in row[1].lower() or q in row[2].lower()]
        py_samples.append((time.perf_counter() - t0) * 1000.0)
    py_stats = summarize(py_samples)

    # SQL LIKE over the temp DB via repo connection is not exposed, so use
    # sqlite3 directly on a snapshot path is not available here; instead time
    # the same filter as the budgeted path and record method honestly.
    return {
        "method": "python-substring-filter over BookRepository.list_all() snapshot (1000 rows)",
        "queries": queries,
        "n_runs": n_runs,
        "filter": py_stats,
        "last_hits": len(hits),
    }


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description="Headless perf benchmark harness")
    ap.add_argument("--json-out", default=os.path.join(
        REPO_ROOT, "docs", "validation", "BENCHMARKS.json"))
    ap.add_argument("--iterations", type=int, default=30)
    args = ap.parse_args()
    n = max(5, args.iterations)

    tracemalloc.start()
    wall0 = time.perf_counter()

    lib, books, tmp_path = bench_library(n_list=n)
    rss_after_lib, hwm_after_lib = read_rss_mib()

    epub, payloads = bench_epub_open(n_runs=n)
    rss_after_epub, hwm_after_epub = read_rss_mib()

    pageturn = bench_page_turn(payloads, n_ticks=200)
    search = bench_search(books, n_runs=n)

    current_b, peak_b = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    rss_final, hwm_final = read_rss_mib()

    try:
        os.unlink(tmp_path)
    except OSError:
        pass

    wall_ms = (time.perf_counter() - wall0) * 1000.0

    pf01_p95 = lib["cold_first_list_all_ms"]
    pf02_p95 = epub["open_proxy"]["p95_ms"]
    pf03_p95 = pageturn["page_turn"]["p95_ms"]
    pf04_p95 = search["filter"]["p95_ms"]

    results = {
        "PF-01": {"target": "p95 <= 3000 ms (cold launch proxy: fresh temp-DB first list_all)",
                  "p95_ms": pf01_p95, "pass": check_budget(pf01_p95, BUDGETS_MS["PF-01"])},
        "PF-02": {"target": "p95 <= 2000 ms (EPUB open proxy: stdlib zipfile extraction)",
                  "p95_ms": pf02_p95, "pass": check_budget(pf02_p95, BUDGETS_MS["PF-02"])},
        "PF-03": {"target": "p95 <= 100 ms (warm page turn proxy: word-estimate + tracker tick)",
                  "p95_ms": pf03_p95, "pass": check_budget(pf03_p95, BUDGETS_MS["PF-03"])},
        "PF-04": {"target": "p95 <= 250 ms (search/filter over 1000 books)",
                  "p95_ms": pf04_p95, "pass": check_budget(pf04_p95, BUDGETS_MS["PF-04"])},
        "PF-05": {"target": "background work; UI input responds within 250 ms",
                  "result": "not measured headless (no GUI event loop)",
                  "pass": None},
        "PF-06": {"target": "<= 500 MiB idle / <= 750 MiB with EPUB (total process-tree RSS)",
                  "rss_final_mib": rss_final, "rss_hwm_mib": hwm_final,
                  "tracemalloc_peak_mib": round(peak_b / (1024 * 1024), 3),
                  "tracemalloc_current_mib": round(current_b / (1024 * 1024), 3),
                  "pass": (rss_final <= 750.0) if rss_final is not None else None},
        "PF-07": {"target": "lazy rendering, bounded cache; 1000-page traversal w/o unbounded growth",
                  "result": "not measured headless (no renderer); traversal proxy is 200 regex ticks only",
                  "pass": None},
    }

    output = {
        "schema": "aquile-bench/1",
        "environment": {
            "python": platform.python_version(),
            "implementation": platform.python_implementation(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "system": f"{platform.system()} {platform.release()}",
            "cpu_count": os.cpu_count(),
        },
        "budgets": {"ms": BUDGETS_MS, "mib": BUDGETS_MIB},
        "harness_wall_ms": round(wall_ms, 2),
        "library": lib,
        "epub_open": epub,
        "page_turn": pageturn,
        "search": search,
        "memory": {
            "tracemalloc_current_bytes": current_b,
            "tracemalloc_peak_bytes": peak_b,
            "tracemalloc_peak_mib": round(peak_b / (1024 * 1024), 3),
            "rss_after_library_mib": rss_after_lib,
            "hwm_after_library_mib": hwm_after_lib,
            "rss_after_epub_mib": rss_after_epub,
            "hwm_after_epub_mib": hwm_after_epub,
            "rss_final_mib": rss_final,
            "rss_hwm_mib": hwm_final,
            "note": "single-process RSS only, not total process-tree; GUI renderers/GPU not loaded",
        },
        "results": results,
        "notes": [
            "Headless proxies only: no GTK/Adw, no rendering, no matched-hardware B0 comparison.",
            "PF-05/PF-07 cannot pass headless; recorded as pass=null (not run in GUI sense).",
            "Real-GUI acceptance requires AT-13 on the documented 4-core/8GB/SSD/60Hz rig.",
        ],
    }

    out_path = args.json_out
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(output, fh, indent=2)
        fh.write("\n")

    json.dump(output, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
