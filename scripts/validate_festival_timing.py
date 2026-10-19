#!/usr/bin/env python3
"""Fail-closed, offline checks for date-sensitive festival copy before paid rendering.

This is NOT a religious fact checker. It validates explicit relative-date claims
against a SOURCE-LINKED and finite calendar, using the proposed publication date
(IST), not a model's self-reported PASS. Evergreen episodes are unaffected.
"""
import argparse
from datetime import date, datetime, timedelta
import json
import os
from pathlib import Path
import re
import sys
from zoneinfo import ZoneInfo


EVENT_ALIASES = {
    "sharad-navratri-2026": ("नवरात्रि", "नवरात्र", "navratri"),
    "vijayadashami-2026": ("विजयदशमी", "दशहरा", "dussehra", "vijayadashami", "रावण दहन"),
    "sharad-purnima-2026": ("शरद पूर्णिमा", "sharad purnima"),
    "karwa-chauth-2026": ("करवा चौथ", "करवाचौथ", "karwa chauth"),
    "ahoi-ashtami-2026": ("अहोई अष्टमी", "ahoi ashtami"),
    "diwali-2026": ("दिवाली", "दीवाली", "दीपावली", "diwali", "deepavali"),
    "govardhan-2026": ("गोवर्धन पूजा", "गोवर्धन", "govardhan"),
    "bhai-dooj-2026": ("भाई दूज", "भैयादूज", "bhai dooj"),
    "chhath-2026": ("छठ", "chhath"),
    "tulsi-vivah-2026": ("तुलसी विवाह", "tulsi vivah"),
    "kartik-purnima-2026": ("कार्तिक पूर्णिमा", "kartik purnima"),
}
# Sentence patterns must mention the event itself; generic "after the festival"
# isn't enough to infer which festival is meant.
AFTER = re.compile(
    r"(?:के\\s+बाद|हो\\s+गया|हो\\s+गई|खत्म|समाप्त|बीत\\s+गए|बीत\\s+गई|"
    r"पूरा\\s+हो\\s+गया|पूरी\\s+हो\\s+गई|after|post[- ]|has ended|is over)",
    re.IGNORECASE,
)
BEFORE = re.compile(r"(?:के\\s+पहले|से\\s+पहले|before|आने\\s+वाला|आने\\s+वाली)", re.IGNORECASE)
TODAY = re.compile(r"(?:आज|today)", re.IGNORECASE)
TOMORROW = re.compile(r"(?:कल|tomorrow)", re.IGNORECASE)
YESTERDAY = re.compile(r"(?:बीते\\s+कल|yesterday)", re.IGNORECASE)
PRESENT = re.compile(r"(?:है|होगा|होगी|मनाएंगे|मनाया\\s+जाएगा|is|will be)", re.IGNORECASE)
FINAL = re.compile(r"(?:आखिरी|अंतिम|final|last day)", re.IGNORECASE)
SENTENCES = re.compile(r"[।!?\\n]+|(?<=\\.)\\s+")


def _iso(value):
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError) as exc:
        raise ValueError("Publication date must be YYYY-MM-DD (Asia/Kolkata)") from exc


def _festival_sources(calendar):
    if not isinstance(calendar, dict) or not isinstance(calendar.get("sources"), list):
        raise ValueError("Festival source calendar is missing or invalid")
    result = {}
    for src in calendar["sources"]:
        if not isinstance(src, dict):
            continue
        identifier = src.get("event", "")
        if identifier not in EVENT_ALIASES:
            continue
        if not str(src.get("source", "")).startswith("https://"):
            raise ValueError(f"Festival source URL missing: {identifier}")
        start, end = _iso(src.get("from")), _iso(src.get("to"))
        if end < start:
            raise ValueError(f"Invalid festival date range: {identifier}")
        result[identifier] = (start, end)
    return result


def _claims(episode):
    seo = episode.get("seo_metadata") or {}
    thumb = episode.get("thumbnail") or {}
    short_thumb = episode.get("shorts_thumbnail") or {}
    yield "title", seo.get("long_video_title", "")
    yield "shorts_title", seo.get("shorts_title", "")
    yield "description", seo.get("long_video_description") or seo.get("description") or ""
    yield "shorts_description", seo.get("shorts_description", "")
    yield "thumbnail", thumb.get("thumbnailText", "")
    yield "shorts_thumbnail", short_thumb.get("thumbnailText", "")
    for format_name in ("long_video", "shorts"):
        for n, scene in enumerate((episode.get(format_name) or {}).get("scenes") or [], 1):
            if isinstance(scene, dict):
                yield f"{format_name}.scene_{n}", scene.get("text") or scene.get("narration_chunk") or ""


def _nearby(sentence, span, window=45):
    a, b = span
    return sentence[max(0, a-window):min(len(sentence), b+window)]


