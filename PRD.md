# Product Requirements Document: Aquile Reader for Ubuntu

| Field | Value |
| --- | --- |
| Document version | 1.0 |
| Date | 2026-10-03 |
| Status | Draft; reference-baseline and product-owner approval required |
| Product | Authorized Ubuntu desktop port of Aquile Reader |
| Reference product | Aquile Reader for Windows; one specific release must be selected and frozen at Gate G1 |
| Proposed release targets | Ubuntu Desktop 24.04 LTS and 26.04 LTS, amd64, default GNOME desktop |
| Primary requirement | Look and behave like the reference application, not merely offer similar reading features |

## 1. Product intent

Bring Aquile Reader to Ubuntu without making existing Aquile Reader users learn a different application. The port must preserve the Windows application's app-owned visual design, reading experience, navigation, controls, settings, feature availability, and observable behavior. Ubuntu-specific integration must not become an excuse to redesign the application.

**Product promise:** "Aquile Reader, on Ubuntu" — not "an eBook reader inspired by Aquile Reader."

**Evidence limitation:** This document was informed by public first-party documentation and the Windows Store listing title. No upstream source code or running Windows build was inspected. Exact UI measurements, current defaults, complete feature availability, account behavior, and format-specific capabilities remain unverified until Gate G1. Requirements below are proposed product requirements, not claims that those details have already been measured.

**Authorization dependency:** Aquile Reader's published terms restrict copying, modification, trademarks, source extraction, and derivative versions (`S6`). Written authorization and appropriate licenses are prerequisites for an authorized port and reuse of protected assets, code, or services. This document does not establish those rights. If authorization cannot be obtained, a separately branded alternative would require a different product brief; it would not fulfill this port's promise.

## 2. Users, goals, and non-goals

### Primary users

- Existing Aquile Reader users moving from Windows to Ubuntu.
- Readers using Windows or Android alongside an Ubuntu desktop, where authorized cross-device interoperability is available.
- Ubuntu users managing local, DRM-free books, documents, and comics.
- Readers relying on typography customization, annotations, keyboard operation, or read-aloud functionality.

### Goals

1. Preserve visual and behavioral parity with a pinned Windows reference release.
2. Preserve the entire reference feature set, including less prominent settings and entitlement-dependent features.
3. Make local reading dependable offline, with no loss of acknowledged annotations or saved reading state.
4. Integrate properly with Ubuntu installation, files, display scaling, accessibility, audio, and updates.
5. Provide an authorized path for existing users' reading data and services where supported by upstream.

### Non-goals

- A GNOME-style redesign, different navigation, new branding, or a simplified reader.
- A Wine/Proton launcher, Windows virtual machine, or browser-only replacement.
- New formats, workflows, or social/AI features absent from the reference release.
- DRM circumvention or bypassing purchases, account restrictions, or service permissions.
- Reverse engineering protected source code or undocumented service access without appropriate authorization.
- First-release support commitments for other Linux distributions, desktop environments, ARM64, or Ubuntu releases outside the approved matrix.

An internal prototype may implement a subset. A subset must be labeled a preview and must not be presented as a completed parity port.

## 3. What "exactly like Aquile Reader" means

All baseline-supported features are **P0 release requirements**. There is no "core-only MVP" exception to the public release promise. Mandatory visual, Ubuntu, and quality requirements in Sections 5, 7, and 8 are also release-blocking; proposed platform scope and performance budgets become binding when approved at G1.

| Dimension | Required parity |
| --- | --- |
| Visual | Same app-owned structure, geometry, typography, colors, icons, artwork, control styling, overlays, and state presentation at equivalent settings and logical viewport sizes. |
| Interaction | Same available actions, action sequence, pointer behavior, keyboard bindings, selection behavior, focus transitions, shortcuts, and dismissal rules. |
| Reading | Same content order, layout modes, text wrapping, pagination, navigation, selection, annotations, and progress semantics for equivalent inputs. |
| State | Same defaults, setting scope, persistence, resume behavior, validation, and feature gating. |
| Services | Same supported catalog and cross-device workflows through authorized integrations; no unrelated replacement service presented as parity. |
| Platform | Ubuntu mechanisms may replace OS-owned Windows mechanisms only under the explicit exception process in Section 9. |

For each workflow, equivalent initial state and equivalent user input must produce equivalent visible state and persisted results. A matching screenshot with different behavior is a failure; equivalent functionality with a different interface is also a failure.

