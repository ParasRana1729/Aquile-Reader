#!/usr/bin/env bash
# Build a root-free preview AppImage for Aquile Reader (manual type-2 method).
#
# Usage: scripts/build_appimage.sh [--version 0.1.0-preview] [--out dist/]
#        [--runtime-url URL]
#
# Method (no appimagetool, no root, no FUSE required at build time):
#   1. curl the official Type-2 runtime (runtime-x86_64) from
#      https://github.com/AppImage/type2-runtime/releases
#   2. stage an AppDir in /tmp/opencode/appimage-stage from repo files
#   3. mksquashfs the AppDir, then cat runtime + squashfs > *.AppImage
#
# The AppImage uses the HOST /usr/bin/python3 + system GTK4/Libadwaita stack
# (no interpreter bundled); AppRun fails with a clear message when the host
# lacks python3 or PyGObject. Offline local reading still applies once the
# host dependencies exist.
#
# NOTE (preview gaps, NOT done here): unsigned build, no zsync update channel,
# host-dependency on system GIR packages, placeholder SVG icon generated at
# build time (repo ships no icon asset). See the verification summary printed
# by this script.
set -euo pipefail

VERSION="0.1.0-preview"
ARCH="x86_64"
OUT_DIR="dist"
RUNTIME_URL="${AQUILE_RUNTIME_URL:-https://github.com/AppImage/type2-runtime/releases/download/continuous/runtime-x86_64}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

while [ $# -gt 0 ]; do
    case "$1" in
        --version) VERSION="$2"; shift 2 ;;
        --out) OUT_DIR="$2"; shift 2 ;;
        --runtime-url) RUNTIME_URL="$2"; shift 2 ;;
        -h|--help)
            echo "Usage: $0 [--version X] [--out DIR] [--runtime-url URL]"
            exit 0
            ;;
        *) echo "Unknown argument: $1" >&2; exit 1 ;;
    esac
done

if [ "$(uname -m)" != "$ARCH" ]; then
    echo "FAIL: host arch '$(uname -m)' != target '$ARCH' runtime" >&2
    exit 1
fi
for tool in curl mksquashfs file; do
    command -v "$tool" >/dev/null 2>&1 \
        || { echo "FAIL: required tool '$tool' not found" >&2; exit 1; }
done

APP_ID="aquile-reader"
STAGE="/tmp/opencode/appimage-stage"
APPDIR="$STAGE/AppDir"
RUNTIME_BIN="$STAGE/runtime-$ARCH"
SQUASHFS_IMG="$STAGE/app.squashfs"

rm -rf "$STAGE"
mkdir -p "$STAGE" "$APPDIR/usr/share/aquile-reader" "$APPDIR/usr/bin"

# --- 1. runtime download + verification ----------------------------------
echo "== downloading type-2 runtime =="
curl -fSL --retry 3 -o "$RUNTIME_BIN" "$RUNTIME_URL"
test -s "$RUNTIME_BIN" \
    || { echo "FAIL: downloaded runtime is empty" >&2; exit 1; }
# ELF magic: 7f 45 4c 46 ("\x7fELF")
if ! head -c 4 "$RUNTIME_BIN" | od -An -tx1 | grep -q '7f 45 4c 46'; then
    echo "FAIL: downloaded runtime lacks ELF magic" >&2
    file "$RUNTIME_BIN" >&2 || true
    exit 1
fi
chmod +x "$RUNTIME_BIN"
echo "runtime OK: $(wc -c < "$RUNTIME_BIN") bytes, $(file -b "$RUNTIME_BIN" | cut -d, -f1)"

# --- 2. AppDir staging (from repo files only) -----------------------------
echo "== staging AppDir =="
cp -r "$REPO_ROOT/src" "$APPDIR/usr/share/aquile-reader/src"
mkdir -p "$APPDIR/usr/share/aquile-reader/data"
cp -r "$REPO_ROOT/data/icons" "$APPDIR/usr/share/aquile-reader/data/icons"
cp "$REPO_ROOT/run_aquile.py" "$APPDIR/usr/share/aquile-reader/run_aquile.py"
# Hygiene: never ship bytecode caches (stale .pyc could shadow source).
find "$APPDIR/usr/share/aquile-reader" -type d -name '__pycache__' -prune -exec rm -rf {} + 2>/dev/null || true
find "$APPDIR/usr/share/aquile-reader" -type f -name '*.py[co]' -delete 2>/dev/null || true
test -f "$APPDIR/usr/share/aquile-reader/src/aquile/app.py" \
    || { echo "FAIL: staged payload missing src/aquile/app.py" >&2; exit 1; }

