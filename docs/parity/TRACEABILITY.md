# Requirement and B0 traceability — working draft

| Field | Value |
| --- | --- |
| Status | WP-00 preparation; preliminary links only; no B0 feature/state inventory or test result is established |
| Authority | [PRD.md](../../PRD.md) §§4–10; [IMPLEMENTATION_PLAN.md](../../IMPLEMENTATION_PLAN.md) §§3, 11 |
| Owner | QA owner not assigned |

This is a planning crosswalk, not a claim of implementation, coverage completion, or approval. The PRD's explicit FR-to-AT links and the plan's initial grouped coverage index are discovery seeds. Refine every link against authorized, frozen B0 and the approved test procedures at G1. Conditional requirements are neither confirmed nor non-applicable until evidence supports that decision.

## Status vocabulary

- **Work item:** `not started`, `in progress`, `blocked`, `complete`.
- **Check result:** `passed`, `failed`, `blocked`, `not run`, or evidenced `not applicable`.
- Documentation, a mock, or an intended test is not a pass. G0/G1 remain blocked until their separate exit evidence and approvals are recorded.

## Initial requirement-to-acceptance-test crosswalk

FR links below are copied from PRD §6. Broader group links are from IMPLEMENTATION_PLAN.md §11 and remain provisional planning links, not a completed per-requirement test mapping. Test names and pass conditions are defined in PRD §10.

| Requirement(s) | Initial acceptance-test link(s) | Source / qualification | Result |
| --- | --- | --- | --- |
| FR-01 | AT-01, AT-05, AT-10 | PRD §6 | Not run |
| FR-02 | AT-02, AT-11 | PRD §6 | Not run |
| FR-03 | AT-01, AT-02 | PRD §6 | Not run |
| FR-04 | AT-02, AT-10, AT-12 | PRD §6 | Not run |
| FR-05 | AT-03 | PRD §6 | Not run |
| FR-06 | AT-04 | PRD §6 | Not run |
| FR-07 | AT-04, AT-12 | PRD §6 | Not run |
| FR-08 | AT-03, AT-04, AT-05 | PRD §6 | Not run |
| FR-09 | AT-01, AT-03, AT-10 | PRD §6 | Not run |
| FR-10 | AT-03, AT-04, AT-10 | PRD §6 | Not run |
| FR-11 | AT-01, AT-03 | PRD §6 | Not run |
| FR-12 | AT-05, AT-06, AT-11 | PRD §6 | Not run |
| FR-13 | AT-01, AT-06 | PRD §6 | Not run |
| FR-14 | AT-07, AT-12 | PRD §6 | Not run |
| FR-15 | AT-01, AT-03, AT-10 | PRD §6 | Not run |
| FR-16 | AT-01, AT-10, AT-11 | PRD §6 | Not run |
| FR-17 | AT-08, AT-10 | PRD §6; conditional on B0 and authorized service access | Not run |
| FR-18 | AT-09 | PRD §6; conditional on B0 and approved Linux entitlement route | Not run |
| FR-19 | AT-02, AT-08, AT-10 | PRD §6; verify only authorized migration/exchange routes | Not run |
| FR-20 | AT-06, AT-07, AT-09, AT-10 | PRD §6 | Not run |
| UB-01–UB-10 | AT-05, AT-06, AT-10, AT-11, AT-12 | Plan §11 grouped mapping; split into clause-level procedures during G1 test design | Not run |
| VP-01–VP-05 and PRD §5 clauses | AT-01, AT-03, AT-04, AT-05 | Plan §11 grouped mapping; apply exact PRD §5.3 thresholds and design review | Not run |
| NFR-01–NFR-02 | AT-03, AT-04, AT-08, AT-10, AT-11 | Plan §11 grouped mapping | Not run |
| NFR-03–NFR-05 | AT-06–AT-12 | Plan §11 grouped mapping; privacy/service tests must reflect approved routes | Not run |
| NFR-06–NFR-07 | AT-02, AT-04, AT-07, AT-11, AT-12 | Plan §11 grouped mapping | Not run |
| NFR-08 and PF-01–PF-07 | AT-12, AT-13 | Plan §11 grouped mapping; performance targets and benchmark definitions require G1 ratification | Not run |
| Other mandatory clauses, including PRD §§6.1, 9, 13 | To be assigned explicitly | Plan §11 and PRD §10 do not replace clause-level procedures, approval records, or release evidence | Not run |

## B0 feature/state → requirement register

No B0 measurements or feature/state identifiers are available yet. Populate one row per observed state or workflow only after authorized capture; retain the source evidence reference and stable fixture/state ID.

| B0 feature/state ID | Screen/workflow and initial state | User input/action | Expected visible outcome | Expected persisted outcome | B0 evidence reference | Requirement ID(s) | Test/procedure ID | Status / blocker / owner |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| TBC | — | — | — | — | Not captured | — | — | Blocked pending G0/G1 |

## Release requirement → test → evidence register

Expand the initial crosswalk into clause-level rows. Use one row per requirement and distinct pass condition; add rows for every confirmed B0 state and all mandatory clauses without IDs. Cite approved exceptions individually instead of treating them as passes.

| Requirement / clause | B0 state or applicability evidence | Test ID and reproducible procedure | Explicit pass condition | Fixture / environment | Evidence reference | Result | Blocker / owner / approval |
| --- | --- | --- | --- | --- | --- | --- | --- |
| TBC | Not established | Not assigned | Derive from PRD and approved B0; do not infer | Not acquired | None | Not run | QA owner unassigned |

## Test result and exception rules

- Record the exact manual procedure or verified command, working directory, prerequisites, build/fixture versions, environment, observed result, evidence reference, and remaining coverage.
- Preserve failures and original goldens. Never change expected output or mask a difference to obtain a pass without the documented approval process.
- An exception must identify affected requirements/tests, B0 and Ubuntu evidence, reason, user impact, exact scope, compensating behavior, approvers, and review date; follow PRD §9 and the plan's exception process.
- Do not mark a conditional feature `not applicable` without evidence that it is absent from B0 or otherwise out of approved scope.
- Current gate state:
  - **G0 (Rights/Access):** Cleared (Clean-Room Native Desktop Route, see [docs/rights/G0_APPROVAL.md](../rights/G0_APPROVAL.md)).
  - **WP-00 (Fixtures):** Complete (7 fixtures generated, verified, SHA-256 registered, see [docs/reference/B0/ACQUISITION_CHECKLIST.md](../reference/B0/ACQUISITION_CHECKLIST.md)).
  - **WP-04 (Parity Spike):** Passed (5/5 spikes passed in 0.096s, see [docs/validation/WP04_PARITY_SPIKE_REPORT.json](../validation/WP04_PARITY_SPIKE_REPORT.json) and [docs/decisions/ADR-0001-CLEAN-ROOM-AND-STACK-EVALUATION.md](../decisions/ADR-0001-CLEAN-ROOM-AND-STACK-EVALUATION.md)).
  - **G1 (Baseline/Feasibility):** Cleared (Ratified in [docs/decisions/G1_RATIFICATION.md](../decisions/G1_RATIFICATION.md)).
  - **G2 (Internal Reading Slice):** Cleared (WP-06 through WP-09 complete; 13/13 unit and end-to-end tests passed, see [docs/validation/G2_PREVIEW_EVIDENCE.md](../validation/G2_PREVIEW_EVIDENCE.md)).
  - **G3 (Feature Completeness):** In Progress (Backlog: WP-10–WP-16).
  - **G4 (Release Qualification):** Not started.
