# Timesheet Nag

Checks Tempo (Jira) for last week's logged hours and shows a popup dialog every 5 minutes until your timesheet is filled and submitted.

## Setup

1. Create a virtual environment and install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

On Ubuntu, install tkinter if not already present:

```bash
sudo apt install python3-tk
```

2. Create your config file with your Tempo API token and Jira account ID:

```bash
echo 'YOUR_TEMPO_TOKEN' > ~/.tempo_token
echo 'YOUR_ACCOUNT_ID' >> ~/.tempo_token
chmod 600 ~/.tempo_token   # Linux/macOS only
```

3. Test it works:

```bash
python timesheet_nag.py --dry-run
```

## Install as scheduled task

Each platform has its own installer that schedules the script to run every Monday at 9:00 AM.

### Linux (systemd)

```bash
./install.sh
systemctl --user status timesheet-nag.timer
```

### macOS (launchd)

```bash
./install_macos.sh
launchctl list | grep timesheet
```

### Windows (Task Scheduler)

```bat
install_windows.bat
schtasks /query /tn "TimesheetNag"
```

## Uninstall

### Linux

```bash
./uninstall.sh
```

### macOS

```bash
./uninstall_macos.sh
```

### Windows

```bat
uninstall_windows.bat
```

## Usage

```
python timesheet_nag.py                  # check last week (default)
python timesheet_nag.py --week current   # check current week
python timesheet_nag.py --dry-run        # preview without API calls
```

## Tests

```bash
python -m pytest test_timesheet_nag.py -v
```
