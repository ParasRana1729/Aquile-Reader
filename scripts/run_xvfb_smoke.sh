#!/usr/bin/env bash
# scripts/run_xvfb_smoke.sh
# Automated Xvfb launch smoke test runner for Aquile Reader.
# Ensures application launches cleanly without SIGABRT/Adwaita-ERROR under isolated profiles.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
XVFB_BIN_DIR="/tmp/opencode/xvfb-pkgs/root/usr/bin"
XVFB_LIB_DIR="/tmp/opencode/xvfb-pkgs/root/usr/lib/x86_64-linux-gnu"

# Configure toolchain search paths
if [ -d "$XVFB_BIN_DIR" ]; then
    export PATH="$XVFB_BIN_DIR:$PATH"
fi
if [ -d "$XVFB_LIB_DIR" ]; then
    export LD_LIBRARY_PATH="$XVFB_LIB_DIR:${LD_LIBRARY_PATH:-}"
fi

# Verify required binaries
for cmd in Xvfb xwd xwdtopnm pnmtopng; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo "ERROR: Required toolchain binary '$cmd' not found in PATH or $XVFB_BIN_DIR." >&2
        echo "To bootstrap the toolchain, run:" >&2
        echo "  mkdir -p /tmp/opencode/xvfb-pkgs && cd /tmp/opencode/xvfb-pkgs && \\" >&2
        echo "  apt-get download xvfb x11-apps netpbm libnetpbm11t64 && dpkg -x *.deb root/" >&2
        exit 1
    fi
done

# CLI argument parsing
DISPLAY_NUM="${AQUILE_TEST_DISPLAY:-99}"
SCREENSHOT_PATH="${1:-$REPO_ROOT/build/smoke_screenshot.png}"
TARGET_SCRIPT="${2:-$REPO_ROOT/run_aquile.py}"
KEEP_PROFILE=0

mkdir -p "$(dirname "$SCREENSHOT_PATH")"

# Manage Xvfb Display
XVFB_STARTED=0
XVFB_PID=""

if DISPLAY=":$DISPLAY_NUM" xwd -root -silent -out /dev/null 2>/dev/null; then
    echo "Using existing active X display :$DISPLAY_NUM"
else
    echo "Starting Xvfb on display :$DISPLAY_NUM (1280x800x24)..."
    Xvfb ":$DISPLAY_NUM" -screen 0 1280x800x24 -noreset >/dev/null 2>&1 &
    XVFB_PID=$!
    XVFB_STARTED=1

    # Wait for display readiness
    for i in $(seq 1 30); do
        if DISPLAY=":$DISPLAY_NUM" xwd -root -silent -out /dev/null 2>/dev/null; then
            break
        fi
        sleep 0.1
    done
    if ! DISPLAY=":$DISPLAY_NUM" xwd -root -silent -out /dev/null 2>/dev/null; then
        echo "ERROR: Xvfb failed to become ready on display :$DISPLAY_NUM." >&2
        kill -9 "$XVFB_PID" 2>/dev/null || true
        exit 1
    fi
fi

cleanup() {
    if [ "$XVFB_STARTED" -eq 1 ] && [ -n "$XVFB_PID" ]; then
        kill "$XVFB_PID" 2>/dev/null || true
        wait "$XVFB_PID" 2>/dev/null || true
    fi
}
trap cleanup EXIT

# Prepare fresh isolated XDG environment
TEST_TMP=$(mktemp -d /tmp/aqtest-smoke-sh.XXXXXX)
export XDG_DATA_HOME="$TEST_TMP/data"
export XDG_CONFIG_HOME="$TEST_TMP/config"
export XDG_CACHE_HOME="$TEST_TMP/cache"
mkdir -p "$XDG_DATA_HOME" "$XDG_CONFIG_HOME" "$XDG_CACHE_HOME"

# Force X11 backend and target display (essential for environments with Wayland)
export DISPLAY=":$DISPLAY_NUM"
export GDK_BACKEND=x11
unset WAYLAND_DISPLAY

APP_LOG="$TEST_TMP/app.log"
echo "Launching target application: $TARGET_SCRIPT"
echo "Isolated XDG_DATA_HOME: $XDG_DATA_HOME"

if [[ "$TARGET_SCRIPT" == *.py ]]; then
    python3 "$TARGET_SCRIPT" > "$APP_LOG" 2>&1 &
else
    "$TARGET_SCRIPT" > "$APP_LOG" 2>&1 &
fi
APP_PID=$!

# Monitor application launch for stabilization
STABLE_WAIT=3
for i in $(seq 1 $((STABLE_WAIT * 2))); do
    sleep 0.5
    if ! kill -0 "$APP_PID" 2>/dev/null; then
        break
    fi
done

if ! kill -0 "$APP_PID" 2>/dev/null; then
    wait "$APP_PID" || APP_EXIT=$?
    echo "ERROR: Application crashed or exited prematurely (exit code: ${APP_EXIT:-unknown})." >&2
    echo "--- Application Output ---" >&2
    cat "$APP_LOG" >&2
    echo "--------------------------" >&2
    rm -rf "$TEST_TMP"
    exit 1
fi

echo "Application running stably after ${STABLE_WAIT}s. Capturing screenshot..."

# Capture XWD and convert to PNG
XWD_FILE="$TEST_TMP/shot.xwd"
xwd -root -silent -out "$XWD_FILE"
xwdtopnm "$XWD_FILE" 2>/dev/null | pnmtopng > "$SCREENSHOT_PATH"

if [ ! -s "$SCREENSHOT_PATH" ]; then
    echo "ERROR: Failed to capture valid screenshot to $SCREENSHOT_PATH." >&2
    kill -TERM "$APP_PID" 2>/dev/null || true
    rm -rf "$TEST_TMP"
    exit 1
fi
SCREENSHOT_SIZE=$(stat -c%s "$SCREENSHOT_PATH")
if [ "$SCREENSHOT_SIZE" -lt 1000 ]; then
    echo "ERROR: Screenshot file size too small ($SCREENSHOT_SIZE bytes); window unpainted." >&2
    kill -TERM "$APP_PID" 2>/dev/null || true
    rm -rf "$TEST_TMP"
    exit 1
fi
echo "Screenshot saved successfully to $SCREENSHOT_PATH ($SCREENSHOT_SIZE bytes)."

# Clean process termination
echo "Shutting down application (PID $APP_PID)..."
kill -TERM "$APP_PID" 2>/dev/null || true
for i in $(seq 1 25); do
    if ! kill -0 "$APP_PID" 2>/dev/null; then
        break
    fi
    sleep 0.2
done
if kill -0 "$APP_PID" 2>/dev/null; then
    kill -KILL "$APP_PID" 2>/dev/null || true
fi
wait "$APP_PID" 2>/dev/null || true

# Check log for fatal Adwaita or crash errors
if grep -q -E "Adwaita-ERROR|SIGABRT|gtk_window_set_titlebar" "$APP_LOG"; then
    echo "ERROR: Fatal errors detected in application log:" >&2
    cat "$APP_LOG" >&2
    rm -rf "$TEST_TMP"
    exit 1
fi

if [ "$KEEP_PROFILE" -eq 0 ]; then
    rm -rf "$TEST_TMP"
fi

echo "=== PASS: Xvfb launch smoke test succeeded! ==="
exit 0
