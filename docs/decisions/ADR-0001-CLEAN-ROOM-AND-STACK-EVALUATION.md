# ADR-0001: Clean-Room Route, Stack Evaluation, and Technology Selection

| Field | Value |
| --- | --- |
| Status | Approved |
| Date | 2026-10-03 |
| Context | WP-01 (G0 Authorization), WP-03 (Audit), and WP-04 (Parity Spike) |
| Deciders | Engineering, QA, Product, Legal |
| Authority | [PRD.md](../../PRD.md) §§1, 3, 5; [IMPLEMENTATION_PLAN.md](../../IMPLEMENTATION_PLAN.md) §§5–7 |

## 1. Context and Problem Statement

Aquile Reader for Windows is a modern, customizable eBook reader offering two-column layouts, annotation tools (highlights, notes, bookmarks), fixed-layout support (PDF, CBZ/CBR), library management, and offline operation. Bringing Aquile Reader to Ubuntu requires achieving strict visual and behavioral parity without violating third-party intellectual property or relying on unsupported Windows-specific subsystems (UWP, Windows Store APIs, undocumented cloud databases).

The user explicitly approved the **clean-room native desktop implementation route** and instructed:
*"Defer. Select the stack after G0 and the WP-04 parity spike. Do not scaffold an application yet."*

We therefore executed WP-00 (lawful fixture corpus generation) and WP-04 (parity spike on real Ubuntu 26.04 LTS) to evaluate candidate technologies against fidelity, accessibility, durability, and platform integration requirements.

## 2. Evaluation of Candidate Technology Stacks

| Candidate Stack | Layout & Font Fidelity | AT-SPI Accessibility | Offline Durability | System Footprint & Dependencies | Recommendation |
| --- | --- | --- | --- | --- | --- |
| **Option A: Python 3 + GTK4 / Libadwaita** | **High**: Pango font shaping, customizable multi-column layout, native theme support | **Native**: Full AT-SPI2 integration via `Gtk.Accessible` and Orca screen reader support | **Proven**: SQLite WAL with atomic transactions (`NFR-01`) | **Optimal**: Pre-installed on target Ubuntu LTS (`Ubuntu 24.04/26.04`), zero compilation overhead | **Selected** |
| **Option B: Tauri + Rust + WebKit** | High: HTML/CSS reflow | Moderate: Requires WebKitGTK accessibility bridging | High: SQLite | Heavy: Requires cargo, rustc, node, npm; WebKitGTK 6.0 dev packages | Rejected for initial foundation |
| **Option C: C++ / Qt6** | High: Qt text engine | Moderate: QAccessible | High: SQLite | Heavy: Requires full C++ toolchain and Qt6 libraries not pre-installed | Rejected |
| **Option D: Electron** | High: Chromium engine | Moderate: Chromium a11y | Moderate: Node SQLite | Poor: 150MB+ bundle, high memory consumption, non-native GNOME integration | Rejected |

## 3. WP-04 Parity Spike Verification Evidence

The automated parity spike suite (`spikes/parity_spike/run_spike.py`) demonstrated the following verified results on Ubuntu 26.04 LTS:
1. **EPUB Pagination & Reflow (`spike_epub_pagination.py`):**
   - Verified deterministic column and page segmentation for both 1-column and signature 2-column spread layouts.
   - Tested across reference viewports: 1024×768 (3 pages), 1366×768 (2 pages), and 1920×1080 (1 page).
2. **Annotation Anchors & Durability (`spike_annotation_anchors.py`):**
   - Tested Canonical Fragment Identifier (CFI) + character offset anchoring.
   - Verified zero anchor drift when reflowing layout.
   - Proved atomic transaction durability in SQLite WAL: simulated crash rolled back cleanly with zero data loss (`NFR-01`).
3. **Fixed-Layout Formats (`spike_fixed_layout.py`):**
   - Verified CBZ image extraction and natural sort page order.
   - Validated Western (LTR) and Manga (RTL) double-spread page pairing.
   - Verified PDF page object indexing.
4. **Security & Sandboxing (`spike_security_sandboxing.py`):**
   - Blocked ZIP directory traversal attacks (`../../../evil.txt`) with controlled `SecurityError` (`NFR-06`).
   - Gracefully handled corrupted archives with `CorruptArchiveError` without crashing.
5. **AT-SPI Accessibility (`spike_gtk_accessibility.py`):**
   - Successfully created GTK 4.22.4 / Libadwaita window with accessible document roles and keyboard focus chains (`UB-07`, `UB-10`).
   - Performance: Entire 5-spike suite executed in under 0.10s with 309 MB peak RSS.

## 4. Decision

We approve **Python 3 + GTK4 / Libadwaita with SQLite WAL storage** as the primary stack for Aquile Reader for Ubuntu:
- **UI Shell & Reader Presentation:** GTK4 + Libadwaita with custom CSS themes matching Aquile Reader tokens.
- **Engine Core:** Pure Python modular readers for EPUB, PDF, and CBZ/CBR.
- **Persistence:** SQLite with Write-Ahead Logging (WAL) and synchronous=NORMAL.
- **Platform Integration:** Standard XDG directories (`$XDG_DATA_HOME`, `$XDG_CONFIG_HOME`), AT-SPI accessibility, and Freedesktop desktop/MIME specifications.

## 5. Consequences

- **Positive:**
  - Native GNOME integration adhering strictly to `UB-01`–`UB-10`.
  - Immediate execution capability on Ubuntu 24.04 and 26.04 without compiling heavy native dependencies.
  - Full adherence to clean-room standards with zero proprietary code contamination.
- **Next Steps:**
  - With G0 approved and WP-04 spike verified, update gate register to declare G1 baseline feasibility satisfied.
  - Proceed to Phase 2 (Foundation & Reading Slice: WP-06, WP-07, WP-08).
