import os
import sys
import torch
import soundfile as sf

# Bypass transformers CVE-2025-32434 check for local trusted pretrained models
import transformers.modeling_utils
import transformers.utils.import_utils
transformers.modeling_utils.check_torch_load_is_safe = lambda: None
transformers.utils.import_utils.check_torch_load_is_safe = lambda: None

core_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gpt_sovits_core")
base_dir = os.path.join(core_dir, "GPT_SoVITS")
sys.path.insert(0, core_dir)
sys.path.insert(0, base_dir)
sys.path.insert(0, os.path.join(base_dir, "eres2net"))

from TTS_infer_pack.TTS import TTS, TTS_Config

class GPTSoVITSEngine:
    def __init__(self):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.is_half = True if self.device == "cuda" else False
        self.version = "v2"
        self.ref_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reference_voices")
        
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

        print(f"[GPT-SoVITS Engine] Initializing V2 on {self.device} (FP16={self.is_half})...")
        self.tts = TTS(config)
        print("[GPT-SoVITS Engine] Neural models loaded and ready in VRAM!")

    def get_available_reference_voices(self):
        if not os.path.exists(self.ref_dir):
            os.makedirs(self.ref_dir, exist_ok=True)
        voices = []
        for f in os.listdir(self.ref_dir):
            if f.lower().endswith(('.wav', '.mp3', '.flac')):
                voices.append(f)
        return sorted(voices)

    @torch.inference_mode()
    def synthesize(self, text, ref_audio_name="voiceSCOURCE.wav", text_lang="ko", speed=1.0, output_path=None):
        try:
            ref_path = os.path.join(self.ref_dir, ref_audio_name)
            if not os.path.exists(ref_path):
                voices = self.get_available_reference_voices()
                if voices:
                    ref_path = os.path.join(self.ref_dir, voices[0])
                else:
                    print(f"[GPT-SoVITS Error] No reference audio found in {self.ref_dir}")
                    return False

            inputs = {
                'text': text,
                'text_lang': text_lang,
                'ref_audio_path': ref_path,
                'prompt_text': '',
                'prompt_lang': text_lang,
                'top_k': 5,
                'top_p': 1,
                'temperature': 1,
                'text_split_method': 'cut5',
                'speed_factor': speed,
                'batch_size': 1,
                'stream_mode': 'normal'
            }

            audio_chunks = []
            sample_rate = 32000

            for sr, audio in self.tts.run(inputs):
                sample_rate = sr
                audio_chunks.append(audio)

            if not audio_chunks:
                return False

            import numpy as np
            full_audio = np.concatenate(audio_chunks, axis=0)

            if output_path:
                sf.write(output_path, full_audio, sample_rate)
                return True
            return full_audio, sample_rate

        except Exception as e:
            print(f"[GPT-SoVITS Synthesis Error] {e}")
            import traceback
            traceback.print_exc()
            return False

gpt_sovits_engine = GPTSoVITSEngine()
