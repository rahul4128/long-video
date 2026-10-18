"""Gemini 3.8 Hindi text-to-speech through the official Interactions REST API.

No GPU, SDK, or Make modules required. Returns an MP3 for the existing
narration-led Remotion/shorts pipeline. Requests use the existing Gemini
free-tier API key when configured, and raise a safe, concise error otherwise.

Official schema: https://ai.google.dev/gemini-api/docs/speech-generation
"""
import base64
import binascii
from io import BytesIO
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import time
import wave

import requests

ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/interactions"
MODELS = {"gemini-3.8-flash-tts", "gemini-3.8-flash-lite-tts"}
DEFAULT_STYLE = (
    "Speak in natural Hindi with warm, authentic, emotionally engaging Indian "
    "devotional storytelling. Gently vary expression for wonder, significance "
    "and the reveal, and use natural pauses. Avoid announcer theatrics. "
    "Recite the supplied Hindi transcript verbatim; do not add any words."
)

# Serialize all Gemini TTS requests (including cooldowns) in this process.
# TTS scenes are otherwise synthesized concurrently and can burst the free tier.
_TTS_API_LOCK = threading.Lock()
_LAST_ATTEMPT_AT = 0.0
_API_ATTEMPTS = 0
_DAILY_QUOTA_EXHAUSTED = False


def _env_int(name, default, low, high):
    try:
        return max(low, min(high, int(os.getenv(name, str(default)))))
    except (ValueError, TypeError):
        return default


def _retry_after(response):
    """Read a numeric Retry-After or a Google RetryInfo retryDelay, capped."""
    headers = getattr(response, "headers", {}) or {}
    try:
        seconds = float(headers.get("Retry-After", ""))
        if seconds >= 0:
            return min(90.0, seconds)
    except (TypeError, ValueError):
        pass
    try:
        details = response.json().get("error", {}).get("details", [])
    except (ValueError, TypeError, AttributeError):
        return None
    for item in details if isinstance(details, list) else []:
        if not isinstance(item, dict):
            continue
        delay = item.get("retryDelay", "")
        if isinstance(delay, str) and delay.endswith("s"):
            try:
                return min(90.0, max(0.0, float(delay[:-1])))
            except ValueError:
                continue
    return None


def _is_daily_quota(response):
    """Detect non-retryable daily/project exhaustion without leaking API text."""
    try:
        err = response.json().get("error", {})
    except (ValueError, TypeError, AttributeError):
        return False
    if not isinstance(err, dict):
        return False
    text = str(err.get("message", "")).lower()
    for detail in err.get("details", []) if isinstance(err.get("details", []), list) else []:
        if isinstance(detail, dict):
            text += " " + str(detail.get("violations", ""))[:2500].lower()
    return any(key in text for key in (
        "requestsperday", "perday", "per day", "daily quota", "per_day",
    ))


def _post_with_cooldown(transport, payload, api_key, timeout):
    """Respect Retry-After and cool down on transient 429/503, never daily quotas."""
    global _LAST_ATTEMPT_AT, _API_ATTEMPTS, _DAILY_QUOTA_EXHAUSTED
    max_retries = _env_int("GEMINI_TTS_MAX_RETRIES", 2, 0, 3)
    max_attempts = _env_int("GEMINI_TTS_MAX_API_ATTEMPTS", 18, 1, 50)
    min_gap = _env_int("GEMINI_TTS_MIN_GAP_SECONDS", 6, 0, 30)
    base_delay = _env_int("GEMINI_TTS_COOLDOWN_SECONDS", 20, 5, 90)
    with _TTS_API_LOCK:
        if _DAILY_QUOTA_EXHAUSTED:
            raise GeminiTTSError("Gemini TTS daily quota exhausted", "quota_daily_exhausted")
        for attempt in range(max_retries + 1):
            if _API_ATTEMPTS >= max_attempts:
                raise GeminiTTSError("Gemini TTS per-run API request cap reached", "request_budget_exhausted")
            gap = min_gap - (time.monotonic() - _LAST_ATTEMPT_AT) if _LAST_ATTEMPT_AT else 0.0
            if gap > 0:
                time.sleep(gap)
            _LAST_ATTEMPT_AT = time.monotonic()
            _API_ATTEMPTS += 1
            try:
                response = transport.post(
                    ENDPOINT,
                    headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
                    json=payload, timeout=(12, timeout),
                )
            except requests.RequestException as exc:
                raise GeminiTTSError(
                    f"Gemini TTS network issue: {type(exc).__name__}", "network_error"
                ) from exc
            status = response.status_code
            if status == 429 and _is_daily_quota(response):
                _DAILY_QUOTA_EXHAUSTED = True
                raise GeminiTTSError("Gemini TTS daily project quota exhausted", "quota_daily_exhausted")
            if status in (429, 503) and attempt < max_retries and _API_ATTEMPTS < max_attempts:
                provider_delay = _retry_after(response)
                backoff = min(90.0, base_delay * (2 ** attempt))
                wait = max(backoff, provider_delay or 0.0)
                print(
                    f"Gemini TTS HTTP {status}: cooling down {wait:.0f}s "
                    f"(retry {attempt + 1}/{max_retries})",
                    flush=True,
                )
                time.sleep(wait)
                continue
            if status >= 400:
                code = ("quota_exceeded" if status == 429 else f"http_{status}")
                raise GeminiTTSError(f"Gemini TTS HTTP {status}", code)
            return response
        raise GeminiTTSError("Gemini TTS retry limit reached", "retry_exhausted")


