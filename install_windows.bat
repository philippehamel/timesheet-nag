@echo off
setlocal

set SCRIPT_DIR=%~dp0
set PYTHON_PATH=%SCRIPT_DIR%.venv\Scripts\python.exe

if not exist "%PYTHON_PATH%" (
    echo Error: .venv not found. Run: python -m venv .venv
    exit /b 1
)

schtasks /create /tn "TimesheetNag" /tr "\"%PYTHON_PATH%\" \"%SCRIPT_DIR%timesheet_nag.py\"" /sc weekly /d MON /st 09:00 /f

echo.
echo Installed. Task status:
schtasks /query /tn "TimesheetNag" /v /fo LIST
