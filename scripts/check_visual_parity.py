#!/usr/bin/env python3
"""
check_visual_parity.py — Headless visual-parity checker (stdlib only).

Maps to PRD section 5.3 visual acceptance thresholds:
  VP-01  Static control edges / text bounding boxes within 1 logical px of B0.
         Headless proxy: assert key CSS geometry tokens exist in
         src/aquile/ui/style.css with px values within tolerance.
         FAILS LOUDLY if any required token is missing.
  VP-02  Flat-color design tokens within Delta-E2000 <= 2 of B0.
         Headless proxy: parse hex color tokens per theme and assert
         WCAG text/bg contrast >= 4.5 (B0-agnostic sanity). True
         Delta-E2000 vs B0 needs captured B0 swatches (G1-blocked).
  VP-03  SSIM >= 0.99 per captured app-owned region.
         BLOCKED headless: screenshot comparison needs a target
         Ubuntu desktop + B0 reference captures. Never attempted here.
  VP-04  Identical text, line breaks, content order, page/spread
         boundaries in canonical EPUB fixtures with matched fonts/settings.
         Headless proxy: re-parse fixtures/canonical-text.epub twice plus
         once more after a settings change; assert identical page-break
         offsets and preserved content order.
  VP-05  Intentional UI timing within max(16ms, 10%) of B0 (PRD 5.3); page-turn
         computation latency follows section 8.2 instead (PF-03: warm EPUB
         page turn p95 <= 100ms). Headless proxy: measure ChapterPaginator
         page-turn p95, assert <= 100ms. Faster execution is acceptable per
         PRD 5.3 and must not be artificially delayed.

No display is used. No screenshots are captured or compared.

Output: PASS/FAIL/BLOCKED per VP on stdout + JSON report at
docs/validation/VISUAL_PARITY.json. Exit 0 unless a VP FAILs
(BLOCKED does not fail the run).
"""

import json
import math
import os
import re
import statistics
import sys
import time
from datetime import datetime, timezone

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
STYLE_CSS = os.path.join(REPO_ROOT, "src", "aquile", "ui", "style.css")
FIXTURE_EPUB = os.path.join(REPO_ROOT, "fixtures", "canonical-text.epub")
REPORT_PATH = os.path.join(REPO_ROOT, "docs", "validation", "VISUAL_PARITY.json")

if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

GEOMETRY_TOLERANCE_PX = 1.0  # VP-01: within 1 logical pixel of B0/documented value.

# Required geometry tokens actually present in style.css.
# selector -> {property: expected px list}. Shorthand values (e.g. "8px 16px")
# expand to ordered lists: padding/margin shorthand order preserved as written.
REQUIRED_GEOMETRY = {
    ".reading-column": {
        "padding": [24.0],
        "border-radius": [4.0],
    },
    ".reading-column-separator": {
        "min-width": [1.0],
        "margin-top": [24.0],
        "margin-bottom": [24.0],
    },
    ".reader-progress-footer": {
        "padding": [8.0, 16.0],
    },
    ".book-card": {
        "padding": [16.0],
        "margin": [8.0],
        "border-radius": [8.0],
    },
    ".empty-library-label": {
        "margin": [48.0],
    },
}

# Required flat-color tokens actually present in style.css.
# (theme, selector) -> {"bg": hex, "fg": hex}
EXPECTED_COLORS = {
    ("light", ".aquile-theme-light"): {"bg": "#fbfbfb", "fg": "#242424"},
    ("light", ".aquile-theme-light .reading-surface"): {"bg": "#ffffff", "fg": "#242424"},
    ("light", ".aquile-theme-light .reading-column"): {"bg": "#ffffff", "fg": "#242424"},
    ("dark", ".aquile-theme-dark"): {"bg": "#1a1a1a", "fg": "#e0e0e0"},
    ("dark", ".aquile-theme-dark .reading-surface"): {"bg": "#202020", "fg": "#dedede"},
    ("dark", ".aquile-theme-dark .reading-column"): {"bg": "#202020", "fg": "#dedede"},
    ("sepia", ".aquile-theme-sepia"): {"bg": "#ece3ce", "fg": "#433422"},
    ("sepia", ".aquile-theme-sepia .reading-surface"): {"bg": "#f6efe2", "fg": "#433422"},
    ("sepia", ".aquile-theme-sepia .reading-column"): {"bg": "#f6efe2", "fg": "#433422"},
}

