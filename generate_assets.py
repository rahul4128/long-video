import os
import json
import time
import base64
import random
import shutil
import asyncio
import subprocess
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
import requests
import edge_tts

# Read payload safely
raw_payload = os.environ.get("DISPATCH_PAYLOAD", "").strip()
payload = {}
if raw_payload and raw_payload != "null":
    try:
        loaded = json.loads(raw_payload)
        if isinstance(loaded, dict):
            payload = loaded
    except Exception:
        payload = {}

# Extract multi-format payload blocks
seo_metadata = payload.get("seo_metadata", {})
thumbnail_data = payload.get("thumbnail", {})
long_data = payload.get("long_video", {})
shorts_data = payload.get("shorts", {})

long_scenes = long_data.get("scenes", []) if isinstance(long_data, dict) else []
shorts_scenes = shorts_data.get("scenes", []) if isinstance(shorts_data, dict) else []

# Fallback test scenes for direct workflow_dispatch testing
if not long_scenes:
    long_scenes = [
        {
            "scene_number": 1,
            "mediaType": "ai_image",
            "text": "जीवन के हर मोड़ पर हमें कर्म और धर्म का सही मार्ग चुनना होता है।",
            "imagePrompt": "Lord Krishna in yellow silk robes standing on golden chariot talking to warrior Arjuna on Kurukshetra battlefield, cinematic 16:9, warm divine lighting",
            "videoSearchQuery": "ancient battlefield dust storm sunset"
        },
        {
            "scene_number": 2,
            "mediaType": "video",
            "text": "जब मन में शांति और श्रद्धा होती है तो सभी संशय स्वतः दूर हो जाते हैं।",
            "imagePrompt": "Ancient Himalayan spiritual temple with glowing diya flames golden light 16:9",
            "videoSearchQuery": "burning diya temple sacred smoke"
        }
    ]

if not shorts_scenes:
    shorts_scenes = [
        {
            "scene_number": 1,
            "text": "क्या आप जानते हैं महाभारत का सबसे बड़ा रहस्य क्या था?",
            "imagePrompt": "Lord Krishna with radiant divine golden aura looking intensely forward, dramatic vertical 9:16",
            "videoSearchQuery": "burning diya aarti flame"
        }
    ]

CLOUDFLARE_ACCOUNT_ID = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "").strip()
CLOUDFLARE_API_TOKEN = os.environ.get("CLOUDFLARE_API_TOKEN", "").strip()
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY", "").strip()
PIXABAY_API_KEY = os.environ.get("PIXABAY_API_KEY", "").strip()
COVERR_API_KEY = os.environ.get("COVERR_API_KEY", "").strip()
FREESOUND_API_KEY = os.environ.get("FREESOUND_API_KEY", "").strip()

os.makedirs("public/images", exist_ok=True)
os.makedirs("public/audio", exist_ok=True)
os.makedirs("public/audio/effects", exist_ok=True)
os.makedirs("out", exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
}

# -------------------------------------------------------------
# 1. MULTI-PLATFORM STOCK VIDEO ENGINE (Pexels + Pixabay + Coverr)
# -------------------------------------------------------------
def fetch_pexels_video(query: str, dest_path: str, orientation: str = "landscape") -> bool:
    if not PEXELS_API_KEY or not query:
        return False
    try:
        clean_q = urllib.parse.quote(query.strip()[:60])
        url = f"https://api.pexels.com/videos/search?query={clean_q}&orientation={orientation}&per_page=4"
        res = requests.get(url, headers={"Authorization": PEXELS_API_KEY}, timeout=15)
        if res.status_code == 200:
            videos = res.json().get("videos", [])
            if videos:
                files = videos[0].get("video_files", [])
                target_file = files[0]
                for f in files:
                    if f.get("width", 0) >= 1080:
                        target_file = f
                        break
                video_url = target_file.get("link")
                v_res = requests.get(video_url, timeout=45)
                if v_res.status_code == 200 and len(v_res.content) > 100000:
                    with open(dest_path, "wb") as f:
                        f.write(v_res.content)
                    return True
    except Exception as e:
        print(f"Pexels notice: {e}", flush=True)
    return False

