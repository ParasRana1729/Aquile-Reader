# G3 .deb Packaging Evidence (preview, unsigned)

Date: 2026-10-03 (UTC)
Host: Ubuntu, dpkg-deb 1.23.7 (amd64), python3 3.14.4, no fakeroot installed.
Scope: verify and harden `.deb` staging WITHOUT editing `src/` or `tests/`.
Changed files (uncommitted): `scripts/build_deb.sh` only (see §7).
No commit was made.

## 1. Build command + output

Inputs read before build:

- `scripts/build_deb.sh` (dpkg-deb staging, root-free, XDG-respecting)
- `debian/control` (Source `aquile-reader`, `Rules-Requires-Root: no`, amd64,
  Depends `python3, python3-gi, gir1.2-gtk-4.0, gir1.2-adw-1, gir1.2-poppler-0.18`)
- `debian/rules` (`dh $@` minimal)
- `data/org.antigravity.AquileReader.desktop` (source entry; dev-machine
  `Exec=python3 /home/.../run_aquile.py %F`, rewritten at stage time)

Commands:

```bash
mkdir -p /tmp/opencode
bash -n scripts/build_deb.sh   # -> SYNTAX_OK
bash scripts/build_deb.sh --out /tmp/opencode
```

Result: exit 0. Staging verification inside the script passed
(`== verifying staged payload ==`), then `dpkg-deb --build` emitted one
benign warning (no fakeroot on this host):

```text
dpkg-deb: warning: root directory ... has unusual owner or group 1000:1000
dpkg-deb: warning: ignoring 1 warning about the control file(s)
```

This warning is expected without `fakeroot` and does not block install.
The script now prefers `fakeroot dpkg-deb --build` when available.

## 2. Artifact: filename + size

- Path: `/tmp/opencode/aquile-reader_0.1.0-preview_amd64.deb`
- Size: 64062 bytes (63K, `ls -lh`)
- sha256: `85176e7f839b3b93784a2bf6fc00486d3b6e2aab98248fe1255de15482728fdb`
- Before hardening (with `__pycache__/*.pyc` shipped): 201984 bytes.
  After stripping bytecode caches: 64062 bytes.

## 3. `dpkg-deb -f` fields

```text
Package: aquile-reader
Version: 0.1.0-preview
Section: office
Priority: optional
Architecture: amd64
Installed-Size: 424
Depends: python3, python3-gi, gir1.2-gtk-4.0, gir1.2-adw-1, gir1.2-poppler-0.18
Maintainer: Aquile Reader Ubuntu Port Team
Description: Modern, customizable eBook reader (Ubuntu port preview)
 Local DRM-free EPUB/PDF/CBZ/CBR reading with two-column layout,
 annotations, and offline-first library storage. Unsigned preview build.
```

Notes:

- `Installed-Size: 424` was computed but dropped before this fix; the script
  now writes it into `DEBIAN/control` (verified above).
- Architecture is `amd64` per UB-03 proposal; no source build required.

## 4. Content listing excerpt (`dpkg-deb -c`)

61 entries total. Head:

```text
./
./usr/
./usr/bin/
-rwxr-xr-x ./usr/bin/aquile-reader
./usr/share/
./usr/share/applications/
-rw-rw-r-- ./usr/share/applications/org.antigravity.AquileReader.desktop
./usr/share/aquile-reader/
-rwxr-xr-x ./usr/share/aquile-reader/run_aquile.py
./usr/share/aquile-reader/src/
./usr/share/aquile-reader/src/aquile/
... (no __pycache__, no *.pyc after hardening)
./usr/share/doc/aquile-reader/README.Debian
./usr/share/doc/aquile-reader/control.txt
./usr/share/mime/packages/aquile-reader.xml
```

Control archive (`dpkg-deb --ctrl-tarfile | tar -tvf -`):

```text
./
./control   (431 bytes after Installed-Size fix)
```

Privacy: docs carry only `control.txt` + `README.Debian` (offline/entitlement
notes); no secrets. No setuid/setgid entries
(`tar -tvf` shows no `s` mode bits).

## 5. Desktop + MIME verification

Source `data/org.antigravity.AquileReader.desktop`:

```ini
[Desktop Entry]
Name=Aquile Reader
Comment=Modern, customizable eBook reader with two-column layout
Exec=python3 /home/paras/Documents/Projects/Aquile-Reader/run_aquile.py %F
Icon=book-open-symbolic
Terminal=false
Type=Application
Categories=Office;Viewer;Literature;
MimeType=application/epub+zip;application/pdf;application/vnd.comicbook+zip;
StartupNotify=true
```

