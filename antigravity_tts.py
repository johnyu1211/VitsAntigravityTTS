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

# Queue and playback control
speech_queue = asyncio.Queue()
current_task = None
skip_requested = False
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
    text = re.sub(r'```[\s\S]*?```', ' ', text)
    text = re.sub(r'`[^`]+`', ' ', text)
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    text = re.sub(r'\\\[[\s\S]*?\\\]', ' ', text)
    text = re.sub(r'\\\([^\)]*?\\\)', ' ', text)
    text = re.sub(r'\$\$[\s\S]*?\$\$', ' ', text)
    text = re.sub(r'\$[^\$]+?\$', ' ', text)
    text = re.sub(r'#+\s*', '', text)
    text = re.sub(r'[*_~>|]', ' ', text)
    text = re.sub(r'^\s*[-+*]\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def split_into_sentences(text):
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

def stop_playback():
    """Immediately stop audio and trigger skip."""
    global skip_requested
    skip_requested = True
    try:
        if pygame.mixer.music.get_busy():
            pygame.mixer.music.stop()
            pygame.mixer.music.unload()
    except Exception as e:
        print(f"[Stop Error] {e}")

def clear_all_queue():
    """Flush all queued speech tasks and stop audio immediately."""
    stop_playback()
    while not speech_queue.empty():
        try:
            speech_queue.get_nowait()
            speech_queue.task_done()
        except:
            break
    print("[Queue Cleared] All pending speech dropped.")

async def speech_worker():
    """Background worker processing speech queue item by item."""
    global skip_requested, last_spoken_text
    while True:
        item = await speech_queue.get()
        text = item.get("text", "")
        override_voice = item.get("voice")
        skip_requested = False

        if not current_settings.get("enabled", True) and not override_voice:
            speech_queue.task_done()
            continue

        clean = clean_markdown_text(text)
        if not clean or len(clean) < 2:
            speech_queue.task_done()
            continue

        last_spoken_text = clean
        rate = current_settings.get("rate", "+0%")
        pitch = current_settings.get("pitch", "+0Hz")
        base_voice = override_voice or current_settings.get("voice", "ko-KR-SunHiNeural")
        auto_lang = current_settings.get("auto_lang", True)

        sentences = split_into_sentences(clean)

        for sentence in sentences:
            if skip_requested:
                print("[Skipped] Moving past current sentence.")
                break

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

                if skip_requested:
                    break

                if os.path.exists(temp_audio) and os.path.getsize(temp_audio) > 0:
                    pygame.mixer.music.load(temp_audio)
                    pygame.mixer.music.play()
                    while pygame.mixer.music.get_busy():
                        if skip_requested:
                            pygame.mixer.music.stop()
                            break
                        await asyncio.sleep(0.06)
                    pygame.mixer.music.unload()
            except Exception as e:
                print(f"[Audio Error] {e}")
            finally:
                if os.path.exists(temp_audio):
                    try:
                        os.remove(temp_audio)
                    except:
                        pass

        speech_queue.task_done()

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
    test_phrase = "안티그래비티 실시간 음성 엔진입니다."
    await speech_queue.put({"text": test_phrase})
    return web.json_response({"status": "queued"})

async def handle_skip(request):
    stop_playback()
    return web.json_response({"status": "skipped"})

async def handle_clear(request):
    clear_all_queue()
    return web.json_response({"status": "cleared"})

async def handle_status(request):
    is_busy = False
    try:
        is_busy = pygame.mixer.music.get_busy()
    except:
        pass
    return web.json_response({
        "enabled": current_settings.get("enabled", True),
        "auto_lang": current_settings.get("auto_lang", True),
        "queue_size": speech_queue.qsize(),
        "is_playing": is_busy,
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
                    latest = get_latest_transcript_path()
                    if latest and latest != current_file:
                        print(f"\n[Session Switch] -> {latest}")
                        # New session: optionally clear old queue
                        clear_all_queue()
                        current_file = latest
                        break

                    line = f.readline()
                    if not line:
                        await asyncio.sleep(0.3)
                        continue

                    try:
                        data = json.loads(line)
                        # When user enters a new prompt, clear backlog
                        if data.get("type") == "USER_INPUT":
                            stop_playback()

                        # When AI responds, queue text
                        elif data.get("type") == "PLANNER_RESPONSE":
                            content = data.get("content", "")
                            if content and current_settings.get("enabled", True):
                                await speech_queue.put({"text": content})
                    except json.JSONDecodeError:
                        pass
        except Exception as e:
            print(f"[Log Error] {e}")
            await asyncio.sleep(1)

async def start_background_tasks(app):
    app['worker'] = asyncio.create_task(speech_worker())
    app['watcher'] = asyncio.create_task(background_log_watcher())

async def cleanup_background_tasks(app):
    app['worker'].cancel()
    app['watcher'].cancel()
    await app['worker']
    await app['watcher']

def main():
    app = web.Application()
    app.router.add_get('/', handle_index)
    app.router.add_get('/api/settings', handle_get_settings)
    app.router.add_post('/api/settings', handle_save_settings)
    app.router.add_post('/api/test_speak', handle_test_speak)
    app.router.add_post('/api/skip', handle_skip)
    app.router.add_post('/api/clear', handle_clear)
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
