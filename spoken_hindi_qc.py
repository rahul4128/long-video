"""Pre-TTS conversational Hindi QA without rewriting scripture, names or claims.

Make's language review is the primary editor. This local check is a deterministic
safety net: it measures long spoken phrases, written-only vocabulary, and
unexplained technical terms. It does NOT alter TTS scripts (which would
invalidate factual review and subtitles).
"""
import json
import os
from pathlib import Path
import re

FORMAL = {
    "अतएव": "इसलिए", "तथापि": "फिर भी", "किंतु": "लेकिन",
    "परंतु": "लेकिन", "यद्यपि": "हालाँकि", "फलस्वरूप": "इसका नतीजा",
    "उपर्युक्त": "ऊपर बताई", "निम्नलिखित": "ये बातें",
    "अत्यंत": "बहुत", "प्रतिपादित": "बताया", "तदुपरांत": "उसके बाद",
    "अनिवार्यतः": "ज़रूर", "प्रायः": "अक्सर",
    "अतः": "इसलिए", "पश्चात": "इसके बाद",
    "परिणामस्वरूप": "इस वजह से", "कदाचित": "शायद",
    "तत्पश्चात": "फिर", "वस्तुतः": "असल में",
    "सर्वप्रथम": "सबसे पहले", "अवगत": "पता",
}
CONCEPTS = ("निष्काम कर्म", "अहंकार", "मोक्ष", "तिथि", "मुहूर्त", "संकल्प",
            "प्रदोष", "अभिषेक", "अर्घ्य", "उपवास", "परिक्रमा")
# Names, chants and scripture can contain necessary complex words.
WORD_RE = re.compile(r"[\u0900-\u097f]+(?:[-\u0900-\u097f]+)*")
SENTENCE_SPLIT = re.compile(r"[।!?]+|\n+")


def assess_text(text, kind="long", scene=1):
    text = str(text or "").strip()
    sentences = [s.strip() for s in SENTENCE_SPLIT.split(text) if s.strip()]
    words = WORD_RE.findall(text)
    flags = []
    long_lengths = []
    for sentence in sentences:
        count = len(WORD_RE.findall(sentence))
        if count > 24:
            flags.append({"type": "long_spoken_sentence", "words": count})
            long_lengths.append(count)
    formal_found = sorted(word for word in FORMAL if re.search(
        r"(?<![\u0900-\u097f])" + re.escape(word) + r"(?![\u0900-\u097f])", text))
    if formal_found:
        flags.append({"type": "written_only_vocabulary", "terms": formal_found[:10]})
    unexplained = []
    for concept in CONCEPTS:
        if concept not in text:
            continue
        # A concept alone is not a failure: we flag only adjacent explanatory
        # wording as a review opportunity for non-expert viewers.
        start = text.index(concept)
        around = text[max(0,start-10):start+len(concept)+100]
        if not any(x in around for x in ("मतलब", "यानी", "अर्थ", "का मतलब", "समझ", "कहते", "इसे")):
            unexplained.append(concept)
    if unexplained:
        flags.append({"type": "religious_term_needs_simple_explanation",
                      "terms": unexplained[:7]})
    hard = bool(any(item["type"] == "long_spoken_sentence" and item["words"] > 47
                    for item in flags))
    if len(words) > 25 and len(formal_found) >= 4:
        hard = True
    return {"format":kind, "scene":scene, "wordCount":len(words),
            "sentenceCount":len(sentences), "longestSentenceWords":max(
                (len(WORD_RE.findall(s)) for s in sentences), default=0),
            "flags":flags,"severe":hard}


def assess_scenes(long_scenes, shorts_scenes, report_path="out/spoken_hindi_report.json",
                  strict=None):
    strict = (os.getenv("SPOKEN_HINDI_STRICT","false").lower() == "true") if strict is None else bool(strict)
    results = []
    for fmt, scenes in (("long",long_scenes),("shorts",shorts_scenes)):
        for i,scene in enumerate(scenes,1):
            results.append(assess_text(scene.get("text") or scene.get("narration_chunk") or "",
                                       fmt,scene.get("scene_number") or i))
    severe = [r for r in results if r["severe"]]
    report = {"version":1, "status":"failed" if severe and strict else
              "review" if any(r["flags"] for r in results) else "clear",
              "strict":strict, "severeScenes":len(severe),
              "notice":"Spoken Hindi QC checks readability only; preserve scripture, proper names, source meaning and TTS-subtitle sync.",
              "scenes":results}
    dest = Path(report_path)
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    if strict and severe:
        raise ValueError("Hindi narration contains extremely long or formal sentences; improve Make script first")
    return report
