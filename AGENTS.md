# Agent guidance

## Scope and instruction precedence

- This guide applies throughout the repository. Higher-priority instructions and the explicit user request govern; `AGENTS.md` is repository guidance, not authorization to bypass rights or release gates.
- Keep work within the requested scope. Do not implement application code when the task is documentation-only.
- Product source-of-truth order: `PRD.md` → approved B0 evidence and decision records → `IMPLEMENTATION_PLAN.md`.
- `PRD.md` defines the product promise, requirements, gates, and acceptance criteria. Acceptance of documentation does not establish G0 authorization or G1 approval.
- The pinned B0 application is the authority for measured UI and behavior. Resolve conflicts with published documentation or the PRD in an approved baseline/decision record; do not silently choose a different target.
- `IMPLEMENTATION_PLAN.md` is the companion execution plan being created alongside this guide. Consult it when available; planned work is not completed work or approval evidence.

## Repository state and technology decisions

- This repository starts documentation-first. No application code, implementation stack, runtime, build/test scripts, or tests are established.
- Do not invent existing directories, APIs, database schemas, dependencies, or runnable commands. Future structures are proposals pending the approved stack.
- Select the stack only after the upstream access/portability audit and authorized parity spike prove font metrics, EPUB pagination, annotation anchors, fixed-layout rendering, Linux accessibility, and required service access.
- Prefer authorized upstream reuse when feasible; do not assume upstream is open source, portable, or available for extraction.
- Do not preselect a framework, rendering engine, package manager, or test runner through speculative scaffolding. Independent test tooling must remain provisional until the relevant decisions are approved.
- Record unknowns, evidence needed, accountable owner, and gate. Unverified defaults, shortcuts, format capabilities, purchase portability, and public or Android documentation are not measured Windows behavior.

## Authorization and delivery gates

- **G0 — rights and access:** require written authorization, an approved source/implementation route, branding/asset/dependency/service rights, reference builds, and authorized test accounts. Legal and product must approve the permitted scope.
- Before G0 approval, harmless independent planning and test infrastructure may proceed using original or public-domain materials, without reusing protected upstream code/assets or accessing restricted services. This does not authorize port implementation, source extraction, or unauthorized reverse engineering.
- Missing rights require a stop/rebrief for affected work, not an unauthorized clone. A separately branded alternative needs a different approved product brief.
- After G0 approval, authorized audits, reference capture, and scoped feasibility spikes may prepare G1 within the granted rights. Do not claim reference measurements without access to the actual authorized build and reproducible states.
- **G1 — B0 and feasibility:** product, design, engineering, and QA must approve the frozen baseline and full-parity feasibility before feature-port rollout or any implementation-ready claim.
- B0 must pin the Windows build/channel, OS, UI language, capture date, settings, fonts/assets and rights, all screens/states/input behavior, format/tier capability matrix, licensed fixtures/checksums, and comparable captures/recordings.
- G1 also resolves Ubuntu/package scope, migration/service/billing routes, benchmark definitions, and the parity spike. Keep unresolved blockers owned and visible; do not label the gate passed without its required decisions and evidence.
- **G2:** an internal reading slice must pass its mapped tests and remain labeled a preview. **G3:** all B0 features and required integrations are complete. **G4:** the full PRD definition of done and release evidence are satisfied.
- Independent harmless planning/test preparation can continue while a gate is blocked; respect task-specific rights and dependencies rather than using that allowance to bypass port gates.

## Parity and Ubuntu scope

