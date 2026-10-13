#!/usr/bin/env python3
"""Fail renders that are missing a scored soundtrack or verifiable rights record."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
AUDIO = ROOT / "public" / "audio"
REPORT = ROOT / "out" / "music_license_report.json"
PROPS = (ROOT / "public" / "props.json", ROOT / "public" / "props_shorts.json")
LICENSES = {"CC0-1.0", "Mixkit Stock Music Free License", "in-house-generated"}


def inspect():
    if not REPORT.is_file():
        raise ValueError("Music license report is missing")
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    tracks = report.get("tracks")
    if not isinstance(tracks, list) or not tracks:
        raise ValueError("No scored music or license provenance")
    by_file = {}
    for track in tracks:
        if track.get("license") not in LICENSES:
            raise ValueError("Unsupported or unidentified music rights")
        filename = track.get("file")
        if not isinstance(filename, str) or not filename.startswith("music/"):
            raise ValueError("Unsafe music file path")
        media = (AUDIO / filename).resolve()
        if AUDIO.resolve() not in media.parents or not media.is_file():
            raise ValueError(f"Missing music: {filename}")
        if media.suffix != ".mp3" or media.stat().st_size < 5000:
            raise ValueError(f"Invalid music file: {filename}")
        digest = hashlib.sha256(media.read_bytes()).hexdigest()
        if digest != track.get("sha256"):
            raise ValueError(f"Music file hash changed: {filename}")
        if track["license"] != "in-house-generated":
            if not str(track.get("source_url", "")).startswith("https://"):
                raise ValueError(f"Music license missing original source: {filename}")
            if not str(track.get("license_url", "")).startswith("https://"):
                raise ValueError(f"Music license URL missing: {filename}")
        try:
            probe = subprocess.run(
                ["ffprobe", "-v", "error", "-select_streams", "a:0",
                 "-show_entries", "stream=codec_type:format=duration", "-of", "json",
                 str(media)], check=True, capture_output=True, text=True, timeout=12,
            )
            result = json.loads(probe.stdout)
            if not result.get("streams") or float(result["format"]["duration"]) < 16:
                raise ValueError("Missing or too-short audio")
        except (OSError, KeyError, subprocess.SubprocessError, ValueError) as exc:
            raise ValueError(f"Unplayable music file: {filename}") from exc
        by_file[filename] = track
    for prop_path in PROPS:
        props = json.loads(prop_path.read_text(encoding="utf-8"))
        for scene in props.get("scenes", []):
            music = scene.get("musicFile")
            if music not in by_file:
                raise ValueError(f"{prop_path.name} scene {scene.get('scene_number')}: no licensed music")
            if scene.get("musicMood") != by_file[music].get("mood"):
                raise ValueError("Scene soundtrack/mood mismatch")
    print(f"🎼 Music QC passed: {len(tracks)} validated tracks, SHA256 and source evidence.", flush=True)
    if report.get("status") == "review_required":
        print("::warning::Source CC0 declarations require human recording-rights and Content ID review before public release.", flush=True)
    return report


if __name__ == "__main__":
    inspect()
