import os
import re
import json
import time
import base64
import random
import shutil
import asyncio
import datetime
import threading
import subprocess
import urllib.parse
import hashlib
from concurrent.futures import ThreadPoolExecutor
import requests
import edge_tts
from director import enrich_scenes
from sfx_engine import resolve_sound_effect_audio
from visual_matcher import extract_visual_requirements, candidate_is_accurate
from content_qc import validate_payload, fact_check_items
from storyteller import build_prosody_map, prepare_storyteller_text
from hindi_text import to_spoken_hindi, hindi_display_text, pick_hindi, text_free_prompt, has_latin, best_hindi_title
try:
    import clip_rerank
except Exception:  # optional dependency (open_clip/torch) - never required
    clip_rerank = None
try:
    from indicf5_engine import generate_indicf5_audio
except Exception:
    generate_indicf5_audio = None

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
if not isinstance(seo_metadata, dict):
    seo_metadata = {}
# Make sends the packaging experiment fields (titleVariants, thumbnailConcepts,
# chapterPlan, cta, keywords...) in a separate "seo" object. Merge them in so
# QC, the thumbnail variants and the YouTube copy-paste pack can all see them.
_seo_pack = payload.get("seo", {})
if isinstance(_seo_pack, dict):
    for _k, _v in _seo_pack.items():
        if _v not in (None, "", [], {}) and not seo_metadata.get(_k):
            seo_metadata[_k] = _v


def _as_list(value):
    """Make sometimes serialises arrays as JSON strings - accept both."""
    if isinstance(value, list):
        return value
    if isinstance(value, str) and value.strip().startswith("["):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else []
        except Exception:
            return []
    return []


# Title repair: Make's gate only requires Hindi to be present, so a stray
# Roman word is converted to Devanagari here (instead of skipping the day),
# and a too-short title is replaced by the best of the 3 titleVariants.
_variant_titles = [str(v.get("title") if isinstance(v, dict) else v) for v in _as_list(seo_metadata.get("titleVariants"))]
_fixed_long_title = best_hindi_title(seo_metadata.get("long_video_title"), _variant_titles)
if _fixed_long_title:
    seo_metadata["long_video_title"] = _fixed_long_title
_fixed_shorts_title = best_hindi_title(seo_metadata.get("shorts_title"), _fixed_long_title, min_len=10, max_len=95)
if _fixed_shorts_title:
    seo_metadata["shorts_title"] = _fixed_shorts_title
payload["seo_metadata"] = seo_metadata
thumbnail_data = payload.get("thumbnail", {})
# Shorts-specific 9:16 thumbnail (own background image + hook text) - see
# the Make.com prompt's new `shorts_thumbnail` field and section 2c below.
# Previously Shorts had no dedicated thumbnail field at all.
_shorts_thumbnail_raw = payload.get("shorts_thumbnail", {})
shorts_thumbnail_data = _shorts_thumbnail_raw if isinstance(_shorts_thumbnail_raw, dict) else {}
# 1-based position (within long_video.scenes) of the story's climax/
# revelation scene, used to swell the bgm volume there instead of leaving it
# flat all video - see DevotionalComposition.tsx's bgmSwellSceneNumbers prop.
# Optional: falls back to a simple heuristic below (section 6) if the
# Make.com prompt hasn't been updated yet to supply it.
_meta_raw = payload.get("_meta", {})
meta_data = _meta_raw if isinstance(_meta_raw, dict) else {}
climax_scene_number = meta_data.get("climax_scene_number")
long_data = payload.get("long_video", {})
shorts_data = payload.get("shorts", {})

long_scenes = long_data.get("scenes", []) if isinstance(long_data, dict) else []
shorts_scenes = shorts_data.get("scenes", []) if isinstance(shorts_data, dict) else []

# AI-Director planning is deterministic and works even when the upstream
# payload has no director fields.
long_scenes = enrich_scenes(long_scenes, format_name="long")
shorts_scenes = enrich_scenes(shorts_scenes, format_name="shorts")

# Fallback test scenes for direct workflow_dispatch testing.
# Keep workflow_dispatch renders inside the same 2:30-3:30 production gate as
# real Make payloads. A short two-scene smoke test is not representative and
# correctly fails media QC, so the manual test payload mirrors the production
# story length instead of weakening QC.
if not long_scenes:
    long_scenes = [
        {"scene_number": 1, "mediaType": "ai_image", "text": "कुरुक्षेत्र की धूल में एक सवाल बार-बार उठ रहा था — जब सामने अपना ही परिवार खड़ा हो, तब धर्म किसे कहते हैं? अर्जुन के हाथ कांप रहे थे, लेकिन कृष्ण शांत थे। उस क्षण गीता का उपदेश केवल युद्ध की बात नहीं था, बल्कि निर्णय के उस डर की बात था, जिसे हर इंसान किसी न किसी रूप में जानता है।", "imagePrompt": "Lord Krishna and Arjuna on a golden chariot in Kurukshetra, tense battlefield, cinematic 16:9, divine dawn lighting", "videoSearchQuery": "ancient battlefield chariot dust"},
        {"scene_number": 2, "mediaType": "video", "text": "कृष्ण ने अर्जुन को तुरंत जीत का वादा नहीं दिया। उन्होंने पहले उसके भ्रम को सामने रखा। यही इस कथा का पहला रोचक मोड़ है — समस्या बाहर के युद्ध से पहले भीतर चल रही थी। अर्जुन को तय करना था कि वह डर के कारण पीछे हटेगा, या अपनी जिम्मेदारी को समझकर आगे बढ़ेगा।", "imagePrompt": "Krishna calmly explaining dharma to Arjuna on chariot, emotional close-up, Kurukshetra, cinematic 16:9", "videoSearchQuery": "Krishna Arjuna chariot battlefield"},
        {"scene_number": 3, "mediaType": "ai_image", "text": "गीता का संदेश यहीं से गहरा होता है। कृष्ण कहते हैं कि मनुष्य का अधिकार अपने कर्म पर है, केवल उसके परिणाम पर नहीं। सुनने में यह सरल लगता है, लेकिन युद्धभूमि में इसका अर्थ बहुत कठोर था। अर्जुन को परिणाम का डर छोड़कर उस कर्म को देखना था, जिसे वह सही मानकर निभा सकता था।", "imagePrompt": "Krishna teaching Arjuna, symbolic glowing scripture and battlefield horizon, reverent cinematic 16:9", "videoSearchQuery": "ancient scripture temple light"},
        {"scene_number": 4, "mediaType": "video", "text": "लेकिन यहाँ एक और दिलचस्प बात छिपी है। निष्काम कर्म का अर्थ यह नहीं कि परिणाम की कोई कीमत ही नहीं है। अर्थ यह है कि परिणाम की चिंता निर्णय को इतना कमजोर न कर दे कि सही कर्म ही छूट जाए। इसी वजह से गीता का संदेश आज भी केवल धार्मिक कथा नहीं, बल्कि निर्णय लेने की एक चुनौती जैसा महसूस होता है।", "imagePrompt": "symbolic crossroads with Krishna silhouette, glowing path and battlefield, cinematic mystery mood, 16:9", "videoSearchQuery": "mysterious ancient path sunrise"},
        {"scene_number": 5, "mediaType": "ai_image", "text": "फिर कथा उस जगह पहुंचती है जहाँ असली बदलाव शुरू होता है। अर्जुन अपने डर को छिपाता नहीं, बल्कि उसे स्वीकार करता है। यही उसकी कमजोरी नहीं, बल्कि सीखने की शुरुआत बनती है। कृष्ण भी उसे केवल सांत्वना नहीं देते — वे उसके सवालों को एक-एक करके चुनौती देते हैं, ताकि फैसला भावुकता से नहीं, समझ से निकले।", "imagePrompt": "Arjuna listening with renewed focus while Krishna speaks, emotional divine light, Kurukshetra, cinematic 16:9", "videoSearchQuery": "warrior listening spiritual teacher"},
        {"scene_number": 6, "mediaType": "video", "text": "और अब आता है वह विचार, जो पूरी कहानी को पलट देता है। मनुष्य अपने कर्म को नियंत्रित कर सकता है, लेकिन हर परिणाम को नहीं। इसलिए असली स्वतंत्रता हर चीज अपने मुताबिक कर लेने में नहीं, बल्कि अनिश्चित परिणाम के बीच भी सही कदम चुनने में है। यही बात अर्जुन के भीतर धीरे-धीरे डर से स्पष्टता की ओर रास्ता खोलती है।", "imagePrompt": "radiant Krishna revealing universal wisdom to Arjuna, dramatic golden aura, cinematic 16:9", "videoSearchQuery": "divine revelation golden light"},
        {"scene_number": 7, "mediaType": "video", "text": "कुरुक्षेत्र का युद्ध बहुत पुरानी घटना है, लेकिन इसका सवाल आज भी नया लगता है। नौकरी का कठिन फैसला हो, परिवार की जिम्मेदारी हो या किसी डर के सामने खड़ा होना — परिणाम हमारे हाथ में हमेशा नहीं होता। फिर भी अगला सही कदम चुनना हमारे हाथ में हो सकता है। यही गीता के इस विचार का सबसे व्यावहारिक अर्थ है।", "imagePrompt": "modern person silhouette visually connected to ancient Krishna Arjuna scene, timeless wisdom, cinematic 16:9", "videoSearchQuery": "person reflection sunrise"},
        {"scene_number": 8, "mediaType": "ai_image", "text": "शायद इसलिए अर्जुन की कहानी सिर्फ युद्धभूमि की कहानी बनकर नहीं रह जाती। उसका असली सवाल है — जब मन डर से भर जाए, तब क्या हम परिणाम के पीछे भागेंगे, या अपने कर्तव्य को समझकर कदम उठाएंगे? यही वह छोटा सा विचार है, जो हजारों साल पुरानी कथा को आज के जीवन से जोड़ देता है।", "imagePrompt": "Krishna and Arjuna silhouetted at sunrise after revelation, peaceful Kurukshetra horizon, cinematic 16:9", "videoSearchQuery": "sunrise ancient battlefield peaceful"}
    ]

if not shorts_scenes:
    shorts_scenes = [
        {"scene_number": 1, "text": "कुरुक्षेत्र में अर्जुन के सामने सबसे बड़ा सवाल जीत या हार नहीं था। सवाल था — जब परिणाम हमारे हाथ में न हो, तब सही कर्म कैसे चुना जाए? कृष्ण का उत्तर आज भी चौंकाता है: परिणाम की चिंता से पहले अपने कर्तव्य को समझो।", "imagePrompt": "Krishna and Arjuna dramatic vertical 9:16, battlefield sunrise", "videoSearchQuery": "Krishna Arjuna chariot"}
    ]

# Re-run the director after fallback scene injection so workflow_dispatch
# test renders receive exactly the same production metadata as normal runs.
long_scenes = enrich_scenes(long_scenes, format_name="long")
shorts_scenes = enrich_scenes(shorts_scenes, format_name="shorts")

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
# 0a. CROSS-RUN CLIP-USAGE HISTORY (avoid reusing the same stock clip
#     across different days' videos)
# -------------------------------------------------------------
# Root cause of "I see the same clip in two videos": every fetch_*_video()
# below scores candidates by keyword overlap and deterministically takes the
# single best-scoring hit (see _best_scoring_index) - with no memory of what
# was used before. Because scene wording repeats a lot day to day ("temple
# bells incense smoke", "diya flame", "ancient battlefield dust storm"), the
# exact same top-ranked clip keeps winning on later videos. This file
# persists a small rolling history of (source, clip id) pairs actually used,
# checked into the repo by the CI workflow after each render (see
# render.yml's "Persist clip-usage history" step), so a later run can see
# what a PREVIOUS run already used and prefer a different, still-relevant
# clip instead.
HISTORY_PATH = "used_clips_history.json"
HISTORY_LOOKBACK_DAYS = 60  # entries older than this are pruned on save

def _load_recent_clip_history() -> tuple:
    """Returns (raw_records, recently_used_ids) - raw_records is the full
    list of {"source", "id", "usedAt"} dicts loaded from disk (kept around so
    save_clip_history() can merge rather than clobber), recently_used_ids is
    a set of "source:id" strings for everything within HISTORY_LOOKBACK_DAYS,
    used as the "avoid these" set while picking candidates below."""
    if not os.path.exists(HISTORY_PATH):
        return [], set()
    try:
        with open(HISTORY_PATH, encoding="utf-8") as f:
            records = json.load(f)
        if not isinstance(records, list):
            return [], set()
    except Exception as e:
        print(f"Clip-history notice (load): {e}", flush=True)
        return [], set()

    cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=HISTORY_LOOKBACK_DAYS)
    recent_ids = set()
    for rec in records:
        try:
            used_at = datetime.datetime.strptime(rec["usedAt"], "%Y-%m-%d")
            if used_at >= cutoff:
                recent_ids.add(f"{rec['source']}:{rec['id']}")
        except Exception:
            continue
    return records, recent_ids

_HISTORY_RECORDS, RECENTLY_USED_CLIP_IDS = _load_recent_clip_history()
if RECENTLY_USED_CLIP_IDS:
    print(f"  📜 Loaded clip-usage history: {len(RECENTLY_USED_CLIP_IDS)} clip(s) used in the last {HISTORY_LOOKBACK_DAYS} days will be deprioritized.", flush=True)

_new_usage_records = []
_usage_lock = threading.Lock()

def record_clip_usage(source: str, clip_id: str) -> None:
    """Called right after a stock clip is actually downloaded successfully -
    thread-safe since process_long_scene_visual/process_shorts_scene_visual
    run inside a ThreadPoolExecutor.

    Also immediately marks the clip as "recently used" in-memory (not just
    on disk at the end of the run via save_clip_history()) - this is what
    makes fetch_video_shots_for_duration()'s multiple fetches for the SAME
    scene actually return different clips instead of the same top-ranked hit
    every time: _best_scoring_index() already deprioritizes anything in
    RECENTLY_USED_CLIP_IDS, so a clip used for shot #1 of a scene is treated
    as "recently used" by the time shot #2 is fetched a moment later, same
    run. Bonus: this also reduces duplicate clips across two DIFFERENT
    scenes matching similar wording within the same day's video."""
    if not clip_id:
        return
    with _usage_lock:
        _new_usage_records.append({
            "source": source,
            "id": str(clip_id),
            "usedAt": datetime.datetime.utcnow().strftime("%Y-%m-%d"),
        })
        RECENTLY_USED_CLIP_IDS.add(f"{source}:{clip_id}")