MIN_CONTRAST = 4.5  # WCAG AA normal-text floor used as B0-agnostic sanity.
PAGE_TURN_P95_BUDGET_MS = 100.0  # PF-03 headless proxy budget.
PAGINATION_SETTINGS = {
    "viewport_width": 1024,
    "viewport_height": 768,
    "columns": 2,
    "font_size": 16,
    "line_height": 1.6,
}
ALT_FONT_SIZE = 18  # "settings change" leg of VP-04 (then restored).


# ---------------------------------------------------------------- CSS parsing

def parse_css_blocks(css_text):
    """Return {selector: {property: value}} with later blocks overriding earlier."""
    css_text = re.sub(r"/\*.*?\*/", "", css_text, flags=re.DOTALL)
    merged = {}
    for match in re.finditer(r"([^{}]+)\{([^{}]*)\}", css_text):
        raw_selectors, body = match.group(1), match.group(2)
        decls = {}
        for decl in body.split(";"):
            if ":" not in decl:
                continue
            prop, _, val = decl.partition(":")
            prop, val = prop.strip().lower(), val.strip()
            if prop and val:
                decls[prop] = val
        for sel in raw_selectors.split(","):
            sel = sel.strip()
            if sel:
                merged.setdefault(sel, {}).update(decls)
    return merged


def extract_px_list(value):
    return [float(v) for v in re.findall(r"(-?\d+(?:\.\d+)?)\s*px", value)]


# ---------------------------------------------------------------- color math

def hex_to_rgb(hex_str):
    h = hex_str.strip().lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) != 6:
        raise ValueError("bad hex color: %r" % hex_str)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _linearize(c):
    c = c / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def relative_luminance(rgb):
    r, g, b = (_linearize(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(fg_hex, bg_hex):
    l1 = relative_luminance(hex_to_rgb(fg_hex))
    l2 = relative_luminance(hex_to_rgb(bg_hex))
    lighter, darker = max(l1, l2), min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def _rgb_to_lab(rgb):
    r, g, b = (_linearize(c) for c in rgb)
    x = (r * 0.4124 + g * 0.3576 + b * 0.1805) / 0.95047
    y = (r * 0.2126 + g * 0.7152 + b * 0.0722) / 1.0
    z = (r * 0.0193 + g * 0.1192 + b * 0.9505) / 1.08883

    def f(t):
        return t ** (1.0 / 3.0) if t > 0.008856 else 7.787 * t + 16.0 / 116.0

    fx, fy, fz = f(x), f(y), f(z)
    return (116.0 * fy - 16.0, 500.0 * (fx - fy), 200.0 * (fy - fz))


def delta_e_approx(hex_a, hex_b):
    """Delta-E approximation (CIE76 over Lab). Stand-in for Delta-E2000 headless."""
    la = _rgb_to_lab(hex_to_rgb(hex_a))
    lb = _rgb_to_lab(hex_to_rgb(hex_b))
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(la, lb)))


# ---------------------------------------------------------------- VP checks

