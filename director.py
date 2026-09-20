"""Deterministic AI-Director-style scene planning layer.

It converts incoming scene JSON into production metadata: camera movement,
shot transitions, emphasis, mood and SFX hints. It is intentionally provider
agnostic so Make.com can later replace/augment it with an LLM director.
"""
import re
from storyteller import build_prosody_map

def _words(text):
    return set(re.findall(r"[\w\u0900-\u097F]+", (text or "").lower()))

def direct_scene(scene, index, total):
    text = scene.get("text") or scene.get("narration_chunk") or ""
    w = _words(text)
    climax = bool(scene.get("isClimax") or scene.get("emphasis") == "climax")
    devotional = bool(w & {"krishna","shiva","ram","hanuman","कृष्ण","शिव","राम","हनुमान","मंदिर","पूजा","धर्म"})
    reveal = bool(w & {"रहस्य","सत्य","reveal","mystery","सच","चमत्कार","अंत","क्यों","क्योंकि","कैसे","लेकिन","अचानक"})
    question = bool("?" in text or "?" in text or w & {"क्यों","कैसे","क्या","रहस्य","सच"})
    action = bool(w & {"भागा","दौड़ा","युद्ध","गिरा","उठा","पहुंचा","पहुंचे","देखा","मिला","खुला","crossed","walked","ran"})
    pattern_break = "hook" if index == 1 else "climax" if climax else "reveal" if reveal else "action" if action else "curiosity" if question else "establish"
    camera = "slow_push" if climax or reveal else ("pan_left" if index % 3 == 0 else "zoom_in" if index % 3 == 1 else "pan_right")
    mood = "climax" if climax else "revelation" if reveal else "devotional" if devotional else "cinematic"
    sfx = scene.get("soundEffect")
    if not sfx or sfx == "none":
        sfx = "temple_bell" if devotional and index % 4 == 0 else "none"
    beat = pattern_break
    prosody = build_prosody_map(text, beat=beat)
    return {
        "camera": camera,
        "mood": mood,
        "emotion": prosody["emotion"],
        "prosody": prosody,
        "transition": "blur_cut" if reveal or climax else ("crossfade" if index % 2 == 0 else "blur_cut"),
        "emphasis": "climax" if climax else "normal",
        "soundEffect": sfx,
        "visual_priority": ["subject","action","environment"],
        "entertainmentBeat": pattern_break,
        "patternBreak": pattern_break in ("hook","climax","reveal","action"),
        "director_version": 2,
    }

def enrich_scenes(scenes):
    total = len(scenes)
    out = []
    for i, scene in enumerate(scenes, 1):
        merged = dict(scene)
        plan = direct_scene(merged, i, total)
        merged["director"] = plan
        merged.setdefault("soundEffect", plan["soundEffect"])
        out.append(merged)
    return out
