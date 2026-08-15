import os
import sys
import time
import json
import re
import glob
import asyncio
import webbrowser
import shutil
import warnings
import base64
import io
import urllib.request

# Protect against WinError 6 / invalid stdout handles when spawned by Electron/GUI
try:
    if sys.stdout is None or not hasattr(sys.stdout, 'write'):
        sys.stdout = open(os.devnull, 'w', encoding='utf-8')
    if sys.stderr is None or not hasattr(sys.stderr, 'write'):
        sys.stderr = open(os.devnull, 'w', encoding='utf-8')
except:
    pass

# Clean startup logs
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
warnings.filterwarnings("ignore")

import soundfile as sf
import librosa
import pygame
from aiohttp import web
from PIL import Image
from gpt_sovits_engine import gpt_sovits_engine

# Initialize audio mixer for 32000Hz GPT-SoVITS audio
pygame.mixer.init(frequency=32000, size=-16, channels=1, buffer=1024)

APP_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(APP_DIR, "config.json")
VIEWS_DIR = os.path.join(APP_DIR, "views")
INDEX_HTML = os.path.join(VIEWS_DIR, "index.html")
TEMP_DIR = os.path.join(APP_DIR, "temp_audio")
REF_DIR = os.path.join(APP_DIR, "reference_voices")
BRAIN_DIR = os.path.expanduser(r"~\.gemini\antigravity\brain")

os.makedirs(REF_DIR, exist_ok=True)

def cleanup_temp_dir():
    if os.path.exists(TEMP_DIR):
        try:
            shutil.rmtree(TEMP_DIR, ignore_errors=True)
        except:
            pass
    os.makedirs(TEMP_DIR, exist_ok=True)

cleanup_temp_dir()

current_settings = {
    "voice_en": "voiceSCOURCE.wav",
    "prompt_en": "",
    "voice_ko": "voiceSCOURCE.wav",
    "prompt_ko": "",
    "voice_default": "voiceSCOURCE.wav",
    "prompt_default": "",
    "temperature": 0.65,
    "volume": 1.0,
    "speed": 1.0,
    "enabled": True,
    "skip_code": True
}

speech_queue = asyncio.Queue()
audio_play_queue = asyncio.Queue()
current_generation_id = 0
last_spoken_text = ""

def load_config():
    global current_settings
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                saved = json.load(f)
                current_settings.update(saved)
                # Backward compatibility migration
                if "reference_voice" in saved:
                    if "voice_en" not in saved: current_settings["voice_en"] = saved["reference_voice"]
                    if "voice_ko" not in saved: current_settings["voice_ko"] = saved["reference_voice"]
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

def clean_markdown_text(text):
    if not text:
        return ""
    
    # 1. Remove code blocks completely
    text = re.sub(r'```[\s\S]*?```', ' ', text)
    text = re.sub(r'`[^`]+`', ' ', text)

    # 2. Markdown links: [Link Title](http://...) -> Link Title
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    
    # 3. Strip all URLs (http, https, ftp, file, www)
    text = re.sub(r'(?:https?|ftp|file)://\S+', ' ', text)
    text = re.sub(r'www\.\S+', ' ', text)
    
    # 4. Strip file paths (e.g. C:\path\to\file or /usr/local/...)
    text = re.sub(r'[A-Za-z]:\\[\w\\\.-]+', ' ', text)
    text = re.sub(r'/(?:[\w\.-]+/)+[\w\.-]+', ' ', text)

    # 5. HTML tags & Markdown elements & Tables
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'\|[^\n]+\|', ' ', text)
    text = re.sub(r'[-:|]{3,}', ' ', text)
    text = re.sub(r'\\\[[\s\S]*?\\\]', ' ', text)
    text = re.sub(r'\\\([^\)]*?\\\)', ' ', text)
    text = re.sub(r'\$\$[\s\S]*?\$\$', ' ', text)
    text = re.sub(r'\$[^\$]+?\$', ' ', text)
    text = re.sub(r'#+\s*', '', text)
    text = re.sub(r'^\s*[-+*•·]\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*>\s*', '', text, flags=re.MULTILINE)
    
    # 6. Comprehensive Special Character Purge
    # Protect decimal points (e.g. 3.14, 2.0)
    text = re.sub(r'(\d+)\.(\d+)', r'\1_DECIMAL_DOT_\2', text)
    
    text = re.sub(r'[^\w\s\uac00-\ud7a3\u1100-\u11ff\u3040-\u30ff\u4e00-\u9fff\.\!\?]', ' ', text)
    text = re.sub(r'[_]', ' ', text)
    
    # 7. Normalize multiple punctuations & replace breathless commas with clean space
    text = re.sub(r'[\.!\?]{2,}', '.', text)
    text = re.sub(r'\s*,\s*', ' ', text)
    text = re.sub(r'\s*([\.!\?])\s*', r'\1 ', text)
    
    # Restore decimal points
    text = text.replace(' DECIMAL DOT ', '.').replace('DECIMAL DOT', '.').replace('DECIMALDOT', '.')
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def split_into_conversational_chunks(text):
    if not text:
        return []
    normalized = re.sub(r'\s*\n+\s*', ' ', text).strip()
    marked = re.sub(r'(\s+)(?=\d+[\.\)]\s+)', r' <CHUNK_SPLIT> ', normalized)
    marked = re.sub(r'(?<=[^\d][\.\!\?])\s+', r' <CHUNK_SPLIT> ', marked)
    raw_chunks = marked.split('<CHUNK_SPLIT>')
    chunks = [c.strip() for c in raw_chunks if c.strip()]
    return chunks if chunks else [normalized]