The actual pinned application is the authority for UI and behavior. Public documentation is a discovery aid, not a substitute for inspecting it. Known upstream security, privacy, accessibility, or data-loss defects must be reviewed, not blindly reproduced; any required divergence must be recorded and approved.

## 4. Reference baseline and evidence

### 4.1 Gate G1: freeze baseline B0

Product, design, engineering, and QA must approve a baseline package before claiming implementation readiness. It must include:

- Exact Windows app version/build, distribution channel, Windows version, UI language, and capture date.
- Free, trial, and premium states present in that build, with authorized test accounts and reproducible fixtures.
- Default settings, all available options and ranges, global versus per-book scope, and reset behavior.
- App fonts and icons, file checksums, redistribution rights, and documented fallback behavior. Identical fonts must not be assumed legally available on Linux.
- Screen and state inventory, including loading, empty, hover, focus, disabled, selection, dialogs, menus, errors, and entitlement states.
- Golden screenshots and interaction recordings, using matching viewport sizes, scale factors, content, settings, and controlled data.
- Complete shortcut map, pointer/touch behavior where supported, focus order, tooltip timing, animation durations, and control hit areas.
- A capability matrix by format: EPUB, PDF, CBZ, CBR, and any additional format actually supported by B0. Identify which operations work in each format rather than assuming all reader tools apply everywhere.
- Legally usable test files with stable identifiers/checksums, expected reading locations, annotation anchors, metadata, and layout results.
- Authorized service interfaces, data contracts, export/import capabilities, entitlement rules, and permitted migration routes.

Use at least 1024×768, 1366×768, and 1920×1080 logical client viewports where supported by B0, plus B0's smallest supported window size. Cover 100%, 125%, 150%, and 200% display scaling. Compare client content, not total window dimensions including OS decorations.

B0 is a frozen versioned artifact. Later upstream releases enter change control; they do not silently change the release target. Conflicts between documentation and B0 must be resolved in the baseline record.

### 4.2 Published feature evidence

| Feature family | Public evidence | What must still be verified in B0 |
| --- | --- | --- |
| Local DRM-free reading | Official website and Windows introduction (`S1`, `S2`) | Import paths, duplicate handling, storage model, supported file variants. |
| EPUB, PDF, CBZ, CBR | Formats named in the Windows Store listing title (`S3`) | Actual support, rendering behavior, and tools available in each format. The dynamic listing body was not accessible during research. |
| Two-column layout and reader customization | Official feature lists (`S1`, `S2`) | Other modes, exact defaults, fonts, ranges, colors, and pagination. |
| Highlights, notes, bookmarks, collections | Windows introduction (`S2`) | Selection, editing, colors, export, list presentation, and navigation. "Collections" here means the documented cross-book annotation view, not assumed custom bookshelves. |
| Read aloud | Official feature lists and historical hotkey documentation (`S1`, `S2`, `S5`) | Controls, voices, speed ranges, text tracking, and per-format availability. |
| Dictionary | Windows how-to documentation (`S4`) | Providers, supported languages, results UI, and any translation tools. |
| Library search/filter/sort, statistics, book details | Official feature lists (`S1`, `S2`) | Available fields, filters, formulas, and presentation. |
| Online catalogs | Official website and Windows introduction (`S1`, `S2`) | Providers, discovery/download behavior, and custom catalog support. The advertised 50,000+ count is not a guaranteed fixed inventory. |
| Cross-device sync | Current official website (`S1`) | Windows build support, provider, authentication, data coverage, conflict behavior, and authorized Linux access. |
| Premium and ads | Windows upgrade guide; cross-platform purchase FAQ (`S4`, `S7`) | Current tiers, trial rules, ads, Linux billing, and entitlement portability. |

Android documentation is supporting evidence only. Android gestures, layouts, features, and purchases must not be assumed to describe the Windows desktop reference.

## 5. User experience requirements

### 5.1 Screen/state inventory

The following is an initial capture checklist, not an invented navigation design. Names, placement, and existence must be reconciled with B0. Any additional B0 screen is in scope.

