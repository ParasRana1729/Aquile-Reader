#!/usr/bin/env bash
# Build an unsigned preview .deb for Aquile Reader via dpkg-deb staging.
# WP-16 groundwork: no root required, no source build needed.
#
# Usage: scripts/build_deb.sh [--version 0.1.0-preview] [--out dist/]
#
# Verifies: desktop entry, MIME associations, and XDG-respecting paths.
#
# NOTE (next manual release step, NOT done here): publish through a signed
# APT repository — generate the Release file, sign it offline with debsigs/
# a repository GPG key (e.g. `dpkg-sig --sign builder pkg.deb` plus
# `apt-ftparchive` + `gpg --clearsign`), keep the private key off build
# hosts, and document key custody/rotation before any public distribution.
set -euo pipefail

VERSION="0.1.0-preview"
OUT_DIR="dist"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

while [ $# -gt 0 ]; do
    case "$1" in
        --version) VERSION="$2"; shift 2 ;;
        --out) OUT_DIR="$2"; shift 2 ;;
        -h|--help)
            echo "Usage: $0 [--version X] [--out DIR]"
            exit 0
            ;;
        *) echo "Unknown argument: $1" >&2; exit 1 ;;
    esac
done

PKG_NAME="aquile-reader"
STAGE="$(mktemp -d /tmp/opencode/aquile-deb-stage.XXXXXX)"
trap 'rm -rf "$STAGE"' EXIT

PKG_DIR="$STAGE/$PKG_NAME"
mkdir -p \
    "$PKG_DIR/DEBIAN" \
    "$PKG_DIR/usr/share/aquile-reader" \
    "$PKG_DIR/usr/share/applications" \
    "$PKG_DIR/usr/share/mime/packages" \
    "$PKG_DIR/usr/share/doc/$PKG_NAME" \
    "$PKG_DIR/usr/bin"

# --- payload ------------------------------------------------------------
cp -r "$REPO_ROOT/src" "$PKG_DIR/usr/share/aquile-reader/src"
cp "$REPO_ROOT/run_aquile.py" "$PKG_DIR/usr/share/aquile-reader/run_aquile.py"
# Hygiene: never ship bytecode caches in the .deb (keeps package small and
# avoids stale .pyc shadowing source on target machines).
find "$PKG_DIR/usr/share/aquile-reader" -type d -name '__pycache__' -prune -exec rm -rf {} + 2>/dev/null || true
find "$PKG_DIR/usr/share/aquile-reader" -type f -name '*.py[co]' -delete 2>/dev/null || true

# Desktop entry: rewrite absolute Exec to the installed launcher path.
sed 's|^Exec=.*|Exec=/usr/bin/aquile-reader %F|' \
    "$REPO_ROOT/data/org.antigravity.AquileReader.desktop" \
    > "$PKG_DIR/usr/share/applications/org.antigravity.AquileReader.desktop"
# Harden staged entry: launcher must be visible (NoDisplay=false) and must
# advertise every MIME type the package registers (EPUB, PDF, CBZ, CBR).
DESKTOP_FILE="$PKG_DIR/usr/share/applications/org.antigravity.AquileReader.desktop"
grep -q '^NoDisplay=' "$DESKTOP_FILE" || printf 'NoDisplay=false\n' >> "$DESKTOP_FILE"
grep -q 'application/vnd.comicbook-rar' "$DESKTOP_FILE" \
    || sed -i 's|^MimeType=.*|MimeType=application/epub+zip;application/pdf;application/vnd.comicbook+zip;application/vnd.comicbook-rar;|' "$DESKTOP_FILE"

# MIME registration for supported formats (reader must not steal defaults:
# package only registers, it sets no default handler).
cat > "$PKG_DIR/usr/share/mime/packages/aquile-reader.xml" <<'EOF'
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
    <comment>Comic book archive</comment>
    <glob pattern="*.cbz"/>
  </mime-type>
  <mime-type type="application/vnd.comicbook-rar">
    <comment>Comic book archive</comment>
    <glob pattern="*.cbr"/>
  </mime-type>
</mime-info>
EOF

# Launcher (root-free at runtime; app data lives under XDG dirs per UB-06).
cat > "$PKG_DIR/usr/bin/aquile-reader" <<'EOF'
#!/bin/sh
exec python3 /usr/share/aquile-reader/run_aquile.py "$@"
EOF
chmod 0755 "$PKG_DIR/usr/bin/aquile-reader"

