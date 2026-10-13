#!/usr/bin/env python3
"""Post-artifact gate: both mastered final mixes must pass source-level QC."""
import json
import math
from pathlib import Path
from master_final_audio import _probe, _loudness

ROOT = Path(__file__).resolve().parents[1]


def inspect(root=ROOT):
    for kind, filename, report_name in (
        ("long", "final_video.mp4", "audio_master_long.json"),
        ("shorts", "final_video_shorts.mp4", "audio_master_shorts.json"),
    ):
        video = root / "out" / filename
        reportfile = root / "out" / report_name
        if not video.is_file() or not reportfile.is_file():
            raise ValueError(f"{kind}: missing mastered file or audio audit")
        report = json.loads(reportfile.read_text(encoding="utf-8"))
        if report.get("status") != "passed" or report.get("output") != filename:
            raise ValueError(f"{kind}: missing successful audio master record")
        actual = _probe(video)
        if abs(actual["duration"] - float(report.get("duration", 0))) > .6:
            raise ValueError(f"{kind}: video duration differs from audio audit")
        final = _loudness(video)
        lufs, peak = final.get("integrated_lufs"), final.get("true_peak_dbtp")
        if (lufs is None or peak is None or not math.isfinite(lufs)
            or not math.isfinite(peak) or lufs < -19.0 or lufs > -13.0
            or peak > -0.75):
            raise ValueError(f"{kind}: mastered audio outside quality window ({lufs} LUFS, {peak} dBTP)")
        print(f"🔊 {kind}: verified {lufs} LUFS; TP {peak} dBTP; "
              f"duration {actual['duration']}s", flush=True)
    return True


if __name__ == "__main__":
    inspect()
