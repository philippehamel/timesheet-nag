#!/usr/bin/env python3

import argparse
import sys
import time
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlparse

import requests

TEMPO_BASE_URL = "https://api.tempo.io/4"
EXPECTED_HOURS = 40
CHECK_INTERVAL_SECONDS = 300
TOKEN_FILE = Path.home() / ".tempo_token"
COMPLETE_STATUSES = {"WAITING_FOR_APPROVAL", "APPROVED"}


def load_config() -> tuple[str, str]:
    if not TOKEN_FILE.exists():
        print(f"Error: {TOKEN_FILE} not found. Create it with:", file=sys.stderr)
        print(f"  echo 'YOUR_TOKEN' > {TOKEN_FILE}", file=sys.stderr)
        print(f"  echo 'YOUR_ACCOUNT_ID' >> {TOKEN_FILE}", file=sys.stderr)
        if sys.platform != "win32":
            print(f"  chmod 600 {TOKEN_FILE}", file=sys.stderr)
        sys.exit(1)
    lines = TOKEN_FILE.read_text().strip().splitlines()
    if len(lines) < 2:
        print(f"Error: {TOKEN_FILE} must have token on line 1 and account ID on line 2.", file=sys.stderr)
        sys.exit(1)
    token, account_id = lines[0].strip(), lines[1].strip()
    if not token or not account_id:
        print(f"Error: {TOKEN_FILE} contains empty token or account ID.", file=sys.stderr)
        sys.exit(1)
    return token, account_id


def get_last_week_range(today: date | None = None) -> tuple[str, str]:
    if today is None:
        today = date.today()
    last_monday = today - timedelta(days=today.weekday() + 7)
    last_sunday = last_monday + timedelta(days=6)
    return last_monday.isoformat(), last_sunday.isoformat()


def get_current_week_range(today: date | None = None) -> tuple[str, str]:
    if today is None:
        today = date.today()
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    return monday.isoformat(), sunday.isoformat()