| Screen family | Capture and reproduce |
| --- | --- |
| Launch and onboarding | First run, initial defaults, loading, permission prompts, and account prompts if present. |
| Home/library | Navigation, book presentation, covers, progress, selection, search, sort/filter controls, context menus, empty/error/loading states. |
| Book information | Metadata, available actions, reading progress, word/line counts where exposed, and missing-data handling. |
| Reader | All format-specific layouts, visible/hidden controls, toolbar/footer, navigation panels, full-screen behavior, and loading/errors. |
| Reader tools | Selection menu, annotations, bookmarks, dictionary, search, read-aloud controls, and customization panels where available. |
| Collections | Cross-book highlights, notes, and bookmarks, their filters, editing actions, and jump-back behavior. |
| Online catalogs | Provider selection, discovery, search/results, book details, download progress, cancellation, and failures. |
| Statistics | Every displayed metric, date grouping, empty state, and reset action if available. |
| Settings/about | Every section, control, default, help action, diagnostics entry point, theme, and reset action. |
| Sync/account and premium | Signed-out/in states, sync status/conflicts, trial/free/premium states, upgrade/restore, and service errors where present. |

### 5.2 UI fidelity requirements

- Reuse authorized assets and design measurements wherever possible. Do not substitute approximate emoji, system icons, or generic component-library styling.
- Extract and match layout spacing, card dimensions, radii, borders, shadows, typography, colors, and motion from B0. These values are intentionally not invented in this PRD.
- Match visible text, capitalization, labels, tooltips, truncation, defaults, and control order for the same language, except approved platform-specific text.
- Match responsive breakpoints, column transitions, minimum sizes, panel behavior, and resize/full-screen transitions.
- Reproduce every B0 app theme and supported customization. Ubuntu's system theme must not restyle app-owned content into a different product.
- Preserve reading location and selection through viewport changes, theme changes, and reflow, following B0's observable behavior.
- Keyboard focus, hover, active, disabled, and error states are part of parity, not optional polish.

### 5.3 Visual acceptance thresholds

For controlled golden captures, each app-owned screen/state must meet all of these thresholds:

1. **VP-01:** Static control edges and text bounding boxes within **1 logical pixel** of B0.
2. **VP-02:** Flat-color design tokens within **ΔE2000 ≤ 2** of B0.
3. **VP-03:** **SSIM ≥ 0.99** per captured app-owned region, plus design review for missing or visibly wrong elements. A score alone is insufficient.
4. **VP-04:** Identical text, line breaks, content order, and page/spread boundaries in canonical EPUB fixtures with matched fonts and settings.
5. **VP-05:** Intentional UI timing — animations, tooltip/dwell delays, and debounce intervals — within **the greater of 16 ms or 10%** of B0's measured values, unless accessibility settings intentionally suppress motion. Computation, loading, and operation-response latency follow Section 8.2 instead; faster execution is acceptable and must not be artificially delayed to match B0.

Mask only documented OS-owned chrome, controlled dynamic fields, and narrowly defined text-edge anti-aliasing differences. Masks must not hide missing controls, changed geometry, font metrics, reading content, or pagination. Use deterministic service/ad fixtures rather than masking whole feature areas. QA and design must approve every mask and exception.

## 6. Functional requirements

Every requirement is P0 when its feature is present in B0. Conditional wording prevents inventing reference functionality; it does not permit dropping a confirmed feature. Format-specific behavior follows the approved capability matrix.

