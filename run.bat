@echo off
cd /d "%~dp0"
echo Starting Antigravity TTS Controller GUI...
pip install -r requirements.txt
python antigravity_tts.py
pause
