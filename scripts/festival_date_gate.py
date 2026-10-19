"""Source-linked calendar consistency gate before paid narration / image generation.

This is a targeted deterministic consistency check, NOT a general fact checker.
It blocks unsupported date-relative claims for known events and records residual
human-review risks for location-dependent Hindu lunar-tithi observances.
"""
import json
from datetime import date, datetime, timedelta
from pathlib import Path
import re
from zoneinfo import ZoneInfo

CALENDAR = Path(__file__).resolve().parents[1] / "data" / "festival_routes_2026.json"
IST = ZoneInfo("Asia/Kolkata")

# Match named observances, not generic devotional language.
EVENT_PATTERNS = {
    "sharad-navratri-2026": r"नवरात्र[िी]|navratri",
    "vijayadashami-2026": r"विजयदशमी|दशहर[ाे]|vijayadashami|dussehra",
    "sharad-purnima-2026": r"शरद\s*पूर्णिमा|sharad\s*purnima",
    "karwa-chauth-2026": r"करवा\s*चौथ|करवा\s*चौथ|karwa\s*chauth",
    "ahoi-ashtami-2026": r"अहोई\s*अष्टमी|ahoi\s*ashtami",
    "diwali-2026": r"दीवाली|दिवाली|दीपावली|diwali|deepavali",
    "govardhan-2026": r"गोवर्धन|अन्नकूट|govardhan",
    "bhai-dooj-2026": r"भाई\s*दूज|भैया\s*दूज|bhai\s*dooj",
    "chhath-2026": r"छठ\s*(?:पूजा|पर्व)?|chhath",
    "tulsi-vivah-2026": r"तुलसी\s*विवाह|tulsi\s*vivah",
    "kartik-purnima-2026": r"कार्तिक\s*पूर्णिमा|kartik\s*purnima",
}


def _text_fields(story):
    seo = story.get("seo_metadata") or {}
    yield "long title", str(seo.get("long_video_title") or "")
    yield "Shorts title", str(seo.get("shorts_title") or "")
    yield "long description", str(seo.get("long_video_description") or seo.get("description") or "")
    yield "Shorts description", str(seo.get("shorts_description") or "")
    for kind in ("long_video", "shorts"):
        for i, scene in enumerate((story.get(kind) or {}).get("scenes") or [], 1):
            yield f"{kind} scene {i}", str(scene.get("text") or scene.get("narration_chunk") or "")
    for name in ("thumbnail", "shorts_thumbnail"):
        yield name, str((story.get(name) or {}).get("thumbnailText") or "")


def _relations(text, match):
    """Return nearby time claims relative to an event mention in natural Hindi."""
    left = text[max(0, match.start() - 42):match.start()]
    right = text[match.end():match.end() + 55]
    # Keep the nearest clause; don't borrow temporal words from a different event.
    left = re.split(r"[।!?;\n]", left)[-1]
    right = re.split(r"[।!?;\n]", right)[0]
    after = re.search(r"^\s*(?:के\s*)?बाद\b", right, re.I) or re.search(r"\bafter\b", right[:25], re.I)
    before = re.search(r"^\s*(?:से\s*)?पहले\b", right, re.I)
    relations = set()
    if after:
        relations.add("after")
    if before:
        relations.add("before")

    # "कल <event> है" and "<event> कल है"; कल थी means yesterday.
    future_pre = re.search(r"(?:कल|tomorrow)\s*(?:की|का|को|है|होगी|होगा|होगे)?\s*$", left, re.I)
    future_post = re.search(r"^\s*(?:कल|tomorrow)(?:\s+(?:है|होगी|होगा|को|मनाया|आएगी))?", right, re.I)
    yesterday = re.search(r"^\s*कल\s*(?:था|थी|मनाया\s*गया)\b", right)
    if yesterday:
        relations.add("yesterday")
    elif future_pre or future_post:
        relations.add("tomorrow")

    today_pre = re.search(r"(?:आज|today)\s*(?:ही|का|की|के|है|होगा|हो|मनाया)?\s*$", left, re.I)
    today_post = re.search(r"^\s*(?:आज|today)(?:\s|$)", right, re.I)
    if today_pre or today_post:
        relations.add("today")

    # "आज नवरात्रि का अंतिम दिन" / "नवरात्रि की नौवीं रात".
    if re.search(r"(?:आज|today).*?(?:नवरात्र[िी]|navratri)", left[-30:] + text[match.start():match.end()], re.I) and re.search(
        r"^\s*(?:का|की|के)?\s*(?:अंतिम|आखिरी|नौव[ीांँ]|नवम[ी]|9(?:वाँ|वां))\s*(?:दिन|रात)", right
    ):
        relations.add("last_day")
    return relations


