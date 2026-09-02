import os
import json
import base64
import requests
from faster_whisper import WhisperModel

# Ensure required directories exist up front
os.makedirs("public/images", exist_ok=True)
os.makedirs("public/videos", exist_ok=True)
os.makedirs("public/audio", exist_ok=True)
os.makedirs("out", exist_ok=True)

PEXELS_KEY = os.getenv("PEXELS_API_KEY", "")
CF_ACCOUNT = os.getenv("CLOUDFLARE_ACCOUNT_ID", "")
CF_TOKEN = os.getenv("CLOUDFLARE_API_TOKEN", "")

payload_raw = os.getenv("DISPATCH_PAYLOAD", "{}")
try:
    payload = json.loads(payload_raw) if payload_raw else {}
except Exception:
    payload = {}

# Handle Make.com nested payloads cleanly
if isinstance(payload, str):
    try:
        payload = json.loads(payload)
    except Exception:
        payload = {}


def as_dict(value):
    """Make.com often serializes nested JSON fields as strings. Normalize to a dict."""
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except Exception:
            return {}
    return value if isinstance(value, dict) else {}


long_video_data = as_dict(payload.get("long_video", {}))
shorts_data = as_dict(payload.get("shorts", {}))
seo_meta = as_dict(payload.get("seo_metadata", {}))
thumbnail_data = as_dict(payload.get("thumbnail", {}))

scenes_input = long_video_data.get("scenes") or payload.get("scenes") or [
    {
        "text": "काशी के पावन तट पर हर संध्या एक दिव्य शांति छा जाती है।",
        "mediaType": "video",
        "videoSearchQuery": "varanasi ganga aarti diya evening",
        "imagePrompt": "Lord Shiva meditating in snow mountain, cinematic 8k"
    },
    {
        "text": "भोलेनाथ अपने मौन में पूरे ब्रह्मांड का गूढ़ रहस्य समाए हुए हैं।",
        "mediaType": "ai_image",
        "videoSearchQuery": "",
        "imagePrompt": "Lord Shiva in deep meditation on Kailash, glowing third eye aura, hyperrealistic"
    }
]

shorts_scenes_input = shorts_data.get("scenes") or scenes_input

GITHUB_REPO = os.getenv("GITHUB_REPOSITORY", "")
ASSET_RELEASE_TAG = payload.get("asset_release_tag", "")


def fetch_kaggle_release_assets(tag: str) -> dict:
    """Look up a GitHub Release's assets by filename -> download URL.

    Used for the Kaggle hybrid pipeline: when a Kaggle notebook run has already
    rendered scene clips and uploaded them as a release, generate_assets.py uses
    those clips instead of calling Cloudflare FLUX for the matching scenes.
    Public repo, so this works without a token.
    """
    if not tag or not GITHUB_REPO:
        return {}
    url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/tags/{tag}"
    try:
        res = requests.get(url, headers={"Accept": "application/vnd.github+json"}, timeout=15)
        if res.status_code == 200:
            return {
                a["name"]: a["browser_download_url"]
                for a in res.json().get("assets", [])
            }
        print(f"Kaggle release lookup notice: {url} returned {res.status_code}")
    except Exception as e:
        print(f"Kaggle release lookup notice: {e}")
    return {}


KAGGLE_ASSETS = fetch_kaggle_release_assets(ASSET_RELEASE_TAG)
if KAGGLE_ASSETS:
    print(f"Found {len(KAGGLE_ASSETS)} Kaggle-rendered clip(s) in release '{ASSET_RELEASE_TAG}'.")


def fetch_pexels_video(query: str, orientation: str = "landscape") -> str | None:
    if not PEXELS_KEY or not query:
        return None
    headers = {"Authorization": PEXELS_KEY}
    url = f"https://api.pexels.com/videos/search?query={query}&orientation={orientation}&per_page=3"
    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            videos = res.json().get("videos", [])
            if videos:
                files = videos[0].get("video_files", [])
                hd_files = [f for f in files if f.get("width") == 1920 or f.get("height") == 1080]
                return hd_files[0]["link"] if hd_files else files[0]["link"]
    except Exception as e:
        print(f"Pexels fetch notice: {e}")
    return None


def generate_cloudflare_flux(prompt: str, out_path: str):
    if not CF_ACCOUNT or not CF_TOKEN:
        print("Cloudflare credentials not provided, skipping FLUX call.")
        with open(out_path, "wb") as f:
            f.write(b"")
        return
    url = f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT}/ai/run/@cf/black-forest-labs/flux-1-schnell"
    headers = {"Authorization": f"Bearer {CF_TOKEN}"}
    try:
        res = requests.post(url, headers=headers, json={"prompt": prompt, "num_steps": 4}, timeout=35)
        if res.status_code == 200:
            data = res.json()
            img_bytes = base64.b64decode(data["result"]["image"])
            with open(out_path, "wb") as f:
                f.write(img_bytes)
    except Exception as e:
        print(f"Cloudflare FLUX error: {e}")


