"""Optional IndicF5 Hindi TTS backend - narrates in the CREATOR'S OWN voice.

Disabled unless AUDIO_TTS_ENGINE=indicf5. It needs a short, clean reference
recording of the channel owner's own voice (with their consent - never clone
anyone else) plus the exact transcript of that recording:

  voice/ref.wav   10-15 s, mono, quiet room, natural storytelling tone
  voice/ref.txt   the exact Hindi words spoken in ref.wav

Paths can be overridden with INDICF5_REF_AUDIO / INDICF5_REF_TEXT(_FILE).
Any failure raises, and generate_assets.py falls back to Edge-TTS.
"""
import os
import subprocess
import threading
from pathlib import Path

_model = None
_lock = threading.Lock()  # the model is not thread-safe; scenes run in parallel
_audio_patched = False


def _patch_torchaudio_load():
    """torchaudio >= 2.9 routes torchaudio.load() through torchcodec, whose
    prebuilt .so must match the exact torch build + FFmpeg libs. On the GitHub
    runner that failed with "Could not load this library: libtorchcodec_image.so",
    so every scene silently fell back to Edge-TTS. IndicF5 only needs
    torchaudio.load() to read the reference WAV, so read it with soundfile
    (already installed) and return the same (tensor[channels, frames], sr)."""
    global _audio_patched
    if _audio_patched:
        return
    import numpy as np
    import soundfile as sf
    import torch
    import torchaudio

    original_load = torchaudio.load

    def _to_tensor(data, sr):
        return torch.from_numpy(np.ascontiguousarray(data.T)), sr  # (ch, frames)

    def _sf_load(path, *args, **kwargs):
        # 1) soundfile: WAV/FLAC/OGG (and MP3 with libsndfile >= 1.1)
        try:
            data, sr = sf.read(str(path), dtype="float32", always_2d=True)
            return _to_tensor(data, sr)
        except Exception:
            pass
        # 2) ffmpeg decodes ANY format to a temp WAV, then soundfile reads it
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            wav = os.path.join(tmp, "decoded.wav")
            proc = subprocess.run(["ffmpeg", "-y", "-i", str(path), "-c:a", "pcm_f32le", wav],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if proc.returncode == 0 and os.path.exists(wav):
                data, sr = sf.read(wav, dtype="float32", always_2d=True)
                return _to_tensor(data, sr)
        # 3) last resort: torchaudio's own loader
        return original_load(path, *args, **kwargs)

    torchaudio.load = _sf_load
    _audio_patched = True


def _load_model():
    global _model
    _patch_torchaudio_load()
    if _model is None:
        from transformers import AutoModel
        repo = os.getenv("INDICF5_MODEL", "ai4bharat/IndicF5")
        token = os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_API_KEY") or None
        _model = AutoModel.from_pretrained(repo, trust_remote_code=True, token=token)
        try:
            import torch
            _model = _model.to("cuda" if torch.cuda.is_available() else "cpu")
        except Exception:
            pass
    return _model


def _reference():
    ref_audio = os.getenv("INDICF5_REF_AUDIO", "").strip() or "voice/ref.wav"
    ref_text = os.getenv("INDICF5_REF_TEXT", "").strip()
    if not ref_text:
        text_file = os.getenv("INDICF5_REF_TEXT_FILE", "").strip() or "voice/ref.txt"
        if Path(text_file).exists():
            ref_text = Path(text_file).read_text(encoding="utf-8").strip()
    if not Path(ref_audio).exists() or not ref_text:
        raise RuntimeError(
            "IndicF5 needs voice/ref.wav + voice/ref.txt (your own voice sample and its exact transcript)."
        )
    return ref_audio, ref_text


def generate_indicf5_audio(text: str, output_path: str) -> bool:
    ref_audio, ref_text = _reference()
    import numpy as np
    import soundfile as sf
    with _lock:
        model = _load_model()
        audio = model(text, ref_audio_path=ref_audio, ref_text=ref_text)
    if getattr(audio, "dtype", None) == np.int16:
        audio = audio.astype(np.float32) / 32768.0
    wav = output_path + ".indicf5.wav"
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    sf.write(wav, np.asarray(audio, dtype=np.float32), 24000)
    proc = subprocess.run(
        ["ffmpeg", "-y", "-i", wav,
         "-af", "loudnorm=I=-16:TP=-1.5:LRA=11,highpass=f=70,lowpass=f=12000",
         "-ar", "24000", "-ac", "1", "-c:a", "libmp3lame", "-q:a", "3", output_path],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        os.remove(wav)
    except OSError:
        pass
    return proc.returncode == 0 and os.path.exists(output_path)