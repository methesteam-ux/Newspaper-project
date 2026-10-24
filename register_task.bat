@echo off
REM ============================================================
REM  Register run_daily.bat in Windows Task Scheduler (daily 08:00)
REM  Right-click -> "Run as administrator" is recommended.
REM  Remove:  register_task.bat -Unregister
REM ============================================================
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0register_task.ps1" %*
pause