def fetch_pixabay_video(query: str, dest_path: str) -> bool:
    if not PIXABAY_API_KEY or not query:
        return False
    clean_q = urllib.parse.quote(query.strip()[:60])
    # Prefer motion-graphic / 3D animation loops first (spinning chakras, glowing diyas,
    # temple bell loops) for a more cinematic, less static-slideshow feel. Fall back to
    # any video type if no animation-tagged result is found for this query.
    for video_type in ("animation", "all"):
        try:
            url = f"https://pixabay.com/api/videos/?key={PIXABAY_API_KEY}&q={clean_q}&video_type={video_type}&per_page=4"
            res = requests.get(url, timeout=15)
            if res.status_code == 200:
                hits = res.json().get("hits", [])
                if hits:
                    videos_dict = hits[0].get("videos", {})
                    target = videos_dict.get("large") or videos_dict.get("medium") or videos_dict.get("small")
                    if target and target.get("url"):
                        v_res = requests.get(target.get("url"), timeout=45)
                        if v_res.status_code == 200 and len(v_res.content) > 100000:
                            with open(dest_path, "wb") as f:
                                f.write(v_res.content)
                            return True
        except Exception as e:
            print(f"Pixabay notice ({video_type}): {e}", flush=True)
    return False

def fetch_coverr_video(query: str, dest_path: str) -> bool:
    if not COVERR_API_KEY or not query:
        return False
    try:
        clean_q = urllib.parse.quote(query.strip()[:60])
        url = f"https://api.coverr.co/videos?query={clean_q}&urls=true&page_size=4"
        res = requests.get(url, headers={"Authorization": f"Bearer {COVERR_API_KEY}"}, timeout=15)
        if res.status_code == 200:
            hits = res.json().get("hits", [])
            if hits:
                video_url = (hits[0].get("urls") or {}).get("mp4")
                if video_url:
                    v_res = requests.get(video_url, timeout=45)
                    if v_res.status_code == 200 and len(v_res.content) > 100000:
                        with open(dest_path, "wb") as f:
                            f.write(v_res.content)
                        return True
    except Exception as e:
        print(f"Coverr notice: {e}", flush=True)
    return False

def fetch_multi_source_video(query: str, dest_path: str, orientation: str = "landscape") -> bool:
    # 1. Try Pexels 4K Video
    if fetch_pexels_video(query, dest_path, orientation):
        print(f"  ✅ Video fetched from Pexels 4K ('{query}')", flush=True)
        return True
    # 2. Try Pixabay (3D Sacred Animations & Diyas)
    if fetch_pixabay_video(query, dest_path):
        print(f"  ✅ Video fetched from Pixabay 3D ('{query}')", flush=True)
        return True
    # 3. Try Coverr (free stock B-roll, demo tier)
    if fetch_coverr_video(query, dest_path):
        print(f"  ✅ Video fetched from Coverr ('{query}')", flush=True)
        return True
    return False

# -------------------------------------------------------------
# 2. CHARACTER-ACCURATE CLOUDFLARE FLUX.1 & FALLBACKS
# -------------------------------------------------------------
def generate_cloudflare_flux(prompt: str, dest_path: str, aspect_ratio: str = "16:9") -> bool:
    if not CLOUDFLARE_ACCOUNT_ID or not CLOUDFLARE_API_TOKEN:
        return False
    url = f"https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}/ai/run/@cf/black-forest-labs/flux-1-schnell"
    headers = {
        "Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}",
        "Content-Type": "application/json"
    }
    clean_text = prompt.replace("\n", " ").replace("\"", "").strip()
    final_prompt = f"{clean_text}, Indian mythological devotional art, {aspect_ratio} composition, warm divine lighting, 8k, highly detailed"

    try:
        res = requests.post(url, headers=headers, json={"prompt": final_prompt[:450], "steps": 4}, timeout=50)
        if res.status_code == 200:
            content_type = res.headers.get("content-type", "")
            if "application/json" in content_type:
                data = res.json()
                if "result" in data and "image" in data["result"]:
                    img_bytes = base64.b64decode(data["result"]["image"])
                    with open(dest_path, "wb") as f:
                        f.write(img_bytes)
                    return True
            elif len(res.content) > 5000:
                with open(dest_path, "wb") as f:
                    f.write(res.content)
                return True
    except Exception as e:
        print(f"Cloudflare error: {e}", flush=True)
    return False

