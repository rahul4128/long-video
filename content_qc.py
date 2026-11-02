"""Pre-render content quality gate for approximately 3-minute Long + standalone Short devotional episodes.

This is intentionally heuristic: it catches structural problems before spending
GitHub Actions time on media generation, but it does not claim to predict views.
"""
import json, os, re, sys

DEVANAGARI = re.compile(r"[\u0900-\u097F]")
def _norm(s):
    return re.sub(r"\s+", " ", str(s or "").strip()).lower()

def _as_dict(value):
    """Accept native objects and JSON-encoded object strings from Make."""
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except (TypeError, ValueError):
            return {}
    return {}

_SENT_SPLIT = re.compile(r"(?<=[।!?])\s+|\n+")
_CHECKABLE = re.compile(
    r"[0-9०-९]|अध्याय|श्लोक|पुराण|उपनिषद|वेद|रामायण|महाभारत|गीता|शिलालेख|"
    r"इतिहासकार|पुरातत्व|ASI|यूनेस्को|सदी|ईसा|वर्ष पहले|साल पहले|राजा|वंश|निर्माण|बनवाया"
)
_OVERCLAIM = re.compile(
    r"वैज्ञानिक(ों)?\s*(ने)?\s*(भी)?\s*(सिद्ध|साबित)|विज्ञान\s*(भी)?\s*(हैरान|नहीं समझ|समझा नहीं)|"
    r"100\s*%|सौ प्रतिशत|आज तक कोई नहीं|कोई नहीं जानता|एलियन|साबित हो चुका|पक्का सबूत"
)
_HEDGED = re.compile(r"मान्यता|लोक कथा|कहा जाता|माना जाता|परंपरा|कथा के अनुसार|प्रमाण नहीं")


def fact_check_items(payload, limit=12):
    items = []
    scenes = ((payload.get("long_video") or {}).get("scenes") or [])
    for n, scene in enumerate(scenes, start=1):
        for sent in _SENT_SPLIT.split(str(scene.get("text") or "")):
            sent = sent.strip()
            if len(sent) < 12:
                continue
            if _OVERCLAIM.search(sent):
                items.append({"scene": n, "claim": sent, "risk": "HIGH - overclaim; soften or remove"})
            elif _CHECKABLE.search(sent) and not _HEDGED.search(sent):
                items.append({"scene": n, "claim": sent, "risk": "CHECK - verify source / date / verse"})
    items.sort(key=lambda x: 0 if x["risk"].startswith("HIGH") else 1)
    return items[:limit]


def _merged_seo(payload):
    seo = _as_dict(payload.get("seo_metadata"))
    for k, v in _as_dict(payload.get("seo")).items():
        if v not in (None, "", [], {}) and not seo.get(k):
            seo[k] = v
    return seo


