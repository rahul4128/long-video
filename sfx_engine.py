"""Resilient sound-effect resolver for the video generation pipeline.

Uses Freesound when configured, then creates a small local FFmpeg fallback.
The fallback keeps CI deterministic and prevents a missing SFX provider from
breaking the whole render.
"""
import os
import subprocess
import tempfile
from pathlib import Path
import requests

FREESOUND_API_KEY = os.environ.get("FREESOUND_API_KEY", "").strip()

_EFFECT_QUERIES = {
    "transition_whoosh": "whoosh transition",
    "temple_bell": "temple bell",
    "bell": "temple bell",
    "shankh": "conch shell",
    "conch": "conch shell",
    "thunder": "thunder",
    "wind": "wind ambience",
    "fire": "fire crackle",
}

def _download_freesound(effect_name: str, output_path: str) -> bool:
    if not FREESOUND_API_KEY:
        return False
    query = _EFFECT_QUERIES.get(effect_name, effect_name.replace("_", " "))
    try:
        r = requests.get(
            "https://freesound.org/apiv2/search/text/",
            params={
                "query": query,
                "token": FREESOUND_API_KEY,
                "fields": "id,name,previews,duration",
                "page_size": 10,
            },
            timeout=15,
        )
        if r.status_code != 200:
            return False
        results = r.json().get("results", [])
        for item in results:
            preview = (item.get("previews") or {}).get("preview-hq-mp3") or (item.get("previews") or {}).get("preview-lq-mp3")
            if not preview:
                continue
            audio = requests.get(preview, timeout=30)
            if audio.status_code == 200 and len(audio.content) > 5000:
                Path(output_path).parent.mkdir(parents=True, exist_ok=True)
                Path(output_path).write_bytes(audio.content)
                return True
    except Exception as exc:
        print(f"Freesound SFX notice ({effect_name}): {exc}", flush=True)
    return False

def _ffmpeg_fallback(effect_name: str, output_path: str) -> bool:
    """Generate a short synthetic cue when no downloadable SFX is available."""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    if effect_name in ("transition_whoosh", "whoosh"):
        # Filtered noise with a short frequency sweep gives a usable transition cue.
        lavfi = (
            "anoisesrc=color=white:duration=0.65:amplitude=0.28,"
            "highpass=f=700,lowpass=f=9000,"
            "afade=t=in:st=0:d=0.08,afade=t=out:st=0.42:d=0.23"
        )
    elif effect_name in ("temple_bell", "bell"):
        lavfi = (
            "sine=frequency=540:duration=1.8,"
            "aecho=0.8:0.88:650:0.35,"
            "afade=t=in:st=0:d=0.01,afade=t=out:st=0.45:d=1.35"
        )
    elif effect_name in ("shankh", "conch"):
        lavfi = (
            "sine=frequency=220:duration=2.0,"
            "tremolo=f=3:d=0.7,"
            "afade=t=in:st=0:d=0.25,afade=t=out:st=1.1:d=0.8"
        )
    elif effect_name == "thunder":
        lavfi = (
            "anoisesrc=color=brown:duration=2.2:amplitude=0.35,"
            "lowpass=f=180,afade=t=in:st=0:d=0.08,afade=t=out:st=0.8:d=1.3"
        )
    else:
        lavfi = (
            "anoisesrc=color=pink:duration=1.0:amplitude=0.18,"
            "lowpass=f=5000,afade=t=in:st=0:d=0.05,afade=t=out:st=0.55:d=0.4"
        )

    try:
        result = subprocess.run(
            [
                "ffmpeg", "-y", "-f", "lavfi", "-i", lavfi,
                "-ar", "44100", "-ac", "2",
                "-af", "loudnorm=I=-20:TP=-2:LRA=7",
                "-c:a", "libmp3lame", "-q:a", "5", output_path,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30,
        )
        if result.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
            return True
        print(f"Synthetic SFX failed ({effect_name}): {result.stderr[-500:]}", flush=True)
    except Exception as exc:
        print(f"Synthetic SFX notice ({effect_name}): {exc}", flush=True)
    return False

def resolve_sound_effect_audio(effect_name: str, output_path: str) -> bool:
    """Resolve an effect without ever making SFX a hard pipeline dependency."""
    if not effect_name or effect_name == "none":
        return False
    if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
        return True

    if _download_freesound(effect_name, output_path):
        print(f"🔊 SFX ready from Freesound: {effect_name}", flush=True)
        return True

    ok = _ffmpeg_fallback(effect_name, output_path)
    if ok:
        print(f"🔊 SFX ready from local fallback: {effect_name}", flush=True)
    return ok