def check_geometry(css_path=STYLE_CSS):
    errors, checked = [], []
    if not os.path.isfile(css_path):
        return {"id": "VP-01", "status": "FAIL",
                "errors": ["style.css not found: %s" % css_path], "checked": []}
    with open(css_path, encoding="utf-8") as fh:
        blocks = parse_css_blocks(fh.read())
    for selector, props in REQUIRED_GEOMETRY.items():
        if selector not in blocks:
            errors.append("missing selector block: %s" % selector)
            continue
        for prop, expected in props.items():
            if prop not in blocks[selector]:
                errors.append("missing token: %s { %s }" % (selector, prop))
                continue
            actual = extract_px_list(blocks[selector][prop])
            if not actual:
                errors.append("token has no px value: %s { %s: %s }"
                              % (selector, prop, blocks[selector][prop]))
                continue
            entry = {"selector": selector, "property": prop,
                     "expected_px": expected, "actual_px": actual}
            checked.append(entry)
            if len(actual) != len(expected) or any(
                    abs(a - e) > GEOMETRY_TOLERANCE_PX for a, e in zip(actual, expected)):
                errors.append(
                    "geometry drift > %.1fpx: %s { %s }: expected %s, found %s"
                    % (GEOMETRY_TOLERANCE_PX, selector, prop, expected, actual))
    return {"id": "VP-01", "status": "FAIL" if errors else "PASS",
            "errors": errors, "checked": checked,
            "tolerance_px": GEOMETRY_TOLERANCE_PX}


def check_colors(css_path=STYLE_CSS):
    errors, pairs = [], []
    if not os.path.isfile(css_path):
        return {"id": "VP-02", "status": "FAIL",
                "errors": ["style.css not found: %s" % css_path], "pairs": []}
    with open(css_path, encoding="utf-8") as fh:
        blocks = parse_css_blocks(fh.read())
    for (theme, selector), expected in EXPECTED_COLORS.items():
        if selector not in blocks:
            errors.append("missing selector block: %s" % selector)
            continue
        decls = blocks[selector]
        bg = decls.get("background-color", "")
        fg = decls.get("color", "")
        try:
            bg_rgb = hex_to_rgb(bg)
            fg_rgb = hex_to_rgb(fg)
        except ValueError:
            errors.append("unparsable color token in %s: bg=%r fg=%r"
                          % (selector, bg, fg))
            continue
        ratio = contrast_ratio(fg, bg)
        drift = {"bg": delta_e_approx(bg, expected["bg"]),
                 "fg": delta_e_approx(fg, expected["fg"])}
        pairs.append({"theme": theme, "selector": selector,
                      "bg": bg.lower(), "fg": fg.lower(),
                      "contrast": round(ratio, 3),
                      "delta_e_vs_documented": {k: round(v, 3) for k, v in drift.items()}})
        if bg.lower() != expected["bg"] or fg.lower() != expected["fg"]:
            errors.append("flat-color token drift in %s: expected bg=%s fg=%s, found bg=%s fg=%s"
                          % (selector, expected["bg"], expected["fg"], bg, fg))
        if ratio < MIN_CONTRAST:
            errors.append("contrast %.2f < %.1f in %s (%s on %s)"
                          % (ratio, MIN_CONTRAST, selector, fg, bg))
    light_bg = dict((p["selector"], p["bg"]) for p in pairs if p["theme"] == "light")
    dark_bg = dict((p["selector"].replace(".aquile-theme-dark", ".aquile-theme-light"), p["bg"])
                   for p in pairs if p["theme"] == "dark")
    theme_separation = {}
    for sel, lbg in light_bg.items():
        if sel in dark_bg:
            theme_separation[sel] = round(delta_e_approx(lbg, dark_bg[sel]), 2)
    return {"id": "VP-02", "status": "FAIL" if errors else "PASS",
            "errors": errors, "pairs": pairs,
            "min_contrast": MIN_CONTRAST,
            "theme_separation_delta_e": theme_separation,
            "b0_delta_e2000": "blocked: needs captured B0 swatches on target desktop (G1); "
                              "documented-token Delta-E reported as headless proxy only"}


def _load_paginator_modules():
    from src.aquile.reader.epub_parser import EpubParser
    from src.aquile.reader.pagination import ChapterPaginator
    return EpubParser, ChapterPaginator


