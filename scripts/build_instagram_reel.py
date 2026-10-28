#!/usr/bin/env python3
"""Zero-API Instagram Reel packaging. Fail closed on unsuitable stories/covers.

Uses the QC-approved vertical Shorts storyboard, not a horizontal YouTube
video or a separately generated thumbnail. No AI/Canva/image credits.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess

from scripts.youtube_pack import instagram_caption_english


ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_CTA = re.compile(r"सब्सक्राइब|subscribe|चैनल को सब्सक्राइब", re.I)
GENERIC_WELLNESS = re.compile(r"क्या (खाएं|न खाएं)|डाइट|तनाव (कम|दूर)|कमजोरी|थकान|एनर्जी|सरगी में (क्या|ये)", re.I)
STORY_SIGNAL = re.compile(r"कथा|कहानी|पौराणिक|पुराण|रामायण|महाभारत|गाथा|किसने|क्यों|देवी|देवता|कृष्ण|राम|शिव|दुर्गा|वृंदावन", re.I)
OFF_NICHE = re.compile(r"auto expo|car expo|utensil|politic|concert|bunny is live", re.I)
FALLBACK_SOURCES = {"local_atmosphere_fallback", "local_continuity_fallback"}


def compact_hook(raw, max_words=4, max_line_chars=18):
    """Keep whole Devanagari words/matras intact; never slice Unicode glyphs."""
    words = str(raw or "").replace("\n", " ").strip().split()
    words = words[:max_words]
    if len(words) < 2 or any(len(w) > max_line_chars for w in words):
        raise ValueError("Instagram cover needs 2-4 complete short Hindi words")
    lines, current = [], ""
    for word in words:
        candidate = (current + " " + word).strip()
        if len(candidate) <= max_line_chars:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    if len(lines) > 2:
        raise ValueError("Instagram hook cannot safely fit in two lines")
    text = "\n".join(lines)
    if not re.search(r"[\u0900-\u097f]", text):
        raise ValueError("Instagram cover needs readable Hindi hook")
    return text


def rejection_reasons(props, metadata):
    title = str(metadata.get("shorts_title") or props.get("title") or "")
    scenes = props.get("scenes") or []
    text = " ".join(str(x.get("narration_chunk") or "") for x in scenes)
    full = title + " " + text
    reasons = []
    if not scenes:
        reasons.append("missing_shorts_scenes")
    if OFF_NICHE.search(title):
        reasons.append("off_niche_title")
    if GENERIC_WELLNESS.search(title) and not STORY_SIGNAL.search(title):
        reasons.append("generic_festival_wellness_not_mythology_story")
    if FORBIDDEN_CTA.search(full):
        reasons.append("youtube_subscribe_spoken_in_instagram_audio")
    seconds = sum(float(s.get("durationInSeconds") or 0) for s in scenes)
    if not 20 <= seconds <= 40:
        reasons.append("outside_preferred_20_to_40_second_window")
    if not STORY_SIGNAL.search(full):
        reasons.append("missing_mythology_or_devotional_story_signal")
    if not str(props.get("hookText") or "").strip():
        reasons.append("missing_first_second_hook")
    if len(scenes) < 2:
        reasons.append("insufficient_visual_changes")
    return reasons, round(seconds, 2)


def first_relevant_shot(props, images_dir):
    scenes = props.get("scenes") or []
    for scene in scenes[:1]:
        for shot in scene.get("shots") or []:
            filename = str(shot.get("file") or "")
            path = (images_dir / filename).resolve()
            if (shot.get("source") in FALLBACK_SOURCES
                or shot.get("qcReason") == "network_visuals_unavailable"
                or shot.get("type") not in ("video", "image")
                or not filename or Path(filename).name != filename
                or not path.is_relative_to(images_dir.resolve())
                or not path.is_file()):
                continue
            return path
    raise ValueError("No QC-approved opening shot for a truthful Instagram cover")


def cover_from_shot(source, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    args = ["ffmpeg", "-hide_banner", "-nostdin", "-y", "-loglevel", "error"]
    if source.suffix.lower() in (".mp4", ".mov", ".mkv"):
        args += ["-ss", "0.2"]
    args += ["-i", str(source), "-frames:v", "1", "-vf",
             "scale=1080:1920:force_original_aspect_ratio=increase,"
             "crop=1080:1920,setsar=1", "-q:v", "2", str(destination)]
    subprocess.run(args, check=True, timeout=45)
    if destination.stat().st_size < 12000:
        raise ValueError("Instagram cover too small or invalid")
    return destination


def build(root=ROOT):
    root = Path(root)
    out = root / "out"
    out.mkdir(parents=True, exist_ok=True)
    with (root / "public/props_shorts.json").open(encoding="utf-8") as f:
        props = json.load(f)
    with (out / "metadata.json").open(encoding="utf-8") as f:
        meta = json.load(f)
    status = {"status": "review_required", "format": "9:16", "width": 1080,
              "height": 1920, "automatic_publish": False}
    reasons, duration = rejection_reasons(props, meta)
    status["duration_seconds"] = duration
    try:
        hook = compact_hook(props.get("hookText") or meta.get("shorts_title"))
        status["hook"] = hook
    except ValueError as exc:
        reasons.append("hook_not_readable_at_phone_size")
        status["hook_error"] = str(exc)
        hook = ""
    try:
        cover = first_relevant_shot(props, root / "public/images")
        cover_from_shot(cover, root / "public/images/instagram_cover_base.jpg")
        status["cover_source"] = cover.name
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        reasons.append("cover_requires_verified_replacement")
        status["cover_error"] = type(exc).__name__
    status["reasons"] = sorted(set(reasons))
    if not reasons:
        vertical = {**props, "platform": "instagram", "hookText": hook.replace("\n", " "),
                    "instagram": {"safeTopPx": 250, "safeBottomPx": 330}}
        (root / "public/props_instagram.json").write_text(
            json.dumps(vertical, ensure_ascii=False, indent=2), encoding="utf-8")
        (root / "public/thumbnail_props_instagram.json").write_text(
            json.dumps({"backgroundImage": "instagram_cover_base.jpg",
                        "hookText": hook, "textPosition": "center"},
                       ensure_ascii=False, indent=2), encoding="utf-8")
        status["status"] = "ready_for_manual_review"

    # Reuse the same story-specific, English SEO caption builder as the
    # YouTube upload pack. No hard-coded per-deity caption/hashtag lookup.
    description = instagram_caption_english(meta)
    (out / "instagram_post.txt").write_text(description + "\n", encoding="utf-8")
    (out / "instagram_status.json").write_text(
        json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    return status


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(ROOT))
    args = parser.parse_args()
    status = build(Path(args.root))
    print(json.dumps(status, ensure_ascii=False))
    # Review-required affects Instagram only; YouTube long/shorts remain viable.


if __name__ == "__main__":
    main()