Staged entry in the `.deb` (after script rewrite + hardening):

```ini
[Desktop Entry]
Name=Aquile Reader
Comment=Modern, customizable eBook reader with two-column layout
Exec=/usr/bin/aquile-reader %F
Icon=book-open-symbolic
Terminal=false
Type=Application
Categories=Office;Viewer;Literature;
MimeType=application/epub+zip;application/pdf;application/vnd.comicbook+zip;application/vnd.comicbook-rar;
StartupNotify=true
NoDisplay=false
```

Checks (against extracted `.deb`):

- `Exec=/usr/bin/aquile-reader %F` — PASS (dev absolute path rewritten).
- `MimeType` contains `application/epub+zip` — PASS.
- `MimeType` contains `application/pdf` — PASS.
- `MimeType` also advertises CBZ + CBR (matches MIME XML) — PASS (hardened;
  source lacked CBR).
- `NoDisplay=false` — PASS in staged file (injected at stage time; source
  file has no `NoDisplay` key — see gap G-1).
- `desktop-file-validate` — exit 0; one non-blocking hint only:

```text
hint: value item "Literature" in key "Categories" ... can be extended with
another category among Education or Science
```

MIME XML (`usr/share/mime/packages/aquile-reader.xml` in `.deb`):

- Registers `application/epub+zip (*.epub)` — PASS.
- Registers `application/pdf (*.pdf)` — PASS.
- Registers `application/vnd.comicbook+zip (*.cbz)` and
  `application/vnd.comicbook-rar (*.cbr)` — PASS.
- Package only registers types; sets no default handler (does not steal
  defaults) — by inspection of XML + no `mimeapps.list` shipped — PASS.

MIME source gap: no versioned `data/*.xml` exists in the repo
(`ls data/*.xml` → absent); the XML is generated inline by
`scripts/build_deb.sh`. Functionally correct, but there is no checked-in
MIME source to review/diff — noted as gap G-2.

## 6. Install / uninstall smoke (root-free, no system mutation)

No `dpkg -i` was run (would mutate the host and need root). Instead:

```bash
rm -rf /tmp/opencode/fs-size && mkdir -p /tmp/opencode/fs-size
dpkg-deb --fsys-tarfile /tmp/opencode/aquile-reader_0.1.0-preview_amd64.deb \
  | tar -x -C /tmp/opencode/fs-size   # exit 0
ls -l /tmp/opencode/fs-size/usr/bin/aquile-reader
# -rwxr-xr-x ... /usr/bin/aquile-reader
cat /tmp/opencode/fs-size/usr/bin/aquile-reader
# #!/bin/sh
# exec python3 /usr/share/aquile-reader/run_aquile.py "$@"
python3 -m py_compile /tmp/opencode/fs-size/usr/share/aquile-reader/run_aquile.py
# compiles OK
rm -rf /tmp/opencode/fs-size  # simulated uninstall leaves no residue
```

- Launcher exists, mode 0755, content delegates to
  `/usr/share/aquile-reader/run_aquile.py` — PASS.
- Direct execution of the extracted launcher is NOT expected to work (it
  references the installed absolute path `/usr/share/...`); `py_compile` of
  the payload entry point passes instead. Full launch remains an AT-10
  on-machine check after a real install.
- No hardcoded `/home/` or `/root/` paths in payload `src` (grep excluding
  `__pycache__` clean) — PASS; runtime data honors
  `$XDG_DATA_HOME` (`src/aquile/storage/database.py:17-18`).
- Simulated uninstall (remove extract dir) is clean — PASS. Real
  install/update/uninstall + data-preservation on Ubuntu 24.04/26.04 remains
  AT-10 work.

## 7. Hardening applied (`scripts/build_deb.sh` only; no `src/`/`tests/` edits)

`git diff --stat`: `scripts/build_deb.sh | 24 ++++... 1 file changed`.
`git status` confirms no `src/` or `tests/` modifications
(an unrelated untracked `src/aquile/ui/tts_controls.py` from concurrent work
was left untouched).

1. Strip `__pycache__` / `*.py[co]` after staging (198K → 63K; avoids stale
   bytecode shadowing source).
2. Write computed `Installed-Size` into `DEBIAN/control` (was computed then
   dropped; `dpkg-deb -f Installed-Size` was empty before).
3. Ensure staged desktop has `NoDisplay=false` (fail-closed check added).
4. Ensure staged desktop `MimeType` covers all registered types incl. CBR
   (source entry lacked `application/vnd.comicbook-rar`).
