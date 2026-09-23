"""Local-first Hindi TTS engine with storyteller-style prosody.

Kokoro remains the primary Hindi narration engine. This layer deliberately
varies pace and silence by storytelling function instead of rendering every
sentence at one fixed speed/pause. The final audio is also mastered with
speech-friendly EQ, gentle compression, loudness normalization, and a true
peak limiter so narration stays consistent across scenes.
"""
import hashlib
import os
import re
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


def _split_cinematic_chunks(text: str) -> list:
    """Split at performance boundaries while keeping natural sentence prosody."""
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


def _story_profile(chunk: str, index: int) -> tuple:
    """Return a restrained speed/pause profile for a human storyteller feel."""
    lowered = (chunk or "").lower()
    speed = 1.0
    pause = None

    if "?" in chunk or any(token in lowered for token in (
        "क्यों", "कैसे", "क्या", "रहस्य", "सच", "लेकिन", "मगर"
    )):
        speed = 0.94
        pause = 0.26

    if any(token in lowered for token in (
        "अचानक", "चौंक", "खुलासा", "सच्चाई", "असल में", "यही वजह",
        "रहस्य", "चमत्कार", "सत्य", "reveal", "mystery"
    )):
        speed = min(speed, 0.90)
        pause = max(pause or 0.0, 0.30)

    if any(token in lowered for token in (
        "भागा", "दौड़ा", "युद्ध", "गिरा", "उठा", "पहुंचा", "पहुंचे",
        "अचानक", "देखा", "मिला", "खुला", "दौड़"
    )):
        speed = max(speed, 1.02)

    if re.search(r"[!]$", chunk):
        speed = max(speed, 1.00)

    digest = hashlib.sha1(chunk.encode("utf-8")).digest()[0]
    micro = (-0.012, 0.0, 0.010)[digest % 3]
    speed = max(0.86, min(1.06, speed + micro))

    if pause is None:
        if chunk.endswith("…"):
            pause = 0.36
        elif chunk.endswith("—"):
            pause = 0.24
        elif re.search(r"[!?]$", chunk):
            pause = 0.22
        elif chunk.endswith("।"):
            pause = 0.16
        else:
            pause = 0.10

    return speed, max(0.07, min(0.42, pause))


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


def _master_narration(input_path: str, output_path: str) -> bool:
    """Apply transparent speech mastering without making the voice loud/harsh.

    High/low-pass removes rumble and codec hiss, the compressor evens out
    sentence-to-sentence level changes, loudnorm targets a consistent program
    loudness, and alimiter prevents transient peaks from clipping.
    """
    filter_chain = (
        "highpass=f=70,"
        "lowpass=f=12000,"
        "acompressor=threshold=-18dB:ratio=2.2:attack=12:release=140:makeup=1.5,"
        "loudnorm=I=-16:TP=-1.5:LRA=9,"
        "alimiter=limit=-1.2:attack=5:release=80"
    )
    result = subprocess.run(
        [
            "ffmpeg", "-y", "-i", input_path,
            "-af", filter_chain,
            "-ar", "24000", "-ac", "1",
            "-c:a", "libmp3lame", "-q:a", "3",
            output_path,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode != 0:
        print(f"Narration mastering failed: {result.stderr[-800:]}", flush=True)
        return False
    return os.path.exists(output_path) and os.path.getsize(output_path) > 1000


def generate_kokoro_audio(text: str, output_path: str) -> bool:
    """Generate Hindi narration with storyteller-style dynamic pacing."""
    if not KOKORO_AVAILABLE:
        raise RuntimeError("Kokoro is not installed. " + KOKORO_IMPORT_ERROR)

    voice = os.getenv("KOKORO_VOICE", "hm_omega")
    base_speed = float(os.getenv("KOKORO_SPEED", "0.96"))
    sample_rate = 24000
    pipeline = _get_pipeline()
    chunks = _split_cinematic_chunks(text)

    if not chunks:
        return False

    audio_parts = []
    silence_cache = {}

    for index, chunk in enumerate(chunks):
        profile_speed, pause = _story_profile(chunk, index)
        speed = max(0.84, min(1.08, base_speed * profile_speed))
        audio = _synthesize_chunk(pipeline, chunk, voice, speed)
        if audio is None:
            return False
        audio_parts.append(audio)

        if index < len(chunks) - 1:
            pause_samples = int(round(pause * sample_rate))
            if pause_samples not in silence_cache:
                silence_cache[pause_samples] = np.zeros(
                    pause_samples, dtype=audio.dtype
                )
            audio_parts.append(silence_cache[pause_samples])

    audio = np.concatenate(audio_parts)
    wav_path = output_path + ".kokoro.wav"
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    sf.write(wav_path, audio, sample_rate)

    mastered = _master_narration(wav_path, output_path)
    try:
        os.remove(wav_path)
    except OSError:
        pass
    return mastered