def page_break_offsets(paginator):
    """Cumulative char offsets at which each page starts in the column-block stream."""
    offsets, cursor = [], 0
    for page in paginator.pages:
        offsets.append(cursor)
        blocks = [page.left_column]
        if page.right_column:
            blocks.append(page.right_column)
        for block in blocks:
            cursor += len(block) + 2  # "\n\n" join assumed by ChapterPaginator
    return offsets


def check_pagination(fixture=FIXTURE_EPUB):
    errors = []
    if not os.path.isfile(fixture):
        return {"id": "VP-04", "status": "FAIL",
                "errors": ["fixture not found: %s" % fixture]}
    try:
        EpubParser, ChapterPaginator = _load_paginator_modules()
    except Exception as exc:  # fail loudly, never silently mock
        return {"id": "VP-04", "status": "FAIL",
                "errors": ["cannot import EPUB paginator stack: %s" % exc]}

    def paginate(font_size):
        parser = EpubParser(fixture)
        full_text = "\n\n".join(ch["clean_text"] for ch in parser.chapters)
        paginator = ChapterPaginator(full_text, PAGINATION_SETTINGS["viewport_width"],
                                     PAGINATION_SETTINGS["viewport_height"],
                                     columns=PAGINATION_SETTINGS["columns"],
                                     font_size=font_size,
                                     line_height=PAGINATION_SETTINGS["line_height"])
        return full_text, paginator, page_break_offsets(paginator)

    text1, pg1, off1 = paginate(PAGINATION_SETTINGS["font_size"])
    text2, pg2, off2 = paginate(PAGINATION_SETTINGS["font_size"])  # re-parse
    _, pg_alt, off_alt = paginate(ALT_FONT_SIZE)  # settings change
    text3, pg3, off3 = paginate(PAGINATION_SETTINGS["font_size"])  # restored

    if text1 != text2 or text1 != text3:
        errors.append("EPUB re-parse is not text-identical across runs")
    if off1 != off2:
        errors.append("page-break offsets differ between identical runs")
    if off1 != off3:
        errors.append("page-break offsets changed after settings restore "
                      "(font %d -> %d -> %d)"
                      % (PAGINATION_SETTINGS["font_size"], ALT_FONT_SIZE,
                         PAGINATION_SETTINGS["font_size"]))
    # Content order: joined page columns must reproduce the source stream.
    stream = []
    for page in pg1.pages:
        stream.append(page.left_column)
        if page.right_column:
            stream.append(page.right_column)
    rejoined = "\n\n".join(b for b in stream if b != "")
    norm = lambda s: re.sub(r"\s+", " ", s).strip()
    if norm(rejoined) != norm(text1):
        errors.append("paginated content order/text does not reproduce source")
    if not pg1.pages:
        errors.append("paginator produced zero pages")
    return {"id": "VP-04", "status": "FAIL" if errors else "PASS",
            "errors": errors,
            "fixture": os.path.basename(fixture),
            "settings": dict(PAGINATION_SETTINGS),
            "page_count": len(pg1.pages),
            "alt_font_size": ALT_FONT_SIZE,
            "alt_page_count": len(pg_alt.pages),
            "offsets_match_rerun": off1 == off2,
            "offsets_match_after_settings_restore": off1 == off3,
            "offsets_head": off1[:8],
            "settings_change_yields_expected_difference": off_alt != off1 or len(pg_alt.pages) == len(pg1.pages)}