# XDG/root hygiene: no hard-coded home paths in the payload.
if grep -R --exclude-dir=__pycache__ -n '/home/\|/root/' "$APPDIR/usr/share/aquile-reader/src" 2>/dev/null; then
    echo "FAIL: hard-coded home/root path in payload" >&2; exit 1
fi

# AppRun: host-interpreter launcher with clear failure messages.
cat > "$APPDIR/AppRun" <<'EOF'
#!/bin/sh
# AppRun for Aquile Reader (preview AppImage).
# Uses the HOST /usr/bin/python3 + system GTK4/Libadwaita stack;
# no interpreter is bundled. Local books work offline once host deps exist.
set -u
APPDIR="$(dirname "$(readlink -f "$0" 2>/dev/null || echo "$0")")"
export APPDIR
APP_MAIN="$APPDIR/usr/share/aquile-reader/run_aquile.py"
if [ ! -x /usr/bin/python3 ]; then
    echo "Aquile Reader: /usr/bin/python3 not found. Install python3, python3-gi and the GTK4/Libadwaita GIR packages, then retry." >&2
    exit 1
fi
if ! /usr/bin/python3 -c 'import gi' 2>/dev/null; then
    echo "Aquile Reader: PyGObject (python3-gi) not found for /usr/bin/python3. Install python3-gi, gir1.2-gtk-4.0, gir1.2-adw-1 and gir1.2-poppler-0.18, then retry." >&2
    exit 1
fi
exec /usr/bin/python3 "$APP_MAIN" "$@"
EOF
chmod 0755 "$APPDIR/AppRun"

# In-payload launcher (target of Exec= in the desktop entry).
cat > "$APPDIR/usr/bin/aquile-reader" <<'EOF'
#!/bin/sh
HERE="$(dirname "$(readlink -f "$0" 2>/dev/null || echo "$0")")"
APPDIR="$(cd "$HERE/../.." && pwd)"
export APPDIR
exec "$APPDIR/AppRun" "$@"
EOF
chmod 0755 "$APPDIR/usr/bin/aquile-reader"

# Desktop entry: derived from the repo source; Exec points at the
# in-payload launcher per AppImage convention (Exec=<name> %F).
sed -e 's|^Exec=.*|Exec=aquile-reader %F|' \
    -e 's|^Icon=.*|Icon=aquile-reader|' \
    "$REPO_ROOT/data/org.antigravity.AquileReader.desktop" \
    > "$APPDIR/$APP_ID.desktop"
DESKTOP_FILE="$APPDIR/$APP_ID.desktop"
grep -q '^NoDisplay=' "$DESKTOP_FILE" || printf 'NoDisplay=false\n' >> "$DESKTOP_FILE"
grep -q 'application/vnd.comicbook-rar' "$DESKTOP_FILE" \
    || sed -i 's|^MimeType=.*|MimeType=application/epub+zip;application/pdf;application/vnd.comicbook+zip;application/vnd.comicbook-rar;|' "$DESKTOP_FILE"
grep -q '^Exec=aquile-reader %F' "$DESKTOP_FILE" \
    || { echo "FAIL: staged desktop Exec line wrong" >&2; exit 1; }
grep -q '^Icon=aquile-reader' "$DESKTOP_FILE" \
    || { echo "FAIL: staged desktop Icon line wrong" >&2; exit 1; }
chmod 0644 "$DESKTOP_FILE"

# Placeholder icon (repo ships no icon asset): minimal book glyph SVG.
# Replaced by real branding once approved assets exist.
cat > "$APPDIR/aquile-reader.svg" <<'EOF'
<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256" viewBox="0 0 256 256">
  <rect x="24" y="16" width="208" height="224" rx="16" fill="#1c71d8"/>
  <path d="M128 16v224" stroke="#ffffff" stroke-width="8"/>
  <path d="M52 64h48M52 96h48M156 64h48M156 96h48" stroke="#ffffff" stroke-width="10" stroke-linecap="round"/>
</svg>
EOF
chmod 0644 "$APPDIR/aquile-reader.svg"
cp "$APPDIR/aquile-reader.svg" "$APPDIR/.DirIcon"