def save_clip_history() -> None:
    """Merges this run's newly-used clips into the on-disk history, prunes
    anything older than HISTORY_LOOKBACK_DAYS, and writes it back out. The CI
    workflow commits this file back to the repo after generate_assets.py
    finishes, so the NEXT run's _load_recent_clip_history() call actually
    sees it."""
    if not _new_usage_records:
        return
    cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=HISTORY_LOOKBACK_DAYS)
    merged = {}
    for rec in _HISTORY_RECORDS + _new_usage_records:
        try:
            used_at = datetime.datetime.strptime(rec["usedAt"], "%Y-%m-%d")
        except Exception:
            continue
        if used_at < cutoff:
            continue
        key = (rec["source"], rec["id"])
        # Keep the most recent usedAt if the same clip appears twice.
        if key not in merged or merged[key]["usedAt"] < rec["usedAt"]:
            merged[key] = rec
    try:
        with open(HISTORY_PATH, "w", encoding="utf-8") as f:
            json.dump(list(merged.values()), f, ensure_ascii=False, indent=2)
        print(f"  📜 Saved clip-usage history: {len(merged)} clip(s) tracked (added {len(_new_usage_records)} from this run).", flush=True)
    except Exception as e:
        print(f"Clip-history notice (save): {e}", flush=True)

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

class VisualKeywordSet(set):
    """A normal set carrying scene-level strict visual requirements."""
    def __init__(self, values=(), requirements=None):
        super().__init__(values)
        self.requirements = requirements or {}

def _extract_keywords(*texts: str) -> VisualKeywordSet:
    words = set()
    for text in texts:
        if not text:
            continue
        for raw in re.split(r"[\s/_\-.,!?()]+", str(text).lower()):
            if len(raw) > 2 and raw not in _STOPWORDS:
                words.add(raw)
    return VisualKeywordSet(words)

def _best_scoring_index(candidate_texts: list, target_keywords, candidate_ids: list = None, source: str = None,
                        preview_urls: list = None):
    """Returns (best_index, best_score, any_text_available) for a list of
    candidate descriptive strings (one per API hit, "" where a source gives
    no usable text). any_text_available is False when every hit had no text
    at all, so callers fall back to "just take hit #1" rather than reject a
    source that structurally can't be scored.

    When candidate_ids + source are also given, this deprioritizes any
    candidate whose "source:id" shows up in RECENTLY_USED_CLIP_IDS (a clip
    used in a recent video - see the clip-usage-history section above):
    among candidates tied for the single best keyword score, it prefers one
    that was NOT recently used, only falling back to a recently-used one if
    every top-scoring candidate has already been used recently. This is the
    actual fix for "same clip in two videos" - previously max() picked
    whichever top hit happened to sort first, every time, for a repeated
    query."""
    if not target_keywords:
        return 0, 0, False
    if not any(candidate_texts):
        return 0, 0, False
    requirements = getattr(target_keywords, "requirements", {}) or {}
    scores = []
    for candidate_text in candidate_texts:
        if requirements.get("strict"):
            accepted, _reason = candidate_is_accurate(candidate_text, requirements)
            if not accepted:
                scores.append(-10000)
                continue
        scores.append(len(_extract_keywords(candidate_text) & target_keywords))
    # Optional OpenCLIP visual re-rank (CLIP_RERANK_ENABLED=true): score each
    # candidate's preview image against the scene prompt. Clips that clearly
    # don't LOOK like the scene are rejected even if their tags matched.
    if clip_rerank is not None and preview_urls and clip_rerank.enabled():
        sims = clip_rerank.similarities(getattr(target_keywords, "prompt", ""), preview_urls)
        if sims:
            floor = clip_rerank.min_similarity()
            for i, sim in enumerate(sims):
                if sim is None or i >= len(scores) or scores[i] < 0:
                    continue
                scores[i] = -1 if sim < floor else scores[i] + sim * 20
    best_score = max(scores)
    if best_score < 0:
        return 0, -1, True
    tied_indices = [i for i, s in enumerate(scores) if s == best_score]
    if candidate_ids and source:
        fresh = [i for i in tied_indices if f"{source}:{candidate_ids[i]}" not in RECENTLY_USED_CLIP_IDS]
        if fresh:
            return fresh[0], best_score, True
    return tied_indices[0], best_score, True

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
                [v.get("url", "") for v in videos], target_keywords,
                candidate_ids=[v.get("id") for v in videos], source="pexels",
                preview_urls=[v.get("image", "") for v in videos],
            )
            if scorable and best_score <= 0:
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
                record_clip_usage("pexels", chosen.get("id"))
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
                    [h.get("tags", "") for h in hits], target_keywords,
                    candidate_ids=[h.get("id") for h in hits], source="pixabay",
                    preview_urls=[((h.get("videos") or {}).get("medium") or {}).get("thumbnail", "") for h in hits],
                )
                if scorable and best_score <= 0:
                    continue
                chosen = hits[best_idx] if scorable else hits[0]
                videos_dict = chosen.get("videos", {})
                target = videos_dict.get("large") or videos_dict.get("medium") or videos_dict.get("small")
                if target and target.get("url"):
                    v_res = requests.get(target.get("url"), timeout=45)
                    if v_res.status_code == 200 and len(v_res.content) > 100000:
                        with open(dest_path, "wb") as f:
                            f.write(v_res.content)
                        record_clip_usage("pixabay", chosen.get("id"))
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
                candidate_ids=[h.get("id") for h in hits], source="coverr",
            )
            if scorable and best_score <= 0:
                return False
            chosen = hits[best_idx] if scorable else hits[0]
            video_url = (chosen.get("urls") or {}).get("mp4")
            if video_url:
                v_res = requests.get(video_url, timeout=45)
                if v_res.status_code == 200 and len(v_res.content) > 100000:
                    with open(dest_path, "wb") as f:
                        f.write(v_res.content)
                    record_clip_usage("coverr", chosen.get("id"))
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
        if scorable and best_score <= 0:
            return False
        ordered = candidates
        if scorable:
            # Recently-used titles (per RECENTLY_USED_CLIP_IDS) get a large
            # penalty so a fresh, still-relevant candidate is tried first -
            # they aren't dropped outright, just pushed to the back, so a
            # recently-used clip is still a fallback if nothing else works.
            def _sort_key(c):
                title = c[0]
                score = len(_extract_keywords(title) & target_keywords)
                if f"wikimedia:{title}" in RECENTLY_USED_CLIP_IDS:
                    score -= 1000
                return score
            ordered = sorted(candidates, key=_sort_key, reverse=True)

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
                    record_clip_usage("wikimedia", _title)
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

def fetch_multi_source_video(query: str, dest_path: str, orientation: str = "landscape",
                             prompt_text: str = "", candidate_queries: list = None,
                             match_meta: dict = None) -> bool:
    bundled_query_text = " ".join(
        str(q).strip() for q in (candidate_queries or []) if str(q).strip()
    )
    requirements = extract_visual_requirements(bundled_query_text or query, prompt_text)
    strict = bool(requirements.get("strict"))
    if strict:
        print(
            f"  🔒 Strict visual gate: entities={requirements.get('entities')} "
            f"attributes={requirements.get('attributes')} - generic stock is not allowed.",
            flush=True,
        )

    # Strict mythological scenes intentionally bypass generic niche rewrites.
    # "Krishna" must not become "golden deity statue"; "Bal Krishna" must not
    # become "generic child". If the stock catalog cannot prove the entity from
    # metadata, the caller falls through to AI generation instead.
    if candidate_queries:
        candidates = []
        for candidate in candidate_queries:
            candidate = str(candidate or "").strip()
            if candidate and candidate not in candidates:
                candidates.append(candidate)
    else:
        candidates = [query.strip()] if strict and query.strip() else build_query_candidates(query, prompt_text)

    if strict and prompt_text and not candidate_queries and prompt_text.strip() not in candidates:
        candidates.append(prompt_text.strip())

    for candidate in candidates:
        target_keywords = _extract_keywords(candidate, prompt_text)
        target_keywords.requirements = requirements
        target_keywords.prompt = f"{prompt_text or candidate}".strip()
        # 1. Try Pexels only when its URL metadata can prove the strict entity.
        if fetch_pexels_video(candidate, dest_path, orientation, target_keywords):
            if match_meta is not None:
                match_meta.update({"matched_query": candidate, "source": "pexels"})
            print(f"  ✅ Accurate video fetched from Pexels ('{candidate}')", flush=True)
            return True
        # 2. Pixabay has the strongest stock tags for strict metadata matching.
        if fetch_pixabay_video(candidate, dest_path, target_keywords):
            if match_meta is not None:
                match_meta.update({"matched_query": candidate, "source": "pixabay"})
            print(f"  ✅ Accurate video fetched from Pixabay ('{candidate}')", flush=True)
            return True
        # 3. Coverr title/tags, still subject to the same hard gate.
        if fetch_coverr_video(candidate, dest_path, target_keywords):
            if match_meta is not None:
                match_meta.update({"matched_query": candidate, "source": "coverr"})
            print(f"  ✅ Accurate video fetched from Coverr ('{candidate}')", flush=True)
            return True
        # 4. Wikimedia Commons is useful for real devotional/historical footage.
        if fetch_wikimedia_video(candidate, dest_path, target_keywords):
            if match_meta is not None:
                match_meta.update({"matched_query": candidate, "source": "wikimedia"})
            print(f"  ✅ Accurate video fetched from Wikimedia Commons ('{candidate}')", flush=True)
            return True

    # Never use fuzzy local matching for strict entity scenes either.
    local_query = bundled_query_text or query
    if not strict and fetch_local_library_video(f"{local_query} {prompt_text}", dest_path):
        if match_meta is not None:
            match_meta.update({"matched_query": local_query, "source": "local_library"})
        return True
    return False

# -------------------------------------------------------------
# 1c. DURATION-AWARE MULTI-CLIP VIDEO ENGINE
# -------------------------------------------------------------
# THIS IS THE FIX for "stock clip finishes, screen freezes, voiceover keeps
# going": generate_multi_shot_ai_images() below already solves the equivalent
# problem for the AI-image fallback (several distinct stills instead of one
# held for the whole scene) - real stock video never got that treatment.
# process_long_scene_visual()/process_shorts_scene_visual() used to fetch
# exactly ONE clip per scene and hand it straight to Scene.tsx, which played
# it once with no loop/trim - a typical 5-15s stock clip would finish and
# freeze on its last frame while the scene's own narration audio (which can
# run 35-55s for a long-form scene) kept playing underneath it.
#
# fetch_video_shots_for_duration() instead fetches as many clips as needed -
# a different search phrasing each time, so a second/third clip for the same
# scene is a genuinely different shot rather than a retry of the same query -
# until their combined REAL (ffprobe-measured) duration covers the scene, up
# to max_shots. Any shortfall (stock sources ran dry before the target was
# reached) is topped up by the caller with AI-image sub-shots, so a scene
# never runs out of real screen time.
MAX_VIDEO_SHOTS_PER_SCENE = 3
MIN_SHOT_SECONDS = 3.0  # never split a scene's remaining time so finely a shot reads as a flash-cut
SUB_SHOT_SECONDS = 5.0  # target visual coverage per generated AI-image sub-shot
HOOK_SUB_SHOT_SECONDS = 2.5  # faster visual rhythm for the opening Shorts hook
SUB_SHOT_FRAMING_HINTS = [
    "cinematic medium shot",
    "close-up detail",
    "dramatic low angle",
]
HOOK_SUB_SHOT_FRAMING_HINTS = [
    "extreme close-up",
    "dynamic low angle",
    "dramatic push-in composition",
]


# -------------------------------------------------------------
# 1d. PHASE-3 BEAT-LEVEL MULTI-SOURCE CANDIDATE RERANKING
# -------------------------------------------------------------
# Phase 2 gave every narration beat its own queries. Phase 3 goes one level
# higher: instead of accepting the first source that returns an acceptable
# clip, collect a small metadata/preview pool across sources, compare the
# candidates against the SAME narration beat, then download only the winner.
#
# Weighting mirrors the visual-director plan:
#   semantic narration match       40%
#   entity/action correctness      20%
#   visual quality                 15%
#   useful motion                  10%
#   scene continuity                5%
#   novelty / reuse penalty         5%
#   composition suitability         5%
#
# OpenCLIP remains optional. When enabled it supplies the strongest semantic
# signal from candidate preview images. When disabled/unavailable, a lexical
# narration-vs-metadata score fills that slot so the reranker still works.
_VISUAL_SCORE_WEIGHTS = {
    "semantic": 0.40,
    "entity_action": 0.20,
    "quality": 0.15,
    "motion": 0.10,
    "continuity": 0.05,
    "novelty": 0.05,
    "composition": 0.05,
}


def _clamp01(value):
    try:
        return max(0.0, min(1.0, float(value)))
    except Exception:
        return 0.0


def _candidate_key(candidate: dict) -> str:
    return f"{candidate.get('source', '')}:{candidate.get('id', '')}"


def _candidate_target_count() -> int:
    try:
        return max(5, min(15, int(os.getenv("VISUAL_CANDIDATE_TARGET", "8") or 8)))
    except ValueError:
        return 8


def _candidate_min_score() -> float:
    try:
        return max(0.20, min(0.85, float(os.getenv("VISUAL_CANDIDATE_MIN_SCORE", "0.46") or 0.46)))
    except ValueError:
        return 0.46


def _rerank_query_limit() -> int:
    try:
        return max(1, min(3, int(os.getenv("VISUAL_RERANK_MAX_QUERIES", "2") or 2)))
    except ValueError:
        return 2


def _candidate_text_score(candidate_text: str, target_text: str) -> float:
    candidate_words = _extract_keywords(candidate_text)
    target_words = _extract_keywords(target_text)
    if not candidate_words or not target_words:
        return 0.0
    overlap = len(candidate_words & target_words)
    # Four meaningful overlaps is already a strong stock-catalog metadata
    # match; saturating here avoids rewarding verbose tag spam.
    return _clamp01(overlap / max(1.0, min(4.0, len(target_words) * 0.45)))


def _candidate_entity_action_score(candidate: dict, beat: dict, requirements: dict) -> tuple:
    text = str(candidate.get("text") or "")
    if requirements.get("strict"):
        accepted, reason = candidate_is_accurate(text, requirements)
        if not accepted:
            return 0.0, False, reason or "strict_visual_requirement_failed"

    required_terms = []
    for key in ("subject", "action", "setting"):
        value = str(beat.get(key) or "").strip()
        if value and value not in {"narrative moment", "story environment", "unspecified"}:
            required_terms.extend(_extract_keywords(value))

    if not required_terms:
        return 0.65, True, "no_specific_entity_action_terms"

    candidate_words = _extract_keywords(text)
    hits = sum(1 for term in set(required_terms) if term in candidate_words)
    score = hits / max(1, len(set(required_terms)))

    # A strict candidate that passed the visual matcher deserves a floor:
    # its metadata may use an alias/transliteration rather than our exact word.
    if requirements.get("strict"):
        score = max(score, 0.75)
    return _clamp01(score), True, "accepted"


def _candidate_quality_score(candidate: dict, orientation: str) -> float:
    width = int(candidate.get("width") or 0)
    height = int(candidate.get("height") or 0)
    if width <= 0 or height <= 0:
        return 0.55
    long_edge = max(width, height)
    short_edge = min(width, height)
    resolution = min(1.0, short_edge / 1080.0)
    # Preserve a little credit for true 720p footage if it's otherwise the
    # strongest semantic match; 1080+ gets full quality credit.
    return _clamp01(0.25 + 0.75 * resolution)