def validate_festival_date_claims(story, *, publish_date=None, calendar_path=None):
    """Validate against calendar event dates and publication day (IST).

    Returns an auditable report. No API, billing, source fabrication or
    mutations. Caller must refuse render on report["ok"] == False.
    """
    if publish_date is None:
        publish_date = datetime.now(IST).date()
    elif isinstance(publish_date, str):
        publish_date = date.fromisoformat(publish_date)
    if not isinstance(publish_date, date):
        raise ValueError("publish_date must be an ISO 8601 date")

    path = Path(calendar_path) if calendar_path else CALENDAR
    doc = json.loads(path.read_text(encoding="utf-8"))
    if doc.get("timezone") != "Asia/Kolkata":
        raise ValueError("Festival calendar is not indexed in Asia/Kolkata")
    sources = {v["event"]: v for v in doc.get("sources", [])}
    issues, warnings, claims = [], [], []
    for location, text in _text_fields(story):
        for event_id, rx in EVENT_PATTERNS.items():
            found = list(re.finditer(rx, text, re.I))
            if not found:
                continue
            source = sources.get(event_id)
            for m in found:
                relations = _relations(text, m)
                if not relations:
                    continue
                if not source:
                    issues.append(f"{location}: {event_id} has a relative-date claim but no verified source calendar entry")
                    continue
                first = date.fromisoformat(source["from"])
                last = date.fromisoformat(source["to"])
                for relation in relations:
                    claims.append({"field": location, "event": event_id, "claim": relation})
                    if relation == "after" and publish_date <= last:
                        issues.append(f"{location}: 'after {event_id}' contradicts event ending {last} when publishing on {publish_date}")
                    elif relation == "before" and publish_date >= first:
                        issues.append(f"{location}: 'before {event_id}' contradicts event beginning {first} when publishing on {publish_date}")
                    elif relation == "today" and not first <= publish_date <= last:
                        issues.append(f"{location}: claims {event_id} is today, calendar says {first}..{last}, publish date {publish_date}")
                    elif relation == "tomorrow" and not first <= publish_date + timedelta(days=1) <= last:
                        issues.append(f"{location}: claims {event_id} is tomorrow, calendar says {first}..{last}, publish date {publish_date}")
                    elif relation == "yesterday" and not first <= publish_date - timedelta(days=1) <= last:
                        issues.append(f"{location}: claims {event_id} was yesterday, calendar says {first}..{last}, publish date {publish_date}")
                    elif relation == "last_day":
                        # End dates for Navratri and regional tithi may vary.
                        # Source proves a span but not the deity/day index.
                        issues.append(f"{location}: exact Navratri final day/tithi requires separately verified local Panchang evidence")
    if claims:
        warnings.append("Date-relative copy must be rechecked if publication moves to a different day")
    if publish_date > date.fromisoformat(doc["coverage_end"]):
        warnings.append("Publication is beyond finite verified calendar coverage")
    return {
        "ok": not issues,
        "publish_date_ist": publish_date.isoformat(),
        "calendar_checked_at": doc.get("checked_at"),
        "issues": sorted(set(issues)),
        "warnings": warnings,
        "relative_claims": claims,
        "verification_scope": "source-linked event dates; local tithi and muhurats require editorial review",
    }
