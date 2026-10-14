"""Source-grounded shot relevance gates for narrative video editing.

A high total score can otherwise come from resolution, motion, and continuity
even when the footage has almost no relationship to the narration. This
module enforces subject/semantic support independently of cinematic polish.

No stock API or ML model calls; scoring and file provenance are inputs.
"""
import os


def _number(value, fallback=0.0):
    try:
        return float(value)
    except (TypeError, ValueError, OverflowError):
        return fallback


def strong_stock_match(candidate, *, allow_legacy=False):
    """Return (accepted, reason). Never accept unrelated B-roll on polish alone."""
    if not isinstance(candidate, dict):
        return False, "missing_candidate_metadata"
    if candidate.get("rejected"):
        return False, str(candidate.get("rejectReason") or "rejected_by_visual_matcher")
    breakdown = candidate.get("scoreBreakdown")
    if not isinstance(breakdown, dict):
        return (allow_legacy, "legacy_not_scored" if not allow_legacy else "legacy_review_only")
    semantics = _number(breakdown.get("semantic"))
    entity_action = _number(breakdown.get("entity_action"))
    total = _number(candidate.get("selectionScore"))
    clip_similarity = candidate.get("clipSimilarity")
    is_strict = bool(candidate.get("visualContractStrict"))
    min_sem = _number(os.getenv("VISUAL_STORY_MIN_SEMANTIC", "0.38"), .38)
    min_entity = _number(os.getenv("VISUAL_STORY_MIN_ENTITY_ACTION", "0.35"), .35)
    min_total = _number(os.getenv("VISUAL_STORY_MIN_TOTAL", "0.60"), .60)
    # Fixed safety floor: even if the aggregate 7-part scoring looks excellent,
    # a nearly unrelated person/temple video is not narrative evidence.
    min_sem = max(.28, min(.75, min_sem))
    min_entity = max(.25, min(.75, min_entity))
    min_total = max(.52, min(.85, min_total))
    if total < min_total:
        return False, "overall_shot_relevance_below_floor"
    if semantics < min_sem:
        return False, "narration_semantic_mismatch"
    if entity_action < min_entity:
        return False, "subject_or_action_mismatch"
    # When the preview model evaluated a shot, respect its actual result.
    # A permissive .20 cosine minimum allowed often unrelated stock.
    if clip_similarity is not None and not is_strict and _number(clip_similarity) < .245:
        return False, "preview_image_weak_narration_match"
    return True, "narration_and_subject_supported"


def visual_relevance_issues(scenes, format_name):
    """Find low-evidence footage/abstract emergencies before Remotion starts.

    This is not an AI visual inspector; it catches precisely the weak metadata
    match and emergency placeholder that the earlier pipeline declared OK.
    """
    problems = []
    for scene_no, scene in enumerate(scenes, 1):
        for shot_no, shot in enumerate(scene.get("shots") or [], 1):
            if not isinstance(shot, dict):
                continue
            source = str(shot.get("source") or "")
            if source in {"local_atmosphere_fallback", "local_continuity_fallback"}:
                problems.append({
                    "format": format_name, "scene": scene_no, "shot": shot_no,
                    "beat": shot.get("beatIndex"),
                    "reason": "emergency_placeholder_not_story_footage",
                    "source": source,
                })
                continue
            # Unscored legacy/local clips must not masquerade as reviewed shots.
            if shot.get("type") == "video":
                if source not in {"pexels", "pixabay", "coverr", "wikimedia"}:
                    problems.append({
                        "format": format_name, "scene": scene_no, "shot": shot_no,
                        "reason": "stock_source_without_provenance",
                        "source": source,
                    })
                    continue
                okay, reason = strong_stock_match(shot)
                if not okay:
                    problems.append({
                        "format": format_name, "scene": scene_no, "shot": shot_no,
                        "beat": shot.get("beatIndex"), "reason": reason,
                        "source": source,
                    })
    return problems
