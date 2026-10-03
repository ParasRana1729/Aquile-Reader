#!/usr/bin/env python3
"""
verify_visual_parity.py — Captures and verifies visual screenshots of Aquile Reader
under Xvfb :99 for Home, Reader (canonical + missing-metadata EPUB), and Settings.
"""

import os
import sys
import time
import subprocess
import tempfile
import shutil

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

XVFB_BIN = "/tmp/opencode/xvfb-pkgs/root/usr/bin"
os.environ["PATH"] = f"{XVFB_BIN}:" + os.environ.get("PATH", "")
os.environ["LD_LIBRARY_PATH"] = "/tmp/opencode/xvfb-pkgs/root/usr/lib/x86_64-linux-gnu"
os.environ["DISPLAY"] = os.environ.get("AQUILE_TEST_DISPLAY", ":99")
os.environ["GDK_BACKEND"] = "x11"
os.environ.pop("WAYLAND_DISPLAY", None)

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib, Gdk

from src.aquile.app import AquileReaderApp
from src.aquile.reader.epub_parser import EpubParser

BUILD_SHOT_DIR = os.path.join(REPO_ROOT, "build", "screenshots")
AGENT_SHOT_DIR = os.path.join(REPO_ROOT, ".agents", "teamwork", "worker_m2_r2", "screenshots")
os.makedirs(BUILD_SHOT_DIR, exist_ok=True)
os.makedirs(AGENT_SHOT_DIR, exist_ok=True)


def pump_events(seconds=1.0):
    ctx = GLib.MainContext.default()
    end_time = time.time() + seconds
    while time.time() < end_time:
        while ctx.iteration(False):
            pass
        time.sleep(0.05)


def capture_screenshot(base_name: str) -> str:
    pump_events(1.0)
    temp_xwd = tempfile.NamedTemporaryFile(suffix=".xwd", delete=False).name
    try:
        cmd_xwd = f"xwd -root -silent -out {temp_xwd}"
        subprocess.run(cmd_xwd, shell=True, check=True)
        
        for out_dir in [BUILD_SHOT_DIR, AGENT_SHOT_DIR]:
            png_path = os.path.join(out_dir, f"{base_name}.png")
            cmd_convert = f"xwdtopnm {temp_xwd} 2>/dev/null | pnmtopng > {png_path}"
            subprocess.run(cmd_convert, shell=True, check=True)
            size = os.path.getsize(png_path)
            assert size > 1000, f"Screenshot {png_path} too small ({size} bytes)"
            print(f"Captured: {png_path} ({size} bytes)")
    finally:
        if os.path.exists(temp_xwd):
            os.remove(temp_xwd)
    return os.path.join(BUILD_SHOT_DIR, f"{base_name}.png")


def main():
    fixtures_dir = os.path.join(REPO_ROOT, "fixtures")
    canonical_epub = os.path.join(fixtures_dir, "canonical-text.epub")
    missing_meta_epub = os.path.join(fixtures_dir, "missing-metadata-coverless.epub")

    assert os.path.exists(canonical_epub), f"Missing {canonical_epub}"
    assert os.path.exists(missing_meta_epub), f"Missing {missing_meta_epub}"

    temp_dir = tempfile.mkdtemp(prefix="aq-visual-")
    try:
        os.environ["XDG_DATA_HOME"] = os.path.join(temp_dir, "data")
        os.environ["XDG_CONFIG_HOME"] = os.path.join(temp_dir, "config")
        os.environ["XDG_CACHE_HOME"] = os.path.join(temp_dir, "cache")
        os.makedirs(os.environ["XDG_DATA_HOME"], exist_ok=True)
        db_path = os.path.join(os.environ["XDG_DATA_HOME"], "aquile.db")

        print("Initializing AquileReaderApp in isolated profile...")
        app = AquileReaderApp(db_path=db_path)
        app.register()
        app.activate()
        app.window.present()
        pump_events(1.5)

        # 1. Home View (Empty)
        print("1. Capturing Home view (empty)...")
        capture_screenshot("01_home_empty")

        # 2. Import canonical EPUB
        print(f"Importing {canonical_epub}...")
        app.library_view.import_file(canonical_epub)
        pump_events(1.0)

        # Import missing metadata EPUB
        print(f"Importing {missing_meta_epub}...")
        app.library_view.import_file(missing_meta_epub)
        pump_events(1.0)

        # Refresh and switch to Home view
        app.show_library()
        app.shell.set_page("home")
        app.home_view.refresh()
        pump_events(1.5)

        # 2. Home View with books
        print("2. Capturing Home view with imported books...")
        capture_screenshot("02_home_with_books")

        # 3. Reader View (Canonical Text)
        books = app.book_repo.list_all()
        canonical_book = next((b for b in books if "Canonical" in b.title), None)
        assert canonical_book is not None, "Canonical book not found in database"
        print(f"Opening '{canonical_book.title}' in Reader...")
        app.open_book(canonical_book)
        pump_events(2.0)
        print("3. Capturing Reader view (Canonical Text)...")
        capture_screenshot("03_reader_canonical")

        # 4. Reader View (Missing Metadata Coverless)
        missing_book = next((b for b in books if b.id != canonical_book.id), None)
        assert missing_book is not None, "Missing metadata book not found in database"
        print(f"Opening '{missing_book.title}' in Reader...")
        app.open_book(missing_book)
        pump_events(2.0)
        print("4. Capturing Reader view (Missing Metadata Coverless)...")
        capture_screenshot("04_reader_missing_metadata")

        # Return to library
        app.show_library()
        pump_events(1.0)

        # 5. Settings Dialog
        print("Opening Settings dialog...")
        app._open_settings()
        pump_events(2.0)
        print("5. Capturing Settings view...")
        capture_screenshot("05_settings_dialog")

        print("\nAll visual verification screenshots captured successfully!")

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
