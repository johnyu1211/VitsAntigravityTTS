# Antigravity GPT-SoVITS Character Voice Studio

Real-time zero-shot AI voice cloning and Text-to-Speech (TTS) background reader for Google Antigravity. Automatically reads Antigravity AI responses aloud in any custom character voice using **GPT-SoVITS V2** neural voice synthesis.

---

## Key Features

- **Zero-Shot Character Voice Cloning**: Clone any character's voice from a short 3~10 second audio clip (`.wav`) in `reference_voices/`.
- **Native Trilingual Support**: 100% natural pronunciation and expressive intonation for **Korean, English, and Japanese**.
- **GPU In-Memory Acceleration**: Real-time CUDA inference with persistent model caching and low-latency audio streaming.
- **Real-Time Log Tracking**: Automatically detects and reads active Antigravity session logs (`transcript.jsonl`) under `~/.gemini/antigravity/brain/`.
- **Intelligent Text Sanitization**: Automatically strips code blocks, markdown tables, URLs, and LaTeX math formulas before synthesis.
- **Instant Interrupt Handling**: Instantly stops speech when a new user message is submitted.
- **Studio Web Controller**: Clean, dark-themed local GUI (`http://localhost:7861`) to switch character voice samples, adjust pitch, speed, and audio toggles.

---

## Architecture

```text
[ Antigravity IDE / CLI ]
           |
           v
[ ~/.gemini/antigravity/brain/<session>/transcript.jsonl ]
           | (Real-time Non-blocking Tailing)
           v
[ Text Cleaner & Language Detector ]
           | (Korean / English / Japanese)
           v
[ GPT-SoVITS V2 Neural Audio Synthesizer ]
           | (Zero-shot reference voice cloning)
           v
[ Speaker Output & Studio Web GUI (Port 7861) ]
```

---

## Quick Start Guide

### 1. Prerequisites
- Windows 10/11 (or Linux)
- Python 3.10 or 3.11
- NVIDIA GPU with CUDA support (4GB+ VRAM recommended)

### 2. Clone Repository
```bash
git clone https://github.com/johnyu1211/RCV-AntigravityTTS.git
cd RCV-AntigravityTTS
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Add Character Voice Samples
Place any 3~10 second character voice clips (`.wav`) into the `reference_voices/` folder:
```text
reference_voices/
  ├── my_character.wav
  └── anime_heroine.wav
```

### 5. Run
On Windows:
```bash
run.bat
```
The Studio Web GUI will open automatically at `http://localhost:7861`.

---

## Legal & License

- **Engine Code**: Licensed under the **MIT License**.
- **Core Architecture**: Powered by [GPT-SoVITS](https://github.com/RVC-Boss/GPT-SoVITS) (MIT License).
- **User Responsibility**: Model weights and audio samples in `reference_voices/` are managed locally by the user and are strictly excluded from the repository.
