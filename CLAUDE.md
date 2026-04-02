# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Timesheet Nag is a cross-platform tool that monitors Jira Tempo timesheets and shows persistent popup notifications every 5 minutes until the user logs >= 40 hours and submits their timesheet. It runs weekly (Monday 9:00 AM) via platform-specific schedulers (systemd on Linux, launchd on macOS, Task Scheduler on Windows).

## Commands

```bash
# Setup
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run tests
python -m pytest test_timesheet_nag.py -v

# Run a single test
python -m pytest test_timesheet_nag.py::TestClassName::test_name -v

# Manual run
python timesheet_nag.py --dry-run              # Preview without API calls
python timesheet_nag.py --week current         # Check current week
```

## Architecture

Single-file application (`timesheet_nag.py`) with a test file (`test_timesheet_nag.py`).

**Core flow:** `main()` runs an infinite loop that calls `fetch_logged_hours()` and `fetch_approval_status()` against the Tempo REST API (`/4/worklogs` and `/4/timesheet-approvals`), checks completion via `is_timesheet_complete()`, and shows `show_nag_popup()` if incomplete. Rechecks every 300 seconds.

**Notification fallback chain:** Tkinter GUI → `notify-send` (Linux) → `osascript` (macOS) → stderr.

**Security:** Pagination URLs are validated (HTTPS + hostname check) to prevent SSRF. Config lives in `~/.tempo_token` (token + account ID).

**Error handling:** Transient/network errors retry with backoff; 4xx auth errors exit immediately.

## Testing

Tests use pytest with `unittest.mock`. Heavy use of `@patch` decorators and `MagicMock` for API responses, Tkinter, and platform-specific notification tools. The `tmp_path` fixture is used for config file tests.
