#!/usr/bin/env python3
"""Build the copy-paste YouTube/Instagram upload pack for MANUAL uploads.

Reads out/metadata.json (written by generate_assets.py) and writes
out/youtube_pack.md, which the workflow puts at the top of the GitHub Release
notes. Everything the creator needs in YouTube Studio is in one place:
titles (+2 alternatives), description with chapters, tags within YouTube's
500-character limit, hashtags, the Shorts text, thumbnail A/B/C files for
"Test & Compare", the AI-disclosure reminder and a fact-check list.

Never fails the workflow (exit 0 on any problem).
"""
import json
import os
import re
import sys
from pathlib import Path

META = os.getenv("PACK_METADATA_JSON", "out/metadata.json")
OUT = os.getenv("PACK_OUTPUT", "out/youtube_pack.md")
INSTAGRAM_URL = "https://www.instagram.com/velvet_bunny.vb/"
SHORTS_PLAYLIST = "पौराणिक Shorts: छोटी कथा, बड़ा अर्थ | Mythology Shorts Hindi"
EXISTING_PLAYLISTS = {
    "temple": "मंदिरों के रहस्य और पौराणिक कथाएँ | Temple Mysteries Hindi",
    "garud": "गरुड़ पुराण और पितृ पक्ष | Garud Puran, Pitru Paksha",
    "krishna": "श्रीकृष्ण लीला और वृंदावन | Krishna Leela, Vrindavan",
    "mahabharat": "महाभारत: धर्म, कर्म और कथाएँ | Mahabharat Stories Hindi",
    "ramayan": "रामायण की कथाएँ और रहस्य | Ramayan Katha in Hindi",
    "navratri": "नवरात्रि कथा और माँ दुर्गा | Navratri Katha",
    "vrat": "व्रत-त्योहार कथा और नियम | Vrat Katha & Festival Guide",
    "karwa": "करवा चौथ 2026: कथा, सरगी और व्रत नियम | Karwa Chauth 2026",
}
NEW_PLAYLISTS = {
    "diwali": "दीपावली और लक्ष्मी पूजा | Diwali, Dhanteras Hindi",
    "chhath": "छठ पूजा: कथा, अर्घ्य और परंपरा | Chhath Puja Hindi",
    "tulsi": "तुलसी विवाह और देवउठनी एकादशी | Tulsi Vivah Katha",
    "dev_deepawali": "देव दीपावली और कार्तिक पूर्णिमा | Dev Deepawali Hindi",
    "shiv": "शिव और महादेव की कथाएँ | Shiv Mahadev Katha",
    "hanuman": "हनुमान जी की कथाएँ और रहस्य | Hanuman Katha Hindi",
    "ganesh": "श्री गणेश कथा और रहस्य | Ganesh Katha Hindi",
    "devi": "देवी और शक्ति की कथाएँ | Devi Shakti Katha",
    "mythology": "पौराणिक कथाएँ और अनसुने प्रसंग | Hindi Mythology Stories",
}