| ID | Requirement | Acceptance evidence |
| --- | --- | --- |
| FR-01 | Preserve application navigation, screen order, back behavior, panels, menus, focus, and window-state restoration. | AT-01, AT-05, AT-10 |
| FR-02 | Import all B0-supported local file types through the same app entry points. Preserve batch, folder, drag-and-drop, duplicate, and watched-folder workflows if B0 provides them. | AT-02, AT-11 |
| FR-03 | Match library presentation, search, filters, sort choices/direction, selection, available metadata, covers, reading status, and book-detail calculations. Preserve rename/edit actions only where available. | AT-01, AT-02 |
| FR-04 | Match library removal and source-file handling without silently changing whether originals are copied, linked, retained, or deleted. Missing, moved, unreadable, duplicate, corrupt, encrypted, and unsupported files require safe, actionable outcomes. | AT-02, AT-10, AT-12 |
| FR-05 | Match EPUB rendering, including chapter structure, publisher styling, embedded assets/fonts, links, supported scripts/languages, and every B0 layout mode. Preserve pagination and progress semantics. | AT-03 |
| FR-06 | Match PDF rendering and B0-supported navigation, zoom, selection, search, annotations, rotation, and fit modes. Do not promise EPUB-style reflow or OCR unless B0 supports it. | AT-04 |
| FR-07 | Match CBZ/CBR page ordering, spreads, reading direction, zoom, fit, navigation, and progress where supported. Respect archive/codec licenses; handle corrupt or unsafe archives without crashing. | AT-04, AT-12 |
| FR-08 | Match reader controls and their visibility rules; table of contents, page/location seeking, internal/external links, in-book search, history, and full-screen actions where available. | AT-03, AT-04, AT-05 |
| FR-09 | Match all reader customization options, defaults, ranges, increments, preview/application behavior, scope, reset rules, and persistence: fonts, sizes, spacing, margins, colors, and layouts actually exposed by B0. | AT-01, AT-03, AT-10 |
| FR-10 | Match creation, presentation, editing, deletion, colors, and navigation for highlights, notes, and bookmarks. Persist stable content/page anchors so reflow or reopening does not move annotations to unrelated content. | AT-03, AT-04, AT-10 |
| FR-11 | Match the cross-book collections view for annotations and bookmarks, including available search/filter/export actions and navigation to the original location. | AT-01, AT-03 |
| FR-12 | Match read-aloud entry/exit, playback, pause/resume, supported seek actions, voice/speed controls, text tracking, and reading-state updates where B0 exposes them. Missing voices must produce a useful Ubuntu-specific recovery path. | AT-05, AT-06, AT-11 |
| FR-13 | Match dictionary lookup from selected text, language settings, results layout, no-result/error handling, and translation functionality only if present in B0. Clearly handle unavailable online providers. | AT-01, AT-06 |
| FR-14 | Match in-app catalog browsing, search, details, download, import/open, cancellation, and retry. Preserve provider/custom-catalog support present in B0 through permitted APIs and provider terms. | AT-07, AT-12 |
| FR-15 | Match displayed reading statistics and book-detail metrics, including formulas, session boundaries, time/date behavior, and reset behavior where exposed. Suspend or idle time must not be counted differently without approval. | AT-01, AT-03, AT-10 |
| FR-16 | Match settings organization, themes, preferences, help/about, diagnostics entry points, persistence, and reset behavior. Adapt platform-specific paths/instructions without changing app-owned layout unnecessarily. | AT-01, AT-10, AT-11 |
| FR-17 | If B0 supports sync, interoperate with its authorized service and supported devices for the same data categories. Match authentication, status, retry, conflict handling, deletion semantics, and sign-out behavior. Never silently overwrite newer annotations or imply unsynced data was uploaded. | AT-08, AT-10 |
| FR-18 | Match B0's free/trial/premium feature gates, upgrade/restore states, and ads if present. Implement an approved Linux purchase/entitlement route; do not assume Microsoft Store or Android purchases transfer to Ubuntu. | AT-09 |
| FR-19 | Retain all B0 import/export features. Provide migration of existing reading data through authorized sync or documented upstream-supported exchange where available; validate supported data coverage before promising it. Direct access to undocumented Windows databases is not assumed. | AT-02, AT-08, AT-10 |
| FR-20 | Local books, local annotations, library navigation, and saved settings remain usable offline without mandatory sign-in. Online-only actions show truthful status and recover without blocking local reading. Any legitimate premium offline entitlement rules must be explicitly specified. | AT-06, AT-07, AT-09, AT-10 |

### 6.1 Keyboard and input parity

Reproduce every binding captured in B0, with the same context and focus behavior. Do not replace known bindings with guessed Linux conventions.

The historical official hotkey documentation (`S5`) provides the following discovery starting point; these are **not a confirmed current or exhaustive map**:

| Binding | Documented action |
| --- | --- |
| Left / Right arrow | Page change |
| Ctrl+R | Enter ReadAloud mode |
| Ctrl+E | Exit ReadAloud mode |
| Ctrl+Left / Ctrl+Right | Previous / next line in ReadAloud mode |
| Space | Start / pause in ReadAloud mode |

Text-entry controls must retain editing behavior; reader shortcuts must not consume typing in a note or search field contrary to B0. OS-reserved combinations and non-US keyboard layouts must be tested and conflicts explicitly resolved. Match mouse buttons, wheel/trackpad input, selection dragging, double-click, context menus, and supported touchscreen input from B0.

## 7. Ubuntu platform requirements

The platform scope and packaging choice below are proposed product decisions, not facts about upstream. Approve them at G1.