- Preserve exact app-owned visual and behavioral parity, not merely similar functionality. Equivalent state/input must produce equivalent visible and persisted outcomes.
- Every confirmed B0 feature is P0, including less prominent settings, supported formats, entitlement states, ads, and services. Mandatory visual, Ubuntu, quality, and approved performance requirements also block release.
- No silent feature cuts, generic redesign, guessed Linux shortcuts, emoji/system-icon substitutions, or replacement services presented as parity. A subset is a preview, never the completed port.
- Match B0 geometry, text, font metrics, pagination, themes, focus, selection, defaults, persistence, and intentional timing. Apply `VP-01`–`VP-05` and PRD §5.3; a screenshot score alone is not acceptance.
- Preserve the proposed Ubuntu 24.04 LTS / 26.04 LTS, amd64, default GNOME matrix pending G1 ratification: Wayland on both and X11 only where that target actually supplies a supported session.
- The proposed distribution is an amd64 `.deb` with authenticated, signed APT updates. Do not assume Snap/Flatpak/AppImage, other distributions/desktops/architectures, Wine, a VM, or a browser-only replacement satisfies this scope.
- Honor XDG locations/overrides, user file associations, supported Linux integration, mixed DPI, keyboard access, AT-SPI/Orca, and normal operation without root, as specified by `UB-01`–`UB-10`.
- Treat platform adaptations as approval candidates, not blanket waivers. Missing fonts, sync, billing, or rendering components are dependencies to resolve, not permission for a close-enough substitute.

## Baselines, changes, exceptions, and traceability

- Keep B0 frozen and versioned. Later upstream releases require explicit change control, impact analysis, updated approvals, and rerun evidence; they do not silently move the target.
- Retain reproducible, legally usable fixtures, stable identifiers/checksums, expected outputs, capture settings, and entitlement/service states. Do not overwrite goldens merely to make a failing change pass.
- Maintain two-way links: B0 feature/state → requirement; release requirement → test → explicit pass condition → evidence or individually approved exception.
- Use the existing PRD IDs: `FR-01`–`FR-20`, `UB-01`–`UB-10`, `VP-01`–`VP-05`, `NFR-01`–`NFR-08`, `PF-01`–`PF-07`, and `AT-01`–`AT-13`. Also trace mandatory clauses without IDs; do not omit them because they lack a Windows counterpart.
- Update affected requirement mappings, decisions, tests, evidence, and plan status together. Conditional features become required when B0 confirms them; document evidence for non-applicability rather than assuming absence.
- An exception must record affected requirements/tests, B0 and Ubuntu evidence, reason, user impact, exact scope, compensating behavior, approvers, and review date.
- Require product and QA approval; add design approval for visual changes and security/legal approval for relevant safety, service, or rights changes. Review upstream defects rather than blindly reproducing them.
- Golden masks require QA/design approval and the narrow limits in PRD §5.3. Never mask missing controls, changed geometry/font metrics, reading content, pagination, or whole service/advertising areas.
- Performance changes and accepted regressions require explicit approval under PRD §8.2. Performance exceptions cannot waive missing features, incorrect content, or data safety.

## Offline operation, data safety, and security

- Keep local books, annotations, navigation, and settings usable offline without mandatory sign-in (`FR-20`). Online failures must be truthful and must not block local reading.
- Books remain local unless the user explicitly invokes/enables a disclosed online function requiring upload. No hidden telemetry or silent cloud upload; cloud voice processing requires explicit disclosure and consent.
- Acknowledged annotation/settings saves must survive restart and simulated failure. Persist reading location at least every five seconds and on orderly close; abrupt failure may lose at most five seconds of unacknowledged position changes (`NFR-01`).
- Preserve books, reading state, annotations, preferences, and entitlements through upgrades/schema changes. Destructive migrations need verified backup/recovery and documented downgrade limitations (`NFR-02`).
- Do not silently change copied/linked/original-file removal semantics, delete user-supplied books on uninstall, overwrite newer annotations in sync, or report an upload that has not occurred.
- Use only authorized sync/catalog/dictionary interfaces and supported migration routes. Do not assume undocumented Windows databases or account schemas are permitted interfaces.
- Purchases, ads, trials, restore, and offline entitlement rules require approved Linux routes. Never bypass restrictions or assume Windows/Android purchases transfer to Ubuntu.
- Never hardcode secrets or store service credentials in plaintext preferences. Use the appropriate desktop credential store, authenticated TLS, approved/scoped authentication, and explicit sign-out/token invalidation.
- Document destinations and transmitted data. Redact credentials, full paths, note contents, and book text from routine logs and diagnostics (`NFR-03`–`NFR-05`).
- Treat imported books, archives, metadata, embedded resources, and catalogs as untrusted. Prevent traversal, decompression abuse, unauthorized script execution, and unintended file/network access; never bypass OS permissions (`NFR-06`).
- Verify rights for code, artwork, icons, fonts, voices, rendering/archive components, fixtures, and services. Retain license notices and dependency/security maintenance information (`NFR-07`).