def recommend_playlist(meta: dict, *, is_short: bool = False) -> dict:
    """Return an exact channel playlist name from story evidence, not model free-text."""
    info = meta.get("meta") or meta.get("_meta") or {}
    title = str(meta.get("long_video_title") or meta.get("shorts_title") or "")
    decision = str(info.get("decisionBasis") or info.get("decision_basis") or "")
    category = str(info.get("category") or "")
    keywords = " ".join(str(x) for x in _list(meta.get("secondaryKeywords")))
    topic = " ".join((title, decision, category, keywords)).casefold()

    def has(*terms):
        return any(term.casefold() in topic for term in terms)

    # Narrow festival playlists take precedence over broad deity/genre lists.
    if has("करवा चौथ", "karwa chauth", "karva chauth"):
        key, exists = "karwa", True
    elif has("छठ पूजा", "छठ महापर्व", "chhath puja", "chhath"):
        key, exists = "chhath", False
    elif has("तुलसी विवाह", "tulsi vivah", "देवउठनी", "देव उठनी", "प्रबोधिनी एकादशी", "dev uthani"):
        key, exists = "tulsi", False
    elif has("देव दीपावली", "देवदीपावली", "dev deepawali", "dev diwali", "कार्तिक पूर्णिमा", "kartik purnima"):
        key, exists = "dev_deepawali", False
    elif has("धनतेरस", "dhanteras", "दीपावली", "दिवाली", "deepawali", "diwali", "लक्ष्मी पूजा", "lakshmi puja"):
        key, exists = "diwali", False
    elif has("गोवर्धन पूजा", "भाई दूज", "भाईदूज", "govardhan puja", "bhai dooj"):
        key, exists = "vrat", True
    elif has("पितृ पक्ष", "पितृपक्ष", "गरुड़ पुराण", "गरुड पुराण", "garud puran", "pitru paksha"):
        key, exists = "garud", True
    elif has("नवरात्रि", "navratri", "दुर्गा", "durga"):
        key, exists = "navratri", True
    elif has("हनुमान", "hanuman", "बजरंगबली", "bajrangbali"):
        key, exists = "hanuman", False
    elif has("महादेव", "शिव", "शिव पुराण", "mahadev", "shiv", "shiva"):
        key, exists = "shiv", False
    elif has("गणेश", "गणपति", "ganesh", "ganapati"):
        key, exists = "ganesh", False
    elif has("देवी", "शक्ति", "काली", "पार्वती", "देवी भागवत", "shakti", "devi"):
        key, exists = "devi", False
    elif has("श्रीकृष्ण", "कृष्ण", "वृंदावन", "राधा", "krishna", "vrindavan", "radha"):
        key, exists = "krishna", True
    elif has("महाभारत", "mahabharat", "कर्ण", "अर्जुन", "द्रौपदी", "भीष्म", "कुरुक्षेत्र"):
        key, exists = "mahabharat", True
    elif has("रामायण", "ramayan", "ramayana", "श्रीराम", "सीता", "रामचरितमानस"):
        key, exists = "ramayan", True
    elif has("मंदिर", "temple", "लेपाक्षी", "स्थापत्य", "मंदिरों"):
        key, exists = "temple", True
    elif has("व्रत", "एकादशी", "पूजा", "त्योहार", "व्रत कथा", "festival", "vrat"):
        key, exists = "vrat", True
    else:
        key, exists = "mythology", False

    name = (EXISTING_PLAYLISTS if exists else NEW_PLAYLISTS)[key]
    result = {"name": name, "status": "EXISTS — select this playlist" if exists else "CREATE BEFORE UPLOAD — exact name below"}
    if is_short:
        result["also_add_to"] = SHORTS_PLAYLIST
    return result


def _add_instagram_link(description: str) -> str:
    text = str(description or "").strip()
    if INSTAGRAM_URL not in text:
        text = f"{text}\n\nInstagram: {INSTAGRAM_URL}".strip()
    return text


def _list(value):
    if isinstance(value, list):
        return [v for v in value if v not in (None, "")]
    if isinstance(value, str) and value.strip():
        text = value.strip()
        if text.startswith("["):
            try:
                parsed = json.loads(text)
                if isinstance(parsed, list):
                    return [v for v in parsed if v not in (None, "")]
            except Exception:
                pass
        return [p.strip() for p in text.replace("\n", ",").split(",") if p.strip()]
    return []


def _title_text(v):
    if isinstance(v, dict):
        return str(v.get("title") or v.get("text") or "").strip()
    return str(v or "").strip()


def _tags_within_limit(tags, limit=480):
    out, used = [], 0
    for t in tags:
        t = str(t).strip().lstrip("#")
        if not t or t in out:
            continue
        cost = len(t) + (2 if out else 0) + (2 if " " in t else 0)
        if used + cost > limit:
            break
        out.append(t)
        used += cost
    return out


def _hashtags(tags):
    out = []
    for h in tags:
        h = "#" + str(h).strip().lstrip("#").replace(" ", "")
        if len(h) > 1 and h not in out:
            out.append(h)
    return out[:5]


def _block(text):
    return "```\n" + (text or "").strip() + "\n```"

def _append_missing_hashtags(description, tags):
    """Append hashtags missing from a description, deduplicating case-insensitively."""
    text = str(description or "").strip()
    normalized = _hashtags(tags)
    existing = {
        tag.lower()
        for tag in re.findall(r"(?<!\w)#[\w]+", text, flags=re.UNICODE)
    }
    missing = [tag for tag in normalized if tag.lower() not in existing]
    if not missing:
        return text
    return f"{text}\n\n{' '.join(missing)}".strip()


