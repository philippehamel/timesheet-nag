#!/usr/bin/env bash
set -euo pipefail

PLIST_NAME="com.timesheet-nag.plist"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
PLIST_PATH="$LAUNCH_AGENTS_DIR/$PLIST_NAME"

if [ -f "$PLIST_PATH" ]; then
    launchctl bootout "gui/$(id -u)/com.timesheet-nag" 2>/dev/null || true
    rm -f "$PLIST_PATH"
    echo "Uninstalled timesheet-nag launch agent."
else
    echo "Nothing to uninstall: $PLIST_PATH not found."
fi