def download_pollinations_fallback(prompt: str, img_dest: str, width: int = 1920, height: int = 1080) -> bool:
    clean_text = prompt.replace("\n", " ").replace("\"", "").strip()[:180]
    encoded = urllib.parse.quote(f"{clean_text}, Indian devotional art")
    seed = random.randint(1000, 999999)
    url = f"https://image.pollinations.ai/prompt/{encoded}?width={width}&height={height}&model=turbo&seed={seed}&nologo=true"

    for attempt in range(1, 4):
        try:
            res = requests.get(url, headers=HEADERS, timeout=30)
            if res.status_code == 200 and len(res.content) > 8000:
                with open(img_dest, "wb") as f:
                    f.write(res.content)
                return True
        except Exception:
            pass
        time.sleep(1)

    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c=0x150a00:s={width}x{height}",
        "-vframes", "1", img_dest
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return False

# -------------------------------------------------------------
# 3. AUDIO SYNTHESIS ENGINE (Edge-TTS)
# -------------------------------------------------------------
def get_audio_duration(file_path: str) -> float:
    cmd = [
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", file_path
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
        return float(res.stdout.strip())
    except Exception:
        return 8.0

tts_semaphore = asyncio.Semaphore(2)

async def generate_clean_audio(narration: str, audio_dest: str):
    async with tts_semaphore:
        clean_text = narration.strip() if narration else "हरि ॐ तत्सत्"
        for attempt in range(1, 4):
            try:
                communicate = edge_tts.Communicate(
                    clean_text,
                    voice="hi-IN-MadhurNeural",
                    rate="-3%",
                    pitch="-1Hz"
                )
                await communicate.save(audio_dest)
                if os.path.exists(audio_dest) and os.path.getsize(audio_dest) > 0:
                    return
            except Exception:
                await asyncio.sleep(1.5)

        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
            "-t", "5", "-q:a", "9", "-acodec", "libmp3lame", audio_dest
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

# -------------------------------------------------------------
# 3b. DYNAMIC SOUND-EFFECT ENGINE (Freesound, CC0-only, with local fallback)
# -------------------------------------------------------------
# Each value here is the search phrase sent to Freesound for that soundEffect label.
SOUND_EFFECT_QUERIES = {
    "temple_bell": "temple bell ring",
    "shankh": "conch shell horn blow",
    "om_drone": "om chant drone meditation",
    "flute_swell": "indian bansuri flute swell",
}

def fetch_freesound_effect(effect_name: str, dest_path: str) -> bool:
    if not FREESOUND_API_KEY:
        return False
    query = SOUND_EFFECT_QUERIES.get(effect_name)
    if not query:
        return False
    try:
        clean_q = urllib.parse.quote(query)
        # CC0 ("Creative Commons 0") only - no attribution required, safe for a
        # monetized channel.
        url = (
            f"https://freesound.org/apiv2/search/text/?query={clean_q}"
            f"&filter=license:\"Creative Commons 0\"&fields=id,previews"
            f"&token={FREESOUND_API_KEY}"
        )
        res = requests.get(url, timeout=15)
        if res.status_code == 200:
            results = res.json().get("results", [])
            if results:
                previews = results[0].get("previews", {})
                preview_url = previews.get("preview-hq-mp3") or previews.get("preview-lq-mp3")
                if preview_url:
                    v_res = requests.get(preview_url, timeout=30)
                    if v_res.status_code == 200 and len(v_res.content) > 1000:
                        with open(dest_path, "wb") as f:
                            f.write(v_res.content)
                        return True
    except Exception as e:
        print(f"Freesound notice ({effect_name}): {e}", flush=True)
    return False

def resolve_sound_effect_audio(effect_name: str, dest_path: str) -> None:
    """Guarantees dest_path exists for a scene's sound-effect layer: try a fresh
    CC0 clip from Freesound first, fall back to a checked-in generic clip under
    public/audio/effects_library/<effect_name>.mp3, and fall back to silence
    last so a render never breaks over a missing sound effect."""
    if fetch_freesound_effect(effect_name, dest_path):
        print(f"  ✅ Sound effect '{effect_name}' fetched from Freesound (CC0)", flush=True)
        return
    library_path = f"public/audio/effects_library/{effect_name}.mp3"
    if os.path.exists(library_path):
        shutil.copyfile(library_path, dest_path)
        print(f"  ℹ️ Sound effect '{effect_name}' used from local library fallback", flush=True)
        return
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
        "-t", "1", "-q:a", "9", "-acodec", "libmp3lame", dest_path
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"  ⚠️ Sound effect '{effect_name}' unavailable (no key, no library file) - using silence", flush=True)

