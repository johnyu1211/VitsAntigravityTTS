# Antigravity Voice Engine (AntigravityTTS Simple)

Real-time Text-to-Speech (TTS) background reader and web controller for Google Antigravity. Automatically reads Antigravity AI responses aloud as they are generated, with multi-language detection, markdown cleaning, and a local web GUI.

---

## Key Features

- **Real-Time Log Tracking**: Automatically detects and monitors active Antigravity session logs (`transcript.jsonl`) under `~/.gemini/antigravity/brain/`.
- **Intelligent Text Sanitization**: Automatically strips code blocks, markdown symbols, inline code, and LaTeX math formulas before synthesis.
- **Multilingual Auto-Routing**: Dynamically detects Korean, English, and Japanese sentences and selects matching native neural voices seamlessly.
- **Studio Web GUI**: Modern, lightweight local web controller (inspired by Poorman's Gravity design system) to adjust voice, rate, pitch, and power toggles.
- **Cross-Environment Compatibility**: Works with Antigravity IDE, CLI, and web interface without manual configuration.

---

## Architecture

```text
[ Antigravity IDE / CLI ]
           |
           v
[ ~/.gemini/antigravity/brain/<session>/transcript.jsonl ]
           | (Real-time tailing)
           v
[ Text Cleaner & Language Detector ]
           | (Multi-language sentence routing)
           v
[ Edge-TTS Neural Audio Engine ]
           |
           v
[ Speaker Output & Web GUI Controller ]
```

---

## Installation & Quick Start

### Prerequisites
- Python 3.10 or higher
- Windows / macOS / Linux

### 1. Clone Repository
```bash
git clone https://github.com/johnyu1211/AntigravityTTS_simple.git
cd AntigravityTTS_simple
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Run
On Windows:
```bash
run.bat
```
Or run directly via Python:
```bash
python antigravity_tts.py
```

The Web GUI will automatically open at `http://localhost:7860`.

---

## Web GUI Parameters

- **Voice Profiles**:
  - `SunHi` (Korean Female)
  - `InJoon` (Korean Male - Newsreader)
  - `Hyunsu` (Korean Male - Conversational)
  - `Jenny` / `Guy` (English)
  - `Nanami` / `Keita` (Japanese)
- **Auto Language Routing**: Automatically routes Korean, English, and Japanese sentences to their native voices.
- **Rate & Pitch Sliders**: Adjust speech speed (-40% to +80%) and voice pitch (-30Hz to +30Hz).
- **Mute / Power Switch**: Toggle TTS playback instantly.

---

## Project Structure

```text
AntigravityTTS_simple/
|-- antigravity_tts.py   # Core backend server, log watcher, and TTS player
|-- index.html           # Modern Studio Web Controller GUI
|-- requirements.txt     # Python dependencies (edge-tts, pygame, aiohttp)
|-- run.bat              # One-click Windows startup batch script
|-- .gitignore           # Ignored config, cache, and audio files
|-- LICENSE              # MIT License
`-- README.md            # Documentation
```

---

## License

Distributed under the MIT License. See [LICENSE](LICENSE) for more information.
