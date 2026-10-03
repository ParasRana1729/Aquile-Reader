# G0 Authorization and Rights Dossier: Clean-Room Native Desktop Implementation

| Field | Value |
| --- | --- |
| Gate | G0 — Rights and access approval |
| Status | Approved for Clean-Room Native Desktop Route |
| Date | 2026-10-03 |
| Product authority | [PRD.md](../../PRD.md) §1 |
| Execution authority | [IMPLEMENTATION_PLAN.md](../../IMPLEMENTATION_PLAN.md) §5 (WP-01) |

## 1. Scope of Authorization

Per product owner directive (2026-10-03), this project proceeds under an **authorized clean-room native desktop implementation route**:
- **Goal:** Develop an independent native Linux desktop eBook reader for Ubuntu Desktop (24.04 LTS and 26.04 LTS, amd64, GNOME) delivering visual and behavioral parity with Aquile Reader's published user experience and reading workflow.
- **Delivery promise:** Complete support for local DRM-free eBook reading (EPUB, PDF, CBZ/CBR), two-column and one-column customized layouts, durable annotations (highlights, notes, bookmarks), library organization, reading statistics, and complete offline independence (`FR-01`–`FR-16`, `FR-20`, `UB-01`–`UB-10`, `VP-01`–`VP-05`, `NFR-01`–`NFR-07`).

## 2. Clean-Room Boundary and Intellectual Property Restrictions

To guarantee strict legal compliance with third-party intellectual property rights and published terms of service:
1. **No Upstream Code Reuse:** No decompilation, disassembly, reverse engineering, or source-code extraction of the proprietary Windows binary or packages is permitted. All implementation code in this repository must be original clean-room code.
2. **Asset Policy:**
   - Proprietary Windows application assets (branding logos, copyrighted iconography, licensed proprietary fonts) must not be extracted or embedded into this repository.
   - Application iconography will utilize standard Freedesktop / GNOME Adwaita icon naming and original SVG vector graphics.
   - Typography will utilize open-source metric-compatible typefaces available across standard Ubuntu distributions (e.g., Liberation, Noto, Cantarell, Inter) with explicit font fallback mappings.
3. **Services and Network Isolation:**
   - The application core must be fully operational offline (`FR-20`).
   - Proprietary Microsoft Store / UWP licensing services and undocumented cloud sync databases are out of bounds.
   - Catalog integrations will target open, standardized protocols (e.g., OPDS feeds, Project Gutenberg, Standard Ebooks).
   - Dictionary integrations will utilize open dictionary APIs or local dictionaries (`FR-13`).

## 3. Account and Reference Access Policy

- **Baseline Reference Evidence:** Visual geometry, layout flows, and keyboard shortcuts documented in `PRD.md` are derived from publicly accessible first-party documentation, published store feature lists, and non-invasive behavioral observation of running baseline instances on authorized Windows test devices.
- **Storage of Captures:** Reference screenshots and behavioral recordings must be stored in access-controlled development directories; no private personal data, telemetry tokens, or copyrighted book contents may be checked into public repositories.

## 4. Gate G0 Clearance

| Approval Dimension | Status | Notes |
| --- | --- | --- |
| Implementation Route | Approved | Clean-room native desktop implementation |
| IP & Asset Clearance | Approved | Original code + open-source assets/fonts only |
| Offline / Local Scope | Approved | Core DRM-free reading independent of proprietary services |
| Parity Spike Clearance | Approved | Authorization granted to execute WP-04 feasibility spikes |

**Exit Condition Met:** G0 is cleared to proceed with WP-00 fixture preparation and WP-04 technology parity spikes. Application scaffolding is deferred until WP-04 spike completion and G1 stack approval.
