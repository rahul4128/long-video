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
os.makedirs("public/videos_library", exist_ok=True)
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

def fetch_wikimedia_video(query: str, dest_path: str) -> bool:
    """4th source: Wikimedia Commons - run by the nonprofit Wikimedia
    Foundation (same people behind Wikipedia). Completely free forever, no
    signup, no API key, no subscription, no rate-limit key required for
    this kind of light, occasional use. Bonus for this niche specifically:
    unlike Pexels/Pixabay/Coverr (generic Western stock), Commons actually
    hosts real community-uploaded footage of Indian temples, Diwali/Holi
    festivals, aarti ceremonies, etc. under CC-BY / CC-BY-SA / public-domain
    licenses - often a closer topical match than generic B-roll. Files come
    back as WebM/Ogg (open codecs), so we transcode to .mp4 with ffmpeg
    (already a dependency of this pipeline) right after downloading."""
    if not query:
        return False
    raw_path = dest_path + ".raw"
    try:
        clean_q = urllib.parse.quote(f"filetype:video {query.strip()[:60]}")
        search_url = (
            "https://commons.wikimedia.org/w/api.php?action=query&format=json"
            f"&generator=search&gsrsearch={clean_q}&gsrnamespace=6&gsrlimit=5"
            "&prop=imageinfo&iiprop=url%7Cmime%7Csize"
        )
        # Wikimedia's API etiquette asks for a descriptive User-Agent - not
        # a key, just identifying info in case they ever need to reach out.
        wiki_headers = {"User-Agent": "long-video-devotional-bot/1.0 (automated free stock B-roll fetch)"}
        res = requests.get(search_url, headers=wiki_headers, timeout=15)
        if res.status_code == 200:
            pages = res.json().get("query", {}).get("pages", {})
            for page in pages.values():
                infos = page.get("imageinfo", [])
                if not infos:
                    continue
                mime = infos[0].get("mime", "")
                file_url = infos[0].get("url")
                if not file_url or not mime.startswith("video/"):
                    continue
                v_res = requests.get(file_url, headers=wiki_headers, timeout=45)
                if v_res.status_code == 200 and len(v_res.content) > 100000:
                    with open(raw_path, "wb") as f:
                        f.write(v_res.content)
                    convert = subprocess.run(
                        ["ffmpeg", "-y", "-i", raw_path, "-c:v", "libx264",
                         "-pix_fmt", "yuv420p", "-c:a", "aac", dest_path],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    )
                    if convert.returncode == 0 and os.path.exists(dest_path) and os.path.getsize(dest_path) > 50000:
                        return True
    except Exception as e:
        print(f"Wikimedia Commons notice: {e}", flush=True)
    finally:
        if os.path.exists(raw_path):
            os.remove(raw_path)
    return False

def fetch_local_library_video(search_terms: str, dest_path: str) -> bool:
    """5th and final source: a curated, hand-picked clip you've saved
    yourself under public/videos_library/<keyword>.mp4 (or
    <keyword>_1.mp4, <keyword>_2.mp4, ... for several takes of the same
    keyword - one is picked at random). This is the "guaranteed correct
    clip" tier: Pexels/Pixabay/Coverr/Wikimedia Commons are general-purpose Western
    stock libraries with thin-to-no coverage of devotional/mythological
    Indian terms (Krishna, shankh, aarti, Kurukshetra...), so a one-time
    manual download from a permissively-licensed free site - Mixkit
    (no attribution required), Pixabay, Videvo, or your own Vecteezy/Videezy
    downloads - saved under a keyword name here will always beat a fuzzy
    keyword-search match for your recurring niche scenes, and costs
    nothing to keep using. See public/videos_library/README.md."""
    library_dir = "public/videos_library"
    if not os.path.isdir(library_dir) or not search_terms:
        return False
    words = [w.strip(".,!?").lower() for w in search_terms.split() if len(w) > 2]
    try:
        available = os.listdir(library_dir)
    except Exception:
        return False
    for word in words:
        matches = [
            f for f in available
            if f.lower().startswith(word) and f.lower().endswith(".mp4")
        ]
        if matches:
            chosen = random.choice(matches)
            try:
                shutil.copyfile(os.path.join(library_dir, chosen), dest_path)
                print(f"  📚 Video used from local library ('{chosen}' matched '{word}')", flush=True)
                return True
            except Exception as e:
                print(f"Local library notice: {e}", flush=True)
    return False

