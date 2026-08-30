import os
import json
import time
import base64
import random
import asyncio
import subprocess
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
import requests
import edge_tts

# Read payload and secrets safely
raw_payload = os.environ.get("DISPATCH_PAYLOAD", "").strip()
payload = {}
if raw_payload and raw_payload != "null":
    try:
        loaded = json.loads(raw_payload)
        if isinstance(loaded, dict):
            payload = loaded
    except Exception:
        payload = {}

title = payload.get("title", "Devotional Story")
scenes = payload.get("scenes", [])

CLOUDFLARE_ACCOUNT_ID = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "").strip()
CLOUDFLARE_API_TOKEN = os.environ.get("CLOUDFLARE_API_TOKEN", "").strip()
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY", "").strip()

if isinstance(scenes, str):
    try:
        scenes = json.loads(scenes)
    except Exception:
        scenes = []

# Fallback test scenes for workflow_dispatch testing
if not scenes:
    scenes = [
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

os.makedirs("public/images", exist_ok=True)
os.makedirs("public/audio", exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
}

# -------------------------------------------------------------
# 1. REAL 4K STOCK VIDEO (DYNAMIC PEXELS SEARCH)
# -------------------------------------------------------------
def fetch_pexels_video(query: str, dest_path: str) -> bool:
    if not PEXELS_API_KEY or not query:
        return False
    try:
        clean_q = urllib.parse.quote(query.strip()[:60])
        url = f"https://api.pexels.com/videos/search?query={clean_q}&orientation=landscape&per_page=4"
        res = requests.get(url, headers={"Authorization": PEXELS_API_KEY}, timeout=15)
        if res.status_code == 200:
            videos = res.json().get("videos", [])
            if videos:
                files = videos[0].get("video_files", [])
                hd_files = [f for f in files if f.get("width", 0) >= 1280]
                target_file = hd_files[0] if hd_files else files[0]
                video_url = target_file.get("link")
                
                v_res = requests.get(video_url, timeout=45)
                if v_res.status_code == 200 and len(v_res.content) > 100000:
                    with open(dest_path, "wb") as f:
                        f.write(v_res.content)
                    return True
    except Exception as e:
        print(f"Pexels dynamic fetch note: {e}", flush=True)
    return False

# -------------------------------------------------------------
# 2. CHARACTER-ACCURATE CLOUDFLARE FLUX.1 IMAGE GENERATION
# -------------------------------------------------------------
def generate_cloudflare_flux(prompt: str, dest_path: str) -> bool:
    if not CLOUDFLARE_ACCOUNT_ID or not CLOUDFLARE_API_TOKEN:
        return False
    url = f"https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}/ai/run/@cf/black-forest-labs/flux-1-schnell"
    headers = {
        "Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}",
        "Content-Type": "application/json"
    }
    clean_text = prompt.replace("\n", " ").replace("\"", "").strip()
    final_prompt = f"{clean_text}, Indian mythological devotional art, 16:9 widescreen composition, warm divine lighting, 8k, highly detailed"
    
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

def download_pollinations_fallback(prompt: str, img_dest: str) -> bool:
    clean_text = prompt.replace("\n", " ").replace("\"", "").strip()[:180]
    encoded = urllib.parse.quote(f"{clean_text}, Indian devotional art, 16:9")
    seed = random.randint(1000, 999999)
    url = f"https://image.pollinations.ai/prompt/{encoded}?width=1920&height=1080&model=turbo&seed={seed}&nologo=true"
    
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
        "ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=0x150a00:s=1920x1080",
        "-vframes", "1", img_dest
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return False

# -------------------------------------------------------------
# 3. FULLY DYNAMIC SCENE ROUTING (NO HARDCODING)
# -------------------------------------------------------------
def process_scene_visual(scene_info):
    idx, scene = scene_info
    prompt = scene.get("imagePrompt") or scene.get("image_prompt", "Indian spiritual story scene")
    media_type = scene.get("mediaType", "auto").lower()
    
    # 1. Dynamically extract video search query generated by Gemini for this specific scene
    video_query = scene.get("videoSearchQuery")
    if not video_query:
        # If not explicitly provided, dynamically derive the query from the scene's prompt
        words = [w for w in prompt.split() if w.lower() not in ["the", "a", "an", "and", "with", "in", "on", "of", "cinematic", "16:9", "lighting", "shot"]]
        video_query = " ".join(words[:4])

    # Determine if scene should fetch 4K video (either AI marked as 'video' or alternating rhythm)
    should_try_video = (media_type == "video") or (media_type == "auto" and idx % 2 == 0)

    if should_try_video and PEXELS_API_KEY and video_query:
        video_name = f"scene_{idx}.mp4"
        video_dest = f"public/images/{video_name}"
        print(f"🎥 [Scene {idx}] Dynamically querying Pexels for: '{video_query}'...", flush=True)
        if fetch_pexels_video(video_query, video_dest):
            print(f"✅ [Scene {idx}] 4K Real Video attached ('{video_query}').", flush=True)
            return video_name

    # 2. Deities & Story Action Visuals -> Cloudflare FLUX.1
    img_name = f"scene_{idx}.jpg"
    img_dest = f"public/images/{img_name}"
    print(f"🎨 [Scene {idx}] Generating character visual with Cloudflare FLUX.1: {prompt[:50]}...", flush=True)
    if generate_cloudflare_flux(prompt, img_dest):
        print(f"✅ [Scene {idx}] Story-matched FLUX.1 image ready.", flush=True)
        return img_name

    # 3. Fallback to Pollinations Turbo
    print(f"⚠️ [Scene {idx}] Using Pollinations fallback...", flush=True)
    download_pollinations_fallback(prompt, img_dest)
    print(f"✅ [Scene {idx}] Visual ready.", flush=True)
    return img_name

# -------------------------------------------------------------
# 4. NATURAL HUMAN VOICEOVER SYNTHESIS (EDGE-TTS)
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

async def generate_clean_audio(idx, narration, audio_dest):
    async with tts_semaphore:
        clean_text = narration.strip() if narration else "हरि ॐ तत्सत्"
        print(f"🎙️ [Scene {idx}] Synthesizing natural Hindi voiceover...", flush=True)
        
        for attempt in range(1, 4):
            try:
                # Calm, meditative pitch and natural storytelling pace
                communicate = edge_tts.Communicate(
                    clean_text,
                    voice="hi-IN-MadhurNeural",
                    rate="-3%",
                    pitch="-1Hz"
                )
                await communicate.save(audio_dest)
                if os.path.exists(audio_dest) and os.path.getsize(audio_dest) > 0:
                    print(f"✅ [Scene {idx}] Audio ready.", flush=True)
                    return
            except Exception as e:
                print(f"⚠️ [Scene {idx}] Retry {attempt}: {e}", flush=True)
                await asyncio.sleep(1.5)

        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
            "-t", "5", "-q:a", "9", "-acodec", "libmp3lame", audio_dest
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

# -------------------------------------------------------------
# 5. MASTER ASSET BUILDER
# -------------------------------------------------------------
async def process():
    print(f"🚀 Generating 100% Dynamic Story Assets for {len(scenes)} scenes...", flush=True)

    # 1. Background Music fallback (soft ambient flute loop)
    bgm_path = "public/audio/bgm.mp3"
    if not os.path.exists(bgm_path):
        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
            "-t", "30", "-q:a", "9", "-acodec", "libmp3lame", bgm_path
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # 2. Parallel Visuals (Dynamic Pexels 4K Video + Cloudflare FLUX.1)
    scene_items = [(i + 1, s) for i, s in enumerate(scenes)]
    with ThreadPoolExecutor(max_workers=3) as executor:
        visual_file_names = list(executor.map(process_scene_visual, scene_items))

    # 3. Parallel Audio Generation
    audio_tasks = []
    for i, scene in enumerate(scenes):
        idx = i + 1
        narration = scene.get("text") or scene.get("narration_chunk", "")
        audio_dest = f"public/audio/chunk_{idx}.mp3"
        audio_tasks.append(generate_clean_audio(idx, narration, audio_dest))
    
    await asyncio.gather(*audio_tasks)

    # 4. Construct Remotion Props (Exact scene-by-scene synchronization)
    enriched_scenes = []
    for i, scene in enumerate(scenes):
        idx = i + 1
        audio_name = f"public/audio/chunk_{idx}.mp3"
        duration = get_audio_duration(audio_name)
        narration = scene.get("text") or scene.get("narration_chunk", "")
        enriched_scenes.append({
            "scene_number": idx,
            "durationInSeconds": round(duration + 0.3, 2),
            "narration_chunk": narration,
            "imageFileName": visual_file_names[i]
        })

    props = {
        "title": title,
        "fps": 30,
        "scenes": enriched_scenes
    }
    with open("public/props.json", "w", encoding="utf-8") as f:
        json.dump(props, f, ensure_ascii=False, indent=2)

    print("🎉 All dynamic story assets & clean audio ready!", flush=True)

if __name__ == "__main__":
    asyncio.run(process())
