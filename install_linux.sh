#!/usr/bin/env bash
set -euo pipefail

command -v systemctl >/dev/null 2>&1 || { echo "Error: systemd not found. This script requires systemd." >&2; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

if ! python3 -c "import tkinter" 2>/dev/null; then
    if command -v apt >/dev/null 2>&1; then
        echo "tkinter not found. Installing python3-tk..."
        sudo apt install python3-tk
    else
        echo "Warning: tkinter not found. Install it manually for popup notifications."
    fi
fi

USER_SYSTEMD_DIR="$HOME/.config/systemd/user"

mkdir -p "$USER_SYSTEMD_DIR"

# Template the service file with the actual script directory
sed "s|__SCRIPT_DIR__|${SCRIPT_DIR}|g" "$SCRIPT_DIR/timesheet-nag.service" > "$USER_SYSTEMD_DIR/timesheet-nag.service"
cp "$SCRIPT_DIR/timesheet-nag.timer" "$USER_SYSTEMD_DIR/"

systemctl --user daemon-reload
systemctl --user enable --now timesheet-nag.timer

echo ""
echo "Installed. Timer status:"
systemctl --user status timesheet-nag.timer --no-pager
