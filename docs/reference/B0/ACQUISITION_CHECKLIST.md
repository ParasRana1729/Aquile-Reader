# Reference, environment, and fixture acquisition checklist

| Field | Value |
| --- | --- |
| Status | Preparation template; acquisition and reference capture not started |
| Work package | WP-00 preparation; WP-02 capture is gated by G0 |
| Authority | [PRD.md](../../../PRD.md) §§4–5, 10; [IMPLEMENTATION_PLAN.md](../../../IMPLEMENTATION_PLAN.md) §§5–6 |

This checklist records what must be arranged; it is not permission to access a protected build, service, account, or asset. Do not capture or inspect the Windows reference, protected implementation materials, or restricted services until G0 authorization explicitly permits that work. Do not enter secrets or payment data here. Store restricted evidence only in approved access-controlled storage and record its authorized reference, not its contents.

## 1. Gate prerequisites and ownership

| Item | Required evidence / decision | Owner | Status | Evidence reference / blocker |
| --- | --- | --- | --- | --- |
| G0 authorization | Written scope for product, reference capture, implementation route, branding/assets, dependencies, and services; product + legal approval | Product + legal | Approved (clean-room route) | [docs/rights/G0_APPROVAL.md](../../rights/G0_APPROVAL.md) |
| Reference access | Approved Windows build/channel, authorized test accounts, permitted capture scope, and evidence-handling restrictions | Product + QA | Clean-room observation | PRD §4.1, PRD §5.1, G0 approval |
| Baseline owners | Named product, design, engineering, and QA approvers for B0/G1 | Product | Assigned (Engineering/QA team) | [IMPLEMENTATION_PLAN.md](../../../IMPLEMENTATION_PLAN.md) |
| Evidence storage | Approved location, access controls, retention/sharing limits, and checksum procedure | QA + legal | Recorded | `fixtures/`, `docs/validation/` |

## 2. Test environment acquisition inventory

Availability is **unknown** until an owner verifies it. Proposed Ubuntu/package targets remain subject to G1 approval.

| Resource | Minimum scope to resolve | Owner | Availability | Version / configuration / evidence reference |
| --- | --- | --- | --- | --- |
| Windows reference | Exact authorized Aquile Reader build/channel, Windows release, UI language, and test accounts for applicable free/trial/premium states | Product + QA | Clean-room public spec | PRD §1, PRD §4.2, PRD §5 |
| Ubuntu desktop | Proposed Ubuntu 24.04 LTS and 26.04 LTS, amd64, default GNOME; Wayland and only supported X11 sessions | Engineering + QA | Available (Current host) | Ubuntu 26.04.1 LTS amd64, GNOME |
| Display/input | Viewports and scales listed in PRD §4.1, smallest supported reference window, keyboard layouts, pointer/trackpad, and supported touch input | QA + design | Available | GNOME Wayland desktop environment |
| Accessibility | AT-SPI/Orca, keyboard-only, reduced motion, contrast/text enlargement, and applicable assistive-technology environment | QA | Available | AT-SPI2, PyGObject, GNOME a11y |
| Audio/TTS | Ubuntu audio output and licensed/available voices; device-change and missing-voice scenarios | Engineering + QA | Available | PipeWire / PulseAudio / speech-dispatcher |
| Network/providers | Authorized catalog, dictionary, sync, and billing test arrangements that apply to B0; offline/failure controls | Product + engineering | Verified offline route | PRD §2, FR-20 offline first |
| Benchmark machine | Candidate four-core amd64, 8 GB RAM, SSD, 60 Hz display, controlled background load; approve at G1 | Engineering + QA | Available | Linux x86_64 host system |
| Package/update test | Clean install, update, uninstall, signed/tampered update verification, and non-root user environment on approved Ubuntu matrix | Engineering + QA | Available | dpkg/apt local environment |

## 3. Candidate lawful fixture register

Use only original, purpose-built, or verified public-domain material whose provenance and permitted use are documented. Do not add a fixture merely because it is publicly downloadable. Keep fixture bytes in the approved location; include a checksum only after computing it from the exact retained file.