def fetch_logged_hours(token: str, account_id: str, from_date: str, to_date: str) -> float:
    url = f"{TEMPO_BASE_URL}/worklogs"
    headers = {"Authorization": f"Bearer {token}"}
    params = {"from": from_date, "to": to_date, "authorAccountId": account_id}
    total_seconds = 0
    while url:
        resp = requests.get(url, headers=headers, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        for worklog in data.get("results", []):
            total_seconds += worklog.get("timeSpentSeconds", 0)
        next_url = data.get("metadata", {}).get("next", None)
        if next_url:
            parsed = urlparse(next_url)
            if parsed.scheme != "https" or parsed.hostname != "api.tempo.io":
                print(f"Warning: ignoring unexpected pagination URL: {next_url}", file=sys.stderr)
                next_url = None
        url = next_url
        params = {}
    return total_seconds / 3600


def fetch_approval_status(token: str, account_id: str, from_date: str, to_date: str) -> str:
    url = f"{TEMPO_BASE_URL}/timesheet-approvals/user/{account_id}"
    headers = {"Authorization": f"Bearer {token}"}
    params = {"from": from_date, "to": to_date}
    resp = requests.get(url, headers=headers, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data.get("status", {}).get("key", "UNKNOWN")


def is_timesheet_complete(hours: float, status: str) -> bool:
    return hours >= EXPECTED_HOURS and status in COMPLETE_STATUSES


def show_nag_popup(hours: float, status: str, from_date: str, to_date: str) -> None:
    status_label = {
        "OPEN": "OPEN (not submitted)",
        "WAITING_FOR_APPROVAL": "SUBMITTED (waiting for approval)",
        "APPROVED": "APPROVED",
    }.get(status, status)

    message = (
        f"Week: {from_date} to {to_date}\n"
        f"Logged: {hours:.1f} / {EXPECTED_HOURS:.1f} hours\n"
        f"Status: {status_label}\n\n"
        f"Go to Tempo and log your hours NOW.\n"
        f"This message will keep appearing every 5 minutes."
    )

    try:
        import tkinter

        BG = "#0000AA"
        FG = "#FFFFFF"
        YELLOW = "#FFFF55"
        FONT = ("Consolas", 14)
        FONT_TITLE = ("Consolas", 28, "bold")

        root = tkinter.Tk()
        root.overrideredirect(True)
        root.attributes("-topmost", True)
        root.configure(bg=FG)

        outer = tkinter.Frame(root, bg=BG, padx=2, pady=2)
        outer.pack(fill="both", expand=True, padx=2, pady=2)

        inner = tkinter.Frame(outer, bg=BG,
                              highlightthickness=1, highlightbackground=FG)
        inner.pack(fill="both", expand=True, padx=4, pady=4)

        tkinter.Label(
            inner, text=" FILL YOUR TIMESHEET! ",
            font=FONT_TITLE, fg=YELLOW, bg=BG,
        ).pack(pady=(16, 8))

        sep = tkinter.Frame(inner, height=1, bg=FG)
        sep.pack(fill="x", padx=12, pady=4)

        tkinter.Label(
            inner, text=message, font=FONT, fg=FG, bg=BG,
            justify="left", anchor="nw",
        ).pack(padx=20, pady=(8, 12), fill="both", expand=True)

        btn = tkinter.Button(
            inner, text="[ OK ]", font=FONT, fg=FG, bg=BG,
            activeforeground="#000000", activebackground=YELLOW,
            relief="flat", bd=0, padx=24, pady=4, command=root.destroy,
        )
        btn.pack(pady=(4, 16))
        btn.bind("<Enter>", lambda e: btn.configure(fg="#000000", bg=YELLOW))
        btn.bind("<Leave>", lambda e: btn.configure(fg=FG, bg=BG))
        btn.bind("<FocusIn>", lambda e: btn.configure(fg="#000000", bg=YELLOW))
        btn.bind("<FocusOut>", lambda e: btn.configure(fg=FG, bg=BG))

        root.update_idletasks()
        w, h = 700, 420
        try:
            import subprocess as _sp
            out = _sp.check_output(
                ["xrandr", "--query"], text=True, stderr=_sp.DEVNULL,
            )
            for line in out.splitlines():
                if " primary " in line:
                    res = line.split()[3]
                    pw, rest = res.split("x")
                    ph = rest.split("+")[0]
                    ox, oy = rest.split("+")[1], rest.split("+")[2]
                    x = int(ox) + (int(pw) - w) // 2
                    y = int(oy) + (int(ph) - h) // 2
                    break
            else:
                raise ValueError
        except Exception:
            x = (root.winfo_screenwidth() - w) // 2
            y = (root.winfo_screenheight() - h) // 2
        root.geometry(f"{w}x{h}+{x}+{y}")

        def _start_drag(e):
            root._drag_x = e.x
            root._drag_y = e.y

        def _do_drag(e):
            dx = e.x - root._drag_x
            dy = e.y - root._drag_y
            nx = root.winfo_x() + dx
            ny = root.winfo_y() + dy
            root.geometry(f"+{nx}+{ny}")

        outer.bind("<Button-1>", _start_drag)
        outer.bind("<B1-Motion>", _do_drag)
        inner.bind("<Button-1>", _start_drag)
        inner.bind("<B1-Motion>", _do_drag)

        root.mainloop()
        return
    except Exception:
        pass

    try:
        import subprocess

        result = subprocess.run(
            [
                "notify-send",
                "--urgency=critical",
                "--app-name=Timesheet Nag",
                "FILL YOUR TIMESHEET!",
                message,
            ],
            capture_output=True,
            timeout=5,
        )
        if result.returncode == 0:
            return
    except Exception:
        pass

    if sys.platform == "darwin":
        try:
            import subprocess

            escaped = message.replace("\\", "\\\\").replace('"', '\\"')
            result = subprocess.run(
                [
                    "osascript",
                    "-e",
                    f'display dialog "{escaped}" with title "FILL YOUR TIMESHEET!" with icon caution buttons {{"OK"}} default button "OK"',
                ],
                capture_output=True,
                timeout=60,
            )
            if result.returncode == 0:
                return
        except Exception:
            pass

    print("Warning: all notification methods failed, falling back to stderr", file=sys.stderr)
    print(message, file=sys.stderr)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check Tempo for last week's hours and nag until filled.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would happen without calling the API or opening files.",
    )
    parser.add_argument(
        "--week",
        choices=["last", "current"],
        default="last",
        help="Which week to check (default: last). Use 'current' for manual runs only.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    token, account_id = load_config()
    if args.week == "current":
        from_date, to_date = get_current_week_range()
    else:
        from_date, to_date = get_last_week_range()

    if args.dry_run:
        masked_id = account_id[:3] + "***" if len(account_id) > 3 else "***"
        print(f"[dry-run] Token file: {TOKEN_FILE} (found)")
        print(f"[dry-run] Account ID: {masked_id}")
        print(f"[dry-run] Week: {from_date} to {to_date}")
        show_nag_popup(0.0, "OPEN", from_date, to_date)
        return

    check = 0
    while True:
        check += 1
        try:
            hours = fetch_logged_hours(token, account_id, from_date, to_date)
            status = fetch_approval_status(token, account_id, from_date, to_date)
        except requests.HTTPError as e:
            if e.response is not None and 400 <= e.response.status_code < 500:
                print(f"Error: API returned {e.response.status_code} — check your token and account ID.", file=sys.stderr)
                sys.exit(1)
            print(f"Warning: API error (attempt {check}): {e}", file=sys.stderr)
            time.sleep(CHECK_INTERVAL_SECONDS)
            continue
        except (requests.RequestException, KeyError, ValueError) as e:
            print(f"Warning: API error (attempt {check}): {e}", file=sys.stderr)
            time.sleep(CHECK_INTERVAL_SECONDS)
            continue

        if is_timesheet_complete(hours, status):
            print(f"Timesheet complete: {hours:.1f}h, status={status}. Stopping.")
            return

        print(f"Check {check}: {hours:.1f}h, status={status}. Nagging...")
        show_nag_popup(hours, status, from_date, to_date)
        time.sleep(CHECK_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
