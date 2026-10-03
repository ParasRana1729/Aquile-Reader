# UX Maturity Plan v3 — test-first road to Aquile parity

Status: implemented 2026-10-03. Full suite: 317/317 pass
(263 prior + 21 WP-A + 19 WP-B + 14 WP-C).

## 5. Results (red → green record)

- WP-A: RED `ModuleNotFoundError: icon_loader` (8 errors) → GREEN 21/21.
  Shipped `data/icons/*.svg` (8 original glyphs), path-based loader, no
  theme dependence. Regression pins: exact Prince filename cleanup, card
  sizes, dc:title preference.
- WP-B: RED `No module named titlebar` (2 errors) → GREEN 19/19.
  `AquileTitleBar` (START+END WindowControls, dynamic title), app wires
  `"<Book> - Aquile Reader"` / `"Aquile Reader"`; RGBA translucent chrome +
  transparency math in `titlebar.py`, stylesheet rules appended.
- WP-C: RED vocabulary mismatch + missing fields (2 failures, 16 errors) →
  GREEN 14/14. `AppSettings.accent`/`transparency`, schema v4 additive
  migration, shared `PAGE_THEMES`/`ACCENT_THEMES` (turquoise #009688,
  vineyard, darkside, clearsky, pulpyorange), settings dialog + reader
  popover share identical objects.
- Main: stale version pins 3→4 in two test files; accent/transparency applied
  at startup from persisted settings. E2E + G2 suites unaffected.

## 1. Defect diagnosis (screenshot → root cause)

| # | Symptom | Root cause | Fix WP |
| --- | --- | --- | --- |
| D1 | Rail icons invisible (empty slots, one red outline) | Theme-icon names missing on the user's icon theme; we probed only ours. Any `has_icon` miss renders nothing/broken. | WP-A: ship our own SVG glyphs, load by file path, zero theme dependence |
| D2 | No minimize / maximize / close | Main window has no title bar at all (we removed the HeaderBar, set only `set_title`). GNOME CSD then shows no controls. B0 has a full title bar (`"<Book> - Aquile Reader"`). | WP-B: slim custom title bar with app title + Gtk.WindowControls |
| D3 | "Themes can't be changed" | Two theme systems disagree: Settings dialog offers Light/Dark/Sepia (`settings.theme` = light/dark/sepia) while the reader popover writes white/silver/sepia/night/solarized/custom; page-theme CSS exists but nothing visibly re-skins the app chrome; no app color themes (Vine Yard, Turquoise…) exist at all. | WP-C: single theme model (page theme + accent color theme), one settings UI, live-apply + persist |
| D4 | Flat, immature surfaces vs B0 acrylic/blur | Solid `#3A3A3A` everywhere, no translucency, gradients, or depth; no transparency control (B0: Personalization → transparent background + slider). | WP-B: translucent dark chrome (RGBA), subtle gradient, transparency slider persisted in settings |
| D5 | Home still looks wrong (giant tile, raw filename) | Partially fixed in v0.2.1 (card halign, title cleanup) but unverified visually: tile shows filename → this EPUB has no dc:title AND filename cleanup did not apply? `clean_display_title` title-cases only all-lower stems; `machiavelli-niccolo-the-prince-1985` is all-lower so it should have applied… unless the installed build predates the fix or metadata path differs. Needs a regression test pinning the exact string. | WP-A/WP-C tests pin exact expectations; verify in build |

## 2. Test-first matrix (write RED, then implement GREEN)

| Test file | What it pins | Key assertions |
| --- | --- | --- |
| `tests/test_ux_icons.py` | D1 | Every rail/toolbar icon resolves from shipped `data/icons/*.svg` by path (no `IconTheme.has_icon` dependence); loader falls back to text label, never empty; all 6 rail + 9 reader names present |
| `tests/test_ux_titlebar.py` | D2 | Main window contains a title bar with `Gtk.WindowControls` (start+end), title label updates to `"<Book> - Aquile Reader"` on open and `"Aquile Reader"` on library |
| `tests/test_ux_themes.py` | D3 | Single `AppSettings` theme vocabulary shared by settings dialog + reader popover; selecting each of White/Silver/Sepia/Night/Solarized/Custom applies the matching root CSS class and persists; accent themes (Turquoise/Vine Yard/…) change `--aquile-accent` + rail highlight |
| `tests/test_ux_transparency.py` | D4 | Transparency 0..100 persists; chrome CSS uses RGBA (parse stylesheet, assert `alpha(`/`rgba(` in rail/toolbar rules); slider bounds respected |
| `tests/test_ux_home_regression.py` | D5 | `clean_display_title("machiavelli-niccolo-the-prince-1985.epub") == "Machiavelli Niccolo The Prince 1985"`; card request size == COVER_SIZE(_LARGE); import path prefers dc:title, falls back to cleaned filename (integration via temp EPUB fixtures with/without metadata) |

Judge rule: each suite must FAIL before its fix and PASS after; paste both runs
into the commit message body. Full suite must stay 263+ green.

## 3. Work packages (disjoint write scopes for parallel workers)

- WP-A (icons + home regression): NEW `data/icons/*.svg` (original glyphs:
  home, library, collections, globe, chart, gear, plus, star), NEW
  `src/aquile/ui/icon_loader.py`, EDIT `aquile_shell.py` + `home_view.py`
  (icon loading only), NEW tests above (icons, home-regression).
- WP-B (title bar + translucency): EDIT `app.py` (title bar wiring only),
  NEW `src/aquile/ui/titlebar.py` (slim bar + WindowControls + transparency
  application), EDIT `style.css` (RGBA chrome only), NEW tests (titlebar,
  transparency).
- WP-C (theme unification): EDIT `domain/models.py` (+ `accent` field,
  default `turquoise`), `storage` migration v4 (additive, keeps data),
  `settings_dialog.py` + `reader_chrome.py` (shared vocabulary), NEW tests
  (themes). Must keep all existing settings tests passing.

Main agent then: wires accent/transparency application at startup, runs full
suite + judges red/green, rebuilds 4 artifacts, cuts v0.2.2-preview, updates
this doc with results.

## 4. Out of scope (stated honestly)

Real background-blur (acrylic) needs compositor support GTK cannot guarantee;
translucency + gradients is the portable approximation. Remote-cover lookup
(never silently fetch); filename cleanup stays until real metadata exists.