# --- 3. squashfs + assemble -------------------------------------------------
# NOTE: the upstream type-2 runtime embeds a squashfs parser that supports
# only zlib/gzip and zstd (xz images fail at run time with
# "Squashfs image uses xz compression"), so gzip is the default here.
echo "== building squashfs =="
if ! mksquashfs "$APPDIR" "$SQUASHFS_IMG" -comp gzip -noappend >/dev/null; then
    echo "gzip compression failed, retrying with zstd"
    rm -f "$SQUASHFS_IMG"
    mksquashfs "$APPDIR" "$SQUASHFS_IMG" -comp zstd -noappend >/dev/null
fi
test -s "$SQUASHFS_IMG" \
    || { echo "FAIL: squashfs image is empty" >&2; exit 1; }

case "$OUT_DIR" in
    /*) ABS_OUT="$OUT_DIR" ;;
    *) ABS_OUT="$REPO_ROOT/$OUT_DIR" ;;
esac
mkdir -p "$ABS_OUT"
OUT_IMG="$ABS_OUT/AquileReader-${VERSION}-${ARCH}.AppImage"
cat "$RUNTIME_BIN" "$SQUASHFS_IMG" > "$OUT_IMG"
chmod +x "$OUT_IMG"

# --- 4. verification (fail closed) ------------------------------------------
echo "== verifying AppImage =="
file "$OUT_IMG"
if ! head -c 4 "$OUT_IMG" | od -An -tx1 | grep -q '7f 45 4c 46'; then
    echo "FAIL: AppImage lacks ELF magic" >&2; exit 1
fi

if command -v desktop-file-validate >/dev/null 2>&1; then
    desktop-file-validate "$DESKTOP_FILE" \
        || { echo "FAIL: desktop-file-validate rejected entry" >&2; exit 1; }
    echo "desktop-file-validate: OK"
else
    echo "desktop-file-validate: not available, skipped"
fi

# Payload check: extract without FUSE (--appimage-extract needs no FUSE);
# fall back to a squashfs-magic offset check when execution is unavailable.
VERIFY_TMP="$(mktemp -d /tmp/opencode/appimage-verify.XXXXXX)"
trap 'rm -rf "$VERIFY_TMP"' EXIT
if ( cd "$VERIFY_TMP" && "$OUT_IMG" --appimage-extract >/dev/null 2>&1 ) \
    && test -x "$VERIFY_TMP/squashfs-root/AppRun"; then
    echo "extract test: OK (squashfs-root/AppRun present)"
    test -f "$VERIFY_TMP/squashfs-root/$APP_ID.desktop" \
        || { echo "FAIL: extracted desktop entry missing" >&2; exit 1; }
    grep -q '^Exec=aquile-reader %F' "$VERIFY_TMP/squashfs-root/$APP_ID.desktop" \
        || { echo "FAIL: extracted desktop Exec line wrong" >&2; exit 1; }
    test -f "$VERIFY_TMP/squashfs-root/usr/share/aquile-reader/run_aquile.py" \
        || { echo "FAIL: extracted run_aquile.py missing" >&2; exit 1; }
    test -f "$VERIFY_TMP/squashfs-root/usr/share/aquile-reader/src/aquile/app.py" \
        || { echo "FAIL: extracted src/aquile/app.py missing" >&2; exit 1; }
    echo "extracted payload: desktop + run_aquile.py + src present, Exec line OK"
else
    echo "extract test: runtime execution unavailable, using offset check"
    SQFS_OFF="$(grep -aob 'hsqs' "$OUT_IMG" | head -n1 | cut -d: -f1 || true)"
    test -n "${SQFS_OFF:-}" \
        || { echo "FAIL: no squashfs magic (hsqs) found in AppImage" >&2; exit 1; }
    test "$SQFS_OFF" -gt 0 \
        || { echo "FAIL: squashfs magic at offset 0 (runtime missing?)" >&2; exit 1; }
    echo "offset check: OK (squashfs magic at byte $SQFS_OFF of $(wc -c < "$OUT_IMG") bytes)"
fi

echo "Built: $OUT_IMG ($(wc -c < "$OUT_IMG") bytes)"
echo "Preview gaps: UNSIGNED, no zsync update channel; requires host /usr/bin/python3 + python3-gi/GTK4 GIR packages; running the AppImage needs FUSE on the host."
