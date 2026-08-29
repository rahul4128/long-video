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

title = payload.get("title", "Devotional Story")
scenes = payload.get("scenes", [])

CLOUDFLARE_ACCOUNT_ID = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "")
CLOUDFLARE_API_TOKEN = os.environ.get("CLOUDFLARE_API_TOKEN", "")
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY", "")

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

# -------------------------------------------------------------
# 1. STORY-MATCHED CLOUDFLARE FLUX.1 IMAGE GENERATION
# -------------------------------------------------------------
def generate_cloudflare_image(prompt: str, dest_path: str) -> bool:
    if not CLOUDFLARE_ACCOUNT_ID or not CLOUDFLARE_API_TOKEN:
        return False
    url = f"https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}/ai/run/@cf/black-forest-labs/flux-1-schnell"
    headers = {
        "Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}",
        "Content-Type": "application/json"
    }
    
    clean_text = prompt.replace("\n", " ").replace("\"", "").strip()
    final_prompt = f"{clean_text}, cinematic mythological devotional art, 16:9 widescreen composition, warm divine lighting, 8k, highly detailed"
    
    try:
        res = requests.post(url, headers=headers, json={"prompt": final_prompt[:450], "num_steps": 4}, timeout=50)
        if res.status_code == 200 and len(res.content) > 10000:
            with open(dest_path, "wb") as f:
                f.write(res.content)
            return True
        else:
            print(f"Cloudflare FLUX status: {res.status_code}")
    except Exception as e:
        print(f"Cloudflare FLUX note: {e}")
    return False

# -------------------------------------------------------------
# 2. REAL 4K STOCK VIDEO B-ROLL (PEXELS API)
# -------------------------------------------------------------
def fetch_pexels_video(query: str, dest_path: str) -> bool:
    if not PEXELS_API_KEY:
        return False
    try:
        url = f"https://api.pexels.com/videos/search?query={urllib.parse.quote(query)}&orientation=landscape&per_page=5"
        res = requests.get(url, headers={"Authorization": PEXELS_API_KEY}, timeout=15)
        if res.status_code == 200:
            videos = res.json().get("videos", [])
            if videos:
                files = videos[0].get("video_files", [])
                hd_files = [f for f in files if f.get("width", 0) >= 1280]
                target_file = hd_files[0] if hd_files else files[0]
                video_url = target_file.get("link")
                
                v_res = requests.get(video_url, timeout=45)
                if v_res.status_code == 200:
                    with open(dest_path, "wb") as f:
                        f.write(v_res.content)
                    return True
    except Exception as e:
        print(f"Pexels fetch note: {e}")
    return False

# -------------------------------------------------------------
# 3. POLLINATIONS FLUX FALLBACK
# -------------------------------------------------------------
def download_pollinations_image(prompt: str, img_dest: str) -> bool:
    clean_text = prompt.replace("\n", " ").replace("\"", "").strip()[:200]
    encoded = urllib.parse.quote(f"{clean_text}, cinematic devotional art, 16:9")
    seed = random.randint(1000, 999999)
    url = f"https://image.pollinations.ai/prompt/{encoded}?width=1920&height=1080&model=flux&seed={seed}&nologo=true"
    
    for attempt in range(1, 3):
        try:
            res = requests.get(url, headers=HEADERS, timeout=35)
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

def process_scene_visual(scene_info):
    idx, scene = scene_info
    prompt = scene.get("imagePrompt") or scene.get("image_prompt", "Indian spiritual mythological story scene")
    
    # 1. Check if scene is pure environment (temple aarti, diya, river, sunrise) and mix 4K B-Roll
    broll_keywords = ["temple bells", "diya flame", "aarti", "sunrise ghats", "ganga river", "incense smoke"]
    if any(k in prompt.lower() for k in broll_keywords) and (idx % 3 == 0) and PEXELS_API_KEY:
        video_name = f"scene_{idx}.mp4"
        video_dest = f"public/images/{video_name}"
        print(f"🎥 [Scene {idx}] Fetching 4K Stock Video from Pexels...", flush=True)
        if fetch_pexels_video(prompt, video_dest):
            print(f"✅ [Scene {idx}] 4K Video B-Roll attached.", flush=True)
            return video_name

    # 2. Primary: Story-accurate Cloudflare FLUX.1
    img_name = f"scene_{idx}.jpg"
    img_dest = f"public/images/{img_name}"
    print(f"🎨 [Scene {idx}] Generating FLUX.1 story visual: {prompt[:60]}...", flush=True)
    if generate_cloudflare_image(prompt, img_dest):
        print(f"✅ [Scene {idx}] Cloudflare FLUX.1 visual ready.", flush=True)
        return img_name

    # 3. Fallback: Pollinations FLUX
    print(f"⚠️ [Scene {idx}] Using Pollinations FLUX engine...", flush=True)
    download_pollinations_image(prompt, img_dest)
    print(f"✅ [Scene {idx}] Visual ready.", flush=True)
    return img_name

