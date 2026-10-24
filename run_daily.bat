@echo off
REM ============================================================
REM  My Daily Newspaper - publish today's edition once
REM  Usage: run_daily.bat [--date YYYY-MM-DD] [--demo] [--no-llm]
REM  Log  : Output\daily_run.log
REM ============================================================
setlocal
chcp 65001 > nul
cd /d "%~dp0"
set PYTHONUTF8=1

if not exist ".venv\Scripts\python.exe" (
    echo [!] .venv not found. Run first:
    echo     python -m venv .venv
    echo     .venv\Scripts\python.exe -m pip install -r requirements.txt
    echo     .venv\Scripts\python.exe -m playwright install chromium
    exit /b 1
)

".venv\Scripts\python.exe" Source\main.py %*
set RC=%ERRORLEVEL%
if %RC% neq 0 echo [!] Publish failed (exit code %RC%). See Output\daily_run.log
exit /b %RC%
