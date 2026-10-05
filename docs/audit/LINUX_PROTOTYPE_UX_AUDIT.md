# Comprehensive UX & Parity Audit: Linux Aquile Reader Implementation

**Audit Date:** 2026-10-05  
**Auditor Role:** Linux App UX Auditor  
**Reference Artifacts Analyzed:**
- Linux Implementation Screencast: `/home/paras/Videos/Screencasts/linux-aquile-reader.webm` (Frames `linux_001.png` – `linux_045.png`)
- Windows B0 Reference Screencast: `/home/paras/Videos/Screencasts/windows-aquile-reader.mp4` (Frames `win_001.png` – `win_055.png`)
- Linux Codebase: `src/aquile/ui/` (`aquile_shell.py`, `home_view.py`, `library_view.py`, `pdf_view.py`, `catalog_dialog.py`, `statistics_dialog.py`, `settings_dialog.py`, `style.css`)
- Normative Specifications: `PRD.md`, `AGENTS.md`, `docs/reference/B0/UI_RESEARCH.md`

---

## Executive Summary & Verdict

The current Linux implementation of **Aquile Reader** is a rudimentary, disjointed prototype that fundamentally misses the visual elegance, architectural structure, and interaction fluidity of the Windows B0 product. 

Rather than delivering the signature Windows Fluent Design aesthetic—defined by deep Mica/Acrylic translucency, dynamic wallpaper blurs, unified client-area titlebars, integrated full-page views, and graceful book-reading typography—the Linux build is an ad-hoc collection of stock GTK4/Libadwaita widgets wrapped in a sterile, flat light-gray `#F2F2F2` container. Major product hubs (Catalogs, Statistics, Settings) are erroneously implemented as jarring, floating modal dialogs (`Adw.Window` / `Adw.PreferencesWindow`) that completely break navigation flow and trap the user. Furthermore, the reader experience for PDFs mimics a basic document utility (akin to a barebones Evince clone with page spinners and zoom percentages) rather than an immersive, modern digital book reader with fluid continuous scrolling and adaptive themes.

**Parity Status:** **FAILED (G1 / VP-01–VP-05 Non-Compliant)**.  
The Linux build cannot be characterized as a faithful port; it is an unapproved, rough prototype requiring systematic structural refactoring.

---

## 1. Visual Aesthetic & Design Deficiencies

| Design Vector | Windows B0 Ground Truth (`win_*.png`) | Current Linux Implementation (`linux_*.png`) | Severity |
| :--- | :--- | :--- | :--- |
| **Materiality & Background** | **Mica / Acrylic Translucency**: Sophisticated wallpaper sampling with variable Gaussian blur, depth layering, and subtle texture tinting (`win_001`, `win_016`, `win_035`). | **Sterile Flat Gray**: Hardcoded `#F2F2F2` / `#FFFFFF` solid opaque background. Zero translucency, zero blur, completely flat and washed out (`linux_001`). | **Critical (VP-01)** |
| **Window Frame & Chrome** | Unified titlebar seamlessly blended into the app canvas with custom brand title and compact window controls (`win_001`). | Double-chrome conflict: A custom top titlebar (`AquileTitleBar`) stacked above an internal GTK HeaderBar (`Adw.HeaderBar`) in views like Library (`linux_018`). | **High (VP-02)** |
| **Color Schemes & Theming** | System-wide coherent palette (e.g., "Dark Side", "Vine Yard", "Clear Sky") with accent-tinted highlights, rich card surfaces, and synced controls. | Fragmented CSS classes. Changing theme accent in Settings only recolors the single active rail icon button, leaving the entire window canvas untouched (`linux_040`, `linux_045`). | **High (VP-03)** |
| **Visual Hierarchy & Depth** | Elevated book cards with soft multi-layer drop shadows, glowing hover rings, and smooth scale transitions (`win_001`, `win_054`). | Flat borders with negligible elevation (`box-shadow: 0 2px 8px alpha(black, 0.35)` on raw white containers); looks like a 2012 web card (`linux_001`). | **Medium (VP-04)** |

