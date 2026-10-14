#!/usr/bin/env python3
"""Contact sheets + shot-to-Hindi-narration ledger before expensive Remotion.

Does not generate new video, query external APIs or modify selected assets.
Outputs proof of what frame was actually chosen for each narration beat.
"""
import json
from pathlib import Path
import subprocess
import tempfile

from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[1]
ROOT_MEDIA = ROOT / "public" / "images"
OUTPUT = ROOT / "out"


def _thumb(file, shot_type, width=288, height=162):
    path = (ROOT_MEDIA / str(file or "")).resolve()
    if not path.is_relative_to(ROOT_MEDIA.resolve()) or not path.is_file():
        return Image.new("RGB", (width, height), (55, 32, 30))
    if shot_type == "video":
        with tempfile.TemporaryDirectory() as tmp:
            still = Path(tmp) / "shot.jpg"
            p = subprocess.run([
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-ss", "0.6", "-i", str(path), "-frames:v", "1",
                "-q:v", "4", str(still),
            ], capture_output=True, timeout=20)
            if p.returncode != 0 or not still.is_file():
                return Image.new("RGB", (width, height), (55, 32, 30))
            with Image.open(still) as frame:
                return ImageOps.fit(frame.convert("RGB"), (width, height))
    try:
        with Image.open(path) as frame:
            return ImageOps.fit(frame.convert("RGB"), (width, height))
    except Exception:
        return Image.new("RGB", (width, height), (55, 32, 30))


def storyboard(format_name, scenes, *, width=288, height=162):
    scenes = list(scenes or [])
    items = []
    for sc_index, scene in enumerate(scenes, 1):
        for shot_index, shot in enumerate(scene.get("shots") or [], 1):
            if not isinstance(shot, dict):
                continue
            items.append({
                "scene": sc_index, "shot": shot_index, "beat": shot.get("beatIndex"),
                "narration": str(shot.get("narrationCue") or ""),
                "source": str(shot.get("source") or "unknown"),
                "file": str(shot.get("file") or ""),
                "type": shot.get("type"), "query": shot.get("queryUsed"),
                "selectionScore": shot.get("selectionScore"),
                "scoreBreakdown": shot.get("scoreBreakdown"),
                "isEmergency": shot.get("source") in {
                    "local_atmosphere_fallback", "local_continuity_fallback"
                },
            })
    OUTPUT.mkdir(exist_ok=True, parents=True)
    path_json = OUTPUT / f"visual_storyboard_{format_name}.json"
    path_json.write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")
    if not items:
        return 0
    cols, pad, banner = 3, 10, 36
    tile_width, tile_height = width + pad * 2, height + pad * 2 + banner
    rows = (len(items) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * tile_width, rows * tile_height), (19, 22, 27))
    draw = ImageDraw.Draw(sheet)
    for index, item in enumerate(items):
        x = (index % cols) * tile_width + pad
        y = (index // cols) * tile_height + pad
        frame = _thumb(item["file"], item["type"], width, height)
        sheet.paste(frame, (x, y))
        if item["isEmergency"]:
            draw.rectangle((x, y, x + width - 1, y + height - 1), outline=(240, 80, 65), width=5)
        label = (f"S{item['scene']:02} B{str(item['beat'] or item['shot']).zfill(2)} "
                 f"{item['source'][:17]} "
                 f"{str(item['selectionScore'] or '')[:5]}")
        draw.text((x + 3, y + height + 8), label, fill=(250, 248, 240))
    path_jpg = OUTPUT / f"visual_storyboard_{format_name}.jpg"
    sheet.save(path_jpg, quality=79, optimize=True)
    return len(items)


def main():
    counts = {}
    for format_name, filename in (("long", "props.json"), ("shorts", "props_shorts.json")):
        path = ROOT / "public" / filename
        if path.exists():
            doc = json.loads(path.read_text(encoding="utf-8"))
            counts[format_name] = storyboard(format_name, doc.get("scenes", []))
    print("Shot-by-shot visual review sheets:", counts, flush=True)


if __name__ == "__main__":
    main()
