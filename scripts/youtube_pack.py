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
    long_desc = _append_missing_hashtags(long_desc, hashtags)
    shorts_desc = (
        meta.get("shorts_description") or meta.get("long_video_description")
        or meta.get("description") or shorts_title or long_title
    )
    shorts_desc = _append_missing_hashtags(shorts_desc, hashtags)
    thumbs = meta.get("thumbnailVariants") or [{"id": "a", "file": "thumbnail.jpg"}]
    facts = meta.get("factCheck") or []
    m = meta.get("meta") or {}
    cta = (meta.get("cta") or "").strip()
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
              "- Language: Hindi · Caption language: Hindi · Category: Education (or Entertainment)",
              "- *Altered or synthetic content*: **Yes** (AI voice / AI images) — protects monetization",
              "- Audience: Not made for kids · Add to the matching series playlist",
              "- End screen: *Best for viewer* video + Subscribe; add a card at the climax to a related video"]
    if cta:
        lines += ["", "**Pinned comment**", _block(cta)]

    lines += ["", "## 2. Short — `final_video_shorts.mp4`", "", "**Title**", _block(shorts_title),
              "", "**Description**", _block(shorts_desc),
              "", "**Thumbnail/cover:** `thumbnail_shorts_final.jpg` (pick it as the cover frame in the app)",
              "- *Related video*: link the long video above (this is what turns Shorts views into watch hours)",
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
        lines += ["- **Story strategy:** NOT PROVIDED — check metadata and choose playlist manually."]
    lines += ["", "**Creator checklist**",
              "- Confirm the suggested playlist exists in YouTube Studio.",
              "- Add each video to a relevant topical playlist; link the Short to the Long.",
              "- Verify event dates and regional variations before publishing.",
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
