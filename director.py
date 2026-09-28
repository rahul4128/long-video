"""Retention-aware deterministic AI Director.

The director deliberately uses fewer effects: a wrong SFX/transition hurts
retention more than a clean cut. Pattern breaks are reserved for real story
beats, reveals, action and climax.

Director v6 adds visual-beat editorial cues on top of the planning layer. It does NOT fetch media
or change the renderer yet. Each narration scene is divided into short,
ordered visual beats that later pipeline phases can use for stock retrieval,
semantic reranking and narration-synchronised editing.
"""
import math
import re

from storyteller import build_prosody_map

_EFFECTS = {"temple_bell", "shankh", "om_drone", "flute_swell", "none"}

_HINDI_STOPWORDS = {
    "और", "का", "की", "के", "में", "से", "को", "पर", "यह", "वह", "है", "था", "थे",
    "थी", "एक", "भी", "तो", "ही", "कि", "जब", "तब", "लेकिन", "या", "अपने", "अपनी",
    "अपने", "इस", "उस", "ने", "नहीं", "हो", "कर", "करके", "लिए", "तक", "जो", "क्या",
    "क्यों", "कैसे", "फिर", "अब", "आज", "इसी", "यही",
}
_ENGLISH_STOPWORDS = {
    "the", "a", "an", "and", "or", "with", "in", "on", "of", "for", "to", "at", "is",
    "are", "was", "were", "this", "that", "from", "into", "then", "when", "how", "why",
}

_ENTITY_TERMS = {
    "कृष्ण", "श्रीकृष्ण", "शिव", "महादेव", "राम", "हनुमान", "गणेश", "लक्ष्मी", "दुर्गा",
    "पार्वती", "विष्णु", "अर्जुन", "कर्ण", "राधा", "सीता", "रावण", "भीष्म", "द्रौपदी",
    "krishna", "shiva", "mahadev", "ram", "hanuman", "ganesh", "lakshmi", "durga",
    "parvati", "vishnu", "arjuna", "karna", "radha", "sita", "ravana", "bhishma",
}

_ACTION_TERMS = {
    "अर्पित", "चढ़ाया", "चढ़ाते", "डाला", "डालते", "बहाया", "पूजा", "प्रार्थना", "युद्ध",
    "लड़ा", "दौड़ा", "भागा", "चला", "चलते", "पहुंचा", "पहुंचे", "देखा", "देखते", "उठाया",
    "खोला", "खुला", "दिया", "देते", "बोला", "कहा", "सुनाया", "बैठा", "खड़ा", "झुका",
    "offering", "pouring", "walking", "running", "fighting", "praying", "worshipping",
    "speaking", "listening", "opening", "revealing", "holding", "lighting",
}

_PLACE_TERMS = {
    "मंदिर", "नदी", "घाट", "वन", "जंगल", "महल", "कुरुक्षेत्र", "युद्धभूमि", "घर", "आंगन",
    "पीपल", "वृक्ष", "पहाड़", "हिमालय", "गुफा", "स्वर्ग", "धरती", "temple", "river",
    "ghat", "forest", "palace", "kurukshetra", "battlefield", "mountain", "cave", "heaven",
}

_TIME_TERMS = {
    "सुबह", "प्रातः", "भोर", "सूर्योदय", "दोपहर", "शाम", "संध्या", "रात", "अमावस्या",
    "पूर्णिमा", "प्राचीन", "आज", "तभी", "अचानक", "dawn", "sunrise", "morning", "evening",
    "sunset", "night", "ancient", "today",
}

_SHOT_TYPES = ("wide", "medium", "close_up", "detail", "atmosphere")
_CAMERA_BY_SHOT = {
    "wide": "slow_push_in",
    "medium": "pan_right",
    "close_up": "slow_push_in",
    "detail": "pan_left",
    "atmosphere": "slow_push_in",
}


def _tokens(text):
    return re.findall(r"[\w\u0900-\u097F'’-]+", (text or "").lower())


def _words(text):
    return set(_tokens(text))


def _clean_terms(text):
    out = []
    seen = set()
    for token in _tokens(text):
        if len(token) < 3 or token in _HINDI_STOPWORDS or token in _ENGLISH_STOPWORDS:
            continue
        if token not in seen:
            seen.add(token)
            out.append(token)
    return out


def _first_match(tokens, vocabulary):
    for token in tokens:
        if token in vocabulary:
            return token
    return ""


def _scene_entities(scene):
    raw = scene.get("visualEntities") or scene.get("visual_entities") or []
    if isinstance(raw, str):
        raw = [raw]
    return [str(v).strip() for v in raw if str(v).strip()]


