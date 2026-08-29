import os
import json
import asyncio
import subprocess
import urllib.parse
import urllib.request
import edge_tts

# Read payload sent from Make.com
raw_payload = os.environ.get("DISPATCH_PAYLOAD", "{}")
payload = json.loads(raw_payload) if raw_payload else {}

title = payload.get("title", "Devotional Story")
scenes = payload.get("scenes", [])

# Handle stringified scenes if passed as JSON string
if isinstance(scenes, str):
    scenes = json.loads(scenes)

os.makedirs("public/images", exist_ok=True)
os.makedirs("public/audio", exist_ok=True)

def get_audio_duration(file_path: str) -> float:
    cmd = [
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", file_path
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
        return float(res.stdout.strip())
    except:
        return 10.0

async def process():
    enriched_scenes = []
    audio_files = []

    for i, scene in enumerate(scenes):
        idx = i + 1
        img_name = f"scene_{idx}.jpg"
        img_dest = f"public/images/{img_name}"
        audio_name = f"public/audio/chunk_{idx}.mp3"

        # 1. Download 16:9 Devotional Visual from Pollinations (Free Flux)
        prompt = scene.get("imagePrompt") or scene.get("image_prompt", "Lord Krishna divine serene 16:9")
        clean_prompt = f"{prompt}, cinematic devotional art, widescreen 16:9, warm golden lighting, temple atmosphere, 8k, photorealistic"
        encoded = urllib.parse.quote(clean_prompt)
        url = f"https://image.pollinations.ai/prompt/{encoded}?width=1920&height=1080&model=flux&nologo=true"
        
        print(f"[{idx}/{len(scenes)}] Downloading image for Scene {idx}...")
        try:
            urllib.request.urlretrieve(url, img_dest)
        except Exception as e:
            print(f"Warning: Image download error ({e}), retrying...")
            urllib.request.urlretrieve(url, img_dest)

        # 2. Synthesize Hindi Voiceover (Madhur - Male or Swara - Female)
        narration = scene.get("text") or scene.get("narration_chunk", "")
        print(f"[{idx}/{len(scenes)}] Synthesizing audio for Scene {idx}...")
        communicate = edge_tts.Communicate(narration, "hi-IN-MadhurNeural", rate="-2%")
        await communicate.save(audio_name)

        # 3. Calculate timing
        duration = get_audio_duration(audio_name)
        enriched_scenes.append({
            "scene_number": idx,
            "durationInSeconds": round(duration + 0.4, 2), # gentle pause
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
