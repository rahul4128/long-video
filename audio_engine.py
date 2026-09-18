"""Local-first Hindi TTS engine.

Uses Kokoro when installed, with the existing Edge-TTS pipeline as a fallback
in generate_assets.py. Audio is normalized to a consistent loudness target.
"""
import os
import subprocess
from pathlib import Path

KOKORO_AVAILABLE = False
KOKORO_IMPORT_ERROR = ""
_pipeline = None

try:
    from kokoro import KPipeline
    import numpy as np
    import soundfile as sf
    KOKORO_AVAILABLE = True
except Exception as exc:
    KOKORO_IMPORT_ERROR = str(exc)


def _get_pipeline():
    global _pipeline
    if _pipeline is None:
        _pipeline = KPipeline(lang_code="h")
    return _pipeline


def generate_kokoro_audio(text: str, output_path: str) -> bool:
    """Generate Hindi narration with Kokoro and write normalized MP3."""
    if not KOKORO_AVAILABLE:
        raise RuntimeError(
            "Kokoro is not installed. " + KOKORO_IMPORT_ERROR
        )

    voice = os.getenv("KOKORO_VOICE", "hm_omega")
    speed = float(os.getenv("KOKORO_SPEED", "0.96"))
    sample_rate = 24000

    pipeline = _get_pipeline()
    pieces = []

    for result in pipeline(text, voice=voice, speed=speed):
        # Kokoro's current iterator yields (graphemes, phonemes, audio).
        # Keep a small compatibility fallback for wrappers that expose an
        # object with an .audio attribute.
        if isinstance(result, tuple) and len(result) >= 3:
            audio = result[2]
        else:
            audio = getattr(result, "audio", None)
        if audio is not None:
            pieces.append(audio)

    if not pieces:
        return False

    audio = np.concatenate(pieces)
    wav_path = output_path + ".kokoro.wav"
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    sf.write(wav_path, audio, sample_rate)

    proc = subprocess.run(
        [
            "ffmpeg", "-y", "-i", wav_path,
            "-af", "loudnorm=I=-16:TP=-1.5:LRA=11,highpass=f=70,lowpass=f=12000",
            "-ar", "24000", "-ac", "1",
            "-c:a", "libmp3lame", "-q:a", "3",
            output_path,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    try:
        os.remove(wav_path)
    except OSError:
        pass

    return proc.returncode == 0 and os.path.exists(output_path)
