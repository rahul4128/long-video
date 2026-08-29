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

# Read payload sent from Make.com
raw_payload = os.environ.get("DISPATCH_PAYLOAD", "{}")
payload = json.loads(raw_payload) if raw_payload else {}

title = payload.get("title", "Devotional Story")
scenes = payload.get("scenes", [])

if isinstance(scenes, str):
    try:
        scenes = json.loads(scenes)
    except Exception:
        scenes = []

# Fallback test scenes for direct workflow_dispatch testing
if not scenes:
    scenes = [
        {
            "scene_number": 1,
            "text": "जीवन के हर मोड़ पर हमें कर्म और धर्म का सही मार्ग चुनना होता है।",
            "imagePrompt": "Lord Krishna golden aura standing in serene ancient temple at sunrise 16:9"
        },
        {
            "scene_number": 2,
            "text": "जब मन में शांति और श्रद्धा होती है तो सभी संशय स्वतः दूर हो जाते हैं।",
            "imagePrompt": "Ancient Himalayan spiritual temple with glowing diya flames golden light 16:9"
        }
    ]

os.makedirs("public/images", exist_ok=True)
os.makedirs("public/audio", exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
}

# Themed Devotional Fallback Pool (Ensures distinct 1080p visuals even during complete AI server outages)
DEVOTIONAL_FALLBACK_POOL = [
    "https://images.unsplash.com/photo-1545128485-c400e7702796?auto=format&fit=crop&w=1920&q=80", # Ancient Indian Temple
    "https://images.unsplash.com/photo-1609766857041-ed402ea8069a?auto=format&fit=crop&w=1920&q=80", # Glowing Diya & Aarti
    "https://images.unsplash.com/photo-1561361058-c24cecae35ca?auto=format&fit=crop&w=1920&q=80", # Himalayan Sunrise Temple
    "https://images.unsplash.com/photo-1582510003544-4d00b7f74220?auto=format&fit=crop&w=1920&q=80", # Sacred River Ghats
    "https://images.unsplash.com/photo-1518709268805-4e9042af9f23?auto=format&fit=crop&w=1920&q=80", # Spiritual Golden Light
    "https://images.unsplash.com/photo-1506744038136-46273834b3fb?auto=format&fit=crop&w=1920&q=80", # Serene Divine Nature
    "https://images.unsplash.com/photo-1519681393784-d120267933ba?auto=format&fit=crop&w=1920&q=80", # Divine Mountain Peaks
    "https://images.unsplash.com/photo-1470071459604-3b5ec3a7fe05?auto=format&fit=crop&w=1920&q=80"  # Golden Sunrise Mist
]

def fetch_lexica_image(prompt: str) -> str:
    """Searches Lexica Art database for pre-generated high quality AI images."""
    try:
        clean_q = urllib.parse.quote(prompt[:80])
        res = requests.get(f"https://lexica.art/api/v1/search?q={clean_q}", headers=HEADERS, timeout=10)
        if res.status_code == 200:
            data = res.json()
            images = data.get("images", [])
            if images and len(images) > 0:
                return images[0].get("src", "")
    except Exception:
        pass
    return ""

def download_single_image(scene_info):
    idx, prompt, img_dest = scene_info
    
    clean_text = prompt.replace("\n", " ").replace("\"", "").strip()
    trimmed_prompt = clean_text[:140]
    final_prompt = f"{trimmed_prompt}, devotional cinematic art, golden lighting, temple atmosphere, 16:9"
    encoded = urllib.parse.quote(final_prompt[:200])
    seed = random.randint(1000, 999999)
    
    # 8-Tier Multi-Engine URLs
    providers = [
        ("Pollinations Turbo 1080p", f"https://image.pollinations.ai/prompt/{encoded}?width=1920&height=1080&model=turbo&seed={seed}&nologo=true"),
        ("Pollinations Flux 1080p", f"https://image.pollinations.ai/prompt/{encoded}?width=1920&height=1080&model=flux&seed={seed}&nologo=true"),
        ("Pollinations Realism", f"https://image.pollinations.ai/prompt/{encoded}?width=1920&height=1080&model=flux-realism&seed={seed}&nologo=true"),
        ("Pollinations 720p Fast", f"https://image.pollinations.ai/prompt/{encoded}?width=1280&height=720&model=turbo&seed={seed}&nologo=true"),
        ("Pollinations SDXL", f"https://image.pollinations.ai/prompt/{encoded}?width=1920&height=1080&model=sdxl&seed={seed}&nologo=true"),
    ]

    print(f"🔄 [Scene {idx}] Generating visual...", flush=True)

    # 1. Try Pollinations Multi-Models
    for name, url in providers:
        try:
            res = requests.get(url, headers=HEADERS, timeout=35)
            if res.status_code == 200 and len(res.content) > 8000:
                with open(img_dest, "wb") as f:
                    f.write(res.content)
                print(f"✅ [Scene {idx}] Success via {name}.", flush=True)
                return True
        except Exception:
            continue
        time.sleep(0.5)

    # 2. Try Lexica Art API
    print(f"⚠️ [Scene {idx}] Checking Lexica AI database...", flush=True)
    lexica_url = fetch_lexica_image(trimmed_prompt)
    if lexica_url:
        try:
            res = requests.get(lexica_url, headers=HEADERS, timeout=20)
            if res.status_code == 200 and len(res.content) > 8000:
                with open(img_dest, "wb") as f:
                    f.write(res.content)
                print(f"✅ [Scene {idx}] Success via Lexica Art.", flush=True)
                return True
        except Exception:
            pass

    # 3. Dedicated Themed Devotional Image Pool
    print(f"⚠️ [Scene {idx}] Using curated high-res devotional background...", flush=True)
    pool_url = DEVOTIONAL_FALLBACK_POOL[(idx - 1) % len(DEVOTIONAL_FALLBACK_POOL)]
    try:
        res = requests.get(pool_url, headers=HEADERS, timeout=20)
        if res.status_code == 200:
            with open(img_dest, "wb") as f:
                f.write(res.content)
            print(f"✅ [Scene {idx}] Devotional background assigned.", flush=True)
            return True
    except Exception:
        pass

    # 4. Ultimate Local Fallback (Dark Temple Amber Frame)
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=0x150a00:s=1920x1080",
        "-vframes", "1", img_dest
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return False

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