def build_scene_assets(scenes, id_prefix, orientation):
    """Download/generate visuals for a list of story scenes and return Remotion scene props.

    Each scene tries stock video first (when a search query is given), falling back to an
    AI-generated still image. Files are namespaced by id_prefix so the long-form and Shorts
    pipelines never clobber each other's assets.
    """
    scene_props = []
    narration_lines = []

    for idx, sc in enumerate(scenes, start=1):
        narration_text = sc.get("text", "")
        narration_lines.append(narration_text)
        media_type = sc.get("mediaType", "ai_image")
        query = sc.get("videoSearchQuery", "")
        prompt = sc.get("imagePrompt", "")

        downloaded = False

        # Prefer a Kaggle-rendered clip for this scene, if the dispatch came with one.
        kaggle_filename = f"{id_prefix}_{idx}.mp4"
        if kaggle_filename in KAGGLE_ASSETS:
            try:
                v_res = requests.get(KAGGLE_ASSETS[kaggle_filename], timeout=60)
                if v_res.status_code == 200:
                    v_path = f"public/videos/{kaggle_filename}"
                    with open(v_path, "wb") as f:
                        f.write(v_res.content)
                    scene_props.append({
                        "id": idx,
                        "type": "video",
                        "src": f"videos/{kaggle_filename}",
                        "durationInFrames": 120
                    })
                    downloaded = True
            except Exception as e:
                print(f"Kaggle clip download notice ({kaggle_filename}): {e}")

        wants_video = media_type == "video" or (media_type != "ai_image" and query)
        if not downloaded and wants_video and query:
            video_url = fetch_pexels_video(query, orientation=orientation)
            if video_url:
                try:
                    v_res = requests.get(video_url, timeout=25)
                    if v_res.status_code == 200:
                        v_path = f"public/videos/{id_prefix}_{idx}.mp4"
                        with open(v_path, "wb") as f:
                            f.write(v_res.content)
                        scene_props.append({
                            "id": idx,
                            "type": "video",
                            "src": f"videos/{id_prefix}_{idx}.mp4",
                            "durationInFrames": 120
                        })
                        downloaded = True
                except Exception as e:
                    print(f"Stock video download notice ({id_prefix}_{idx}): {e}")

        if not downloaded:
            img_path = f"public/images/{id_prefix}_{idx}.png"
            generate_cloudflare_flux(prompt, img_path)
            scene_props.append({
                "id": idx,
                "type": "image",
                "src": f"images/{id_prefix}_{idx}.png",
                "durationInFrames": 120
            })

    return scene_props, narration_lines


def synthesize_narration(text: str, audio_path: str, whisper_model) -> list:
    """Generate a voiceover with edge-tts and return word-level captions via Whisper."""
    with open("temp_script.txt", "w", encoding="utf-8") as f:
        f.write(text)

    exit_code = os.system(
        f'edge-tts --voice hi-IN-MadhurNeural --file temp_script.txt --write-media "{audio_path}"'
    )
    if exit_code != 0:
        print(f"edge-tts notice: narration synthesis for {audio_path} exited with code {exit_code}")

    captions = []
    if whisper_model is None or not os.path.exists(audio_path) or os.path.getsize(audio_path) == 0:
        return captions

    try:
        segments, _ = whisper_model.transcribe(audio_path, word_timestamps=True)
        for seg in segments:
            for w in seg.words:
                captions.append({
                    "text": w.word.strip(),
                    "startMs": int(w.start * 1000),
                    "endMs": int(w.end * 1000)
                })
    except Exception as e:
        print(f"Whisper subtitle notice ({audio_path}): {e}")

    return captions


# ---- Long-form video: visuals, voiceover, captions ----
props_scenes, long_narration_lines = build_scene_assets(scenes_input, "scene", orientation="landscape")

whisper_model = None
try:
    whisper_model = WhisperModel("base", device="cpu", compute_type="int8")
except Exception as e:
    print(f"Whisper model load notice: {e}")

long_captions = synthesize_narration(
    " ".join(long_narration_lines), "public/audio/narration.mp3", whisper_model
)

props_long = {
    "audioUrl": "audio/narration.mp3",
    "captions": long_captions,
    "scenes": props_scenes
}

with open("public/props.json", "w", encoding="utf-8") as f:
    json.dump(props_long, f, indent=2, ensure_ascii=False)

# ---- Shorts teaser: its own visuals (vertical), its own voiceover and captions ----
shorts_props_scenes, shorts_narration_lines = build_scene_assets(
    shorts_scenes_input, "shorts_scene", orientation="portrait"
)

shorts_captions = synthesize_narration(
    " ".join(shorts_narration_lines), "public/audio/narration_shorts.mp3", whisper_model
)

props_shorts = {
    "audioUrl": "audio/narration_shorts.mp3",
    "captions": shorts_captions,
    "scenes": shorts_props_scenes
}

with open("public/props_shorts.json", "w", encoding="utf-8") as f:
    json.dump(props_shorts, f, indent=2, ensure_ascii=False)

# YouTube Upload Metadata
meta = {
    "long_video_title": seo_meta.get("long_video_title", "महाकाल का रहस्य | Divine Devotional Story"),
    "long_video_description": seo_meta.get("long_video_description", "श्री महाकाल कथा एवं दर्शन #devotional #shiva"),
    "tags": seo_meta.get("tags", ["Mahakal", "Shiva", "Bhakti", "Devotional"]),
    "shorts_title": seo_meta.get("shorts_title", "भोलेनाथ की असीम कृपा #shorts #shiva"),
    "shorts_description": seo_meta.get("shorts_description", "हर हर महादेव #shorts"),
    "hashtags": seo_meta.get("hashtags", ["#shorts", "#shiva", "#mahadev"])
}
with open("out/metadata.json", "w", encoding="utf-8") as f:
    json.dump(meta, f, indent=2, ensure_ascii=False)

thumb_prompt = thumbnail_data.get("imagePrompt") or scenes_input[0].get("imagePrompt", "Lord Shiva divine aura")
generate_cloudflare_flux(thumb_prompt or "Lord Shiva divine aura", "out/thumbnail.jpg")