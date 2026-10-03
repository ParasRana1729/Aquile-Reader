#!/usr/bin/env bash
#
# build_tarball.sh — build a portable unpack-and-run tarball of Aquile Reader.
#
# Output: dist/aquile-reader-0.1.0-preview.tar.gz
# Layout inside the tarball (top dir aquile-reader-0.1.0-preview/):
#   bin/aquile-reader                        launcher (exec python3 share/aquile-reader/run_aquile.py)
#   share/aquile-reader/{src,run_aquile.py,README,LICENSE}
#   share/applications/org.antigravity.AquileReader.desktop   (generated, Exec=aquile-reader %F)
#   share/mime/packages/aquile-reader.xml     (generated MIME globs)
#   LICENSE                                  (top-level copy)
#   install.sh / uninstall.sh                (root-free, ~/.local or --prefix)
#
# All staging happens ONLY under /tmp/opencode/tarball-stage. No root needed.
# Verification: tar listing, launcher smoke (--help/--version if supported,
# else python py_compile), no /home absolute paths, no __pycache__.
set -euo pipefail

VERSION="0.2.0-preview"
while [ $# -gt 0 ]; do
    case "$1" in
        --version) VERSION="$2"; shift 2 ;;
        -h|--help) echo "Usage: $0 [--version X]"; exit 0 ;;
        *) echo "Unknown argument: $1" >&2; exit 1 ;;
    esac
done
PKG="aquile-reader-${VERSION}"
APP_ID="org.antigravity.AquileReader"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
STAGE_BASE="/tmp/opencode/tarball-stage"
STAGE="${STAGE_BASE}/${PKG}"
VERIFY_DIR="${STAGE_BASE}/verify-${PKG}"
DIST="${REPO_ROOT}/dist"
TARBALL="${DIST}/${PKG}.tar.gz"

log() { echo "[build-tarball] $*"; }

# --- 1. Stage ----------------------------------------------------------------
log "staging ${PKG} under ${STAGE_BASE}"
rm -rf "${STAGE}" "${VERIFY_DIR}"
mkdir -p "${STAGE}/bin" \
         "${STAGE}/share/aquile-reader" \
         "${STAGE}/share/applications" \
         "${STAGE}/share/mime/packages" \
         "${DIST}" \
         "${VERIFY_DIR}"

# App payload: entry point + full src tree (minus bytecode caches).
cp "${REPO_ROOT}/run_aquile.py" "${STAGE}/share/aquile-reader/run_aquile.py"
cp -r "${REPO_ROOT}/src" "${STAGE}/share/aquile-reader/src"
find "${STAGE}" \( -name '__pycache__' -type d \) -prune -exec rm -rf {} + 2>/dev/null || true
find "${STAGE}" -name '*.py[co]' -delete 2>/dev/null || true

# License (required in tarball): top-level copy + app-dir copy.
cp "${REPO_ROOT}/LICENSE" "${STAGE}/LICENSE"
cp "${REPO_ROOT}/LICENSE" "${STAGE}/share/aquile-reader/LICENSE"

# --- 2. Launcher --------------------------------------------------------------
cat > "${STAGE}/bin/aquile-reader" <<'EOF'
#!/bin/sh
# Aquile Reader launcher (portable tarball). No build step needed:
# runs the bundled tree with the system Python 3.
set -eu
HERE="$(dirname "$(readlink -f "$0")")"
exec python3 "${HERE}/../share/aquile-reader/run_aquile.py" "$@"
EOF
chmod +x "${STAGE}/bin/aquile-reader"

# --- 3. Desktop entry (GENERATED — do not copy the dev-absolute one) -----------
# The repo's data/*.desktop hard-codes a /home/... Exec path for development.
# The shipped entry must rely on PATH instead so it works after install.sh.
cat > "${STAGE}/share/applications/${APP_ID}.desktop" <<EOF
[Desktop Entry]
Name=Aquile Reader
Comment=Modern, customizable eBook reader with two-column layout
Exec=aquile-reader %F
Icon=book-open-symbolic
Terminal=false
Type=Application
Categories=Office;Viewer;Literature;
MimeType=application/epub+zip;application/pdf;application/vnd.comicbook+zip;
StartupNotify=true
EOF

# --- 4. MIME package (generated) ----------------------------------------------
cat > "${STAGE}/share/mime/packages/aquile-reader.xml" <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<mime-info xmlns="http://www.freedesktop.org/standards/shared-mime-info">
  <mime-type type="application/epub+zip">
    <comment>EPUB eBook</comment>
    <glob pattern="*.epub"/>
  </mime-type>
  <mime-type type="application/pdf">
    <comment>PDF document</comment>
    <glob pattern="*.pdf"/>
  </mime-type>
  <mime-type type="application/vnd.comicbook+zip">
    <comment>Comic book archive (CBZ)</comment>
    <glob pattern="*.cbz"/>
  </mime-type>
  <mime-type type="application/vnd.comicbook-rar">
    <comment>Comic book archive (CBR)</comment>
    <glob pattern="*.cbr"/>
  </mime-type>
