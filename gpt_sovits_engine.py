import os
import sys

# Force English localization for clean international terminal logs
os.environ["I18N_LANG"] = "en_US"

import soundfile as sf
import json

core_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gpt_sovits_core")
base_dir = os.path.join(core_dir, "GPT_SoVITS")
sys.path.insert(0, core_dir)
sys.path.insert(0, base_dir)
sys.path.insert(0, os.path.join(base_dir, "eres2net"))

class GPTSoVITSEngine:
    def __init__(self):
        self.device = "cuda"
        self.is_half = True
        self.version = "v2"
        self.ref_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reference_voices")
        os.makedirs(self.ref_dir, exist_ok=True)
        self.tts = None
        self._is_ready = False
        self._is_loading = False

    def is_ready(self):
        return self._is_ready

    def load_models(self):
        if self._is_ready:
            return True
        if self._is_loading:
            import time
            while self._is_loading and not self._is_ready:
                time.sleep(0.1)
            return self._is_ready

        self._is_loading = True
        try:
            import torch
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            self.is_half = True if self.device == "cuda" else False

            # Bypass transformers CVE-2025-32434 check for local trusted pretrained models
            try:
                import transformers.modeling_utils
                import transformers.utils.import_utils
                transformers.modeling_utils.check_torch_load_is_safe = lambda: None
                transformers.utils.import_utils.check_torch_load_is_safe = lambda: None
            except:
                pass

            from TTS_infer_pack.TTS import TTS, TTS_Config
            t2s_path = os.path.join(base_dir, "pretrained_models", "gsv-v2final-pretrained", "s1bert25hz-5kh-longer-epoch=12-step=369668.ckpt")
            vits_path = os.path.join(base_dir, "pretrained_models", "gsv-v2final-pretrained", "s2G2333k.pth")
            bert_path = os.path.join(base_dir, "pretrained_models", "chinese-roberta-wwm-ext-large")
            cnhubert_path = os.path.join(base_dir, "pretrained_models", "chinese-hubert-base")

            config = TTS_Config()
            config.device = self.device
            config.is_half = self.is_half
            config.version = self.version
            config.t2s_weights_path = t2s_path
            config.vits_weights_path = vits_path
            config.bert_base_path = bert_path
            config.cnhuhbert_base_path = cnhubert_path
            if torch.cuda.is_available():
                torch.backends.cudnn.benchmark = True
                try:
                    torch.backends.cuda.matmul.allow_tf32 = True
                    torch.backends.cudnn.allow_tf32 = True
                except:
                    pass

            print(f"[GPT-SoVITS Engine] Initializing V2 on {self.device} (FP16={self.is_half})...")
            self.tts = TTS(config)
            print("[GPT-SoVITS Engine] Neural models loaded and ready in VRAM!")

            # Pre-warm GPU CUDA kernels for zero-lag first response
            try:
                voices = self.get_available_reference_voices()
                if voices:
                    warmup_ref = os.path.join(self.ref_dir, voices[0]["filename"])
                    dummy_inputs = {
                        'text': "Ready.",
                        'text_lang': "en",
                        'ref_audio_path': warmup_ref,
                        'prompt_text': "Ready.",
                        'prompt_lang': "en",
                        'top_k': 5,
                        'top_p': 1.0,
                        'temperature': 0.6,
                        'text_split_method': 'cut0',
                        'speed_factor': 1.0,
                        'batch_size': 1,
                        'stream_mode': 'normal',
                        'parallel_infer': True
                    }
                    for _ in self.tts.run(dummy_inputs): pass
                    print("[GPT-SoVITS Engine] GPU kernels pre-warmed for ultra-low latency inference!")
            except Exception as e:
                print(f"[GPT-SoVITS Warmup Notice] {e}")

            self._is_ready = True
            return True
        except Exception as e:
            print(f"[GPT-SoVITS Engine Load Error] {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            self._is_loading = False

    def get_voice_metadata(self, voice_filename):
        base_name = os.path.splitext(voice_filename)[0]
        txt_path = os.path.join(self.ref_dir, f"{base_name}.txt")
        if os.path.exists(txt_path):
            try:
                with open(txt_path, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                if content.startswith("[") and "]" in content:
                    parts = content.split("]", 1)
                    lang = parts[0].replace("[", "").strip().lower()
                    text = parts[1].strip()
                    return {"text": text, "lang": lang}
                return {"text": content, "lang": "auto"}
            except:
                pass
        return {"text": "", "lang": "auto"}

    def save_voice_metadata(self, voice_filename, prompt_text, prompt_lang="auto"):
        base_name = os.path.splitext(voice_filename)[0]
        txt_path = os.path.join(self.ref_dir, f"{base_name}.txt")
        try:
            with open(txt_path, 'w', encoding='utf-8') as f:
                if prompt_lang and prompt_lang != "auto":
                    f.write(f"[{prompt_lang}] {prompt_text}")
                else:
                    f.write(prompt_text)
            return True
        except Exception as e:
            print(f"[Error saving voice prompt metadata] {e}")
            return False

    def rename_voice(self, old_filename, new_filename, new_prompt_text=None, new_prompt_lang="auto"):
        if not old_filename or not new_filename:
            return False, "Invalid filename"
        
        old_base, old_ext = os.path.splitext(old_filename)
        if not old_ext:
            old_ext = ".wav"
            old_filename = old_base + old_ext
            
        new_base, new_ext = os.path.splitext(new_filename)
        if not new_ext:
            new_ext = old_ext
            new_filename = new_base + new_ext

        old_audio_path = os.path.join(self.ref_dir, old_filename)
        new_audio_path = os.path.join(self.ref_dir, new_filename)
        old_txt_path = os.path.join(self.ref_dir, f"{old_base}.txt")
        new_txt_path = os.path.join(self.ref_dir, f"{new_base}.txt")

        if not os.path.exists(old_audio_path):
            return False, f"File '{old_filename}' not found"

        if old_filename != new_filename and os.path.exists(new_audio_path):
            return False, f"Target filename '{new_filename}' already exists"

        # 1. Rename audio file
        if old_audio_path != new_audio_path:
            os.rename(old_audio_path, new_audio_path)

        # 2. Rename or update companion txt file simultaneously
        if new_prompt_text is not None:
            self.save_voice_metadata(new_filename, new_prompt_text, new_prompt_lang)
            if old_txt_path != new_txt_path and os.path.exists(old_txt_path):
                try: os.remove(old_txt_path)
                except: pass
        else:
            if os.path.exists(old_txt_path) and old_txt_path != new_txt_path:
                os.rename(old_txt_path, new_txt_path)

        # 3. Rename companion thumbnail image if exists
        for ext in ['.png', '.jpg', '.jpeg', '.webp']:
            old_img = os.path.join(self.ref_dir, f"{old_base}{ext}")
            new_img = os.path.join(self.ref_dir, f"{new_base}{ext}")
            if os.path.exists(old_img) and old_img != new_img:
                try: os.rename(old_img, new_img)
                except: pass

        return True, new_filename

    def delete_voice(self, filename):
        base, ext = os.path.splitext(filename)
        audio_path = os.path.join(self.ref_dir, filename)
        txt_path = os.path.join(self.ref_dir, f"{base}.txt")
        if os.path.exists(audio_path):
            try: os.remove(audio_path)
            except: pass
        if os.path.exists(txt_path):
            try: os.remove(txt_path)
            except: pass
        for img_ext in ['.png', '.jpg', '.jpeg', '.webp']:
            img_path = os.path.join(self.ref_dir, f"{base}{img_ext}")
            if os.path.exists(img_path):
                try: os.remove(img_path)
                except: pass
        return True

    def get_voice_thumbnail(self, voice_filename):
        base = os.path.splitext(voice_filename)[0]
        for ext in ['.png', '.jpg', '.jpeg', '.webp']:
            img_path = os.path.join(self.ref_dir, f"{base}{ext}")
            if os.path.exists(img_path):
                return f"/reference_voices/{base}{ext}"
        return None

    def get_available_reference_voices(self):
        if not os.path.exists(self.ref_dir):
            os.makedirs(self.ref_dir, exist_ok=True)
        voices = []
        for f in os.listdir(self.ref_dir):
            if f.lower().endswith(('.wav', '.mp3', '.flac')):
                meta = self.get_voice_metadata(f)
                thumb = self.get_voice_thumbnail(f)
                voices.append({
                    "filename": f,
                    "prompt_text": meta.get("text", ""),
                    "prompt_lang": meta.get("lang", "auto"),
                    "thumbnail": thumb
                })
        return sorted(voices, key=lambda x: x["filename"])

    def synthesize(self, text, ref_audio_name="voiceSCOURCE.wav", text_lang="ko", speed=1.0, temperature=0.65, prompt_text="", prompt_lang="auto", output_path=None, volume=1.0, fast_mode=True):
        if not self._is_ready:
            self.load_models()
        if not self.tts:
            print("[GPT-SoVITS Engine] Error: Model is not ready for synthesis!")
            return False
        try:
            ref_path = os.path.join(self.ref_dir, ref_audio_name)
            if not os.path.exists(ref_path):
                voices = self.get_available_reference_voices()
                if voices:
                    ref_audio_name = voices[0]["filename"]
                    ref_path = os.path.join(self.ref_dir, ref_audio_name)
                else:
                    print(f"[GPT-SoVITS Error] No reference audio found in {self.ref_dir}")
                    return False

            if not prompt_text:
                meta = self.get_voice_metadata(ref_audio_name)
                prompt_text = meta.get("text", "")
                if meta.get("lang") and meta.get("lang") != "auto":
                    prompt_lang = meta.get("lang")

            if not prompt_lang or prompt_lang == "auto":
                import re
                if re.search(r'[\uac00-\ud7a3]', prompt_text):
                    prompt_lang = "ko"
                elif re.search(r'[\u3040-\u30ff]', prompt_text):
                    prompt_lang = "ja"
                elif re.search(r'[a-zA-Z]', prompt_text):
                    prompt_lang = "en"
                else:
                    prompt_lang = text_lang

            # Use cut0 (no artificial chunking inside model) for smooth, unbroken human sentence flow
            inputs = {
                'text': text,
                'text_lang': text_lang,
                'ref_audio_path': ref_path,
                'prompt_text': prompt_text,
                'prompt_lang': prompt_lang if prompt_text else text_lang,
                'top_k': 5 if fast_mode else 15,
                'top_p': 0.85 if fast_mode else 0.95,
                'temperature': max(0.5, min(1.0, float(temperature))),
                'text_split_method': 'cut0',
                'speed_factor': speed,
                'batch_size': 1,
                'stream_mode': 'normal',
                'parallel_infer': True if fast_mode else False
            }

            audio_chunks = []
            sample_rate = 32000

            import torch
            with torch.inference_mode():
                for sr, audio in self.tts.run(inputs):
                    sample_rate = sr
                    audio_chunks.append(audio)

            if not audio_chunks:
                return False

            import numpy as np
            full_audio = np.concatenate(audio_chunks, axis=0)

            if output_path:
                if full_audio.dtype != np.int16:
                    max_abs = np.max(np.abs(full_audio))
                    if max_abs > 1.0:
                        full_audio = full_audio / max_abs
                    full_audio = (full_audio * 32767.0).astype(np.int16)
                sf.write(output_path, full_audio, sample_rate, subtype='PCM_16')
                return True
            return full_audio, sample_rate

        except Exception as e:
            print(f"[GPT-SoVITS Synthesis Error] {e}")
            import traceback
            traceback.print_exc()
            return False

gpt_sovits_engine = GPTSoVITSEngine()