def _candidate_motion_score(candidate: dict) -> float:
    duration = float(candidate.get("duration") or 0.0)
    style = str(candidate.get("style") or "live").lower()
    # Useful B-roll usually has enough real motion for a 4-7 second edit but
    # does not need to be extremely long. Unknown duration gets a neutral mark.
    if duration <= 0:
        base = 0.65
    elif 4.0 <= duration <= 30.0:
        base = 1.0
    elif 2.0 <= duration < 4.0:
        base = 0.70
    else:
        base = 0.78
    if style == "animation":
        base = min(1.0, base + 0.08)
    return _clamp01(base)


_CONTINUITY_STYLIZED_TERMS = {
    "animation", "animated", "illustration", "illustrated", "cartoon", "anime",
    "3d render", "cgi", "digital art", "painting", "watercolor",
}
_CONTINUITY_ANCIENT_TERMS = {
    "ancient", "vedic", "mythological", "temple", "palace", "chariot",
    "battlefield", "traditional", "heritage", "ritual",
}
_CONTINUITY_MODERN_TERMS = {
    "modern", "city", "urban", "office", "smartphone", "phone", "car",
    "traffic", "skyscraper", "technology", "contemporary",
}
_CONTINUITY_WARM_TERMS = {
    "golden", "warm", "sunrise", "sunset", "candle", "diya", "lamp",
    "fire", "orange", "amber",
}
_CONTINUITY_NIGHT_TERMS = {
    "night", "moon", "moonlight", "dark", "blue hour", "midnight",
}
_CONTINUITY_NATURAL_TERMS = {
    "daylight", "day", "natural light", "sunlight", "outdoor",
}

_CONTINUITY_ENTITY_ALIASES = {
    "krishna": {"krishna", "shri krishna", "lord krishna", "कृष्ण", "श्रीकृष्ण"},
    "shiva": {"shiva", "mahadev", "lord shiva", "शिव", "महादेव"},
    "ram": {"ram", "rama", "lord ram", "राम"},
    "hanuman": {"hanuman", "bajrangbali", "हनुमान", "बजरंगबली"},
    "ganesh": {"ganesh", "ganesha", "गणेश"},
    "vishnu": {"vishnu", "विष्णु"},
    "lakshmi": {"lakshmi", "laxmi", "लक्ष्मी"},
    "durga": {"durga", "दुर्गा"},
    "parvati": {"parvati", "पार्वती"},
    "arjuna": {"arjuna", "arjun", "अर्जुन"},
    "karna": {"karna", "karn", "कर्ण"},
    "radha": {"radha", "राधा"},
    "sita": {"sita", "सीता"},
}


def _canonical_entity(text: str) -> str:
    value = str(text or "").lower()
    for canonical, aliases in _CONTINUITY_ENTITY_ALIASES.items():
        if any(alias.lower() in value for alias in aliases):
            return canonical
    return ""


def _contains_any(text: str, terms: set) -> bool:
    value = str(text or "").lower()
    return any(term in value for term in terms)


def _candidate_style_profile(candidate: dict, beat: dict = None) -> dict:
    text = " ".join([
        str(candidate.get("text") or ""),
        str(candidate.get("query") or ""),
    ]).lower()
    source_style = str(candidate.get("style") or "live").lower()

    realism = (
        "stylized"
        if source_style == "animation" or _contains_any(text, _CONTINUITY_STYLIZED_TERMS)
        else "cinematic_realism"
    )

    if _contains_any(text, _CONTINUITY_MODERN_TERMS):
        period = "modern"
    elif _contains_any(text, _CONTINUITY_ANCIENT_TERMS):
        period = "ancient"
    else:
        period = "unknown"

    if _contains_any(text, _CONTINUITY_NIGHT_TERMS):
        lighting = "low_key_night"
    elif _contains_any(text, _CONTINUITY_WARM_TERMS):
        lighting = "warm_golden"
    elif _contains_any(text, _CONTINUITY_NATURAL_TERMS):
        lighting = "natural_cinematic"
    else:
        lighting = "unknown"

    setting_text = str((beat or {}).get("setting") or "").lower()
    setting_match = 0.75
    if setting_text and setting_text not in {"story environment", "unspecified"}:
        setting_words = _extract_keywords(setting_text)
        candidate_words = _extract_keywords(text)
        setting_match = 1.0 if setting_words & candidate_words else 0.45

    return {
        "realism": realism,
        "period": period,
        "lighting": lighting,
        "settingMatch": round(setting_match, 3),
    }


def _continuity_duplicate_threshold() -> float:
    try:
        return max(0.90, min(0.995, float(os.getenv("VISUAL_DUPLICATE_SIMILARITY", "0.965") or 0.965)))
    except ValueError:
        return 0.965


def _candidate_continuity_score(candidate: dict, beat: dict,
                                previous_candidate: dict = None,
                                preview_similarity=None) -> tuple:
    """Return (score, rejected, reason, profile, flags).

    Continuity is mostly a soft preference, except for two high-confidence
    editorial failures:
      1. explicit modern-vs-ancient contradiction;
      2. adjacent previews that are effectively the same composition.
    """
    desired = dict(beat.get("styleProfile") or {})
    profile = _candidate_style_profile(candidate, beat)
    flags = []
    rejected = False
    reason = ""

    desired_realism = desired.get("realism")
    current_realism = profile.get("realism")
    if desired_realism and current_realism == desired_realism:
        realism_score = 1.0
    elif desired_realism and current_realism and desired_realism != current_realism:
        realism_score = 0.0
        rejected = True
        reason = "realism_conflict"
        flags.append("realism_conflict")
    else:
        realism_score = 0.72

    desired_entity = _canonical_entity(desired.get("entityAnchor", ""))
    candidate_entity = _canonical_entity(
        " ".join([
            str(candidate.get("text") or ""),
            str(candidate.get("query") or ""),
        ])
    )
    if desired_entity and candidate_entity and desired_entity != candidate_entity:
        rejected = True
        reason = "entity_conflict"
        flags.append("entity_conflict")

    desired_period = desired.get("period", "timeless")
    current_period = profile.get("period", "unknown")
    if desired_period in {"ancient", "modern"} and current_period in {"ancient", "modern"}:
        if desired_period != current_period:
            rejected = True
            reason = "period_conflict"
            flags.append("period_conflict")
            period_score = 0.0
        else:
            period_score = 1.0
    elif current_period == "unknown" or desired_period == "timeless":
        period_score = 0.78
    else:
        period_score = 0.72

    desired_lighting = desired.get("lighting")
    current_lighting = profile.get("lighting")
    if not desired_lighting or current_lighting == "unknown":
        lighting_score = 0.74
    elif desired_lighting == current_lighting:
        lighting_score = 1.0
    elif {desired_lighting, current_lighting} <= {"warm_golden", "natural_cinematic"}:
        lighting_score = 0.72
    else:
        lighting_score = 0.48
        flags.append("lighting_jump")

    previous_score = 0.78
    if previous_candidate:
        previous_profile = dict(previous_candidate.get("continuityProfile") or {})
        if not previous_profile:
            previous_profile = _candidate_style_profile(previous_candidate, beat)

        previous_realism = previous_profile.get("realism")
        if previous_realism and previous_realism == current_realism:
            previous_score = 1.0
        elif previous_realism:
            previous_score = 0.28
            flags.append("adjacent_realism_jump")

        previous_period = previous_profile.get("period")
        if (
            previous_period in {"ancient", "modern"}
            and current_period in {"ancient", "modern"}
            and previous_period != current_period
        ):
            previous_score = min(previous_score, 0.22)
            flags.append("adjacent_period_jump")

    similarity_score = 0.75
    if preview_similarity is not None:
        sim = float(preview_similarity)
        if sim >= _continuity_duplicate_threshold():
            rejected = True
            reason = reason or "near_duplicate_composition"
            flags.append("near_duplicate")
            similarity_score = 0.0
        elif sim >= 0.90:
            # Very similar but not identical: useful continuity, less novelty.
            similarity_score = 0.70
            flags.append("very_similar_composition")
        elif 0.48 <= sim < 0.90:
            similarity_score = 1.0
        else:
            # Low image similarity can simply mean the narration changed
            # subject, so penalise gently rather than rejecting.
            similarity_score = 0.58
            flags.append("large_visual_change")

    setting_score = float(profile.get("settingMatch") or 0.75)

    score = (
        realism_score * 0.28
        + period_score * 0.20
        + lighting_score * 0.14
        + setting_score * 0.13
        + previous_score * 0.15
        + similarity_score * 0.10
    )

    return _clamp01(score), rejected, reason, profile, flags


def _candidate_novelty_score(candidate: dict) -> float:
    return 0.20 if _candidate_key(candidate) in RECENTLY_USED_CLIP_IDS else 1.0


def _candidate_composition_score(candidate: dict, orientation: str) -> float:
    width = int(candidate.get("width") or 0)
    height = int(candidate.get("height") or 0)
    if width <= 0 or height <= 0:
        return 0.55
    landscape = width >= height
    wanted_landscape = orientation != "portrait"
    if landscape == wanted_landscape:
        return 1.0
    # A square-ish source can still crop reasonably; a strongly wrong aspect
    # ratio receives a low composition score.
    ratio = max(width, height) / max(1, min(width, height))
    return 0.45 if ratio < 1.25 else 0.15


def _pexels_candidates(query: str, orientation: str, per_page: int = 5) -> list:
    if not PEXELS_API_KEY or not query:
        return []
    try:
        clean_q = urllib.parse.quote(query.strip()[:60])
        url = (
            f"https://api.pexels.com/videos/search?query={clean_q}"
            f"&orientation={orientation}&per_page={per_page}"
        )
        res = requests.get(url, headers={"Authorization": PEXELS_API_KEY}, timeout=15)
        if res.status_code != 200:
            return []
        out = []
        for video in res.json().get("videos", []):
            files = video.get("video_files", []) or []
            hd_files = sorted(
                (f for f in files if int(f.get("width") or 0) >= 1080),
                key=lambda f: int(f.get("width") or 0),
            )
            target = hd_files[0] if hd_files else (files[0] if files else {})
            video_url = target.get("link")
            if not video_url:
                continue
            out.append({
                "source": "pexels",
                "id": str(video.get("id") or video_url),
                "query": query,
                "text": video.get("url", ""),
                "preview_url": video.get("image", ""),
                "video_url": video_url,
                "width": int(target.get("width") or video.get("width") or 0),
                "height": int(target.get("height") or video.get("height") or 0),
                "duration": float(video.get("duration") or 0),
                "style": "live",
            })
        return out
    except Exception as exc:
        print(f"Pexels candidate-pool notice: {exc}", flush=True)
        return []


def _pixabay_candidates(query: str, per_page: int = 5) -> list:
    if not PIXABAY_API_KEY or not query:
        return []
    try:
        clean_q = urllib.parse.quote(query.strip()[:60])
        url = f"https://pixabay.com/api/videos/?key={PIXABAY_API_KEY}&q={clean_q}&video_type=all&per_page={per_page}"
        res = requests.get(url, timeout=15)
        if res.status_code != 200:
            return []
        out = []
        for hit in res.json().get("hits", []):
            videos = hit.get("videos", {}) or {}
            target = videos.get("large") or videos.get("medium") or videos.get("small") or {}
            video_url = target.get("url")
            if not video_url:
                continue
            tags = str(hit.get("tags") or "")
            out.append({
                "source": "pixabay",
                "id": str(hit.get("id") or video_url),
                "query": query,
                "text": tags,
                "preview_url": target.get("thumbnail", ""),
                "video_url": video_url,
                "width": int(target.get("width") or 0),
                "height": int(target.get("height") or 0),
                "duration": float(hit.get("duration") or 0),
                "style": "animation" if "animation" in tags.lower() else "live",
            })
        return out
    except Exception as exc:
        print(f"Pixabay candidate-pool notice: {exc}", flush=True)
        return []


def _coverr_candidates(query: str, per_page: int = 5) -> list:
    if not COVERR_API_KEY or not query:
        return []
    try:
        clean_q = urllib.parse.quote(query.strip()[:60])
        url = f"https://api.coverr.co/videos?query={clean_q}&urls=true&page_size={per_page}"
        res = requests.get(url, headers={"Authorization": f"Bearer {COVERR_API_KEY}"}, timeout=15)
        if res.status_code != 200:
            return []
        out = []
        for hit in res.json().get("hits", []):
            video_url = (hit.get("urls") or {}).get("mp4")
            if not video_url:
                continue
            preview = (
                hit.get("thumbnail")
                or hit.get("poster")
                or hit.get("image")
                or (hit.get("urls") or {}).get("thumbnail")
                or ""
            )
            out.append({
                "source": "coverr",
                "id": str(hit.get("id") or video_url),
                "query": query,
                "text": f"{hit.get('title', '')} {_coverr_tags_text(hit)}".strip(),
                "preview_url": preview,
                "video_url": video_url,
                "width": int(hit.get("width") or 0),
                "height": int(hit.get("height") or 0),
                "duration": float(hit.get("duration") or 0),
                "style": "live",
            })
        return out
    except Exception as exc:
        print(f"Coverr candidate-pool notice: {exc}", flush=True)
        return []


def _wikimedia_candidates(query: str, limit: int = 5) -> list:
    if not query:
        return []
    try:
        clean_q = urllib.parse.quote(f"filetype:video {query.strip()[:60]}")
        search_url = (
            "https://commons.wikimedia.org/w/api.php?action=query&format=json"
            f"&generator=search&gsrsearch={clean_q}&gsrnamespace=6&gsrlimit={limit}"
            "&prop=imageinfo&iiprop=url%7Cmime%7Csize&iiurlwidth=640"
        )
        headers = {"User-Agent": "long-video-devotional-bot/1.0 (automated free stock B-roll fetch)"}
        res = requests.get(search_url, headers=headers, timeout=15)
        if res.status_code != 200:
            return []
        out = []
        for page in (res.json().get("query", {}).get("pages", {}) or {}).values():
            infos = page.get("imageinfo", []) or []
            if not infos:
                continue
            info = infos[0]
            file_url = info.get("url")
            mime = info.get("mime", "")
            if not file_url or not str(mime).startswith("video/"):
                continue
            title = page.get("title", "")
            out.append({
                "source": "wikimedia",
                "id": str(title or file_url),
                "query": query,
                "text": title,
                "preview_url": info.get("thumburl", ""),
                "video_url": file_url,
                "width": int(info.get("width") or 0),
                "height": int(info.get("height") or 0),
                "duration": 0.0,
                "style": "live",
            })
        return out
    except Exception as exc:
        print(f"Wikimedia candidate-pool notice: {exc}", flush=True)
        return []