def stop_and_clear_everything():
    global current_generation_id
    current_generation_id += 1
    try:
        if pygame.mixer.music.get_busy():
            pygame.mixer.music.stop()
        pygame.mixer.music.unload()
    except:
        pass
    for q in [speech_queue, audio_play_queue]:
        while not q.empty():
            try:
                q.get_nowait()
                q.task_done()
            except:
                break

import numpy as np

def apply_studio_volume_boost(wav_path, volume_multiplier):
    """Applies studio-grade dynamic analog saturation and soft-knee limiting for clean loudness boost without clipping."""
    if volume_multiplier <= 1.0 or not os.path.exists(wav_path):
        return wav_path
    try:
        data, sr = sf.read(wav_path)
        gain = 1.0 + (volume_multiplier - 1.0) * 1.3
        boosted = np.tanh(data * gain)
        max_val = np.max(np.abs(boosted))
        if max_val > 0:
            boosted = (boosted / max_val) * 0.98
        sf.write(wav_path, boosted, sr)
    except Exception as e:
        print(f"[Volume Boost Error] {e}")
    return wav_path

async def audio_player_worker():
    global current_generation_id
    while True:
        item = await audio_play_queue.get()
        gen_id = item.get("gen_id")
        audio_file = item.get("path")

        if gen_id != current_generation_id or not os.path.exists(audio_file):
            if os.path.exists(audio_file):
                try: os.remove(audio_file)
                except: pass
            audio_play_queue.task_done()
            continue

        try:
            vol = float(current_settings.get("volume", 1.0))
            if vol > 1.0:
                # Apply high-fidelity analog volume boost on playback audio stream
                audio_file = await asyncio.to_thread(apply_studio_volume_boost, audio_file, vol)
                pygame.mixer.music.set_volume(1.0)
            else:
                pygame.mixer.music.set_volume(max(0.0, min(1.0, vol)))

            pygame.mixer.music.load(audio_file)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                if gen_id != current_generation_id:
                    pygame.mixer.music.stop()
                    break
                await asyncio.sleep(0.02)
            pygame.mixer.music.unload()
        except Exception as e:
            print(f"[Player Error] {e}")
        finally:
            try:
                pygame.mixer.music.unload()
                if os.path.exists(audio_file):
                    os.remove(audio_file)
            except:
                pass
            audio_play_queue.task_done()