## Working practices

- Inspect relevant files and current user changes before editing. Verify paths; keep patches small, focused, and consistent with approved decisions.
- Preserve work you did not create. Do not overwrite, revert, rename, delete, or refactor unrelated material without an explicit request.
- Update relevant tests/docs/call sites with behavioral changes, but do not fix unrelated failures or add speculative dependencies.
- Do not create commits or branches unless explicitly requested.

## Validation and evidence

- Derive checks from the mapped PRD requirements and approved B0 fixtures. Start with affected checks, then expand to the required platform/format/tier/service matrix.
- Document commands only after the tooling exists and the commands are verified. Record working directory, prerequisites, fixture/build versions, and environment; do not invent runtime/build/test commands now.
- Distinguish `passed`, `failed`, `blocked`, `not run`, and evidenced `not applicable`. Never claim a pass from documentation, intent, a mock, or an unexecuted command.
- Record exact command/check, result/error, environment, evidence, and remaining coverage. If an attempt reports `Cannot set tty process group`, report that attempt accurately; do not infer a permanent terminal limitation or invent an unverified workaround.
- Headless/unit/golden checks support development but cannot replace actual Ubuntu desktop, Orca/AT-SPI, audio/input, file/portal/MIME, scaling, or package testing (`AT-11`).
- Test real clean install/update/uninstall and signed/tampered update handling on both approved Ubuntu releases, GNOME Wayland, and supplied supported X11 sessions. Verify preserved user data and root-free normal operation.
- Run visual comparisons with matched logical client viewports, scales, fonts, settings, and content, plus design/QA review. Replay behavior and compare persisted outcomes as well as screenshots.
- Exercise offline/provider failures, authorized interoperability/entitlements, malicious inputs, fault recovery, migrations, and acknowledged-save durability through the applicable `AT-02`–`AT-12` checks.
- Run approved percentile benchmarks, matched-hardware B0 regression comparisons, large-document traversal, and the 24-hour endurance run (`AT-13`). Do not relax budgets or sacrifice fidelity/data safety to obtain a pass.
- If tools, accounts, reference builds, Ubuntu machines, or accessibility/package environments are unavailable, identify the blocked requirement/test and needed access. Documentation-only work is not application validation.

## Definition of done and handoff

- PRD §13 is the release definition of done, not a simplified MVP checklist. Record G0/G1 approvals and G4 qualification; map 100% of B0 features/states and all mandatory requirements to executable/manual acceptance evidence.
- All applicable P0 checks must pass across the approved matrix, with only individually approved exceptions. Every golden state needs the specified thresholds and design/QA sign-off; no unapproved redesign or pagination drift may remain.
- Validate the complete local-reading and applicable listen/lookup, catalog, sync, and premium workflows. At least five existing Windows users must complete core local-reading workflows without app-specific retraining or unapproved interaction differences.
- No release-blocking functional defect, lost acknowledged data, critical/high security defect, unsupported rights/service use, or unresolved required integration may remain.
- Publish performance/accessibility/persistence/package/endurance evidence, supported matrix and known differences, exceptions, migration coverage, privacy/network disclosures, licenses, authenticated update channel, and support/recovery instructions.
- Final task summaries must name relevant project-relative paths, affected requirement/AT IDs, checks actually run and their results, known blockers, and decisions or approvals still needed. Distinguish task completion from gate or release completion.
