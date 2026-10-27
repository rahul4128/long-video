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
        # User requested no burned-in subtitles until explicitly re-enabled.
        # An old cached payload must not turn captions back on accidentally.
        if os.getenv("SUBTITLES_ENABLED", "false").lower() != "true" and props.get("showSubtitles") is True:
            raise SystemExit(f"Burned-in subtitles unexpectedly enabled in {format_name}")
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
                    if (os.getenv("EDITORIAL_TEXT_OVERLAYS_ENABLED", "false").lower() != "true"
                            and (shot.get("editorialLabel") or shot.get("documentaryGraphic"))):
                        raise SystemExit("Unrequested recurring editorial text overlays")
                    if shot.get("comparisonApproved") is True:
                        for key in ("comparisonBeforeFile", "comparisonAfterFile"):
                            candidate = ROOT / "public" / "images" / str(shot.get(key) or "")
                            if not candidate.is_file():
                                raise SystemExit(f"Missing comparison evidence asset: {key}")
                    if len(str(shot.get("editorialLabel") or "").split()) > 4:
                        raise SystemExit("Editorial label too long")
                    # Editing must NOT introduce extra, unsourced hyperlinks.
                    if "http://" in str(shot.get("editorialLabel") or ""):
                        raise SystemExit("Unsafe URL in editorial annotation")
    print("🎞️ Editorial QC passed: timed shots, restrained annotations and transitions", flush=True)


if __name__ == "__main__":
    main()