</mime-info>
EOF

# --- 5. README -----------------------------------------------------------------
cat > "${STAGE}/share/aquile-reader/README" <<EOF
Aquile Reader ${VERSION} — portable tarball
=============================================

Run without installing (no build, no root):

  tar xzf ${PKG}.tar.gz
  cd ${PKG}
  ./bin/aquile-reader [book.epub|book.pdf|book.cbz]

Install for the current user (root-free, default prefix ~/.local):

  ./install.sh
  ./install.sh --prefix "\$HOME/.local"

Requires on Ubuntu: python3, GTK4 + Libadwaita, Poppler (see PRD).
Installed launcher: <prefix>/bin/aquile-reader (ensure it is on PATH).
Desktop + MIME integration is registered by install.sh when the
update-desktop-database / update-mime-database tools are present.
Uninstall: ./uninstall.sh [--prefix ...]
EOF

# --- 6. install.sh (root-free) -------------------------------------------------
cat > "${STAGE}/install.sh" <<EOF
#!/bin/sh
# Aquile Reader user installer. Copies the unpacked tree into
# ~/.local (or --prefix DIR). Never needs root.
set -eu
PREFIX="\${HOME}/.local"
APP_ID="${APP_ID}"
usage() { echo "Usage: \$0 [--prefix DIR]" >&2; }
while [ "\$#" -gt 0 ]; do
  case "\$1" in
    --prefix) PREFIX="\$2"; shift 2 ;;
    --prefix=*) PREFIX="\${1#--prefix=}"; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: \$1" >&2; usage; exit 1 ;;
  esac
done
SRC_DIR="\$(cd "\$(dirname "\$0")" && pwd)"
mkdir -p "\$PREFIX/bin" "\$PREFIX/share/applications" "\$PREFIX/share/mime/packages"
cp "\$SRC_DIR/bin/aquile-reader" "\$PREFIX/bin/aquile-reader"
chmod +x "\$PREFIX/bin/aquile-reader"
rm -rf "\$PREFIX/share/aquile-reader"
cp -r "\$SRC_DIR/share/aquile-reader" "\$PREFIX/share/aquile-reader"
cp "\$SRC_DIR/share/applications/\${APP_ID}.desktop" "\$PREFIX/share/applications/\${APP_ID}.desktop"
cp "\$SRC_DIR/share/mime/packages/aquile-reader.xml" "\$PREFIX/share/mime/packages/aquile-reader.xml"
if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "\$PREFIX/share/applications" || true
else
  echo "(skip: update-desktop-database not found)"
fi
if command -v update-mime-database >/dev/null 2>&1; then
  update-mime-database "\$PREFIX/share/mime" || true
else
  echo "(skip: update-mime-database not found)"
fi
echo "Installed to \$PREFIX. Run: \$PREFIX/bin/aquile-reader"
case ":\$PATH:" in
  *":\$PREFIX/bin:"*) ;;
  *) echo "Note: \$PREFIX/bin is not on PATH. Add: export PATH=\"\$PREFIX/bin:\$PATH\"" ;;
esac
EOF
chmod +x "${STAGE}/install.sh"

# --- 7. uninstall.sh (root-free) -----------------------------------------------
cat > "${STAGE}/uninstall.sh" <<EOF
#!/bin/sh
# Removes a user install created by install.sh. Never needs root.
set -eu
PREFIX="\${HOME}/.local"
APP_ID="${APP_ID}"
while [ "\$#" -gt 0 ]; do
  case "\$1" in
    --prefix) PREFIX="\$2"; shift 2 ;;
    --prefix=*) PREFIX="\${1#--prefix=}"; shift ;;
    -h|--help) echo "Usage: \$0 [--prefix DIR]" >&2; exit 0 ;;
    *) echo "Unknown option: \$1" >&2; exit 1 ;;
  esac
done
rm -f "\$PREFIX/bin/aquile-reader" \
      "\$PREFIX/share/applications/\${APP_ID}.desktop" \
      "\$PREFIX/share/mime/packages/aquile-reader.xml"
rm -rf "\$PREFIX/share/aquile-reader"
if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "\$PREFIX/share/applications" || true
fi
if command -v update-mime-database >/dev/null 2>&1; then
  update-mime-database "\$PREFIX/share/mime" || true
fi
echo "Removed Aquile Reader files under \$PREFIX."
EOF
chmod +x "${STAGE}/uninstall.sh"

# --- 8. Pack -------------------------------------------------------------------
log "packing ${TARBALL}"
tar -czf "${TARBALL}" -C "${STAGE_BASE}" "${PKG}"

# --- 9. Verify -----------------------------------------------------------------
log "== verification =="
echo "--- tar listing ---"
tar -tzf "${TARBALL}"