def _short_phrase(words, max_words=8):
    words = [w for w in words if w]
    if not words:
        return ""
    value = " ".join(words[:max_words])
    return value + ("…" if len(words) > max_words else "")


def _segment_words(words, count):
    """Split words into count balanced, ordered chunks.

    The word-index boundaries are intentionally deterministic. Phase 2 can
    later replace these estimated boundaries with real TTS word timestamps
    without changing the visual-beat schema.
    """
    if not words:
        return []
    count = max(1, min(count, len(words)))
    chunks = []
    start = 0
    for i in range(count):
        remaining_words = len(words) - start
        remaining_chunks = count - i
        size = int(math.ceil(remaining_words / remaining_chunks))
        end = min(len(words), start + size)
        chunks.append((start, end, words[start:end]))
        start = end
    return chunks


def _visual_beat_count(word_count, format_name):
    if word_count <= 0:
        return 0

    # At ~2.5 spoken words/sec, a normal 60-75 word long scene is ~24-30s.
    # A 5-6 second visual rhythm therefore naturally produces 4-5 beats.
    estimated_seconds = word_count / 2.5

    if format_name == "shorts":
        return max(1, min(3, round(estimated_seconds / 3.8)))

    if word_count >= 18:
        return max(3, min(5, round(estimated_seconds / 5.5)))
    if word_count >= 10:
        return 2
    return 1


def _build_queries(scene, beat_words, subject, action, setting):
    base = str(scene.get("videoSearchQuery") or scene.get("video_search_query") or "").strip()
    prompt = str(scene.get("imagePrompt") or scene.get("image_prompt") or "").strip()

    beat_terms = _clean_terms(" ".join(beat_words))[:5]
    prompt_terms = _clean_terms(prompt)[:3]

    # Beat-specific intent comes first. The scene-wide videoSearchQuery is
    # deliberately last: using it first for every beat makes a 25-second
    # narration scene search the same broad phrase repeatedly and defeats
    # the point of narration-aware visual direction.
    candidates = [
        " ".join(v for v in (subject, action, setting) if v),
        " ".join((beat_terms[:3] + prompt_terms[:2])),
        " ".join(beat_terms),
        base,
    ]

    queries = []
    seen = set()
    for q in candidates:
        q = re.sub(r"\s+", " ", q).strip(" ,.-")
        if not q:
            continue
        key = q.lower()
        if key in seen:
            continue
        seen.add(key)
        queries.append(q)
        if len(queries) == 4:
            break

    return queries



_STYLE_ANCIENT_TERMS = {
    "ancient", "vedic", "mythological", "mahabharata", "ramayana", "kurukshetra",
    "प्राचीन", "वैदिक", "महाभारत", "रामायण", "कुरुक्षेत्र", "राजमहल", "युद्धभूमि",
}
_STYLE_MODERN_TERMS = {
    "modern", "city", "urban", "office", "car", "phone", "contemporary",
    "आधुनिक", "शहर", "कार", "फोन", "ऑफिस",
}
_STYLE_STYLIZED_TERMS = {
    "illustration", "painting", "artwork", "anime", "cartoon", "3d render",
    "digital art", "watercolor", "चित्र", "पेंटिंग", "कार्टून",
}
_STYLE_NIGHT_TERMS = {
    "night", "moon", "moonlight", "dark", "midnight", "रात", "चांद", "चाँद", "अंधेरा",
}
_STYLE_DAWN_TERMS = {
    "dawn", "sunrise", "golden hour", "morning", "भोर", "सूर्योदय", "प्रातः", "सुबह",
}


def _visual_style_profile(scene, mood):
    """Create one restrained visual language shared by all beats in a scene.

    This profile is deterministic and can be evaluated independently by
    parallel asset workers. It gives Phase 7 an episode/scene style target
    without serialising scene generation.
    """
    text = " ".join([
        str(scene.get("text") or scene.get("narration_chunk") or ""),
        str(scene.get("imagePrompt") or scene.get("image_prompt") or ""),
        str(scene.get("videoSearchQuery") or scene.get("video_search_query") or ""),
    ]).lower()

    realism = (
        "stylized"
        if any(term in text for term in _STYLE_STYLIZED_TERMS)
        else "cinematic_realism"
    )

    if any(term in text for term in _STYLE_ANCIENT_TERMS):
        period = "ancient"
    elif any(term in text for term in _STYLE_MODERN_TERMS):
        period = "modern"
    else:
        period = "timeless"

    if any(term in text for term in _STYLE_NIGHT_TERMS):
        lighting = "low_key_night"
    elif any(term in text for term in _STYLE_DAWN_TERMS):
        lighting = "warm_golden"
    elif mood in {"devotional", "revelation", "climax"}:
        lighting = "warm_golden"
    else:
        lighting = "natural_cinematic"

    palette = (
        "warm_gold_earth"
        if mood in {"devotional", "revelation", "climax"}
        else "natural_earth"
    )
    entities = _scene_entities(scene)
    entity_anchor = entities[0] if entities else ""

    return {
        "realism": realism,
        "period": period,
        "lighting": lighting,
        "palette": palette,
        "entityAnchor": entity_anchor,
    }