async def generate_single_audio(idx, narration, audio_dest):
    async with tts_semaphore:
        clean_text = narration.strip() if narration else "हरि ॐ तत्सत्"
        print(f"🎙️ [Scene {idx}] Synthesizing voiceover...", flush=True)
        for attempt in range(1, 4):
            try:
                communicate = edge_tts.Communicate(clean_text, "hi-IN-MadhurNeural", rate="-2%")
                await communicate.save(audio_dest)
                if os.path.exists(audio_dest) and os.path.getsize(audio_dest) > 0:
                    print(f"✅ [Scene {idx}] Voiceover ready.", flush=True)
                    return
            except Exception as e:
                print(f"⚠️ [Scene {idx}] Audio retry {attempt}: {e}", flush=True)
                await asyncio.sleep(1.5)

        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
            "-t", "5", "-q:a", "9", "-acodec", "libmp3lame", audio_dest
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

async def process():
    print(f"🚀 Starting generation for {len(scenes)} scenes...", flush=True)

    # 1. Background Music fallback
    bgm_path = "public/audio/bgm.mp3"
    if not os.path.exists(bgm_path):
        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
            "-t", "30", "-q:a", "9", "-acodec", "libmp3lame", bgm_path
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # 2. Parallel Image Downloads
    image_tasks = []
    for i, scene in enumerate(scenes):
        idx = i + 1
        prompt = scene.get("imagePrompt") or scene.get("image_prompt", "Indian spiritual temple golden lighting 16:9")
        img_dest = f"public/images/scene_{idx}.jpg"
        image_tasks.append((idx, prompt, img_dest))

    print("⚡ Fetching all scene visuals in parallel...", flush=True)
    with ThreadPoolExecutor(max_workers=3) as executor:
        list(executor.map(download_single_image, image_tasks))

    # 3. Parallel Audio Generation
    print("⚡ Synthesizing scene voiceovers...", flush=True)
    audio_tasks = []
    for i, scene in enumerate(scenes):
        idx = i + 1
        narration = scene.get("text") or scene.get("narration_chunk", "")
        audio_dest = f"public/audio/chunk_{idx}.mp3"
        audio_tasks.append(generate_single_audio(idx, narration, audio_dest))
    
    await asyncio.gather(*audio_tasks)

    # 4. Measure durations and build Remotion props
    enriched_scenes = []
    audio_files = []
    for i, scene in enumerate(scenes):
        idx = i + 1
        audio_name = f"public/audio/chunk_{idx}.mp3"
        duration = get_audio_duration(audio_name)
        narration = scene.get("text") or scene.get("narration_chunk", "")
        enriched_scenes.append({
            "scene_number": idx,
            "durationInSeconds": round(duration + 0.4, 2),
            "narration_chunk": narration,
            "imageFileName": f"scene_{idx}.jpg"
        })
        audio_files.append(audio_name)

    # 5. Concatenate audio
    with open("audio_list.txt", "w") as f:
        for a in audio_files:
            f.write(f"file '{os.path.abspath(a)}'\n")

    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", "audio_list.txt", "-c", "copy", "public/audio/voiceover.mp3"
    ], check=True)

    # 6. Save props
    props = {
        "title": title,
        "fps": 30,
        "scenes": enriched_scenes
    }
    with open("public/props.json", "w", encoding="utf-8") as f:
        json.dump(props, f, ensure_ascii=False, indent=2)

    print("🎉 All assets & props.json generated successfully!", flush=True)

if __name__ == "__main__":
    asyncio.run(process())
