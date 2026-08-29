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

os.makedirs("public/images", exist_ok=True)
os.makedirs("public/audio", exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
}

def download_single_image(scene_info):
    idx, prompt, img_dest = scene_info
    clean_prompt = f"{prompt}, cinematic devotional art, widescreen 16:9, warm golden lighting, temple atmosphere, 8k, photorealistic"
    encoded = urllib.parse.quote(clean_prompt)
    seed = random.randint(1000, 999999)
    
    # Using turbo model with seed for high speed and 100% uptime
    url = f"https://image.pollinations.ai/prompt/{encoded}?width=1920&height=1080&model=turbo&seed={seed}&nologo=true"
    
    print(f"🔄 [Scene {idx}] Generating image...", flush=True)
    for attempt in range(1, 5):
        try:
            res = requests.get(url, headers=HEADERS, timeout=30)
            if res.status_code == 200 and len(res.content) > 10000:
                with open(img_dest, "wb") as f:
                    f.write(res.content)
                print(f"✅ [Scene {idx}] Image downloaded.", flush=True)
                return True
            else:
                print(f"⚠️ [Scene {idx}] Retry {attempt} (status {res.status_code})...", flush=True)
        except Exception as e:
            print(f"⚠️ [Scene {idx}] Retry {attempt} ({e})...", flush=True)
        time.sleep(2)

    # Fallback only if server completely unreachable
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=0x1a0f00:s=1920x1080",
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
        if not clean_text:
            clean_text = "हरि ॐ तत्सत्"
            
        print(f"🎙️ [Scene {idx}] Synthesizing voiceover...", flush=True)
        for attempt in range(1, 4):
            try:
                communicate = edge_tts.Communicate(clean_text, "hi-IN-MadhurNeural", rate="-2%")
                await communicate.save(audio_dest)
                if os.path.exists(audio_dest) and os.path.getsize(audio_dest) > 0:
                    print(f"✅ [Scene {idx}] Voiceover ready.", flush=True)
                    return
            except Exception as e:
                print(f"⚠️ [Scene {idx}] Audio attempt {attempt} retry: {e}", flush=True)
                await asyncio.sleep(1.5)

        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
            "-t", "5", "-q:a", "9", "-acodec", "libmp3lame", audio_dest
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

async def process():
    print(f"🚀 Starting asset generation for {len(scenes)} scenes...", flush=True)

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

    print("⚡ Downloading all scene images...", flush=True)
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