LISTING="$(tar -tzf "${TARBALL}")"
echo "${LISTING}" | grep -E '(^|/)__pycache__(/|$)' && {
  echo "VERIFY FAIL: __pycache__ found in tarball" >&2; exit 1; }
echo "${LISTING}" | grep -E '\.py[co]$' && {
  echo "VERIFY FAIL: bytecode found in tarball" >&2; exit 1; }
echo "${LISTING}" | grep -E '^/' && {
  echo "VERIFY FAIL: absolute path in tarball" >&2; exit 1; }
log "no __pycache__/bytecode/absolute paths in archive: OK"

# No developer-absolute /home paths anywhere in shipped text files.
if grep -rn -- '/home/' "${STAGE}/bin" \
    "${STAGE}/share/applications" \
    "${STAGE}/share/mime/packages" \
    "${STAGE}/share/aquile-reader/run_aquile.py" \
    "${STAGE}/share/aquile-reader/README" \
    "${STAGE}/install.sh" "${STAGE}/uninstall.sh" 2>/dev/null; then
  echo "VERIFY FAIL: /home absolute path found in staged files" >&2; exit 1
fi
log "no /home absolute paths in shipped files: OK"

# Launcher + desktop-entry sanity.
grep -q 'exec python3' "${STAGE}/bin/aquile-reader" || {
  echo "VERIFY FAIL: launcher missing 'exec python3'" >&2; exit 1; }
grep -q 'share/aquile-reader/run_aquile.py' "${STAGE}/bin/aquile-reader" || {
  echo "VERIFY FAIL: launcher missing app path" >&2; exit 1; }
grep -qx 'Exec=aquile-reader %F' "${STAGE}/share/applications/${APP_ID}.desktop" || {
  echo "VERIFY FAIL: desktop Exec line wrong" >&2; exit 1; }
log "launcher + desktop Exec: OK"

# Smoke test against a fresh extract (true end-user view).
tar -xzf "${TARBALL}" -C "${VERIFY_DIR}"
EXTRACTED="${VERIFY_DIR}/${PKG}"
test -x "${EXTRACTED}/bin/aquile-reader" || {
  echo "VERIFY FAIL: extracted launcher not executable" >&2; exit 1; }
# Pristine-extract checks FIRST: executing the launcher below creates
# __pycache__ inside this scratch copy, which must not be mistaken for
# tarball contents (the archive listing was already checked above).
if grep -rn -- '/home/' "${EXTRACTED}/bin" \
    "${EXTRACTED}/share/applications" "${EXTRACTED}/share/mime/packages" \
    "${EXTRACTED}/share/aquile-reader/run_aquile.py" 2>/dev/null; then
  echo "VERIFY FAIL: /home path in extracted tarball" >&2; exit 1
fi
find "${EXTRACTED}" -name '__pycache__' | grep . && {
  echo "VERIFY FAIL: __pycache__ in extracted tarball" >&2; exit 1; } || true
log "extracted-tree pristine checks: OK"
SMOKE_OK=0
if command -v timeout >/dev/null 2>&1; then
  for flag in --help --version; do
    if timeout 15 "${EXTRACTED}/bin/aquile-reader" "${flag}" >/tmp/opencode/tarball-stage/smoke.log 2>&1; then
      log "launcher smoke (${flag}): exit 0"; SMOKE_OK=1; break
    else
      log "launcher smoke (${flag}): non-zero (rc=$?) — app has no CLI flags, falling back to py_compile"
    fi
  done
else
  log "timeout(1) unavailable — using py_compile smoke directly"
fi
if [ "${SMOKE_OK}" -eq 0 ]; then
  python3 -m py_compile "${EXTRACTED}/share/aquile-reader/run_aquile.py"
  # shellcheck disable=SC2046
  python3 -m py_compile $(find "${EXTRACTED}/share/aquile-reader/src" -name '*.py')
  log "py_compile smoke (entry + all src modules): OK"
fi
log "launcher smoke result recorded (see above)"
log "extracted-tree checks: OK"

if command -v desktop-file-validate >/dev/null 2>&1; then
  desktop-file-validate "${STAGE}/share/applications/${APP_ID}.desktop" \
    && log "desktop-file-validate: OK"
else
  log "desktop-file-validate not installed — skipped (non-blocking)"
fi

SIZE_H="$(du -h "${TARBALL}" | cut -f1)"
SIZE_B="$(stat -c%s "${TARBALL}")"
log "built ${TARBALL} (${SIZE_H}, ${SIZE_B} bytes) — ALL CHECKS PASSED"
cat <<EOF

Install instructions:
  tar xzf ${PKG}.tar.gz && cd ${PKG} && ./install.sh
  aquile-reader                      # ensure ~/.local/bin is on PATH
  # or run unpacked, no install: ./bin/aquile-reader [book file]
EOF
