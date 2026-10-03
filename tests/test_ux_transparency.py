"""WP-B transparency tests (UX_PLAN_V3 sections 2-3, D4).

Pins: transparency_to_alpha pure math (0=solid -> 1.0, 100=fully
transparent chrome -> 0.0, clamped), apply_transparency clamping, and
stylesheet chrome rules using rgba/alpha translucency.
"""
import os
import re
import unittest

import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk

from src.aquile.ui.titlebar import transparency_to_alpha, apply_transparency

STYLE_CSS = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "src", "aquile", "ui", "style.css"))


def _blocks_for(css_text, selector):
    pattern = re.compile(re.escape(selector) + r"\s*\{([^}]*)\}", re.DOTALL)
    return pattern.findall(css_text)


class TestTransparencyMath(unittest.TestCase):
    def test_zero_is_opaque(self):
        self.assertAlmostEqual(transparency_to_alpha(0), 1.0)

    def test_hundred_is_fully_transparent(self):
        self.assertAlmostEqual(transparency_to_alpha(100), 0.0)

    def test_fifty_is_half(self):
        self.assertAlmostEqual(transparency_to_alpha(50), 0.5)

    def test_negative_clamps_to_opaque(self):
        self.assertAlmostEqual(transparency_to_alpha(-10), 1.0)
        self.assertAlmostEqual(transparency_to_alpha(-1000), 1.0)

    def test_over_hundred_clamps_to_transparent(self):
        self.assertAlmostEqual(transparency_to_alpha(150), 0.0)
        self.assertAlmostEqual(transparency_to_alpha(1000), 0.0)

    def test_bounds_respected_monotonic(self):
        prev = transparency_to_alpha(0)
        for p in (10, 25, 50, 75, 100):
            cur = transparency_to_alpha(p)
            self.assertGreaterEqual(cur, 0.0)
            self.assertLessEqual(cur, 1.0)
            self.assertLessEqual(cur, prev)
            prev = cur


class TestApplyTransparency(unittest.TestCase):
    def setUp(self):
        try:
            Gtk.init()
        except Exception:
            pass

    def test_apply_returns_alpha_and_sets_opacity(self):
        bar_box = Gtk.Box()
        alpha = apply_transparency(bar_box, 30)
        self.assertAlmostEqual(alpha, 0.7)
        self.assertAlmostEqual(bar_box.get_opacity(), 0.7, delta=0.02)

    def test_apply_clamps_bounds(self):
        w1 = Gtk.Box()
        self.assertAlmostEqual(apply_transparency(w1, -20), 1.0)
        self.assertAlmostEqual(apply_transparency(w1, 200), 0.0)


class TestStylesheetTranslucency(unittest.TestCase):
    def test_rail_rule_uses_rgba_or_alpha(self):
        self.assertTrue(os.path.exists(STYLE_CSS), f"missing {STYLE_CSS}")
        with open(STYLE_CSS, encoding="utf-8") as f:
            css = f.read()
        blocks = _blocks_for(css, ".aquile-rail")
        self.assertGreater(len(blocks), 0, "no .aquile-rail rule found")
        translucent = [b for b in blocks
                       if "rgba(" in b.lower() or "alpha(" in b.lower()]
        self.assertGreater(len(translucent), 0,
                           ".aquile-rail chrome must use rgba()/alpha() translucency")

    def test_toolbar_rule_uses_rgba_or_alpha(self):
        self.assertTrue(os.path.exists(STYLE_CSS), f"missing {STYLE_CSS}")
        with open(STYLE_CSS, encoding="utf-8") as f:
            css = f.read()
        blocks = _blocks_for(css, ".reader-toolbar")
        self.assertGreater(len(blocks), 0, "no .reader-toolbar rule found")
        translucent = [b for b in blocks
                       if "rgba(" in b.lower() or "alpha(" in b.lower()]
        self.assertGreater(len(translucent), 0,
                           ".reader-toolbar chrome must use rgba()/alpha() translucency")


if __name__ == "__main__":
    unittest.main()
