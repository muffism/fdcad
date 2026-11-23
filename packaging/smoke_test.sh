#!/usr/bin/env bash
# Start the packaged app on the Qt offscreen platform and check it is still running after a few seconds.
# This catches missing libraries and bundling errors. CI has no GPU, so the viewport itself is checked by hand.
# Then run the app's bundle check (FDCAD_BUNDLE_CHECK): icons, Qt SVG support, theme images and samples.
# Usage: bash packaging/smoke_test.sh PATH_TO_EXECUTABLE
# The app is stopped with kill -9 (D2659): on Windows, Git Bash's plain kill starts a
# thread in the app that calls ExitProcess, and Qt's shut down on that thread can end
# in an access violation that crash.log records. kill -9 ends the process at once.
set -euo pipefail

if [ $# -ne 1 ]; then
  echo "usage: smoke_test.sh PATH_TO_EXECUTABLE" >&2
  exit 2
fi

LOG="$(mktemp)"
QT_QPA_PLATFORM=offscreen "$1" > "$LOG" 2>&1 &
PID=$!
sleep 8
if kill -0 "$PID" 2>/dev/null; then
  kill -9 "$PID" 2>/dev/null || true
  echo "smoke test passed: app still running after 8 s"
else
  wait "$PID" || true
  echo "smoke test failed: app exited early. Output:" >&2
  cat "$LOG" >&2
  exit 1
fi

# Bundle check: the app writes what is missing to a file and quits.
REPORT="$(mktemp)"
rm -f "$REPORT"
FDCAD_BUNDLE_CHECK="$REPORT" QT_QPA_PLATFORM=offscreen "$1" > "$LOG" 2>&1 &
PID=$!
for _ in $(seq 1 60); do
  if ! kill -0 "$PID" 2>/dev/null; then break; fi
  sleep 1
done
if kill -0 "$PID" 2>/dev/null; then
  kill -9 "$PID" 2>/dev/null || true
  echo "bundle check failed: the app did not finish within 60 s. Output:" >&2
  cat "$LOG" >&2
  exit 1
fi
wait "$PID" || true
if [ ! -s "$REPORT" ]; then
  echo "bundle check failed: no report written. Output:" >&2
  cat "$LOG" >&2
  exit 1
fi
if ! grep -q '"problems": \[\]' "$REPORT"; then
  echo "bundle check failed:" >&2
  cat "$REPORT" >&2
  exit 1
fi
echo "bundle check passed: icons, SVG support, theme images and samples are in the build"