async def speech_worker():
    global current_generation_id, last_spoken_text
    while True:
        item = await speech_queue.get()
        text = item.get("text", "")
        gen_id = item.get("gen_id")

        if gen_id != current_generation_id or not text:
            speech_queue.task_done()
            continue

        if not current_settings.get("enabled", True):
            speech_queue.task_done()
            continue

        clean = clean_markdown_text(text)
        if not clean:
            speech_queue.task_done()
            continue

        last_spoken_text = clean
        vol = float(current_settings.get("volume", 1.0))
        speed = float(current_settings.get("speed", 1.0))
        temperature = float(current_settings.get("temperature", 0.65))

        chunks = split_into_conversational_chunks(clean)
        slot_override = item.get("slot_override")

        for chunk in chunks:
            if gen_id != current_generation_id:
                break

            if not chunk or not chunk.strip():
                continue

            lang = detect_language(chunk)
            
            # Universal Language Routing with Slot Override Support:
            if slot_override == "en" or slot_override == "first":
                ref_voice = current_settings.get("voice_en", "voiceSCOURCE.wav")
                prompt_text = current_settings.get("prompt_en", "")
                prompt_lang = "en"
                lang = "en"
            elif slot_override == "ko" or slot_override == "second":
                ref_voice = current_settings.get("voice_ko", current_settings.get("voice_en", "voiceSCOURCE.wav"))
                prompt_text = current_settings.get("prompt_ko", "")
                prompt_lang = "auto"
                if lang == "en":
                    prompt_lang = "en"
            else:
                if lang == "en":
                    ref_voice = current_settings.get("voice_en", "voiceSCOURCE.wav")
                    prompt_text = current_settings.get("prompt_en", "")
                    prompt_lang = "en"
                else:
                    ref_voice = current_settings.get("voice_ko", current_settings.get("voice_en", "voiceSCOURCE.wav"))
                    prompt_text = current_settings.get("prompt_ko", "")
                    prompt_lang = "auto"

            uid = f"{int(time.time()*1000)}_{os.getpid()}_{hash(chunk)%10000}"
            temp_out = os.path.join(TEMP_DIR, f"speech_{uid}.wav")

            try:
                print(f"[GPT-SoVITS] [{lang.upper()}] Voice: '{ref_voice}' (Vol: {int(vol*100)}%, Temp: {temperature:.2f}) -> {chunk[:35]}...")
                success = await asyncio.to_thread(
                    gpt_sovits_engine.synthesize, chunk, ref_voice, lang, speed, temperature, prompt_text, prompt_lang, temp_out, vol
                )

                if gen_id != current_generation_id:
                    if os.path.exists(temp_out): os.remove(temp_out)
                    break

                if success and os.path.exists(temp_out) and os.path.getsize(temp_out) > 0:
                    if gen_id == current_generation_id:
                        await audio_play_queue.put({"gen_id": gen_id, "path": temp_out})
                    else:
                        if os.path.exists(temp_out): os.remove(temp_out)

            except Exception as e:
                print(f"[Synthesize Chunk Error] {e}")
                continue

        speech_queue.task_done()

# Web Handlers
async def handle_index(request):
    return web.FileResponse(INDEX_HTML)

async def handle_get_settings(request):
    return web.json_response({
        "status": "ok",
        "settings": current_settings,
        "available_voices": gpt_sovits_engine.get_available_reference_voices()
    })

async def handle_save_settings(request):
    global current_settings
    data = await request.json()
    current_settings.update(data)
    save_config()
    
    # Save accompanying transcripts if provided
    if "voice_en" in data and "prompt_en" in data:
        gpt_sovits_engine.save_voice_metadata(data["voice_en"], data.get("prompt_en", ""), "en")
    if "voice_ko" in data and "prompt_ko" in data:
        gpt_sovits_engine.save_voice_metadata(data["voice_ko"], data.get("prompt_ko", ""), "ko")

    if "volume" in current_settings:
        try:
            pygame.mixer.music.set_volume(float(current_settings["volume"]))
        except:
            pass
    return web.json_response({
        "status": "ok",
        "settings": current_settings,
        "available_voices": gpt_sovits_engine.get_available_reference_voices()
    })

