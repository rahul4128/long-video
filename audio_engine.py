"""Local-first Hindi TTS engine with storyteller-style prosody.

Kokoro remains the primary Hindi narration engine. This layer deliberately
varies pace and silence by storytelling function instead of rendering every
sentence at one fixed speed/pause. The caller keeps Edge-TTS as the fallback.
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
    """Return a restrained speed/pause profile for a human storyteller feel.

    The variation is deterministic (not random) so renders remain reproducible.
    It uses lexical and punctuation cues rather than pretending TTS has emotion
    it cannot reliably express.
    """
    lowered = (chunk or "").lower()
    speed = 1.0
    pause = None

    # Curiosity / question: slightly slower, then leave room for the viewer.
    if "?" in chunk or any(token in lowered for token in (
        "क्यों", "कैसे", "क्या", "रहस्य", "सच", "लेकिन", "मगर"
    )):
        speed = 0.94
        pause = 0.26

    # Revelation / high-stakes words: slow the key sentence without making it
    # unnaturally theatrical.
    if any(token in lowered for token in (
        "अचानक", "चौंक", "खुलासा", "सच्चाई", "असल में", "यही वजह",
        "रहस्य", "चमत्कार", "सत्य", "reveal", "mystery"
    )):
        speed = min(speed, 0.90)
        pause = max(pause or 0.0, 0.30)

    # Action: a little quicker to create contrast with explanation/reveal.
    if any(token in lowered for token in (
        "भागा", "दौड़ा", "युद्ध", "गिरा", "उठा", "पहुंचा", "पहुंचे",
        "अचानक", "देखा", "मिला", "खुला", "दौड़", "युद्ध"
    )):
        speed = max(speed, 1.02)

    # Exclamation gets energy; don't let this override a deliberate reveal.
    if re.search(r"[!]$", chunk):
        speed = max(speed, 1.00)

    # Short deterministic micro-variation prevents every chunk from having
    # exactly the same cadence while remaining reproducible across CI runs.
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

    # Keep pauses short enough that the narration never sounds chopped up.
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
        # KOKORO_SPEED remains the global personality control; the profile is a
        # bounded multiplier so the new layer never becomes cartoonishly fast.
        speed = max(0.84, min(1.08, base_speed * profile_speed))
        audio = _synthesize_chunk(pipeline, chunk, voice, speed)
        if audio is None:
            return False
        audio_parts.append(audio)

        if index < len(chunks) - 1:
            pause_ms = int(round(pause * 1000))
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
