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

long_video_data = payload.get("long_video", {})
if isinstance(long_video_data, str):
    try:
        long_video_data = json.loads(long_video_data)
    except Exception:
        long_video_data = {}

shorts_data = payload.get("shorts", {})
if isinstance(shorts_data, str):
    try:
        shorts_data = json.loads(shorts_data)
    except Exception:
        shorts_data = {}

seo_meta = payload.get("seo_metadata", {})
if isinstance(seo_meta, str):
    try:
        seo_meta = json.loads(seo_meta)
    except Exception:
        seo_meta = {}

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

props_scenes = []
full_narration = []

for idx, sc in enumerate(scenes_input, start=1):
    narration_text = sc.get("text", "")
    full_narration.append(narration_text)
    media_type = sc.get("mediaType", "ai_image")
    query = sc.get("videoSearchQuery", "")
    prompt = sc.get("imagePrompt", "")

    downloaded = False
    if media_type == "video" and query:
        video_url = fetch_pexels_video(query, orientation="landscape")
        if video_url:
            v_res = requests.get(video_url, timeout=25)
            if v_res.status_code == 200:
                v_path = f"public/videos/scene_{idx}.mp4"
                with open(v_path, "wb") as f:
                    f.write(v_res.content)
                props_scenes.append({
                    "id": idx,
                    "type": "video",
                    "src": f"videos/scene_{idx}.mp4",
                    "durationInFrames": 120
                })
                downloaded = True

    if not downloaded:
        img_path = f"public/images/scene_{idx}.png"
        generate_cloudflare_flux(prompt, img_path)
        props_scenes.append({
            "id": idx,
            "type": "image",
            "src": f"images/scene_{idx}.png",
            "durationInFrames": 120
        })

# Edge-TTS voiceover
combined_script = " ".join(full_narration)
with open("temp_script.txt", "w", encoding="utf-8") as f:
    f.write(combined_script)

os.system("edge-tts --voice hi-IN-MadhurNeural --file temp_script.txt --write-media public/audio/narration.mp3")

# Word-level subtitles via Whisper
captions = []
try:
    model = WhisperModel("base", device="cpu", compute_type="int8")
    segments, _ = model.transcribe("public/audio/narration.mp3", word_timestamps=True)
    for seg in segments:
        for w in seg.words:
            captions.append({
                "text": w.word.strip(),
                "startMs": int(w.start * 1000),
                "endMs": int(w.end * 1000)
            })
except Exception as e:
    print(f"Whisper subtitle notice: {e}")

props_long = {
    "audioUrl": "audio/narration.mp3",
    "captions": captions,
    "scenes": props_scenes
}

with open("public/props.json", "w", encoding="utf-8") as f:
    json.dump(props_long, f, indent=2, ensure_ascii=False)

shorts_props_scenes = []
for idx, sc in enumerate(shorts_scenes_input, start=1):
    src_file = f"videos/scene_{idx}.mp4" if os.path.exists(f"public/videos/scene_{idx}.mp4") else f"images/scene_{idx}.png"
    shorts_props_scenes.append({
        "id": idx,
        "type": "video" if "videos/" in src_file else "image",
        "src": src_file,
        "durationInFrames": 120
    })

props_shorts = {
    "audioUrl": "audio/narration.mp3",
    "captions": captions,
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

thumb_prompt = payload.get("thumbnail", {}).get("imagePrompt") if isinstance(payload.get("thumbnail"), dict) else scenes_input[0].get("imagePrompt", "Lord Shiva divine aura")
generate_cloudflare_flux(thumb_prompt or "Lord Shiva divine aura", "out/thumbnail.jpg")