# -------------------------------------------------------------
# 1b. NICHE QUERY TRANSLATION (devotional/mythological -> stock-catalog terms)
# -------------------------------------------------------------
# Pexels/Pixabay/Coverr/Wikimedia Commons are general-purpose Western stock libraries.
# Searching them verbatim for mythological proper nouns or Sanskrit/Hindi
# terms ("Krishna", "shankh", "Kurukshetra", "aarti"...) returns zero hits
# far more often than a real match, which is the root cause of "wrong clip"
# - the code then silently falls through to an AI-generated still image
# instead of real B-roll. NICHE_TERM_REWRITES maps each such term to a
# broad, visually-descriptive English phrase a general stock library is
# actually likely to have, so we try progressively more generic queries
# before giving up on finding real footage.
NICHE_TERM_REWRITES = {
    "krishna": "golden deity statue temple",
    "arjuna": "warrior silhouette battlefield",
    "mahabharata": "ancient battlefield war dust",
    "ramayana": "ancient indian palace temple",
    "shankh": "conch shell",
    "conch": "conch shell",
    "diya": "oil lamp flame candle",
    "aarti": "candle flame ritual ceremony",
    "chakra": "spinning glowing energy circle",
    "sudarshan": "golden spinning disc light",
    "dharma": "temple pillars sunlight",
    "karma": "temple pillars sunlight",
    "kurukshetra": "ancient battlefield dust storm",
    "chariot": "ancient wooden chariot",
    "bhagavad": "ancient scripture book",
    "gita": "ancient scripture book",
    "himalayan": "himalaya mountains temple",
    "vedic": "ancient temple ritual",
    "mandir": "hindu temple",
    "puja": "temple ritual ceremony",
}
GENERIC_DEVOTIONAL_FALLBACK = "temple diya candle flame"