def _relative_issues(event, text, anchor, start, end, publish_day, label):
    issues = []
    for segment in SENTENCES.split(text):
        sentence = segment.strip().lower()
        if not sentence:
            continue
        for match in re.finditer(re.escape(anchor.lower()), sentence):
            left, right = sentence[:match.start()], sentence[match.end():]
            nearby = _nearby(sentence, match.span())
            # e.g. विजयदशमी के बाद / नवरात्रि खत्म / after Vijayadashami.
            nearby_after = AFTER.search(right[:40])
            before_after = re.search(r"(?:after|post[- ])\\s*$", left[-15:])
            past_nine_days = (
                event == "sharad-navratri-2026"
                and re.search(r"नौ\\s+दिन|नौ\\s+रात|9\\s+दिन|9\\s+रात", right[:25])
                and AFTER.search(right[:65])
            )
            if (nearby_after or before_after or past_nine_days) and publish_day <= end:
                issues.append(f"{label}: {event} is described as already finished but ends on {end}")
            if BEFORE.search(right[:25]) and publish_day > start:
                issues.append(f"{label}: {event} is described as upcoming, but starts on {start}")
            # "कल विजयदशमी है" or "विजयदशमी कल है" (not generic 'कल याद करेंगे').
            prefix_tomorrow = re.search(r"(?:कल|tomorrow)\\s*$", left[-14:])
            suffix_tomorrow = re.match(r"\\s*(?:कल|tomorrow)\\b?", right[:13])
            near_tomorrow = prefix_tomorrow or suffix_tomorrow
            if near_tomorrow and not YESTERDAY.search(nearby):
                if PRESENT.search(right[:55]) or PRESENT.search(left[-28:]):
                    if not (start <= publish_day + timedelta(days=1) <= end):
                        issues.append(f"{label}: 'tomorrow' for {event} conflicts with event dates {start}..{end}")
            prefix_today = re.search(r"(?:आज|today)\\s*$", left[-14:])
            suffix_today = re.match(r"\\s*(?:आज|today)\\b?", right[:14])
            near_today = prefix_today or suffix_today
            if near_today and not (start <= publish_day <= end):
                issues.append(f"{label}: 'today' for {event} conflicts with event dates {start}..{end}")
            if near_today and FINAL.search(right[:40]) and publish_day != end:
                issues.append(f"{label}: 'today is final day' for {event} but last date is {end}")
            # "कल <event> खत्म" is not a future event announcement;
            # ambiguous Hindi कल is deliberately not guessed here.
    return issues


def validate(episode, *, publish_date=None, calendar=None):
    if not isinstance(episode, dict):
        raise ValueError("Episode must be a JSON object")
    if publish_date is None:
        publish_date = datetime.now(ZoneInfo("Asia/Kolkata")).date()
    elif not isinstance(publish_date, date):
        publish_date = _iso(publish_date)
    if calendar is None:
        calendar = json.loads(
            (Path(__file__).resolve().parents[1] / "data/festival_routes_2026.json")
            .read_text(encoding="utf-8")
        )
    sources = _festival_sources(calendar)
    issues = []
    checked = []
    for label, raw in _claims(episode):
        if not isinstance(raw, str) or not raw.strip():
            continue
        for event, anchors in EVENT_ALIASES.items():
            present = [x for x in anchors if x.casefold() in raw.casefold()]
            if not present:
                continue
            if event not in sources:
                if any(TODAY.search(raw) or TOMORROW.search(raw) for _ in [0]):
                    issues.append(f"{label}: no verified dates for {event}; remove relative-day claim")
                continue
            start, end = sources[event]
            for anchor in present:
                issues.extend(_relative_issues(event, raw, anchor, start, end, publish_date, label))
            checked.append(event)
    # Treat _meta.decisionBasis as a hint, NEVER authoritative evidence.
    # EVENT_DATE must coincide with at least one referenced calendar event,
    # otherwise it cannot be used as a 'verified' date assertion.
    meta = episode.get("_meta") or {}
    basis = str(meta.get("decisionBasis") or "")
    asserted = re.search(r"\\bEVENT_DATE\\s*:\\s*(\\d{4}-\\d{2}-\\d{2})", basis)
    if asserted and checked:
        day = _iso(asserted.group(1))
        if not any(sources[event][0] <= day <= sources[event][1] for event in set(checked)):
            issues.append("_meta.decisionBasis: EVENT_DATE contradicts linked calendar events")
    return {
        "ok": not issues, "publish_date_ist": publish_date.isoformat(),
        "source_checked_at": calendar.get("checked_at"),
        "calendar_coverage_end": calendar.get("coverage_end"),
        "checked_events": sorted(set(checked)), "issues": list(dict.fromkeys(issues)),
        "notes": [
            "Static sources are location-sensitive; verify local tithi and muhurat before publishing.",
            "No LLM PASS or unverified EVENT_DATE can override a known date contradiction.",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--replay", required=True, help="out/replay_inputs.json")
    parser.add_argument("--publish-date-ist", default=os.getenv("TARGET_PUBLISH_DATE_IST", ""))
    args = parser.parse_args(argv)
    saved = json.loads(Path(args.replay).read_text(encoding="utf-8"))
    episode = json.loads(saved["payload"])
    report = validate(episode, publish_date=args.publish_date_ist or None)
    dest = Path("out/festival_date_qc.json")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report["ok"]:
        print("::error::Festival date QC blocked paid media generation. Correct cached story or publication date.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