def _collect_visual_candidates(queries: list, orientation: str) -> list:
    """Collect 5-15 lightweight candidate records without downloading video."""
    target = _candidate_target_count()
    query_limit = _rerank_query_limit()
    pool = []
    seen = set()

    for query in (queries or [])[:query_limit]:
        # Pexels/Pixabay generally provide the best preview metadata for CLIP,
        # so collect them first; Coverr adds variety. Wikimedia is queried only
        # if the pool is still thin, reducing API traffic.
        batches = [
            _pexels_candidates(query, orientation, per_page=5),
            _pixabay_candidates(query, per_page=5),
            _coverr_candidates(query, per_page=4),
        ]
        for batch in batches:
            for candidate in batch:
                key = _candidate_key(candidate)
                if not candidate.get("video_url") or not key or key in seen:
                    continue
                seen.add(key)
                pool.append(candidate)

        if len(pool) >= target:
            break

    if len(pool) < 5:
        for query in (queries or [])[:query_limit]:
            for candidate in _wikimedia_candidates(query, limit=5):
                key = _candidate_key(candidate)
                if not candidate.get("video_url") or not key or key in seen:
                    continue
                seen.add(key)
                pool.append(candidate)
            if len(pool) >= target:
                break

    # Avoid spending CLIP time on dozens of previews. Keep the first 15
    # deduplicated candidates; search APIs have already ranked them by query.
    return pool[:15]


def _score_visual_candidates(candidates: list, beat: dict, beat_prompt: str,
                             orientation: str, previous_candidate: dict = None) -> list:
    if not candidates:
        return []

    requirements = extract_visual_requirements(
        " ".join(str(q) for q in beat.get("queries", [])),
        beat_prompt,
    )
    target_text = " ".join([
        str(beat.get("narrationText") or ""),
        str(beat.get("subject") or ""),
        str(beat.get("action") or ""),
        str(beat.get("setting") or ""),
        beat_prompt,
    ])

    preview_urls = [c.get("preview_url", "") for c in candidates]
    clip_sims = None
    continuity_sims = None
    if clip_rerank is not None and clip_rerank.enabled():
        clip_sims = clip_rerank.similarities(beat_prompt, preview_urls)
        previous_preview = str((previous_candidate or {}).get("preview_url") or "")
        if previous_preview:
            continuity_sims = clip_rerank.image_similarities(
                previous_preview,
                preview_urls,
            )

    scored = []
    clip_floor = (
        clip_rerank.min_similarity()
        if clip_rerank is not None and clip_rerank.enabled()
        else 0.0
    )

    for index, candidate in enumerate(candidates):
        entity_action, accepted, reject_reason = _candidate_entity_action_score(
            candidate, beat, requirements
        )
        if not accepted:
            candidate = dict(candidate)
            candidate["selectionScore"] = 0.0
            candidate["rejected"] = True
            candidate["rejectReason"] = reject_reason
            scored.append(candidate)
            continue

        lexical_semantic = _candidate_text_score(
            candidate.get("text", ""),
            target_text,
        )
        clip_sim = None
        if clip_sims and index < len(clip_sims):
            clip_sim = clip_sims[index]

        clip_rejected = False
        if clip_sim is not None:
            if clip_sim < clip_floor:
                semantic = 0.0
                clip_rejected = True
            else:
                semantic = _clamp01(
                    (clip_sim - clip_floor) / max(0.08, 0.35 - clip_floor)
                )
                semantic = max(semantic, lexical_semantic * 0.55)
        else:
            semantic = lexical_semantic

        continuity_sim = None
        if continuity_sims and index < len(continuity_sims):
            continuity_sim = continuity_sims[index]

        (
            continuity_score,
            continuity_rejected,
            continuity_reason,
            continuity_profile,
            continuity_flags,
        ) = _candidate_continuity_score(
            candidate,
            beat,
            previous_candidate=previous_candidate,
            preview_similarity=continuity_sim,
        )

        breakdown = {
            "semantic": semantic,
            "entity_action": entity_action,
            "quality": _candidate_quality_score(candidate, orientation),
            "motion": _candidate_motion_score(candidate),
            "continuity": continuity_score,
            "novelty": _candidate_novelty_score(candidate),
            "composition": _candidate_composition_score(candidate, orientation),
        }
        total = sum(
            _VISUAL_SCORE_WEIGHTS[k] * breakdown[k]
            for k in _VISUAL_SCORE_WEIGHTS
        )

        candidate = dict(candidate)
        candidate["selectionScore"] = round(total, 4)
        candidate["scoreBreakdown"] = {
            k: round(v, 4) for k, v in breakdown.items()
        }
        candidate["clipSimilarity"] = (
            None if clip_sim is None else round(float(clip_sim), 4)
        )
        candidate["continuitySimilarity"] = (
            None
            if continuity_sim is None
            else round(float(continuity_sim), 4)
        )
        candidate["continuityProfile"] = continuity_profile
        candidate["continuityFlags"] = continuity_flags

        rejected = bool(clip_rejected or continuity_rejected)
        reasons = []
        if clip_rejected:
            reasons.append("clip_similarity_below_floor")
        if continuity_rejected and continuity_reason:
            reasons.append(continuity_reason)

        candidate["rejected"] = rejected
        candidate["rejectReason"] = "|".join(reasons)
        scored.append(candidate)

    scored.sort(
        key=lambda candidate: (
            0 if candidate.get("rejected") else 1,
            float(candidate.get("selectionScore") or 0.0),
            0
            if _candidate_key(candidate) in RECENTLY_USED_CLIP_IDS
            else 1,
        ),
        reverse=True,
    )
    return scored


