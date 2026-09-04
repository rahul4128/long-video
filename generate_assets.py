import os
import re
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
HUGGINGFACE_API_KEY = os.environ.get("HUGGINGFACE_API_KEY", "").strip()
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
# 0b. STOCK-CLIP RELEVANCE SCORING (keyword overlap against scene wording)
# -------------------------------------------------------------
# Every fetch_*_video() below used to just take hit #1 from its API and trust
# it blindly - the search endpoint's own relevance ranking was the only
# safeguard, which for this niche (Krishna/Kurukshetra/aarti searched against
# generic Western stock catalogs) is often too loose: a query like "golden
# deity statue temple" can just as easily return a Buddhist temple in
# Thailand as anything a viewer reads as "this devotional Hindu story", and a
# short/ambiguous query like "conch shell" can return a beach photo-shoot
# clip with a shell prop instead of a ritual moment. This scores each
# candidate hit's own descriptive text (Pixabay's tags, Coverr's title/tags,
# Wikimedia's page title, Pexels' URL slug) against the words actually in
# THIS scene's search query + imagePrompt, and only accepts a hit that shares
# at least one real keyword - otherwise that source is treated as a miss for
# this scene and the caller falls through to the next source/candidate query,
# same philosophy as the "no generic catch-all" rule in build_query_candidates()
# below: better to run out of real matches than show something confidently
# wrong.
_STOPWORDS = {
    "the", "a", "an", "and", "or", "with", "in", "on", "of", "for", "to", "at",
    "is", "are", "by", "from", "this", "that", "scene", "cinematic", "shot",
    "lighting", "composition", "16:9", "9:16", "divine", "warm", "file",
}

def _extract_keywords(*texts: str) -> set:
    words = set()
    for text in texts:
        if not text:
            continue
        for raw in re.split(r"[\s/_\-.,!?()]+", str(text).lower()):
            if len(raw) > 2 and raw not in _STOPWORDS:
                words.add(raw)
    return words

def _best_scoring_index(candidate_texts: list, target_keywords):
    """Returns (best_index, best_score, any_text_available) for a list of
    candidate descriptive strings (one per API hit, "" where a source gives
    no usable text). any_text_available is False when every hit had no text
    at all, so callers fall back to "just take hit #1" rather than reject a
    source that structurally can't be scored."""
    if not target_keywords:
        return 0, 0, False
    if not any(candidate_texts):
        return 0, 0, False
    scores = [len(_extract_keywords(t) & target_keywords) for t in candidate_texts]
    best_index = max(range(len(scores)), key=lambda i: scores[i])
    return best_index, scores[best_index], True

# -------------------------------------------------------------
# 1. MULTI-PLATFORM STOCK VIDEO ENGINE (Pexels + Pixabay + Coverr)
# -------------------------------------------------------------
def fetch_pexels_video(query: str, dest_path: str, orientation: str = "landscape", target_keywords: set = None) -> bool:
    if not PEXELS_API_KEY or not query:
        return False
    try:
        clean_q = urllib.parse.quote(query.strip()[:60])
        # per_page raised 4 -> 6: gives the relevance scorer below a bigger
        # pool to pick a genuine match from, instead of only ever choosing
        # between whichever 4 hits happened to sort first.
        url = f"https://api.pexels.com/videos/search?query={clean_q}&orientation={orientation}&per_page=6"
        res = requests.get(url, headers={"Authorization": PEXELS_API_KEY}, timeout=15)
        if res.status_code == 200:
            videos = res.json().get("videos", [])
            if not videos:
                return False
            # Pexels doesn't expose tags on video search results, but its own
            # URL slug (".../video/a-monk-praying-at-a-temple-1571995/") is
            # genuinely descriptive - score each hit's slug against this
            # scene's wording and prefer the best match over hit #1.
            best_idx, best_score, scorable = _best_scoring_index(
                [v.get("url", "") for v in videos], target_keywords
            )
            if scorable and best_score == 0:
                return False
            chosen = videos[best_idx] if scorable else videos[0]
            files = chosen.get("video_files", [])
            # Pick the SMALLEST file that's still >=1080p, not just the first
            # one that clears the bar - Pexels' video_files aren't size-ordered,
            # so the naive "first match" could just as easily grab a 4K file.
            # A 4K clip takes ~4x longer to download AND ~4x longer for Remotion
            # to decode frame-by-frame during render, for zero visible quality
            # gain in a 1920x1080 output composition.
            hd_files = sorted(
                (f for f in files if f.get("width", 0) >= 1080),
                key=lambda f: f.get("width", 0),
            )
            target_file = hd_files[0] if hd_files else (files[0] if files else {})
            video_url = target_file.get("link")
            if not video_url:
                return False
            v_res = requests.get(video_url, timeout=45)
            if v_res.status_code == 200 and len(v_res.content) > 100000:
                with open(dest_path, "wb") as f:
                    f.write(v_res.content)
                return True
    except Exception as e:
        print(f"Pexels notice: {e}", flush=True)
    return False

