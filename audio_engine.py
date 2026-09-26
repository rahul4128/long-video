"""Kokoro Hindi TTS with a soft, human storyteller finish.

Same Kokoro model as the main branch (hexgrad/Kokoro-82M, lang_code="h"),
fast on a CPU runner (seconds per scene, no GPU needed). On top of the
main-branch pacing logic this version adds what makes a synthetic voice read
as a calm human narrator:

  1. Soft female voice by default (hf_alpha; Natasha-like). Two voices can be
     blended: KOKORO_VOICE="hf_alpha,hf_beta" averages them.
  2. Calmer base pace (0.92) with gentle per-sentence variation.
  3. Human sentence gaps: 0.28-0.55 s depending on punctuation (main used
     0.10-0.36 s, which sounds rushed), with small deterministic jitter so
     the rhythm is never mechanical.
  4. "Room tone" instead of digital silence in the gaps - a real recording is
     never absolutely silent, and hard zero-silence is a big robotic tell.
  5. Each sentence is trimmed of Kokoro's own edge silence and gets 12 ms
     fades, so gaps are exactly as intended and there are no clicks.
  6. Soft vocal finish (ffmpeg): warmth boost, reduced 3-4 kHz harshness,
     de-essing, softened top end, gentle compression, a very small room,
     broadcast loudness (-16 LUFS).

Every setting has a good default - no repo variables are needed. Optional
overrides: KOKORO_VOICE, KOKORO_SPEED, KOKORO_SOFTNESS (0 = plain, 1 =
default, 1.5 = extra soft).
"""
import hashlib
import os
import re
import subprocess
import threading
from pathlib import Path

KOKORO_AVAILABLE = False
KOKORO_IMPORT_ERROR = ""
_pipeline = None
_lock = threading.Lock()  # scenes run in parallel threads; Kokoro is not thread-safe

SAMPLE_RATE = 24000

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
        _pipeline = KPipeline(lang_code="h", repo_id="hexgrad/Kokoro-82M")
    return _pipeline


def _split_cinematic_chunks(text: str) -> list:
    """Split at sentence/performance boundaries (commas stay inside a sentence
    so Kokoro keeps its natural intonation across the phrase)."""
    text = re.sub(r"\s+", " ", (text or "").strip())
    if not text:
        return []
    chunks, start = [], 0
    for match in re.finditer(r"[।!?]+|…+|—", text):
        piece = text[start:match.end()].strip()
        if piece:
            chunks.append(piece)
        start = match.end()
        while start < len(text) and text[start].isspace():
            start += 1
    tail = text[start:].strip()
    if tail:
        chunks.append(tail)
    return chunks or [text]


def _story_profile(chunk: str, index: int, total: int) -> tuple:
    """(speed multiplier, pause after this sentence in seconds)."""
    lowered = (chunk or "").lower()
    speed, pause = 1.0, None

    # Curiosity / question: a touch slower, then give the viewer a beat.
    if "?" in chunk or any(t in lowered for t in ("क्यों", "कैसे", "क्या", "रहस्य", "सच", "लेकिन", "मगर")):
        speed, pause = 0.95, 0.40
    # Revelation: slow the key sentence and hold a longer silence after it.
    if any(t in lowered for t in ("अचानक", "चौंक", "खुलासा", "सच्चाई", "असल में", "यही वजह",
                                   "रहस्य", "चमत्कार", "सत्य")):
        speed, pause = min(speed, 0.91), max(pause or 0.0, 0.48)
    # Action: slightly quicker for contrast.
    if any(t in lowered for t in ("भागा", "दौड़ा", "दौड़", "युद्ध", "गिरा", "उठा", "पहुंचा",
                                   "पहुंचे", "पहुँचे", "देखा", "मिला", "खुला")):
        speed = max(speed, 1.02)
    # Devotional close (जय श्री ..., हर हर महादेव, ॐ): slow and warm.
    if any(t in chunk for t in ("जय ", "हर हर", "ॐ", "नमः", "राधे")):
        speed = min(speed, 0.90)

    digest = hashlib.sha1(chunk.encode("utf-8")).digest()
    speed += (-0.015, -0.005, 0.0, 0.008)[digest[0] % 4]
    speed = max(0.86, min(1.05, speed))

    if pause is None:
        if chunk.endswith("…"):
            pause = 0.52
        elif chunk.endswith("—"):
            pause = 0.30
        elif chunk.endswith("?"):
            pause = 0.40
        elif chunk.endswith("!"):
            pause = 0.34
        else:  # । or no end mark
            pause = 0.30
    # The opening hook flows straight on; human narrators don't stop early.
    if index == 0 and total > 1:
        pause = min(pause, 0.32)
    pause += (-0.03, -0.01, 0.0, 0.02, 0.04)[digest[1] % 5]  # natural jitter
    return speed, max(0.22, min(0.60, pause))