def plan_visual_beats(scene, mood, camera, pattern_break, format_name="long"):
    """Return ordered narration-aware visual beats for one scene.

    Phase 1 is intentionally planning-only: these beats are persisted in the
    scene/director metadata but the existing stock/image engine keeps using
    its old scene-level query until Phase 2/3 explicitly opts into this data.
    """
    text = scene.get("text") or scene.get("narration_chunk") or ""
    words = _tokens(text)
    if not words:
        return []

    beat_count = _visual_beat_count(len(words), format_name)
    chunks = _segment_words(words, beat_count)
    scene_entities = _scene_entities(scene)
    scene_terms = _clean_terms(
        " ".join([
            str(scene.get("videoSearchQuery") or ""),
            str(scene.get("imagePrompt") or ""),
        ])
    )

    estimated_scene_seconds = max(2.5, len(words) / 2.5)
    style_profile = _visual_style_profile(scene, mood)
    beats = []

    for beat_index, (word_start, word_end, beat_words) in enumerate(chunks, 1):
        beat_tokens = [w.lower() for w in beat_words]
        entity = next(
            (e for e in scene_entities if any(part.lower() in beat_tokens for part in _tokens(e))),
            "",
        )
        if not entity:
            entity = _first_match(beat_tokens, _ENTITY_TERMS)
        if not entity and scene_entities:
            entity = scene_entities[0]

        action = _first_match(beat_tokens, _ACTION_TERMS)
        setting = _first_match(beat_tokens, _PLACE_TERMS)
        if not setting:
            setting = _first_match(scene_terms, _PLACE_TERMS)

        time_context = _first_match(beat_tokens, _TIME_TERMS)
        if not time_context:
            time_context = _first_match(scene_terms, _TIME_TERMS)

        content_terms = _clean_terms(" ".join(beat_words))
        subject = entity or " ".join(content_terms[:3]) or "devotional story detail"
        action_label = action or ("reveal" if pattern_break in {"reveal", "climax"} else "narrative moment")
        setting_label = setting or "story environment"
        time_label = time_context or "unspecified"

        shot_type = _SHOT_TYPES[(beat_index - 1) % len(_SHOT_TYPES)]
        if beat_index == len(chunks) and len(chunks) >= 4 and pattern_break in {"reveal", "climax"}:
            shot_type = "close_up"

        beat_word_count = max(1, word_end - word_start)
        duration = round(estimated_scene_seconds * beat_word_count / len(words), 1)
        duration = max(2.5 if format_name == "shorts" else 4.0, duration)
        duration = min(5.5 if format_name == "shorts" else 7.0, duration)

        transition = "cut"
        if beat_index > 1 and mood == "devotional" and beat_index == len(chunks):
            transition = "crossfade"
        if pattern_break in {"reveal", "climax"} and beat_index == len(chunks):
            transition = "blur_cut"

        beats.append({
            "beatIndex": beat_index,
            "narrationCue": _short_phrase(beat_words, 8),
            "narrationText": " ".join(beat_words),
            "wordStart": word_start,
            "wordEnd": word_end,
            "durationTarget": duration,
            "subject": subject,
            "action": action_label,
            "setting": setting_label,
            "mood": mood,
            "time": time_label,
            "shotType": shot_type,
            "cameraMotion": _CAMERA_BY_SHOT.get(shot_type, camera or "slow_push_in"),
            "queries": _build_queries(scene, beat_words, subject, action, setting),
            "preferredMedia": "video" if action else "auto",
            "transition": transition,
            "styleProfile": dict(style_profile),
        })

    return beats



def _focus_beat_index(visual_beats, pattern_break):
    """Choose the one beat in a scene that deserves editorial emphasis."""
    if not visual_beats:
        return None
    if pattern_break in {"reveal", "climax"}:
        return len(visual_beats) - 1
    if pattern_break == "action":
        for i, beat in enumerate(visual_beats):
            if beat.get("action") not in (None, "", "narrative moment", "reveal"):
                return i
        return min(1, len(visual_beats) - 1)
    if pattern_break == "hook":
        return 0
    return None


