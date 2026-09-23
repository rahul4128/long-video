"""Automated media QC for generated devotional videos."""
import json
import os
import subprocess
import sys


def probe(path):
    r = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries",
            "format=duration:stream=codec_type,codec_name,width,height,sample_rate,duration",
            "-of", "json", path,
        ],
        capture_output=True,
        text=True,
    )
    if r.returncode:
        return {"ok": False, "error": r.stderr.strip()}
    try:
        return {"ok": True, **json.loads(r.stdout)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def check(path, kind):
    if not os.path.exists(path):
        return {"path": path, "ok": False, "error": "missing"}

    p = probe(path)
    p["path"] = path
    streams = p.get("streams", [])
    duration = float(p.get("format", {}).get("duration", 0) or 0)
    p["duration"] = duration

    if kind == "video":
        video_streams = [s for s in streams if s.get("codec_type") == "video"]
        audio_streams = [s for s in streams if s.get("codec_type") == "audio"]
        p["hasVideo"] = bool(video_streams)
        p["hasAudio"] = bool(audio_streams)

        if not video_streams:
            p["ok"] = False
            p["error"] = "missing video stream"
            return p

        width = int(video_streams[0].get("width", 0) or 0)
        height = int(video_streams[0].get("height", 0) or 0)
        p["width"] = width
        p["height"] = height
        p["aspectRatio"] = round(width / height, 4) if height else 0

        if path.endswith("final_video.mp4"):
            p["durationTargetOk"] = 150 <= duration <= 210
            p["aspectTargetOk"] = abs((width / height if height else 0) - (16 / 9)) < 0.03
            if not p["durationTargetOk"]:
                p["durationTargetError"] = "long video outside 150–210 second target"
            if not p["aspectTargetOk"]:
                p["aspectTargetError"] = "long video is not approximately 16:9"
        elif path.endswith("final_video_shorts.mp4"):
            p["durationTargetOk"] = 20 <= duration <= 60
            p["aspectTargetOk"] = abs((width / height if height else 0) - (9 / 16)) < 0.03
            if not p["durationTargetOk"]:
                p["durationTargetError"] = "shorts video outside 20–60 second target"
            if not p["aspectTargetOk"]:
                p["aspectTargetError"] = "shorts video is not approximately 9:16"

        # A rendered video without narration/music is a production failure.
        p["audioTargetOk"] = bool(audio_streams)
        p["ok"] = (
            p.get("ok", True)
            and duration > 0
            and p["hasVideo"]
            and p["audioTargetOk"]
            and p.get("durationTargetOk", True)
            and p.get("aspectTargetOk", True)
        )
        if not p["audioTargetOk"]:
            p["audioTargetError"] = "video has no audio stream"
        return p

    if kind == "image":
        has_dimensions = any(
            s.get("codec_type") == "video"
            and int(s.get("width", 0) or 0) > 0
            and int(s.get("height", 0) or 0) > 0
            for s in streams
        )
        p["ok"] = p["ok"] and has_dimensions
        return p

    has_kind = any(s.get("codec_type") == kind for s in streams)
    p["ok"] = p["ok"] and duration > 0 and has_kind
    return p


def main():
    targets = [
        ("out/final_video.mp4", "video"),
        ("out/final_video_shorts.mp4", "video"),
        ("out/thumbnail.jpg", "image"),
        ("out/thumbnail_shorts_final.jpg", "image"),
    ]
    results = [check(path, kind) for path, kind in targets]

    audio_files = []
    if os.path.isdir("public/audio"):
        for root, _, files in os.walk("public/audio"):
            audio_files.extend(
                os.path.join(root, name)
                for name in files
                if name.lower().endswith(".mp3")
            )
    results += [check(x, "audio") for x in audio_files[:500]]

    failed = [r for r in results if not r["ok"]]
    report = {
        "ok": not failed,
        "checked": len(results),
        "failed": failed,
        "results": results,
    }
    os.makedirs("out", exist_ok=True)
    with open("out/qc_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
