#!/usr/bin/env bash
# Build an unsigned preview .rpm for Aquile Reader via a local rpmbuild.
# No root required: rpmbuild runs with _topdir under /tmp/opencode/rpm-stage,
# and the toolchain is bootstrapped with apt-get download + dpkg -x when the
# system has no rpmbuild.
#
# Usage: scripts/build_rpm.sh [--version 0.1.0] [--release 1.preview] [--out dist/]
#
# Verifies: launcher, desktop entry, MIME associations, payload hygiene,
# and XDG-respecting paths via rpm -qpi/-qpl.
#
# NOTE (next manual release step, NOT done here): sign the rpm (rpmsign with
# an offline key) and publish through a signed yum/dnf repository
# (createrepo_c + signed repomd). Keep the private key off build hosts and
# document key custody/rotation before any public distribution. Do not
# distribute unsigned .rpms as updates.
set -euo pipefail

SPEC_VERSION="0.1.0"
SPEC_RELEASE="1.preview"
OUT_DIR="dist"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

while [ $# -gt 0 ]; do
    case "$1" in
        --version) SPEC_VERSION="$2"; shift 2 ;;
        --release) SPEC_RELEASE="$2"; shift 2 ;;
        --out) OUT_DIR="$2"; shift 2 ;;
        -h|--help)
            echo "Usage: $0 [--version X] [--release Y] [--out DIR]"
            exit 0
            ;;
        *) echo "Unknown argument: $1" >&2; exit 1 ;;
    esac
done

PKG_NAME="aquile-reader"
SPEC_FILE="$REPO_ROOT/packaging/rpm/aquile-reader.spec"
RPM_TOOLS="/tmp/opencode/rpm-tools"
STAGE_BASE="/tmp/opencode/rpm-stage"

# --- toolchain: system rpmbuild or root-free bootstrap --------------------
RPMBUILD_BIN=""
RPM_BIN=""

find_system_rpmbuild() {
    if command -v rpmbuild >/dev/null 2>&1; then
        RPMBUILD_BIN="$(command -v rpmbuild)"
        RPM_BIN="$(command -v rpm || echo "")"
        return 0
    fi
    return 1
}

