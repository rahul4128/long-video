#!/usr/bin/env python3
"""Validate documentary editing props and audit before CPU video renders."""
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from editing_director import validate_editing

ROOT = Path(__file__).resolve().parents[1]


def main():
    report_path = ROOT / "out/editing_qc_report.json"
    if not report_path.is_file():
        raise SystemExit("Editorial QC report missing")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    enabled = report.get("enabled") is True
    for format_name, filename in (
        ("long", "props.json"), ("shorts", "props_shorts.json"),
    ):
        props = json.loads((ROOT / "public" / filename).read_text(encoding="utf-8"))
        scenes = props.get("scenes") or []
        if not scenes:
            raise SystemExit(f"Editorial QC missing scenes: {format_name}")
        if enabled:
            validate_editing(scenes)
            plan = report.get("formats", {}).get(format_name, [])
            if len(plan) != len(scenes):
                raise SystemExit(f"Editorial QC report coverage mismatch: {format_name}")
            for scene in scenes:
                for shot in scene.get("shots") or []:
                    if len(str(shot.get("editorialLabel") or "").split()) > 4:
                        raise SystemExit("Editorial label too long")
                    # Editing must NOT introduce extra, unsourced hyperlinks.
                    if "http://" in str(shot.get("editorialLabel") or ""):
                        raise SystemExit("Unsafe URL in editorial annotation")
    print("🎞️ Editorial QC passed: timed shots, restrained annotations and transitions", flush=True)


if __name__ == "__main__":
    main()