| ID | Requirement |
| --- | --- |
| UB-01 | Ship a standalone desktop application for Ubuntu 24.04 LTS and 26.04 LTS on amd64. No Windows runtime, Wine/Proton, or VM dependency. A cross-platform UI framework is acceptable only if parity and accessibility gates pass. |
| UB-02 | Support default GNOME Wayland sessions on both targets; test X11 on supported targets where that session is available. Do not promise an X11 session on an OS that no longer supplies one. |
| UB-03 | Primary distribution: an amd64 `.deb` with declared dependencies and an authenticated, signed APT update channel. Installation must not require building from source or developer tools. Snap/Flatpak/AppImage are separate future distribution decisions, not first-release obligations. |
| UB-04 | Install a correct desktop entry and authorized application icon. Register MIME associations for supported formats without forcibly replacing user defaults. Opening a file from Files or an "Open With" action must reach the same import/open outcome as the corresponding in-app action. |
| UB-05 | Use appropriate Linux file pickers/portals, clipboard, external-link handling, and notifications. Preserve application-level intent, multi-selection, cancellation, and error behavior. Correctly handle spaces, Unicode, case-sensitive paths, removable storage, symlinks, and permission failures. |
| UB-06 | Honor XDG configuration/data/cache/state locations and configured directory overrides, including package-specific equivalents if future confinement requires them. Never use hard-coded Windows paths. Normal application use must not need root privileges. |
| UB-07 | Render cleanly at 100%, 125%, 150%, and 200% scale; support mixed-DPI monitor movement, maximization, full-screen, resizing, and supported input methods. App layout and font metrics remain subject to parity thresholds. |
| UB-08 | Use supported Ubuntu audio/TTS mechanisms. Handle output-device changes and voice availability without losing reading state. Audio content must not be uploaded to a cloud voice service without explicit disclosure and consent. |
| UB-09 | Provide keyboard access, visible focus, semantic control names, and an AT-SPI/Orca-readable interface and reading content where technically applicable. Respect reduced-motion preferences and test high contrast/text enlargement without unusable clipping. Accessibility adaptations must be documented if they change B0 visuals. |
| UB-10 | Recover from suspend/resume, screen lock, lost network/storage access, and interrupted downloads. Preserve saved state across package upgrades. Uninstall must not silently delete user-supplied books; user-data cleanup must be explicit. |

Choose the implementation stack only after a parity spike proves font metrics, EPUB pagination, annotations, fixed-layout rendering, Linux accessibility, and required service access. Prefer authorized upstream reuse when feasible. This PRD does not presume the existing application is open source or portable as-is.

## 8. Quality, data, privacy, and performance

### 8.1 Reliability and security

- **NFR-01:** An annotation or settings change acknowledged as saved must survive restart and simulated process failure. Persist current reading location at least every five seconds and on orderly close; an abrupt failure may lose at most those five seconds of unacknowledged position changes.
- **NFR-02:** Package upgrades and schema changes must preserve books, reading state, annotations, preferences, and entitlement state. Destructive migrations require a verified backup/recovery path; downgrade limitations must be documented.
- **NFR-03:** Books remain local unless the user explicitly invokes/enables an online function requiring upload. Do not add hidden telemetry or a mandatory account to local reading.
- **NFR-04:** Document network destinations, transmitted data, online dictionary queries, catalog requests, sync contents, and voice processing before release. Obtain required consent; redact credentials, full paths, note content, and book text from routine diagnostic output.
- **NFR-05:** Store service secrets in the desktop's appropriate credential store, not plaintext preferences. Use authenticated TLS, approved authentication flows, scoped permissions, and explicit sign-out/token invalidation behavior.
- **NFR-06:** Treat imported books, archives, metadata, remote catalogs, and embedded resources as untrusted. Prevent traversal, decompression abuse, script execution outside an approved sandbox, and unintended local-file/network access. Never bypass OS permissions.
- **NFR-07:** Honor font, rendering-engine, archive/codec, catalog, and third-party service licenses. Supply required notices and a dependency/security maintenance plan.
- **NFR-08:** Pass a 24-hour scripted reading/import/annotation/suspend stress run with no crashes, corruption, or lost acknowledged data. No unresolved critical/high-severity security or data-loss defects may ship.

### 8.2 Proposed performance acceptance budgets

These budgets are product targets, **not measured Aquile Reader performance**. Ratify benchmark definitions and feasibility at G1; resolve any incompatible target before baseline approval. Changes require documented product approval rather than silently relaxing the definition of parity. Response latency must meet the approved absolute budget and the B0 regression rule below; it is not subject to VP-05's symmetric intentional-timing tolerance.

