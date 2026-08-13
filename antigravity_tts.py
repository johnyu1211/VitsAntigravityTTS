import os
import sys
import time
import json
import re
import glob
import asyncio
import webbrowser
from aiohttp import web
import edge_tts
import pygame

# Initialize audio mixer
pygame.mixer.init()

APP_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(APP_DIR, "config.json")
INDEX_HTML = os.path.join(APP_DIR, "index.html")
BRAIN_DIR = os.path.expanduser(r"~\.gemini\antigravity\brain")

# Default Global State
current_settings = {
    "voice": "ko-KR-SunHiNeural",
    "rate": "+0%",
    "pitch": "+0Hz",
    "volume": "+0%",
    "enabled": True,
    "auto_lang": True,
    "skip_code": True
}
last_spoken_text = ""

def load_config():
    global current_settings
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                current_settings.update(json.load(f))
        except:
            pass

def save_config():
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(current_settings, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[ERROR] Config save failed: {e}")

load_config()

def detect_language(text):
    """Detect dominant language of a given text segment."""
    hangul_count = len(re.findall(r'[\uac00-\ud7a3\u1100-\u11ff]', text))
    japanese_count = len(re.findall(r'[\u3040-\u30ff]', text))
    latin_count = len(re.findall(r'[a-zA-Z]', text))

    if hangul_count > 0:
        return "ko"
    if japanese_count > 0:
        return "ja"
    if latin_count > 0:
        return "en"
    return "ko"

def get_voice_for_lang(lang, base_voice):
    """Map language to appropriate high-quality neural voice."""
    is_male = any(m in base_voice for m in ["InJoon", "Hyunsu", "Guy", "Keita", "Yunxi"])
    
    if lang == "en":
        return "en-US-GuyNeural" if is_male else "en-US-JennyNeural"
    elif lang == "ja":
        return "ja-JP-KeitaNeural" if is_male else "ja-JP-NanamiNeural"
    elif lang == "ko":
        return base_voice if base_voice.startswith("ko-KR") else ("ko-KR-InJoonNeural" if is_male else "ko-KR-SunHiNeural")
    return base_voice

def clean_markdown_text(text):
    if not text:
        return ""
    # Strip markdown code blocks
    text = re.sub(r'```[\s\S]*?```', ' ', text)
    # Strip inline code
    text = re.sub(r'`[^`]+`', ' ', text)
    # Strip links [text](url) -> text
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    # Strip LaTeX math formulas
    text = re.sub(r'\\\[[\s\S]*?\\\]', ' ', text)
    text = re.sub(r'\\\([^\)]*?\\\)', ' ', text)
    text = re.sub(r'\$\$[\s\S]*?\$\$', ' ', text)
    text = re.sub(r'\$[^\$]+?\$', ' ', text)
    # Strip headers & special markdown syntax
    text = re.sub(r'#+\s*', '', text)
    text = re.sub(r'[*_~>|]', ' ', text)
    text = re.sub(r'^\s*[-+*]\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def split_into_sentences(text):
    """Split text into sentences or language segments."""
    # Split by newlines and common punctuation
    raw_chunks = re.split(r'(\n+|[\.\?\!]+\s+)', text)
    sentences = []
    buf = ""
    for c in raw_chunks:
        if not c:
            continue
        buf += c
        if re.search(r'[\.\?\!\n]', c):
            cleaned = buf.strip()
            if len(cleaned) > 1:
                sentences.append(cleaned)
            buf = ""
    if buf.strip():
        sentences.append(buf.strip())
    return sentences if sentences else [text]

async def speak_text(text, override_voice=None, override_rate=None, override_pitch=None):
    global last_spoken_text
    if not current_settings.get("enabled", True) and not override_voice:
        return

    clean = clean_markdown_text(text)
    if not clean or len(clean) < 2:
        return

    last_spoken_text = clean
    rate = override_rate or current_settings.get("rate", "+0%")
    pitch = override_pitch or current_settings.get("pitch", "+0Hz")
    base_voice = override_voice or current_settings.get("voice", "ko-KR-SunHiNeural")
    auto_lang = current_settings.get("auto_lang", True)

    sentences = split_into_sentences(clean)

    for sentence in sentences:
        if not sentence or len(sentence.strip()) < 2:
            continue

        if auto_lang and not override_voice:
            lang = detect_language(sentence)
            voice = get_voice_for_lang(lang, base_voice)
        else:
            voice = base_voice

        print(f"[TTS Playing] [{voice}] {sentence[:45]}...")
        temp_audio = os.path.join(APP_DIR, f"tts_{int(time.time()*1000)}.mp3")

        try:
            communicate = edge_tts.Communicate(sentence, voice=voice, rate=rate, pitch=pitch)
            await communicate.save(temp_audio)

            if os.path.exists(temp_audio) and os.path.getsize(temp_audio) > 0:
                pygame.mixer.music.load(temp_audio)
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy():
                    await asyncio.sleep(0.08)
                pygame.mixer.music.unload()
        except Exception as e:
            print(f"[TTS Audio Error] {e}")
        finally:
            if os.path.exists(temp_audio):
                try:
                    os.remove(temp_audio)
                except:
                    pass

# Web Handlers
async def handle_index(request):
    return web.FileResponse(INDEX_HTML)

async def handle_get_settings(request):
    return web.json_response(current_settings)

async def handle_save_settings(request):
    global current_settings
    data = await request.json()
    current_settings.update(data)
    save_config()
    return web.json_response({"status": "ok", "settings": current_settings})

async def handle_test_speak(request):
    test_phrase = "안티그래비티 음성 설정 완료. Automatic language routing is active!"
    asyncio.create_task(speak_text(test_phrase))
    return web.json_response({"status": "speaking"})

async def handle_status(request):
    return web.json_response({
        "enabled": current_settings.get("enabled", True),
        "auto_lang": current_settings.get("auto_lang", True),
        "last_spoken": last_spoken_text
    })

def get_latest_transcript_path():
    pattern = os.path.join(BRAIN_DIR, "*", ".system_generated", "logs", "transcript.jsonl")
    files = glob.glob(pattern)
    if not files:
        return None
    return max(files, key=os.path.getmtime)

async def background_log_watcher():
    print("[Watcher] Tracking active transcript.jsonl...")
    current_file = get_latest_transcript_path()
    
    while True:
        if not current_file or not os.path.exists(current_file):
            current_file = get_latest_transcript_path()
            await asyncio.sleep(1)
            continue

        try:
            with open(current_file, 'r', encoding='utf-8', errors='ignore') as f:
                f.seek(0, os.SEEK_END)
                while True:
                    # Check if session switched
                    latest = get_latest_transcript_path()
                    if latest and latest != current_file:
                        print(f"\n[Session Switch] -> {latest}")
                        current_file = latest
                        break

                    line = f.readline()
                    if not line:
                        await asyncio.sleep(0.3)
                        continue

                    try:
                        data = json.loads(line)
                        if data.get("type") == "PLANNER_RESPONSE":
                            content = data.get("content", "")
                            if content and current_settings.get("enabled", True):
                                await speak_text(content)
                    except json.JSONDecodeError:
                        pass
        except Exception as e:
            print(f"[Log Error] {e}")
            await asyncio.sleep(1)

async def start_background_tasks(app):
    app['watcher'] = asyncio.create_task(background_log_watcher())

async def cleanup_background_tasks(app):
    app['watcher'].cancel()
    await app['watcher']

def main():
    app = web.Application()
    app.router.add_get('/', handle_index)
    app.router.add_get('/api/settings', handle_get_settings)
    app.router.add_post('/api/settings', handle_save_settings)
    app.router.add_post('/api/test_speak', handle_test_speak)
    app.router.add_get('/api/status', handle_status)
    
    app.on_startup.append(start_background_tasks)
    app.on_cleanup.append(cleanup_background_tasks)

    port = 7860
    print("=" * 60)
    print(f"Antigravity Voice Engine GUI: http://localhost:{port}")
    print("=" * 60)
    
    webbrowser.open(f"http://localhost:{port}")
    web.run_app(app, host='127.0.0.1', port=port)

if __name__ == "__main__":
    main()