def fetch_pixabay_video(query: str, dest_path: str, target_keywords: set = None) -> bool:
    if not PIXABAY_API_KEY or not query:
        return False
    clean_q = urllib.parse.quote(query.strip()[:60])
    # Prefer motion-graphic / 3D animation loops first (spinning chakras, glowing diyas,
    # temple bell loops) for a more cinematic, less static-slideshow feel. Fall back to
    # any video type if no animation-tagged result is found for this query.
    for video_type in ("animation", "all"):
        try:
            url = f"https://pixabay.com/api/videos/?key={PIXABAY_API_KEY}&q={clean_q}&video_type={video_type}&per_page=6"
            res = requests.get(url, timeout=15)
            if res.status_code == 200:
                hits = res.json().get("hits", [])
                if not hits:
                    continue
                # Pixabay hits carry a real, usually-thorough "tags" field -
                # the strongest relevance signal of any source here.
                best_idx, best_score, scorable = _best_scoring_index(
                    [h.get("tags", "") for h in hits], target_keywords
                )
                if scorable and best_score == 0:
                    continue
                chosen = hits[best_idx] if scorable else hits[0]
                videos_dict = chosen.get("videos", {})
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

def _coverr_tags_text(hit: dict) -> str:
    tags = hit.get("tags") or []
    if isinstance(tags, str):
        return tags
    return " ".join(str(t) for t in tags)

def fetch_coverr_video(query: str, dest_path: str, target_keywords: set = None) -> bool:
    if not COVERR_API_KEY or not query:
        return False
    try:
        clean_q = urllib.parse.quote(query.strip()[:60])
        url = f"https://api.coverr.co/videos?query={clean_q}&urls=true&page_size=6"
        res = requests.get(url, headers={"Authorization": f"Bearer {COVERR_API_KEY}"}, timeout=15)
        if res.status_code == 200:
            hits = res.json().get("hits", [])
            if not hits:
                return False
            best_idx, best_score, scorable = _best_scoring_index(
                [f"{h.get('title', '')} {_coverr_tags_text(h)}" for h in hits],
                target_keywords,
            )
            if scorable and best_score == 0:
                return False
            chosen = hits[best_idx] if scorable else hits[0]
            video_url = (chosen.get("urls") or {}).get("mp4")
            if video_url:
                v_res = requests.get(video_url, timeout=45)
                if v_res.status_code == 200 and len(v_res.content) > 100000:
                    with open(dest_path, "wb") as f:
                        f.write(v_res.content)
                    return True
    except Exception as e:
        print(f"Coverr notice: {e}", flush=True)
    return False

