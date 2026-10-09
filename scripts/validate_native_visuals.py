#!/usr/bin/env python3
"""Validate native stock/AI scene assets before Remotion renders.

This replaces the optional Google Flow import entirely. This guard verifies
that generate_assets.py produced real, readable local media for BOTH formats.
No external video generation or network calls are required here.
"""
import json
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MEDIA_ROOT = ROOT / "public" / "images"
FILES = [("Long", ROOT / "public" / "props.json"), ("Shorts", ROOT / "public" / "props_shorts.json")]


def verify_shot(kind, scene_num, shot):
    if not isinstance(shot, dict):
        raise ValueError(f"{kind} scene {scene_num}: invalid shot object")
    filename = shot.get("file")
    mediatype = shot.get("type")
    if mediatype not in ("image", "video") or not isinstance(filename, str) or not filename:
        raise ValueError(f"{kind} scene {scene_num}: missing or unsupported media: {shot!r}")
    path = (MEDIA_ROOT / filename).resolve()
    if not path.is_relative_to(MEDIA_ROOT.resolve()):
        raise ValueError(f"{kind} scene {scene_num}: unsafe path")
    if not path.is_file() or path.stat().st_size < 100:
        raise ValueError(f"{kind} scene {scene_num}: missing or empty media {filename}")
    with open(path, "rb") as stream:
        head = stream.read(16)
    if mediatype == "image":
        if not (head.startswith(b"\xff\xd8\xff") or head.startswith(b"\x89PNG\r\n\x1a\n") or head[:4] == b"RIFF" and head[8:12] == b"WEBP"):
            raise ValueError(f"{kind} scene {scene_num}: not a valid image signature {filename}")
    else:
        if len(head) < 12 or head[4:8] != b"ftyp":
            raise ValueError(f"{kind} scene {scene_num}: not an MP4 container {filename}")
        try:
            probe = subprocess.run(
                ["ffprobe", "-v", "error", "-select_streams", "v:0",
                 "-show_entries", "stream=width,height:format=duration",
                 "-of", "json", str(path)],
                check=True, capture_output=True, text=True, timeout=30,
            )
            meta = json.loads(probe.stdout)
            video = (meta.get("streams") or [{}])[0]
            if int(video.get("width") or 0) < 240 or int(video.get("height") or 0) < 240:
                raise ValueError("video resolution too low")
            if float(meta.get("format", {}).get("duration") or 0) <= 0:
                raise ValueError("zero video duration")
        except (OSError, subprocess.CalledProcessError, ValueError, json.JSONDecodeError) as exc:
            raise ValueError(f"{kind} scene {scene_num}: unreadable MP4 {filename}: {exc}") from exc


from visual_evidence import (
    detect_instructional_category,
    validate_demonstration_evidence,
)


def _requires_precise_action_footage(titles):
    """Compatibility helper used by older tests."""
    return detect_instructional_category(titles) is not None


def validate_tutorial_visual_evidence(titles, report, *, long_scenes=None,
                                      shorts_scenes=None, manifest_path=None,
                                      media_root=MEDIA_ROOT):
    """Use actual file-hash-pinned review, NEVER stock search title/score alone."""
    validate_demonstration_evidence(
        titles,
        long_scenes or [],
        shorts_scenes or [],
        report,
        manifest_path or ROOT / "public" / "verified_action_clips.json",
        media_root,
    )


def main():
    counts = {"images": 0, "videos": 0}
    for kind, propsfile in FILES:
        if not propsfile.is_file():
            raise ValueError(f"{kind}: props file not generated: {propsfile}")
        data = json.loads(propsfile.read_text(encoding="utf-8"))
        scenes = data.get("scenes")
        if not isinstance(scenes, list) or not scenes:
            raise ValueError(f"{kind}: empty scene array")
        expected = 6 if kind == "Long" else 5
        if len(scenes) != expected:
            raise ValueError(f"{kind}: expected {expected} scenes, found {len(scenes)}")
        for i, scene in enumerate(scenes, 1):
            shots = scene.get("shots")
            if not isinstance(shots, list) or not shots:
                raise ValueError(f"{kind} scene {i}: no visuals. Refusing black scene.")
            for shot in shots:
                verify_shot(kind, i, shot)
                counts["videos" if shot["type"] == "video" else "images"] += 1
            print(f"Native visuals OK: {kind} scene {i}, {len(shots)} shot(s)", flush=True)
    if counts["images"] + counts["videos"] == 0:
        raise ValueError("Native visuals: no shots at all")
    props = [json.loads(filename.read_text(encoding="utf-8")) for _, filename in FILES]
    titles = [data.get("title", "") for data in props]
    reportfile = ROOT / "out" / "visual_search_report.json"
    report = json.loads(reportfile.read_text(encoding="utf-8")) if reportfile.is_file() else None
    validate_tutorial_visual_evidence(
        titles, report,
        long_scenes=props[0]["scenes"],
        shorts_scenes=props[1]["scenes"],
        manifest_path=os.environ.get("ACTION_DEMONSTRATION_MANIFEST")
                      or ROOT / "public" / "verified_action_clips.json",
        media_root=MEDIA_ROOT,
    )
    print(f"SUCCESS: native media validated; {counts['videos']} stock/local clips, {counts['images']} AI/stock images", flush=True)


if __name__ == "__main__":
    main()
