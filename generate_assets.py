import os
import json
import subprocess
from faster_whisper import WhisperModel

payload = json.loads(os.getenv("DISPATCH_PAYLOAD", "{}"))
release_tag = payload.get("asset_release_tag")

os.makedirs("public/videos", exist_ok=True)
os.makedirs("public/audio", exist_ok=True)
os.makedirs("out", exist_ok=True)

# 1. Download video clips from Kaggle release
if release_tag:
    print(f"Downloading video clips from release {release_tag}...")
    subprocess.run(
        f"gh release download {release_tag} -D public/videos --pattern '*.mp4'",
        shell=True,
        check=True
    )

# 2. Generate Voiceover via Edge-TTS (Local CPU)
full_text = "भगवान शिव के रहस्य और उनकी अनंत कृपा की दिव्य कथा।"
with open("temp_script.txt", "w", encoding="utf-8") as f:
    f.write(full_text)

os.system("edge-tts --voice hi-IN-MadhurNeural --file temp_script.txt --write-media public/audio/narration.mp3")

# 3. Word-level Subtitle Timestamps
model = WhisperModel("base", device="cpu", compute_type="int8")
segments, _ = model.transcribe("public/audio/narration.mp3", word_timestamps=True)

captions = []
for segment in segments:
    for word in segment.words:
        captions.append({
            "text": word.word.strip(),
            "startMs": int(word.start * 1000),
            "endMs": int(word.end * 1000)
        })

# 4. Map downloaded clips into props.json
clip_files = sorted([f for f in os.listdir("public/videos") if f.endswith(".mp4")])
scenes = [
    {"id": i + 1, "videoUrl": f"videos/{name}", "durationInFrames": 120}
    for i, name in enumerate(clip_files)
]

props = {
    "audioUrl": "audio/narration.mp3",
    "captions": captions,
    "scenes": scenes
}

with open("public/props.json", "w") as f:
    json.dump(props, f, indent=2)