Benchmark on a documented four-core amd64 machine with 8 GB RAM, SSD, 60 Hz display, and the same background-load conditions. Use a 1,000-book library, a canonical text-focused EPUB up to 10 MiB, and agreed large PDF/comic fixtures. Record percentiles over at least 30 application/book opens and 200 page changes.

| ID | Operation | Target |
| --- | --- | --- |
| PF-01 | Cold launch to interactive library | p95 ≤ 3 seconds |
| PF-02 | Open canonical EPUB to readable content | p95 ≤ 2 seconds |
| PF-03 | Warm EPUB page turn | p95 ≤ 100 ms |
| PF-04 | Library search/filter on 1,000 books | p95 ≤ 250 ms |
| PF-05 | Long imports, indexing, downloads | Background work; cancellation and other UI input respond within 250 ms |
| PF-06 | Memory: idle library / canonical EPUB | ≤ 500 MiB / ≤ 750 MiB total process-tree resident memory |
| PF-07 | Large PDFs/comics | Lazy rendering and bounded caching; no decoding every page into memory at open, no unbounded growth during a 1,000-page traversal |

Also compare equivalent operations against B0 on matched hardware. Investigate regressions exceeding 20%; any accepted regression requires an explicit performance exception. Do not compromise pagination, image fidelity, or saved-data integrity to satisfy a benchmark.

## 9. Permitted platform adaptations and exception control

Literal identity of OS-owned Windows and Ubuntu UI is not possible. The following are **candidate adaptation categories**, not blanket waivers:

| Category | May differ after approval | Must stay equivalent |
| --- | --- | --- |
| OS-owned window chrome | Compositor borders, shadows, native window controls, system scaling rasterization. | App-owned content, fullscreen/window intent, restore behavior. App-drawn chrome remains part of visual parity. |
| File/access dialogs | Native picker appearance, permission wording, portals, Unix paths. | Available operation, selected files, cancellation, confirmation, and safe result. |
| Voices/audio | Available licensed system voices and voice names/timbre. | Spoken content, playback actions, tracking, speed/seek semantics, and saved position. A missing read-aloud feature is not an acceptable adaptation. |
| Installation/update/billing | Linux package management, browser/authentication/payment handoff, provider-specific system dialogs. | Clear state, feature gates, recoverable failures, and approved entitlement behavior. |
| OS text/accessibility | Platform help instructions, unavailable OS-specific key bindings, accessibility/reduced-motion adjustments. | Functional intent, discoverability, keyboard access, and unchanged default app design wherever possible. |

Each exception record must identify affected requirement/test, B0 evidence, Ubuntu evidence, reason, user impact, exact scope, compensating behavior, approvers, and review date. Product and QA must approve it; design approves visual deviations, and security/legal approve relevant service or rights changes.

Unavailable upstream fonts, sync access, billing, or rendering components are dependencies to resolve, not permission to silently substitute something "close enough." Unapproved omissions or material deviations block a full-parity release.

## 10. Acceptance and test plan

Use a reproducible corpus of licensed/public-domain or purpose-built files, including text-heavy and illustrated EPUBs, embedded fonts, supported multilingual/RTL content, long PDFs, high-resolution comics, and malformed/unsafe inputs. Test only claims supported by the B0 capability matrix, and retain expected outputs alongside fixtures.