bootstrap_rpmbuild() {
    # Reuse a previous bootstrap when it still runs (avoids re-downloading).
    if [ -x "$RPM_TOOLS/usr/bin/rpmbuild" ]; then
        export LD_LIBRARY_PATH="$RPM_TOOLS/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
        export RPM_CONFIGDIR="$RPM_TOOLS/usr/lib/rpm"
        if "$RPM_TOOLS/usr/bin/rpmbuild" --version >/dev/null 2>&1; then
            echo "== reusing bootstrapped rpmbuild in $RPM_TOOLS =="
            RPMBUILD_BIN="$RPM_TOOLS/usr/bin/rpmbuild"
            RPM_BIN="$RPM_TOOLS/usr/bin/rpm"
            return 0
        fi
        echo "== previous bootstrap broken; re-bootstrapping into $RPM_TOOLS =="
    fi
    if ! command -v apt-get >/dev/null 2>&1; then
        echo "FAIL: no system rpmbuild and no apt-get to bootstrap one." >&2
        echo "Install the 'rpm' package (or run on a system with it) and retry." >&2
        return 1
    fi
    if ! command -v dpkg-deb >/dev/null 2>&1 && ! command -v dpkg >/dev/null 2>&1; then
        echo "FAIL: need dpkg/dpkg-deb to unpack the bootstrapped rpm stack." >&2
        return 1
    fi
    mkdir -p "$RPM_TOOLS"
    local dl_dir
    dl_dir="$(mktemp -d "${TMPDIR:-/tmp}/rpm-bootstrap-dl.XXXXXX")"
    trap "rm -rf '$dl_dir'" RETURN
    # Ubuntu resolute names for the rpm 6.0.1 stack. If distro versions move,
    # apt-get download resolves the current names; unpack every .deb fetched.
    (
        cd "$dl_dir"
        apt-get download rpm rpm2cpio librpm10 librpmbuild10 librpmio10 \
            librpmsign10 rpm-common librpm-sequoia-1 libfsverity0 \
            liblua5.3-0 libpopt0
    )
    for deb in "$dl_dir"/*.deb; do
        dpkg -x "$deb" "$RPM_TOOLS"
    done
    rm -rf "$dl_dir"
    trap - RETURN
    export LD_LIBRARY_PATH="$RPM_TOOLS/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
    export RPM_CONFIGDIR="$RPM_TOOLS/usr/lib/rpm"
    RPMBUILD_BIN="$RPM_TOOLS/usr/bin/rpmbuild"
    RPM_BIN="$RPM_TOOLS/usr/bin/rpm"
    "$RPMBUILD_BIN" --version
}

if ! find_system_rpmbuild; then
    bootstrap_rpmbuild || {
        echo "FAIL: rpm bootstrap failed; exact error above." >&2
        echo "Manual fallback: install 'rpm' as root (or via your distro's" >&2
        echo "package manager) and re-run $0." >&2
        exit 1
    }
fi

# Bootstrapped binaries need their config/lib env even when rpmbuild exists
# under $RPM_TOOLS from a previous run.
if [ -x "$RPM_TOOLS/usr/bin/rpmbuild" ] && [ "$RPMBUILD_BIN" = "$RPM_TOOLS/usr/bin/rpmbuild" ]; then
    export LD_LIBRARY_PATH="$RPM_TOOLS/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
    export RPM_CONFIGDIR="$RPM_TOOLS/usr/lib/rpm"
fi
if [ -z "$RPM_BIN" ]; then
    if [ -x "$RPM_TOOLS/usr/bin/rpm" ]; then
        RPM_BIN="$RPM_TOOLS/usr/bin/rpm"
        export LD_LIBRARY_PATH="$RPM_TOOLS/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
        export RPM_CONFIGDIR="$RPM_TOOLS/usr/lib/rpm"
    else
        echo "FAIL: rpm query tool missing (need 'rpm' for verification)." >&2
        exit 1
    fi
fi
echo "Using rpmbuild: $RPMBUILD_BIN"
echo "Using rpm:      $RPM_BIN"

# --- stage: _topdir strictly under /tmp/opencode/rpm-stage -----------------
mkdir -p "$STAGE_BASE"
TOPDIR="$(mktemp -d "$STAGE_BASE/topdir.XXXXXX")"
trap 'rm -rf "$TOPDIR"' EXIT
mkdir -p "$TOPDIR"/{BUILD,RPMS,SOURCES,SPECS,SRPMS}
# Stage-local rpmdb: keeps non-root build/queries off /var/lib/rpm entirely.
RPM_DB="$TOPDIR/rpmdb"
mkdir -p "$RPM_DB"

# Source tarball assembled from repo-relative paths only (never /home/...).
TARBALL_DIR="$TOPDIR/tarball/$PKG_NAME-$SPEC_VERSION"
mkdir -p "$TARBALL_DIR"
cp -r "$REPO_ROOT/src" "$TARBALL_DIR/src"
cp "$REPO_ROOT/run_aquile.py" "$TARBALL_DIR/run_aquile.py"
mkdir -p "$TARBALL_DIR/data"
cp -r "$REPO_ROOT/data/icons" "$TARBALL_DIR/data/icons"
cp "$REPO_ROOT/data/org.antigravity.AquileReader.desktop" \
    "$TARBALL_DIR/data/org.antigravity.AquileReader.desktop"
cp "$REPO_ROOT/LICENSE" "$TARBALL_DIR/LICENSE"
find "$TARBALL_DIR" -type d -name '__pycache__' -prune -exec rm -rf {} + \
    2>/dev/null || true
find "$TARBALL_DIR" -type f -name '*.py[co]' -delete 2>/dev/null || true
tar -czf "$TOPDIR/SOURCES/$PKG_NAME-$SPEC_VERSION.tar.gz" \
    -C "$TOPDIR/tarball" "$PKG_NAME-$SPEC_VERSION"

# Stage a copy of the spec with the requested Version/Release (keeps the
# repo spec as the default; overrides stay inside the stage dir).
STAGED_SPEC="$TOPDIR/SPECS/$PKG_NAME.spec"
cp "$SPEC_FILE" "$STAGED_SPEC"
sed -i "s|^Version:.*|Version:        $SPEC_VERSION|" "$STAGED_SPEC"
sed -i "s|^Release:.*|Release:        $SPEC_RELEASE%{?dist}|" "$STAGED_SPEC"
grep -q "^Version: *$SPEC_VERSION" "$STAGED_SPEC" \
    || { echo "FAIL: staged spec Version mismatch" >&2; exit 1; }
grep -q "^Release: *$SPEC_RELEASE" "$STAGED_SPEC" \
    || { echo "FAIL: staged spec Release mismatch" >&2; exit 1; }

# --- build -----------------------------------------------------------------
# --dbpath keeps the non-root build off /var/lib/rpm entirely.
"$RPMBUILD_BIN" -bb "$STAGED_SPEC" \
    --define "_topdir $TOPDIR" \
    --define "_rpmdir $TOPDIR/RPMS" \
    --define "_dbpath $RPM_DB" \
    --dbpath "$RPM_DB"

RPM_FILE="$(find "$TOPDIR/RPMS" -name '*.rpm' | head -n 1)"
[ -n "$RPM_FILE" ] || { echo "FAIL: no rpm produced" >&2; exit 1; }

case "$OUT_DIR" in
    /*) ABS_OUT="$OUT_DIR" ;;
    *) ABS_OUT="$REPO_ROOT/$OUT_DIR" ;;
esac
mkdir -p "$ABS_OUT"
OUT_RPM="$ABS_OUT/$(basename "$RPM_FILE")"
cp "$RPM_FILE" "$OUT_RPM"

# --- verification (fail closed) --------------------------------------------
QRY=( "$RPM_BIN" --dbpath "$RPM_DB" )

echo "== rpm info =="
"${QRY[@]}" -qpi "$OUT_RPM"
echo "== rpm payload =="
"${QRY[@]}" -qpl "$OUT_RPM"

PAYLOAD_LIST="$("${QRY[@]}" -qpl "$OUT_RPM")"
for want in '/usr/bin/aquile-reader' \
            '/usr/share/aquile-reader/run_aquile.py' \
            '/usr/share/applications/org.antigravity.AquileReader.desktop' \
            '/usr/share/mime/packages/aquile-reader.xml'; do
    echo "$PAYLOAD_LIST" | grep -q "$want" \
        || { echo "FAIL: payload missing $want" >&2; exit 1; }
done
if echo "$PAYLOAD_LIST" | grep -E '__pycache__|\.py[co]$'; then
    echo "FAIL: bytecode cache shipped in rpm" >&2; exit 1
fi

# Extract payload to the stage dir (never to system paths) for content checks.
PAYDIR="$TOPDIR/paycheck"
mkdir -p "$PAYDIR"
# rpm2cpio may live beside the bootstrapped rpm or on the system.
RPM2CPIO=""
if command -v rpm2cpio >/dev/null 2>&1; then
    RPM2CPIO="rpm2cpio"
elif [ -x "$RPM_TOOLS/usr/bin/rpm2cpio" ]; then
    RPM2CPIO="$RPM_TOOLS/usr/bin/rpm2cpio"
fi
[ -n "$RPM2CPIO" ] || { echo "FAIL: rpm2cpio not found" >&2; exit 1; }
(
    cd "$PAYDIR"
    "$RPM2CPIO" "$OUT_RPM" | cpio -idm --quiet
)
grep -q '^exec python3 /usr/share/aquile-reader/run_aquile.py' \
    "$PAYDIR/usr/bin/aquile-reader" \
    || { echo "FAIL: launcher payload wrong" >&2; exit 1; }
test -x "$PAYDIR/usr/bin/aquile-reader" \
    || { echo "FAIL: launcher not executable" >&2; exit 1; }
grep -q '^Exec=/usr/bin/aquile-reader %F' \
    "$PAYDIR/usr/share/applications/org.antigravity.AquileReader.desktop" \
    || { echo "FAIL: desktop Exec path wrong" >&2; exit 1; }
grep -q '^NoDisplay=false' \
    "$PAYDIR/usr/share/applications/org.antigravity.AquileReader.desktop" \
    || { echo "FAIL: desktop NoDisplay=false missing" >&2; exit 1; }
for mime in 'application/epub+zip' 'application/pdf' \
            'application/vnd.comicbook+zip' 'application/vnd.comicbook-rar'; do
    grep -q "$mime" "$PAYDIR/usr/share/mime/packages/aquile-reader.xml" \
        || { echo "FAIL: MIME $mime not registered" >&2; exit 1; }
    grep -q "$mime" \
        "$PAYDIR/usr/share/applications/org.antigravity.AquileReader.desktop" \
        || { echo "FAIL: desktop MimeType $mime missing" >&2; exit 1; }
done

# XDG: no hard-coded home paths, no root-owned runtime writes in payload.
if grep -R --exclude-dir=__pycache__ -n '/home/\|/root/' \
        "$PAYDIR/usr/share/aquile-reader/src" | grep -v 'run_aquile.py:'; then
    echo "FAIL: hard-coded home/root path in payload" >&2; exit 1
fi

echo "Built (UNSIGNED preview): $OUT_RPM"
echo "Size: $(du -h "$OUT_RPM" | cut -f1) ($(stat -c%s "$OUT_RPM") bytes)"
echo "Next manual step: sign and publish via an authenticated yum/dnf channel;"
echo "see the header of this script. Do not distribute unsigned .rpms as updates."