def _emphasis_phrase(beat, max_words=4):
    """Return a compact narration-derived phrase for motion typography."""
    text = str(beat.get("narrationText") or "")
    raw_words = re.findall(r"[\w\u0900-\u097F'’-]+", text)
    meaningful = []
    for word in raw_words:
        token = word.lower()
        if (
            len(token) >= 2
            and token not in _HINDI_STOPWORDS
            and token not in _ENGLISH_STOPWORDS
        ):
            meaningful.append(word)
    chosen = meaningful[:max_words] or raw_words[:max_words]
    return " ".join(chosen).strip()


def _apply_editorial_beat_cues(plan, format_name, typography_allowed=True):
    """Attach at most one typography cue and one meaningful SFX cue per scene.

    Hook typography is intentionally skipped because HookOverlay already owns
    the first 1.8 seconds. SFX can still accompany the hook if the director
    explicitly budgeted one.
    """
    beats = plan.get("visualBeats") or []
    pattern = plan.get("entertainmentBeat") or "establish"
    focus_index = _focus_beat_index(beats, pattern)

    if focus_index is not None and 0 <= focus_index < len(beats):
        focus = beats[focus_index]

        if typography_allowed and pattern in {"reveal", "climax", "action"}:
            phrase = _emphasis_phrase(focus, max_words=4 if format_name == "long" else 3)
            if phrase:
                focus["emphasisText"] = phrase
                focus["emphasisStyle"] = pattern
                focus["emphasisDurationSeconds"] = 1.45 if format_name == "shorts" else 1.7

    effect = plan.get("soundEffect") or "none"
    if effect != "none" and beats:
        # Normally SFX follows the editorial focus beat. For an explicit SFX
        # request on an establish/curiosity scene, keep the request instead of
        # silently dropping it: use the final beat for curiosity, otherwise
        # the opening beat.
        sfx_index = focus_index
        if sfx_index is None:
            sfx_index = len(beats) - 1 if pattern == "curiosity" else 0
        sfx_focus = beats[max(0, min(len(beats) - 1, sfx_index))]
        sfx_focus["soundEffect"] = effect
        sfx_focus["soundEffectVolume"] = 0.14 if format_name == "shorts" else 0.17
        sfx_focus["soundEffectReason"] = plan.get("effectReason", "story_beat")

    return beats


def direct_scene(scene, index, total, effect_slot=False, format_name="long"):
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

    if requested_sfx != "none":
        sfx = requested_sfx
    elif effect_slot and devotional and pattern_break in {"hook", "reveal", "climax"}:
        sfx = "temple_bell"
    else:
        sfx = "none"

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
    visual_beats = plan_visual_beats(
        scene,
        mood=mood,
        camera=camera,
        pattern_break=pattern_break,
        format_name=format_name,
    )

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
        "visualBeats": visual_beats,
        "visualBeatCount": len(visual_beats),
        "visualStyleProfile": (
            dict(visual_beats[0].get("styleProfile") or {})
            if visual_beats else _visual_style_profile(scene, mood)
        ),
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
        "director_version": 7,
    }


def enrich_scenes(scenes, format_name="long"):
    total = len(scenes)
    out = []
    effect_budget = max(1, min(3, round(total / 4)))
    # Motion typography is deliberately rarer than ordinary captions:
    # roughly four emphasis moments in a long episode, two in a Short.
    typography_budget = min(total, 2 if format_name == "shorts" else 4)
    used_effects = 0
    used_typography = 0

    for i, scene in enumerate(scenes, 1):
        merged = dict(scene)
        explicit = merged.get("soundEffect") not in (None, "", "none")
        effect_slot = used_effects < effect_budget
        plan = direct_scene(
            merged,
            i,
            total,
            effect_slot=effect_slot,
            format_name=format_name,
        )

        if plan["soundEffect"] != "none":
            if explicit or effect_slot:
                used_effects += 1
            else:
                plan["soundEffect"] = "none"
                plan["effectReason"] = "effect_budget_exhausted"

        typography_allowed = (
            used_typography < typography_budget
            and plan.get("entertainmentBeat") in {"reveal", "climax", "action"}
        )
        plan["visualBeats"] = _apply_editorial_beat_cues(
            plan,
            format_name=format_name,
            typography_allowed=typography_allowed,
        )
        if any(b.get("emphasisText") for b in plan["visualBeats"]):
            used_typography += 1

        merged["director"] = plan
        merged["visualBeats"] = plan["visualBeats"]

        # Phase 6 moves meaningful scene SFX to the exact narration beat.
        # Keep the director's requested effect in plan["soundEffect"] for
        # auditability, but suppress the legacy scene-start playback.
        merged["soundEffect"] = "none"
        merged["transition"] = plan["transition"]
        out.append(merged)

    return out