| Test | Scenario and pass condition |
| --- | --- |
| AT-01 — Visual parity | Every B0 screen/state passes Section 5 thresholds, all reference themes, required viewports/scales, and design review. Compare controls, menus, overlays, book details, collections, settings, stats, and entitlement states, not just the reader. |
| AT-02 — Library/import/migration | Single/batch import, baseline folder/watch/drop workflows, duplicates, metadata, filters/sorts/search, remove/cancel, source-file semantics, and supported migration/export produce B0-equivalent results. Include Unicode/case-sensitive paths and unavailable storage. |
| AT-03 — EPUB/annotations | Open, navigate, search, customize, select, annotate, use collections, close/reopen, and change layout/scale. Canonical text, pagination, progress, anchors, and applicable statistics match B0. |
| AT-04 — PDF/comics | Exercise every supported format-specific tool, page order, spreads/direction, zoom/fit, navigation, progress, and annotation behavior; compare rendered output and persistent results with B0. |
| AT-05 — Interaction/input | Replay the complete B0 shortcut/input map and focus transitions. Test note/search editing, menus, hover, mouse/trackpad, supported touch, input methods, and non-US keyboards. No actions fire in the wrong context. |
| AT-06 — TTS/dictionary | Exercise every baseline playback/lookup control, selections, languages, seek/voice changes, missing voices, no-definition results, and offline/provider failure. Check text tracking and recovery, not identical unlicensed voice timbre. |
| AT-07 — Catalogs/offline | Discover, search, download, cancel, retry, import, and open through approved providers. Check failure states and local-reading independence; inventory changes do not create a fixed-book-count guarantee. |
| AT-08 — Sync/interoperability | Use authorized Windows/Android/Linux endpoints supported by B0. Validate each synced data type, concurrent edits, conflict/deletion behavior, offline reconnection, sign-out, and migration coverage. No fake success, unauthorized API calls, or lost newer data. |
| AT-09 — Entitlements | Validate each free/trial/premium state and associated ads/gates, successful/cancelled/failed purchase, restore, expiration/refund where applicable, and documented offline/cross-platform rights. Use approved provider test environments. |
| AT-10 — Persistence/faults | Restart, kill process, interrupt downloads/import/migration, exhaust disk, revoke storage/network access, suspend/resume, and upgrade packages. Saved data survives and error/recovery behavior meets parity or approved safety exceptions. |
| AT-11 — Ubuntu integration/accessibility | Clean install/update/uninstall on both supported releases; GNOME Wayland and available X11; desktop/MIME launch; file dialogs; XDG directory overrides; mixed DPI; audio routing; keyboard-only use; Orca, contrast, and reduced motion. Reject unauthenticated/tampered updates; verify user data is retained. No root required for normal operation. |
| AT-12 — Security/privacy | Malicious archive/content tests, permission boundaries, authentication/secret handling, license review, telemetry/network inspection, and diagnostic redaction meet Section 8. |
| AT-13 — Performance/endurance | Run the approved percentile benchmarks, B0 regression comparison, large-document traversal, and 24-hour stress test. Meet budgets and report any approved exception. |

Maintain two-way traceability: **every B0 feature/state → requirement**, and **every release requirement → test → explicit pass condition → evidence or permitted approved exception**. Cover FR, UB, VP, NFR, PF, and the remaining mandatory clauses in Sections 5–8, including requirements with no Windows counterpart. No feature or requirement may be marked passed from documentation alone. QA must publish the supported platform/format/service matrix and known differences.

## 11. Delivery gates

Dates and effort estimates follow the upstream access and portability audit; this document does not invent a delivery timeline.

| Gate | Deliverable | Exit condition |
| --- | --- | --- |
| G0 — Rights and access | Written authorization; asset/dependency/service rights; available source or approved implementation route; reference builds and test accounts. | Legal/product approve the authorized scope. Unavailable rights trigger a stop/rebrief, not an unauthorized clone. |
| G1 — Baseline and feasibility | Approved B0 package, measured design specification, complete feature/format/tier matrix, Ubuntu/package scope, parity spike, migration/service/billing decisions, and benchmark definitions. | Product/design/engineering/QA agree that the full-parity scope is specified and feasible; unresolved blockers have owners and no false implementation-ready status. |
| G2 — Internal reading slice | Shell/library, canonical reader, customization, annotations, persistence, Ubuntu integration, and early visual regression tooling. | The implemented slice passes its mapped tests; it remains an internal preview, not a complete port. |
| G3 — Feature completeness | All B0 features, supported formats, catalogs, statistics, TTS/dictionary, authorized sync, and entitlement integrations. | No unimplemented B0 feature or unresolved required integration; full traceability exists. |
| G4 — Release qualification | Complete acceptance evidence, package/update checks, security/accessibility review, endurance results, approved exception register, support and release documentation. | Section 13 is satisfied on the complete supported matrix. |

## 12. Decisions, dependencies, and risks

| Item | Required resolution | Accountable role / gate |
| --- | --- | --- |
| Authorization and branding | Confirm permission to produce an Aquile Reader port and reuse source/assets/services; published terms do not grant it. | Product + legal / G0 |
| Reference version | Select the exact Windows release and freeze B0; identify current versus historical documented features. | Product + QA / G1 |
| Upstream portability | Audit actual source/framework availability and rendering dependencies. Prove typography/pagination before selecting a framework. | Engineering + design / G1 |
| Ubuntu/package scope | Approve 24.04/26.04 amd64, session coverage, `.deb`/APT delivery, supported input/locales, and benchmark hardware. | Product + engineering / G1 |
| Fonts, voices, archive/rendering licenses | Obtain rights and Linux-compatible implementations; record permitted voice variation without compromising typography/layout. | Engineering + legal + design / G1 |
| Cloud interoperability and migration | Obtain documented, authorized service/data access and verify exactly which user data transfers. Do not assume a local database or account schema. | Product + upstream owner + engineering / G1 |
| Linux premium and ads | Approve provider, tier mapping, trials, offline entitlement rules, restore/refund behavior, and purchase portability. The official FAQ describes platform-specific Windows/Android purchases (`S7`), not Linux entitlements. | Product + upstream owner + legal / G1 |
| Parity versus defects/accessibility | Decide safe behavior for upstream defects and accessibility adaptations; document each visible/behavioral exception. | Product + design + QA + security / G1–G4 |
| External provider availability | Confirm catalog/dictionary/sync access, terms, quotas, and outages; keep local reading independent and do not guarantee external inventory. | Product + engineering / G1–G4 |

