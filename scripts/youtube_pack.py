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


def build(meta: dict) -> str:
    long_title = (meta.get("long_video_title") or "").strip()
    shorts_title = (meta.get("shorts_title") or "").strip()
    variants = [t for t in (_title_text(v) for v in _list(meta.get("titleVariants"))) if t and t != long_title]
    tags = _tags_within_limit(_list(meta.get("tags")))
    hashtags = _hashtags(_list(meta.get("hashtags")))
    long_desc = (meta.get("long_video_description") or meta.get("description") or "").strip()
    if hashtags and not any(h in long_desc for h in hashtags):
        long_desc = f"{long_desc}\n\n{' '.join(hashtags[:3])}".strip()
    shorts_desc = (meta.get("shorts_description") or "").strip()
    shorts_desc = f"{shorts_desc}\n\n{' '.join(hashtags)}".strip()
    thumbs = meta.get("thumbnailVariants") or [{"id": "a", "file": "thumbnail.jpg"}]
    facts = meta.get("factCheck") or []
    m = meta.get("meta") or {}
    cta = (meta.get("cta") or "").strip()

    lines = ["# 📋 YouTube upload pack (copy-paste)", ""]
    lines += ["## 1. Long video — `final_video.mp4`", "", "**Title**", _block(long_title)]
    if variants:
        lines += ["", "**Alternative titles** (use one in *Test & Compare* or swap after 48 h if CTR < 4%)"]
        lines += [f"- {v}" for v in variants[:2]]
    lines += ["", "**Description** (chapters included)", _block(long_desc)]
    lines += ["", "**Tags** (paste into *Tags*, under the 500-character limit)", _block(", ".join(tags))]
    lines += ["", "**Thumbnail** — *Test & Compare*: upload all of these, YouTube picks the winner by watch time:"]
    lines += [f"- `{t.get('file')}` — {t.get('hookText', '')}" for t in thumbs]
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
              "", "## 3. Instagram Reel (same Short file)", _block(f"{shorts_title}\n\n{shorts_desc}")]

    lines += ["", "## 4. Fact check before uploading (1 minute)"]
    if facts:
        lines += ["Verify or soften these lines. **HIGH** = fix before publishing.", ""]
        lines += [f"- Scene {f.get('scene')}: {f.get('claim')} — **{f.get('risk')}**" for f in facts]
    else:
        lines += ["- No specific dates/verses/overclaims detected. Still skim the script once."]

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
