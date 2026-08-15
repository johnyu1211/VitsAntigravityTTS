@echo off
title Antigravity Voice Studio (Desktop App)
cd /d "%~dp0"

echo ===================================================
echo   Antigravity Voice Studio - Electron Desktop App
echo ===================================================

:: Check node_modules
if not exist "node_modules" (
    echo [INFO] Installing Electron dependencies (First run only)...
    call npm install
)

echo [INFO] Launching Desktop App...
call npm start
