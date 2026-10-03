# Test / evidence record template

Copy this template for an actual check. Do not pre-fill a result from a plan or mock. Keep sensitive source material, account details, and restricted evidence in approved access-controlled storage; this record should contain references, not credentials or protected contents.

## Work item

- Work-package ID:
- Check / run ID:
- Owner:
- Work status: `not started` / `in progress` / `blocked` / `complete`
- Requirement IDs and mandatory PRD clauses:
- B0 screen/state IDs (once authorized and frozen):
- Acceptance test ID(s):
- Prerequisites / approvals:
- Blockers and accountable owner:

## Check definition

- Type: manual / automated / benchmark / visual review / other
- Exact command or step-by-step procedure (only verified commands):
- Working directory:
- Explicit pass condition (from approved requirement/B0):
- Expected visible outcome:
- Expected persisted outcome:
- Fixture ID, provenance reference, version, and checksum:

## Environment

- Application build / commit / package:
- Ubuntu release, architecture, session, and desktop (or authorized B0 reference environment):
- Display viewport, scale, fonts, locale, input devices, and accessibility configuration, as applicable:
- Service/provider and entitlement state, if applicable (no secrets):
- Hardware/background-load details, if applicable:
- Other relevant configuration:

## Result

- Result: `passed` / `failed` / `blocked` / `not run` / evidenced `not applicable`
- Date/time and operator:
- Actual outcome:
- Evidence reference and storage location:
- Error / defect / deviation:
- Remaining coverage and related risks:

## Exception, review, and sign-off (if applicable)

- Affected requirement/test IDs:
- B0 evidence and Ubuntu evidence:
- Reason and user impact:
- Exact exception scope and compensating behavior:
- Approvers (product + QA; design/security/legal as applicable):
- Review date:

A documentation-only artifact is not application validation. Never claim a pass without executing the check and retaining the evidence required by the mapped requirement.
