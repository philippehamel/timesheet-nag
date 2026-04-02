# Timesheet Nag

Checks Tempo (Jira) for last week's logged hours and opens an annoying reminder every 5 minutes until your timesheet is filled and submitted.

## Setup

1. Create a virtual environment and install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Create your config file with your Tempo API token and Jira account ID:

```bash
echo 'YOUR_TEMPO_TOKEN' > ~/.tempo_token
echo 'YOUR_ACCOUNT_ID' >> ~/.tempo_token
chmod 600 ~/.tempo_token
```

3. Test it works:

```bash
python timesheet_nag.py --dry-run
```

## Install as systemd timer

This sets up a user timer that runs every Monday at 9:00 AM:

```bash
./install.sh
```

Check timer status:

```bash
systemctl --user status timesheet-nag.timer
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