### Detailed Visual Findings
1. **Total Absence of Mica / Acrylic Backdrop:**
   In Windows Aquile Reader, the application creates a signature atmospheric reading environment by allowing desktop wallpaper textures to softly bleed through the window with dark Mica/Acrylic materials (`win_016`, `win_035`, `win_040`). The Linux application has completely replaced this with an abrasive `#F2F2F2` flat background (`src/aquile/ui/style.css:159`).
2. **Broken Accent Propagation:**
   In `linux_037.png` and `linux_040.png`, the user selects "Clear Sky" accent and "Silver" theme. In response, only the `.aquile-rail .rail-active` button changes its CSS background (`aquile_shell.py:146`). The rest of the interface (header, library rows, cards, background) remains completely unaware of the theme change.

---

## 2. Home Screen Architecture & Card Hierarchy

### Side-by-Side Architectural Discrepancy

```
WINDOWS B0 ARCHITECTURE (win_001.png):
┌───┬─────────────────────────────────────────────────────────────────────────────────┐
│ R │ Recent Reads               Open Library › │ Favourite Books         See more ›  │
│ A │ ┌──────────┐  ┌──────────┐                │                 ★                   │
│ I │ │ Featured │  │ Secondary│                │     Your favourite books would      │
│ L │ │   Hero   │  │   Book   │                │            appear here              │
│   │ │   Book   │  ├──────────┤                ├─────────────────────────────────────┤
│   │ │  Cover   │  │ Secondary│                │ Recently Added Books    See more ›  │
│   │ │  (Glow)  │  │   Book   │                │ ┌──────────┐                        │
│   │ └──────────┘  └──────────┘                │ └──────────┘                        │
└───┴─────────────────────────────────────────────────────────────────────────────────┘

LINUX PROTOTYPE DISASTER (linux_001.png):
┌───┬─────────────────────────────────────────────────────────────────────────────────┐
│ R │ Home                                                                        [+] │
│ A │ Recent Reads                                                                    │
│ I │ ┌──────────┐                                                                    │
│ L │ │[Raw Gray]│  <--- Massive empty white void                                      │
│   │ └──────────┘                                                                    │
│   │ Favourite Books                                                                 │
│   │                            No favourite books yet.                              │
│   │                                                                                 │
│   │ [Open Library ›]                                                   [See more ›] │
└───┴─────────────────────────────────────────────────────────────────────────────────┘
```

### Critical Flaws in Home Screen
1. **Collapsed Layout Grid (Two-Column vs Vertical Dump):**
   Windows B0 arranges the Home view into a balanced two-column hero dashboard: **Recent Reads** on the left with a primary featured book cover and adjacent stacked recent titles; **Favourite Books** and **Recently Added Books** neatly partitioned on the right.  
   The Linux implementation (`home_view.py:66-130`) throws everything into a single vertical `Gtk.Box`, leaving 80% of the display as an empty white wasteland.
2. **Amateurish Fallback Cover Tile:**
   In `linux_001.png`, the book card for *"The Prince"* renders as a dismal dark gray rectangle (`#4A4A4A`) with raw unwrapped filename text (`machiavelli-niccolo-the-prince-1985`) dumped into a label (`home_view.py:205`). In Windows B0 (`win_001.png`), even PDFs render full-fidelity cover previews with crisp typography and glowing border illumination.
3. **Misplaced Navigation Action Links:**
   On Windows, "Open Library ›" and "See more ›" are contextual header links positioned directly alongside their respective section titles ("Recent Reads" and "Favourite Books").  
   In Linux, the developer shoved both buttons into a detached footer bar (`home_view.py:114-130`) at the bottom corners of the screen, separated by an empty `spacer`. This is completely unintuitive and breaks visual continuity.
4. **Empty State Degradation:**
   Windows B0 provides an elegant magenta star glyph above the subtle text *"Your favourite books would appear here"*.  
   The Linux prototype renders a plain GTK label *"No favourite books yet."* in the dead center of the screen without an icon, illustration, or call to action.

---

## 3. Library View & Document Management

