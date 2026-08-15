# Antigravity Voice Studio (GPT-SoVITS Desktop)

A professional, real-time AI neural voice suite and standalone desktop application powered by **GPT-SoVITS V2**.

---

## Key Features

1. **Standalone Desktop Application (Clean GUI, No Console Window)**
   - Launch silently via `run_app.vbs` without command prompt windows.
   - Clean IPC lifecycle management ensures 100% background process cleanup upon window exit.
2. **Universal Dual-Slot Language Routing (English Primary & Second Language Secondary)**
   - Automatically routes spoken English text to **Slot 1 (English Voice)**.
   - Automatically routes all other languages (Korean, Japanese, Chinese, etc.) to **Slot 2 (Second Language Voice)**.
3. **Visual Waveform Sample Editor (Video & Audio Trimmer)**
   - Load video files (`MP4`, `MKV`, `MOV`, `WebM`) or audio tracks (`MP3`, `FLAC`, `WAV`, `M4A`) with an interactive canvas waveform viewer.
   - Fine-tune clip boundaries and extract 32kHz reference samples with a single click.
4. **Voice Library & Avatar Thumbnails**
   - Manage reference audio files and companion transcript scripts.
   - Attach character avatar thumbnails directly via clipboard image paste (`Ctrl+V`) or web URLs.
5. **Studio Analog Saturation Volume Booster (Up to 200%)**
   - Non-linear soft-saturation limiter enhances voice clarity and punch without digital clipping distortion.
6. **Robust Text Normalizer & Cleaner**
   - Filters markdown, URLs, code blocks, and unwanted breath artifacts while preserving natural prosody and decimals.

---

## How to Run

- **[run_app.vbs](run_app.vbs)**: Double-click to launch the application silently in desktop mode.

---

## Tab Overview

- **`Voice Studio`**: Live transcript feed, primary English and secondary multilingual voice slots, speed, volume, and temperature tuning.
- **`Video & Audio Trimmer`**: Interactive audio waveform trimmer with 32kHz high-fidelity extraction.
- **`Voice Library`**: Reference voice manager with companion scripts and 90px character avatars.
- **`System Logs`**: Live terminal log stream with auto-scroll and one-click log export.
