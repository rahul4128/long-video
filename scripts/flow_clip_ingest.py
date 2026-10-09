#!/usr/bin/env python3
"""Optional Google Flow MP4 importer, preserving the existing Remotion render path.

Input from workflow_dispatch FLOW_CLIPS_JSON or repository_dispatch payload.flow_clips:
{"long":[{"scene":1,"url":"https://github.com/rahul4128/long-video/releases/download/flow-2026-10-09/hook-long.mp4"}],
 "shorts":[{"scene":1,"url":"https://github.com/rahul4128/long-video/releases/download/flow-2026-10-09/hook-shorts.mp4"}]}
Downloads only assets in this repository's GitHub Releases, removes clip audio,
normalizes the orientation/codec, then replaces the FIRST visual shot of the
selected scene. Existing narration, scenes and fallback shot lists remain intact.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path

RELEASE_PREFIX = "/rahul4128/long-video/releases/download/"
MAX_BYTES = 100 * 1024 * 1024
MAX_PER_FORMAT = 5
RENDER_FORMATS = {
    "long": ("public/props.json", (1280, 720)),
    "shorts": ("public/props_shorts.json", (720, 1280)),
}


def manifest_from_environment():
    override = os.environ.get("FLOW_CLIPS_JSON", "").strip()
    if override:
        return json.loads(override)
    raw = os.environ.get("DISPATCH_PAYLOAD", "{}").strip() or "{}"
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("Dispatch payload must be a JSON object")
    return payload.get("flow_clips") or payload.get("flowClips") or {}


def validate_release_url(url):
    if not isinstance(url, str) or not url:
        raise ValueError("Clip URL is required")
    parsed = urllib.parse.urlsplit(url)
    parts = parsed.path
    if (parsed.scheme != "https" or parsed.netloc != "github.com"
            or not parts.startswith(RELEASE_PREFIX) or parsed.query or parsed.fragment):
        raise ValueError("Only HTTPS Release asset URLs from rahul4128/long-video are permitted")
    if len(parts.split("/")) < 7 or any(c in parts for c in ["..", "%2f", "%2F"]):
        raise ValueError("Malformed GitHub Release asset URL")
    if not parts.lower().endswith(".mp4"):
        raise ValueError("The release asset must be an MP4")
    return url


def download_release(url, destination):
    validate_release_url(url)
    request = urllib.request.Request(url, headers={"User-Agent": "FlowClipImporter/1.0"})
    with urllib.request.urlopen(request, timeout=50) as response, open(destination, "wb") as out:
        length = 0
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            length += len(chunk)
            if length > MAX_BYTES:
                raise ValueError("Video exceeds 100 MB limit")
            out.write(chunk)
    if length < 8192:
        raise ValueError("Video download is unexpectedly small")


def probe_clip(path):
    data = json.loads(subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries",
        "format=duration:stream=codec_type,width,height",
        "-of", "json", str(path)
    ], text=True, timeout=30))
    duration = float(data.get("format", {}).get("duration") or 0)
    streams = [s for s in data.get("streams", []) if s.get("codec_type") == "video"]
    if not streams or duration < 2.0 or duration > 45.0:
        raise ValueError("A Flow clip needs a video stream and 2–45 seconds duration")
    if int(streams[0].get("width") or 0) < 240 or int(streams[0].get("height") or 0) < 240:
        raise ValueError("Flow clip resolution is too small")
    return duration


def normalize_clip(source, output, size, max_seconds=12):
    w, h = size
    filter_graph = (
        f"scale={w}:{h}:force_original_aspect_ratio=increase,"
        f"crop={w}:{h},setsar=1,fps=30"
    )
    subprocess.run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(source), "-t", str(max_seconds), "-an",
        "-vf", filter_graph, "-c:v", "libx264", "-preset", "veryfast",
        "-crf", "25", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        str(output),
    ], check=True, timeout=150)
    probe_clip(output)


def install_into_props(props_path, scene_number, filename):
    props = json.loads(Path(props_path).read_text(encoding="utf-8"))
    scenes = props.get("scenes", [])
    scene = next((s for s in scenes if s.get("scene_number") == scene_number), None)
    if scene is None:
        raise ValueError(f"Scene {scene_number} does not exist in {props_path}")
    old_shots = scene.get("shots") or []
    if old_shots and not isinstance(old_shots, list):
        raise ValueError("Invalid shot list")
    # Maintain the shot count and relative durations. The Flow clip becomes
    # the opening shot only; remaining stock/image shots and audio are unchanged.
    new_shots = [{"type": "video", "file": filename, "transition": "crossfade"}]
    new_shots.extend(old_shots[1:])
    scene["shots"] = new_shots
    scene["imageFileName"] = filename  # legacy single-shot fallback
    Path(props_path).write_text(
        json.dumps(props, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def run(manifest, strict=False):
    if not isinstance(manifest, dict):
        raise ValueError("Flow clip manifest must be an object")
    report = {"applied": [], "failed": [], "skipped": []}
    for fmt, (props_path, size) in RENDER_FORMATS.items():
        entries = manifest.get(fmt, [])
        if not isinstance(entries, list) or len(entries) > MAX_PER_FORMAT:
            raise ValueError(f"{fmt} must be a list of at most {MAX_PER_FORMAT} clips")
        seen = set()
        for item in entries:
            try:
                if not isinstance(item, dict):
                    raise ValueError("Each entry must be an object")
                scene_no = item.get("scene")
                if type(scene_no) is not int or scene_no < 1 or scene_no in seen:
                    raise ValueError("scene must be a unique positive integer")
                seen.add(scene_no)
                url = validate_release_url(item.get("url"))
                # Verify scene exists BEFORE downloading a potentially large MP4.
                props = json.loads(Path(props_path).read_text(encoding="utf-8"))
                if not any(s.get("scene_number") == scene_no for s in props.get("scenes", [])):
                    raise ValueError(f"Scene {scene_no} not found in {props_path}")
                Path("public/images").mkdir(parents=True, exist_ok=True)
                filename = f"flow_{fmt}_scene_{scene_no}.mp4"
                output = Path("public/images") / filename
                with tempfile.TemporaryDirectory(prefix="flow_clip_") as tmp:
                    source = Path(tmp) / "source.mp4"
                    download_release(url, source)
                    probe_clip(source)
                    normalize_clip(source, output, size)
                install_into_props(props_path, scene_no, filename)
                report["applied"].append({"format": fmt, "scene": scene_no, "file": filename})
                print(f"FLOW OK: {fmt} scene {scene_no} = {filename}", flush=True)
            except Exception as exc:
                msg = f"{fmt} scene {item.get('scene') if isinstance(item, dict) else '?'}: {exc}"
                report["failed"].append(msg)
                print(f"::warning::FLOW import skipped: {msg}", flush=True)
                if strict:
                    break
        if strict and report["failed"]:
            break
    Path("out").mkdir(parents=True, exist_ok=True)
    Path("out/flow_clip_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    if strict and report["failed"]:
        raise RuntimeError("Strict Flow clip import failed: " + "; ".join(report["failed"]))
    return report


if __name__ == "__main__":
    try:
        manifest = manifest_from_environment()
        strict = os.getenv("FLOW_CLIPS_STRICT", "false").lower() == "true"
        if not manifest:
            print("FLOW: No clips supplied; original generator visuals remain unchanged.")
        else:
            result = run(manifest, strict=strict)
            print(f"FLOW: {len(result['applied'])} clips applied, {len(result['failed'])} failed.")
    except Exception as exc:
        print(f"::error::FLOW manifest/import error: {exc}", file=sys.stderr)
        sys.exit(1)