### Comparison Analysis (`win_018.png` vs `linux_018.png`)
1. **Flat `Gtk.ListBox` vs Visual Cover Shelves:**
   Windows Aquile Reader is celebrated for its warm, shelf-like cover grid with cream/paper background options, rich thumbnail artwork, and metadata overlays.  
   The Linux implementation (`library_view.py:114-117`) renders a stark, uninspiring GTK `boxed-list` row (`linux_018.png`). It looks like a generic system utility (such as GNOME Disk Usage Analyzer or Settings) rather than an eBook library.
2. **Double Headerbar Clutter:**
   Navigating to the Library view renders **two stacked headerbars**:
   - Top: `AquileTitleBar` with "Aquile Reader" and window min/max/close controls.
   - Second Bar: `Adw.HeaderBar` containing an import button, collections button, stats button, catalog globe, sync button, "My Local Library" subtitle, format dropdown, sort dropdown, and search entry.  
   This double-decker header layout wastes vertical space and looks entirely unpolished.
3. **Metadata Absurdity ("140 ch"):**
   In `linux_018.png`, the metadata subtext for a PDF reads:  
   `Unknown Author • PDF • Progress: 7% • 140 ch • 4521 KB`  
   The code blindly labels PDF pages as **chapters** (`140 ch`), exposing unformatted internal data structures to the end user.
4. **Missing Side Details Flyout:**
   Windows B0 includes an inspector pane showing high-resolution cover artwork, synopsis, reading pace, publisher, and genre tags. The Linux prototype completely omits this panel.

---

## 4. Reader Experience: The PDF/Viewer Canvas

### Viewer Canvas Flaws (`linux_004.png` – `linux_017.png` vs `win_005.png` – `win_015.png`)

1. **Evince-Style Document Utility vs Immersive Book Reader:**
   - In Windows Aquile Reader (`win_005.png`, `win_009.png`), reading a document immerses the user in the active theme (dark night mode, sepia, or paper). Document pages seamlessly integrate into the background with elegant serif typography ("23 of 239" in italics) and fluid controls.
   - In Linux (`linux_004.png`), the viewer immediately reverts to a crude Poppler/Cairo rasterizer: a giant stark-white page pasted onto a light-gray canvas, surrounded by a desktop document toolbar featuring "Fit Page", "Fit Width", raw zoom percentages ("216%", "464%"), and numeric spinboxes (`[ 3 ] / 140`).
2. **Lack of Continuous Scrolling & Fluid Transitions:**
   - As demonstrated in `win_009.png` and `win_012.png`, Windows Aquile Reader supports smooth continuous vertical scrolling where consecutive pages flow naturally into one another.
   - The Linux prototype (`pdf_view.py:189-195`) renders only **one single page at a time** into a `Gtk.Picture` widget. Advancing pages produces jarring, abrupt image swaps without transition animations, smooth momentum scrolling, or two-page spread rendering.
3. **Unstyled Margins and Canvas Padding:**
   The rendered page in `linux_007.png` sits rigidly in the viewport with uneven scan margins. There are no reading margin sliders, no background color inversion for PDF viewing, and no text selection handles.

---

## 5. "Dialogitis" Trap: Modals vs Integrated Pages

The single most egregious architectural flaw of the Linux prototype is its reliance on modal popup dialogs (`Adw.Window` / `Adw.PreferencesWindow`) for primary destinations that are full integrated views in Windows B0.

```
+---------------------------------------------------------------------------------------+
| ARCHITECTURAL COMPARISON: DESTINATION NAVIGATION                                     |
+---------------------------------------------------------------------------------------+
| Feature Hub     | Windows B0 Implementation            | Linux Prototype Blunder      |
+-----------------+--------------------------------------+------------------------------+
| Catalogs (OPDS) | Integrated Master-Detail page with   | Jarring Adw.Window modal     |
|                 | provider sidebar & store browser     | dialog with raw text entries |
|                 | (win_022.png)                        | (linux_022.png)              |
+-----------------+--------------------------------------+------------------------------+
| Statistics      | Dedicated Settings page with reading | Clunky Adw.Window dialog     |
| (Insights)      | streak cards & interactive bar chart | with 3x3 dark square tiles   |
|                 | (win_045.png)                        | (linux_027.png)              |
+-----------------+--------------------------------------+------------------------------+
| Reader Settings | Full-window master-detail settings   | Tiny 480x500 Adw.Preferences |
|                 | suite with live wallpaper previews   | modal dialog with stock rows |
|                 | (win_024.png, win_035.png)           | (linux_033.png)              |
+-----------------+--------------------------------------+------------------------------+
```

