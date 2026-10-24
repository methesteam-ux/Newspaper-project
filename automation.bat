@echo off
REM ============================================================
REM  Automatic publishing ON/OFF  (default: everything OFF)
REM    automation.bat                 show status
REM    automation.bat local on|off    Windows Task Scheduler
REM    automation.bat cloud on|off    GitHub Actions schedule (asks before push)
REM  Schedule follows PUBLISH_DAYS / PUBLISH_HOUR in .env (default mon-fri 08:00)
REM ============================================================
setlocal
chcp 65001 > nul
cd /d "%~dp0"
set PYTHONUTF8=1
if not exist ".venv\Scripts\python.exe" (
    echo [!] .venv not found. See README.md "1." to install.
    exit /b 1
)
".venv\Scripts\python.exe" Source\automation.py %*
set RC=%ERRORLEVEL%
if "%~1"=="" pause
exit /b %RC%