# -------------------------------------------------------------
# 4. PROCESS LONG VIDEO SCENES (Pexels + Pixabay + Coverr + FLUX.1)
# -------------------------------------------------------------
def process_long_scene_visual(scene_info):
    idx, scene = scene_info
    prompt = scene.get("imagePrompt") or scene.get("image_prompt", "Indian spiritual story scene")
    media_type = scene.get("mediaType", "auto").lower()

    video_query = scene.get("videoSearchQuery")
    if not video_query:
        words = [w for w in prompt.split() if w.lower() not in ["the", "a", "an", "and", "with", "in", "on", "of", "cinematic", "16:9", "lighting", "shot"]]
        video_query = " ".join(words[:4])

    should_try_video = (media_type == "video") or (media_type == "auto" and idx % 2 == 0)

    if should_try_video and video_query:
        video_name = f"scene_{idx}.mp4"
        video_dest = f"public/images/{video_name}"
        print(f"🎥 [Long Scene {idx}] Searching 4K Video (Pexels + Pixabay + Coverr) for: '{video_query}'...", flush=True)
        if fetch_multi_source_video(video_query, video_dest, orientation="landscape"):
            return video_name

    img_name = f"scene_{idx}.jpg"
    img_dest = f"public/images/{img_name}"
    print(f"🎨 [Long Scene {idx}] Generating FLUX.1 visual: {prompt[:40]}...", flush=True)
    if not generate_cloudflare_flux(prompt, img_dest, aspect_ratio="16:9"):
        download_pollinations_fallback(prompt, img_dest, width=1920, height=1080)
    return img_name

# -------------------------------------------------------------
# 5. PROCESS SHORTS SCENES (9:16 Vertical)
# -------------------------------------------------------------
def process_shorts_scene_visual(scene_info):
    idx, scene = scene_info
    prompt = scene.get("imagePrompt") or scene.get("image_prompt", "Devotional sacred 9:16")
    video_query = scene.get("videoSearchQuery") or "sacred temple diya"

    video_name = f"shorts_scene_{idx}.mp4"
    video_dest = f"public/images/{video_name}"
    print(f"🎥 [Shorts Scene {idx}] Searching Vertical Video (Pexels + Pixabay + Coverr)...", flush=True)
    if fetch_multi_source_video(video_query, video_dest, orientation="portrait"):
        return video_name

    img_name = f"shorts_scene_{idx}.jpg"
    img_dest = f"public/images/{img_name}"
    print(f"🎨 [Shorts Scene {idx}] Generating 9:16 FLUX.1 visual...", flush=True)
    if not generate_cloudflare_flux(f"{prompt}, vertical 9:16 composition", img_dest, aspect_ratio="9:16"):
        download_pollinations_fallback(prompt, img_dest, width=1080, height=1920)
    return img_name