def check_timing(fixture=FIXTURE_EPUB, turns=200):
    try:
        EpubParser, ChapterPaginator = _load_paginator_modules()
    except Exception as exc:
        return {"id": "VP-05", "status": "FAIL",
                "errors": ["cannot import EPUB paginator stack: %s" % exc]}
    if not os.path.isfile(fixture):
        return {"id": "VP-05", "status": "FAIL",
                "errors": ["fixture not found: %s" % fixture]}
    parser = EpubParser(fixture)
    full_text = "\n\n".join(ch["clean_text"] for ch in parser.chapters)
    paginator = ChapterPaginator(full_text, PAGINATION_SETTINGS["viewport_width"],
                                 PAGINATION_SETTINGS["viewport_height"],
                                 columns=PAGINATION_SETTINGS["columns"],
                                 font_size=PAGINATION_SETTINGS["font_size"],
                                 line_height=PAGINATION_SETTINGS["line_height"])
    if not paginator.pages:
        return {"id": "VP-05", "status": "FAIL", "errors": ["zero pages to turn"]}
    samples = []
    for i in range(turns):
        t0 = time.perf_counter()
        paginator.get_page(i % len(paginator.pages))
        samples.append((time.perf_counter() - t0) * 1000.0)
    samples.sort()
    p50 = statistics.median(samples)
    p95 = samples[min(len(samples) - 1, int(math.ceil(0.95 * len(samples))) - 1)]
    worst = samples[-1]
    errors = []
    if p95 > PAGE_TURN_P95_BUDGET_MS:
        errors.append("page-turn p95 %.3fms exceeds %.1fms budget" % (p95, PAGE_TURN_P95_BUDGET_MS))
    return {"id": "VP-05", "status": "FAIL" if errors else "PASS",
            "errors": errors,
            "turns": turns, "pages": len(paginator.pages),
            "p50_ms": round(p50, 4), "p95_ms": round(p95, 4),
            "max_ms": round(worst, 4),
            "budget_p95_ms": PAGE_TURN_P95_BUDGET_MS,
            "headless_proxy_note": "headless paginator timing only; on-device PF-03 "
                                   "confirmation needs target desktop (matched hardware)"}


def check_ssim():
    return {"id": "VP-03",
            "status": "BLOCKED",
            "errors": [],
            "reason": "SSIM >= 0.99 per captured app-owned region requires screenshots "
                      "from the target Ubuntu desktop (GNOME Wayland/X11, matched logical "
                      "viewport, fonts, settings) plus frozen B0 reference captures. "
                      "No display is available headless, and screenshot comparison is "
                      "explicitly out of scope for this checker."}


# ---------------------------------------------------------------- runner

def run_all():
    return {
        "VP-01": check_geometry(),
        "VP-02": check_colors(),
        "VP-03": check_ssim(),
        "VP-04": check_pagination(),
        "VP-05": check_timing(),
    }


def main():
    results = run_all()
    for vp_id in ("VP-01", "VP-02", "VP-03", "VP-04", "VP-05"):
        res = results[vp_id]
        print("%s: %s" % (vp_id, res["status"]))
        for err in res.get("errors", []):
            print("  - %s" % err)
        if vp_id == "VP-05" and "p95_ms" in res:
            print("  page-turn p50=%sms p95=%sms max=%sms (budget %sms, n=%d)"
                  % (res["p50_ms"], res["p95_ms"], res["max_ms"],
                     res["budget_p95_ms"], res["turns"]))
        if vp_id == "VP-04" and "page_count" in res:
            print("  pages=%d rerun_match=%s restore_match=%s"
                  % (res["page_count"], res["offsets_match_rerun"],
                     res["offsets_match_after_settings_restore"]))
    report = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "headless": True,
        "no_screenshots": True,
        "style_css": os.path.relpath(STYLE_CSS, REPO_ROOT),
        "fixture": os.path.relpath(FIXTURE_EPUB, REPO_ROOT),
        "results": results,
    }
    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
    print("report: %s" % os.path.relpath(REPORT_PATH, REPO_ROOT))
    failed = [k for k, v in results.items() if v["status"] == "FAIL"]
    if failed:
        print("OVERALL: FAIL (%s)" % ", ".join(failed))
        return 1
    blocked = [k for k, v in results.items() if v["status"] == "BLOCKED"]
    print("OVERALL: PASS%s" % (" (blocked: %s)" % ", ".join(blocked) if blocked else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
