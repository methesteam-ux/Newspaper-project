@echo off
REM ============================================================
REM  Register local automatic publishing (Windows Task Scheduler)
REM  Same as: automation.bat local on      (remove: automation.bat local off)
REM  Days/time follow PUBLISH_DAYS / PUBLISH_HOUR in .env (default mon-fri 08:00)
REM ============================================================
cd /d "%~dp0"
if /i "%~1"=="-Unregister" (
    call "%~dp0automation.bat" local off
) else (
    call "%~dp0automation.bat" local on
)
pause
