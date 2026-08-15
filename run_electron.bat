@echo off
cd /d "%~dp0"

REM Check if electron binary exists
if not exist "%~dp0node_modules\electron\dist\electron.exe" (
    echo [INFO] Installing Electron desktop runtime...
    call npm install
)

REM Launch completely silent without keeping any CMD window open
start "" wscript.exe "%~dp0run_app.vbs"
exit
