"""Helpers that keep every viewer-facing string Hindi (Devanagari).

The render pipeline must never show or speak Roman/English words: YouTube
viewers of this channel read and listen in Hindi, and Latin-script words both
look out of place on screen and make the Hindi TTS voice switch accent
mid-sentence (a big part of the "robotic" feel).
"""
import re

LATIN_WORD = re.compile(r"[A-Za-z][A-Za-z'’\-]*")
DEVANAGARI = re.compile(r"[ऀ-ॿ]")

# Common English/Hinglish words that slip into scripts -> Devanagari spelling
# that a Hindi voice pronounces naturally.
LOANWORDS = {
    "subscribe": "सब्सक्राइब", "like": "लाइक", "share": "शेयर", "comment": "कमेंट",
    "channel": "चैनल", "video": "वीडियो", "videos": "वीडियो", "short": "शॉर्ट",
    "shorts": "शॉर्ट्स", "please": "प्लीज़", "ok": "ओके", "okay": "ओके",
    "tension": "टेंशन", "stress": "स्ट्रेस", "exam": "एग्ज़ाम", "interview": "इंटरव्यू",
    "job": "जॉब", "office": "ऑफिस", "phone": "फ़ोन", "mobile": "मोबाइल",
    "science": "साइंस", "power": "पावर", "energy": "एनर्जी", "mystery": "रहस्य",
    "secret": "रहस्य", "story": "कहानी", "power-full": "पावरफुल", "powerful": "पावरफुल",
    "ka": "का", "ki": "की", "ke": "के", "hai": "है", "hain": "हैं", "aur": "और",
    "raaz": "राज़", "katha": "कथा", "kahani": "कहानी", "rahasya": "रहस्य",
    "vrat": "व्रत", "puja": "पूजा", "mandir": "मंदिर", "bhagwan": "भगवान",
    "prasad": "प्रसाद", "pitru": "पितृ", "pitra": "पितृ", "paksha": "पक्ष", "shraddha": "श्राद्ध",
    "shradh": "श्राद्ध", "tarpan": "तर्पण", "pind": "पिंड", "daan": "दान", "gaya": "गया",
    "karna": "कर्ण", "bhishma": "भीष्म", "krishna": "कृष्ण", "ram": "राम", "rama": "राम",
    "sita": "सीता", "shiv": "शिव", "shiva": "शिव", "mahadev": "महादेव", "ganesh": "गणेश",
    "ganesha": "गणेश", "hanuman": "हनुमान", "vishnu": "विष्णु", "lakshmi": "लक्ष्मी",
    "durga": "दुर्गा", "navratri": "नवरात्रि", "diwali": "दिवाली", "dussehra": "दशहरा",
    "amavasya": "अमावस्या", "purnima": "पूर्णिमा", "ekadashi": "एकादशी", "mahabharat": "महाभारत",
    "mahabharata": "महाभारत", "ramayan": "रामायण", "ramayana": "रामायण", "gita": "गीता",
    "satyanarayan": "सत्यनारायण", "bhadrapada": "भाद्रपद", "garuda": "गरुड़", "purana": "पुराण",
    "yamraj": "यमराज", "kauwa": "कौवा", "kaua": "कौवा", "ghoshna": "घोषणा", "pehli": "पहली",
    "shuru": "शुरू", "hone": "होने", "wala": "वाला", "wali": "वाली", "kya": "क्या", "kyon": "क्यों",
    "kyu": "क्यों", "kaise": "कैसे", "sach": "सच", "raasta": "रास्ता", "vajah": "वजह", "dikkat": "दिक्कत",
    "the": "", "a": "", "an": "", "of": "", "and": "और", "in": "में", "is": "",
}


def _transliterate_unknown(word: str) -> str:
    """Best-effort Roman -> Devanagari for words not in LOANWORDS."""
    try:
        from indic_transliteration import sanscript
        w = word.lower().replace("ksh", "kSh").replace("aa", "A").replace("ee", "I").replace("oo", "U")
        out = sanscript.transliterate(w, sanscript.ITRANS, sanscript.DEVANAGARI)
        return out.rstrip("\u094d")  # drop a dangling halant
    except Exception:
        return ""


def has_latin(text: str) -> bool:
    return bool(LATIN_WORD.search(text or ""))


def devanagari_ratio(text: str) -> float:
    letters = [c for c in (text or "") if c.isalpha()]
    if not letters:
        return 0.0
    return sum(1 for c in letters if DEVANAGARI.match(c)) / len(letters)


def to_spoken_hindi(text: str) -> str:
    """Replace known Latin words with Devanagari; drop the rest for speech.

    Used only for the TTS input (subtitles use hindi_display_text below) so the
    Hindi voice never has to pronounce a Roman word.
    """
    def repl(match):
        word = match.group(0)
        key = word.lower()
        if key in LOANWORDS:
            return LOANWORDS[key]
        return _transliterate_unknown(word)
    out = LATIN_WORD.sub(repl, text or "")
    out = re.sub(r"\(\s*\)", "", out)
    return re.sub(r"\s{2,}", " ", out).strip()


def hindi_display_text(text: str) -> str:
    """Same as to_spoken_hindi, used for on-screen captions/overlays."""
    return to_spoken_hindi(text)


def pick_hindi(*candidates: str, max_words: int = 0) -> str:
    """Return the first candidate that is mostly Devanagari (cleaned)."""
    ordered = [c for c in candidates if c and not has_latin(c)] + [c for c in candidates if c and has_latin(c)]
    for cand in ordered:
        cand = (cand or "").strip()
        if not cand:
            continue
        cleaned = to_spoken_hindi(cand) if has_latin(cand) else cand
        if cleaned and devanagari_ratio(cleaned) >= 0.8:
            if max_words:
                cleaned = " ".join(cleaned.split()[:max_words])
            return cleaned
    return ""


# Words in image prompts that make FLUX paint (usually English) lettering.
_TEXT_TRIGGERS = re.compile(
    r"\b(thumbnail|poster|title|headline|caption|text|typography|lettering|"
    r"logo|banner|sign|signage|label|words?|quote|subtitle|watermark)\b",
    re.IGNORECASE,
)

NO_TEXT_PREFIX = "text-free artwork, no letters, no words, no writing, no signage, no watermark. "


def text_free_prompt(prompt: str) -> str:
    """Strip lettering triggers and put the no-text instruction FIRST.

    It must come first because the image APIs truncate long prompts, which is
    why a trailing 'no text' was never reaching the model.
    """
    clean = _TEXT_TRIGGERS.sub("", (prompt or "").replace("\n", " "))
    clean = re.sub(r"\s{2,}", " ", clean).strip(" ,.")
    return NO_TEXT_PREFIX + clean