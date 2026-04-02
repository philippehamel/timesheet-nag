#!/usr/bin/env bash
set -euo pipefail

command -v systemctl >/dev/null 2>&1 || { echo "Error: systemd not found." >&2; exit 1; }

USER_SYSTEMD_DIR="$HOME/.config/systemd/user"

systemctl --user disable --now timesheet-nag.timer 2>/dev/null || true
systemctl --user stop timesheet-nag.service 2>/dev/null || true

rm -f "$USER_SYSTEMD_DIR/timesheet-nag.service"
rm -f "$USER_SYSTEMD_DIR/timesheet-nag.timer"

systemctl --user daemon-reload

echo "Uninstalled timesheet-nag timer and service."