async def handle_test_speak(request):
    global current_generation_id
    current_generation_id += 1
    
    slot = "en"
    custom_text = ""
    try:
        if request.can_read_body:
            body = await request.json()
            slot = body.get("slot", "en")
            custom_text = body.get("text", "")
    except:
        pass

    if custom_text:
        test_phrase = custom_text
    elif slot == "en" or slot == "first":
        test_phrase = "Hello! Nice to meet you. This is an English voice test."
    elif slot == "ko" or slot == "second":
        test_phrase = "Hello there! Nice to meet you. This is a second language voice test."
    else:
        test_phrase = "Hello! Nice to meet you. This is an AI voice synthesis test."

    await speech_queue.put({"text": test_phrase, "gen_id": current_generation_id, "slot_override": slot})
    return web.json_response({"status": "queued"})

async def handle_status(request):
    is_busy = False
    try:
        is_busy = pygame.mixer.music.get_busy() or not audio_play_queue.empty()
    except:
        pass
    return web.json_response({
        "enabled": current_settings.get("enabled", True),
        "is_playing": is_busy,
        "last_spoken": last_spoken_text
    })

async def handle_get_logs(request):
    logs = []
    log_file = os.path.join(APP_DIR, "logs", "electron_backend.log")
    if os.path.exists(log_file):
        try:
            with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
                logs = [line.rstrip() for line in lines[-300:]]
        except:
            pass
    return web.json_response({"logs": logs})

async def handle_rename_voice(request):
    global current_settings
    try:
        data = await request.json()
        old_filename = data.get("old_filename", "").strip()
        new_filename = data.get("new_filename", "").strip()
        prompt_text = data.get("prompt_text", "").strip()
        prompt_lang = data.get("prompt_lang", "auto")

        ok, msg = gpt_engine.rename_voice(old_filename, new_filename, new_prompt_text=prompt_text, new_prompt_lang=prompt_lang)
        if not ok:
            return web.json_response({"status": "error", "error": msg}, status=400)

        actual_new_name = msg
        # Update current_settings if the renamed voice was selected in EN or KO slots
        changed = False
        if current_settings.get("voice_en") == old_filename:
            current_settings["voice_en"] = actual_new_name
            current_settings["prompt_en"] = prompt_text
            changed = True
        if current_settings.get("voice_ko") == old_filename:
            current_settings["voice_ko"] = actual_new_name
            current_settings["prompt_ko"] = prompt_text
            changed = True

        if changed:
            save_config(current_settings)

        voices = gpt_engine.get_available_reference_voices()
        return web.json_response({
            "status": "ok",
            "new_filename": actual_new_name,
            "available_voices": voices,
            "settings": current_settings
        })
    except Exception as e:
        return web.json_response({"status": "error", "error": str(e)}, status=500)

async def handle_delete_voice(request):
    global current_settings
    try:
        data = await request.json()
        filename = data.get("filename", "").strip()
        gpt_engine.delete_voice(filename)

        voices = gpt_engine.get_available_reference_voices()
        # Fallback if active voice was deleted
        changed = False
        if voices:
            fallback = voices[0]["filename"]
            if current_settings.get("voice_en") == filename:
                current_settings["voice_en"] = fallback
                changed = True
            if current_settings.get("voice_ko") == filename:
                current_settings["voice_ko"] = fallback
                changed = True
            if changed:
                save_config(current_settings)

        return web.json_response({
            "status": "ok",
            "available_voices": voices,
            "settings": current_settings
        })
    except Exception as e:
        return web.json_response({"status": "error", "error": str(e)}, status=500)

