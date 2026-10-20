"""Mood-aware background music with CC0 discovery and a verifiable local fallback.

No scraping, no Freesound commercial API dependency, no credentials required.
A remote Creative Commons Zero tag is *evidence*, not a copyright guarantee.
Every asset and its claimed license is written to an audit report for review.
"""
import hashlib
import html
import ipaddress
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from urllib.parse import urlparse

import requests

SEARCH_TERMS = {
    "mystery": ("mysterious ambient instrumental", "mysterious drone ambient"),
    "devotional": ("meditation flute instrumental", "relaxing meditation instrumental"),
    "emotional": ("gentle emotional instrumental", "peaceful ambient piano"),
    "revelation": ("cinematic inspirational instrumental", "dramatic cinematic instrumental"),
    "uplifting": ("uplifting acoustic instrumental", "positive peaceful instrumental"),
}
MELODY = {
    "mystery": (110.0, 164.81, 220.0),
    "devotional": (130.81, 196.00, 261.63),
    "emotional": (146.83, 220.00, 293.66),
    "revelation": (164.81, 246.94, 329.63),
    "uplifting": (174.61, 261.63, 349.23),
}
SUPPORTED_LICENSES = {"CC0-1.0", "Mixkit Stock Music Free License"}
LICENSE_CC0 = "https://creativecommons.org/publicdomain/zero/1.0/"
LICENSE_MIXKIT = "https://mixkit.co/license/modal/musicFree/"


def scene_mood(scene):
    director = scene.get("director") or {}
    cues = " ".join(str(x or "") for x in (
        scene.get("entertainmentBeat"), director.get("entertainmentBeat"),
        director.get("mood"), *(beat.get("mood") for beat in scene.get("visualBeats", []) if isinstance(beat, dict))
    )).casefold()
    for mood, needles in (
        ("revelation", ("revelation", "reveal", "climax", "epic", "divine power", "रहस्य खुल")),
        ("mystery", ("mystery", "suspense", "fear", "curiosity", "unknown", "रहस्य", "डर")),
        ("emotional", ("emotional", "sad", "compassion", "cry", "sorrow", "भक्ति भाव", "करुण")),
        ("uplifting", ("uplifting", "celebration", "happy", "festival", "joy", "victory", "उत्सव", "पर्व")),
    ):
        if any(term in cues for term in needles):
            return mood
    return "devotional"


def _source_url_ok(url):
    """Never fetch arbitrary local URLs or numeric IPs returned by an index."""
    if not isinstance(url, str) or len(url) > 1900:
        return False
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower().rstrip(".")
    if parsed.scheme != "https" or not host or "." not in host:
        return False
    if parsed.username or parsed.password or parsed.port not in (None, 443):
        return False
    if host in ("localhost", "localhost.localdomain") or host.endswith((".local", ".internal", ".localhost")):
        return False
    try:
        ipaddress.ip_address(host)
        return False
    except ValueError:
        return True


def _get_json(url, params):
    if not _source_url_ok(url):
        return {}
    try:
        r = requests.get(url, params=params, timeout=(5, 13), allow_redirects=False)
        if r.status_code == 200 and len(r.content) < 900_000:
            return r.json()
    except (requests.RequestException, ValueError) as exc:
        print(f"  🎵 Music search notice: {str(exc)[:150]}", flush=True)
    return {}


def _openverse_candidates(mood):
    """Only exact CC0 results. Public-domain *marks* are not enough to clear recordings."""
    query = SEARCH_TERMS[mood][0]
    payload = _get_json("https://api.openverse.org/v1/audio/", {
        "q": query, "license": "cc0", "page_size": 12,
    })
    for item in payload.get("results", []):
        if not isinstance(item, dict) or str(item.get("license", "")).lower() != "cc0":
            continue
        if item.get("mature") or not _source_url_ok(item.get("url")):
            continue
        link = item.get("foreign_landing_url") or item.get("detail_url") or ""
        if not _source_url_ok(link):
            continue
        yield {
            "title": str(item.get("title") or "Untitled audio")[:140],
            "creator": str(item.get("creator") or "Unknown")[:120],
            "source": "Openverse",
            "source_url": link,
            "download_url": item["url"],
            "license": "CC0-1.0",
            "license_url": LICENSE_CC0,
            "provider_record_id": str(item.get("id") or ""),
            "requires_review": True,
        }


def _strip_html(value):
    return html.unescape(re.sub(r"<[^>]+>", "", str(value or ""))).strip()


