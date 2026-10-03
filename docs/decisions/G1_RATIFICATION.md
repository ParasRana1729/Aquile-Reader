# G1 Ratification: Baseline Freeze and Full-Parity Feasibility Approval

| Field | Value |
| --- | --- |
| Gate | G1 — Reference baseline freeze and feasibility approval |
| Status | Approved |
| Date | 2026-10-03 |
| Product authority | [PRD.md](../../PRD.md) §§4, 5, 10 |
| Execution authority | [IMPLEMENTATION_PLAN.md](../../IMPLEMENTATION_PLAN.md) §6 (WP-05) |
| Architecture decision | [ADR-0001](ADR-0001-CLEAN-ROOM-AND-STACK-EVALUATION.md) |

## 1. Ratification Scope

Following the clearance of Gate G0 ([docs/rights/G0_APPROVAL.md](../rights/G0_APPROVAL.md)) and the successful execution of the WP-04 Parity Spike suite ([docs/validation/WP04_PARITY_SPIKE_REPORT.json](../validation/WP04_PARITY_SPIKE_REPORT.json)), Gate G1 is formally ratified:
1. **Reference Target Specification:** Frozen based on Aquile Reader's published desktop UX, navigation structure, and two-column reading workflow specified in `PRD.md` §§4–5.
2. **Approved Implementation Stack:** Python 3 + GTK4 / Libadwaita with SQLite WAL storage, providing native GNOME integration, AT-SPI2 accessibility, zero external build dependencies, and robust persistence durability.
3. **Platform Scope:** Ubuntu 24.04 LTS and 26.04 LTS (amd64), default GNOME session on Wayland and supported X11 sessions, adhering to `UB-01`–`UB-10`.
4. **Offline Independence:** Local DRM-free library management and reading (EPUB, PDF, CBZ/CBR) operate with 100% offline autonomy without required accounts or external cloud dependencies (`FR-20`).

## 2. Gate Approvals

| Approval Dimension | Status | Approver Role | Evidence Reference |
| --- | --- | --- | --- |
| Baseline Specification | Approved | Product + Design | PRD §§4–5, candidate fixture register |
| Feasibility & Architecture | Approved | Engineering | ADR-0001, WP-04 spike results |
| Test Strategy & Fixtures | Approved | QA | WP-00 fixtures, SHA-256 registered |
| Clean-Room IP Boundaries | Approved | Legal + Engineering | G0 approval dossier |

## 3. Authorization to Proceed to Phase 2 (Gate G2 Preview)

With Gate G1 ratified, authorization is granted to begin Phase 2:
- **WP-06:** Application foundation, package layout, and test suite.
- **WP-07:** Local data safety, application shell, and library management.
- **WP-08:** Canonical two-column EPUB reader, typography controls, and durable annotation engine.
- **WP-09:** Early Ubuntu desktop integration and internal preview verification.
