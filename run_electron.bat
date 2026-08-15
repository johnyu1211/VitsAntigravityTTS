@echo off
title Antigravity Voice Studio (Desktop App)
cd /d "%~dp0"

echo ===================================================
echo   Antigravity Voice Studio - Electron Desktop App
echo ===================================================

:: Check node_modules
if not exist "node_modules\electron" (
    echo [INFO] Installing Electron dependencies (First run only)...
    call npm install
)

echo [INFO] Launching Desktop App...
call npx electron .
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Electron exited with error code %ERRORLEVEL%
    pause
)
