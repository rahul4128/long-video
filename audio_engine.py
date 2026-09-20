"""Local-first Hindi TTS with storyteller-style prosody.

Kokoro is primary and Edge-TTS remains the automatic fallback. The engine
adds restrained emotional pacing, micro-breaths, emphasis cues, pronunciation
awareness, and light voice finishing without changing the original narration
words used by subtitles.
"""
import hashlib
import os
import re
import subprocess
from pathlib import Path

from storyteller import build_prosody_map, apply_prosody_map, prepare_storyteller_text

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


def _split_cinematic_chunks(text: str) -> list:
    text = re.sub(r"\s+", " ", (text or "").strip())
    if not text:
        return []

    chunks = []
    start = 0
    for match in re.finditer(r"[।!?]+|…+|—", text):
        end = match.end()
        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)
        start = end
        while start < len(text) and text[start].isspace():
            start += 1

    tail = text[start:].strip()
    if tail:
        chunks.append(tail)
    return chunks or [text]


def _story_profile(chunk: str, index: int, total: int, prosody: dict) -> tuple:
    lower = (chunk or "").lower()
    speed = float(prosody.get("speed", 0.98) or 0.98)
    pause = float(prosody.get("pause_after", 0.16) or 0.16)

    if "?" in chunk or any(x in lower for x in ("क्यों", "कैसे", "क्या", "रहस्य", "लेकिन", "मगर")):
        speed = min(speed, 0.94)
        pause = max(pause, 0.24)

    if any(x in lower for x in ("अचानक", "चौंक", "खुलासा", "सच्चाई", "असल में", "यही वजह", "चमत्कार", "सत्य", "reveal", "mystery")):
        speed = min(speed, 0.90)
        pause = max(pause, 0.30)

    if any(x in lower for x in ("भागा", "दौड़ा", "युद्ध", "गिरा", "उठा", "पहुंचा", "देखा", "मिला", "खुला")):
        speed = max(speed, 1.02)
        pause = min(pause, 0.14)

    if re.search(r"[!]$", chunk):
        speed = max(speed, 1.00)

    # First line gets a slightly more direct delivery; final line is warmer
    # and slower so the CTA does not sound like an abrupt ad read.
    if index == 0:
        speed = min(speed, 0.97)
    if index == total - 1:
        speed = min(speed, 0.96)
        pause = max(pause, 0.18)

    digest = hashlib.sha1(chunk.encode("utf-8")).digest()[0]
    micro = (-0.012, 0.0, 0.010)[digest % 3]
    speed = max(0.86, min(1.06, speed + micro))
    pause = max(0.07, min(0.42, pause))
    return speed, pause


def _synthesize_chunk(pipeline, text: str, voice: str, speed: float):
    pieces = []
    for result in pipeline(text, voice=voice, speed=speed):
        if isinstance(result, tuple) and len(result) >= 3:
            audio = result[2]
        else:
            audio = getattr(result, "audio", None)
        if audio is not None:
            pieces.append(audio)
    if not pieces:
        return None
    return np.concatenate(pieces)


def _ffmpeg_finish(wav_path: str, output_path: str) -> bool:
    """Light voice finishing: loudness, gentle cleanup, and soft compression."""
    proc = subprocess.run(
        [
            "ffmpeg", "-y", "-i", wav_path,
            "-af",
            "highpass=f=70,lowpass=f=12000,"
            "acompressor=threshold=-18dB:ratio=2.2:attack=12:release=90:makeup=1,"
            "loudnorm=I=-16:TP=-1.5:LRA=11",
            "-ar", "24000", "-ac", "1",
            "-c:a", "libmp3lame", "-q:a", "3",
            output_path,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return proc.returncode == 0 and os.path.exists(output_path)


def generate_kokoro_audio(text: str, output_path: str, prosody: dict | None = None) -> bool:
    """Generate Hindi narration with human-like storyteller pacing."""
    if not KOKORO_AVAILABLE:
        raise RuntimeError("Kokoro is not installed. " + KOKORO_IMPORT_ERROR)

    original = re.sub(r"\s+", " ", (text or "").strip())
    if not original:
        return False

    prosody = prosody or build_prosody_map(original)
    spoken = apply_prosody_map(original, prosody)

    voice = os.getenv("KOKORO_VOICE", "hm_omega")
    base_speed = float(os.getenv("KOKORO_SPEED", "0.96"))
    sample_rate = 24000
    pipeline = _get_pipeline()
    chunks = _split_cinematic_chunks(spoken)
    if not chunks:
        return False

    audio_parts = []
    silence_cache = {}

    for index, chunk in enumerate(chunks):
        profile_speed, pause = _story_profile(chunk, index, len(chunks), prosody)
        speed = max(0.84, min(1.08, base_speed * profile_speed))
        audio = _synthesize_chunk(pipeline, chunk, voice, speed)
        if audio is None:
            return False
        audio_parts.append(audio)

        if index < len(chunks) - 1:
            pause_samples = int(round(pause * sample_rate))
            if pause_samples not in silence_cache:
                silence_cache[pause_samples] = np.zeros(pause_samples, dtype=audio.dtype)
            audio_parts.append(silence_cache[pause_samples])

    audio = np.concatenate(audio_parts)
    wav_path = output_path + ".kokoro.wav"
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    sf.write(wav_path, audio, sample_rate)

    try:
        return _ffmpeg_finish(wav_path, output_path)
    finally:
        try:
            os.remove(wav_path)
        except OSError:
            pass
