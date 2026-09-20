#!/usr/bin/env python3
"""Optional Canva asset bridge.

Canva Connect can upload images/videos to the user's Canva library. It cannot
programmatically search Canva's internal stock catalog or invoke Canva's
built-in Hindi TTS/AI-video UI. This bridge therefore uses Canva where the
public API actually supports it: preserve the best generated visual assets in
Canva for premium/manual finishing without making the render dependent on an
unsupported API.
"""
import base64
import json
import os
import sys
import time
from pathlib import Path

import requests

API = "https://api.canva.com/rest/v1"

def upload(path, token, name):
    data = Path(path).read_bytes()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/octet-stream",
        "Asset-Upload-Metadata": json.dumps({
            "name_base64": base64.b64encode(name.encode("utf-8")).decode("ascii")
        }),
    }
    r = requests.post(f"{API}/asset-uploads", headers=headers, data=data, timeout=120)
    r.raise_for_status()
    job_id = r.json()["job"]["id"]
    for _ in range(30):
        s = requests.get(f"{API}/asset-uploads/{job_id}", headers={"Authorization": f"Bearer {token}"}, timeout=30)
        s.raise_for_status()
        job = s.json()["job"]
        if job.get("status") == "success":
            return job.get("asset", {})
        if job.get("status") == "failed":
            raise RuntimeError(job.get("error", {}).get("message", "Canva asset upload failed"))
        time.sleep(2)
    raise TimeoutError(f"Canva asset upload timed out: {name}")

def main():
    token = os.getenv("CANVA_ACCESS_TOKEN", "").strip()
    enabled = os.getenv("CANVA_ASSET_BRIDGE_ENABLED", "true").lower() == "true"
    if not enabled:
        return
    if not token:
        print("CANVA_ASSET_BRIDGE: skipped (no access token)")
        return

    candidates = [
        ("out/thumbnail.jpg", "Devotional Long Video Thumbnail"),
        ("out/thumbnail_shorts.jpg", "Devotional Shorts Thumbnail"),
    ]
    # Upload only the final thumbnails by default: this avoids filling the
    # user's Canva library with dozens of intermediate renders.
    extra = os.getenv("CANVA_UPLOAD_SCENE_ASSETS", "").lower() == "true"
    if extra:
        candidates.extend((str(p), f"Scene Visual {p.stem}") for p in sorted(Path("public/images").glob("*")) if p.is_file()][:3])

    results = []
    for path, name in candidates:
        if not Path(path).exists():
            continue
        try:
            asset = upload(path, token, name)
            results.append({"path": path, "name": name, "assetId": asset.get("id"), "type": asset.get("type")})
        except Exception as exc:
            print(f"::warning::Canva upload failed for {path}: {exc}")

    Path("out").mkdir(exist_ok=True)
    Path("out/canva_assets.json").write_text(json.dumps({
        "enabled": True,
        "assets": results,
        "note": "Canva API-supported asset bridge; final video remains rendered by Remotion."
    }, ensure_ascii=False, indent=2), encoding="utf-8")

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"::warning::Canva asset bridge skipped: {exc}")
        sys.exit(0)
