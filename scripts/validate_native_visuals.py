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


def _requires_precise_action_footage(titles):
    """Physical movement lessons need a verified demonstration, not generic B-roll.

    This does not ban Garba or dance content. Cultural stories, history, festivals
    and celebration footage continue to work normally. It applies when a video's
    central promise is to TEACH named dance steps or choreography.
    """
    text = " ".join(str(x or "") for x in titles).casefold()
    dance = any(x in text for x in (
        "गरबा", "डांडिया", "डांस", "नृत्य", "garba", "dandiya", "dance", "dancing",
    ))
    instruction = bool(re.search(
        r"स्टेप|कदम.*(?:सीख|सिख)|(?:सीख|सिख).*कदम|"
        r"\\bstep(?:s)?\\b|\\bfootwork\\b|\\bchoreograph|"
        r"(?:सीख|सिख).*नाच|(?:सीख|सिख).*डांस",
        text, flags=re.IGNORECASE,
    ))
    return dance and instruction


def validate_tutorial_visual_evidence(titles, report):
    """Reject unverified choreography demonstrations before public/private delivery.

    A stock search for a generic person, hands or dancer does not prove the
    movement shown matches a narrated Garba step. This checks only available
    source/query evidence; even a PASS still requires a human video review.
    """
    if not _requires_precise_action_footage(titles):
        return
    if not isinstance(report, dict):
        raise ValueError("Instructional dance topic needs visual search evidence")
    for kind in ("long", "shorts"):
        scenes = report.get(kind) or []
        videos = [
            shot for scene in scenes for shot in (scene.get("shots") or [])
            if shot.get("type") == "video"
        ]
        specific = [
            shot for shot in videos
            if any(token in str(shot.get("queryUsed") or "").casefold() for token in (
                "garba", "dandiya", "गरबा", "डांडिया",
                "footwork", "dance steps", "choreography",
            ))
            and float(shot.get("selectionScore") or 0) >= 0.65
        ]
        if len(specific) < 2:
            raise ValueError(
                f"{kind}: title promises precise dance steps but no confirmed "
                f"technique-relevant visual examples ({len(specific)} specific clips; "
                f"{len(videos)} total). Generic person/hands/dancer footage or AI "
                "stills cannot verify a real choreography lesson. Choose a "
                "non-instructional culture/celebration story or provide real "
                "reviewable demonstrations."
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
    titles = []
    for _, filename in FILES:
        titles.append(json.loads(filename.read_text(encoding="utf-8")).get("title", ""))
    reportfile = ROOT / "out" / "visual_search_report.json"
    report = json.loads(reportfile.read_text(encoding="utf-8")) if reportfile.is_file() else None
    validate_tutorial_visual_evidence(titles, report)
    print(f"SUCCESS: native media validated; {counts['videos']} stock/local clips, {counts['images']} AI/stock images", flush=True)


if __name__ == "__main__":
    main()
