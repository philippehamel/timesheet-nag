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

if ! python3 -c "import tkinter" 2>/dev/null; then
    PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    if command -v brew >/dev/null 2>&1; then
        echo "tkinter not found. Installing python-tk@${PYTHON_VERSION}..."
        brew install "python-tk@${PYTHON_VERSION}"
    else
        echo "Warning: tkinter not found. Install it for popup notifications:"
        echo "  brew install python-tk@${PYTHON_VERSION}"
    fi
fi

mkdir -p "$LAUNCH_AGENTS_DIR"

sed -e "s|__SCRIPT_DIR__|${SCRIPT_DIR}|g" \
    -e "s|__PYTHON_PATH__|${PYTHON_PATH}|g" \
    -e "s|__HOME__|${HOME}|g" \
    "$SCRIPT_DIR/$PLIST_NAME" > "$LAUNCH_AGENTS_DIR/$PLIST_NAME"

launchctl bootout "gui/$(id -u)/com.timesheet-nag" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$LAUNCH_AGENTS_DIR/$PLIST_NAME"

echo ""
echo "Installed. Verify with:"
echo "  launchctl list | grep timesheet"
