@echo off
setlocal

REM Robust launcher that keeps the window open when started via Explorer
set "SCRIPT_DIR=%~dp0"
powershell -NoExit -ExecutionPolicy Bypass -File "%SCRIPT_DIR%build_win_utf8.ps1"

endlocal
