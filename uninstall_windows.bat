@echo off

schtasks /delete /tn "TimesheetNag" /f 2>nul
if %errorlevel% equ 0 (
    echo Uninstalled TimesheetNag scheduled task.
) else (
    echo Nothing to uninstall: TimesheetNag task not found.
)
