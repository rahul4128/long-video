"""Hindi storyteller text preparation and prosody planning.

Keeps the original words intact for subtitles while adding restrained
performance punctuation, emphasis cues, and pronunciation-aware metadata.
The goal is conversational narration rather than perfectly uniform TTS.
"""
import re

# Words/phrases that benefit from a tiny performance cue. We do not replace
# the words, because the original narration must remain subtitle-safe.
PRONUNCIATION_DICTIONARY = {
    "कृष्ण": {"group": "divine", "slow": 0.97},
    "शिव": {"group": "divine", "slow": 0.97},
    "राम": {"group": "divine", "slow": 0.97},
    "हनुमान": {"group": "divine", "slow": 0.96},
    "नरसिंह": {"group": "divine", "slow": 0.95},
    "महिषासुर": {"group": "mythology", "slow": 0.95},
    "कुरुक्षेत्र": {"group": "place", "slow": 0.96},
    "द्वारका": {"group": "place", "slow": 0.97},
    "ऋषि": {"group": "mythology", "slow": 0.96},
    "क्षत्रिय": {"group": "mythology", "slow": 0.96},
    "त्रिशूल": {"group": "object", "slow": 0.97},
    "सुदर्शन": {"group": "object", "slow": 0.95},
    "महाभारत": {"group": "epic", "slow": 0.97},
    "रामायण": {"group": "epic", "slow": 0.97},
    "भगवद्गीता": {"group": "epic", "slow": 0.97},
}

EMPHASIS_PHRASES = (
    "असल में", "यही वजह", "सबसे बड़ा", "पहली बार", "असली कारण",
    "सच्चाई", "सच यह है", "ध्यान दीजिए", "सोचिए", "क्यों", "कैसे",
    "लेकिन", "और यहीं से", "अचानक", "रहस्य", "खुलासा",
)

def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())

def _has_marker(text: str, marker: str) -> bool:
    return marker in text

def prepare_storyteller_text(text: str) -> str:
    """Add restrained conversational punctuation without changing words."""
    text = _normalize(text)
    if not text:
        return text

    # Normalize punctuation first.
    text = re.sub(r"[.]{2,}", "…", text)
    text = re.sub(r"…{2,}", "…", text)
    text = re.sub(r"\s*—\s*", " — ", text)
    text = re.sub(r"\s*,\s*", ", ", text)

    # Conversational connectors get a small breath. Limit the number of
    # inserted cues so the narration never sounds artificially chopped up.
    cue_count = 0
    replacements = (
        (r"\b(और यहीं से)\b", r"\1—"),
        (r"\b(लेकिन)\b", r"\1…"),
        (r"\b(असल में)\b", r"\1—"),
        (r"\b(सच यह है)\b", r"\1—"),
        (r"\b(सोचिए)\b", r"\1…"),
    )
    for pattern, replacement in replacements:
        if cue_count >= 2:
            break
        if re.search(pattern, text):
            updated = re.sub(pattern, replacement, text, count=1)
            if updated != text:
                text = updated
                cue_count += 1

    # Long clauses sound less synthetic when a natural conjunction gets a
    # comma. Never split a sentence just because it is long.
    for conjunction in (" क्योंकि ", " इसलिए ", " जबकि ", " और "):
        if len(text.split()) >= 22 and conjunction in text and "," not in text:
            text = text.replace(conjunction, "," + conjunction, 1)
            break

    return re.sub(r"\s{2,}", " ", text).strip()

def build_prosody_map(text: str, beat: str = "") -> dict:
    """Return machine-readable storytelling cues for the TTS layer."""
    text = _normalize(text)
    lower = text.lower()

    if beat in {"hook", "curiosity"} or "?" in text:
        emotion = "curiosity"
        speed = 0.94
        pause = 0.24
    elif beat in {"climax", "reveal"} or any(x in lower for x in ("अचानक", "खुलासा", "सच्चाई", "रहस्य")):
        emotion = "reveal"
        speed = 0.90
        pause = 0.30
    elif beat == "action" or any(x in lower for x in ("युद्ध", "दौड़ा", "भागा", "गिरा", "उठा")):
        emotion = "action"
        speed = 1.02
        pause = 0.12
    elif beat == "divine" or any(x in text for x in ("कृष्ण", "शिव", "राम", "हनुमान", "मंदिर", "पूजा")):
        emotion = "divine"
        speed = 0.96
        pause = 0.22
    else:
        emotion = "conversational"
        speed = 0.98
        pause = 0.16

    emphasis = [p for p in EMPHASIS_PHRASES if p in text][:3]
    pronunciation_hits = [
        {"text": word, **meta}
        for word, meta in PRONUNCIATION_DICTIONARY.items()
        if word in text
    ]
    return {
        "emotion": emotion,
        "speed": speed,
        "pause_after": pause,
        "emphasis": emphasis,
        "pronunciation_hits": pronunciation_hits,
        "storyteller_version": 1,
    }

def apply_prosody_map(text: str, prosody: dict | None = None) -> str:
    """Add only a small amount of emphasis punctuation from a prosody map."""
    text = prepare_storyteller_text(text)
    if not prosody:
        return text

    emphasis = prosody.get("emphasis") or []
    for phrase in emphasis[:2]:
        if phrase in text and phrase not in {"क्यों", "कैसे"}:
            # Avoid stacking punctuation if the phrase was already cued.
            if not re.search(re.escape(phrase) + r"[…—]", text):
                text = text.replace(phrase, phrase + "…", 1)
    return re.sub(r"\.{2,}", "…", text).strip()