# -------------------------------------------------------------
# 6. MASTER EXECUTION PIPELINE
# -------------------------------------------------------------
async def process():
    print(f"🚀 Starting Multi-Source Production: Long Video ({len(long_scenes)} scenes) + Shorts ({len(shorts_scenes)} scenes)...", flush=True)

    # 1. Background Music fallback
    bgm_path = "public/audio/bgm.mp3"
    if not os.path.exists(bgm_path):
        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
            "-t", "30", "-q:a", "9", "-acodec", "libmp3lame", bgm_path
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # 2. Render High-CTR 16:9 Thumbnail Image
    thumb_prompt = thumbnail_data.get("imagePrompt") or "Lord Krishna radiant divine aura with glowing Sudarshan Chakra, dramatic 8k thumbnail"
    print("🖼️ Generating High-CTR Thumbnail...", flush=True)
    thumb_dest = "public/images/thumbnail.jpg"
    if not generate_cloudflare_flux(thumb_prompt, thumb_dest, aspect_ratio="16:9"):
        download_pollinations_fallback(thumb_prompt, thumb_dest, width=1920, height=1080)
    subprocess.run(["cp", thumb_dest, "out/thumbnail.jpg"], check=False)

    # 3. Parallel Visuals (Pexels + Pixabay + Coverr + FLUX.1 for Long & Shorts)
    long_items = [(i + 1, s) for i, s in enumerate(long_scenes)]
    shorts_items = [(i + 1, s) for i, s in enumerate(shorts_scenes)]

    with ThreadPoolExecutor(max_workers=4) as executor:
        long_visuals = list(executor.map(process_long_scene_visual, long_items))
        shorts_visuals = list(executor.map(process_shorts_scene_visual, shorts_items))

    # 4. Parallel Audio Generation (Long + Shorts)
    audio_tasks = []
    for i, scene in enumerate(long_scenes):
        idx = i + 1
        narration = scene.get("text") or scene.get("narration_chunk", "")
        audio_tasks.append(generate_clean_audio(narration, f"public/audio/chunk_{idx}.mp3"))

    for i, scene in enumerate(shorts_scenes):
        idx = i + 1
        narration = scene.get("text") or scene.get("narration_chunk", "")
        audio_tasks.append(generate_clean_audio(narration, f"public/audio/shorts_chunk_{idx}.mp3"))

    await asyncio.gather(*audio_tasks)

    # 4b. Sound-Effect Layer (Long video only - the shorts payload has no soundEffect field)
    for i, scene in enumerate(long_scenes):
        idx = i + 1
        effect_name = scene.get("soundEffect", "none")
        if effect_name and effect_name != "none":
            resolve_sound_effect_audio(effect_name, f"public/audio/effects/long_effect_{idx}.mp3")

    # 5. Build Remotion Props for Long Video
    enriched_long = []
    for i, scene in enumerate(long_scenes):
        idx = i + 1
        audio_path = f"public/audio/chunk_{idx}.mp3"
        duration = get_audio_duration(audio_path)
        enriched_long.append({
            "scene_number": idx,
            "durationInSeconds": round(duration + 0.3, 2),
            "narration_chunk": scene.get("text", ""),
            "imageFileName": long_visuals[i],
            "soundEffect": scene.get("soundEffect", "none")
        })

    # 6. Build Remotion Props for Shorts Video
    enriched_shorts = []
    for i, scene in enumerate(shorts_scenes):
        idx = i + 1
        audio_path = f"public/audio/shorts_chunk_{idx}.mp3"
        duration = get_audio_duration(audio_path)
        enriched_shorts.append({
            "scene_number": idx,
            "durationInSeconds": round(duration + 0.2, 2),
            "narration_chunk": scene.get("text", ""),
            "imageFileName": shorts_visuals[i]
        })

    # Save props and metadata
    long_props = {
        "title": seo_metadata.get("long_video_title", "Devotional Long Video"),
        "fps": 30,
        "scenes": enriched_long,
        "seo_metadata": seo_metadata
    }
    shorts_props = {
        "title": seo_metadata.get("shorts_title", "Devotional Shorts"),
        "fps": 30,
        "scenes": enriched_shorts,
        "seo_metadata": seo_metadata
    }

    with open("public/props.json", "w", encoding="utf-8") as f:
        json.dump(long_props, f, ensure_ascii=False, indent=2)

    with open("public/props_shorts.json", "w", encoding="utf-8") as f:
        json.dump(shorts_props, f, ensure_ascii=False, indent=2)

    with open("out/metadata.json", "w", encoding="utf-8") as f:
        json.dump(seo_metadata, f, ensure_ascii=False, indent=2)

    print("🎉 All Multi-Source Assets (Pexels + Pixabay + Coverr + FLUX), Thumbnail, Sound Effects, and Metadata ready!", flush=True)

if __name__ == "__main__":
    asyncio.run(process())