### Forensic Analysis of the Three Dialogs

#### A. Book Catalogs Dialog (`linux_022.png` vs `win_022.png`)
- **Windows B0:** A first-class navigation view. The left pane displays catalog sources (Gutenberg, Standard Ebooks, ManyBooks) with custom brand icons; the right pane is an integrated web/OPDS catalog explorer with navigation controls (`win_022`).
- **Linux Prototype:** Implemented as `CatalogDialog(Adw.Window)` (`catalog_dialog.py:53`). It opens a modal dialog that locks the main window, presenting a raw text entry field to "Paste an http(s) OPDS catalog URL", a clunky "Load Catalog" button, and an unstyled list of feeds. It looks like an internal debugging utility.

#### B. Reading Statistics Dialog (`linux_027.png` – `linux_031.png` vs `win_045.png`)
- **Windows B0:** Part of the integrated Settings experience under "Reading insights". Features beautiful streak summary cards ("Daily streak record", "Weekly streak record") and an interactive, animated monthly bar chart ("Reading trends over months") rendered directly over the Mica wallpaper.
- **Linux Prototype:** Implemented as `StatisticsDialog(Adw.Window)` (`statistics_dialog.py:41`). Pops up an awkward dialog containing eight dark-gray square tiles (`.stat-tile`) with harsh cyan numbers. Because there are only 8 tiles in a 3-column grid, the bottom-right spot is left awkwardly empty! The second tab ("Book Insights", `linux_029.png`) is a plain `Adw.PreferencesGroup` list truncated at the dialog boundary.

#### C. Reader Settings Dialog (`linux_033.png` – `linux_040.png` vs `win_024.png`, `win_035.png`)
- **Windows B0:** A comprehensive settings center. Features interactive ToggleSwitches ("Standardize margins", "Override text alignment", "ReadAloud auto-scroll"), visual theme palette swatches ("Vine Yard", "Dark Side", "Fresh Berry"), and a background transparency slider that adjusts window opacity in real-time.
- **Linux Prototype:** Implemented as a cramped `SettingsDialog(Adw.PreferencesWindow)` (`settings_dialog.py:26`). It reduces rich visual choices to standard text dropdowns (`Adw.ComboRow`) for themes ("White", "Silver", "Sepia", "Night", "Solarized") and font size sliders.

#### D. The Bizarre `_revert_rail()` Navigation Bug
In `src/aquile/app.py` lines 162–169 and 181–208:
```python
        elif page == "catalogs":
            self._open_catalogs()
        elif page == "statistics":
            self.show_statistics()
            self._revert_rail()
        elif page == "settings":
            self._open_settings()
```
When a user clicks "Catalogs", "Statistics", or "Settings" on the left navigation rail, the application presents the modal dialog and **immediately forces the left rail selection back to "Home"** behind the dialog! As soon as the modal is dismissed, the user finds themselves unexpectedly dumped back onto the Home screen. This completely breaks standard desktop navigational mental models.

---

## 6. Amateurish Prototype Friction Points Summary

1. **Window Sizing & Responsiveness:** Hardcoded default size of 1280x800 with non-responsive inner boxes; shrinking or maximizing leads to unbalanced empty areas.
2. **Missing Brand Identity:** Absence of the Aquile brand crest, custom typography, or polished vector iconography. Uses generic GNOME symbolic icons (`utilities-system-monitor-symbolic`, `emblem-documents-symbolic`).
3. **No Smooth View Transitions:** Zero animated page swaps between Home, Library, and Reader. Content snaps harshly into place.
4. **Crude PDF Engine Integration:** Single-page Cairo rendering without texture caching or background pre-rendering, resulting in noticeable flicker during page turns.
5. **No Visual Shelf or Cover Grid:** The library is incapable of displaying a visual grid of covers—the primary mode of modern digital book readers.

