#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLIST_NAME="com.timesheet-nag.plist"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
PYTHON_PATH="${SCRIPT_DIR}/.venv/bin/python3"

if [ ! -f "$PYTHON_PATH" ]; then
    echo "Error: .venv not found. Run: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
    exit 1
fi

mkdir -p "$LAUNCH_AGENTS_DIR"

sed -e "s|__SCRIPT_DIR__|${SCRIPT_DIR}|g" \
    -e "s|__PYTHON_PATH__|${PYTHON_PATH}|g" \
    -e "s|__HOME__|${HOME}|g" \
    "$SCRIPT_DIR/$PLIST_NAME" > "$LAUNCH_AGENTS_DIR/$PLIST_NAME"

launchctl unload "$LAUNCH_AGENTS_DIR/$PLIST_NAME" 2>/dev/null || true
launchctl load "$LAUNCH_AGENTS_DIR/$PLIST_NAME"

echo ""
echo "Installed. Verify with:"
echo "  launchctl list | grep timesheet"