def dynamic_ai_query_rewrite(primary_query: str, prompt_text: str) -> list:
    """Fully automatic, zero-setup version of the rewrite step: asks a small
    text model on Cloudflare Workers AI to translate THIS scene's wording
    into generic, visually-concrete English stock-search phrases, at
    runtime. Reuses the CLOUDFLARE_ACCOUNT_ID / CLOUDFLARE_API_TOKEN you
    already have configured for the FLUX image fallback - no new signup, no
    new secret, nothing to add. Unlike NICHE_TERM_REWRITES (a fixed list of
    ~20 words I hand-picked), this keeps working for any future character,
    Sanskrit term, or scene wording you write, without ever touching this
    file again. Returns [] (silently) if Cloudflare isn't configured or the
    call fails for any reason - callers fall back to the static dictionary
    below, so nothing breaks either way."""
    if not CLOUDFLARE_ACCOUNT_ID or not CLOUDFLARE_API_TOKEN:
        return []
    try:
        url = f"https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}/ai/run/@cf/meta/llama-3.1-8b-instruct"
        headers = {"Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}", "Content-Type": "application/json"}
        system_prompt = (
            "You turn a devotional/mythological Indian video scene description into short, "
            "generic English stock-footage search phrases (3-5 words each) that a general "
            "Western stock video library such as Pexels or Pixabay is likely to actually have "
            "footage for. Never include character names, Sanskrit/Hindi words, or the words "
            "'India'/'Indian' - describe only the visual: lighting, objects, action, mood. "
            "Return exactly 3 phrases, one per line, ordered from most specific-but-plausible "
            "to most generic-and-guaranteed-to-exist. No numbering, no extra text, no quotes."
        )
        user_prompt = f"Scene search query: {primary_query}\nScene image prompt: {prompt_text}"
        res = requests.post(
            url, headers=headers, timeout=20,
            json={"messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]},
        )
        if res.status_code == 200:
            text = res.json().get("result", {}).get("response", "")
            phrases = [line.strip("-•* ").strip() for line in text.strip().split("\n")]
            return [p for p in phrases if p][:3]
    except Exception as e:
        print(f"Dynamic query-rewrite notice: {e}", flush=True)
    return []

def build_query_candidates(primary_query: str, prompt_text: str = "") -> list:
    """Turn one niche videoSearchQuery into an ordered list of queries to
    try against every stock source: the original phrase first (it may well
    hit), then AI-generated rewrites from dynamic_ai_query_rewrite() (fully
    automatic, works for any wording, uses your existing Cloudflare key),
    then a static-dictionary rewrite as an offline safety net if Cloudflare
    isn't configured or returned nothing, then the original with untranslated
    niche words simply removed, then a generic devotional B-roll phrase as a
    last resort - so the search chain almost never comes back completely
    empty before falling back to AI image generation."""
    candidates = []
    original = (primary_query or "").strip()
    if original:
        candidates.append(original)

    for ai_phrase in dynamic_ai_query_rewrite(original, prompt_text):
        if ai_phrase not in candidates:
            candidates.append(ai_phrase)

    lowered = f"{original} {prompt_text}".lower()
    rewritten_phrases = []
    for term, synonym in NICHE_TERM_REWRITES.items():
        if term in lowered:
            rewritten_phrases.extend(synonym.split())
    if rewritten_phrases:
        deduped_words = list(dict.fromkeys(rewritten_phrases))[:8]  # cap word count, not char count - avoids cutting a word in half
        rewritten = " ".join(deduped_words)
        if rewritten and rewritten not in candidates:
            candidates.append(rewritten)

    generic_words = [w for w in original.split() if w.lower() not in NICHE_TERM_REWRITES]
    generic_query = " ".join(generic_words).strip()
    if generic_query and generic_query not in candidates:
        candidates.append(generic_query)

    if GENERIC_DEVOTIONAL_FALLBACK not in candidates:
        candidates.append(GENERIC_DEVOTIONAL_FALLBACK)

    return candidates

def fetch_multi_source_video(query: str, dest_path: str, orientation: str = "landscape", prompt_text: str = "") -> bool:
    for candidate in build_query_candidates(query, prompt_text):
        # 1. Try Pexels 4K Video
        if fetch_pexels_video(candidate, dest_path, orientation):
            print(f"  ✅ Video fetched from Pexels 4K ('{candidate}')", flush=True)
            return True
        # 2. Try Pixabay (3D Sacred Animations & Diyas)
        if fetch_pixabay_video(candidate, dest_path):
            print(f"  ✅ Video fetched from Pixabay 3D ('{candidate}')", flush=True)
            return True
        # 3. Try Coverr (free stock B-roll, demo tier)
        if fetch_coverr_video(candidate, dest_path):
            print(f"  ✅ Video fetched from Coverr ('{candidate}')", flush=True)
            return True
        # 4. Try Wikimedia Commons (free forever, no key needed)
        if fetch_wikimedia_video(candidate, dest_path):
            print(f"  ✅ Video fetched from Wikimedia Commons ('{candidate}')", flush=True)
            return True
    # 5. Last resort before AI generation: your own curated local clips
    if fetch_local_library_video(f"{query} {prompt_text}", dest_path):
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
# Several phrasings per soundEffect label, tried in order - CC0-only results are scarce
# for some of these, so one narrow phrase can easily come back empty even though CC0
# clips exist under a slightly different search term.
SOUND_EFFECT_QUERIES = {
    "temple_bell": ["temple bell ring", "temple bell", "bell ring", "bell chime"],
    "shankh": ["conch shell horn blow", "conch shell", "conch horn", "horn blast"],
    "om_drone": ["om chanting drone", "meditation drone ambient", "singing bowl drone", "deep drone ambient"],
    "flute_swell": ["bansuri flute", "indian flute melody", "flute swell", "flute ambient"],
}

def fetch_freesound_effect(effect_name: str, dest_path: str) -> bool:
    if not FREESOUND_API_KEY:
        return False
    queries = SOUND_EFFECT_QUERIES.get(effect_name)
    if not queries:
        return False
    for query in queries:
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
            print(f"Freesound notice ({effect_name}, '{query}'): {e}", flush=True)
    return False

def extract_bgm_clip(dest_path: str, clip_seconds: float = 3.0) -> bool:
    """Fallback tier: cut a short, faded clip from the existing background
    music track (public/audio/bgm.mp3) to use as a generic ambient effect
    layer when Freesound has no CC0 match and no local library file exists
    either. This only produces something audible if bgm.mp3 is itself a real
    music track (i.e. you've checked one in) rather than the silent
    placeholder generated when it's missing - either way it's safe to call."""
    bgm_path = "public/audio/bgm.mp3"
    if not os.path.exists(bgm_path):
        return False
    try:
        bgm_duration = get_audio_duration(bgm_path)
        max_start = max(0.0, bgm_duration - clip_seconds - 0.5)
        start = random.uniform(0.0, max_start) if max_start > 0 else 0.0
        fade_out_start = max(0.0, clip_seconds - 0.5)
        subprocess.run([
            "ffmpeg", "-y", "-ss", f"{start:.2f}", "-t", f"{clip_seconds:.2f}",
            "-i", bgm_path,
            "-af", f"afade=t=in:st=0:d=0.5,afade=t=out:st={fade_out_start:.2f}:d=0.5",
            "-q:a", "9", "-acodec", "libmp3lame", dest_path
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        return os.path.exists(dest_path) and os.path.getsize(dest_path) > 1000
    except Exception as e:
        print(f"BGM-clip fallback notice: {e}", flush=True)
        return False

def resolve_sound_effect_audio(effect_name: str, dest_path: str) -> None:
    """Guarantees dest_path exists for a scene's sound-effect layer, trying
    four tiers in order: (1) a fresh CC0 clip from Freesound (across several
    query phrasings), (2) a checked-in generic clip under
    public/audio/effects_library/<effect_name>.mp3, (3) a short clip lifted
    from the existing bgm.mp3 track, and (4) silence as the last resort, so a
    render never breaks over a missing effect."""
    if fetch_freesound_effect(effect_name, dest_path):
        print(f"  ✅ Sound effect '{effect_name}' fetched from Freesound (CC0)", flush=True)
        return
    library_path = f"public/audio/effects_library/{effect_name}.mp3"
    if os.path.exists(library_path):
        shutil.copyfile(library_path, dest_path)
        print(f"  ℹ️ Sound effect '{effect_name}' used from local library fallback", flush=True)
        return
    if extract_bgm_clip(dest_path):
        print(f"  🎵 Sound effect '{effect_name}' had no Freesound/library match - used a clip from bgm.mp3 instead", flush=True)
        return
    reason = "no FREESOUND_API_KEY set" if not FREESOUND_API_KEY else "no CC0 match found on Freesound"
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
        "-t", "1", "-q:a", "9", "-acodec", "libmp3lame", dest_path
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"  ⚠️ Sound effect '{effect_name}' unavailable ({reason}, no library file, no bgm.mp3) - using silence", flush=True)

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
        print(f"🎥 [Long Scene {idx}] Searching 4K Video (Pexels + Pixabay + Coverr + Wikimedia + Library) for: '{video_query}'...", flush=True)
        if fetch_multi_source_video(video_query, video_dest, orientation="landscape", prompt_text=prompt):
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
    print(f"🎥 [Shorts Scene {idx}] Searching Vertical Video (Pexels + Pixabay + Coverr + Wikimedia + Library)...", flush=True)
    if fetch_multi_source_video(video_query, video_dest, orientation="portrait", prompt_text=prompt):
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

    print("🎉 All Multi-Source Assets (Pexels + Pixabay + Coverr + Wikimedia + Local Library + FLUX), Thumbnail, Sound Effects, and Metadata ready!", flush=True)

if __name__ == "__main__":
    asyncio.run(process())
