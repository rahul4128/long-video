"""Retention-aware deterministic AI Director.

The director deliberately uses fewer effects: a wrong SFX/transition hurts
retention more than a clean cut. Pattern breaks are reserved for real story
beats, reveals, action and climax.
"""
import re
from storyteller import build_prosody_map

_EFFECTS = {"temple_bell", "shankh", "om_drone", "flute_swell", "none"}

def _words(text):
    return set(re.findall(r"[\w\u0900-\u097F]+", (text or "").lower()))

def direct_scene(scene, index, total, effect_slot=False):
    text = scene.get("text") or scene.get("narration_chunk") or ""
    w = _words(text)
    climax = bool(scene.get("isClimax") or scene.get("emphasis") == "climax")
    devotional = bool(w & {"krishna","shiva","ram","hanuman","कृष्ण","शिव","राम","हनुमान","मंदिर","पूजा","धर्म"})
    reveal = bool(w & {"रहस्य","सत्य","reveal","mystery","सच","चमत्कार","अंत","क्यों","क्योंकि","कैसे","लेकिन","अचानक","खुलासा"})
    question = "?" in text or bool(w & {"क्यों","कैसे","क्या","रहस्य","सच"})
    action = bool(w & {"भागा","दौड़ा","युद्ध","गिरा","उठा","पहुंचा","पहुंचे","देखा","मिला","खुला","crossed","walked","ran"})

    pattern_break = (
        "hook" if index == 1 else
        "climax" if climax else
        "reveal" if reveal else
        "action" if action else
        "curiosity" if question else
        "establish"
    )

    camera = (
        "slow_push" if climax or reveal else
        ("pan_left" if index % 3 == 0 else "zoom_in" if index % 3 == 1 else "pan_right")
    )
    mood = "climax" if climax else "revelation" if reveal else "devotional" if devotional else "cinematic"

    requested_sfx = scene.get("soundEffect")
    if requested_sfx not in _EFFECTS:
        requested_sfx = "none"

    # Never invent a decorative effect. Only honor an explicit scene SFX, or
    # use one restrained divine accent on a genuine hook/reveal/climax slot.
    if requested_sfx != "none":
        sfx = requested_sfx
    elif effect_slot and devotional and pattern_break in {"hook", "reveal", "climax"}:
        sfx = "temple_bell"
    else:
        sfx = "none"

    # Clean cuts are the default. Blur/crossfade are reserved for actual
    # narrative transitions rather than alternating mechanically every scene.
    if climax or reveal:
        transition = "blur_cut"
    elif pattern_break in {"hook", "action"}:
        transition = "cut"
    elif devotional and index % 4 == 0:
        transition = "crossfade"
    else:
        transition = "cut"

    beat = "divine" if devotional and pattern_break == "establish" else pattern_break
    prosody = build_prosody_map(text, beat=beat)

    return {
        "camera": camera,
        "mood": mood,
        "emotion": prosody["emotion"],
        "audioBeat": beat,
        "prosody": prosody,
        "transition": transition,
        "emphasis": "climax" if climax else "normal",
        "soundEffect": sfx,
        "visual_priority": ["subject", "action", "environment"],
        "entertainmentBeat": pattern_break,
        "patternBreak": pattern_break in ("hook", "climax", "reveal", "action"),
        "effectReason": (
            "explicit_scene_request" if requested_sfx != "none"
            else "story_beat" if sfx != "none"
            else "clean_audio"
        ),
        "transitionReason": (
            "reveal_or_climax" if transition == "blur_cut"
            else "story_pattern_break" if transition == "cut" and pattern_break in {"hook", "action"}
            else "restrained_devotional_transition" if transition == "crossfade"
            else "default_clean_cut"
        ),
        "director_version": 3,
    }

def enrich_scenes(scenes):
    total = len(scenes)
    out = []
    effect_budget = max(1, min(3, round(total / 4)))
    used_effects = 0

    for i, scene in enumerate(scenes, 1):
        merged = dict(scene)
        explicit = merged.get("soundEffect") not in (None, "", "none")
        effect_slot = used_effects < effect_budget
        plan = direct_scene(merged, i, total, effect_slot=effect_slot)

        # Keep an explicit effect, but cap automatic effects to the video budget.
        if plan["soundEffect"] != "none":
            if explicit or effect_slot:
                used_effects += 1
            else:
                plan["soundEffect"] = "none"
                plan["effectReason"] = "effect_budget_exhausted"

        merged["director"] = plan
        merged["soundEffect"] = plan["soundEffect"]
        merged["transition"] = plan["transition"]
        out.append(merged)

    return out