def fetch_wikimedia_video(query: str, dest_path: str, target_keywords: set = None) -> bool:
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
        # gsrlimit raised 5 -> 8: more candidates for the relevance scorer to
        # choose the best-titled match from.
        search_url = (
            "https://commons.wikimedia.org/w/api.php?action=query&format=json"
            f"&generator=search&gsrsearch={clean_q}&gsrnamespace=6&gsrlimit=8"
            "&prop=imageinfo&iiprop=url%7Cmime%7Csize"
        )
        # Wikimedia's API etiquette asks for a descriptive User-Agent - not
        # a key, just identifying info in case they ever need to reach out.
        wiki_headers = {"User-Agent": "long-video-devotional-bot/1.0 (automated free stock B-roll fetch)"}
        res = requests.get(search_url, headers=wiki_headers, timeout=15)
        if res.status_code != 200:
            return False
        pages = res.json().get("query", {}).get("pages", {})
        candidates = []
        for page in pages.values():
            infos = page.get("imageinfo", [])
            if not infos:
                continue
            mime = infos[0].get("mime", "")
            file_url = infos[0].get("url")
            if not file_url or not mime.startswith("video/"):
                continue
            candidates.append((page.get("title", ""), file_url))
        if not candidates:
            return False

        # Commons page titles are genuinely descriptive (e.g. "File:Ganesh
        # Chaturthi immersion procession Mumbai.webm") - score them and try
        # the best-matching candidates first, falling through to the next
        # one if a download/transcode fails, instead of only ever trying
        # whichever page the search API happened to rank first.
        best_idx, best_score, scorable = _best_scoring_index(
            [title for title, _ in candidates], target_keywords
        )
        if scorable and best_score == 0:
            return False
        ordered = candidates
        if scorable:
            ordered = sorted(
                candidates,
                key=lambda c: len(_extract_keywords(c[0]) & target_keywords),
                reverse=True,
            )

        for _title, file_url in ordered:
            v_res = requests.get(file_url, headers=wiki_headers, timeout=45)
            if v_res.status_code == 200 and len(v_res.content) > 100000:
                with open(raw_path, "wb") as f:
                    f.write(v_res.content)
                convert = subprocess.run(
                    # Cap at 1920px wide (scale is a no-op if the source is
                    # already smaller) - Commons videos can come back at very
                    # high source resolution, and decoding that during Remotion
                    # render costs real minutes for zero visible gain in a
                    # 1920x1080 composition. "-2" keeps height even (required
                    # by yuv420p) while preserving aspect ratio.
                    ["ffmpeg", "-y", "-i", raw_path, "-vf", "scale='min(1920,iw)':-2",
                     "-c:v", "libx264", "-preset", "veryfast",
                     "-pix_fmt", "yuv420p", "-c:a", "aac", dest_path],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                if convert.returncode == 0 and os.path.exists(dest_path) and os.path.getsize(dest_path) > 50000:
                    return True
            if os.path.exists(raw_path):
                os.remove(raw_path)
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
    niche words simply removed.

    Deliberately NOT included: a generic catch-all phrase (e.g. "temple diya
    candle flame") tried against every remaining scene. That used to be the
    single biggest source of visibly wrong clips - once every real candidate
    above comes up empty, forcing a totally unrelated scene (a battlefield
    beat, say) to match on "temple diya candle flame" just because it's the
    only thing left to try is how you get a temple video playing under a
    battlefield line. It's better to run out of candidates and fall through
    to a purpose-built AI image (see fetch_multi_source_video) than to show
    footage that's confidently wrong."""
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

    return candidates

def fetch_multi_source_video(query: str, dest_path: str, orientation: str = "landscape", prompt_text: str = "") -> bool:
    for candidate in build_query_candidates(query, prompt_text):
        # The relevance target is the candidate query itself plus the scene's
        # own imagePrompt (already visually descriptive) - NOT the original
        # unrewritten query, so a rewritten candidate like "candle flame
        # ritual ceremony" is scored against exactly the words a stock hit
        # would need to match, while still crediting extra descriptive words
        # from the scene (e.g. "golden", "battlefield") if present.
        target_keywords = _extract_keywords(candidate, prompt_text)
        # 1. Try Pexels 4K Video
        if fetch_pexels_video(candidate, dest_path, orientation, target_keywords):
            print(f"  ✅ Video fetched from Pexels 4K ('{candidate}')", flush=True)
            return True
        # 2. Try Pixabay (3D Sacred Animations & Diyas)
        if fetch_pixabay_video(candidate, dest_path, target_keywords):
            print(f"  ✅ Video fetched from Pixabay 3D ('{candidate}')", flush=True)
            return True
        # 3. Try Coverr (free stock B-roll, demo tier)
        if fetch_coverr_video(candidate, dest_path, target_keywords):
            print(f"  ✅ Video fetched from Coverr ('{candidate}')", flush=True)
            return True
        # 4. Try Wikimedia Commons (free forever, no key needed)
        if fetch_wikimedia_video(candidate, dest_path, target_keywords):
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

def generate_huggingface_image(prompt: str, dest_path: str, aspect_ratio: str = "16:9") -> bool:
    """2nd AI-image tier - only runs if HUGGINGFACE_API_KEY is set (harmless
    no-op otherwise, same pattern as the other optional keys). Uses the same
    FLUX.1-schnell model family as the Cloudflare tier above (via Hugging
    Face's serverless Inference Providers), so this is mainly a fallback for
    when Cloudflare is unset, rate-limited, or briefly erroring - not a
    different visual style. Get a free token at huggingface.co/settings/tokens
    (create one with "Make calls to Inference Providers" permission)."""
    if not HUGGINGFACE_API_KEY or not prompt:
        return False
    url = "https://router.huggingface.co/hf-inference/models/black-forest-labs/FLUX.1-schnell"
    headers = {
        "Authorization": f"Bearer {HUGGINGFACE_API_KEY}",
        "Content-Type": "application/json",
    }
    clean_text = prompt.replace("\n", " ").replace("\"", "").strip()
    final_prompt = f"{clean_text}, Indian mythological devotional art, {aspect_ratio} composition, warm divine lighting, 8k, highly detailed"
    width, height = (1024, 576) if aspect_ratio == "16:9" else (576, 1024)
    try:
        res = requests.post(
            url, headers=headers, timeout=50,
            json={
                "inputs": final_prompt[:450],
                "parameters": {"width": width, "height": height, "num_inference_steps": 4},
            },
        )
        content_type = res.headers.get("content-type", "")
        if res.status_code == 200 and content_type.startswith("image/"):
            with open(dest_path, "wb") as f:
                f.write(res.content)
            return True
        if res.status_code != 200:
            # A cold model (503, "currently loading") or a rate limit (429) both
            # land here - either way, don't retry-loop, just fall through to the
            # next tier so a slow/busy HF endpoint never becomes a slow render.
            print(f"Hugging Face notice: HTTP {res.status_code} - {res.text[:200]}", flush=True)
    except Exception as e:
        print(f"Hugging Face notice: {e}", flush=True)
    return False

def generate_ai_image(prompt: str, dest_path: str, aspect_ratio: str = "16:9",
                       pollinations_width: int = 1920, pollinations_height: int = 1080) -> None:
    """Single entry point for the AI-image fallback chain: Cloudflare FLUX.1
    (if configured) -> Hugging Face FLUX.1-schnell (if configured) ->
    Pollinations (no key needed, always works). Guarantees dest_path exists
    when it returns, same contract as resolve_sound_effect_audio()."""
    if generate_cloudflare_flux(prompt, dest_path, aspect_ratio=aspect_ratio):
        return
    if generate_huggingface_image(prompt, dest_path, aspect_ratio=aspect_ratio):
        print("  ✅ Image fetched from Hugging Face (FLUX.1-schnell)", flush=True)
        return
    download_pollinations_fallback(prompt, dest_path, width=pollinations_width, height=pollinations_height)

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

async def generate_clean_audio(narration: str, audio_dest: str) -> list:
    """Synthesizes narration and returns word-level caption timing captured
    from edge-tts's WordBoundary events during streaming synthesis - a list
    of {"word", "start", "end"} in seconds, relative to the start of THIS
    clip. This is what powers the word-by-word synced captions in
    Subtitles.tsx (a real retention/accessibility upgrade over one static
    sentence sitting on screen for the whole scene). Also loudness-normalizes
    the narration to a consistent target (single-pass loudnorm, ~-16 LUFS)
    so volume doesn't drift scene-to-scene or video-to-video.

    Returns [] if word timing couldn't be captured - Subtitles.tsx falls
    back to the old static full-sentence caption in that case, so a render
    never breaks over it."""
    async with tts_semaphore:
        clean_text = narration.strip() if narration else "हरि ॐ तत्सत्"
        raw_path = audio_dest + ".raw.mp3"
        for attempt in range(1, 4):
            try:
                communicate = edge_tts.Communicate(
                    clean_text,
                    voice="hi-IN-MadhurNeural",
                    rate="-3%",
                    pitch="-1Hz"
                )
                submaker = edge_tts.SubMaker()
                audio_bytes = bytearray()
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        audio_bytes.extend(chunk["data"])
                    elif chunk["type"] == "WordBoundary":
                        submaker.feed(chunk)

                if audio_bytes:
                    with open(raw_path, "wb") as f:
                        f.write(audio_bytes)
                    normalize = subprocess.run(
                        ["ffmpeg", "-y", "-i", raw_path, "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
                         "-ar", "24000", "-q:a", "4", "-acodec", "libmp3lame", audio_dest],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    )
                    if normalize.returncode != 0 or not os.path.exists(audio_dest):
                        # Normalization failed for some reason - the raw (un-normalized)
                        # clip is still a perfectly valid narration track, use it as-is
                        # rather than losing the scene's audio entirely.
                        shutil.copyfile(raw_path, audio_dest)
                    if os.path.exists(raw_path):
                        os.remove(raw_path)
                    return [
                        {
                            "word": cue.content,
                            "start": round(cue.start.total_seconds(), 3),
                            "end": round(cue.end.total_seconds(), 3),
                        }
                        for cue in submaker.cues
                    ]
            except Exception:
                await asyncio.sleep(1.5)

        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
            "-t", "5", "-q:a", "9", "-acodec", "libmp3lame", audio_dest
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return []

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
# 3c. MULTI-SHOT AI IMAGES (visual variety for scenes that fall back to a
#     static image instead of real video footage)
# -------------------------------------------------------------
# Scene duration was recently raised (10-15 minute total target) so a single
# scene can now easily run 30-55 seconds. A scene that falls back to a
# generated still image used to hold that ONE image on screen for the whole
# time, under only a slow, barely-perceptible Ken Burns pan - which is
# exactly the "feels like one image for 10 sec" complaint. Instead of
# generating one image per image-type scene, we now generate a small number
# of distinct AI images for the SAME subject/setting (same imagePrompt, a
# different framing hint appended each time) and let Scene.tsx cut between
# them with its own short cross-fade + fresh Ken Burns per sub-shot - real
# footage still always wins when a matching stock clip is found; this only
# affects the image fallback path.
SUB_SHOT_FRAMING_HINTS = [
    "wide establishing shot, full scene visible, epic scale",
    "close-up shot, emotional facial expression, shallow depth of field",
    "medium shot, different camera angle, side profile",
    "dramatic low-angle shot, intense mood, rim lighting",
]

SUB_SHOT_SECONDS = 14.0  # roughly how long one still image can hold viewer interest

def estimate_scene_duration_seconds(narration_text: str) -> float:
    """Rough speaking-time estimate for Hindi narration, used only to decide
    how many AI-image sub-shots a static-image scene deserves - the real,
    ffprobe-measured duration isn't known yet at this point in the pipeline
    (audio and visuals are generated in parallel for speed, see process()).
    Deliberately a slight overestimate (fewer words/sec than natural spoken
    Hindi) so a scene is never under-provisioned with sub-shots."""
    words = len((narration_text or "").split())
    return max(3.0, words / 2.5)

def generate_multi_shot_ai_images(prompt: str, base_name: str, aspect_ratio: str, count: int,
                                   pollinations_width: int, pollinations_height: int) -> list:
    """Generates `count` distinct AI images for the SAME scene (same subject/
    setting/character, so the scene still reads as one continuous moment) by
    appending a different framing hint from SUB_SHOT_FRAMING_HINTS to the
    scene's own imagePrompt each time. Returns the list of filenames (bare,
    relative to public/images/) in shot order, for Scene.tsx's multi-shot
    slideshow to cross-fade between."""
    filenames = []
    for i in range(count):
        hint = SUB_SHOT_FRAMING_HINTS[i % len(SUB_SHOT_FRAMING_HINTS)]
        shot_prompt = f"{prompt}, {hint}"
        suffix = chr(ord('a') + i)
        fname = f"{base_name}_{suffix}.jpg"
        dest = f"public/images/{fname}"
        generate_ai_image(shot_prompt, dest, aspect_ratio=aspect_ratio,
                           pollinations_width=pollinations_width, pollinations_height=pollinations_height)
        filenames.append(fname)
    return filenames

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

    narration_text = scene.get("text") or scene.get("narration_chunk", "")
    est_duration = estimate_scene_duration_seconds(narration_text)
    num_shots = max(1, min(4, round(est_duration / SUB_SHOT_SECONDS)))
    print(f"🎨 [Long Scene {idx}] Generating {num_shots} FLUX.1 visual sub-shot(s): {prompt[:40]}...", flush=True)
    filenames = generate_multi_shot_ai_images(
        prompt, f"scene_{idx}", "16:9", num_shots,
        pollinations_width=1920, pollinations_height=1080,
    )
    return filenames if num_shots > 1 else filenames[0]

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

    narration_text = scene.get("text") or scene.get("narration_chunk", "")
    est_duration = estimate_scene_duration_seconds(narration_text)
    # Shorts scenes are naturally briefer and vertical framing has less room
    # for a wide/medium-shot distinction, so cap at 2 sub-shots instead of 4.
    num_shots = max(1, min(2, round(est_duration / SUB_SHOT_SECONDS)))
    print(f"🎨 [Shorts Scene {idx}] Generating {num_shots} 9:16 FLUX.1 visual sub-shot(s)...", flush=True)
    filenames = generate_multi_shot_ai_images(
        f"{prompt}, vertical 9:16 composition", f"shorts_scene_{idx}", "9:16", num_shots,
        pollinations_width=1080, pollinations_height=1920,
    )
    return filenames if num_shots > 1 else filenames[0]

# -------------------------------------------------------------
# 5b. AUTO-CHAPTERS (YouTube description timestamps)
# -------------------------------------------------------------
def format_chapter_timestamp(total_seconds: float) -> str:
    total_seconds = max(0, int(total_seconds))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"

def build_chapters_block(scenes: list) -> str:
    """YouTube auto-detects chapters from timestamp lines in a video's
    description, as long as: the first line is exactly 0:00, there are at
    least 3 lines, and each chapter is at least 10 seconds. Labels are a
    short excerpt of that scene's own narration rather than generic 'Part N'
    text, so viewers scrubbing the chapter bar (and YouTube's own indexing)
    get real content signal."""
    if len(scenes) < 3:
        return ""
    lines = []
    elapsed = 0.0
    for i, scene in enumerate(scenes):
        label = (scene.get("narration_chunk") or "").strip().replace("\n", " ")
        if len(label) > 45:
            label = label[:45].rsplit(" ", 1)[0] + "..."
        if not label:
            label = f"भाग {i + 1}"
        lines.append(f"{format_chapter_timestamp(elapsed)} {label}")
        elapsed += scene.get("durationInSeconds", 5)
    return "\n".join(lines)

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
    generate_ai_image(thumb_prompt, thumb_dest, aspect_ratio="16:9", pollinations_width=1920, pollinations_height=1080)
    subprocess.run(["cp", thumb_dest, "out/thumbnail.jpg"], check=False)

    # 2b. Thumbnail hook-text props, for the Remotion ThumbnailComposition
    # still-render in the GitHub Actions workflow (see render.yml's
    # render-thumbnail job) that overlays bold Hindi hook text on top of the
    # background image generated just above. Rendered through Remotion/
    # Chromium - the same pipeline that already renders Devanagari captions
    # correctly in Subtitles.tsx - rather than a naive image-library text
    # overlay, which risks garbled conjuncts/matra-reordering for Hindi
    # script. out/thumbnail.jpg above stays as the plain background image;
    # the render-thumbnail job produces the final text-overlaid version that
    # publish-and-notify actually releases and sends to YouTube.
    thumbnail_hook_text = (thumbnail_data.get("thumbnailText") or "").strip()
    if not thumbnail_hook_text:
        # Fallback so the thumbnail still gets SOME on-image text even if the
        # upstream Make.com prompt hasn't been updated yet to supply a
        # dedicated thumbnailText field - a short slice of the video's own
        # title beats no text at all.
        fallback_title = (seo_metadata.get("long_video_title") or "").strip()
        thumbnail_hook_text = " ".join(fallback_title.split()[:6])
    with open("public/thumbnail_props.json", "w", encoding="utf-8") as f:
        json.dump(
            {"backgroundImage": "thumbnail.jpg", "hookText": thumbnail_hook_text},
            f, ensure_ascii=False, indent=2,
        )

    # 3. Parallel Visuals (Pexels + Pixabay + Coverr + FLUX.1 for Long & Shorts)
    long_items = [(i + 1, s) for i, s in enumerate(long_scenes)]
    shorts_items = [(i + 1, s) for i, s in enumerate(shorts_scenes)]

    # max_workers=8 (was 4): this stage is I/O-bound (HTTP calls to stock/AI
    # APIs), not CPU-bound, so doubling it is safe and meaningfully faster.
    # Also submit long + shorts scenes together rather than as two sequential
    # executor.map() calls - the old code fully finished every long scene
    # before starting a single shorts scene, even though they're completely
    # independent work and could easily interleave.
    with ThreadPoolExecutor(max_workers=8) as executor:
        long_futures = [executor.submit(process_long_scene_visual, item) for item in long_items]
        shorts_futures = [executor.submit(process_shorts_scene_visual, item) for item in shorts_items]
        long_visuals = [f.result() for f in long_futures]
        shorts_visuals = [f.result() for f in shorts_futures]

    # 4. Parallel Audio Generation (Long + Shorts) - each task also returns
    # that scene's word-level caption timing (see generate_clean_audio).
    audio_tasks = []
    for i, scene in enumerate(long_scenes):
        idx = i + 1
        narration = scene.get("text") or scene.get("narration_chunk", "")
        audio_tasks.append(generate_clean_audio(narration, f"public/audio/chunk_{idx}.mp3"))

    for i, scene in enumerate(shorts_scenes):
        idx = i + 1
        narration = scene.get("text") or scene.get("narration_chunk", "")
        audio_tasks.append(generate_clean_audio(narration, f"public/audio/shorts_chunk_{idx}.mp3"))

    audio_word_timings = await asyncio.gather(*audio_tasks)
    long_word_timings = audio_word_timings[:len(long_scenes)]
    shorts_word_timings = audio_word_timings[len(long_scenes):]

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
            "soundEffect": scene.get("soundEffect", "none"),
            "words": long_word_timings[i]
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
            "imageFileName": shorts_visuals[i],
            "words": shorts_word_timings[i]
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

    # out/metadata.json is what your publish/upload flow reads for the
    # YouTube title+description - unlike props.json (which only Remotion
    # reads), it's safe to enrich this copy with auto-generated chapters
    # without touching anything about how the video itself renders.
    chapters_block = build_chapters_block(enriched_long)
    metadata_for_upload = dict(seo_metadata)
    if chapters_block:
        base_description = (metadata_for_upload.get("long_video_description") or "").strip()
        metadata_for_upload["long_video_description"] = f"{base_description}\n\n{chapters_block}".strip()
        metadata_for_upload["chapters"] = chapters_block

    with open("out/metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata_for_upload, f, ensure_ascii=False, indent=2)

    print("🎉 All Multi-Source Assets (Pexels + Pixabay + Coverr + Wikimedia + Local Library + FLUX), Thumbnail, Sound Effects, and Metadata ready!", flush=True)

if __name__ == "__main__":
    asyncio.run(process())
