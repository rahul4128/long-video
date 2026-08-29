import os
import json
import time
import asyncio
import subprocess
import urllib.parse
import requests
import edge_tts

# Read payload sent from Make.com
raw_payload = os.environ.get("DISPATCH_PAYLOAD", "{}")
payload = json.loads(raw_payload) if raw_payload else {}

title = payload.get("title", "Devotional Story")
scenes = payload.get("scenes", [])

# Handle stringified scenes if passed as JSON string
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

def download_file_with_retry(url: str, dest_path: str, max_retries: int = 3):
    """Downloads a file using requests with browser headers and retry logic."""
    for attempt in range(1, max_retries + 1):
        try:
            response = requests.get(url, headers=HEADERS, timeout=60)
            if response.status_code == 200:
                with open(dest_path, "wb") as f:
                    f.write(response.content)
                return True
            else:
                print(f"Attempt {attempt}: Received status code {response.status_code}")
        except Exception as e:
            print(f"Attempt {attempt} failed: {e}")
        time.sleep(2)
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

async def process():
    enriched_scenes = []
    audio_files = []

    # Ensure background music exists (or generate gentle ambient silence if missing)
    bgm_path = "public/audio/bgm.mp3"
    if not os.path.exists(bgm_path):
        print("Creating placeholder background track...")
        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
            "-t", "30", "-q:a", "9", "-acodec", "libmp3lame", bgm_path
        ], check=True)

    print(f"Processing {len(scenes)} scenes...")

    for i, scene in enumerate(scenes):
        idx = i + 1
        img_name = f"scene_{idx}.jpg"
        img_dest = f"public/images/{img_name}"
        audio_name = f"public/audio/chunk_{idx}.mp3"

        # 1. Download 16:9 Devotional Visual from Pollinations
        prompt = scene.get("imagePrompt") or scene.get("image_prompt", "Indian spiritual temple golden lighting 16:9")
        clean_prompt = f"{prompt}, cinematic devotional art, widescreen 16:9, warm golden lighting, temple atmosphere, 8k, photorealistic"
        encoded = urllib.parse.quote(clean_prompt)
        url = f"https://image.pollinations.ai/prompt/{encoded}?width=1920&height=1080&model=flux&nologo=true"
        
        print(f"[{idx}/{len(scenes)}] Downloading image for Scene {idx}...")
        success = download_file_with_retry(url, img_dest)
        if not success:
            # Fallback placeholder if image API is busy
            print(f"Using fallback image for scene {idx}")
            subprocess.run([
                "ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=0x1a0f00:s=1920x1080",
                "-vframes", "1", img_dest
            ], check=True)

        # 2. Synthesize Hindi Voiceover
        narration = scene.get("text") or scene.get("narration_chunk", "")
        print(f"[{idx}/{len(scenes)}] Synthesizing audio for Scene {idx}...")
        communicate = edge_tts.Communicate(narration, "hi-IN-MadhurNeural", rate="-2%")
        await communicate.save(audio_name)

        # 3. Calculate audio timing
        duration = get_audio_duration(audio_name)
        enriched_scenes.append({
            "scene_number": idx,
            "durationInSeconds": round(duration + 0.4, 2),
            "narration_chunk": narration,
            "imageFileName": img_name
        })
        audio_files.append(audio_name)

    # 4. Merge audio chunks into voiceover.mp3
    with open("audio_list.txt", "w") as f:
        for a in audio_files:
            f.write(f"file '{os.path.abspath(a)}'\n")

    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", "audio_list.txt", "-c", "copy", "public/audio/voiceover.mp3"
    ], check=True)

    # 5. Export props.json for Remotion
    props = {
        "title": title,
        "fps": 30,
        "scenes": enriched_scenes
    }
    with open("public/props.json", "w", encoding="utf-8") as f:
        json.dump(props, f, ensure_ascii=False, indent=2)

    print("✅ All assets and public/props.json generated successfully.")

if __name__ == "__main__":
    asyncio.run(process())
