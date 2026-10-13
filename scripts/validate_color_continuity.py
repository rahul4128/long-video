#!/usr/bin/env python3
"""Pre-render QC of limited CPU-only color matching and continuity report."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from color_continuity import validate_corrections


def inspect(root=ROOT):
    report_path = root / "out" / "color_continuity_report.json"
    if not report_path.is_file():
        raise ValueError("Missing color continuity audit")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if report.get("enabled") is not True:
        print("🎨 Color continuity disabled by repo setting.", flush=True)
        return report
    files = (("long", "props.json"), ("shorts", "props_shorts.json"))
    for kind, name in files:
        props = json.loads((root / "public" / name).read_text(encoding="utf-8"))
        scenes = props.get("scenes") or []
        validate_corrections(scenes)
        count = sum(len(scene.get("shots") or []) for scene in scenes)
        if count != report.get("formats", {}).get(kind, {}).get("shotCount"):
            raise ValueError(f"Missing analyzed color shots: {kind}")
    if report.get("samples", 0) < 1:
        raise ValueError("No source media could be sampled for color continuity")
    print(f"🎨 Color continuity QC passed: {report['samples']} sampled files; "
          f"{len(report.get('warnings') or [])} warnings", flush=True)
    return report


if __name__ == "__main__":
    inspect()
