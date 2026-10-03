"""Automated Xvfb launch smoke test for Aquile Reader.

Verifies:
- Clean launch under Xvfb with isolated XDG_DATA_HOME
- Absence of Adwaita-ERROR or SIGABRT
- Screen rendering and PNG screenshot capture (>1000 bytes)
- Graceful shutdown upon SIGTERM
"""
import os
import sys
import unittest
import tempfile
import subprocess
import shutil
import time

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


class TestXvfbLaunchSmoke(unittest.TestCase):
    """Smoke test asserting application launch and window rendering under Xvfb."""

    @classmethod
    def setUpClass(cls):
        # 1. Locate toolchain
        toolchain_bin = "/tmp/opencode/xvfb-pkgs/root/usr/bin"
        toolchain_lib = "/tmp/opencode/xvfb-pkgs/root/usr/lib/x86_64-linux-gnu"

        path = os.environ.get("PATH", "")
        if os.path.exists(toolchain_bin):
            path = f"{toolchain_bin}:{path}"

        ld_path = os.environ.get("LD_LIBRARY_PATH", "")
        if os.path.exists(toolchain_lib):
            ld_path = f"{toolchain_lib}:{ld_path}"

        cls.env = os.environ.copy()
        cls.env["PATH"] = path
        cls.env["LD_LIBRARY_PATH"] = ld_path
        cls.env["GDK_BACKEND"] = "x11"
        cls.env.pop("WAYLAND_DISPLAY", None)

        # Check required binaries
        for binary in ["Xvfb", "xwd", "xwdtopnm", "pnmtopng"]:
            if not shutil.which(binary, path=path):
                raise unittest.SkipTest(f"Missing required toolchain binary: {binary}")

        # Check or start Xvfb server
        cls.xvfb_proc = None
        cls.display = cls.env.get("AQUILE_TEST_DISPLAY", ":99")

        # Test if target display is active
        res = subprocess.run(
            ["xwd", "-root", "-silent", "-out", "/dev/null"],
            env={**cls.env, "DISPLAY": cls.display},
            capture_output=True,
        )
        if res.returncode != 0:
            cls.xvfb_proc = subprocess.Popen(
                ["Xvfb", cls.display, "-screen", "0", "1280x800x24", "-noreset"],
                env=cls.env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            # Wait up to 3 seconds for Xvfb readiness
            ready = False
            for _ in range(30):
                time.sleep(0.1)
                chk = subprocess.run(
                    ["xwd", "-root", "-silent", "-out", "/dev/null"],
                    env={**cls.env, "DISPLAY": cls.display},
                    capture_output=True,
                )
                if chk.returncode == 0:
                    ready = True
                    break
            if not ready:
                if cls.xvfb_proc:
                    cls.xvfb_proc.kill()
                raise unittest.SkipTest(f"Failed to start responsive Xvfb on {cls.display}")

        cls.env["DISPLAY"] = cls.display

    @classmethod
    def tearDownClass(cls):
        if cls.xvfb_proc:
            cls.xvfb_proc.terminate()
            try:
                cls.xvfb_proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                cls.xvfb_proc.kill()

    def test_application_launches_and_renders_cleanly(self):
        """Assert app starts without crash, maps UI, allows screenshot, and shuts down."""
        with tempfile.TemporaryDirectory(prefix="aqtest-smoke-") as tmpdir:
            run_env = self.env.copy()
            run_env["XDG_DATA_HOME"] = os.path.join(tmpdir, "data")
            run_env["XDG_CONFIG_HOME"] = os.path.join(tmpdir, "config")
            run_env["XDG_CACHE_HOME"] = os.path.join(tmpdir, "cache")
            os.makedirs(run_env["XDG_DATA_HOME"], exist_ok=True)

            launcher_path = os.path.join(REPO_ROOT, "run_aquile.py")
            proc = subprocess.Popen(
                [sys.executable, launcher_path],
                env=run_env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            try:
                # Wait 3 seconds for window allocation and mapping
                time.sleep(3.0)

                # 1. Assert application did not crash
                poll_code = proc.poll()
                self.assertIsNone(
                    poll_code,
                    f"Application crashed prematurely on launch with exit code {poll_code}",
                )

                # 2. Capture screenshot
                xwd_path = os.path.join(tmpdir, "shot.xwd")
                png_path = os.path.join(tmpdir, "shot.png")

                res_xwd = subprocess.run(
                    ["xwd", "-root", "-silent", "-out", xwd_path],
                    env=run_env,
                    capture_output=True,
                )
                self.assertEqual(res_xwd.returncode, 0, "xwd screenshot capture failed")

                with open(png_path, "wb") as f_png:
                    p_xwd = subprocess.Popen(
                        ["xwdtopnm", xwd_path],
                        env=run_env,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.DEVNULL,
                    )
                    p_png = subprocess.Popen(
                        ["pnmtopng"],
                        env=run_env,
                        stdin=p_xwd.stdout,
                        stdout=f_png,
                        stderr=subprocess.DEVNULL,
                    )
                    p_xwd.stdout.close()
                    p_png.communicate()
                    p_xwd.wait()

                self.assertTrue(os.path.exists(png_path), "Screenshot PNG was not generated")
                png_size = os.path.getsize(png_path)
                self.assertGreater(
                    png_size, 1000, f"Screenshot file too small ({png_size} bytes); window unpainted"
                )

            finally:
                # 3. Clean process termination
                if proc.poll() is None:
                    proc.terminate()
                    try:
                        stdout, stderr = proc.communicate(timeout=5.0)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        stdout, stderr = proc.communicate(timeout=2.0)
                else:
                    stdout, stderr = proc.communicate()

            # 4. Assert absence of fatal errors in output
            self.assertNotIn("Adwaita-ERROR", stderr)
            self.assertNotIn("SIGABRT", stderr)
            self.assertNotIn("gtk_window_set_titlebar() is not supported", stderr)
            self.assertIn(proc.returncode, (0, -15, 143), f"Unexpected exit code: {proc.returncode}")


if __name__ == "__main__":
    unittest.main()
