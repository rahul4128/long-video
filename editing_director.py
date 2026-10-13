"""Narration-led documentary editing plan for Remotion (no GPU / paid API).

This stage edits metadata, not the story or the media source: it never changes
a shot's factual subject, narration word timing, or visual start/end positions.
"""
import json
import os
import re
from collections import Counter
from pathlib import Path
from editing_style_engine import select_edit_style

TREATMENTS = {"clean", "detail", "impact", "breathing", "question"}
TRANSITIONS = {"cut", "crossfade", "blur_cut", "whip_pan", "flash_cut"}
CUE_WORDS = ("लेकिन", "असल", "यही", "तभी", "कैसे", "क्यों", "देखिए", "रहस्य", "सच", "क्या",
             "जानिए", "इसलिए", "नहीं", "पहली", "बात", "बदल", "अचानक")
STOPWORDS = {"और", "लेकिन", "आप", "अगर", "इस", "उस", "एक", "तो", "है", "हैं", "में", "को", "के",
             "की", "का", "ही", "ये", "वो", "यह", "यहाँ", "वहाँ", "हो", "था", "थी", "कि",
             "जो", "अब", "से", "भी", "पर", "ने", "क्या"}


def _short_phrase(text):
    """Use verbatim narration words, never invent 'facts' for overlay labels."""
    words = re.findall(r"[\w\u0900-\u097f]+", str(text or ""), flags=re.UNICODE)
    if not words:
        return ""
    # A label is meaningful only if it has at least one substantive token.
    useful = [w for w in words if w not in STOPWORDS and len(w) >= 3]
    if not useful:
        return ""
    # Preserve spoken order; choose a compact 2-4 word phrase containing a cue.
    start = next((i for i, w in enumerate(words) if w in CUE_WORDS), 0)
    chosen = words[start:start + 4]
    result = " ".join(chosen)
    if len(result) > 36:
        result = " ".join(chosen[:3])
    return result[:36].rstrip()


def _beat_for_shot(shot, scene):
    beats = scene.get("visualBeats") or []
    index = shot.get("beatIndex")
    if index is not None:
        for beat in beats:
            if beat.get("beatIndex") == index:
                return beat
    start = shot.get("startSeconds")
    if isinstance(start, (int, float)):
        for beat in beats:
            lo = beat.get("actualStartSeconds")
            hi = beat.get("actualEndSeconds")
            if isinstance(lo, (int, float)) and isinstance(hi, (int, float)) and lo - 0.1 <= start < hi + 0.1:
                return beat
    return {}


def _word_focus(scene):
    text = str(scene.get("narration_chunk") or scene.get("text") or "")
    director = scene.get("director") or {}
    pattern = str(director.get("entertainmentBeat") or scene.get("entertainmentBeat") or "")
    return bool("?" in text or "?" in str(director.get("mood") or "") or pattern in {"hook", "curiosity"})