# -------------------------------------------------------------
# 4. HUMANIZED AUDIO SYNTHESIS WITH SSML & MASTERING
# -------------------------------------------------------------
def format_hindi_ssml(text: str) -> str:
    formatted = text.replace("।", "। <break time=\"450ms\"/> ")
    formatted = formatted.replace(",", ", <break time=\"200ms\"/> ")
    formatted = formatted.replace("?", "? <break time=\"450ms\"/> ")
    formatted = formatted.replace("!", "! <break time=\"350ms\"/> ")
    
    return f"""<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="hi-IN">
    <voice name="hi-IN-MadhurNeural">
        <prosody rate="-4%" pitch="-2Hz">
            {formatted}
        </prosody>
    </voice>
</speak>"""

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

async def generate_humanized_audio(idx, narration, raw_audio_dest):
    async with tts_semaphore:
        clean_text = narration.strip() if narration else "हरि ॐ तत्सत्"
        ssml_content = format_hindi_ssml(clean_text)
        
        print(f"🎙️ [Scene {idx}] Synthesizing humanized voiceover...", flush=True)
        for attempt in range(1, 4):
            try:
                communicate = edge_tts.Communicate(ssml_content, "hi-IN-MadhurNeural")
                await communicate.save(raw_audio_dest)
                if os.path.exists(raw_audio_dest) and os.path.getsize(raw_audio_dest) > 0:
                    print(f"✅ [Scene {idx}] Voiceover ready.", flush=True)
                    return
            except Exception:
                try:
                    communicate = edge_tts.Communicate(clean_text, "hi-IN-MadhurNeural", rate="-4%", pitch="-2Hz")
                    await communicate.save(raw_audio_dest)
                    return
                except:
                    await asyncio.sleep(1.5)

        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
            "-t", "5", "-q:a", "9", "-acodec", "libmp3lame", raw_audio_dest
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

# -------------------------------------------------------------
# 5. MASTER PIPELINE
# -------------------------------------------------------------
async def process():
    print(f"🚀 Generating assets for {len(scenes)} story scenes...", flush=True)

    # 1. Background Music fallback
    bgm_path = "public/audio/bgm.mp3"
    if not os.path.exists(bgm_path):
        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
            "-t", "30", "-q:a", "9", "-acodec", "libmp3lame", bgm_path
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # 2. Parallel Visuals
    scene_items = [(i + 1, s) for i, s in enumerate(scenes)]
    with ThreadPoolExecutor(max_workers=3) as executor:
        visual_file_names = list(executor.map(process_scene_visual, scene_items))

    # 3. Parallel Humanized Audio
    audio_tasks = []
    for i, scene in enumerate(scenes):
        idx = i + 1
        narration = scene.get("text") or scene.get("narration_chunk", "")
        audio_dest = f"public/audio/chunk_{idx}.mp3"
        audio_tasks.append(generate_humanized_audio(idx, narration, audio_dest))
    
    await asyncio.gather(*audio_tasks)

    # 4. Construct Remotion Props
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
            "imageFileName": visual_file_names[i]
        })
        audio_files.append(audio_name)

    # 5. Concatenate & Apply Vocal Warmth Filter
    with open("audio_list.txt", "w") as f:
        for a in audio_files:
            f.write(f"file '{os.path.abspath(a)}'\n")

    vocal_filter = "highpass=f=75,equalizer=f=220:t=q:w=1.2:g=3,equalizer=f=3500:t=q:w=1.5:g=1.5,compand=attacks=0.03:decays=0.3:points=-80/-80|-24/-16|0/-3"

    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", "audio_list.txt",
        "-af", vocal_filter,
        "-c:a", "libmp3lame", "-b:a", "192k",
        "public/audio/voiceover.mp3"
    ], check=True)

    # 6. Save props.json
    props = {
        "title": title,
        "fps": 30,
        "scenes": enriched_scenes
    }
    with open("public/props.json", "w", encoding="utf-8") as f:
        json.dump(props, f, ensure_ascii=False, indent=2)

    print("🎉 All story-matched assets & mastered audio ready!", flush=True)

if __name__ == "__main__":
    asyncio.run(process())