async def handle_save_voice_thumbnail(request):
    try:
        data = await request.json()
        filename = data.get("filename", "").strip()
        image_data = data.get("image_data", "").strip()
        image_url = data.get("image_url", "").strip()

        if not filename:
            return web.json_response({"status": "error", "error": "Filename required"}, status=400)

        base_name = os.path.splitext(filename)[0]
        target_img_path = os.path.join(REF_DIR, f"{base_name}.png")

        raw_bytes = None
        if image_data:
            if "," in image_data:
                image_data = image_data.split(",", 1)[1]
            raw_bytes = base64.b64decode(image_data)
        elif image_url:
            req = urllib.request.Request(
                image_url, 
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                raw_bytes = response.read()
        else:
            return web.json_response({"status": "error", "error": "No image data or URL provided"}, status=400)

        # Optimize and save image with PIL
        try:
            from PIL import Image
            import io
            img = Image.open(io.BytesIO(raw_bytes))
            if img.mode not in ("RGB", "RGBA"):
                img = img.convert("RGBA")
            # Downscale giant images to crisp 512x512 max avatar
            img.thumbnail((512, 512), Image.Resampling.LANCZOS)
            img.save(target_img_path, format="PNG", optimize=True)
        except Exception as pil_err:
            print(f"[Thumbnail Save Warning] PIL optimize failed, saving raw bytes: {pil_err}")
            with open(target_img_path, "wb") as f:
                f.write(raw_bytes)

        voices = gpt_sovits_engine.get_available_reference_voices()
        print(f"[Thumbnail Saved] Saved 512x512 thumbnail avatar for: {filename}")
        return web.json_response({
            "status": "ok",
            "thumbnail": f"/reference_voices/{base_name}.png?t={int(time.time()*1000)}",
            "available_voices": voices
        })
    except Exception as e:
        print(f"[Thumbnail Error] {e}")
        return web.json_response({"status": "error", "error": str(e)}, status=500)

async def handle_shutdown(request):
    async def shutdown_process():
        await asyncio.sleep(0.3)
        print("[Shutdown] Server stopped by user request from GUI.")
        os._exit(0)
    
    asyncio.create_task(shutdown_process())
    return web.json_response({"status": "shutdown"})

async def handle_trim_audio(request):
    try:
        reader = await request.multipart()
        audio_bytes = None
        start_sec = 0.0
        end_sec = 5.0
        segments_json = None
        filename = "custom_sample.wav"
        prompt_text = ""
        prompt_lang = "auto"

        while True:
            field = await reader.next()
            if field is None:
                break
            if field.name == 'audio':
                audio_bytes = await field.read()
            elif field.name == 'segments':
                segments_json = await field.text()
            elif field.name == 'start_sec':
                start_sec = float(await field.text())
            elif field.name == 'end_sec':
                end_sec = float(await field.text())
            elif field.name == 'filename':
                filename = (await field.text()).strip()
            elif field.name == 'prompt_text':
                prompt_text = (await field.text()).strip()
            elif field.name == 'prompt_lang':
                prompt_lang = (await field.text()).strip()

        if not audio_bytes:
            return web.json_response({"status": "error", "error": "No audio/video file received"}, status=400)

        # Parse multi-segment configurations
        segments = []
        if segments_json:
            try:
                segments = json.loads(segments_json)
            except Exception as pe:
                print(f"[Segment Parse Warning] {pe}")
        if not segments:
            segments = [{"start": start_sec, "end": end_sec}]

        temp_input = os.path.join(TEMP_DIR, f"upload_{int(time.time()*1000)}_{filename}")
        with open(temp_input, 'wb') as f:
            f.write(audio_bytes)

        target_path = os.path.join(REF_DIR, filename)

        try:
            # High-precision multi-segment extraction and splice via librosa + soundfile
            import numpy as np
            audio_data, sr = librosa.load(temp_input, sr=32000, mono=True)
            total_samples = len(audio_data)

            chunks = []
            for seg in segments:
                s_sec = max(0.0, float(seg.get('start', 0.0)))
                e_sec = min(total_samples / sr, float(seg.get('end', s_sec + 0.1)))
                if e_sec > s_sec:
                    s_idx = max(0, int(s_sec * sr))
                    e_idx = min(total_samples, int(e_sec * sr))
                    chunk = audio_data[s_idx:e_idx].copy()
                    
                    # 5ms micro-fade in/out to eliminate zero-crossing pops and clicks between segments
                    fade_len = int(0.005 * sr)
                    if len(chunk) > fade_len * 2:
                        fade_in = np.linspace(0.0, 1.0, fade_len)
                        fade_out = np.linspace(1.0, 0.0, fade_len)
                        chunk[:fade_len] *= fade_in
                        chunk[-fade_len:] *= fade_out
                    chunks.append(chunk)

            if chunks:
                merged_audio = np.concatenate(chunks)
            else:
                merged_audio = audio_data[:int(min(5.0 * sr, total_samples))]

            sf.write(target_path, merged_audio, sr)
        finally:
            if os.path.exists(temp_input):
                try: os.remove(temp_input)
                except: pass

        if prompt_text:
            gpt_sovits_engine.save_voice_metadata(filename, prompt_text, prompt_lang)

        print(f"[Media Trimmer] Extracted and merged {len(segments)} segments into 32kHz WAV: {target_path} (Prompt: '{prompt_text}')")

        return web.json_response({
            "status": "ok",
            "filename": filename,
            "available_voices": gpt_sovits_engine.get_available_reference_voices()
        })

    except Exception as e:
        print(f"[Media Trimmer Error] {e}")
        return web.json_response({"status": "error", "error": str(e)}, status=500)

def get_latest_transcript_path():
    pattern = os.path.join(BRAIN_DIR, "*", ".system_generated", "logs", "transcript.jsonl")
    files = glob.glob(pattern)
    if not files:
        return None
    return max(files, key=os.path.getmtime)

async def background_log_watcher():
    global current_generation_id
    print("[Watcher] Tracking active transcript.jsonl (GPT-SoVITS Complete Reader)...")
    
    last_file = None
    last_pos = 0

    while True:
        latest = get_latest_transcript_path()
        if not latest or not os.path.exists(latest):
            await asyncio.sleep(0.5)
            continue

        if latest != last_file:
            last_file = latest
            last_pos = os.path.getsize(latest)
            stop_and_clear_everything()

        try:
            curr_size = os.path.getsize(last_file)
            if curr_size > last_pos:
                with open(last_file, 'r', encoding='utf-8', errors='ignore') as f:
                    f.seek(last_pos)
                    new_lines = f.readlines()
                    last_pos = f.tell()

                for line in new_lines:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        msg_type = data.get("type")

                        if msg_type == "USER_INPUT":
                            stop_and_clear_everything()
                        elif msg_type == "PLANNER_RESPONSE":
                            tool_calls = data.get("tool_calls", [])
                            content = data.get("content", "")
                            if content and len(tool_calls) == 0 and current_settings.get("enabled", True):
                                stop_and_clear_everything()
                                await speech_queue.put({"text": content, "gen_id": current_generation_id})
                    except Exception as e:
                        pass
            elif curr_size < last_pos:
                last_pos = curr_size
        except Exception as e:
            pass

        await asyncio.sleep(0.15)

async def start_background_tasks(app):
    app['worker'] = asyncio.create_task(speech_worker())
    app['player'] = asyncio.create_task(audio_player_worker())
    app['watcher'] = asyncio.create_task(background_log_watcher())

async def cleanup_background_tasks(app):
    app['worker'].cancel()
    app['player'].cancel()
    app['watcher'].cancel()
    await app['worker']
    await app['player']
    await app['watcher']
    cleanup_temp_dir()

def main():
    app = web.Application(client_max_size=100 * 1024 * 1024)
    app.router.add_get('/', handle_index)
    app.router.add_get('/api/settings', handle_get_settings)
    app.router.add_post('/api/settings', handle_save_settings)
    app.router.add_post('/api/test_speak', handle_test_speak)
    app.router.add_post('/api/shutdown', handle_shutdown)
    app.router.add_post('/api/trim_audio', handle_trim_audio)
    app.router.add_post('/api/rename_voice', handle_rename_voice)
    app.router.add_post('/api/delete_voice', handle_delete_voice)
    app.router.add_post('/api/save_voice_thumbnail', handle_save_voice_thumbnail)
    app.router.add_get('/api/status', handle_status)
    app.router.add_get('/api/logs', handle_get_logs)
    app.router.add_static('/reference_voices/', REF_DIR)
    
    app.on_startup.append(start_background_tasks)
    app.on_cleanup.append(cleanup_background_tasks)

    port = 7861
    print("=" * 60)
    print(f"Antigravity GPT-SoVITS Voice Studio: http://localhost:{port}")
    print("=" * 60)
    
    if "--no-browser" not in sys.argv:
        webbrowser.open(f"http://localhost:{port}")
    web.run_app(app, host='127.0.0.1', port=port)

if __name__ == "__main__":
    main()
