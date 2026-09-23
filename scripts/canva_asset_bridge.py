#!/usr/bin/env python3
"""Optional Canva asset bridge.

The bridge uses Canva only where the public API supports a deterministic
library upload. The Remotion render remains the production source of truth;
the final outputs are additionally preserved in the user's Canva library so
they can be opened for manual finishing/branding without a re-upload step.
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
    r = requests.post(f"{API}/asset-uploads", headers=headers, data=data, timeout=180)
    r.raise_for_status()
    job_id = r.json()["job"]["id"]
    for _ in range(60):
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
            raise RuntimeError(
                job.get("error", {}).get("message", "Canva asset upload failed")
            )
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
        ("out/final_video.mp4", "Devotional Long Video — Final"),
        ("out/final_video_shorts.mp4", "Devotional Shorts — Final"),
        ("out/thumbnail.jpg", "Devotional Long Video Thumbnail"),
        ("out/thumbnail_shorts_final.jpg", "Devotional Shorts Thumbnail"),
    ]

    # Optional scene preservation remains opt-in so the Canva library is not
    # flooded with every intermediate image.
    if os.getenv("CANVA_UPLOAD_SCENE_ASSETS", "").lower() == "true":
        scene_assets = [
            (str(p), f"Scene Visual {p.stem}")
            for p in sorted(Path("public/images").glob("*"))
            if p.is_file()
        ][:6]
        candidates.extend(scene_assets)

    results = []
    for path, name in candidates:
        if not Path(path).exists():
            continue
        try:
            asset = upload(path, token, name)
            results.append({
                "path": path,
                "name": name,
                "assetId": asset.get("id"),
                "type": asset.get("type"),
            })
            print(f"Canva asset ready: {name}", flush=True)
        except Exception as exc:
            print(f"::warning::Canva upload failed for {path}: {exc}")

    Path("out").mkdir(exist_ok=True)
    Path("out/canva_assets.json").write_text(
        json.dumps({
            "enabled": True,
            "assets": results,
            "note": (
                "Final Remotion outputs are preserved in Canva for optional "
                "manual finishing/branding. The production render remains "
                "deterministic and does not depend on Canva editing."
            ),
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"::warning::Canva asset bridge skipped: {exc}")
        sys.exit(0)
