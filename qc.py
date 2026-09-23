"""Automated production/media QC for generated devotional videos.

This gate checks structure, dimensions, duration, audio presence/loudness,
black/frozen-frame anomalies, generated asset integrity, and caption timing.
Warnings are preserved in out/qc_report.json for debugging; severe media
failures stop publication.
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path


def probe(path):
    r = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries",
            "format=duration:stream=codec_type,codec_name,width,height,sample_rate,duration",
            "-of", "json", path,
        ],
        capture_output=True, text=True,
    )
    if r.returncode:
        return {"ok": False, "error": r.stderr.strip()}
    try:
        return {"ok": True, **json.loads(r.stdout)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _run_filter(path, vf):
    r = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", path, "-vf", vf, "-an", "-f", "null", "-"],
        capture_output=True, text=True,
    )
    return r.stderr


def _max_metric(stderr, pattern):
    values = []
    for match in re.finditer(pattern, stderr):
        try:
            values.append(float(match.group(1)))
        except (TypeError, ValueError):
            pass
    return max(values) if values else 0.0


def visual_anomalies(path):
    if not os.path.exists(path):
        return {"blackMaxSeconds": 0, "freezeMaxSeconds": 0, "warnings": []}

    black_log = _run_filter(path, "blackdetect=d=1.5:pix_th=0.98")
    freeze_log = _run_filter(path, "freezedetect=n=-60dB:d=2.0")

    black_max = _max_metric(black_log, r"black_duration:([0-9.]+)")
    freeze_max = _max_metric(freeze_log, r"freeze_duration:([0-9.]+)")

    warnings = []
    if black_max >= 1.5:
        warnings.append(f"black_segment_{black_max:.2f}s")
    if freeze_max >= 2.0:
        warnings.append(f"freeze_segment_{freeze_max:.2f}s")

    return {
        "blackMaxSeconds": round(black_max, 3),
        "freezeMaxSeconds": round(freeze_max, 3),
        "warnings": warnings,
    }


def audio_loudness(path):
    r = subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-i", path,
            "-af", "ebur128=framelog=verbose",
            "-f", "null", "-",
        ],
        capture_output=True, text=True,
    )
    text = r.stderr
    integrated = [float(x) for x in re.findall(r"I:\s*(-?\d+(?:\.\d+)?)\s+LUFS", text)]
    true_peak = [float(x) for x in re.findall(r"Peak:\s*(-?\d+(?:\.\d+)?)\s+dBFS", text)]
    return {
        "integratedLUFS": round(integrated[-1], 2) if integrated else None,
        "truePeakDbfs": round(max(true_peak), 2) if true_peak else None,
    }


def check_caption_timing(props_path):
    if not os.path.exists(props_path):
        return {"ok": True, "warnings": ["props_file_missing"]}
    try:
        props = json.loads(Path(props_path).read_text(encoding="utf-8"))
    except Exception as exc:
        return {"ok": False, "warnings": [f"props_parse_failed:{exc}"]}

    warnings = []
    scenes = props.get("scenes") or []
    for index, scene in enumerate(scenes, 1):
        duration = float(scene.get("durationInSeconds") or 0)
        words = scene.get("words") or []
        if not words:
            warnings.append(f"scene_{index}_missing_word_timings")
            continue
        last_end = 0.0
        for cue in words:
            start = float(cue.get("start", 0) or 0)
            end = float(cue.get("end", 0) or 0)
            if start < 0 or end <= start:
                warnings.append(f"scene_{index}_invalid_word_timing")
                break
            if start + 0.15 < last_end:
                warnings.append(f"scene_{index}_word_timings_overlap")
                break
            if end > duration + 0.75:
                warnings.append(f"scene_{index}_word_timing_exceeds_duration")
                break
            last_end = end

    return {"ok": True, "warnings": sorted(set(warnings))}


def check(path, kind):
    if not os.path.exists(path):
        return {"path": path, "ok": False, "error": "missing"}

    p = probe(path)
    p["path"] = path
    streams = p.get("streams", [])
    duration = float(p.get("format", {}).get("duration", 0) or 0)
    p["duration"] = round(duration, 3)

    if kind == "video":
        video_streams = [s for s in streams if s.get("codec_type") == "video"]
        audio_streams = [s for s in streams if s.get("codec_type") == "audio"]
        p["hasVideo"] = bool(video_streams)
        p["hasAudio"] = bool(audio_streams)
        if not video_streams:
            p.update(ok=False, error="missing video stream")
            return p

        width = int(video_streams[0].get("width", 0) or 0)
        height = int(video_streams[0].get("height", 0) or 0)
        ratio = width / height if height else 0
        p.update(width=width, height=height, aspectRatio=round(ratio, 4))

        is_long = path.endswith("final_video.mp4")
        is_shorts = path.endswith("final_video_shorts.mp4")
        min_width = 1280 if is_long else 720
        min_height = 720 if is_long else 1280

        if is_long:
            p["durationTargetOk"] = 150 <= duration <= 210
            p["aspectTargetOk"] = abs(ratio - 16 / 9) < 0.03
        elif is_shorts:
            p["durationTargetOk"] = 20 <= duration <= 60
            p["aspectTargetOk"] = abs(ratio - 9 / 16) < 0.03
        else:
            p["durationTargetOk"] = duration > 0
            p["aspectTargetOk"] = True

        p["resolutionTargetOk"] = width >= min_width and height >= min_height
        p["audioTargetOk"] = bool(audio_streams)

        p["ok"] = (
            duration > 0
            and p["hasVideo"]
            and p["audioTargetOk"]
            and p["durationTargetOk"]
            and p["aspectTargetOk"]
            and p["resolutionTargetOk"]
        )

        if p["ok"]:
            p["visualAnalysis"] = visual_anomalies(path)
            # Black/frozen segments are debugging signals. Only unusually long
            # segments block publication; short intentional fades/transitions
            # remain visible in the report as warnings.
            if p["visualAnalysis"]["blackMaxSeconds"] >= 4.0:
                p["ok"] = False
                p["error"] = "severe black-frame segment detected"
            if p["visualAnalysis"]["freezeMaxSeconds"] >= 5.0:
                p["ok"] = False
                p["error"] = "severe frozen-frame segment detected"
            p["audioAnalysis"] = audio_loudness(path)
            lufs = p["audioAnalysis"].get("integratedLUFS")
            if lufs is not None and not (-18.5 <= lufs <= -13.0):
                p.setdefault("warnings", []).append(
                    f"integrated_loudness_outside_target:{lufs:.2f}LUFS"
                )
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

    # Check the final narration/effect assets and generated props as well.
    audio_files = []
    if os.path.isdir("public/audio"):
        for root, _, files in os.walk("public/audio"):
            audio_files.extend(
                os.path.join(root, name)
                for name in files if name.lower().endswith(".mp3")
            )
    results += [check(x, "audio") for x in audio_files[:500]]

    caption_checks = [
        check_caption_timing("public/props.json"),
        check_caption_timing("public/props_shorts.json"),
    ]

    failed = [r for r in results if not r["ok"]]
    warnings = []
    for r in results:
        warnings.extend(r.get("warnings", []))
        warnings.extend(r.get("visualAnalysis", {}).get("warnings", []))
    for c in caption_checks:
        warnings.extend(c.get("warnings", []))

    report = {
        "ok": not failed,
        "checked": len(results),
        "failed": failed,
        "warnings": sorted(set(warnings)),
        "captionChecks": caption_checks,
        "results": results,
    }
    os.makedirs("out", exist_ok=True)
    with open("out/qc_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # A compact contact sheet is useful when debugging a failed render without
    # downloading the entire video. Keep it as a CI artifact.
    for video_path, sheet_name in (
        ("out/final_video.mp4", "out/qc_contact_long.jpg"),
        ("out/final_video_shorts.mp4", "out/qc_contact_shorts.jpg"),
    ):
        if os.path.exists(video_path):
            subprocess.run(
                [
                    "ffmpeg", "-y", "-ss", "0", "-i", video_path,
                    "-vf", "fps=1/15,scale=480:-1,tile=4x4",
                    "-frames:v", "1", sheet_name,
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

    print(json.dumps(report, ensure_ascii=False, indent=2))
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
