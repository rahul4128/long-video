#!/usr/bin/env python3
"""Verify an Instagram-specific full-bleed Reel + cover before release."""
import argparse
import json
from pathlib import Path
import subprocess


def probe(path):
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "format=duration:stream=codec_type,width,height", "-of", "json", str(path)],
        check=True, capture_output=True, text=True, timeout=20)
    return json.loads(result.stdout)


def validate(video, cover, state):
    status = json.loads(Path(state).read_text(encoding="utf-8"))
    if status.get("status") != "ready_for_manual_review" or status.get("reasons"):
        raise ValueError("Instagram packaging requires editorial review")
    meta = probe(video)
    stream = next((s for s in meta.get("streams", []) if s.get("codec_type") == "video"), {})
    if (stream.get("width"), stream.get("height")) != (1080, 1920):
        raise ValueError("Instagram must use actual 1080x1920 portrait frames, never letterbox")
    if not any(s.get("codec_type") == "audio" for s in meta.get("streams", [])):
        raise ValueError("Instagram Reel has no soundtrack")
    seconds = float((meta.get("format") or {}).get("duration") or 0)
    if not 20 <= seconds <= 40.5:
        raise ValueError("Instagram Reel duration outside 20-40 second editorial window")
    meta2 = probe(cover)
    photo = next((s for s in meta2.get("streams", []) if s.get("codec_type") == "video"), {})
    if (photo.get("width"), photo.get("height")) != (1080, 1920):
        raise ValueError("Instagram cover must be 1080x1920 portrait")
    if Path(cover).stat().st_size < 12000:
        raise ValueError("Instagram cover cannot be empty")
    return {"status": "passed", "video": str(video), "cover": str(cover),
            "width": 1080, "height": 1920, "duration_seconds": round(seconds, 2)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", default="out/final_video_instagram.mp4")
    parser.add_argument("--cover", default="out/instagram_cover.jpg")
    parser.add_argument("--status", default="out/instagram_status.json")
    args = parser.parse_args()
    report = validate(args.video, args.cover, args.status)
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
