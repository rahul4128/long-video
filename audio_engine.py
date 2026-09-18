"""Local-first Hindi TTS engine.

Uses Kokoro as the primary Hindi narration engine, with cinematic punctuation
pauses assembled as real silence between short prosody-safe chunks. The caller
in generate_assets.py keeps Edge-TTS as the automatic fallback.
"""
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
    """Split narration at strong performance boundaries without over-fragmenting it.

    Ellipsis and em-dash are treated as intentional cinematic beats. Sentence
    punctuation stays attached to the preceding text so Kokoro still receives
    the punctuation cue and produces its own natural prosody.
    """
    text = re.sub(r"\s+", " ", (text or "").strip())
    if not text:
        return []

    chunks = []
    start = 0
    # Split after sentence-ending punctuation, ellipsis, or an em-dash.
    # A dash is kept with the preceding clause so it sounds like a reveal beat.
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


def _pause_seconds(chunk: str, index: int, total: int) -> float:
    """Return a cinematic pause after a chunk based on its ending cue."""
    if index >= total - 1:
        return 0.0

    chunk = chunk.rstrip()
    if chunk.endswith("…"):
        return max(0.0, float(os.getenv("KOKORO_ELLIPSIS_PAUSE_MS", "360")) / 1000.0)
    if chunk.endswith("—"):
        return max(0.0, float(os.getenv("KOKORO_DASH_PAUSE_MS", "260")) / 1000.0)
    if re.search(r"[!?]$", chunk):
        return max(0.0, float(os.getenv("KOKORO_EXCLAMATION_PAUSE_MS", "300")) / 1000.0)
    if chunk.endswith("।"):
        return max(0.0, float(os.getenv("KOKORO_SENTENCE_PAUSE_MS", "220")) / 1000.0)
    return max(0.0, float(os.getenv("KOKORO_CLAUSE_PAUSE_MS", "110")) / 1000.0)


def _synthesize_chunk(pipeline, text: str, voice: str, speed: float):
    pieces = []
    for result in pipeline(text, voice=voice, speed=speed):
        # Kokoro's current iterator yields (graphemes, phonemes, audio).
        # Keep a compatibility fallback for wrappers exposing .audio.
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
    """Generate Hindi narration with Kokoro and cinematic punctuation pauses."""
    if not KOKORO_AVAILABLE:
        raise RuntimeError("Kokoro is not installed. " + KOKORO_IMPORT_ERROR)

    voice = os.getenv("KOKORO_VOICE", "hm_omega")
    speed = float(os.getenv("KOKORO_SPEED", "0.96"))
    sample_rate = 24000
    pipeline = _get_pipeline()
    chunks = _split_cinematic_chunks(text)

    if not chunks:
        return False

    audio_parts = []
    silence_cache = {}

    for index, chunk in enumerate(chunks):
        audio = _synthesize_chunk(pipeline, chunk, voice, speed)
        if audio is None:
            return False
        audio_parts.append(audio)

        pause = _pause_seconds(chunk, index, len(chunks))
        if pause > 0:
            pause_samples = int(round(pause * sample_rate))
            # Reuse identical silence arrays to keep concatenation lightweight.
            if pause_samples not in silence_cache:
                silence_cache[pause_samples] = np.zeros(pause_samples, dtype=audio.dtype)
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
