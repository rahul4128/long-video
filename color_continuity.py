"""CPU-bounded exposure, color and shot-continuity analysis.

Sample one tiny frame per UNIQUE source asset via FFmpeg, preserve source bytes.
Only mild, scene-safe corrections are attached to props for Remotion. Bright
night-temple symbolism and faithfully rendered deity colors must not be flattened.
"""
import concurrent.futures
import json
import math
import os
from pathlib import Path
from statistics import median
import subprocess

SIZE = 36
PIXELS = SIZE * SIZE
MIN_EXPOSURE = 0.13
MAX_EXPOSURE = 0.82
MAX_SOURCES = 150
BUDGET_SECONDS = 13


def _clamp(x, lo, hi):
    return min(hi, max(lo, x))


def _sample(source, is_video=False):
    source = Path(source)
    args = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-threads", "1"]
    if is_video:
        args += ["-ss", "0.22"]
    args += ["-i", str(source), "-an", "-sn", "-frames:v", "1",
             "-vf", f"scale={SIZE}:{SIZE},format=rgb24", "-pix_fmt", "rgb24",
             "-f", "rawvideo", "-"]
    try:
        result = subprocess.run(args, capture_output=True, timeout=BUDGET_SECONDS)
        raw = result.stdout
        if result.returncode != 0 or len(raw) != PIXELS * 3:
            return None
        red = green = blue = luminance = chroma = 0.0
        for i in range(0, len(raw), 3):
            r, g, b = raw[i], raw[i + 1], raw[i + 2]
            red += r
            green += g
            blue += b
            luminance += 0.2126 * r + 0.7152 * g + 0.0722 * b
            chroma += max(r, g, b) - min(r, g, b)
        denom = PIXELS * 255.0
        return {
            "luma": round(luminance / denom, 4),
            "chroma": round(chroma / denom, 4),
            "rgb": [round(red / denom, 4), round(green / denom, 4),
                    round(blue / denom, 4)],
        }
    except (OSError, subprocess.SubprocessError):
        return None


def _resolve_file(shot, root):
    name = shot.get("file")
    if not isinstance(name, str) or not name:
        return None
    base = Path(root).resolve()
    path = (base / name).resolve()
    if not path.is_relative_to(base) or not path.is_file():
        return None
    return path


def inspect_shots(long_scenes, shorts_scenes, media_root="public/images",
                  report_path="out/color_continuity_report.json", enabled=None):
    enabled = (os.getenv("COLOR_MATCH_ENABLED", "true").lower() == "true") if enabled is None else bool(enabled)
    entries = []
    for kind, scenes in (("long", long_scenes), ("shorts", shorts_scenes)):
        for scene in scenes:
            for index, shot in enumerate(scene.get("shots") or []):
                source = _resolve_file(shot, media_root)
                entries.append((kind, scene.get("scene_number"), index, shot, source))
    report = {
        "version": 1, "enabled": enabled, "method": "one_tiny_frame_per_unique_media",
        "limitations": "CSS exposure/saturation only; white-balance drift is flagged, not destructively auto-fixed; artistic low-key scenes are protected",
        "shots": len(entries), "samples": 0, "warnings": [], "formats": {},
    }
    if enabled:
        unique = {}
        for _, _, _, shot, source in entries:
            if source is not None:
                unique[str(source)] = (str(source), shot.get("type") == "video")
        if len(unique) > MAX_SOURCES:
            report["warnings"].append({"code": "sample_limit", "count": len(unique)})
        ordered = list(unique.values())[:MAX_SOURCES]
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            sampled = list(pool.map(lambda task: _sample(*task), ordered))
        stats = {path: data for (path, _), data in zip(ordered, sampled) if data is not None}
        report["samples"] = len(stats)
        for kind in ("long", "shorts"):
            subset = [(scene, index, shot, stats.get(str(source))) for fmt, scene, index, shot, source
                      in entries if fmt == kind]
            healthy = [x[3] for x in subset if x[3] and MIN_EXPOSURE <= x[3]["luma"] <= MAX_EXPOSURE]
            target_luma = _clamp(median(x["luma"] for x in healthy), .32, .66) if healthy else .48
            target_chroma = median(x["chroma"] for x in healthy) if healthy else .22
            target_balance = median(x["rgb"][0] - x["rgb"][2] for x in healthy) if healthy else 0.0
            prev = None
            shots_report = []
            for scene, index, shot, data in subset:
                factor, saturation, warnings = 1.0, 1.0, []
                if data is None:
                    warnings.append("sample_unavailable")
                else:
                    luma, chroma = data["luma"], data["chroma"]
                    # Deliberately dark temples / sunlit scenes remain untouched.
                    if not MIN_EXPOSURE <= luma <= MAX_EXPOSURE:
                        warnings.append("artistic_or_extreme_lighting_preserved")
                    else:
                        factor = round(_clamp(target_luma / max(.03, luma), .92, 1.08), 3)
                        if chroma >= .065 and target_chroma >= .065:
                            saturation = round(_clamp(target_chroma / chroma, .95, 1.05), 3)
                    if prev is not None and prev["scene"] == scene:
                        delta = abs(luma - prev["luma"])
                        if delta > .29:
                            warnings.append("adjacent_exposure_jump")
                    if abs((data["rgb"][0] - data["rgb"][2]) - target_balance) > .22:
                        warnings.append("white_balance_mismatch_manual_review")
                    prev = {"scene": scene, "luma": luma}
                shot["colorCorrection"] = {"brightness": factor, "saturation": saturation}
                if warnings:
                    report["warnings"].append({"format": kind, "scene": scene, "shot": index, "codes": warnings})
                shots_report.append({"scene": scene, "shot": index, "file": shot.get("file"),
                                     "sample": data, "brightness": factor,
                                     "saturation": saturation, "warnings": warnings})
            report["formats"][kind] = {
                "shotCount": len(subset), "targetLuma": round(target_luma, 4),
                "targetChroma": round(target_chroma, 4),
                "shots": shots_report,
            }
    target = Path(report_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def validate_corrections(scenes):
    for scene in scenes:
        for shot in scene.get("shots") or []:
            correct = shot.get("colorCorrection")
            if not isinstance(correct, dict):
                raise ValueError("Missing color correction/continuity data")
            for name, low, high in (("brightness", .92, 1.08), ("saturation", .95, 1.05)):
                val = correct.get(name)
                if not isinstance(val, (int, float)) or not math.isfinite(val) or not low <= val <= high:
                    raise ValueError(f"Unsafe {name} color correction: {val!r}")
