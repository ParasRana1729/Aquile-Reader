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
