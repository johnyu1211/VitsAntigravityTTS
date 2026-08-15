@echo off
title Antigravity Voice Studio (Desktop App)
cd /d "%~dp0"

echo ===================================================
echo   Antigravity Voice Studio - Electron Desktop App
echo ===================================================

REM Check if electron binary exists
if not exist "%~dp0node_modules\electron\dist\electron.exe" (
    echo [INFO] Installing Electron desktop runtime...
    call npm install
)

echo [INFO] Launching Desktop Application...
start "" "%~dp0node_modules\electron\dist\electron.exe" "%~dp0."
exit /b 0
