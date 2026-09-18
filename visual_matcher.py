"""Strict visual-accuracy gate for devotional/mythological scenes.

Stock libraries are weak at identifying mythological entities. This module
therefore treats named deities/characters and age/gender attributes as hard
constraints: ambiguous generic footage is rejected and the caller falls back
to a purpose-built AI visual.

The matcher is intentionally metadata-only. It never downloads a candidate
just to discover that it is wrong, which keeps Make.com out of the media path
and reduces GitHub/stock bandwidth too.
"""
import re
from typing import Dict, List, Set, Tuple

ENTITY_ALIASES: Dict[str, Set[str]] = {
    "krishna": {"krishna", "कृष्ण", "shri krishna", "lord krishna", "kanha", "कान्हा", "kanhaiya", "कन्हैया", "gopal", "गोपाल", "govinda", "गोविंद"},
    "radha": {"radha", "राधा", "radharani", "राधारानी"},
    "shiva": {"shiva", "शिव", "mahadev", "महादेव", "bholenath", "भोलेनाथ", "rudra", "रुद्र"},
    "parvati": {"parvati", "पार्वती", "gauri", "गौरी"},
    "hanuman": {"hanuman", "हनुमान", "bajrang", "बजरंग", "anjaneya", "अंजनेय"},
    "rama": {"rama", "ram", "राम", "shri ram", "श्री राम", "raghu", "रघु"},
    "sita": {"sita", "सीता", "janaki", "जानकी"},
    "ganesha": {"ganesha", "गणेश", "ganapati", "गणपति", "vinayak", "विनायक"},
    "vishnu": {"vishnu", "विष्णु", "narayan", "नारायण"},
    "lakshmi": {"lakshmi", "लक्ष्मी", "mahalakshmi", "महालक्ष्मी"},
    "saraswati": {"saraswati", "सरस्वती", "sharada", "शारदा"},
    "durga": {"durga", "दुर्गा", "ambe", "अंबे", "chamunda", "चामुंडा"},
    "kartikeya": {"kartikeya", "कार्तिकेय", "murugan", "मुरुगन", "skanda", "स्कंद"},
    "arjuna": {"arjuna", "अर्जुन", "dhananjaya", "धनंजय"},
    "karna": {"karna", "कर्ण", "radheya", "राधेय"},
    "draupadi": {"draupadi", "द्रौपदी", "panchali", "पांचाली"},
    "bhishma": {"bhishma", "भीष्म", "devavrata", "देवव्रत"},
}

ATTRIBUTE_ALIASES = {
    "child": {"child", "kid", "boy", "bal", "बाल कृष्ण", "girl", "baby", "infant", "young", "toddler", "बाल", "बच्चा", "बालक", "किशोर", "कन्हैया"},
    "adult": {"adult", "man", "woman", "grown", "elder", "पुरुष", "महिला", "वयस्क"},
    "female": {"female", "woman", "girl", "mother", "स्त्री", "महिला", "नारी", "कन्या"},
    "male": {"male", "man", "boy", "पुरुष", "बालक"},
}

GENERIC_NEGATIVE_FOR_ENTITY = {
    "krishna": {"generic child", "random child", "boy", "girl", "human child", "generic man", "generic woman", "buddha", "buddhist"},
}

def _tokens(text: str) -> Set[str]:
    raw = re.findall(r"[A-Za-z][A-Za-z0-9']*|[\u0900-\u097F]+", (text or "").lower())
    return {x for x in raw if len(x) > 1}

def extract_visual_requirements(*texts: str) -> Dict[str, object]:
    joined = " ".join(str(t or "") for t in texts).lower()
    tokens = _tokens(joined)
    entities: List[str] = []
    attributes: List[str] = []
    for entity, aliases in ENTITY_ALIASES.items():
        if any(alias.lower() in joined for alias in aliases):
            entities.append(entity)
    for attr, aliases in ATTRIBUTE_ALIASES.items():
        if any(alias.lower() in joined for alias in aliases):
            attributes.append(attr)

    # "Bal Krishna / बाल कृष्ण / child Krishna" is a special strict compound.
    if "krishna" in entities and (
        any(x in joined for x in ("bal krishna", "बाल कृष्ण", "child krishna", "baby krishna", "infant krishna", "bal krishna", "कन्हैया", "बाल कृष्ण"))
        or "child" in attributes
    ):
        attributes.append("child")
    return {
        "entities": sorted(set(entities)),
        "attributes": sorted(set(attributes)),
        "strict": bool(entities),
        "tokens": tokens,
    }

def _has_entity_evidence(candidate_text: str, entity: str) -> bool:
    text = (candidate_text or "").lower()
    return any(alias.lower() in text for alias in ENTITY_ALIASES.get(entity, {entity}))

def _has_attribute_evidence(candidate_text: str, attribute: str) -> bool:
    text = (candidate_text or "").lower()
    return any(alias.lower() in text for alias in ATTRIBUTE_ALIASES.get(attribute, {attribute}))

def candidate_is_accurate(candidate_text: str, requirements: Dict[str, object]) -> Tuple[bool, str]:
    """Return (accepted, reason). Empty/weak metadata is rejected for strict scenes."""
    entities = requirements.get("entities", []) or []
    attributes = requirements.get("attributes", []) or []
    if not requirements.get("strict"):
        return True, "non-strict scene"

    text = (candidate_text or "").lower()
    if not text.strip():
        return False, "strict scene but candidate has no descriptive metadata"

    for entity in entities:
        if not _has_entity_evidence(text, entity):
            return False, f"missing entity evidence: {entity}"

    # Age/role attributes are hard constraints only when explicitly requested.
    for attr in attributes:
        if attr == "child" and not _has_attribute_evidence(text, attr):
            return False, "missing child-age evidence"
        if attr == "adult" and not _has_attribute_evidence(text, attr):
            return False, "missing adult-age evidence"
        if attr == "female" and not _has_attribute_evidence(text, attr):
            return False, "missing female evidence"
        if attr == "male" and not _has_attribute_evidence(text, attr):
            return False, "missing male evidence"

    for forbidden in GENERIC_NEGATIVE_FOR_ENTITY.get(entities[0], set()):
        if forbidden in text and not any(_has_entity_evidence(text, e) for e in entities):
            return False, f"generic/incorrect visual cue: {forbidden}"

    return True, "strict visual requirements satisfied"