def _synthesize_chunk(pipeline, text: str, voice: str, speed: float):
    pieces = []
    for result in pipeline(text, voice=voice, speed=speed):
        audio = result[2] if isinstance(result, tuple) and len(result) >= 3 else getattr(result, "audio", None)
        if audio is not None:
            pieces.append(audio.detach().cpu().numpy() if hasattr(audio, "detach") else np.asarray(audio))
    if not pieces:
        return None
    return np.concatenate(pieces).astype(np.float32)


def _trim_and_fade(audio, keep_ms: int = 35, fade_ms: int = 12):
    """Trim Kokoro's own leading/trailing silence (keep a little breath room)
    and fade the edges so joins never click."""
    if audio.size == 0:
        return audio
    threshold = max(0.004, float(np.max(np.abs(audio))) * 0.02)
    voiced = np.where(np.abs(audio) > threshold)[0]
    if voiced.size:
        keep = int(SAMPLE_RATE * keep_ms / 1000)
        audio = audio[max(0, voiced[0] - keep): min(audio.size, voiced[-1] + keep)]
    n = min(int(SAMPLE_RATE * fade_ms / 1000), audio.size // 2)
    if n > 0:
        ramp = np.linspace(0.0, 1.0, n, dtype=np.float32)
        audio = audio.copy()
        audio[:n] *= ramp
        audio[-n:] *= ramp[::-1]
    return audio


def _room_tone(seconds: float, seed: int):
    """Very quiet, soft noise (about -62 dBFS) instead of digital silence."""
    n = max(1, int(round(seconds * SAMPLE_RATE)))
    rng = np.random.default_rng(seed)
    noise = rng.standard_normal(n).astype(np.float32)
    noise = np.convolve(noise, np.ones(24, dtype=np.float32) / 24, mode="same")  # darker, softer
    return noise * (0.0008 / (float(np.std(noise)) or 1.0))


def _soft_voice_filter(softness: float) -> str:
    """ffmpeg chain for a warm, soft, natural narrator sound."""
    s = max(0.0, min(1.5, softness))
    if s == 0:
        return "highpass=f=70,loudnorm=I=-16:TP=-1.5:LRA=11"
    return ",".join([
        "highpass=f=75",
        f"lowshelf=f=180:g={2.0 * s:.2f}",                   # warmth / body
        f"equalizer=f=3400:t=q:w=1.3:g={-2.5 * s:.2f}",      # less harsh, less "digital"
        f"deesser=i={min(0.6, 0.35 * s):.2f}:m=0.5:f=0.5",   # softer s / sh
        f"highshelf=f=9000:g={-3.0 * s:.2f}",                # gentler top end
        "lowpass=f=12500",
        "acompressor=threshold=-20dB:ratio=2.2:attack=20:release=250:makeup=1.5",  # even, calm level
        f"aecho=0.85:0.9:28|47:{0.06 * s:.3f}|{0.035 * s:.3f}",  # tiny room, not an echo
        "loudnorm=I=-16:TP=-1.5:LRA=9",
    ])


def generate_kokoro_audio(text: str, output_path: str) -> bool:
    """Generate one scene's Hindi narration. Raises on failure (caller falls back to Edge)."""
    if not KOKORO_AVAILABLE:
        raise RuntimeError("Kokoro is not installed. " + KOKORO_IMPORT_ERROR)

    voice = os.getenv("KOKORO_VOICE", "").strip() or "hf_alpha"
    base_speed = float(os.getenv("KOKORO_SPEED", "").strip() or "0.92")
    softness = float(os.getenv("KOKORO_SOFTNESS", "").strip() or "1.0")

    chunks = _split_cinematic_chunks(text)
    if not chunks:
        return False

    parts = []
    with _lock:
        pipeline = _get_pipeline()
        for index, chunk in enumerate(chunks):
            profile_speed, pause = _story_profile(chunk, index, len(chunks))
            speed = max(0.82, min(1.06, base_speed * profile_speed))
            audio = _synthesize_chunk(pipeline, chunk, voice, speed)
            if audio is None:
                raise RuntimeError(f"Kokoro returned no audio for: {chunk[:40]}")
            parts.append(_trim_and_fade(audio))
            if index < len(chunks) - 1:
                parts.append(_room_tone(pause, seed=index + len(chunk)))

    # Short lead-in / tail so each scene starts and ends like a real take.
    audio = np.concatenate([_room_tone(0.12, 1)] + parts + [_room_tone(0.20, 2)])
    wav_path = output_path + ".kokoro.wav"
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    sf.write(wav_path, audio, SAMPLE_RATE)

    proc = subprocess.run(
        ["ffmpeg", "-y", "-i", wav_path, "-af", _soft_voice_filter(softness),
         "-ar", str(SAMPLE_RATE), "-ac", "1", "-c:a", "libmp3lame", "-q:a", "2", output_path],
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True,
    )
    try:
        os.remove(wav_path)
    except OSError:
        pass
    if proc.returncode != 0 or not os.path.exists(output_path):
        raise RuntimeError("ffmpeg voice finishing failed: " + (proc.stderr or "")[-300:])
    return True