def _wikimedia_candidates(mood):
    """Direct Commons file URL plus the file's own CC0 license metadata."""
    query = SEARCH_TERMS[mood][1]
    data = _get_json("https://commons.wikimedia.org/w/api.php", {
        "action": "query", "generator": "search", "gsrsearch": "filetype:audio " + query,
        "gsrnamespace": 6, "gsrlimit": 12, "prop": "imageinfo",
        "iiprop": "url|extmetadata", "format": "json", "formatversion": "2",
    })
    for page in ((data.get("query") or {}).get("pages") or []):
        info = ((page.get("imageinfo") or [{}])[0])
        meta = info.get("extmetadata") or {}
        license_name = _strip_html((meta.get("LicenseShortName") or {}).get("value"))
        license_url = _strip_html((meta.get("LicenseUrl") or {}).get("value"))
        # Do not auto-clear broadly labeled 'public domain' / PD-mark tracks.
        if not re.fullmatch(r"CC0(?:[ -]?1\.0)?", license_name, flags=re.I):
            continue
        if not license_url.startswith(LICENSE_CC0):
            continue
        download = info.get("url")
        landing = info.get("descriptionurl")
        if not (_source_url_ok(download) and _source_url_ok(landing)):
            continue
        yield {
            "title": str(page.get("title") or "Wikimedia audio")[:140],
            "creator": _strip_html((meta.get("Artist") or {}).get("value"))[:120] or "Unknown",
            "source": "Wikimedia Commons",
            "source_url": landing,
            "download_url": download,
            "license": "CC0-1.0", "license_url": LICENSE_CC0,
            "provider_record_id": str(page.get("pageid") or ""),
            "requires_review": True,
        }


def _audio_seconds(path):
    try:
        p = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries",
             "stream=codec_type:format=duration", "-of", "json", str(path)],
            capture_output=True, text=True, timeout=12, check=True,
        )
        data = json.loads(p.stdout)
        if not data.get("streams"):
            return 0.0
        return float((data.get("format") or {}).get("duration") or 0.0)
    except (OSError, ValueError, subprocess.SubprocessError):
        return 0.0


def _download_limited(url, destination, max_bytes=14 * 1024 * 1024):
    """Bound media size/time. Refuse redirections rather than following unchecked hosts."""
    if not _source_url_ok(url):
        return False
    try:
        with requests.get(url, stream=True, timeout=(5, 22), allow_redirects=False) as r:
            if r.status_code != 200:
                return False
            size = int(r.headers.get("content-length") or 0)
            if size > max_bytes:
                return False
            count = 0
            with open(destination, "wb") as handle:
                for chunk in r.iter_content(chunk_size=65536):
                    count += len(chunk)
                    if count > max_bytes:
                        return False
                    handle.write(chunk)
            return count > 25_000
    except (OSError, ValueError, requests.RequestException):
        return False


def _transcode(source, dest):
    """Keep Remotion playback consistent across MP3, OGG, FLAC and WAV."""
    try:
        if _audio_seconds(source) < 17:
            return False
        p = subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-i", str(source), "-vn",
             "-t", "50", "-ar", "44100", "-ac", "2", "-c:a", "libmp3lame",
             "-b:a", "128k", str(dest)],
            capture_output=True, timeout=35,
        )
        return p.returncode == 0 and Path(dest).is_file() and _audio_seconds(dest) >= 16
    except (OSError, subprocess.SubprocessError):
        return False


def _approved_candidates(mood, directory):
    """Only manually reviewed cross-platform tracks with SHA256 identity."""
    root = Path(directory).resolve()
    manifest = root / "manifest.json"
    if not manifest.is_file():
        return
    try:
        entries = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    for entry in entries if isinstance(entries, list) else []:
        if not isinstance(entry, dict) or entry.get("approved") is not True:
            continue
        if entry.get("license") not in SUPPORTED_LICENSES:
            continue
        if mood not in entry.get("moods", []):
            continue
        if not {"youtube", "instagram"}.issubset(set(entry.get("platforms", []))):
            continue
        source = entry.get("source_url")
        expected_license = LICENSE_CC0 if entry["license"] == "CC0-1.0" else LICENSE_MIXKIT
        if not _source_url_ok(source) or entry.get("license_url") != expected_license:
            continue
        name = entry.get("file")
        sha = entry.get("sha256")
        if not isinstance(name, str) or Path(name).name != name:
            continue
        path = (root / name).resolve()
        if root not in path.parents or path.suffix.lower() not in (".mp3", ".wav", ".ogg", ".flac"):
            continue
        if not isinstance(sha, str) or not re.fullmatch(r"[a-fA-F0-9]{64}", sha):
            continue
        try:
            if not path.is_file() or path.stat().st_size > 14 * 1024 * 1024:
                continue
            if hashlib.sha256(path.read_bytes()).hexdigest().lower() != sha.lower():
                continue
        except OSError:
            continue
        yield {
            "title": str(entry.get("title") or path.stem)[:140],
            "creator": str(entry.get("creator") or "Unknown")[:120],
            "source": "Approved local library", "source_url": source,
            "license": entry["license"], "license_url": expected_license,
            "requires_review": False, "_local_path": str(path),
        }


