"""Automated media QC for generated devotional videos.

Everything is DYNAMIC - no repo variables, nothing depends on voice speed.

1. Render check: each video must match the length of its own scenes in
   public/props.json / props_shorts.json (sum of durationInSeconds = real
   narration length + scene padding, exactly what Remotion renders),
   +/- 10 % (min 3 s). Catches cut-off, padded or frozen renders.
2. Story-length check: counted in narration WORDS, not seconds, so a slower
   (Natasha/IndicF5) or faster (Edge) voice never changes the verdict.
     long  : fail < 250 or > 650 words, warn outside 360-520 (target 400-460)
     Short : fail < 15  or > 200 words, warn outside 40-120
   A runaway 7-minute script fails here; a tight 147 s story passes.
3. Final videos must have an audio track; thumbnails need real dimensions.
"""
import json, os, subprocess, sys

LONG_PATH = "out/final_video.mp4"
SHORTS_PATH = "out/final_video_shorts.mp4"


def probe(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                        "format=duration:stream=codec_type,codec_name,width,height,sample_rate",
                        "-of", "json", path], capture_output=True, text=True)
    if r.returncode:
        return {"ok": False, "error": r.stderr.strip()}
    try:
        return {"ok": True, **json.loads(r.stdout)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def expected_seconds(props_path):
    """Sum of scene durations from the props file Remotion rendered from."""
    try:
        with open(props_path, encoding="utf-8") as f:
            scenes = json.load(f).get("scenes", [])
        # Remotion uses max(1 s, duration) per scene (30 frames at 30 fps).
        return sum(max(1.0, float(s.get("durationInSeconds") or 5)) for s in scenes) or None
    except Exception:
        return None


# path -> (props file, label, word fail min, word fail max, word warn min, word warn max)
DURATION_RULES = {
    LONG_PATH: ("public/props.json", "long video", 250, 650, 360, 520),
    SHORTS_PATH: ("public/props_shorts.json", "Short", 15, 200, 40, 120),
}


def narration_words(props_path):
    try:
        with open(props_path, encoding="utf-8") as f:
            scenes = json.load(f).get("scenes", [])
        return sum(len(str(s.get("narration_chunk") or "").split()) for s in scenes) or None
    except Exception:
        return None


def check_duration(p, path, duration):
    props, label, w_fail_min, w_fail_max, w_warn_min, w_warn_max = DURATION_RULES[path]
    ok = True
    errors = []

    expected = expected_seconds(props)
    p["expectedDuration"] = round(expected, 2) if expected else None
    if expected:
        tolerance = max(3.0, expected * 0.10)
        if abs(duration - expected) > tolerance:
            ok = False
            errors.append(f"{label} is {duration:.1f}s but its scenes add up to {expected:.1f}s "
                          f"(allowed +/-{tolerance:.1f}s) - render/timing problem")
    if duration < 5:
        ok = False
        errors.append(f"{label} is only {duration:.1f}s - empty render")

    words = narration_words(props)
    p["narrationWords"] = words
    if words is not None:
        if not (w_fail_min <= words <= w_fail_max):
            ok = False
            errors.append(f"{label} narration has {words} words, allowed {w_fail_min}-{w_fail_max} - script length problem")
        elif not (w_warn_min <= words <= w_warn_max):
            p["durationWarning"] = (f"{label} narration has {words} words, outside {w_warn_min}-{w_warn_max} "
                                    f"target ({duration:.0f}s) - not blocking")
            print(f"::warning::{p['durationWarning']}")
    if errors:
        p["durationError"] = "; ".join(errors)
    return ok


def check(path, kind):
    if not os.path.exists(path):
        return {"path": path, "ok": False, "error": "missing"}
    p = probe(path)
    p["path"] = path
    streams = p.get("streams", [])
    duration = float(p.get("format", {}).get("duration", 0) or 0)
    p["duration"] = duration
    has_kind = any(s.get("codec_type") == kind for s in streams)

    # Still images (thumbnails) have no media duration in ffprobe; require
    # real dimensions instead. Audio/video must have a positive duration.
    if kind == "image":
        has_dimensions = any(
            s.get("codec_type") == "video"
            and int(s.get("width", 0) or 0) > 0
            and int(s.get("height", 0) or 0) > 0
            for s in streams
        )
        p["ok"] = p["ok"] and has_dimensions
        return p

    p["ok"] = p["ok"] and duration > 0 and has_kind
    if kind == "video" and path in DURATION_RULES:
        # A final video must also carry an audio track (narration).
        if not any(s.get("codec_type") == "audio" for s in streams):
            p["ok"] = False
            p["error"] = "no audio track"
        p["ok"] = check_duration(p, path, duration) and p["ok"]
    return p


def main():
    targets = [(LONG_PATH, "video"), (SHORTS_PATH, "video"),
               ("out/thumbnail.jpg", "image"), ("out/thumbnail_shorts_final.jpg", "image")]
    results = [check(path, kind) for path, kind in targets]
    audio_files = []
    if os.path.isdir("public/audio"):
        for root, _, files in os.walk("public/audio"):
            audio_files.extend(os.path.join(root, n) for n in files if n.lower().endswith(".mp3"))
    results += [check(x, "audio") for x in audio_files[:500]]
    failed = [r for r in results if not r["ok"]]
    report = {"ok": not failed, "checked": len(results), "failed": failed, "results": results}
    os.makedirs("out", exist_ok=True)
    with open("out/qc_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()