An unresolved required sync, purchase, asset, or format dependency prevents calling the release full parity. A local-only preview may be useful, but narrowing the promise requires explicit product approval and transparent labeling.

## 13. Definition of done and success criteria

- [ ] G0 rights/access and G1 baseline approvals are recorded.
- [ ] 100% of B0 features, screens, settings, supported formats, and entitlement states are mapped to requirements and executable/manual acceptance evidence; all mandatory visual, Ubuntu, quality, and performance requirements have equivalent test coverage.
- [ ] All applicable P0 tests pass across the approved Ubuntu matrix, with only individually approved platform/safety/accessibility/performance exceptions. Performance exceptions may not waive missing features, incorrect content, or data-safety requirements.
- [ ] Every golden UI state meets the visual thresholds and has design/QA sign-off; no unapproved app redesign or pagination drift remains.
- [ ] Core end-to-end workflows have equivalent actions and outcomes: import → find → read/customize → annotate → resume; listen/lookup; browse/download; sync and premium where present.
- [ ] At least five existing Windows Aquile Reader users complete the core local-reading workflows without app-specific retraining; feedback does not identify an unapproved navigation or interaction difference.
- [ ] No release-blocking functional defect, lost acknowledged data, critical/high security defect, or unsupported rights/service usage remains.
- [ ] Performance, accessibility, persistence, clean-install/update, and 24-hour endurance evidence is available.
- [ ] The exception register, migration coverage, supported matrix, privacy/network disclosures, license notices, update channel, and support/recovery instructions are published.

**Release success is fidelity plus dependability:** all agreed parity checks pass, existing users can transfer their habits, and Ubuntu-specific integration does not weaken data safety or misrepresent unavailable services.

## 14. Sources

Sources reviewed on 2026-10-03. Public pages can change and some historical Windows documentation may not match the current release; B0 verification remains mandatory.

- **S1 — Current official website:** [Aquile Reader](https://www.aquilereader.in/). General features, customization, catalogs, statistics, and Windows/Android cross-device sync.
- **S2 — Official Windows introduction:** [Aquile Reader — An immersive reading experience](https://aquilereader.wordpress.com/). Windows feature list, including cross-book collections and book details.
- **S3 — Windows distribution listing:** [Microsoft Store: Aquile Reader](https://apps.microsoft.com/detail/9p08t4jltqnk?gl=US&hl=en-US). Listing title names EPUB/PDF/CBZ/CBR; the JavaScript-dependent full description was not verified.
- **S4 — Official Windows how-to:** [How to on Windows](https://aquilereader.wordpress.com/how-to-windows/). Settings/Reader dictionary language, diagnostics, and premium upgrade flow; exact current layout requires B0 confirmation.
- **S5 — Official historical hotkey documentation:** [Aquile Reader blog](https://aquilereader.wordpress.com/blog/), "Keyboard hotkeys" entry, dated 2020-06-14 and updated 2021-01-19. Discovery evidence only; verify the complete current map in B0.
- **S6 — Published terms:** [Aquile Reader terms of service](https://www.aquilereader.in/terms.html), effective date shown as 2023-10-27. Rights restrictions and third-party service dependencies; obtain appropriate authorization and legal review.
- **S7 — Official Android FAQ:** [FAQ — Android](https://www.aquilereader.in/faq-android.html). Supporting evidence for Windows/Android sync and platform-specific purchases; not the desktop UI/behavior baseline.
- **S8 — Ubuntu support baseline:** [Canonical Ubuntu release cycle](https://ubuntu.com/about/release-cycle). Confirms 24.04 LTS and 26.04 LTS as supported LTS releases; application support scope remains a product decision.