class GeminiTTSError(RuntimeError):
    def __init__(self, message, code="gemini_tts_error"):
        self.code = code
        super().__init__(str(message)[:260])


def _audio_from_response(payload):
    if not isinstance(payload, dict):
        raise GeminiTTSError("Gemini TTS response is not an object", "invalid_response")
    for step in payload.get("steps", []):
        if not isinstance(step, dict) or step.get("type") != "model_output":
            continue
        for part in step.get("content", []):
            if not isinstance(part, dict) or part.get("type") != "audio":
                continue
            data = part.get("data")
            if not isinstance(data, str) or not data:
                continue
            try:
                decoded = base64.b64decode(data, validate=True)
            except (binascii.Error, ValueError) as exc:
                raise GeminiTTSError("Gemini TTS audio is invalid base64", "invalid_audio") from exc
            if len(decoded) > 18_000_000:
                raise GeminiTTSError("Gemini TTS audio exceeds safe size limit", "invalid_audio")
            return decoded
    raise GeminiTTSError("Gemini TTS response has no audio output", "empty_audio")


def _verify_wav(raw):
    if not raw.startswith(b"RIFF") or raw[8:12] != b"WAVE":
        raise GeminiTTSError("Gemini TTS returned non-WAV audio", "invalid_audio")
    try:
        with wave.open(BytesIO(raw), "rb") as reader:
            duration = reader.getnframes() / max(1, reader.getframerate())
            if not (0.8 <= duration <= 240):
                raise GeminiTTSError("Gemini TTS audio duration is invalid", "invalid_audio")
            if reader.getnchannels() not in (1, 2):
                raise GeminiTTSError("Gemini TTS channel count is invalid", "invalid_audio")
    except (EOFError, wave.Error, OSError) as exc:
        raise GeminiTTSError("Gemini TTS returned unreadable WAV", "invalid_audio") from exc


def generate_gemini_audio(
    text, output_path, *, api_key=None, model=None, voice=None, style=None,
    session=None, timeout=110,
):
    """Synthesize one complete Hindi narration scene into an MP3, or raise.

    The model receives the EXACT transcript separately from speech_metadata,
    so it will not try to read the delivery instructions aloud. API failures
    never leave a partial MP3 and never leak the secret in logs.
    """
    api_key = (api_key if api_key is not None else
               os.getenv("GEMINI_API_KEY", "")).strip()
    if not api_key:
        raise GeminiTTSError("GEMINI_API_KEY secret missing in GitHub Actions", "missing_key")
    model = model or os.getenv("GEMINI_TTS_MODEL", "gemini-3.8-flash-tts")
    if model not in MODELS:
        raise GeminiTTSError("Unsupported Gemini TTS model", "invalid_model")
    speech = " ".join(str(text or "").split())
    if not speech or len(speech) > 12500:
        raise GeminiTTSError("Gemini TTS transcript is empty or oversized", "invalid_text")
    voice = (voice or os.getenv("GEMINI_TTS_VOICE") or "Kore").strip()
    style = (style or os.getenv("GEMINI_TTS_STYLE") or DEFAULT_STYLE).strip()[:600]
    payload = {
        "model": model,
        "input": [{"type": "user_input", "content": [{
            "type": "text", "text": speech,
            "annotations": [{"type": "speech_metadata", "style": style}],
        }]}],
        "response_format": {"type": "audio"},
        "generation_config": {"speech_config": [{"voice": voice}]},
    }
    transport = session or requests
    # Transient rate limits get bounded retries; the rest go to Kokoro/Edge.
    # Never print the API's free-text errors (may contain user content).
    response = _post_with_cooldown(transport, payload, api_key, timeout)
    try:
        audio = _audio_from_response(response.json())
    except (ValueError, AttributeError) as exc:
        raise GeminiTTSError("Gemini TTS returned invalid JSON", "invalid_response") from exc
    _verify_wav(audio)
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    wav_path = None
    mp3_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", dir=target.parent, delete=False) as f:
            wav_path = Path(f.name)
            f.write(audio)
        with tempfile.NamedTemporaryFile(suffix=".mp3", dir=target.parent, delete=False) as f:
            mp3_path = Path(f.name)
        proc = subprocess.run([
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(wav_path), "-ac", "1", "-ar", "24000",
            "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
            "-c:a", "libmp3lame", "-q:a", "4", str(mp3_path)
        ], capture_output=True, timeout=65, check=False)
        if proc.returncode != 0 or not mp3_path.is_file() or mp3_path.stat().st_size < 1500:
            raise GeminiTTSError("Gemini TTS audio conversion failed", "conversion_failed")
        os.replace(mp3_path, target)
        return True
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise GeminiTTSError(f"Gemini TTS file/FFmpeg issue: {type(exc).__name__}", "conversion_failed") from exc
    finally:
        for file in (wav_path, mp3_path):
            if file and file.exists():
                file.unlink()