---

## 7. Requirement & Parity Traceability Matrix

| Requirement ID | Description | Linux Implementation Finding | Compliance Status |
| :--- | :--- | :--- | :--- |
| **FR-01** | Multi-Format Library & Management | Library is restricted to a flat `Gtk.ListBox`. Cover grid mode missing. PDF pages mislabeled as chapters ("140 ch"). | **FAILED** |
| **FR-06 / FR-07** | Fixed-Layout & PDF Rendering | Renders single static images via `Gtk.Picture`. Lacks continuous scroll, spread layout, and margin standardization. | **FAILED** |
| **FR-14** | OPDS Book Catalogs Discovery | Shunted into a barebones modal dialog with URL text boxes instead of an integrated catalog store. | **FAILED** |
| **FR-15** | Reading Statistics & Insights | Implemented as a floating dialog with an incomplete 3x3 tile grid. Interactive streak charts absent. | **FAILED** |
| **FR-16** | Reader Customization & Settings | Confined to an Adwaita Preferences modal. Dynamic transparency and visual theme swatch pickers missing. | **FAILED** |
| **VP-01** | App-Shell Geometry & Chromeless Layout | Mica/Acrylic wallpaper background missing; replaced with flat `#F2F2F2`. Double headerbars in Library. | **FAILED** |
| **VP-02** | Visual Typography & Cover Styling | Book covers fail to render properly on Home; fallback tile is a plain gray box with raw filename text. | **FAILED** |
| **VP-03** | Theme & Accent Coherence | Accent color changes fail to propagate across view canvases; only tints the single rail button. | **FAILED** |
| **UB-01** | Modern GNOME Wayland Integration | Modals break multi-window tiling and Wayland shell expectations. | **FAILED** |
| **AT-01** | Clean-Room Visual Parity Verification | Visual regression against B0 Windows goldens reveals complete structural divergence. | **FAILED** |

---

## 8. Actionable Architectural Remediation Roadmap

To elevate the Linux port from this amateurish prototype to an authentic, release-ready Aquile Reader implementation, the following architectural overhaul is required:

1. **Eliminate All Primary Modal Dialogs:**
   Refactor `CatalogDialog`, `StatisticsDialog`, and `SettingsDialog` into first-class `Gtk.Box` / `Adw.Bin` views hosted directly inside `AquileShell.stack`. Remove `_revert_rail()` hack.
2. **Implement the Fluid Mica / Acrylic Translucency Engine:**
   - Integrate Gaussian blur surface styling via CSS shaders or high-performance Cairo/Vulkan background compositing.
   - Support dynamic wallpaper sampling and transparency sliders matching Windows B0 Personalization.
3. **Rebuild the Home View Grid:**
   - Restore the two-column side-by-side architecture: Recent Reads hero + secondary stack on the left; Favourite Books and Recently Added on the right.
   - Restore inline section links ("Open Library ›", "See more ›") directly in section headers.
   - Implement authentic cover drop shadows and glowing border hover states.
4. **Transform Library into a Visual Shelf:**
   - Implement `Gtk.GridView` with high-resolution cover tiles, title/author overlay badges, and smooth hover scaling.
   - Add the collapsible right-hand book metadata inspector flyout.
   - Remove redundant stacked headerbars.
5. **Modernize the Reader Engine:**
   - Replace single-page `Gtk.Picture` swapping with a virtualized, continuously scrollable canvas supporting both vertical continuous scroll and multi-column spreads.
   - Apply reader color themes (Night, Sepia, Solarized) directly to document rendering surfaces.
   - Replace the generic PDF zoom toolbar with Aquile's minimal, elegant reading controls.

---
*Report compiled and verified against video frame evidence.*