5. Fail-closed staging checks for `NoDisplay=false` and required desktop
   `MimeType` entries (`application/epub+zip`, `application/pdf`).
6. Use `fakeroot dpkg-deb --build` when available, fallback to plain
   `dpkg-deb` (keeps root-free builds working; silences owner warning where
   fakeroot exists).

`debian/` needed no change: `debian/control` already declares
`Rules-Requires-Root: no` and the `dpkg-deb` staging path does not consume
`debian/rules` beyond documentation.

## 8. Remaining gaps (signed APT is an explicit manual step)

- G-0 (expected, by design): package is UNSIGNED preview. No `Release`/`InRelease`
  signing, no `debsigs`, no repository GPG key, no key custody/rotation.
  Script header + `README.Debian` state this. Do not distribute unsigned
  `.deb`s as updates. Manual release step per `scripts/build_deb.sh` header.
- G-1: source desktop `data/org.antigravity.AquileReader.desktop` still carries
  a dev-machine absolute `Exec` and lacks `NoDisplay=false` / CBR mime; the
  staged file is corrected at build time. Consider versioning the corrected
  entry or a `data/*.desktop.in` template (outside this task's allowed paths).
- G-2: MIME XML has no versioned source (`data/*.xml` absent); generated inline
  in the build script. Consider checking in `data/aquile-reader-mime.xml`.
- G-3: data-file owners are `user:user` without fakeroot (warning only);
  install `fakeroot` on the build host or build via `debuild` for root-owned
  entries.
- G-4: `debian/` has only `control` + `rules` (no `changelog`/`compat` beyond
  `debhelper-compat` dep); sufficient for the current `dpkg-deb` staging route
  but not a full `debuild` source package.
- G-5: real install/update/uninstall, signed/tampered-update handling, X11/Wayland
  launch, file-association end-to-end, and clean-upgrade data preservation on
  Ubuntu 24.04 + 26.04 (AT-10/AT-11) are still unrun — need target machines.
- G-6: `lintian` and `desktop-file-validate` beyond the single validate run above
  are not enforced in CI; `lintian` is not installed on this host.

## 9. Requirement mapping

Per `PRD.md` §Ubuntu scope and `IMPLEMENTATION_PLAN.md` WP-16:

| Requirement | Verdict | Evidence |
|---|---|---|
| UB-03 (amd64 `.deb`, declared deps, signed APT channel; no source build) | PARTIAL (preview) | `Architecture: amd64`, `Depends` declared, no build-from-source needed; APT signing explicitly deferred (G-0). |
| UB-04 (desktop entry + icon, MIME registration w/o stealing defaults, Files/Open-With parity) | PARTIAL (static) | Staged desktop `Exec`/`MimeType`/`NoDisplay=false` verified + `desktop-file-validate` exit 0; MIME XML registers EPUB/PDF/CBZ/CBR without defaults; end-to-end open parity needs AT-10 on target. |
| UB-05 (pickers/portals/clipboard/links/notifications, spaces/Unicode/case/symlink/permission handling) | NOT RUN here | No behavior change in this task; covered by app tests + AT matrix elsewhere. |
| UB-06 (XDG locations/overrides, no hardcoded Windows paths, no root for normal use) | PASS (static) | No `/home/`/`/root/` in payload; `database.py` honors `XDG_DATA_HOME`; launcher is root-free `#!/bin/sh`; no setuid. Multi-user/override runtime checks remain AT scope. |
| WP-16 (production `.deb` + signed APT lifecycle groundwork) | GROUNDWORK ONLY | Unsigned preview builds reproducibly via `scripts/build_deb.sh --out`; signed repo, key custody, tamper/interrupt tests outstanding (G-0, G-5). |

## 10. Reproduction

```bash
bash scripts/build_deb.sh --out /tmp/opencode
dpkg-deb -f /tmp/opencode/aquile-reader_0.1.0-preview_amd64.deb
dpkg-deb -c /tmp/opencode/aquile-reader_0.1.0-preview_amd64.deb | head
rm -rf /tmp/opencode/smoke && mkdir -p /tmp/opencode/smoke \
  && dpkg-deb --fsys-tarfile /tmp/opencode/aquile-reader_0.1.0-preview_amd64.deb \
  | tar -x -C /tmp/opencode/smoke \
  && cat /tmp/opencode/smoke/usr/share/applications/org.antigravity.AquileReader.desktop \
  && cat /tmp/opencode/smoke/usr/share/mime/packages/aquile-reader.xml
```
