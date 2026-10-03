"""
Unit tests for the headless visual-parity checker (PRD 5.3, VP-01..VP-05).
Wraps scripts/check_visual_parity.py via sys.path import (no logic duplicated).
Headless only: VP-03 SSIM screenshot comparison stays BLOCKED (target desktop).
"""

import json
import os
import sys
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import check_visual_parity as cvp


class TestVisualParity(unittest.TestCase):
    def test_geometry_tokens_present(self):
        res = cvp.check_geometry()
        self.assertEqual(res["status"], "PASS", msg="VP-01 errors: %r" % res["errors"])
        self.assertTrue(len(res["checked"]) >= 10,
                        msg="expected >=10 geometry token checks, got %d" % len(res["checked"]))
        selectors = {c["selector"] for c in res["checked"]}
        self.assertIn(".reading-column", selectors)
        self.assertIn(".reading-column-separator", selectors)

    def test_colors_parse(self):
        res = cvp.check_colors()
        self.assertEqual(res["status"], "PASS", msg="VP-02 errors: %r" % res["errors"])
        self.assertEqual(len(res["pairs"]), len(cvp.EXPECTED_COLORS))
        for pair in res["pairs"]:
            self.assertRegex(pair["bg"], r"^#[0-9a-f]{6}$")
            self.assertRegex(pair["fg"], r"^#[0-9a-f]{6}$")

    def test_contrast_minimum(self):
        res = cvp.check_colors()
        for pair in res["pairs"]:
            self.assertGreaterEqual(
                pair["contrast"], cvp.MIN_CONTRAST,
                msg="%s contrast %.3f < %.1f" % (pair["selector"], pair["contrast"], cvp.MIN_CONTRAST))

    def test_pagination_deterministic(self):
        res = cvp.check_pagination()
        self.assertEqual(res["status"], "PASS", msg="VP-04 errors: %r" % res["errors"])
        self.assertTrue(res["offsets_match_rerun"])
        self.assertTrue(res["offsets_match_after_settings_restore"])
        self.assertGreater(res["page_count"], 0)

    def test_page_turn_timing_bound(self):
        res = cvp.check_timing()
        self.assertEqual(res["status"], "PASS", msg="VP-05 errors: %r" % res["errors"])
        self.assertLessEqual(res["p95_ms"], cvp.PAGE_TURN_P95_BUDGET_MS)

    def test_ssim_blocked_marker(self):
        res = cvp.check_ssim()
        self.assertEqual(res["id"], "VP-03")
        self.assertEqual(res["status"], "BLOCKED")
        self.assertIn("desktop", res["reason"].lower())

    def test_json_report_written(self):
        exit_code = cvp.main()
        self.assertEqual(exit_code, 0)
        with open(cvp.REPORT_PATH, encoding="utf-8") as fh:
            report = json.load(fh)
        self.assertTrue(report["headless"])
        for vp_id in ("VP-01", "VP-02", "VP-03", "VP-04", "VP-05"):
            self.assertIn(vp_id, report["results"])
            self.assertIn(report["results"][vp_id]["status"], ("PASS", "FAIL", "BLOCKED"))
        self.assertEqual(report["results"]["VP-03"]["status"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