def _is_generic_instagram_caption(value):
    """Reject old boilerplate rather than presenting it as story-specific copy."""
    normalized = re.sub(r"\s+", " ", str(value or "")).strip().casefold()
    generic_openings = (
        "a short devotional story about",
        "discover this devotional story",
        "step into a devotional story",
        "explore this devotional story",
        "enter a devotional story",
        "a devotional tale of",
        "this devotional tale of",
        "this devotional story of",
        "follow this devotional tale of",
        "this story from lord rama's tradition",
        "this moment from the mahabharata",
        "behind the karva chauth tradition is a katha remembered",
    )
    generic_ctas = (
        "watch till the end for the complete moment",
        "what part of this story stayed with you? tell us in the comments",
    )
    return normalized.startswith(generic_openings) or any(phrase in normalized for phrase in generic_ctas)


def instagram_caption_english(meta: dict, *, long_video: bool = False) -> str:
    """Package story-specific Instagram copy generated with the episode SEO metadata."""
    caption_key = "instagram_long_caption" if long_video else "instagram_caption"
    caption = str(meta.get(caption_key) or "").strip()

    # Refuse non-English generated captions; Instagram copies are deliberately
    # English while the actual video can remain in Hindi.
    if re.search(r"[\u0900-\u097F]", caption) or _is_generic_instagram_caption(caption):
        caption = ""

    # Older cached episodes may not have Instagram captions. Reuse an
    # episode-specific English description when possible.
    if not caption:
        source_keys = (
            ("long_video_description", "description")
            if long_video else
            ("shorts_description", "long_video_description", "description")
        )
        for key in source_keys:
            value = str(meta.get(key) or "").strip()
            if (not value or re.search(r"[\u0900-\u097F]", value)
                    or _is_generic_instagram_caption(value)):
                continue
            lines = []
            for line in value.splitlines():
                line = line.strip()
                if not line or re.match(r"^\d{1,2}:\d{2}(?::\d{2})?\b", line):
                    continue
                if line.lower().startswith(("chapters:", "timestamps:")):
                    break
                lines.append(line)
            candidate = "\n".join(lines).strip()
            if candidate and re.search(r"[A-Za-z]", candidate):
                caption = candidate
                break

    # No template fallback: if neither generated Instagram copy nor a genuine
    # English episode description exists, leave the caption unavailable.
    if not caption.strip():
        return ""

    # Keep hashtags supplied by the story-writing model first, followed by
    # approved episode hashtags. Do not convert raw multiword SEO keywords
    # into awkward hashtags; keywords belong naturally in the caption itself.
    caption_tags = re.findall(r"(?<!\w)#[\w]+", caption, flags=re.UNICODE)
    body = re.sub(r"(?<!\w)#[\w]+", "", caption, flags=re.UNICODE)
    body = re.sub(r"[ \t]{2,}", " ", body)
    body = re.sub(r"\n[ \t]*\n(?:[ \t]*\n)+", "\n\n", body).strip()
    if not body:
        return ""

    candidate_tags = list(caption_tags)
    candidate_tags.extend(_hashtags(_list(meta.get("hashtags"))))
    hashtags = []
    for tag in candidate_tags:
        normalized = "#" + str(tag).strip().lstrip("#").replace(" ", "")
        if len(normalized) > 1 and normalized.lower() not in {x.lower() for x in hashtags}:
            hashtags.append(normalized)
        if len(hashtags) >= 8:
            break

    if body and hashtags:
        return f"{body}\n\n{' '.join(hashtags)}"
    return body or " ".join(hashtags)


