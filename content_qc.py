"""Pre-render content quality gate for short-form devotional episodes.

This is intentionally heuristic: it catches structural problems before spending
GitHub Actions time on media generation, but it does not claim to predict views.
"""
import json, os, re, sys

DEVANAGARI = re.compile(r"[\u0900-\u097F]")
def _norm(s):
    return re.sub(r"\s+", " ", str(s or "").strip()).lower()

def validate_payload(payload):
    seo = payload.get("seo_metadata") or {}
    long_video = payload.get("long_video") or {}
    scenes = long_video.get("scenes") or []
    title = _norm(seo.get("long_video_title"))
    description = _norm(seo.get("long_video_description"))
    tags = seo.get("tags") or []
    hashtags = seo.get("hashtags") or []
    thumbnail = payload.get("thumbnail") or {}
    hook = _norm(thumbnail.get("thumbnailText") or seo.get("thumbnailText"))
    title_variants = seo.get("titleVariants") or []
    thumbnail_concepts = seo.get("thumbnailConcepts") or []
    primary_keyword = _norm(seo.get("primaryKeyword"))
    secondary_keywords = seo.get("secondaryKeywords") or []
    cta = _norm(seo.get("cta"))
    issues, warnings = [], []

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
        strict_missing = [
            str(i + 1) for i, s in enumerate(scenes)
            if s.get("visualStrict") and not s.get("visualEntities")
        ]
        if strict_missing:
            issues.append("strict_visual_scene_missing_entity:" + ",".join(strict_missing))
        if len(scenes) < 5:
            warnings.append("fewer_than_5_scenes_for_3_minute_format")
        if len(scenes) > 12:
            warnings.append("too_many_scenes_for_3_minute_format")

    # Growth-oriented packaging/originality guardrails. These are warnings rather than
    # hard failures so a legitimate episode is never blocked solely by metadata.
    all_scene_text = " ".join(_norm(s.get("text") or s.get("narration_chunk")) for s in scenes)
    if all_scene_text:
        words = all_scene_text.split()
        if len(words) > 520:
            warnings.append("narration_over_520_words")
        if len(words) < 280:
            warnings.append("narration_under_280_words")
        # Repeated long phrases are a useful proxy for templated/mass-produced narration.
        ngrams = {}
        for i in range(max(0, len(words) - 5)):
            gram = " ".join(words[i:i+6])
            ngrams[gram] = ngrams.get(gram, 0) + 1
        repeated_ngrams = sum(1 for v in ngrams.values() if v > 1)
        if repeated_ngrams >= 3:
            warnings.append("repeated_six_word_phrases_detected")

    # Growth-oriented packaging/originality guardrails. These are warnings rather than
    # hard failures so a legitimate episode is never blocked solely by metadata.
    all_scene_text = " ".join(_norm(s.get("text") or s.get("narration_chunk")) for s in scenes)
    if all_scene_text:
        words = all_scene_text.split()
        if len(words) > 520:
            warnings.append("narration_over_520_words")
        if len(words) < 280:
            warnings.append("narration_under_280_words")
        ngrams = {}
        for i in range(max(0, len(words) - 5)):
            gram = " ".join(words[i:i+6])
            ngrams[gram] = ngrams.get(gram, 0) + 1
        repeated_ngrams = sum(1 for v in ngrams.values() if v > 1)
        if repeated_ngrams >= 3:
            warnings.append("repeated_six_word_phrases_detected")

    # Detect obvious generic filler that tends to weaken retention.
    filler = ("आज की इस वीडियो में", "नमस्कार दोस्तों", "स्वागत है दोस्तों",
              "इस वीडियो में हम जानेंगे", "आज हम जानेंगे")
    if any(x in _norm(s.get("text")) for s in scenes for x in filler):
        warnings.append("generic_intro_filler_detected")

    report = {
        "ok": not issues,
        "warnings": warnings,
        "issues": issues,
        "sceneCount": len(scenes),
        "hasHindi": any(DEVANAGARI.search(str(s.get("text") or "")) for s in scenes),
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
    # Only hard structural failures stop the expensive media pipeline.
    if not report["ok"]:
        sys.exit(1)

if __name__ == "__main__":
    main()
