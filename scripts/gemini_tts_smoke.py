#!/usr/bin/env python3
"""Single short Gemini Hindi narration test; opt-in, no Make or YouTube upload.

Uses at most one paid/free-tier API request, produces an MP3 review artifact.
"""
from pathlib import Path
import subprocess
import json

from scripts.gemini_tts import generate_gemini_audio

SAMPLE = (
    "नवरात्रि की हर आराधना में एक सुंदर संदेश छिपा है। "
    "माँ दुर्गा हमें सिखाती हैं कि सच्ची शक्ति हमारे साहस, दया और विश्वास में है।"
)


def main():
    dest = Path("out/gemini_tts_smoke.mp3")
    generate_gemini_audio(SAMPLE, str(dest))
    result = subprocess.run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "json", str(dest),
    ], capture_output=True, text=True, check=True, timeout=10)
    duration = float(json.loads(result.stdout)["format"]["duration"])
    if duration < 3.0 or dest.stat().st_size < 1500:
        raise RuntimeError("Gemini narration smoke test produced too little audio")
    print(f"Gemini TTS smoke SUCCESS: {dest}, {duration:.1f}s, {dest.stat().st_size} bytes")


if __name__ == "__main__":
    main()
