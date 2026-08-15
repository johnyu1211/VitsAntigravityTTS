@echo off
title Antigravity Voice Studio (Desktop App)
cd /d "%~dp0"

echo ===================================================
echo   Antigravity Voice Studio - Electron Desktop App
echo ===================================================

:: Check if electron binary exists
if not exist "node_modules\electron\dist\electron.exe" (
    echo [INFO] Installing Electron desktop runtime (First run only)...
    call npm install
)

echo [INFO] Launching Desktop Application...
start "" "node_modules\electron\dist\electron.exe" .
exit /b 0