def validate_payload(payload):
    payload = _as_dict(payload)
    seo = _merged_seo(payload)
    long_video = _as_dict(payload.get("long_video"))
    scenes = long_video.get("scenes") or []
    shorts = _as_dict(payload.get("shorts"))
    shorts_scenes = shorts.get("scenes") or []
    title = _norm(seo.get("long_video_title"))
    description = _norm(seo.get("long_video_description"))
    tags = seo.get("tags") or []
    hashtags = seo.get("hashtags") or []
    thumbnail = _as_dict(payload.get("thumbnail"))
    hook = _norm(thumbnail.get("thumbnailText") or seo.get("thumbnailText"))
    title_variants = seo.get("titleVariants") or []
    thumbnail_concepts = seo.get("thumbnailConcepts") or []
    primary_keyword = _norm(seo.get("primaryKeyword"))
    secondary_keywords = seo.get("secondaryKeywords") or []
    cta = _norm(seo.get("cta"))
    meta = _as_dict(payload.get("_meta"))
    entertainment_angle = _norm(meta.get("entertainment_angle"))
    festival_priority = _norm(meta.get("festival_priority"))
    fun_with_fact_angle = _norm(meta.get("fun_with_fact_angle"))
    content_role = _norm(meta.get("content_role"))
    experiment_hypothesis = _norm(meta.get("experiment_hypothesis"))
    next_episode_angle = _norm(meta.get("next_episode_angle"))
    retention_adaptation = _norm(meta.get("retention_adaptation"))
    experiment_id = _norm(meta.get("experiment_id"))
    shorts_funnel_hook = _norm(meta.get("shorts_funnel_hook"))
    long_video_continuation = _norm(meta.get("long_video_continuation"))
    issues, warnings = [], []
    try:
        from hindi_text import has_latin
        if has_latin(title):
            warnings.append("title_contains_latin_letters")
        latin_scenes = [i + 1 for i, sc in enumerate(scenes) if has_latin((sc or {}).get("text", ""))]
        if latin_scenes:
            warnings.append(f"latin_words_in_narration_scenes_{latin_scenes}_auto_converted")
        if has_latin(hook):
            warnings.append("thumbnail_text_contains_latin_auto_replaced")
    except Exception:
        pass

    if not scenes:
        issues.append("no_long_video_scenes")
    if not title:
        issues.append("missing_title")
    if len(title) > 100:
        warnings.append("title_over_100_chars")
    if not description:
        warnings.append("missing_description")
    if not tags:
        warnings.append("missing_seo_tags")
    if not hashtags:
        warnings.append("missing_hashtags")
    if len(hashtags) > 8:
        warnings.append("too_many_hashtags")
    if not hook:
        warnings.append("missing_thumbnail_hook")
    elif len(hook.split()) > 5:
        warnings.append("thumbnail_hook_too_long")
    if len(title_variants) != 3:
        warnings.append("title_variants_should_be_exactly_3")
    elif len({_norm(x) for x in title_variants if x}) < 3:
        warnings.append("title_variants_are_not_materially_distinct")
    if len(thumbnail_concepts) != 3:
        warnings.append("thumbnail_concepts_should_be_exactly_3")
    if not primary_keyword:
        warnings.append("missing_primary_keyword")
    if not (5 <= len(secondary_keywords) <= 10):
        warnings.append("secondary_keywords_should_be_5_to_10")
    if not cta:
        warnings.append("missing_story_specific_cta")
    if not entertainment_angle:
        warnings.append("missing_entertainment_angle")
    if not fun_with_fact_angle:
        warnings.append("missing_fun_with_fact_angle")
    if festival_priority in ("high", "medium") and not meta.get("festival_angle"):
        warnings.append("festival_priority_without_festival_angle")
    # Content-role values are authored strategy labels, not a closed enum.
    # Keep the core taxonomy while accepting the explicit exploratory role
    # produced by the current Visual Director / Make pipeline.
    valid_content_roles = {
        "discovery", "retention", "conversion", "loyalty", "authority",
        "primary_long_and_short_explorer", "educational_presenter",
    }
    if content_role not in valid_content_roles:
        warnings.append("missing_or_invalid_content_role")
    if not experiment_hypothesis:
        warnings.append("missing_experiment_hypothesis")
    if not next_episode_angle:
        warnings.append("missing_viewer_journey_next_episode")
    if not retention_adaptation:
        warnings.append("missing_retention_adaptation")
    if not experiment_id:
        warnings.append("missing_experiment_id")
    if not shorts_funnel_hook:
        warnings.append("missing_shorts_funnel_hook")
    if not long_video_continuation:
        warnings.append("missing_long_video_continuation")
    if cta and not any(token in cta for token in ("सब्सक्राइब", "subscribe", "कमेंट", "comment", "share", "शेयर")):
        warnings.append("cta_has_no_engagement_or_subscribe_signal")
    if scenes:
        texts = [_norm(s.get("text") or s.get("narration_chunk")) for s in scenes]
        empty = sum(not t for t in texts)
        if empty:
            issues.append(f"{empty}_scenes_missing_narration")
        nonempty = [t for t in texts if t]
        repeated = 0
        for i, t in enumerate(nonempty):
            if len(t.split()) < 7:
                warnings.append(f"scene_{i+1}_narration_very_short")
            if i and t == nonempty[i-1]:
                repeated += 1
        if repeated:
            issues.append("consecutive_duplicate_narration")
        strict_missing = [str(i + 1) for i, s in enumerate(scenes) if s.get("visualStrict") and not s.get("visualEntities")]
        if strict_missing:
            issues.append("strict_visual_scene_missing_entity:" + ",".join(strict_missing))
        if len(scenes) != 6:
            issues.append(f"long_scene_count_must_be_6:{len(scenes)}")
    if len(shorts_scenes) != 5:
        issues.append(f"short_scene_count_must_be_5:{len(shorts_scenes)}")

    all_scene_text = " ".join(_norm(s.get("text") or s.get("narration_chunk")) for s in scenes)
    words = all_scene_text.split() if all_scene_text else []
    short_words = sum(len(str(scene.get("text") or scene.get("narration_chunk") or "").split()) for scene in shorts_scenes)
    if all_scene_text:
        if not (330 <= len(words) <= 430):
            issues.append(f"long_narration_outside_330_430_words:{len(words)}")
        ngrams = {}
        for i in range(max(0, len(words) - 5)):
            gram = " ".join(words[i:i+6])
            ngrams[gram] = ngrams.get(gram, 0) + 1
        repeated_ngrams = sum(1 for v in ngrams.values() if v > 1)
        if repeated_ngrams >= 3:
            warnings.append("repeated_six_word_phrases_detected")
    if shorts_scenes:
        if short_words < 50 or short_words > 150:
            issues.append(f"short_narration_outside_50_150_words:{short_words}")
        elif not (70 <= short_words <= 110):
            warnings.append(f"short_narration_outside_70_110_target:{short_words}")

    filler = ("आज की इस वीडियो में", "नमस्कार दोस्तों", "स्वागत है दोस्तों", "इस वीडियो में हम जानेंगे", "आज हम जानेंगे")
    if any(x in _norm(s.get("text")) for s in scenes for x in filler):
        warnings.append("generic_intro_filler_detected")

    risky = [i for i in fact_check_items(payload) if i["risk"].startswith("HIGH")]
    if risky:
        warnings.append(f"fact_overclaim_in_scenes_{','.join(str(i['scene']) for i in risky)}")

    report = {
        "ok": not issues,
        "warnings": warnings,
        "issues": issues,
        "sceneCount": len(scenes),
        "shortSceneCount": len(shorts_scenes),
        "longNarrationWords": len(all_scene_text.split()) if all_scene_text else 0,
        "shortNarrationWords": short_words,
        "targetLongMinutes": 3,
        "targetLongSeconds": [150, 210],
        "hasHindi": any(DEVANAGARI.search(str(s.get("text") or "")) for s in scenes),
        "entertainmentAngle": entertainment_angle,
        "festivalPriority": festival_priority,
        "funWithFactAngle": fun_with_fact_angle,
        "contentRole": content_role,
        "retentionAdaptation": retention_adaptation,
        "experimentId": experiment_id,
        "shortsFunnelHook": shorts_funnel_hook,
        "longVideoContinuation": long_video_continuation,
    }
    return report

def main():
    raw = os.environ.get("DISPATCH_PAYLOAD", "").strip()
    payload = json.loads(raw) if raw else {}
    report = validate_payload(payload)
    os.makedirs("out", exist_ok=True)
    with open("out/content_qc_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report["ok"]:
        sys.exit(1)

if __name__ == "__main__":
    main()