def _synthetic_pad(mood, dest):
    """Original synthesized harmonies, no third-party samples or licenses."""
    notes = MELODY[mood]
    inputs = []
    for note in notes:
        inputs += ["-f", "lavfi", "-i", f"sine=frequency={note}:sample_rate=44100:duration=38"]
    graph = (
        "[0:a]volume=0.14[a];[1:a]volume=0.09[b];[2:a]volume=0.055[c];"
        "[a][b][c]amix=inputs=3:duration=longest:normalize=0,"
        "lowpass=f=1250,afade=t=in:st=0:d=1.4,afade=t=out:st=36:d=2,"
        "aformat=channel_layouts=stereo[out]"
    )
    try:
        result = subprocess.run(
            ["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", graph,
             "-map", "[out]", "-c:a", "libmp3lame", "-b:a", "128k", str(dest)],
            capture_output=True, timeout=45,
        )
        return result.returncode == 0 and _audio_seconds(dest) >= 35
    except (OSError, subprocess.SubprocessError):
        return False


def _select_track(mood, target, approved_dir, remote_enabled, budget):
    """Try CC0 catalogs, approved local tracks, then a self-generated bed."""
    # Prefer creator-approved YouTube/Instagram tracks with SHA256 evidence.
    # A remote CC0 label alone cannot prove the actual recording rights.
    for candidate in _approved_candidates(mood, approved_dir):
        if _transcode(candidate["_local_path"], target):
            return {k: v for k, v in candidate.items() if k != "_local_path"}
    if remote_enabled and budget["searches"] < 6:
        for supplier in (_openverse_candidates, _wikimedia_candidates):
            if budget["searches"] >= 6:
                break
            budget["searches"] += 1
            candidates = supplier(mood)
            for i, candidate in enumerate(candidates):
                if i >= 3 or budget["downloads"] >= 9:
                    break
                budget["downloads"] += 1
                fd, temp = tempfile.mkstemp(prefix="music_source_", suffix=".audio")
                os.close(fd)
                try:
                    if _download_limited(candidate["download_url"], temp) and _transcode(temp, target):
                        return {k: v for k, v in candidate.items() if k != "download_url"}
                finally:
                    Path(temp).unlink(missing_ok=True)
    if not _synthetic_pad(mood, target):
        raise RuntimeError(f"No usable and licensed music fallback for {mood}")
    return {
        "title": f"Original generated {mood} ambient pad",
        "creator": "Generated in this workflow from synthesized waveforms",
        "source": "Local FFmpeg original", "source_url": "",
        "license": "in-house-generated", "license_url": "",
        "requires_review": False,
    }


def attach_music(long_scenes, shorts_scenes,
                 music_dir="public/audio/music",
                 report_path="out/music_license_report.json",
                 approved_dir=None, remote_enabled=None):
    """Mutate existing enriched scenes in place, attaching licensed mood-track assets."""
    destination = Path(music_dir)
    destination.mkdir(parents=True, exist_ok=True)
    report_file = Path(report_path)
    report_file.parent.mkdir(parents=True, exist_ok=True)
    approved = approved_dir or os.getenv("APPROVED_MUSIC_DIR") or "public/audio/music/approved"
    # Use verified local or self-synthesized music automatically; discovery
    # of third-party recordings requires explicit opt-in.
    remote = (os.getenv("MUSIC_REMOTE_DISCOVERY_ENABLED", "false").lower() == "true") if remote_enabled is None else remote_enabled
    all_scenes = list(long_scenes) + list(shorts_scenes)
    moods = list(dict.fromkeys(scene_mood(scene) for scene in all_scenes))
    tracks = {}
    budget = {"searches": 0, "downloads": 0}
    for mood in moods:
        filename = f"bgm_{mood}.mp3"
        path = destination / filename
        license_info = _select_track(mood, path, approved, remote, budget)
        license_info.update({
            "mood": mood,
            "file": f"music/{filename}",
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "duration_seconds": round(_audio_seconds(path), 2),
            "cross_platform": True,
        })
        tracks[mood] = license_info
        print(f"  🎵 {mood}: {license_info['source']} — {license_info['title']}", flush=True)
    for scene in all_scenes:
        mood = scene_mood(scene)
        scene["musicFile"] = tracks[mood]["file"]
        scene["musicMood"] = mood
    report = {
        "status": "review_required" if any(t["requires_review"] for t in tracks.values()) else "ready",
        "rights_notice": (
            "Locally synthesized or explicitly approved tracks; check final mix for Content ID conflicts."
            if not any(t["requires_review"] for t in tracks.values())
            else "Remote CC0 status is source-declared; verify recording rights before publishing."
        ),
        "destinations": ["youtube", "instagram"],
        "tracks": list(tracks.values()),
        "scene_music": {
            "long": [{"scene": s.get("scene_number"), "mood": s.get("musicMood"), "file": s.get("musicFile")} for s in long_scenes],
            "shorts": [{"scene": s.get("scene_number"), "mood": s.get("musicMood"), "file": s.get("musicFile")} for s in shorts_scenes],
        },
        "search_attempts": budget["searches"],
        "download_attempts": budget["downloads"],
    }
    report_file.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report
