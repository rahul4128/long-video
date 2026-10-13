#!/usr/bin/env python3
"""Master the *final* Remotion audio mix, not only the Kokoro voice stems.

FFmpeg-only. Video stream is copied losslessly; soundtrack is normalized to
-16 integrated LUFS and <= -1.5 dBTP. Nothing is sent to a third-party API.
A bounded post-process QC measures the resulting *actual* encoded track.
"""
import argparse
import json
import math
import os
from pathlib import Path
import re
import subprocess


TARGET_LUFS = -16.0
TARGET_TRUE_PEAK = -1.5
LOUDNORM = "loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json"


def _run(args, timeout=180):
    return subprocess.run(args, capture_output=True, text=True,
                          timeout=timeout, check=True)


def _probe(path):
    result = _run(["ffprobe", "-v", "error", "-show_entries",
                   "format=duration:stream=codec_type,codec_name,width,height",
                   "-of", "json", str(path)], timeout=15)
    parsed = json.loads(result.stdout)
    streams = parsed.get("streams") or []
    if not any(stream.get("codec_type") == "audio" for stream in streams):
        raise ValueError("Final render has no audio stream")
    if not any(stream.get("codec_type") == "video" for stream in streams):
        raise ValueError("Final render has no video stream")
    duration = float((parsed.get("format") or {}).get("duration") or 0)
    if duration < 2 or not math.isfinite(duration):
        raise ValueError("Rendered video is too short or invalid")
    return {"duration": round(duration, 3),
            "video": next(s for s in streams if s["codec_type"] == "video"),
            "audio": next(s for s in streams if s["codec_type"] == "audio")}


def _loudness(path):
    result = _run(["ffmpeg", "-hide_banner", "-nostdin", "-v", "info",
                   "-i", str(path), "-vn", "-af", LOUDNORM,
                   "-f", "null", "-"], timeout=150)
    matches = re.findall(r'\{\s*"input_i"\s*:.*?\}', result.stderr, flags=re.S)
    if not matches:
        raise ValueError("FFmpeg did not return loudness analysis")
    raw = json.loads(matches[-1])
    def read(key):
        try:
            number = float(raw[key])
            return round(number, 2) if math.isfinite(number) else None
        except (TypeError, ValueError, KeyError):
            return None
    return {
        "integrated_lufs": read("input_i"),
        "true_peak_dbtp": read("input_tp"),
        "loudness_range_lu": read("input_lra"),
    }


def _silences(path):
    result = _run(["ffmpeg", "-hide_banner", "-nostdin", "-v", "info",
                   "-i", str(path), "-vn",
                   "-af", "silencedetect=noise=-42dB:d=3.5",
                   "-f", "null", "-"], timeout=140)
    starts = re.findall(r"silence_start:\s*([0-9.]+)", result.stderr)
    ends = re.findall(r"silence_end:\s*([0-9.]+)", result.stderr)
    paired = []
    for start, end in zip(starts, ends):
        try:
            a, b = float(start), float(end)
            if b > a:
                paired.append({"start": round(a, 2), "end": round(b, 2),
                               "duration": round(b - a, 2)})
        except ValueError:
            pass
    return paired


def master(input_path, output_path, report_path):
    src, dest = Path(input_path), Path(output_path)
    report_file = Path(report_path)
    if not src.is_file() or src.resolve() == dest.resolve():
        raise ValueError("Expected distinct existing input and mastered output")
    dest.parent.mkdir(parents=True, exist_ok=True)
    report_file.parent.mkdir(parents=True, exist_ok=True)
    before_probe = _probe(src)
    before = _loudness(src)
    if before["integrated_lufs"] is None or before["integrated_lufs"] < -65:
        raise ValueError("Input final mix is silent; refusing artificial normalization")
    if before["true_peak_dbtp"] is None:
        raise ValueError("Cannot measure final-mix true peak")
    tmp = dest.with_name(dest.stem + ".partial.mp4")
    try:
        # Video copy avoids *any* visual re-encoding or aspect-ratio changes.
        _run(["ffmpeg", "-y", "-hide_banner", "-nostdin", "-v", "error",
              "-i", str(src), "-map", "0:v:0", "-map", "0:a:0",
              "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
              "-ar", "48000", "-af", LOUDNORM.replace(":print_format=json", ""),
              "-movflags", "+faststart", str(tmp)], timeout=180)
        after_probe = _probe(tmp)
        if abs(after_probe["duration"] - before_probe["duration"]) > 0.65:
            raise ValueError("Mastering unexpectedly changed video duration")
        if (after_probe["video"].get("width") != before_probe["video"].get("width") or
            after_probe["video"].get("height") != before_probe["video"].get("height")):
            raise ValueError("Mastering changed video dimensions")
        after = _loudness(tmp)
        level, peak = after["integrated_lufs"], after["true_peak_dbtp"]
        if level is None or peak is None:
            raise ValueError("Final mix loudness could not be measured")
        # Allow tolerance for a lossy AAC re-encode and loudness range.
        if not -19.0 <= level <= -13.0:
            raise ValueError(f"Final mix outside acceptable loudness: {level} LUFS")
        if peak > -0.75:
            raise ValueError(f"Final mix true peak is too high: {peak} dBTP")
        silences = _silences(tmp)
        mid_silences = [s for s in silences
                        if s["start"] > 6 and s["end"] < after_probe["duration"] - 5]
        if any(s["duration"] > 11 for s in mid_silences):
            raise ValueError("Unexpected long silence in the middle of the video")
        report = {
            "status": "passed", "target_lufs": TARGET_LUFS,
            "target_true_peak_dbtp": TARGET_TRUE_PEAK,
            "processing": "FFmpeg loudnorm with AAC audio only; H264/video stream copied",
            "source": src.name, "output": dest.name,
            "before": before, "after": after,
            "duration": after_probe["duration"],
            "silence_intervals_over_3_5_seconds": silences,
            "warnings": ["extended_internal_silence_review"] if mid_silences else [],
        }
        report_file.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, dest)
        return report
    finally:
        tmp.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--report", required=True)
    args = parser.parse_args()
    result = master(args.input, args.output, args.report)
    print(f"🎚️ Final mix mastered: {result['after']['integrated_lufs']} LUFS, "
          f"true peak {result['after']['true_peak_dbtp']} dBTP", flush=True)


if __name__ == "__main__":
    main()