def _decorate_scene(scene, format_name, style_plan=None):
    shots = scene.get("shots") or []
    if not shots:
        return {"shots": 0, "cuts": 0, "accent": 0, "impact": 0, "warnings": ["missing_shots"]}
    mood = str(scene.get("musicMood") or "devotional")
    director = scene.get("director") or {}
    pattern = str(director.get("entertainmentBeat") or scene.get("entertainmentBeat") or "")
    style = str((style_plan or {}).get("style") or "cinematic_devotional")
    scene["editStyle"] = style
    scene["captionStyle"] = (style_plan or {}).get("profile", {}).get("caption", "focus")
    focus_idx = None
    # Prefer the authored meaningful visual beat over arbitrary periodic edits.
    if pattern in {"reveal", "climax", "action"}:
        candidates = [(i, shot) for i, shot in enumerate(shots) if
                      (_beat_for_shot(shot, scene).get("emphasisText") or
                       _beat_for_shot(shot, scene).get("emphasisStyle") in {"reveal", "climax", "action"})]
        if candidates:
            focus_idx = candidates[0][0]
        elif len(shots) > 1:
            focus_idx = max(1, round(len(shots) * 0.68) - 1)
    elif pattern == "curiosity" or _word_focus(scene):
        focus_idx = 0
    elif style == "presenter_explainer" and len(shots) >= 2:
        focus_idx = 1
    elif style == "festival_energy" and len(shots) >= 2:
        focus_idx = len(shots) - 1

    accent_count = 0
    impact_count = 0
    cuts = 0
    for index, shot in enumerate(shots):
        beat = _beat_for_shot(shot, scene)
        kind = str(shot.get("shotType") or beat.get("shotType") or "")
        shot["editTreatment"] = "clean"
        if kind in {"detail", "close_up"}:
            shot["editTreatment"] = "detail"
        elif mood == "emotional" or kind == "atmosphere":
            shot["editTreatment"] = "breathing"
        if index == focus_idx and (pattern in {"reveal", "climax", "action"} or style == "festival_energy"):
            shot["editTreatment"] = "impact"
            impact_count += 1
        elif index == focus_idx and (pattern in {"hook", "curiosity"} or _word_focus(scene) or style == "presenter_explainer"):
            shot["editTreatment"] = "question"

        # Every skill is *eligible*, not automatically applied to every shot:
        # subtle spotlight blur supports questions, and subject-safe grading
        # supports cinematic / bright celebration / emotional moments.
        shot["editAccent"] = style
        shot["editSpotlight"] = bool(shot["editTreatment"] == "question" and
                                     style in {"curiosity_reveal", "presenter_explainer"})
        shot["editBeatSnap"] = bool(style == "festival_energy" and
                                    shot["editTreatment"] == "impact")

        # News/documentary grammar: most edits are clean cuts. Limit expensive
        # blurs and crossfades to a justified story pivot or a calm close.
        if index == 0:
            shot["transition"] = "cut"
        elif index == focus_idx and pattern in {"climax", "reveal"}:
            shot["transition"] = (
                "flash_cut" if style == "curiosity_reveal" else
                "whip_pan" if style == "festival_energy" else
                "blur_cut"
            )
        elif index == focus_idx and style == "festival_energy" and index > 0:
            shot["transition"] = "whip_pan"
        elif (index == len(shots) - 1 and len(shots) >= 3 and
              mood in {"devotional", "emotional"}):
            shot["transition"] = "crossfade"
        else:
            shot["transition"] = "cut"
        if index and shot["transition"] == "cut":
            cuts += 1

        # At most ONE tasteful documentary label per scene, no collision with
        # existing kinetic typography, and never on top of a hook overlay.
        shot.pop("editorialLabel", None)
        if index == focus_idx and not beat.get("emphasisText"):
            start = shot.get("startSeconds")
            is_opening_hook = scene.get("scene_number") == 1 and (
                start is None or (isinstance(start, (int, float)) and start < 1.85))
            if not is_opening_hook:
                label = _short_phrase(beat.get("narrationText") or beat.get("narrationCue") or "")
                if label:
                    shot["editorialLabel"] = label
                    accent_count += 1

    return {
        "shots": len(shots),
        "cuts": cuts,
        "accent": accent_count,
        "impact": impact_count,
        "warnings": [],
        "style": style,
        "skills_used": sorted({key for shot in shots for key, on in (
            ("kinetic_text", bool(shot.get("editorialLabel"))),
            ("spotlight_blur", bool(shot.get("editSpotlight"))),
            ("impact_cut", shot.get("editTreatment") == "impact"),
            ("whip_pan", shot.get("transition") == "whip_pan"),
            ("flash_cut", shot.get("transition") == "flash_cut"),
            ("soft_transition", shot.get("transition") == "crossfade"),
            ("word_captions", True),
            ("b_roll", True),
        ) if on}),
        "treatments": dict(Counter(s.get("editTreatment") for s in shots)),
        "transitions": dict(Counter(s.get("transition") for s in shots[1:])),
    }


def validate_editing(scenes):
    """Checks planned-only data; final visual files/timing handled by visual QC."""
    for scene in scenes:
        shots = scene.get("shots") or []
        if not shots:
            raise ValueError(f"Scene {scene.get('scene_number')}: missing editing shots")
        if sum(bool(s.get("editorialLabel")) for s in shots) > 1:
            raise ValueError("Too many text cards in one scene")
        if sum(s.get("transition") == "blur_cut" for s in shots) > 1:
            raise ValueError("Excessive blur transitions")
        for shot in shots:
            if shot.get("editTreatment") not in TREATMENTS:
                raise ValueError("Invalid visual treatment")
            if shot.get("transition") not in TRANSITIONS:
                raise ValueError("Invalid edit transition")
            if shot.get("editSpotlight") not in (True, False, None):
                raise ValueError("Invalid spotlight flag")
            if shot.get("editBeatSnap") not in (True, False, None):
                raise ValueError("Invalid snap flag")
            if shot.get("editAccent") and shot.get("editAccent") not in (
                "cinematic_devotional", "curiosity_reveal", "presenter_explainer",
                "emotional_story", "festival_energy"
            ):
                raise ValueError("Invalid edit accent")
            if len(str(shot.get("editorialLabel") or "")) > 36:
                raise ValueError("Unsafe editorial text length")
            if shot.get("file") is None:
                raise ValueError("Missing visual reference")


def attach_editing(long_scenes, shorts_scenes,
                   report_path="out/editing_qc_report.json",
                   enabled=None, context=None):
    enabled = (os.getenv("EDITORIAL_EDITING_ENABLED", "true").lower() == "true") if enabled is None else bool(enabled)
    style_plan = select_edit_style(context, long_scenes)
    report = {"editorVersion": 2, "enabled": enabled,
              "note": "Story-aware CPU editing, no assumption that tutorial thumbnails are trend metrics",
              "selectedStyle": style_plan["style"],
              "styleDecision": style_plan,
              "formats": {}}
    if enabled:
        for name, scenes in (("long", long_scenes), ("shorts", shorts_scenes)):
            details = []
            for scene in scenes:
                result = _decorate_scene(scene, name, style_plan)
                details.append({"scene": scene.get("scene_number"), **result})
            validate_editing(scenes)
            report["formats"][name] = details
    path = Path(report_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report
