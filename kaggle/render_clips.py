# Kaggle GPU clip generator for the Devotional Long Video pipeline.
#
# How this fits together (hybrid pipeline):
#   1. Make.com's Gemini step writes the story JSON to a new timestamped
#      file under kaggle_jobs/ in this repo (job-YYYYMMDDHHmmss.json —
#      a small "commit file" step added to the Make.com scenario, PUT to
#      /repos/{repo}/contents/kaggle_jobs/job-....json) instead of
#      dispatching the render workflow directly. Writing a new file each
#      time (rather than overwriting one fixed file) avoids needing to
#      look up a git blob sha from Make.com.
#   2. You run this notebook on Kaggle (manually, or on a Kaggle
#      schedule) whenever you want fresh clips. It lists kaggle_jobs/,
#      picks the most recent job-*.json (falling back to a static
#      kaggle_jobs/latest.json if none exist yet), generates one short
#      video clip per scene with LTX-Video on the free T4 GPU, uploads
#      the clips as a GitHub Release, and then dispatches
#      `trigger-render-long` to GitHub Actions with the SAME story JSON
#      plus the release tag.
#   3. generate_assets.py (in the main repo) sees `asset_release_tag` in
#      the dispatch payload, downloads any matching clip for each scene
#      from that release, and uses it instead of calling Cloudflare FLUX
#      for that scene. Pexels-sourced "video" scenes in the long video
#      are untouched by this — Kaggle only replaces the AI-generated
#      scenes (mediaType == "ai_image" for long_video scenes; ALL scenes
#      for the Shorts teaser, since Shorts scenes have no mediaType).
#
# Only one Kaggle secret is required (Add-ons -> Secrets):
#   GH_TOKEN  - a GitHub token with `repo` scope (public repo contents
#               read doesn't need auth, but creating the release does).
# REPO must match your GitHub repo below.

import os
import json
import time
import subprocess

import torch
import requests
from kaggle_secrets import UserSecretsClient
from diffusers import LTXPipeline
from diffusers.utils import export_to_video

# ---- Configuration ----
REPO = "rahul4128/long-video"
JOB_DIR = "kaggle_jobs"
DISPATCH_EVENT_TYPE = "trigger-render-long"

user_secrets = UserSecretsClient()
GH_TOKEN = user_secrets.get_secret("GH_TOKEN")
os.environ["GH_TOKEN"] = GH_TOKEN

os.makedirs("generated_clips", exist_ok=True)


def as_dict(value):
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except Exception:
            return {}
    return value if isinstance(value, dict) else {}


# ---- 1. Fetch the most recent job (story JSON) that Make.com staged in the repo ----
print("Looking up the latest job file in the repo...")
dir_res = requests.get(
    f"https://api.github.com/repos/{REPO}/contents/{JOB_DIR}",
    headers={"Accept": "application/vnd.github+json"},
    timeout=20,
)
dir_res.raise_for_status()
job_files = sorted(
    (item for item in dir_res.json() if item["name"].startswith("job-") and item["name"].endswith(".json")),
    key=lambda item: item["name"],
)

if job_files:
    latest_job = job_files[-1]
    print(f"Using job file: {latest_job['name']}")
    job_res = requests.get(latest_job["download_url"], timeout=20)
else:
    print("No timestamped job files yet - falling back to kaggle_jobs/latest.json")
    job_res = requests.get(
        f"https://raw.githubusercontent.com/{REPO}/main/{JOB_DIR}/latest.json", timeout=20
    )
job_res.raise_for_status()
job_payload = job_res.json()

long_video_data = as_dict(job_payload.get("long_video", {}))
shorts_data = as_dict(job_payload.get("shorts", {}))
seo_meta = as_dict(job_payload.get("seo_metadata", {}))
thumbnail_data = as_dict(job_payload.get("thumbnail", {}))

long_scenes = long_video_data.get("scenes", [])
shorts_scenes = shorts_data.get("scenes", [])

# Long-video scenes only need Kaggle when they're an AI-generated character/deity
# shot (mediaType == "ai_image"); stock-footage "video" scenes stay on Pexels.
# Shorts scenes have no mediaType in the schema, so every one of them is rendered
# here (Shorts is short enough that GPU time stays bounded).
render_jobs = []
for sc in long_scenes:
    if sc.get("mediaType") == "ai_image":
        render_jobs.append({
            "id": sc.get("id") or (long_scenes.index(sc) + 1),
            "prefix": "scene",
            "prompt": sc.get("imagePrompt", "Divine devotional scene, cinematic 8k"),
            "width": 768,
            "height": 512,
        })

for idx, sc in enumerate(shorts_scenes, start=1):
    render_jobs.append({
        "id": idx,
        "prefix": "shorts_scene",
        "prompt": sc.get("imagePrompt", "Divine devotional scene, cinematic 8k, vertical"),
        "width": 512,
        "height": 768,
    })

if not render_jobs:
    raise SystemExit("No ai_image scenes found in the fetched job - nothing for Kaggle to render.")

job_names = [f"{j['prefix']}_{j['id']}" for j in render_jobs]
print(f"{len(render_jobs)} clip(s) to generate: {job_names}")

# ---- 2. Load LTX-Video pipeline on the T4 GPU ----
print("Loading LTX-Video diffusion pipeline...")
pipe = LTXPipeline.from_pretrained("Lightricks/LTX-Video", torch_dtype=torch.bfloat16)
pipe.enable_model_cpu_offload()
pipe.enable_vae_tiling()

# ---- 3. Generate each clip ----
for job in render_jobs:
    out_path = f"generated_clips/{job['prefix']}_{job['id']}.mp4"
    print(f"Generating {out_path}...")
    frames = pipe(
        prompt=job["prompt"],
        negative_prompt="worst quality, blurry, distorted, jittery, watermark, text",
        width=job["width"],
        height=job["height"],
        num_frames=97,  # ~4 seconds at 24fps, matches the 120-frame/30fps scene slot after re-encode
        num_inference_steps=30,
    ).frames[0]
    export_to_video(frames, out_path, fps=24)

# ---- 4. Upload clips as a GitHub Release ----
tag = f"assets-{int(time.time())}"
print(f"Creating GitHub Release {tag}...")
subprocess.run(
    ["gh", "release", "create", tag, *[
        f"generated_clips/{job['prefix']}_{job['id']}.mp4" for job in render_jobs
    ], "--repo", REPO, "--title", f"Kaggle clips {tag}"],
    check=True,
)

# ---- 5. Dispatch to GitHub Actions, passing the story JSON straight through ----
# so generate_assets.py has the same narration/SEO/thumbnail data it would get
# from a direct Make.com dispatch, plus the release tag to pull clips from.
dispatch_url = f"https://api.github.com/repos/{REPO}/dispatches"
headers = {
    "Authorization": f"Bearer {GH_TOKEN}",
    "Accept": "application/vnd.github+json",
}
client_payload = {
    "long_video": long_video_data,
    "shorts": shorts_data,
    "seo_metadata": seo_meta,
    "thumbnail": thumbnail_data,
    "asset_release_tag": tag,
    "dispatchedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
}
res = requests.post(dispatch_url, json={
    "event_type": DISPATCH_EVENT_TYPE,
    "client_payload": client_payload,
}, headers=headers, timeout=20)
res.raise_for_status()
print(f"Dispatched GitHub workflow with release tag {tag}: status {res.status_code}")