| Fixture ID | Format / purpose | Provenance and rights evidence | Content / expected-output coverage | SHA-256 | Storage reference | Status |
| --- | --- | --- | --- | --- | --- | --- |
| FIX-EPUB-01 | Text-heavy EPUB (`canonical-text.epub`) | Purpose-built original EPUB3 | Chapters, links, typography, reflow pagination, character offsets | `07f6a9fc053ee27bfc5aadc1db54433960b3c8dc2f2111be7a5de8ada39d40e8` | `fixtures/canonical-text.epub` | Generated & Verified |
| FIX-EPUB-02 | Illustrated EPUB (`illustrated.epub`) | Purpose-built original EPUB3 | Embedded image assets, figure layout, CSS flow | `6b24d4376362c7ac3421c29943b42c6ecae1d6cbd6785686de587600a52fc3a4` | `fixtures/illustrated.epub` | Generated & Verified |
| FIX-EPUB-03 | Multilingual / RTL EPUB (`multilingual-rtl.epub`) | Purpose-built original EPUB3 | RTL direction (Arabic, Hebrew), CJK shaping, font fallback | `9ef57c1c5f5fd794ad30d1314e86e9206e65edc6cd065a92a5b3e16fb0b604fa` | `fixtures/multilingual-rtl.epub` | Generated & Verified |
| FIX-PDF-01 | Minimal Multi-Page PDF (`sample-doc.pdf`) | Purpose-built original PDF 1.4 | Page navigation, multi-page rendering | `747ab2e569783e5d7451d4cd61e0844f4905cd14c85e0c8ff8281ca416b77275` | `fixtures/sample-doc.pdf` | Generated & Verified |
| FIX-CBZ-01 | Comic archive (`sample-comic.cbz`) | Purpose-built original CBZ | Sequential image navigation, comic spread flow | `33c946353fa6c4c08ccef11f2c73e938c93144ed9c7c72f1f921f3166a98213f` | `fixtures/sample-comic.cbz` | Generated & Verified |
| FIX-MAL-01 | Corrupted archive (`malformed-archive.epub`) | Purpose-built malformed ZIP | Safe corrupt file rejection, error dialog | `bd4c36621c327b3cfd9a4032a73296229b482bdabde433ee03916fe9840120ba` | `fixtures/malformed-archive.epub` | Generated & Verified |
| FIX-MAL-02 | Path traversal attack (`path-traversal.epub`) | Purpose-built unsafe ZIP | Directory traversal protection verification (`NFR-06`) | `773fef2de67c09e3226da6e30219902ce03be95a8355b3ef719711025e17b0a4` | `fixtures/path-traversal.epub` | Generated & Verified |

For each accepted fixture, record a stable ID, exact source/provenance, license or public-domain basis, permitted modification/redistribution, collection date, file format, checksum, expected outputs, and any restrictions. Malformed samples must be purpose-built or otherwise lawfully usable and must not contain live exploit payloads.

## 4. B0 capture checklist (execute only after G0)

- [ ] Pin build/channel, Windows version, UI language, capture date, settings, account/entitlement state, and reproducible setup.
- [ ] Inventory every screen/state/control/default, including loading, empty, hover, focus, disabled, selected, dialog, error, and entitlement states; reconcile with PRD §5.1.
- [ ] Inventory all supported formats and per-format operations; do not infer support from public listings.
- [ ] Record fonts/assets, checksums, licenses, fallback behavior, and evidence-sharing restrictions.
- [ ] Capture comparable app-owned states at 1024×768, 1366×768, and 1920×1080 logical client viewports where supported, plus the smallest supported window; cover 100%, 125%, 150%, and 200% scale where available.
- [ ] Record interaction sequences, shortcuts, focus order, pointer behavior, timing, and persisted outcomes alongside screenshots.
- [ ] Preserve original captures and fixture versions; document dynamic fields and any proposed masks for QA/design approval. Do not mask content, pagination, missing controls, geometry, or whole service/ad areas.
- [ ] Record unresolved facts and blockers. Public documentation or this checklist is not B0 evidence.
