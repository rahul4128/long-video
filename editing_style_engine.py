"""Evidence-gated video editing styles for CPU-only Remotion rendering.

References describe *techniques*, not a license to claim they are trending.
Select from topic/format/audience intent; only measured recent performance
records can change the order of supported styles.
"""
from datetime import date, datetime
import os
import json
from pathlib import Path
import re

STYLES = {
    "cinematic_devotional": {
        "description": "Warm restrained color, beautiful B-roll, spacious explanation",
        "caption": "calm",
        "accent": "gold",
        "pace": "measured",
        "skills": ["b_roll", "clean_cuts", "depth_motion", "soft_transitions", "film_grade", "clean_captions", "music_ducking"],
    },
    "curiosity_reveal": {
        "description": "Visible question, purposeful suspense, timed reveal and impact",
        "caption": "focus",
        "accent": "amber",
        "pace": "brisk",
        "skills": ["b_roll", "hook_reveal", "whip_transition", "blur_transition", "kinetic_text", "spotlight_blur", "sound_punctuation"],
    },
    "presenter_explainer": {
        "description": "Clear key points and explanatory details, minimal distracting effects",
        "caption": "focus",
        "accent": "blue",
        "pace": "steady",
        "skills": ["b_roll", "clean_cuts", "animated_keywords", "detail_focus", "comparisons_if_verified", "clean_captions"],
    },
    "emotional_story": {
        "description": "Natural holds, soft reveals, patient typography and musical contrast",
        "caption": "calm",
        "accent": "warm",
        "pace": "measured",
        "skills": ["b_roll", "gentle_pans", "soft_transitions", "music_ducking", "quiet_pause", "clean_captions"],
    },
    "festival_energy": {
        "description": "Celebration/action coverage with faster, controlled cuts",
        "caption": "focus",
        "accent": "saffron",
        "pace": "brisk",
        "skills": ["b_roll", "match_cuts", "whip_transition", "text_reveal", "color_pop", "beat_sfx", "clean_captions"],
    },
}
ALIASES = {
    "cinematic": "cinematic_devotional",
    "devotional": "cinematic_devotional",
    "documentary": "presenter_explainer",
    "explainer": "presenter_explainer",
    "journalist": "presenter_explainer",
    "mystery": "curiosity_reveal",
    "reveal": "curiosity_reveal",
    "emotional": "emotional_story",
    "festival": "festival_energy",
}


def _text(x, limit=2000):
    return str(x or "")[:limit].casefold()


def infer_story_style(context=None, scenes=None):
    context = context if isinstance(context, dict) else {}
    scenes = scenes or []
    meta = context.get("_meta") if isinstance(context.get("_meta"), dict) else {}
    seo = context.get("seo_metadata") if isinstance(context.get("seo_metadata"), dict) else {}
    title = _text(seo.get("long_video_title"))
    genre = " ".join(_text(meta.get(k), 400) for k in (
        "category", "track", "festival_angle", "entertainment_angle",
        "fun_with_fact_angle", "content_role",
    ))
    narrative = " ".join(_text(s.get("narration_chunk"), 350) for s in scenes[:5] if isinstance(s, dict))
    patterns = [str((s.get("director") or {}).get("entertainmentBeat") or "") for s in scenes if isinstance(s, dict)]
    combined = " ".join((title, genre, narrative))
    if re.search(r"गरबा|डांडिया|जुलूस|झांकी|नृत्य|मेला|dance|celebrat|festival|उत्सव", combined):
        return "festival_energy", "story_subject_and_visual_action"
    if re.search(r"करुणा|माँ की|आँसू|भक्ति का|emotional|ममता|त्याग|संघर्ष|सहानुभूति", combined):
        return "emotional_story", "emotional_story_intent"
    if re.search(r"कैसे करें|क्यों करें|कब करें|गलती|समझिए|तरीका|पाँच|तीन|5 |3 |tips|explain|reason|how to|what is", combined):
        return "presenter_explainer", "explanation_or_audience_question"
    if re.search(r"रहस्य|खुलासा|सच क्या|अचानक|पहली बार|क्यों ऐसा|myster|secret|truth|surpris", combined) or patterns.count("reveal") >= 2:
        return "curiosity_reveal", "story_curiosity_or_revelation"
    return "cinematic_devotional", "safe_devotional_default"


