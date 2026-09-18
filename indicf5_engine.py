"""Optional IndicF5 Hindi TTS backend.

Disabled unless AUDIO_TTS_ENGINE=indicf5 and a reference WAV + transcript are
configured. This keeps the default GitHub runner lightweight while exposing
IndicF5 as a higher-quality, opt-in engine.
"""
import os
import subprocess
from pathlib import Path

_model = None

def _load_model():
    global _model
    if _model is None:
        from transformers import AutoModel
        repo = os.getenv("INDICF5_MODEL", "ai4bharat/IndicF5")
        _model = AutoModel.from_pretrained(repo, trust_remote_code=True)
        try:
            import torch
            _model = _model.to("cuda" if torch.cuda.is_available() else "cpu")
        except Exception:
            pass
    return _model

def generate_indicf5_audio(text: str, output_path: str) -> bool:
    ref_audio = os.getenv("INDICF5_REF_AUDIO", "").strip()
    ref_text = os.getenv("INDICF5_REF_TEXT", "").strip()
    if not ref_audio or not ref_text or not Path(ref_audio).exists():
        raise RuntimeError("Set INDICF5_REF_AUDIO and INDICF5_REF_TEXT for IndicF5.")
    import numpy as np
    import soundfile as sf
    model = _load_model()
    audio = model(text, ref_audio_path=ref_audio, ref_text=ref_text)
    if getattr(audio, "dtype", None) == np.int16:
        audio = audio.astype(np.float32) / 32768.0
    wav = output_path + ".indicf5.wav"
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    sf.write(wav, np.asarray(audio, dtype=np.float32), 24000)
    proc = subprocess.run(["ffmpeg","-y","-i",wav,"-af","loudnorm=I=-16:TP=-1.5:LRA=11,highpass=f=70,lowpass=f=12000","-ar","24000","-ac","1","-c:a","libmp3lame","-q:a","3",output_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try: os.remove(wav)
    except OSError: pass
    return proc.returncode == 0 and os.path.exists(output_path)
