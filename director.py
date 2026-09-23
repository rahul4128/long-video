"""Retention-aware deterministic AI Director.

The director assigns restrained, story-aware animation and voice direction.
It is intentionally deterministic: the same scene produces the same plan,
while legacy payloads remain valid because every field is optional/defaulted.
"""
import re
from storyteller import build_prosody_map

_EFFECTS = {"temple_bell", "shankh", "om_drone", "flute_swell", "none"}

def _words(text):
    return set(re.findall(r"[\w\u0900-\u097F]+", (text or "").lower()))

def _voice_direction(prosody, beat, text):
    energy = {
        "hook": 0.78,
        "climax": 0.88,
        "reveal": 0.82,
        "action": 0.84,
        "curiosity": 0.68,
        "divine": 0.60,
        "establish": 0.52,
    }.get(beat, 0.55)
    pace = float(prosody.get("speed", 0.96))
    pause_after = float(prosody.get("pause_after", 0.16))
    emphasis = list(prosody.get("emphasis") or [])[:3]
    return {
        "emotion": prosody.get("emotion", "conversational"),
        "energy": energy,
        "pace": pace,
        "pauseBefore": 0.18 if beat in {"hook", "reveal", "climax"} else 0.08,
        "pauseAfter": pause_after,
        "emphasis": emphasis,
    }

def _animation_plan(index, total, beat, devotional, reveal, climax, action):
    # Most scenes remain subtle. Strong effects are reserved for story beats.
    if beat == "hook":
        return {
            "type": "climax_push",
            "intensity": 0.42,
            "direction": "forward",
            "particles": False,
            "lightRays": devotional,
            "vignette": 0.42,
            "cameraShake": 0.0,
            "overlay": "none",
            "transition": "cut",
        }
    if climax:
        return {
            "type": "climax_push",
            "intensity": 0.55,
            "direction": "forward",
            "particles": devotional,
            "lightRays": True,
            "vignette": 0.32,
            "cameraShake": 0.012,
            "overlay": "fact",
            "transition": "blur_cut",
        }
    if reveal:
        return {
            "type": "reveal",
            "intensity": 0.40,
            "direction": "forward",
            "particles": devotional,
            "lightRays": True,
            "vignette": 0.48,
            "cameraShake": 0.0,
            "overlay": "fact",
            "transition": "blur_cut",
        }
    if action:
        return {
            "type": "pan_right" if index % 2 else "pan_left",
            "intensity": 0.34,
            "direction": "right" if index % 2 else "left",
            "particles": False,
            "lightRays": False,
            "vignette": 0.34,
            "cameraShake": 0.006,
            "overlay": "none",
            "transition": "cut",
        }
    if beat == "curiosity":
        return {
            "type": "slow_push",
            "intensity": 0.30,
            "direction": "forward",
            "particles": False,
            "lightRays": False,
            "vignette": 0.50,
            "cameraShake": 0.0,
            "overlay": "none",
            "transition": "crossfade",
        }
    if devotional:
        return {
            "type": "parallax",
            "intensity": 0.24,
            "direction": "forward" if index % 2 else "left",
            "particles": index % 4 == 0,
            "lightRays": index % 3 == 0,
            "vignette": 0.38,
            "cameraShake": 0.0,
            "overlay": "none",
            "transition": "crossfade" if index % 3 == 0 else "cut",
        }
    return {
        "type": "parallax" if index % 2 else "slow_push",
        "intensity": 0.22,
        "direction": "right" if index % 2 else "forward",
        "particles": False,
        "lightRays": False,
        "vignette": 0.34,
        "cameraShake": 0.0,
        "overlay": "none",
        "transition": "crossfade" if index % 3 == 0 else "cut",
    }

def direct_scene(scene, index, total, effect_slot=False):
    text = scene.get("text") or scene.get("narration_chunk") or ""
    w = _words(text)
    climax = bool(scene.get("isClimax") or scene.get("emphasis") == "climax")
    devotional = bool(w & {"krishna","shiva","ram","hanuman","कृष्ण","शिव","राम","हनुमान","मंदिर","पूजा","धर्म"})
    reveal = bool(w & {"रहस्य","सत्य","reveal","mystery","सच","चमत्कार","अंत","क्यों","क्योंकि","कैसे","लेकिन","अचानक","खुलासा"})
    question = "?" in text or bool(w & {"क्यों","कैसे","क्या","रहस्य","सच"})
    action = bool(w & {"भागा","दौड़ा","युद्ध","गिरा","उठा","पहुंचा","पहुंचे","देखा","मिला","खुला","crossed","walked","ran"})

    beat = (
        "hook" if index == 1 else
        "climax" if climax else
        "reveal" if reveal else
        "action" if action else
        "curiosity" if question else
        "divine" if devotional else
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
    if requested_sfx != "none":
        sfx = requested_sfx
    elif effect_slot and devotional and beat in {"hook", "reveal", "climax"}:
        sfx = "temple_bell"
    else:
        sfx = "none"

    prosody = build_prosody_map(text, beat=beat)
    animation = _animation_plan(index, total, beat, devotional, reveal, climax, action)
    voice_direction = _voice_direction(prosody, beat, text)

    return {
        "camera": camera,
        "mood": mood,
        "emotion": prosody["emotion"],
        "audioBeat": beat,
        "prosody": prosody,
        "voiceDirection": voice_direction,
        "animation": animation,
        "transition": animation["transition"],
        "emphasis": "climax" if climax else "normal",
        "soundEffect": sfx,
        "visual_priority": ["subject", "action", "environment"],
        "entertainmentBeat": beat,
        "patternBreak": beat in ("hook", "climax", "reveal", "action"),
        "effectReason": "explicit_scene_request" if requested_sfx != "none" else "story_beat" if sfx != "none" else "clean_audio",
        "transitionReason": "story_directed_animation",
        "director_version": 4,
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

        if plan["soundEffect"] != "none":
            if explicit or effect_slot:
                used_effects += 1
            else:
                plan["soundEffect"] = "none"
                plan["effectReason"] = "effect_budget_exhausted"

        # Respect explicit upstream director fields where present, but fill all
        # new V4 fields automatically for legacy Make payloads.
        existing_director = merged.get("director") if isinstance(merged.get("director"), dict) else {}
        if existing_director:
            plan.update({k: v for k, v in existing_director.items() if v is not None})
        merged["director"] = plan
        merged["soundEffect"] = plan["soundEffect"]
        merged["transition"] = plan["transition"]
        out.append(merged)

    return out
