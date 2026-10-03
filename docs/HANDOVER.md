# HANDOVER — Aquile Reader Ubuntu (v0.2.2 → crash-fix in progress)

Date: 2026-10-03. Last pushed commit: `c057cf9`. **DO NOT cut a release and
DO NOT `git push` until the crash below is fixed AND verified under Xvfb.**
(User instruction: test first, no more releases/pushes until proven.)

## 1. What broke (user-reported, reproduced locally)

Installed 0.2.2 from `.deb` crashes on launch. Ubuntu crash dialog:
`run_aquile.py crashed with SIGABRT in gtk_widget_allocate()`.
Root cause (reproduced under Xvfb, log `/tmp/opencode/app-x.log` — ephemeral):
`attach_titlebar()` calls `window.set_titlebar()`, and libadwaita windows
**fatally abort** on `gtk_window_set_titlebar()`:
- `Adw.ApplicationWindow` → `Adwaita-ERROR ... not supported` → SIGABRT
- `Adw.Window` → same abort (verified 16:39 log line)
Headless unit tests never caught it: they skip window work with no display,
and the abort only fires with a real display.

## 2. Fix direction (DECIDED, partially implemented, UNCOMMITTED)

Do NOT use `set_titlebar()` on any Adwaita window. Correct libadwaita pattern:
pack the title bar as the first child of the window content.
`Gtk.WindowControls` works in content (renders + operates on ancestor window).

Uncommitted working-tree changes (`git status`: 3 modified files):
- `src/aquile/app.py` — window class `Adw.ApplicationWindow` →
  `Adw.Window` (type annotation + constructor + comment); `_create_main_window`
  builds `outer = Gtk.Box(vertical)` = [titlebar, shell] and
  `set_content(outer)` (replaces `set_content(self.shell)`).
- `src/aquile/ui/titlebar.py` — `attach_titlebar()` refuses
  `AdwApplicationWindow` (returns False) instead of aborting the process.
- `docs/validation/VISUAL_PARITY.json` — rerun timestamp artifact, ignore.

STILL NEEDED to complete the fix:
1. `AquileTitleBar` is constructed but only `attach_titlebar` (now a refuser)
   was ever called — verify `app.titlebar` exists and is packed (see edit
   above; if `self.titlebar` wiring is absent, add it in `_create_main_window`).
2. Update `tests/test_ux_titlebar.py::TestTitleBarAppWiring` — it asserts
   `app.window.get_titlebar()`; must assert the bar is the first content
   child instead. Also un-skip it under Xvfb (it skips headless).
3. Add a permanent Xvfb launch smoke test (see §3) so this class of bug can
   never ship again; wire it into the pre-release checklist.
4. Re-run FULL suite, launch under Xvfb, screenshot Home + open reader,
   THEN commit/push/rebuild/release.

## 3. GUI testing harness (NEW — use this, screenshots required, not optional)

Previous sessions had no display testing; that is how a launch crash shipped.
Toolchain is bootstrapped at `/tmp/opencode/xvfb-pkgs/root/usr/bin`
(Xvfb, xwd, xwdtopnm, pnmtopng + libnetpbm11t64). Re-bootstrap:
`apt-get download xvfb x11-apps netpbm libnetpbm11t64 && dpkg -x *.deb root/`.

```sh
export PATH=/tmp/opencode/xvfb-pkgs/root/usr/bin:$PATH
export LD_LIBRARY_PATH=/tmp/opencode/xvfb-pkgs/root/usr/lib/x86_64-linux-gnu
Xvfb :99 -screen 0 1280x800x24 >/tmp/opencode/xvfb.log 2>&1 &
sleep 2
# launch (fresh profile! reuse of a dirty XDG_DATA_HOME hides migration bugs)
rm -rf /tmp/aqtest-home && mkdir -p /tmp/aqtest-home
DISPLAY=:99 XDG_DATA_HOME=/tmp/aqtest-home timeout 40 \
  python3 run_aquile.py >/tmp/opencode/app-x.log 2>&1 &
sleep 10
# screenshot
DISPLAY=:99 xwd -root -silent -out /tmp/opencode/shot.xwd
xwdtopnm /tmp/opencode/shot.xwd 2>/dev/null | pnmtopng > /tmp/opencode/shot.png
# read /tmp/opencode/shot.png with the Read tool (it renders images)
# pass criteria: process alive, no Adwaita-ERROR/SIGABRT in app-x.log,
#   window visible with rail + title bar controls
```

 Broadway (`broadwayd`) was tried and ABANDONED (socket/display mismatch,
 Gtk never initializes) — do not retry; use Xvfb.

## 4. Repo state and conventions

- Tests: 317/317 pass headless (`python3 -m unittest discover tests`).
  Plan of record: `docs/UX_PLAN_V3.md` (add §6 results when done).
  Research: `docs/reference/B0/UI_RESEARCH.md`. Tests-first is mandatory:
  every fix needs RED→GREEN evidence quoted (see UX_PLAN_V3 §5 precedent).
