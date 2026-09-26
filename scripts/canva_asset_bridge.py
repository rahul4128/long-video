#!/usr/bin/env python3
"""Canva finishing bridge (runs AFTER the final video + thumbnails are rendered).

What it does with a normal Canva Pro/Teams subscription (no Enterprise needed):
  1. Uploads the FINAL long video, Shorts video and both text-overlaid
     thumbnails to your Canva "Uploads".
  2. Creates two ready-to-edit Canva designs with the thumbnail already placed:
       - "YT Thumbnail ..."      1280x720
       - "Shorts Cover ..."      1080x1920
  3. Writes the Canva edit links to out/canva_assets.json and
     out/canva_notes.md (added to the GitHub Release notes).

What the Canva API can NOT do (Canva limitation, not this script):
  - Autofill / brand templates (Enterprise only).
  - Put a VIDEO into a design automatically (create-design accepts images only).
  - Magic Studio, Beat Sync, background remover, animations - editor only.
So you open the links, polish, and export/upload from Canva.

Every failure is a warning only: Canva can never block publishing.
"""
import base64
import json
import os
import sys
import time
from pathlib import Path

import requests

API = "https://api.canva.com/rest/v1"


def _env_path(name, default):
    return Path(os.getenv(name, default))


def _short_title():
    """Readable design/asset name from the video title (Canva limit: 50 chars)."""
    meta_path = _env_path("CANVA_METADATA_JSON", "assets/out/metadata.json")
    title = ""
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        title = (meta.get("long_video_title") or "").strip()
    except Exception:
        pass
    run_id = os.getenv("GITHUB_RUN_ID", "")
    base = title or f"Devotional {run_id}"
    return base[:38]


def upload(path, token, name, timeout_s=240):
    data = Path(path).read_bytes()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/octet-stream",
        "Asset-Upload-Metadata": json.dumps({
            "name_base64": base64.b64encode(name[:50].encode("utf-8")).decode("ascii")
        }),
    }
    r = requests.post(f"{API}/asset-uploads", headers=headers, data=data, timeout=600)
    r.raise_for_status()
    job_id = r.json()["job"]["id"]
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        s = requests.get(
            f"{API}/asset-uploads/{job_id}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
        s.raise_for_status()
        job = s.json()["job"]
        if job.get("status") == "success":
            return job.get("asset", {})
        if job.get("status") == "failed":
            raise RuntimeError(job.get("error", {}).get("message", "Canva asset upload failed"))
        time.sleep(3)
    raise TimeoutError(f"Canva asset upload timed out: {name}")


def create_design(token, asset_id, title, width, height):
    r = requests.post(
        f"{API}/designs",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={
            "design_type": {"type": "custom", "width": width, "height": height},
            "asset_id": asset_id,
            "title": title[:50],
        },
        timeout=60,
    )
    r.raise_for_status()
    design = r.json().get("design", {})
    urls = design.get("urls", {}) or {}
    return {
        "id": design.get("id"),
        "title": design.get("title"),
        "edit_url": urls.get("edit_url"),
        "view_url": urls.get("view_url"),
    }


def main():
    out_dir = Path("out")
    out_dir.mkdir(exist_ok=True)
    notes_path = out_dir / "canva_notes.md"
    report = {"enabled": False, "assets": [], "designs": [], "warnings": []}

    token = os.getenv("CANVA_ACCESS_TOKEN", "").strip()
    enabled = os.getenv("CANVA_ASSET_BRIDGE_ENABLED", "true").lower() == "true"
    if not enabled or not token:
        msg = "Canva finishing skipped (disabled or no access token)."
        print(msg)
        notes_path.write_text(f"_{msg}_\n", encoding="utf-8")
        (out_dir / "canva_assets.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        return
    report["enabled"] = True

    title = _short_title()
    upload_videos = os.getenv("CANVA_UPLOAD_VIDEOS", "true").lower() == "true"

    items = [
        # (env var, default path, asset name, design spec or None)
        ("CANVA_THUMB_PATH", "thumbnail_final/thumbnail.jpg", f"Thumb | {title}",
         ("YT Thumbnail", 1280, 720)),
        ("CANVA_SHORTS_THUMB_PATH", "thumbnail_shorts_final/thumbnail_shorts_final.jpg",
         f"Shorts cover | {title}", ("Shorts Cover", 1080, 1920)),
    ]
    if upload_videos:
        items += [
            ("CANVA_LONG_VIDEO_PATH", "video/final_video.mp4", f"Long video | {title}", None),
            ("CANVA_SHORTS_VIDEO_PATH", "shorts/final_video_shorts.mp4", f"Short | {title}", None),
        ]

    for env_name, default, asset_name, design_spec in items:
        path = _env_path(env_name, default)
        if not path.exists():
            report["warnings"].append(f"missing file: {path}")
            continue
        try:
            is_video = path.suffix.lower() in (".mp4", ".mov", ".webm")
            asset = upload(path, token, asset_name, timeout_s=600 if is_video else 120)
            entry = {"path": str(path), "name": asset_name, "assetId": asset.get("id"),
                     "type": "video" if is_video else "image"}
            report["assets"].append(entry)
            print(f"Canva: uploaded {path} -> asset {asset.get('id')}")
            if design_spec and asset.get("id"):
                label, w, h = design_spec
                design = create_design(token, asset["id"], f"{label} | {title}", w, h)
                design["label"] = label
                report["designs"].append(design)
                print(f"Canva: created design '{label}' -> {design.get('edit_url')}")
        except Exception as exc:
            msg = f"Canva step failed for {path}: {exc}"
            report["warnings"].append(msg)
            print(f"::warning::{msg}")

    (out_dir / "canva_assets.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    lines = ["### Canva finishing (optional)", ""]
    for d in report["designs"]:
        if d.get("edit_url"):
            lines.append(f"- **{d['label']}** – [open in Canva]({d['edit_url']})")
    vids = [a for a in report["assets"] if a["type"] == "video"]
    if vids:
        lines.append("- Videos are in Canva → **Uploads**: " + ", ".join(a["name"] for a in vids))
    lines += [
        "",
        "Polish in Canva, then: thumbnail → replace in YouTube Studio any time; "
        "video → only BEFORE the upload goes public (YouTube cannot replace a published video).",
    ]
    if report["warnings"]:
        lines += ["", "Warnings: " + "; ".join(report["warnings"])]
    notes_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"::warning::Canva finishing skipped: {exc}")
        Path("out").mkdir(exist_ok=True)
        Path("out/canva_notes.md").write_text(f"_Canva finishing skipped: {exc}_\n", encoding="utf-8")
        sys.exit(0)