# Docs: package must ship license/upgrade-path notes, never secrets.
cp "$REPO_ROOT/debian/control" "$PKG_DIR/usr/share/doc/$PKG_NAME/control.txt" 2>/dev/null || true
cat > "$PKG_DIR/usr/share/doc/$PKG_NAME/README.Debian" <<'EOF'
Aquile Reader for Ubuntu (preview package)
==========================================
Local books, annotations, and settings work fully offline with no sign-in.
Entitlements on Linux are local records only; Microsoft Store / Google Play
purchases do not transfer to Ubuntu. The approved Linux upgrade path and
signed APT channel are documented separately and are not part of this
unsigned preview build.
Runtime writes only to XDG user directories; normal use never needs root.
EOF

# --- control metadata ---------------------------------------------------
INSTALLED_SIZE="$(du -sk "$PKG_DIR/usr" | cut -f1)"
cat > "$PKG_DIR/DEBIAN/control" <<EOF
Package: $PKG_NAME
Version: $VERSION
Section: office
Priority: optional
Architecture: amd64
Installed-Size: $INSTALLED_SIZE
Depends: python3, python3-gi, gir1.2-gtk-4.0, gir1.2-adw-1, gir1.2-poppler-0.18
Maintainer: Aquile Reader Ubuntu Port Team
Description: Modern, customizable eBook reader (Ubuntu port preview)
 Local DRM-free EPUB/PDF/CBZ/CBR reading with two-column layout,
 annotations, and offline-first library storage. Unsigned preview build.
EOF

# --- verification (fail closed) -----------------------------------------
echo "== verifying staged payload =="
test -f "$PKG_DIR/usr/share/applications/org.antigravity.AquileReader.desktop" \
    || { echo "FAIL: desktop entry missing" >&2; exit 1; }
grep -q '^Exec=/usr/bin/aquile-reader' \
    "$PKG_DIR/usr/share/applications/org.antigravity.AquileReader.desktop" \
    || { echo "FAIL: desktop Exec path wrong" >&2; exit 1; }
grep -q 'MimeType=' \
    "$PKG_DIR/usr/share/applications/org.antigravity.AquileReader.desktop" \
    || { echo "FAIL: desktop MimeType missing" >&2; exit 1; }
grep -q '^NoDisplay=false' \
    "$PKG_DIR/usr/share/applications/org.antigravity.AquileReader.desktop" \
    || { echo "FAIL: desktop NoDisplay=false missing" >&2; exit 1; }
for mime in 'application/epub+zip' 'application/pdf'; do
    grep -q "$mime" \
        "$PKG_DIR/usr/share/applications/org.antigravity.AquileReader.desktop" \
        || { echo "FAIL: desktop MimeType $mime missing" >&2; exit 1; }
done

for mime in 'application/epub+zip' 'application/pdf' 'application/vnd.comicbook+zip'; do
    grep -q "$mime" "$PKG_DIR/usr/share/mime/packages/aquile-reader.xml" \
        || { echo "FAIL: MIME $mime not registered" >&2; exit 1; }
done

# XDG: no hard-coded home paths, no root-owned runtime writes.
if grep -R --exclude-dir=__pycache__ -n '/home/\|/root/' "$PKG_DIR/usr/share/aquile-reader/src" \
    | grep -v 'run_aquile.py:' ; then
    echo "FAIL: hard-coded home/root path in payload" >&2; exit 1;
fi
test -x "$PKG_DIR/usr/bin/aquile-reader" \
    || { echo "FAIL: launcher not executable" >&2; exit 1; }

# --- build --------------------------------------------------------------
case "$OUT_DIR" in
    /*) ABS_OUT="$OUT_DIR" ;;
    *) ABS_OUT="$REPO_ROOT/$OUT_DIR" ;;
esac
mkdir -p "$ABS_OUT"
DEB="$ABS_OUT/${PKG_NAME}_${VERSION}_amd64.deb"
if command -v fakeroot >/dev/null 2>&1; then
    fakeroot dpkg-deb --build "$PKG_DIR" "$DEB" >/dev/null
else
    dpkg-deb --build "$PKG_DIR" "$DEB" >/dev/null
fi
echo "== package contents =="
dpkg-deb -c "$DEB"
echo "Built (UNSIGNED preview): $DEB"
echo "Next manual step: sign and publish via an authenticated APT channel;"
echo "see the header of this script. Do not distribute unsigned .debs as updates."