- `dist/` is gitignored; release artifacts attach to GitHub Releases only.
- Packaged `data/icons/*.svg` MUST stay staged in all 4 build scripts
  (deb/tarball/appimage/rpm) — `icon_loader.find_icon_dir()` covers repo,
  /usr/share, /usr/local, tarball layouts. If you add icons, add SVGs +
  NAMES entries + extend `tests/test_ux_icons.py`.
- Settings schema is v4 (`AppSettings.accent`/`transparency`); stale version
  pins bit twice — after any schema bump, grep tests for hardcoded versions.
- Known cosmetic debt (user screenshots): tile for coverless EPUBs,
  reader/annotation dialogs still Adwaita-default, no true background blur
  (portable approximation only — see UX_PLAN_V3 §4).

## 5. Verification Results (Milestones M1, M2, M3)

Verification conducted on 2026-10-03 under Linux / Xvfb :99 (1280x800x24) with isolated `XDG_DATA_HOME` profiles and `GDK_BACKEND=x11`.

### 5.1 Defect Remediation & Hardening Summary
1. **Titlebar-as-Content Architecture (R1 / M1)**:
   - Eliminated `attach_titlebar()` and `set_titlebar()` calls on libadwaita windows (`Adw.Window` / `Adw.ApplicationWindow`).
   - Packed `AquileTitleBar` as first content child in vertical `Gtk.Box([self.titlebar, self.shell])`.
   - Hardened `attach_titlebar()` to refuse all `Adw` window classes including subclasses via MRO inspection (`any("Adw" in getattr(cls, "__module__", "") for cls in type(window).__mro__)`).
2. **Permanent Xvfb Smoke Test Harness (R2 / M2)**:
   - Created `scripts/run_xvfb_smoke.sh` (executable): self-contained CLI runner resolving toolchain binaries (`Xvfb`, `xwd`, `xwdtopnm`, `pnmtopng`), managing isolated XDG environments, ensuring `GDK_BACKEND=x11` and unsetting `WAYLAND_DISPLAY`, verifying process stability, capturing XWD/PNG screenshots (>1000 bytes check), gracefully shutting down via `SIGTERM`, and verifying zero `SIGABRT`/`Adwaita-ERROR`.
   - Created `tests/test_launch_smoke.py`: automated discoverable `unittest.TestCase` executing the launch smoke test in ~3.1s with 100% reliability.
3. **Defect Fixes & Missing Metadata Fixture (R3 / M3)**:
   - **Defect V1 (Pango markup parsing error)**: Escaped ampersand in `src/aquile/ui/settings_dialog.py:42` (`title="Appearance &amp; Theme"`), restoring the section header in settings.
   - **Defect V2 (Settings live appearance updates)**: Wired `on_changed_callback=lambda s: self._apply_saved_appearance()` in `src/aquile/app.py:202`.
   - **Defect V3 (Gtk-CRITICAL gtk_stack_remove)**: Cleaned duplicate remove on `self.nav_stack` in `open_book()` and guarded stack child removal in `AquileShell.add_page()` and `show_library()`.
   - **Fixture**: Created `fixtures/missing-metadata-coverless.epub` (and updated `scripts/generate_fixtures.py`). Verified clean parsing via `EpubParser` and automated test coverage in `tests/test_epub_and_pagination.py`.

### 5.2 Visual Verification Findings
Screenshots captured under Xvfb `:99` with isolated profiles and verified against `docs/reference/B0/UI_RESEARCH.md`:
- `build/screenshots/01_home_empty.png` (12,844 B): Slim dark title bar with window controls, sharp SVG rail icons (teal Home active), clean empty state placeholders and footer links.
- `build/screenshots/02_home_with_books.png` (20,127 B): Home view showing asymmetric card sizing (`COVER_SIZE_LARGE` = 184x256 for first card, `COVER_SIZE` = 128x180 for second), dark fallback cover tiles with wrapped titles, and clean author lines.
- `build/screenshots/03_reader_canonical.png` (66,448 B): Window title `"Canonical Text Fixture - Aquile Reader"`, dark reader toolbar (9 white icons), two-column reading canvas, and footer status bar (`Chapter 1 » Page 1`, `1/1`, `33.30%`).
- `build/screenshots/04_reader_missing_metadata.png` (46,020 B): Window title `"Missing Metadata Coverless - Aquile Reader"`, clean fallback title derivation, two-column layout, and accurate pagination.
- `build/screenshots/05_settings_dialog.png` (19,961 B): Settings modal with restored `"Appearance & Theme"` header, theme/accent combo rows, and typography sliders.

### 5.3 Test Suite Status
- **Test Command**: `python3 -m unittest discover tests`
- **Result**: `Ran 320 tests in ~9.7s — OK` (320 tests passing, 0 failures, 0 errors).
- Zero `SIGABRT`, zero `Adwaita-ERROR`, zero `Gtk-CRITICAL` assertions.