def _download_ranked_candidate(candidate: dict, dest_path: str) -> bool:
    source = candidate.get("source")
    url = candidate.get("video_url")
    if not source or not url:
        return False

    if source == "wikimedia":
        raw_path = dest_path + ".raw"
        try:
            headers = {"User-Agent": "long-video-devotional-bot/1.0 (automated free stock B-roll fetch)"}
            res = requests.get(url, headers=headers, timeout=45)
            if res.status_code != 200 or len(res.content) <= 100000:
                return False
            with open(raw_path, "wb") as f:
                f.write(res.content)
            convert = subprocess.run(
                [
                    "ffmpeg", "-y", "-i", raw_path,
                    "-vf", "scale='min(1920,iw)':-2",
                    "-c:v", "libx264", "-preset", "veryfast",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", dest_path,
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            ok = (
                convert.returncode == 0
                and os.path.exists(dest_path)
                and os.path.getsize(dest_path) > 50000
            )
            if ok:
                record_clip_usage(source, candidate.get("id"))
            return ok
        finally:
            if os.path.exists(raw_path):
                os.remove(raw_path)

    try:
        res = requests.get(url, timeout=45)
        if res.status_code != 200 or len(res.content) <= 100000:
            return False
        with open(dest_path, "wb") as f:
            f.write(res.content)
        record_clip_usage(source, candidate.get("id"))
        return True
    except Exception as exc:
        print(f"{source} ranked-candidate download notice: {exc}", flush=True)
        return False


def select_best_visual_candidate(queries: list, beat: dict, beat_prompt: str,
                                 orientation: str, dest_path: str,
                                 previous_candidate: dict = None) -> dict:
    """Collect, score and download the strongest candidate for one beat.

    If the top candidate fails to download, try the next ranked candidate.
    If every candidate is below the quality/relevance threshold, return {}
    so the caller can use its narration-specific AI-image fallback.
    """
    candidates = _collect_visual_candidates(queries, orientation)
    if not candidates:
        return {}

    ranked = _score_visual_candidates(
        candidates,
        beat,
        beat_prompt,
        orientation,
        previous_candidate=previous_candidate,
    )
    threshold = _candidate_min_score()
    viable = [
        c for c in ranked
        if not c.get("rejected") and float(c.get("selectionScore") or 0.0) >= threshold
    ]

    top_preview = [
        {
            "source": c.get("source"),
            "score": c.get("selectionScore"),
            "query": c.get("query"),
            "text": str(c.get("text") or "")[:80],
        }
        for c in ranked[:3]
    ]
    print(
        f"    🧠 Rerank: {len(candidates)} candidate(s), threshold={threshold:.2f}, "
        f"top={top_preview}",
        flush=True,
    )

    for candidate in viable:
        if _download_ranked_candidate(candidate, dest_path):
            return candidate

    return {}


def _visual_beat_prompt(scene_prompt: str, beat: dict) -> str:
    """Build one media-generation/search context string for a visual beat."""
    parts = [
        scene_prompt,
        f"Narration beat: {beat.get('narrationText', '')}",
        f"Subject: {beat.get('subject', '')}",
        f"Action: {beat.get('action', '')}",
        f"Setting: {beat.get('setting', '')}",
        f"Mood: {beat.get('mood', '')}",
        f"Time: {beat.get('time', '')}",
        f"Shot type: {beat.get('shotType', '')}",
        f"Style profile: {json.dumps(beat.get('styleProfile') or {}, ensure_ascii=False)}",
    ]
    return ". ".join(str(p).strip(" .") for p in parts if str(p).strip(" ."))


def _visual_beat_queries(beat: dict, fallback_query: str = "") -> list:
    """Return an ordered, de-duplicated query bundle for one visual beat.

    Phase 2 deliberately tries several director-authored beat queries but
    still selects the first acceptable stock result. Multi-candidate semantic
    reranking is a later phase.
    """
    configured_limit = int(os.getenv("VISUAL_BEAT_MAX_QUERIES", "3") or 3)
    limit = max(1, min(4, configured_limit))

    queries = []
    for raw in (beat.get("queries") or []):
        q = re.sub(r"\s+", " ", str(raw or "")).strip()
        if q and q.lower() not in {x.lower() for x in queries}:
            queries.append(q)
        if len(queries) >= limit:
            break

    fallback_query = re.sub(r"\s+", " ", str(fallback_query or "")).strip()
    if fallback_query and fallback_query.lower() not in {x.lower() for x in queries}:
        queries.append(fallback_query)

    return queries[:limit]


def _generate_visual_beat_image(scene_prompt: str, beat: dict, orientation: str,
                                base_name: str) -> dict:
    """Generate a narration-specific AI image when stock misses this beat."""
    beat_index = int(beat.get("beatIndex") or 1)
    shot_type = str(beat.get("shotType") or "medium").replace("_", " ")
    camera = str(beat.get("cameraMotion") or "slow_push_in").replace("_", " ")
    style_profile = dict(beat.get("styleProfile") or {})
    realism_phrase = (
        "stylized devotional artwork"
        if style_profile.get("realism") == "stylized"
        else "cinematic photorealistic devotional frame"
    )
    period_phrase = {
        "ancient": "ancient Indian period details, no modern objects",
        "modern": "contemporary Indian setting",
        "timeless": "timeless devotional setting",
    }.get(style_profile.get("period"), "timeless devotional setting")
    lighting_phrase = {
        "warm_golden": "warm golden devotional lighting",
        "low_key_night": "low-key night lighting with controlled highlights",
        "natural_cinematic": "natural cinematic lighting",
    }.get(style_profile.get("lighting"), "natural cinematic lighting")

    prompt = (
        f"{_visual_beat_prompt(scene_prompt, beat)}. "
        f"{shot_type} cinematic composition, designed for {camera} motion, "
        f"{realism_phrase}, {period_phrase}, {lighting_phrase}, "
        "consistent visual language, single coherent moment, no collage, no text"
    )
    aspect_ratio = "9:16" if orientation == "portrait" else "16:9"
    width, height = (1080, 1920) if orientation == "portrait" else (1920, 1080)
    filename = f"{base_name}_b{beat_index}.jpg"
    dest = os.path.join("public/images", filename)

    generate_ai_image(
        prompt,
        dest,
        aspect_ratio=aspect_ratio,
        pollinations_width=width,
        pollinations_height=height,
    )
    if not _valid_generated_image(dest):
        return {}

    return {
        "type": "image",
        "file": filename,
        "beatIndex": beat_index,
        "durationTarget": beat.get("durationTarget"),
        "subject": beat.get("subject", ""),
        "shotType": beat.get("shotType", ""),
        "queryUsed": "",
        "source": "ai_image",
        "queryCandidates": beat.get("queries", []),
        "motionProfile": "cinematic_depth",
        "continuityProfile": {
            "realism": style_profile.get("realism", "cinematic_realism"),
            "period": style_profile.get("period", "timeless"),
            "lighting": style_profile.get("lighting", "warm_golden"),
            "settingMatch": 1.0,
        },
        "continuityFlags": [],
    }


def fetch_visual_beat_shots(scene: dict, scene_prompt: str, orientation: str,
                            base_name: str, fallback_query: str = "",
                            force_images: bool = False) -> list:
    """Resolve exactly one visual shot per director beat.

    Phase 3 compares a lightweight multi-source candidate pool before
    downloading the winner. If no candidate clears the relevance/quality
    threshold, use a narration-specific AI image instead of unrelated stock.
    """
    beats = scene.get("visualBeats") or scene.get("director", {}).get("visualBeats") or []
    if not beats:
        return []

    shots = []
    previous_candidate = None
    print(
        f"  🎯 Visual-beat retrieval: {len(beats)} beat(s), "
        f"candidate target={_candidate_target_count()}, "
        f"rerank queries={_rerank_query_limit()}/beat.",
        flush=True,
    )

    for fallback_index, beat in enumerate(beats, 1):
        beat = dict(beat or {})
        beat_index = int(beat.get("beatIndex") or fallback_index)
        queries = _visual_beat_queries(beat, fallback_query)
        beat_prompt = _visual_beat_prompt(scene_prompt, beat)
        shot = {}

        if not force_images and queries:
            filename = f"{base_name}_b{beat_index}.mp4"
            dest = os.path.join("public/images", filename)
            print(
                f"    🔎 Beat {beat_index}: {beat.get('narrationCue', '')[:70]} "
                f"→ queries={queries}",
                flush=True,
            )

            selected = select_best_visual_candidate(
                queries=queries,
                beat=beat,
                beat_prompt=beat_prompt,
                orientation=orientation,
                dest_path=dest,
                previous_candidate=previous_candidate,
            )
            if selected:
                shot = {
                    "type": "video",
                    "file": filename,
                    "beatIndex": beat_index,
                    "durationTarget": beat.get("durationTarget"),
                    "subject": beat.get("subject", ""),
                    "shotType": beat.get("shotType", ""),
                    "queryUsed": selected.get("query", ""),
                    "source": selected.get("source", "unknown"),
                    "queryCandidates": queries,
                    "selectionScore": selected.get("selectionScore"),
                    "scoreBreakdown": selected.get("scoreBreakdown", {}),
                    "clipSimilarity": selected.get("clipSimilarity"),
                    "continuitySimilarity": selected.get("continuitySimilarity"),
                    "continuityProfile": selected.get("continuityProfile", {}),
                    "continuityFlags": selected.get("continuityFlags", []),
                    "candidateId": selected.get("id"),
                }
                previous_candidate = selected
                print(
                    f"    ✅ Beat {beat_index}: selected {selected.get('source')} "
                    f"score={selected.get('selectionScore')} "
                    f"continuity={selected.get('scoreBreakdown', {}).get('continuity')} "
                    f"flags={selected.get('continuityFlags', [])} "
                    f"query='{selected.get('query')}'",
                    flush=True,
                )
            else:
                # Keep the hand-curated local library as a zero-network,
                # trusted fallback before generating an AI image. Strict
                # mythology scenes intentionally skip this fuzzy filename match.
                requirements = extract_visual_requirements(" ".join(queries), beat_prompt)
                local_terms = " ".join(queries)
                if not requirements.get("strict") and fetch_local_library_video(local_terms, dest):
                    shot = {
                        "type": "video",
                        "file": filename,
                        "beatIndex": beat_index,
                        "durationTarget": beat.get("durationTarget"),
                        "subject": beat.get("subject", ""),
                        "shotType": beat.get("shotType", ""),
                        "queryUsed": local_terms,
                        "source": "local_library",
                        "queryCandidates": queries,
                        "selectionScore": 1.0,
                        "scoreBreakdown": {"curated_local_library": 1.0},
                        "clipSimilarity": None,
                        "continuitySimilarity": None,
                        "continuityProfile": {
                            "realism": (beat.get("styleProfile") or {}).get("realism", "cinematic_realism"),
                            "period": (beat.get("styleProfile") or {}).get("period", "timeless"),
                            "lighting": (beat.get("styleProfile") or {}).get("lighting", "warm_golden"),
                            "settingMatch": 1.0,
                        },
                        "continuityFlags": ["curated_local_library"],
                        "candidateId": "local_library",
                    }
                    previous_candidate = {
                        "source": "local_library",
                        "id": "local_library",
                        "style": "live",
                        "continuityProfile": shot.get("continuityProfile", {}),
                    }

        if not shot:
            print(
                f"    🎨 Beat {beat_index}: no stock candidate cleared the gate; "
                "using narration-specific AI visual.",
                flush=True,
            )
            shot = _generate_visual_beat_image(
                scene_prompt,
                beat,
                orientation=orientation,
                base_name=base_name,
            )
            if shot:
                previous_candidate = {
                    "source": "ai_image",
                    "id": shot.get("file", f"ai_beat_{beat_index}"),
                    "style": (
                        "animation"
                        if (beat.get("styleProfile") or {}).get("realism") == "stylized"
                        else "live"
                    ),
                    "continuityProfile": shot.get("continuityProfile", {}),
                    "preview_url": "",
                }

        if shot:
            transition = beat.get("transition")
            if transition in {"cut", "crossfade", "blur_cut"}:
                shot["transition"] = transition
            shots.append(shot)

    return shots


def fetch_video_shots_for_duration(primary_query: str, prompt_text: str, target_seconds: float,
                                    orientation: str, base_name: str,
                                    max_shots: int = MAX_VIDEO_SHOTS_PER_SCENE) -> tuple:
    """Returns (shots, covered_seconds). `shots` is a list of
    {"type": "video", "file": <filename under public/images/>} dicts in shot
    order. `covered_seconds` is the sum of each fetched clip's own measured
    duration - callers compare this against target_seconds and top up any
    remainder with AI-image sub-shots (see generate_multi_shot_ai_images)."""
    shots = []
    covered = 0.0
    # Several plausible phrasings for this scene, reused round-robin across
    # shot attempts - build_query_candidates() already exists for the
    # single-clip case, so this just cycles through the same list instead of
    # re-querying with the exact same phrase every time.
    query_variants = build_query_candidates(primary_query, prompt_text) or [primary_query]

    for shot_index in range(max(1, max_shots)):
        if covered >= target_seconds:
            break
        query = query_variants[shot_index % len(query_variants)]
        dest_name = f"{base_name}_v{shot_index}.mp4"
        dest_path = f"public/images/{dest_name}"
        if not fetch_multi_source_video(query, dest_path, orientation=orientation, prompt_text=prompt_text):
            # Ran out of real stock footage for this scene entirely - stop
            # here rather than trying every remaining shot slot in vain; the
            # caller tops up the rest with AI images.
            break
        clip_duration = get_audio_duration(dest_path)
        shots.append({"type": "video", "file": dest_name})
        covered += clip_duration
        print(f"    🎬 Shot {shot_index + 1} for '{base_name}': {clip_duration:.1f}s (covered {covered:.1f}s / {target_seconds:.1f}s target)", flush=True)

    return shots, covered

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
    clean_text = text_free_prompt(prompt).replace("\"", "").strip()
    final_prompt = f"{clean_text}, Indian mythological devotional painting, {aspect_ratio} composition, warm divine lighting, highly detailed"

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
    clean_text = text_free_prompt(prompt).replace("\"", "").strip()
    final_prompt = f"{clean_text}, Indian mythological devotional painting, {aspect_ratio} composition, warm divine lighting, highly detailed"
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

def _valid_generated_image(path: str, min_bytes: int = 8000) -> bool:
    """Reject missing, corrupt, tiny, or near-solid images before Remotion sees them."""
    if not path or not os.path.exists(path) or os.path.getsize(path) < min_bytes:
        return False
    try:
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height,codec_name",
             "-of", "json", path],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, timeout=10,
        )
        info = json.loads(probe.stdout or "{}").get("streams", [])
        if not info or int(info[0].get("width", 0)) < 256 or int(info[0].get("height", 0)) < 256:
            return False
    except Exception:
        return False

    # Detect the exact class of placeholder that caused the recent black screens:
    # a tiny-variance, very-dark image. Sample a downscaled frame with ffmpeg.
    try:
        sample = subprocess.run(
            ["ffmpeg", "-v", "error", "-i", path, "-vf", "scale=32:32,format=gray",
             "-frames:v", "1", "-f", "rawvideo", "pipe:1"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=10,
        )
        pixels = list(sample.stdout)
        if len(pixels) < 512:
            return False
        avg = sum(pixels) / len(pixels)
        variance = sum((p - avg) ** 2 for p in pixels) / len(pixels)
        if avg < 18 and variance < 25:
            print(f"  ⚠️ Rejected near-black/flat image: avg={avg:.1f}, variance={variance:.1f}", flush=True)
            return False
    except Exception:
        return False
    return True


def generate_hf_fallback_model(prompt: str, dest_path: str, model_id: str,
                               aspect_ratio: str = "16:9") -> bool:
    """Try an alternate Hugging Face text-to-image model when the primary FLUX route fails.

    This is optional: it only runs when HUGGINGFACE_API_KEY is configured.
    Public models can still fail if the provider does not currently expose them.
    """
    if not HUGGINGFACE_API_KEY or not prompt or not model_id:
        return False
    url = f"https://router.huggingface.co/hf-inference/models/{model_id}"
    width, height = (1024, 576) if aspect_ratio == "16:9" else (576, 1024)
    clean_text = text_free_prompt(prompt).replace("\"", "").strip()
    final_prompt = f"{clean_text}, Indian mythological devotional painting, {aspect_ratio} composition, warm divine lighting, highly detailed"
    try:
        res = requests.post(
            url,
            headers={"Authorization": f"Bearer {HUGGINGFACE_API_KEY}", "Content-Type": "application/json"},
            timeout=60,
            json={"inputs": final_prompt[:450], "parameters": {"width": width, "height": height}},
        )
        if res.status_code == 200 and res.headers.get("content-type", "").startswith("image/"):
            with open(dest_path, "wb") as f:
                f.write(res.content)
            if _valid_generated_image(dest_path):
                print(f"  ✅ Image fetched from Hugging Face ({model_id})", flush=True)
                return True
            try:
                os.remove(dest_path)
            except OSError:
                pass
        else:
            print(f"Hugging Face fallback notice ({model_id}): HTTP {res.status_code}", flush=True)
    except Exception as e:
        print(f"Hugging Face fallback notice ({model_id}): {e}", flush=True)
    return False


def generate_ai_image(prompt: str, dest_path: str, aspect_ratio: str = "16:9",
                       pollinations_width: int = 1920, pollinations_height: int = 1080) -> None:
    """Single entry point for AI visuals with resilient, validated fallbacks.

    Order:
      1. Cloudflare FLUX
      2. Hugging Face FLUX.1-schnell
      3. Optional HF SDXL
      4. Optional HF Qwen-Image
      5. Optional HF SD 3.5 Medium
      6. Pollinations
      7. No dark placeholder: caller will fall through to stock/local assets
    """
    import hashlib
    cache_key = hashlib.sha256(
        f"{prompt.strip()}|{aspect_ratio}|{pollinations_width}x{pollinations_height}".encode("utf-8")
    ).hexdigest()[:24]
    cache_dir = os.path.join("out", "visual_cache")
    os.makedirs(cache_dir, exist_ok=True)
    cache_path = os.path.join(cache_dir, cache_key + ".png")
    if _valid_generated_image(cache_path):
        shutil.copyfile(cache_path, dest_path)
        print(f"  ♻️ AI visual cache hit: {cache_key}", flush=True)
        return

    if generate_cloudflare_flux(prompt, dest_path, aspect_ratio=aspect_ratio) and _valid_generated_image(dest_path):
        print("  ✅ Image fetched from Cloudflare FLUX", flush=True)
    elif generate_huggingface_image(prompt, dest_path, aspect_ratio=aspect_ratio) and _valid_generated_image(dest_path):
        print("  ✅ Image fetched from Hugging Face (FLUX.1-schnell)", flush=True)
    else:
        fallback_models = [
            ("stabilityai/stable-diffusion-xl-base-1.0", "SDXL"),
            ("Qwen/Qwen-Image-2512", "Qwen-Image"),
            ("stabilityai/stable-diffusion-3.5-medium", "SD 3.5 Medium"),
        ]
        generated = False
        for model_id, label in fallback_models:
            if generate_hf_fallback_model(prompt, dest_path, model_id, aspect_ratio=aspect_ratio):
                generated = True
                break
        if not generated:
            generated = download_pollinations_fallback(
                prompt, dest_path, width=pollinations_width, height=pollinations_height
            )
        if generated and not _valid_generated_image(dest_path):
            try:
                os.remove(dest_path)
            except OSError:
                pass

    if _valid_generated_image(dest_path):
        try:
            shutil.copyfile(dest_path, cache_path)
        except Exception:
            pass


def download_pollinations_fallback(prompt: str, img_dest: str, width: int = 1920, height: int = 1080) -> bool:
    clean_text = text_free_prompt(prompt).replace("\"", "").strip()[:220]
    encoded = urllib.parse.quote(f"{clean_text}, Indian devotional painting")
    seed = random.randint(1000, 999999)
    url = f"https://image.pollinations.ai/prompt/{encoded}?width={width}&height={height}&model=turbo&seed={seed}&nologo=true"

    for attempt in range(1, 4):
        try:
            res = requests.get(url, headers=HEADERS, timeout=30)
            if res.status_code == 200 and len(res.content) > 8000:
                with open(img_dest, "wb") as f:
                    f.write(res.content)
                if _valid_generated_image(img_dest):
                    return True
                try:
                    os.remove(img_dest)
                except OSError:
                    pass
        except Exception:
            pass
        time.sleep(1)

    # Never manufacture a dark placeholder. Returning False lets the caller
    # continue to its real-stock/local-library fallback instead.
    return False

# -------------------------------------------------------------
# 2b. MULTI-SHOT AI IMAGE FALLBACK
# -------------------------------------------------------------
def generate_multi_shot_ai_images(
    prompt: str,
    base_name: str,
    aspect_ratio: str = "16:9",
    num_shots: int = 2,
    pollinations_width: int = 1920,
    pollinations_height: int = 1080,
    framing_hints: list = None,
) -> list:
    """Generate several visually distinct AI-image shots for one narration scene.

    Each shot gets a different camera/framing instruction while preserving the
    same core scene prompt. This keeps long narration from looking like one
    frozen still and gives Scene.tsx multiple frames to animate/cross-fade.
    """
    hints = framing_hints or [
        "cinematic medium shot",
        "close-up detail",
        "dramatic low angle",
        "wide establishing shot",
    ]
    count = max(1, int(num_shots or 1))
    filenames = []

    for shot_index in range(count):
        framing = hints[shot_index % len(hints)]
        shot_prompt = (
            f"{prompt}, {framing}, shot {shot_index + 1} of {count}, "
            "distinct composition from the previous shot, cinematic visual storytelling"
        )
        filename = f"{base_name}_{shot_index + 1}.jpg"
        dest = os.path.join("public/images", filename)
        try:
            generate_ai_image(
                shot_prompt,
                dest,
                aspect_ratio=aspect_ratio,
                pollinations_width=pollinations_width,
                pollinations_height=pollinations_height,
            )
            if _valid_generated_image(dest):
                filenames.append(filename)
                print(
                    f"    🎨 AI sub-shot {shot_index + 1}/{count}: {filename}",
                    flush=True,
                )
        except Exception as e:
            print(
                f"AI sub-shot {shot_index + 1} notice: {e}",
                flush=True,
            )

    return filenames


# -------------------------------------------------------------
# 3. AUDIO SYNTHESIS ENGINE
# -------------------------------------------------------------
# Primary: local Kokoro Hindi TTS (free/open weights, no API key).
# Fallback: the existing Edge-TTS path. Set AUDIO_TTS_ENGINE=edge to force
# the legacy engine, or kokoro to require Kokoro.
# -------------------------------------------------------------
from audio_engine import generate_kokoro_audio, KOKORO_AVAILABLE

def _fit_long_narration_to_target(audio_paths: list, word_timings: list, target_seconds: float = 205.0) -> float:
    """Keep long-form narration inside the production duration target.

    The Make payload can occasionally contain a perfectly valid story whose
    generated narration is longer than the 150-210s production window. Rather
    than rendering a >210s file and failing QC, speed the narration uniformly
    with FFmpeg's atempo filter (pitch-preserving), then scale the word
    timestamps by the same factor so subtitles stay synchronized.
    """
    durations = [get_audio_duration(path) for path in audio_paths if os.path.exists(path)]
    total = sum(durations)
    if total <= target_seconds or total <= 0:
        return total

    # Speeding speech up by more than ~8% is clearly audible and makes the
    # voice sound mechanical, so never compress harder than that; a slightly
    # longer video is better than a chipmunk-fast narrator.
    max_factor = float(os.getenv("NARRATION_MAX_TEMPO", "1.08"))
    factor = min(max_factor, max(1.0, total / target_seconds))
    if total / target_seconds > max_factor:
        print(f"⚠️ Narration {total:.1f}s exceeds target even at {max_factor}x; keeping natural pace (video will run longer).", flush=True)
    print(
        f"🎚️ Long narration is {total:.2f}s; fitting to {target_seconds:.0f}s "
        f"with pitch-preserving {factor:.3f}x tempo.",
        flush=True,
    )

    for path in audio_paths:
        if not os.path.exists(path):
            continue
        temp_path = path + ".fit.mp3"
        result = subprocess.run(
            [
                "ffmpeg", "-y", "-i", path,
                "-filter:a", f"atempo={factor:.6f}",
                "-ar", "24000", "-ac", "1",
                "-c:a", "libmp3lame", "-q:a", "3",
                temp_path,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if result.returncode != 0 or not os.path.exists(temp_path):
            raise RuntimeError(f"Failed to fit narration audio: {path}")
        os.replace(temp_path, path)

    for timings in word_timings:
        if not timings:
            continue
        for cue in timings:
            cue["start"] = round(float(cue.get("start", 0)) / factor, 3)
            cue["end"] = round(float(cue.get("end", 0)) / factor, 3)

    return sum(get_audio_duration(path) for path in audio_paths if os.path.exists(path))


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

def _naturalize_text(text: str) -> str:
    """Add gentle punctuation cues so local TTS engines breathe naturally."""
    text = re.sub(r"\s+", " ", (text or "").strip())
    text = re.sub(r"[,，]\s*", ", ", text)
    text = re.sub(r"([!?।])\s*", r"\1 ", text)
    return text.strip()

def _fallback_word_timings(text: str, audio_path: str) -> list:
    """Approximate word timings for TTS engines without WordBoundary events."""
    words = re.findall(r"\S+", text or "")
    if not words:
        return []
    duration = max(0.1, get_audio_duration(audio_path))
    weights = [max(1, len(w.strip(".,!?।"))) for w in words]
    total = float(sum(weights))
    cursor = 0.0
    timings = []
    for word, weight in zip(words, weights):
        span = duration * weight / total
        timings.append({
            "word": word,
            "start": round(cursor, 3),
            "end": round(cursor + span, 3),
        })
        cursor += span
    return timings

async def _generate_edge_chunked_audio(clean_text: str, audio_dest: str) -> list:
    """Generate narration sentence-by-sentence for more human pacing.

    Edge's Hindi neural voices are free to use through edge-tts and provide
    natural prosody. Generating shorter sentence chunks lets punctuation create
    real pauses instead of forcing one long paragraph through a single prosodic
    pass. WordBoundary timings are preserved with cumulative offsets.
    """
    voice = os.getenv("EDGE_TTS_VOICE", "hi-IN-MadhurNeural")
    rate = os.getenv("EDGE_TTS_RATE", "-6%")
    pitch = os.getenv("EDGE_TTS_PITCH", "-2Hz")
    pause_ms = max(0, int(os.getenv("EDGE_TTS_SENTENCE_PAUSE_MS", "140")))

    # One synthesis pass per scene keeps the neural voice's natural intonation
    # across sentences; sentence-by-sentence synthesis resets the pitch contour
    # on every sentence, which is what made narration sound robotic. Set
    # EDGE_TTS_SENTENCE_CHUNKS=true to restore the old behaviour.
    if os.getenv("EDGE_TTS_SENTENCE_CHUNKS", "false").lower() == "true":
        chunks = [
            part.strip()
            for part in re.split(r"(?<=[।!?])\s+|(?<=[.!?])\s+", clean_text)
            if part.strip()
        ]
    else:
        chunks = [clean_text]
    if not chunks:
        chunks = [clean_text]

    work_dir = audio_dest + ".chunks"
    os.makedirs(work_dir, exist_ok=True)
    chunk_paths = []
    all_timings = []
    cursor = 0.0

    try:
        for index, chunk in enumerate(chunks):
            path = os.path.join(work_dir, f"{index:04d}.mp3")
            communicate = edge_tts.Communicate(
                chunk,
                voice=voice,
                rate=rate,
                pitch=pitch,
            )
            submaker = edge_tts.SubMaker()
            audio_bytes = bytearray()

            async for item in communicate.stream():
                if item["type"] == "audio":
                    audio_bytes.extend(item["data"])
                elif item["type"] == "WordBoundary":
                    submaker.feed(item)

            if not audio_bytes:
                raise RuntimeError(f"Edge-TTS returned no audio for sentence {index + 1}")

            with open(path, "wb") as f:
                f.write(audio_bytes)

            duration = max(0.05, get_audio_duration(path))
            for cue in submaker.cues:
                all_timings.append({
                    "word": cue.content,
                    "start": round(cursor + cue.start.total_seconds(), 3),
                    "end": round(cursor + cue.end.total_seconds(), 3),
                })

            chunk_paths.append(path)
            cursor += duration

            if index < len(chunks) - 1:
                cursor += pause_ms / 1000.0

        # Build a tiny MP3 silence segment and concatenate:
        # sentence -> pause -> sentence -> pause -> ...
        silence = os.path.join(work_dir, "silence.mp3")
        subprocess.run(
            [
                "ffmpeg", "-y", "-f", "lavfi",
                "-i", "anullsrc=r=24000:cl=mono",
                "-t", str(pause_ms / 1000.0),
                "-c:a", "libmp3lame", "-q:a", "5", silence,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )

        concat_list = os.path.join(work_dir, "concat.txt")
        with open(concat_list, "w", encoding="utf-8") as f:
            for index, path in enumerate(chunk_paths):
                f.write(f"file '{os.path.abspath(path)}'\n")
                if index < len(chunk_paths) - 1:
                    f.write(f"file '{os.path.abspath(silence)}'\n")

        normalize = subprocess.run(
            [
                "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                "-i", concat_list,
                "-af",
                "loudnorm=I=-16:TP=-1.5:LRA=11,highpass=f=70,lowpass=f=12000",
                "-ar", "24000", "-ac", "1",
                "-c:a", "libmp3lame", "-q:a", "3",
                audio_dest,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if normalize.returncode != 0 or not os.path.exists(audio_dest):
            raise RuntimeError("FFmpeg failed while assembling chunked narration")

        return all_timings
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


async def generate_clean_audio(narration: str, audio_dest: str, beat: str = "") -> list:
    """Kokoro Hindi TTS -> cinematic pause handling -> Edge fallback.

    Kokoro is the default local Hindi voice. Edge-TTS remains the automatic
    fallback so a temporary Kokoro/model/runtime failure does not stop a run.
    """
    async with tts_semaphore:
        if has_latin(narration):
            print(f"🔤 Hindi-only notice: removed/converted Latin words before TTS: {narration[:80]}", flush=True)
        original_text = _naturalize_text(to_spoken_hindi(narration)) or "हरि ॐ तत्सत्"
        prosody = build_prosody_map(original_text, beat=beat)
        clean_text = prepare_storyteller_text(original_text)
        # Edge's Hindi neural voices (Madhur/Swara) sound far more human than
        # Kokoro's Hindi voice, which listeners described as robotic. Kokoro is
        # still available with AUDIO_TTS_ENGINE=kokoro.
        engine = os.getenv("AUDIO_TTS_ENGINE", "kokoro").strip().lower()

        # Own-voice narration (human element): IndicF5 clones the creator's
        # own recorded reference voice. Opt-in; falls back to Edge on error.
        if engine == "indicf5":
            if generate_indicf5_audio is not None:
                try:
                    ok = await asyncio.to_thread(generate_indicf5_audio, clean_text, audio_dest)
                    if ok and os.path.exists(audio_dest):
                        return _fallback_word_timings(clean_text, audio_dest)
                except Exception as e:
                    import traceback
                    print(f"IndicF5 notice: {e} - falling back to Edge-TTS.", flush=True)
                    # Shows as a yellow warning on the run's Summary page, so a
                    # non-Natasha narration is visible before you upload.
                    print(f"::warning title=Own voice NOT used::IndicF5 failed for {os.path.basename(audio_dest)} ({e}); this scene uses Edge-TTS.", flush=True)
                    traceback.print_exc()
                    if os.getenv("INDICF5_STRICT", "false").strip().lower() == "true":
                        raise RuntimeError(f"INDICF5_STRICT=true: own voice failed ({e}); stopping instead of using Edge-TTS.")
            else:
                print("IndicF5 notice: engine not installed - falling back to Edge-TTS.", flush=True)
                print("::warning title=Own voice NOT used::IndicF5 is not installed; narration uses Edge-TTS.", flush=True)
                if os.getenv("INDICF5_STRICT", "false").strip().lower() == "true":
                    raise RuntimeError("INDICF5_STRICT=true: IndicF5 engine not installed; stopping instead of using Edge-TTS.")
            engine = "edge"

        # Kokoro is primary. audio_engine.py adds real silence after cinematic
        # punctuation such as …, —, । and !/? while preserving Kokoro prosody.
        if engine in ("kokoro", "auto"):
            if KOKORO_AVAILABLE:
                try:
                    ok = await asyncio.to_thread(
                        generate_kokoro_audio, clean_text, audio_dest
                    )
                    if ok and os.path.exists(audio_dest):
                        return _fallback_word_timings(clean_text, audio_dest)
                except Exception as e:
                    print(
                        f"Kokoro notice: {e} - falling back to Edge-TTS.",
                        flush=True,
                    )
                    print(f"::warning title=Kokoro voice NOT used::{os.path.basename(audio_dest)}: {e} - this scene uses Edge-TTS.", flush=True)
            else:
                print("Kokoro notice: package unavailable - falling back to Edge-TTS.", flush=True)
                print("::warning title=Kokoro voice NOT used::Kokoro is not installed - narration uses Edge-TTS.", flush=True)

        # Edge remains available as an explicit engine and as the automatic
        # fallback when Kokoro fails.
        if engine in ("edge", "auto", "kokoro"):
            for attempt in range(1, 4):
                try:
                    timings = await _generate_edge_chunked_audio(clean_text, audio_dest)
                    if os.path.exists(audio_dest):
                        return timings
                except Exception as e:
                    print(
                        f"Edge-TTS chunked attempt {attempt} failed: {e}",
                        flush=True,
                    )
                    await asyncio.sleep(1.5)

        # Legacy single-pass Edge-TTS fallback.
        raw_path = audio_dest + ".raw.mp3"
        for attempt in range(1, 4):
            try:
                communicate = edge_tts.Communicate(
                    clean_text,
                    voice=os.getenv("EDGE_TTS_VOICE", "hi-IN-MadhurNeural"),
                    rate=os.getenv("EDGE_TTS_RATE", "-4%"),
                    pitch=os.getenv("EDGE_TTS_PITCH", "+0Hz"),
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
                        [
                            "ffmpeg", "-y", "-i", raw_path,
                            "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
                            "-ar", "24000", "-q:a", "4",
                            "-acodec", "libmp3lame", audio_dest,
                        ],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    if normalize.returncode != 0 or not os.path.exists(audio_dest):
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
            except Exception as e:
                print(f"Edge-TTS attempt {attempt} failed: {e}", flush=True)
                await asyncio.sleep(1.5)

        subprocess.run(
            [
                "ffmpeg", "-y", "-f", "lavfi",
                "-i", "anullsrc=r=24000:cl=mono",
                "-t", "5", "-c:a", "libmp3lame", "-q:a", "8", audio_dest,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return []


def estimate_scene_duration_seconds(narration_text: str) -> float:
    """Estimate spoken duration before TTS so visual shot coverage matches narration.

    Hindi narration typically runs around 2.2-2.6 spoken words/second depending
    on punctuation and delivery. We deliberately use a conservative 2.35 words/s
    target and add small pause allowances for sentence punctuation. The final
    Remotion duration is still taken from the actual generated audio, so this
    estimate only controls how much visual material we fetch/generate.
    """
    text = re.sub(r"\s+", " ", (narration_text or "").strip())
    if not text:
        return 5.0

    words = re.findall(r"\S+", text)
    base_seconds = len(words) / 2.35

    # Natural pause allowance for punctuation. Keep it modest because actual
    # TTS duration is authoritative later.
    pause_seconds = (
        len(re.findall(r"[।!?]", text)) * 0.28
        + len(re.findall(r"[,;:]", text)) * 0.08
    )
    estimated = base_seconds + pause_seconds
    return round(max(5.0, min(120.0, estimated)), 2)

# -------------------------------------------------------------
# 4. PROCESS LONG VIDEO SCENES (Pexels + Pixabay + Coverr + FLUX.1)
# -------------------------------------------------------------
def process_long_scene_visual(scene_info):
    """Resolve long-form visuals.

    Phase 2 prefers the narration-aware visualBeats plan from director.py:
    one ordered shot per beat, with up to several beat-specific stock queries
    before an AI-image fallback. Older/no-plan payloads keep the existing
    duration-aware scene-level path unchanged.
    """
    idx, scene = scene_info
    prompt = scene.get("imagePrompt") or scene.get("image_prompt", "Indian spiritual story scene")
    media_type = scene.get("mediaType", "auto").lower()
    visual_entities = scene.get("visualEntities") or scene.get("visual_entities") or []
    visual_attributes = scene.get("visualAttributes") or scene.get("visual_attributes") or []
    visual_strict = bool(scene.get("visualStrict") or scene.get("visual_strict") or visual_entities)
    if visual_strict and visual_entities:
        visual_contract = (
            f" REQUIRED VISUAL ENTITY: {', '.join(map(str, visual_entities))}."
            f" REQUIRED ATTRIBUTES: {', '.join(map(str, visual_attributes))}."
            " Do not substitute a generic person, child, animal, statue, or unrelated deity."
        )
        prompt = f"{prompt}{visual_contract}"

    video_query = scene.get("videoSearchQuery")
    if not video_query:
        words = [w for w in prompt.split() if w.lower() not in ["the", "a", "an", "and", "with", "in", "on", "of", "cinematic", "16:9", "lighting", "shot"]]
        video_query = " ".join(words[:4])

    visual_beats = scene.get("visualBeats") or scene.get("director", {}).get("visualBeats") or []
    if visual_beats:
        print(
            f"🎬 [Long Scene {idx}] Resolving {len(visual_beats)} narration-aware visual beats...",
            flush=True,
        )
        beat_shots = fetch_visual_beat_shots(
            scene,
            prompt,
            orientation="landscape",
            base_name=f"scene_{idx}",
            fallback_query=video_query,
            force_images=(media_type == "ai_image"),
        )
        if beat_shots:
            return beat_shots
        print(
            f"⚠️ [Long Scene {idx}] Beat-aware retrieval produced no usable assets; falling back to legacy scene-level path.",
            flush=True,
        )

    # Backward-compatible scene-level fallback.
    should_try_video = (media_type == "video") or (media_type == "auto" and idx % 2 == 0)
    narration_text = scene.get("text") or scene.get("narration_chunk", "")
    target_seconds = estimate_scene_duration_seconds(narration_text)

    shots = []
    covered = 0.0
    if should_try_video and video_query:
        print(f"🎥 [Long Scene {idx}] Legacy search ~{target_seconds:.0f}s for: '{video_query}'...", flush=True)
        shots, covered = fetch_video_shots_for_duration(
            video_query, prompt, target_seconds, orientation="landscape", base_name=f"scene_{idx}",
        )

    remaining = target_seconds - covered
    if not shots or remaining > MIN_SHOT_SECONDS:
        basis = remaining if shots else target_seconds
        num_image_shots = max(1, min(4, round(basis / SUB_SHOT_SECONDS)))
        verb = "Topping up with" if shots else "Generating"
        print(f"🎨 [Long Scene {idx}] {verb} {num_image_shots} AI visual sub-shot(s): {prompt[:40]}...", flush=True)
        filenames = generate_multi_shot_ai_images(
            prompt, f"scene_{idx}_img", "16:9", num_image_shots,
            pollinations_width=1920, pollinations_height=1080,
        )
        shots.extend({"type": "image", "file": f} for f in filenames)

    return shots

def recover_shots(shots, scene_idx, aspect="16:9") -> list:
    """Drop invalid assets; never create a black placeholder frame."""
    valid = []
    for shot in shots or []:
        path = os.path.join("public/images", shot.get("file", ""))
        if shot.get("file") and _valid_generated_image(path):
            valid.append(shot)
    if valid:
        return valid
    print(
        f"⚠️ No valid visual asset survived for scene {scene_idx}; "
        "no black placeholder will be created.",
        flush=True,
    )
    return []

# -------------------------------------------------------------
# 5. PROCESS SHORTS SCENES (9:16 Vertical)
# -------------------------------------------------------------
def process_shorts_scene_visual(scene_info):
    """Resolve Shorts visuals using the same per-beat query strategy.

    Existing hook-specific legacy behavior remains as a fallback for payloads
    without visualBeats or if every beat-aware asset attempt fails.
    """
    idx, scene = scene_info
    prompt = scene.get("imagePrompt") or scene.get("image_prompt", "Devotional sacred 9:16")
    media_type = scene.get("mediaType", "auto").lower()
    visual_entities = scene.get("visualEntities") or scene.get("visual_entities") or []
    visual_attributes = scene.get("visualAttributes") or scene.get("visual_attributes") or []
    visual_strict = bool(scene.get("visualStrict") or scene.get("visual_strict") or visual_entities)
    if visual_strict and visual_entities:
        visual_contract = (
            f" REQUIRED VISUAL ENTITY: {', '.join(map(str, visual_entities))}."
            f" REQUIRED ATTRIBUTES: {', '.join(map(str, visual_attributes))}."
            " Do not substitute a generic person, child, animal, statue, or unrelated deity."
        )
        prompt = f"{prompt}{visual_contract}"

    video_query = scene.get("videoSearchQuery") or "sacred temple diya"
    visual_beats = scene.get("visualBeats") or scene.get("director", {}).get("visualBeats") or []
    if visual_beats:
        print(
            f"🎬 [Shorts Scene {idx}] Resolving {len(visual_beats)} narration-aware visual beats...",
            flush=True,
        )
        beat_shots = fetch_visual_beat_shots(
            scene,
            f"{prompt}, vertical 9:16 composition",
            orientation="portrait",
            base_name=f"shorts_scene_{idx}",
            fallback_query=video_query,
            force_images=(media_type == "ai_image"),
        )
        if beat_shots:
            return beat_shots
        print(
            f"⚠️ [Shorts Scene {idx}] Beat-aware retrieval produced no usable assets; falling back to legacy path.",
            flush=True,
        )

    narration_text = scene.get("text") or scene.get("narration_chunk", "")
    target_seconds = estimate_scene_duration_seconds(narration_text)
    is_hook = idx == 1

    print(f"🎥 [Shorts Scene {idx}] Legacy search ~{target_seconds:.0f}s of vertical video...", flush=True)
    shots, covered = fetch_video_shots_for_duration(
        video_query, prompt, target_seconds, orientation="portrait",
        base_name=f"shorts_scene_{idx}", max_shots=3 if is_hook else 2,
    )

    remaining = target_seconds - covered
    if shots and remaining <= MIN_SHOT_SECONDS:
        return shots

    basis = remaining if shots else target_seconds
    if is_hook:
        num_image_shots = max(2, min(3, round(basis / HOOK_SUB_SHOT_SECONDS)))
        framing_hints = HOOK_SUB_SHOT_FRAMING_HINTS
        verb = "Topping up with" if shots else "No video match - generating"
        print(f"🎨 [Shorts HOOK Scene {idx}] {verb} {num_image_shots} quick, dynamic 9:16 sub-shot(s)...", flush=True)
    else:
        num_image_shots = max(1, min(2, round(basis / SUB_SHOT_SECONDS)))
        framing_hints = SUB_SHOT_FRAMING_HINTS
        verb = "Topping up with" if shots else "Generating"
        print(f"🎨 [Shorts Scene {idx}] {verb} {num_image_shots} 9:16 AI visual sub-shot(s)...", flush=True)

    filenames = generate_multi_shot_ai_images(
        f"{prompt}, vertical 9:16 composition", f"shorts_scene_{idx}_img", "9:16", num_image_shots,
        pollinations_width=1080, pollinations_height=1920,
        framing_hints=framing_hints,
    )
    shots.extend({"type": "image", "file": f} for f in filenames)
    return shots


# -------------------------------------------------------------
# 5a. PHASE-4 NARRATION-SYNCHRONISED VISUAL TIMING
# -------------------------------------------------------------
def sync_visual_beats_to_narration(scene: dict, shots: list, word_timings: list,
                                   scene_duration: float) -> tuple:
    """Map director word ranges onto real TTS timestamps.

    Director visualBeats are planned before TTS and contain wordStart/wordEnd
    indices. TTS later gives us the actual spoken start/end time for each word.
    This function joins those datasets after audio generation.

    It is intentionally tolerant of token-count drift: spoken-Hindi cleanup can
    change the number of TTS words, so director indices are projected
    proportionally onto the available timing cues rather than assuming both
    token streams have identical lengths.

    Returns (timed_beats, timed_shots). Shot ranges are gap-free: when a beat's
    visual asset could not be generated, the previous/next surviving visual
    expands to cover that missing beat instead of exposing black frames.
    """
    raw_beats = scene.get("visualBeats") or scene.get("director", {}).get("visualBeats") or []
    beats = [dict(b or {}) for b in raw_beats if isinstance(b, dict)]
    if not beats:
        return beats, [dict(s) for s in (shots or [])]

    beats.sort(key=lambda b: int(b.get("beatIndex") or 0))
    safe_scene_duration = max(0.1, float(scene_duration or 0.1))
    cues = [c for c in (word_timings or []) if isinstance(c, dict)]
    cue_count = len(cues)

    planned_word_count = max(
        1,
        max(int(b.get("wordEnd") or 0) for b in beats),
    )

    # Calculate the real start boundary for every beat. Beat 1 always starts
    # at 0 so intro ambience/scene padding is covered. Subsequent beats start
    # exactly when their first mapped narration word begins.
    boundaries = []
    timing_source = "tts_word_boundaries" if cue_count else "proportional_fallback"

    for i, beat in enumerate(beats):
        word_start = max(0, int(beat.get("wordStart") or 0))
        if i == 0:
            start = 0.0
        elif cue_count:
            ratio = word_start / planned_word_count
            cue_index = min(cue_count - 1, max(0, int(round(ratio * cue_count))))
            start = float(cues[cue_index].get("start") or 0.0)
        else:
            start = safe_scene_duration * (word_start / planned_word_count)

        # Keep boundaries strictly monotonic even if a TTS engine emits a
        # duplicate/zero timestamp for two adjacent cues.
        if boundaries:
            start = max(boundaries[-1] + 0.05, start)
        start = min(max(0.0, start), max(0.0, safe_scene_duration - 0.05))
        boundaries.append(start)

    # Convert boundaries into beat windows; the final beat covers the small
    # render tail after the last spoken word as well.
    for i, beat in enumerate(beats):
        start = boundaries[i]
        end = boundaries[i + 1] if i + 1 < len(boundaries) else safe_scene_duration
        end = max(start + 0.05, min(safe_scene_duration, end))
        beat["actualStartSeconds"] = round(start, 3)
        beat["actualEndSeconds"] = round(end, 3)
        beat["actualDurationSeconds"] = round(max(0.05, end - start), 3)
        beat["timingSource"] = timing_source
        effect_name = str(beat.get("soundEffect") or "none")
        if effect_name != "none":
            effect_rel = f"audio/effects/beat_{effect_name}.mp3"
            effect_abs = os.path.join("public", effect_rel)
            if os.path.exists(effect_abs) and os.path.getsize(effect_abs) > 1000:
                beat["soundEffectFile"] = effect_rel
            else:
                beat["soundEffectFile"] = ""
                beat["soundEffectReason"] = "effect_asset_unavailable"

    # Attach real windows to surviving shots. Usually there is one shot per
    # beat. If one beat failed to produce media, use the next surviving
    # shot's beat start as the previous shot's end so the timeline remains
    # completely covered.
    shot_list = [dict(s) for s in (shots or [])]
    beat_by_index = {
        int(b.get("beatIndex") or i + 1): b
        for i, b in enumerate(beats)
    }

    indexed_shots = []
    for i, shot in enumerate(shot_list):
        try:
            beat_index = int(shot.get("beatIndex") or i + 1)
        except Exception:
            beat_index = i + 1
        shot["beatIndex"] = beat_index
        indexed_shots.append((beat_index, i, shot))

    indexed_shots.sort(key=lambda item: (item[0], item[1]))

    for pos, (beat_index, _original_index, shot) in enumerate(indexed_shots):
        beat = beat_by_index.get(beat_index)
        if beat:
            base_start = float(beat.get("actualStartSeconds") or 0.0)
        elif pos == 0:
            base_start = 0.0
        else:
            base_start = float(indexed_shots[pos - 1][2].get("endSeconds") or 0.0)

        if pos == 0:
            start = 0.0
        else:
            start = base_start

        if pos + 1 < len(indexed_shots):
            next_beat_index = indexed_shots[pos + 1][0]
            next_beat = beat_by_index.get(next_beat_index)
            end = (
                float(next_beat.get("actualStartSeconds") or safe_scene_duration)
                if next_beat
                else safe_scene_duration
            )
        else:
            end = safe_scene_duration

        end = max(start + 0.05, min(safe_scene_duration, end))
        shot["startSeconds"] = round(start, 3)
        shot["endSeconds"] = round(end, 3)
        shot["syncedDurationSeconds"] = round(max(0.05, end - start), 3)
        shot["timingSource"] = timing_source
        if beat:
            shot["narrationCue"] = beat.get("narrationCue", "")
            shot["cameraMotion"] = beat.get("cameraMotion", "")

    # Restore visual order, which is beat order for the new path.
    timed_shots = [item[2] for item in indexed_shots]

    if timed_shots:
        print(
            f"  ⏱️ Narration sync: {len(timed_shots)} visual(s), "
            f"source={timing_source}, duration={safe_scene_duration:.2f}s, "
            f"cuts={[s.get('startSeconds') for s in timed_shots[1:]]}",
            flush=True,
        )

    return beats, timed_shots


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
    content_report = validate_payload(payload)
    with open("out/content_qc_report.json", "w", encoding="utf-8") as f:
        json.dump(content_report, f, ensure_ascii=False, indent=2)
    print(f"🧪 Content QC: {len(content_report['issues'])} blocking issue(s), {len(content_report['warnings'])} warning(s).", flush=True)
    if not content_report["ok"]:
        raise RuntimeError("Content QC failed: " + "; ".join(content_report["issues"]))
    print(f"🚀 Starting Multi-Source Production: Long Video ({len(long_scenes)} scenes) + Shorts ({len(shorts_scenes)} scenes)...", flush=True)

    # 1. Background Music fallback
    bgm_path = "public/audio/bgm.mp3"
    if not os.path.exists(bgm_path):
        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
            "-t", "30", "-q:a", "9", "-acodec", "libmp3lame", bgm_path
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # 1b. Shared transition "whoosh" - one small SFX file, reused by
    # Scene.tsx at every shot-boundary cut in both Long and Shorts renders
    # (see the multi-shot video/image fix). Resolved once here rather than
    # per-scene since it's the exact same cue everywhere, not a per-scene
    # mood choice like temple_bell/shankh/etc.
    os.makedirs("public/audio/sfx", exist_ok=True)
    resolve_sound_effect_audio("transition_whoosh", "public/audio/sfx/whoosh.mp3")

    # 2. Render ONE final high-CTR 16:9 thumbnail.
    # The pipeline intentionally keeps only one long-video thumbnail and one
    # Shorts thumbnail. thumbnailConcepts may still arrive from Make for
    # creative planning, but they are not rendered into extra files.
    thumb_prompt = thumbnail_data.get("imagePrompt") or "Lord Krishna radiant divine aura with glowing Sudarshan Chakra, dramatic 8k thumbnail"

    def _thumb_layout(base_prompt: str, title: str, vertical: bool = False):
        source = shorts_thumbnail_data if vertical else thumbnail_data
        raw = str(source.get("textPosition", "")).strip().lower()
        aliases = {
            "top-left": "topLeft", "topleft": "topLeft", "upper-left": "topLeft",
            "top-right": "topRight", "topright": "topRight", "upper-right": "topRight",
            "center-left": "centerLeft", "centerleft": "centerLeft",
            "center-right": "centerRight", "centerright": "centerRight",
            "bottom-left": "bottomLeft", "bottomleft": "bottomLeft",
            "bottom-right": "bottomRight", "bottomright": "bottomRight",
            "center": "center",
        }
        if raw in aliases:
            return aliases[raw]
        choices = ["topLeft", "topRight", "centerLeft", "centerRight", "bottomLeft", "bottomRight"]
        seed = hashlib.sha256(f"{base_prompt}|{title}|{'short' if vertical else 'long'}".encode("utf-8")).digest()[0]
        return choices[seed % len(choices)]

    def _opposite_side(layout: str):
        return {
            "topLeft": "right side",
            "topRight": "left side",
            "centerLeft": "right side",
            "centerRight": "left side",
            "bottomLeft": "upper-right area",
            "bottomRight": "upper-left area",
            "center": "upper area",
        }.get(layout, "one side")

    thumbnail_text_position = _thumb_layout(thumb_prompt, seo_metadata.get("long_video_title", ""), False)
    thumb_prompt = (
        f"{thumb_prompt}. YouTube creator thumbnail art direction: ONE dominant focal subject, "
        f"dramatic emotion/action, strong contrast, cinematic lighting, clean uncluttered composition, "
        f"no text, no watermark, no collage, no split screen. Keep the main subject unobstructed and "
        f"leave intentional clean negative space on the {_opposite_side(thumbnail_text_position)} "
        f"for a short Hindi hook."
    )
    print(f"🖼️ Generating ONE High-CTR Long Thumbnail ({thumbnail_text_position})...", flush=True)
    thumb_dest = "public/images/thumbnail.jpg"
    generate_ai_image(thumb_prompt, thumb_dest, aspect_ratio="16:9", pollinations_width=1920, pollinations_height=1080)
    subprocess.run(["cp", thumb_dest, "out/thumbnail.jpg"], check=False)

    # 2b. Remotion hook-text props. The text position is dynamic instead of
    # forcing every thumbnail into a bottom-only text band.
    thumbnail_hook_text = pick_hindi(
        thumbnail_data.get("thumbnailText"),
        seo_metadata.get("thumbnailText"),
        seo_metadata.get("long_video_title"),
        max_words=6,
    )
    if not thumbnail_hook_text:
        fallback_title = (seo_metadata.get("long_video_title") or "").strip()
        thumbnail_hook_text = pick_hindi(fallback_title, max_words=6)
    with open("public/thumbnail_props.json", "w", encoding="utf-8") as f:
        json.dump(
            {
                "backgroundImage": "thumbnail.jpg",
                "hookText": thumbnail_hook_text,
                "textPosition": thumbnail_text_position,
            },
            f, ensure_ascii=False, indent=2,
        )

    # 2c. ONE Shorts-specific 9:16 thumbnail with its own hook and layout.
    shorts_thumb_prompt = shorts_thumbnail_data.get("imagePrompt") or f"{thumbnail_data.get('imagePrompt') or thumb_prompt}, vertical 9:16 composition"
    shorts_thumbnail_text_position = _thumb_layout(shorts_thumb_prompt, seo_metadata.get("shorts_title", ""), True)
    shorts_thumb_prompt = (
        f"{shorts_thumb_prompt}. YouTube Shorts cover art direction: ONE dominant focal subject, "
        f"dramatic emotion/action, strong contrast, cinematic lighting, clean uncluttered composition, "
        f"no text, no watermark, no collage, no split screen. Keep the main subject unobstructed and "
        f"leave intentional clean negative space on the {_opposite_side(shorts_thumbnail_text_position)} "
        f"for a short Hindi hook."
    )
    print(f"🖼️ Generating ONE High-CTR Shorts Thumbnail ({shorts_thumbnail_text_position})...", flush=True)
    shorts_thumb_dest = "public/images/thumbnail_shorts.jpg"
    generate_ai_image(shorts_thumb_prompt, shorts_thumb_dest, aspect_ratio="9:16", pollinations_width=1080, pollinations_height=1920)
    subprocess.run(["cp", shorts_thumb_dest, "out/thumbnail_shorts.jpg"], check=False)

    shorts_thumbnail_hook_text = pick_hindi(
        shorts_thumbnail_data.get("thumbnailText"),
        seo_metadata.get("shorts_title"),
        thumbnail_hook_text,
        max_words=6,
    )
    if not shorts_thumbnail_hook_text:
        fallback_shorts_title = (seo_metadata.get("shorts_title") or "").strip()
        shorts_thumbnail_hook_text = pick_hindi(fallback_shorts_title, max_words=6)
    with open("public/thumbnail_props_shorts.json", "w", encoding="utf-8") as f:
        json.dump(
            {
                "backgroundImage": "thumbnail_shorts.jpg",
                "hookText": shorts_thumbnail_hook_text,
                "textPosition": shorts_thumbnail_text_position,
            },
            f, ensure_ascii=False, indent=2,
        )

    # Exactly one thumbnail per format. No A/B/C variant rendering.
    thumbnail_variants = []
    print("🖼️ Thumbnail output policy: 1 long + 1 Shorts thumbnail only.", flush=True)

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
        long_visuals = [recover_shots(f.result(), i + 1, "16:9") for i, f in enumerate(long_futures)]
        shorts_visuals = [recover_shots(f.result(), i + 1, "9:16") for i, f in enumerate(shorts_futures)]

    # 4. Parallel Audio Generation (Long + Shorts) - each task also returns
    # that scene's word-level caption timing (see generate_clean_audio).
    audio_tasks = []
    for i, scene in enumerate(long_scenes):
        idx = i + 1
        narration = scene.get("text") or scene.get("narration_chunk", "")
        audio_tasks.append(generate_clean_audio(narration, f"public/audio/chunk_{idx}.mp3", scene.get("director", {}).get("audioBeat", scene.get("director", {}).get("entertainmentBeat", ""))))

    for i, scene in enumerate(shorts_scenes):
        idx = i + 1
        narration = scene.get("text") or scene.get("narration_chunk", "")
        audio_tasks.append(generate_clean_audio(narration, f"public/audio/shorts_chunk_{idx}.mp3", scene.get("director", {}).get("audioBeat", scene.get("director", {}).get("entertainmentBeat", ""))))

    audio_word_timings = await asyncio.gather(*audio_tasks)
    long_word_timings = audio_word_timings[:len(long_scenes)]
    shorts_word_timings = audio_word_timings[len(long_scenes):]

    # Keep the long-form narration inside the 150-210s production window.
    # Target 205s here so the per-scene render padding still leaves headroom
    # for the final Remotion composition without weakening media QC.
    long_audio_paths = [f"public/audio/chunk_{i + 1}.mp3" for i in range(len(long_scenes))]
    # 240 s (top of the 2-4 min target): the calm Kokoro pace is kept as-is for a
    # normal-length story; only an unusually long script gets a gentle (<=8%) trim.
    _fit_long_narration_to_target(long_audio_paths, long_word_timings, target_seconds=240.0)

    # 4b. Phase-6 Beat-Level Sound-Effect Layer.
    # Resolve each unique cue once, then Scene.tsx schedules the shared file
    # at the beat's actualStartSeconds. The old scene-start SFX playback is
    # intentionally suppressed by director.py.
    beat_effects = set()
    for scene in list(long_scenes) + list(shorts_scenes):
        for beat in (scene.get("visualBeats") or scene.get("director", {}).get("visualBeats") or []):
            effect_name = str(beat.get("soundEffect") or "none")
            if effect_name != "none":
                beat_effects.add(effect_name)

    for effect_name in sorted(beat_effects):
        resolve_sound_effect_audio(
            effect_name,
            f"public/audio/effects/beat_{effect_name}.mp3",
        )


    # 5. Build Remotion Props for Long Video
    # long_visuals[i] / shorts_visuals[i] are now ordered shot LISTS (see
    # process_long_scene_visual/process_shorts_scene_visual + Scene.tsx's
    # `shots` field) rather than a single filename - this is what actually
    # fixes a scene's video running out before its narration does.
    enriched_long = []
    for i, scene in enumerate(long_scenes):
        idx = i + 1
        audio_path = f"public/audio/chunk_{idx}.mp3"
        duration = get_audio_duration(audio_path)
        shots = long_visuals[i] or []
        director = scene.get("director", {})
        shots = [dict(s, transition=s.get("transition", director.get("transition", "crossfade"))) for s in shots]
        scene_duration = round(duration + 0.3, 2)
        timed_beats, shots = sync_visual_beats_to_narration(
            scene, shots, long_word_timings[i], scene_duration
        )
        enriched_long.append({
            "scene_number": idx,
            "durationInSeconds": scene_duration,
            "narration_chunk": hindi_display_text(scene.get("text", "")),
            "shots": shots,
            "director": scene.get("director", {}),
            "visualBeats": timed_beats,
            "entertainmentBeat": scene.get("director", {}).get("entertainmentBeat", ""),
            "imageFileName": shots[0]["file"] if shots else "",  # legacy/debug only, see Scene.tsx's resolveShots()
            "soundEffect": scene.get("soundEffect", "none"),
            "visualEntities": scene.get("visualEntities", scene.get("visual_entities", [])),
            "visualAttributes": scene.get("visualAttributes", scene.get("visual_attributes", [])),
            "visualStrict": bool(scene.get("visualStrict") or scene.get("visual_strict")),
            "words": long_word_timings[i]
        })

    # 6. Build Remotion Props for Shorts Video
    enriched_shorts = []
    for i, scene in enumerate(shorts_scenes):
        idx = i + 1
        audio_path = f"public/audio/shorts_chunk_{idx}.mp3"
        duration = get_audio_duration(audio_path)
        shots = shorts_visuals[i] or []
        director = scene.get("director", {})
        shots = [dict(s, transition=s.get("transition", director.get("transition", "crossfade"))) for s in shots]
        scene_duration = round(duration + 0.2, 2)
        timed_beats, shots = sync_visual_beats_to_narration(
            scene, shots, shorts_word_timings[i], scene_duration
        )
        enriched_shorts.append({
            "scene_number": idx,
            "durationInSeconds": scene_duration,
            "narration_chunk": hindi_display_text(scene.get("text", "")),
            "shots": shots,
            "director": scene.get("director", {}),
            "visualBeats": timed_beats,
            "imageFileName": shots[0]["file"] if shots else "",  # legacy/debug only, see Scene.tsx's resolveShots()
            "soundEffect": scene.get("soundEffect", "none"),
            "visualEntities": scene.get("visualEntities", scene.get("visual_entities", [])),
            "visualAttributes": scene.get("visualAttributes", scene.get("visual_attributes", [])),
            "visualStrict": bool(scene.get("visualStrict") or scene.get("visual_strict")),
            "words": shorts_word_timings[i]
        })

    # Phase-6 audit: selected asset + rerank score + narration-synchronised
    # shot timing + editorial typography/SFX cues. This lets us compare what
    # the director asked for with exactly what Remotion will render/play.
    visual_search_report = {
        "phase": 7,
        "reranker": {
            "candidateTarget": _candidate_target_count(),
            "maxQueriesPerBeat": _rerank_query_limit(),
            "minimumScore": _candidate_min_score(),
            "clipEnabled": bool(clip_rerank is not None and clip_rerank.enabled()),
            "weights": _VISUAL_SCORE_WEIGHTS,
        },
        "timing": {
            "mode": "tts_word_boundary_sync",
            "fallback": "proportional_scene_timing",
        },
        "imageMotion": {
            "profile": "cinematic_depth",
            "scope": "ai_image_shots_only",
            "layers": ["soft_depth_background", "foreground_camera_move", "subtle_light_pass", "vignette"],
        },
        "editorialCues": {
            "typography": "reveal_climax_action_only",
            "soundEffects": "beat_timed",
            "calmCrossfadeWhoosh": false,
        },
        "continuity": {
            "styleProfile": ["realism", "period", "lighting", "palette"],
            "adjacentPreviewSimilarity": bool(clip_rerank is not None and clip_rerank.enabled()),
            "nearDuplicateThreshold": _continuity_duplicate_threshold(),
            "hardRejects": ["realism_conflict", "entity_conflict", "period_conflict", "near_duplicate_composition"],
        },
        "long": [
            {
                "scene_number": scene.get("scene_number"),
                "shots": scene.get("shots", []),
                "visualBeats": scene.get("visualBeats", []),
            }
            for scene in enriched_long
        ],
        "shorts": [
            {
                "scene_number": scene.get("scene_number"),
                "shots": scene.get("shots", []),
                "visualBeats": scene.get("visualBeats", []),
            }
            for scene in enriched_shorts
        ],
    }
    with open("out/visual_search_report.json", "w", encoding="utf-8") as f:
        json.dump(visual_search_report, f, ensure_ascii=False, indent=2)

    # 6b. Climax scene(s) for the bgm-swell in DevotionalComposition.tsx.
    # Prefer whatever the Make.com prompt supplied (_meta.climax_scene_number
    # - a 1-based position in long_video.scenes); fall back to a simple
    # heuristic (roughly 70% through the story, where the revelation/turning
    # point usually lands per the story-structure instructions in module 1's
    # prompt) so every render gets a swell even before that prompt is updated.
    if isinstance(climax_scene_number, int) and 1 <= climax_scene_number <= len(enriched_long):
        bgm_swell_scene_numbers = [climax_scene_number]
    elif enriched_long:
        bgm_swell_scene_numbers = [max(1, round(len(enriched_long) * 0.7))]
    else:
        bgm_swell_scene_numbers = []

    # Phase-1 visual director report. This is planning metadata only; asset
    # retrieval still uses the existing scene-level search path until the
    # next phase explicitly consumes visualBeats.
    visual_plan = {
        "directorVersion": 4,
        "long": [
            {
                "scene_number": s.get("scene_number", i + 1),
                "visualBeatCount": len(s.get("visualBeats", [])),
                "visualBeats": s.get("visualBeats", []),
            }
            for i, s in enumerate(long_scenes)
        ],
        "shorts": [
            {
                "scene_number": s.get("scene_number", i + 1),
                "visualBeatCount": len(s.get("visualBeats", [])),
                "visualBeats": s.get("visualBeats", []),
            }
            for i, s in enumerate(shorts_scenes)
        ],
    }
    with open("out/visual_director_plan.json", "w", encoding="utf-8") as f:
        json.dump(visual_plan, f, ensure_ascii=False, indent=2)

    print(
        "🎬 Visual Director v4 plan: "
        f"{sum(x['visualBeatCount'] for x in visual_plan['long'])} long-form beats + "
        f"{sum(x['visualBeatCount'] for x in visual_plan['shorts'])} Shorts beats. "
        "Beat planning + media selection + narration timing metadata are ready.",
        flush=True,
    )

    # Save props and metadata
    # On-screen Hindi hook for the first ~1.8 s (HookOverlay.tsx): the
    # thumbnail promise repeated on screen so viewers who clicked see it
    # confirmed instantly - the biggest early-drop fix for Shorts and long.
    hook_enabled = os.getenv("HOOK_OVERLAY_ENABLED", "true").strip().lower() != "false"
    long_hook = pick_hindi(thumbnail_hook_text, seo_metadata.get("thumbnailText"), max_words=6) if hook_enabled else ""
    shorts_hook = pick_hindi(shorts_thumbnail_hook_text, thumbnail_hook_text, max_words=6) if hook_enabled else ""

    long_props = {
        "title": seo_metadata.get("long_video_title", "Devotional Long Video"),
        "hookText": long_hook,
        "fps": 30,
        "scenes": enriched_long,
        "seo_metadata": seo_metadata,
        "bgmSwellSceneNumbers": bgm_swell_scene_numbers
    }
    shorts_props = {
        "title": seo_metadata.get("shorts_title", "Devotional Shorts"),
        "hookText": shorts_hook,
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

    # Extra context for the YouTube copy-paste pack (scripts/youtube_pack.py).
    metadata_for_upload["thumbnailVariants"] = [
        {"id": "a", "file": "thumbnail.jpg", "hookText": thumbnail_hook_text}
    ]
    metadata_for_upload["meta"] = {
        k: meta_data.get(k) for k in (
            "category", "track", "content_role", "festival_angle", "experiment_id",
            "experiment_hypothesis", "agent_critique", "qc_verdict", "next_episode_angle",
        ) if meta_data.get(k)
    }
    metadata_for_upload["factCheck"] = fact_check_items(payload)
    metadata_for_upload["aiDisclosureRecommended"] = True

    with open("out/metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata_for_upload, f, ensure_ascii=False, indent=2)

    # Persist which stock clips this run actually used, so a LATER run's
    # _load_recent_clip_history() call (top of this file) can deprioritize
    # them - see the clip-usage-history section near the top of this file.
    # The CI workflow commits used_clips_history.json back to the repo right
    # after this script finishes (see render.yml).
    save_clip_history()

    print("🎉 All Multi-Source Assets (Pexels + Pixabay + Coverr + Wikimedia + Local Library + FLUX), Thumbnail, Sound Effects, and Metadata ready!", flush=True)

if __name__ == "__main__":
    asyncio.run(process())