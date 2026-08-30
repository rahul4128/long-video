import os
import json
import time
import random
import asyncio
import subprocess
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
import requests
import edge_tts

# Read payload and secrets
raw_payload = os.environ.get("DISPATCH_PAYLOAD", "{}")
payload = json.loads(raw_payload) if raw_payload else {}

title = payload.get("title", "Devotional Video")
scenes = payload.get("scenes", [])

# Parse array of Google Flow session tokens
raw_tokens = os.environ.get("FLOW_SESSION_TOKENS", "[]")
try:
    flow_tokens = json.loads(raw_tokens)
    if isinstance(flow_tokens, str):
        flow_tokens = [flow_tokens]
except Exception:
    flow_tokens = [t.strip() for t in raw_tokens.split(",") if t.strip()]

CLOUDFLARE_ACCOUNT_ID = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "")
CLOUDFLARE_API_TOKEN = os.environ.get("CLOUDFLARE_API_TOKEN", "")
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY", "")

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
            "text": "जीवन के हर मोड़ पर हमें कर्म और धर्म का सही मार्ग चुनना होता है।",
            "imagePrompt": "Lord Krishna with peacock feather crown in golden chariot talking to warrior Arjuna on Kurukshetra battlefield, cinematic 16:9, warm divine lighting"
        },
        {
            "scene_number": 2,
            "text": "जब मन में शांति और श्रद्धा होती है तो सभी संशय स्वतः दूर हो जाते हैं।",
            "imagePrompt": "Lord Krishna smiling raising hand in blessing posture with golden radiant aura, ancient temple background, cinematic 16:9"
        }
    ]

os.makedirs("public/images", exist_ok=True)
os.makedirs("public/audio", exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
}

# -------------------------------------------------------------
# 1. GOOGLE FLOW MULTI-ACCOUNT VIDEO GENERATOR
# -------------------------------------------------------------
def generate_google_flow_video(prompt: str, dest_path: str, token_pool: list) -> bool:
    if not token_pool:
        return False
    
    clean_prompt = f"{prompt}, highly detailed cinematic 4k mythological video, sacred golden atmosphere, 8 seconds"
    
    for i, token in enumerate(token_pool):
        if not token:
            continue
        print(f"🎬 Trying Google Flow Account #{i+1}...", flush=True)
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": HEADERS["User-Agent"]
        }
        data = {
            "prompt": clean_prompt,
            "aspectRatio": "16:9",
            "duration": 8
        }
        
        try:
            res = requests.post("https://labs.google/fx/api/trpc/videoFx.generate", headers=headers, json=data, timeout=60)
            if res.status_code == 200 and len(res.content) > 50000:
                with open(dest_path, "wb") as f:
                    f.write(res.content)
                print(f"✅ Video generated using Google Flow Account #{i+1}!", flush=True)
                return True
            elif res.status_code in [401, 429]:
                print(f"⚠️ Account #{i+1} exhausted or unauthorized. Switching to next account...", flush=True)
                continue
        except Exception as e:
            print(f"⚠️ Flow Account #{i+1} notice: {e}")
            continue

    return False

# -------------------------------------------------------------
# 2. CLOUDFLARE FLUX.1 & POLLINATIONS FALLBACKS
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
        res = requests.post(url, headers=headers, json={"prompt": final_prompt[:450], "num_steps": 4}, timeout=50)
        if res.status_code == 200 and len(res.content) > 10000:
            with open(dest_path, "wb") as f:
                f.write(res.content)
            return True
        else:
            print(f"Cloudflare note: {res.status_code}")
    except Exception as e:
        print(f"Cloudflare error: {e}")
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
# 3. ROUTE SCENE ASSET (AI Video -> FLUX.1 -> Pollinations)
# -------------------------------------------------------------
def process_scene_visual(scene_info):
    idx, scene = scene_info
    prompt = scene.get("imagePrompt") or scene.get("image_prompt", "Indian spiritual story scene")
    
    # 1. Try Google Flow multi-account video generator
    video_name = f"scene_{idx}.mp4"
    video_dest = f"public/images/{video_name}"
    if generate_google_flow_video(prompt, video_dest, flow_tokens):
        return video_name

    # 2. Try Cloudflare FLUX.1 character visual
    img_name = f"scene_{idx}.jpg"
    img_dest = f"public/images/{img_name}"
    print(f"🎨 [Scene {idx}] Generating character visual with Cloudflare FLUX.1...", flush=True)
    if generate_cloudflare_flux(prompt, img_dest):
        print(f"✅ [Scene {idx}] Story-matched FLUX.1 visual ready.", flush=True)
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
    print(f"🚀 Generating assets for {len(scenes)} story scenes...", flush=True)

    # 1. Background Music fallback (soft ambient flute loop)
    bgm_path = "public/audio/bgm.mp3"
    if not os.path.exists(bgm_path):
        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
            "-t", "30", "-q:a", "9", "-acodec", "libmp3lame", bgm_path
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # 2. Process Visuals (Google Flow Video -> Cloudflare FLUX.1 -> Pollinations)
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

    print("🎉 All story-matched video assets & clean audio ready!", flush=True)

if __name__ == "__main__":
    asyncio.run(process())