def build(meta: dict) -> str:
    long_title = (meta.get("long_video_title") or "").strip()
    shorts_title = (meta.get("shorts_title") or "").strip()
    variants = [t for t in (_title_text(v) for v in _list(meta.get("titleVariants"))) if t and t != long_title]
    tags = _tags_within_limit(_list(meta.get("tags")))
    hashtags = _hashtags(_list(meta.get("hashtags")))
    long_desc = (meta.get("long_video_description") or meta.get("description") or long_title).strip()
    long_desc = _append_missing_hashtags(_add_instagram_link(long_desc), hashtags)
    shorts_desc = (
        meta.get("shorts_description") or meta.get("long_video_description")
        or meta.get("description") or shorts_title or long_title
    )
    shorts_desc = _append_missing_hashtags(_add_instagram_link(shorts_desc), hashtags)
    thumbs = meta.get("thumbnailVariants") or [{"id": "a", "file": "thumbnail.jpg"}]
    facts = meta.get("factCheck") or []
    m = meta.get("meta") or {}
    cta = (meta.get("cta") or "").strip()
    long_playlist = recommend_playlist(meta, is_short=False)
    short_playlist = recommend_playlist(meta, is_short=True)
    instagram_short_caption = instagram_caption_english(meta)
    instagram_long_caption = instagram_caption_english(meta, long_video=True)
    missing_caption_note = "_CAPTION NOT GENERATED — do not post to Instagram until story-specific English copy is added._"

    lines = ["# 📋 YouTube upload pack (copy-paste)", ""]
    lines += ["## 1. Long video — `final_video.mp4`", "", "**Title**", _block(long_title)]
    if variants:
        lines += ["", "**Alternative titles** (use one in *Test & Compare* or swap after 48 h if CTR < 4%)"]
        lines += [f"- {v}" for v in variants[:2]]
    lines += ["", "**Description** (chapters included)", _block(long_desc)]
    lines += ["", "**Tags** (paste into *Tags*, under the 500-character limit)", _block(", ".join(tags))]
    lines += ["", "**Thumbnail** — one final creator-style thumbnail:"]
    lines += [f"- `{t.get('file')}` — {t.get('hookText', '')}" for t in thumbs[:1]]
    lines += ["", "**Settings checklist**",
              "- Video language: Hindi. Choose the category that accurately describes this episode.",
              "- Audience: choose Made for kids only when the video is actually directed to children; family-friendly alone does not decide this.",
              "- Altered/synthetic disclosure: answer from the actual visuals/audio. AI assistance alone does not automatically mean Yes; disclose realistic synthetic or materially altered scenes/people/events where YouTube requires it.",
              "- Add to the exact playlist shown below. Add an end screen to a relevant next video/playlist plus Subscribe when available."]
    if cta:
        lines += ["", "**Pinned comment**", _block(cta)]

    lines += ["", "**Long video playlist**",
              f"- {long_playlist['name']}",
              f"- Status: {long_playlist['status']}",
              "", "## 2. Short — `final_video_shorts.mp4`", "", "**Title**", _block(shorts_title),
              "", "**Description**", _block(shorts_desc),
              "", "**Short playlist placement**",
              f"- Primary topic playlist: {short_playlist['name']}",
              f"- Status: {short_playlist['status']}",
              f"- Also add to: {short_playlist['also_add_to']}",
              "- Keep the Short in the topic playlist as well as the Shorts collection.",
              "", "**Thumbnail/cover:** `thumbnail_shorts_final.jpg` (select the cover frame in YouTube's Shorts upload flow where available)",
              "", "## 3. Instagram — reuse both original YouTube videos",
              "### Short / Reel — same original 9:16 YouTube Short",
              "- Upload `final_video_shorts.mp4` directly to Instagram (do not generate another Reel).",
              "- Cover: `thumbnail_shorts_final.jpg` (check Instagram profile crop).",
              "- Video narration can remain in natural everyday Hindi; Instagram captions are English.",
              "", "**English Instagram Short caption (copy and paste)**",
              _block(instagram_short_caption) if instagram_short_caption else missing_caption_note,
              "", "### Long video — same original 16:9 YouTube Long",
              "- Upload `final_video.mp4` without creating a second video or audio track.",
              "- Cover: `thumbnail.jpg` (check Instagram's cover/crop preview).",
              "- 16:9 is horizontal, not native 9:16: expect empty space or cropping in Instagram Reels. Review in-app before posting.",
              "", "**English Instagram Long caption (copy and paste)**",
              _block(instagram_long_caption) if instagram_long_caption else missing_caption_note,
              "- Review deity identity, festival/date references, video length and rights before either post."]

    # Audit trail: source/creator/rights for all selected music is stored in
    # music_license_report.json on the GitHub draft release.
    music = meta.get("music") or {}
    tracks = music.get("tracks") or []
    lines += ["", "## 4. Background music and rights review", ""]
    if tracks:
        for track in tracks:
            title = str(track.get("title") or "Unnamed track")
            source = str(track.get("source") or "")
            license_name = str(track.get("license") or "UNVERIFIED")
            source_url = str(track.get("source_url") or "")
            lines.append(f"- **{track.get('mood', 'scene')}**: {title} — {source}; rights: {license_name}")
            if source_url:
                lines.append(f"  - Recording/source: {source_url}")
        if music.get("status") == "review_required":
            lines += ["", "**Manual review required before publishing**: source-reported CC0 status is not proof of ownership or a guarantee against Content ID claims. Verify rights and listen to the audio."]
        else:
            lines += ["", "All selected tracks have local verified approval or original synthesized provenance; still listen before posting."]
    else:
        lines.append("- Legacy video: no mood-music manifest present.")
    lines += ["", "Detailed SHA256, source URLs, and file-level license evidence: `music_license_report.json` in GitHub release assets."]

    lines += ["", "## 5. Fact check before uploading (1 minute)"]
    if facts:
        lines += ["Verify or soften these lines. **HIGH** = fix before publishing.", ""]
        lines += [f"- Scene {f.get('scene')}: {f.get('claim')} — **{f.get('risk')}**" for f in facts]
    else:
        lines += ["- No specific dates/verses/overclaims detected. Still skim the script once."]

    # Story strategy is embedded in the existing _meta.decisionBasis text.
    strategy_keys = ("CONTENT_BUCKET", "PLAYLIST_NAME", "SERIES_NAME", "TARGET_AUDIENCE",
                     "TOPIC_LONGEVITY", "VIEWER_QUESTION", "VIEWER_MOTIVATION",
                     "EVENT_DATE", "PUBLISH_BEFORE", "DATE_SOURCE", "HOOK_0_5S",
                     "RETENTION_BEATS", "EMOTIONAL_PAYOFF", "SUBSCRIBER_REASON",
                     "RELATED_NEXT_EPISODE", "ANALYTICS_HYPOTHESIS", "SOURCE_REFERENCES")
    strategy = {}
    for line in str(m.get("decisionBasis") or "").splitlines():
        line = line.strip().lstrip("- ").strip()
        for key in strategy_keys:
            if line.startswith(key + "=") or line.startswith(key + ":"):
                strategy[key] = line[len(key) + 1:].strip()
                break
    lines += ["", "## 6. Story strategy and playlist placement", ""]
    if strategy:
        for key in strategy_keys:
            lines.append(f"- **{key}**: {strategy.get(key) or 'NOT PROVIDED — review before upload'}")
    else:
        lines += ["- **Story strategy:** NOT PROVIDED — review topic and sources before upload."]
    lines += ["", "**Exact playlist to select for the Long**",
              f"- {long_playlist['name']}",
              f"- {long_playlist['status']}",
              "", "**Exact playlist to select for the Short**",
              f"- {short_playlist['name']}",
              f"- {short_playlist['status']}",
              f"- Additional Shorts collection: {short_playlist['also_add_to']}",
              "", "**No video ID or URL input is needed.** These playlist names are chosen from the story topic. Create any playlist marked CREATE BEFORE UPLOAD in YouTube Studio, then select it during manual upload."]
    lines += ["", "**Creator checklist**",
              "- Select the exact Long and Short playlists printed above; create any missing playlist with the exact supplied name first.",
              "- Check auto-generated chapters against the narration and remove any inaccurate chapter.",
              "- Paste the pinned comment after publication; no YouTube URL or video ID is required by this workflow.",
              "- Verify event dates, scripture/story attribution, regional variations, visual identity and music rights before publishing.",
              "- Keep the upload manual. Do not treat a completed GitHub Release as a published YouTube video.",
              "- Track 7/30/90-day performance by content bucket, excluding one-off outliers."]

    if m:
        lines += ["", "<details><summary>Agent notes (experiment / critique)</summary>", ""]
        lines += [f"- **{k}**: {v}" for k, v in m.items()]
        lines += ["", "</details>"]
    return "\n".join(lines) + "\n"


def main():
    path = Path(META)
    if not path.exists():
        print(f"::warning::YouTube pack skipped - {META} not found")
        return
    meta = json.loads(path.read_text(encoding="utf-8"))
    Path(OUT).parent.mkdir(parents=True, exist_ok=True)
    Path(OUT).write_text(build(meta), encoding="utf-8")
    print(f"YouTube pack written to {OUT}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"::warning::YouTube pack skipped: {exc}")
    sys.exit(0)
