"""Fail-closed provenance checks for videos that *teach* physical actions.

Stock search text, CLIP scores and synthetic stills are not proof that a
specific dance/recipe/exercise technique is depicted accurately. General
cultural stories remain fully automatic. Precise lessons require externally
reviewed, file-hash-pinned video demonstrations before rendering or upload.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

GENERIC_STOCK_QUERIES = frozenset({
    "person", "people", "human", "hands", "hand", "dancer", "dancing",
    "man", "woman", "girl", "boy", "crowd", "face", "feet", "foot",
    "body", "person looking", "person walking", "people dancing",
})

_SKILLS = {
    "dance": ("गरबा", "डांडिया", "नृत्य", "नाच", "डांस", "garba",
              "dandiya", "dance", "dancing", "footwork", "choreograph"),
    "fitness": ("योग", "योगासन", "व्यायाम", "एक्सरसाइज", "workout",
                "yoga", "exercise", "stretching"),
    "cooking": ("रेसिपी", "पकाना", "बनाने की विधि", "recipe",
                "cook", "cooking", "baking"),
    "craft": ("क्राफ्ट", "पेपर क्राफ्ट", "diy", "handicraft",
              "craft tutorial", "origami"),
}
_INSTRUCTION = re.compile(
    r"स्टेप|सीख|सिख|कैसे (?:करें|बनाएं|बनाएँ|करे)|"
    r"फुटवर्क|कदम|विधि|रेसिपी|ट्यूटोरियल|"
    r"\bstep(?:s)?\b|\bhow to\b|\blearn\b|"
    r"\btutorial\b|\btechnique\b|\bexercise\b",
    flags=re.IGNORECASE,
)
_ACTION = re.compile(
    r"स्टेप|कदम|सीख|सिख|फुटवर्क|रेसिपी|विधि|"
    r"\bstep(?:s)?\b|\bfootwork\b|\bmove\b|"
    r"\bposture\b|\bpose\b|\btechnique\b|"
    r"\binstruction\b|\btutorial\b",
    flags=re.IGNORECASE,
)


def is_generic_stock_query(query: str) -> bool:
    """Exclude very broad queries, which repeatedly led to unrelated clips."""
    q = re.sub(r"\s+", " ", str(query or "").casefold()).strip()
    return q in GENERIC_STOCK_QUERIES


def detect_instructional_category(titles) -> str | None:
    """Return a category only when a title promises a hands-on lesson."""
    text = " ".join(str(x or "") for x in titles).casefold()
    if not _INSTRUCTION.search(text):
        return None
    for category, terms in _SKILLS.items():
        if any(term in text for term in terms):
            return category
    return None


def _instructional_scenes(scenes, category):
    """Identify narration scenes that actually promise/show technique."""
    for index, scene in enumerate(scenes, 1):
        speech = " ".join(str(scene.get(k) or "") for k in ("text", "narration_chunk"))
        if _ACTION.search(speech):
            yield index, scene


def validate_demonstration_evidence(titles, long_scenes, shorts_scenes, report,
                                    manifest_path, media_root) -> None:
    """Require independent human-reviewed hashes for all promised action beats.

    Provenance alone cannot establish motion semantics automatically; therefore
    it only accepts an explicit human-reviewed manifest tied to exact bytes,
    format, scene and named technique. Stock text alone can never pass.
    """
    category = detect_instructional_category(titles)
    if not category:
        return
    path = Path(manifest_path)
    if not path.is_file():
        raise ValueError(
            f"Precise {category} tutorial requires verified demonstration footage. "
            "Automatic stock/AI selection cannot prove exact steps. "
            "Provide a human-reviewed clip manifest or choose a cultural/story "
            "concept that does not claim to teach physical techniques."
        )
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError) as exc:
        raise ValueError("Instructional video manifest unreadable") from exc
    if not isinstance(manifest, dict) or manifest.get("version") != 1:
        raise ValueError("Instructional video manifest must use version 1")
    reviewed = manifest.get("reviewed_clips")
    if not isinstance(reviewed, list) or not reviewed:
        raise ValueError("Instructional video has no independently reviewed clips")
    clip_by_key = {}
    for entry in reviewed:
        if not isinstance(entry, dict):
            raise ValueError("Malformed reviewed clip")
        key = (entry.get("format"), entry.get("scene"), entry.get("file"))
        digest = entry.get("sha256")
        if (entry.get("category") != category or
                entry.get("human_reviewed") is not True or
                not entry.get("reviewer") or
                not entry.get("step_label") or
                not isinstance(digest, str) or
                not re.fullmatch(r"[0-9a-f]{64}", digest)):
            raise ValueError("Instructional clip missing explicit human-reviewed provenance")
        if key in clip_by_key:
            raise ValueError("Duplicate approved demonstration clip")
        clip_by_key[key] = entry

    root = Path(media_root).resolve()
    for kind, scenes in (("long", long_scenes), ("shorts", shorts_scenes)):
        instructional = list(_instructional_scenes(scenes, category))
        if not instructional:
            raise ValueError(f"{kind}: tutorial title but no actual instructional scenes")
        verified_labels = set()
        for scene_num, scene in instructional:
            ok = False
            for shot in scene.get("shots") or []:
                if shot.get("type") != "video":
                    continue
                name = shot.get("file")
                if not isinstance(name, str) or not name:
                    continue
                record = clip_by_key.get((kind, scene_num, name))
                if record is None:
                    continue
                media = (root / name).resolve()
                if not media.is_relative_to(root) or not media.is_file():
                    raise ValueError(f"{kind} scene {scene_num}: reviewed file missing")
                real_sha = hashlib.sha256(media.read_bytes()).hexdigest()
                if real_sha != record["sha256"]:
                    raise ValueError(f"{kind} scene {scene_num}: approved footage hash differs")
                verified_labels.add(record["step_label"].casefold().strip())
                ok = True
            if not ok:
                raise ValueError(
                    f"{kind} scene {scene_num}: narrated tutorial requires a "
                    "human-reviewed, SHA256-matched exact action clip; a generic "
                    "query, AI image or high selectionScore is insufficient"
                )
        if not verified_labels:
            raise ValueError(f"{kind}: no independently verified techniques present")