def _recent_signal_winner(signals, today=None, required_format="long"):
    """Opt-in aggregate performance records, not guessed trend rankings.

    Format: {style, published_on, videos, average_view_percentage,
             shares_per_1000, platform, source}. A single viral video is not
    evidence for the editing effect. Require >=3 recent videos per style.
    """
    today = today or date.today()
    if not isinstance(signals, list):
        return None, "no_structured_editing_style_metrics"
    options = []
    for item in signals[:35]:
        if not isinstance(item, dict):
            continue
        style = ALIASES.get(str(item.get("style") or "").lower(), item.get("style"))
        if style not in STYLES:
            continue
        if item.get("format") and item["format"] != required_format:
            continue
        try:
            published = date.fromisoformat(str(item.get("published_on")))
            age = (today - published).days
            videos = int(item.get("videos") or 0)
            watch = float(item.get("average_view_percentage") or 0)
            shares = float(item.get("shares_per_1000") or 0)
            source = str(item.get("source") or "")
            platform = str(item.get("platform") or "")
        except (ValueError, TypeError):
            continue
        if not 0 <= age <= 45 or videos < 3 or not 0 < watch <= 100:
            continue
        if not 0 <= shares <= 1000 or platform not in ("youtube", "instagram"):
            continue
        if not source or len(source) > 300:
            continue
        # Reward watch fraction and sharing modestly, not raw views.
        score = watch + min(shares, 50) * 0.3 - (age / 45) * 5
        options.append((score, style, {"style": style, "age_days": age,
                                       "videos": videos, "source": source,
                                       "average_view_percentage": watch,
                                       "shares_per_1000": shares,
                                       "platform": platform}))
    if not options:
        return None, "no_eligible_verified_metrics"
    options.sort(key=lambda row: row[0], reverse=True)
    return options[0][2], "recent_source_reported_multi_video_metric"


def select_edit_style(context=None, scenes=None):
    context = context if isinstance(context, dict) else {}
    narrative_style, reason = infer_story_style(context, scenes)
    meta = context.get("_meta") if isinstance(context.get("_meta"), dict) else {}
    # Make's existing schema passes _meta.decisionBasis unchanged. Let the
    # story council add an EDIT_STYLE marker there; do not alter JSON mapping.
    basis = str(meta.get("decisionBasis") or "")[:10000]
    match = re.search(r"(?:^|\n)\s*EDIT_STYLE\s*[:=]\s*([a-z_]+)", basis, re.I)
    declared = meta.get("editing_style") or (match.group(1) if match else None)
    compatible_hints = {
        "cinematic_devotional": set(STYLES),
        "curiosity_reveal": {"curiosity_reveal", "presenter_explainer"},
        "presenter_explainer": {"presenter_explainer", "curiosity_reveal"},
        "emotional_story": {"emotional_story", "cinematic_devotional"},
        "festival_energy": {"festival_energy", "curiosity_reveal"},
    }
    if isinstance(declared, str):
        requested = ALIASES.get(declared.strip().lower(), declared.strip().lower())
        if requested in compatible_hints[narrative_style]:
            narrative_style = requested
            reason = "script_style_from_existing_make_payload"
    # Optional read-only, owner-auditable channel data import. This file is
    # empty until real, labeled video metrics are provided; never ask an LLM
    # to invent per-style retention or treat raw YouTube search as evidence.
    signals = meta.get("editing_style_signals")
    if not isinstance(signals, list):
        scope = os.environ.get("EDITING_METRICS_SCOPE", "").strip().lower()
        if scope.startswith("visual-director-v2-"):
            scope = scope[len("visual-director-v2-"):]
        filename = ("editing_style_signals_" + scope + ".json") if scope in ("primary", "oflifepart31") else "editing_style_signals.json"
        stored = Path("data") / filename
        try:
            loaded = json.loads(stored.read_text(encoding="utf-8")) if stored.is_file() else []
            signals = loaded if isinstance(loaded, list) else []
        except (OSError, ValueError):
            signals = []
    trend, trend_reason = _recent_signal_winner(signals)
    selected = narrative_style
    # Preserve story-topic fit. A fast festival edit must not be imposed on an
    # intimate emotional story merely because festival video metrics grew.
    compatible = {
        "cinematic_devotional": {"cinematic_devotional", "emotional_story"},
        "curiosity_reveal": {"curiosity_reveal", "presenter_explainer"},
        "presenter_explainer": {"presenter_explainer", "curiosity_reveal"},
        "emotional_story": {"emotional_story", "cinematic_devotional"},
        "festival_energy": {"festival_energy", "curiosity_reveal"},
    }
    if trend and trend["style"] in compatible[narrative_style] and trend["style"] != narrative_style:
        selected = trend["style"]
        reason = "reported_channel_style_performance"
    return {
        "style": selected,
        "reason": reason,
        "story_style": narrative_style,
        "trend_signal": trend,
        "trend_verdict": trend_reason,
        "trend_claim": "source_reported_not_independently_verified" if trend else "not_verified",
        "profile": STYLES[selected],
        "all_available_styles": list(STYLES),
        "skills_available": sorted({skill for s in STYLES.values() for skill in s["skills"]}),
    }
