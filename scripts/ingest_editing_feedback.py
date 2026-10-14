#!/usr/bin/env python3
"""Deterministic, non-LLM bridge from channel YouTube metrics to real render styles.

Requires:
- a GitHub render that passed audio/visual QC, recorded in the render ledger;
- an exact one-to-one match of that render's video title to the channel's
  YouTube Data API video id & publication timestamp;
- matching YouTube Analytics video-id metrics;
- >=7 days of publication maturity, >=100 views, >=3 distinct videos/style;
- no crossing Primary/oflifepart account scopes.

Outcomes are OBSERVATIONAL performance signals, not causal proof of effects.
Never copies a metric to the wrong title, assumes a missing video is a zero,
or makes up an Instagram metric.
"""
import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
import unicodedata

VALID_STYLES = {
    "cinematic_devotional", "curiosity_reveal", "presenter_explainer",
    "emotional_story", "festival_energy",
}
SCOPES = {"primary", "oflifepart31"}


def _utc(value):
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)


def _title(text):
    return " ".join(unicodedata.normalize("NFC", str(text or "")).split()).casefold()


def _json_array(text, max_size=54000):
    if not isinstance(text, str) or len(text) > max_size:
        raise ValueError("Invalid input size or content")
    result = json.loads(text)
    if not isinstance(result, list):
        raise ValueError("Expected JSON array from real YouTube source")
    return result


def compute_channel_signals(ledger, analytics, ids, titles, published, *, scope,
                            now=None):
    if scope not in SCOPES:
        raise ValueError("Unknown Make account scope")
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("UTC timestamp required")
    if not all(isinstance(x, list) for x in (ledger, ids, titles, published)):
        raise ValueError("Invalid attribution data format")
    if not (len(ids) == len(titles) == len(published)):
        raise ValueError("YouTube ID, title and published-date columns do not align")
    if not isinstance(analytics, dict) or analytics.get("kind") != "youtubeAnalytics#resultTable":
        raise ValueError("Missing real YouTube Analytics result table")
    columns = [h.get("name") for h in analytics.get("columnHeaders", []) if isinstance(h, dict)]
    expected = {"video", "views", "averageViewPercentage", "shares"}
    if not expected.issubset(set(columns)):
        raise ValueError("Missing mandatory YouTube Analytics metrics")
    index = {name: columns.index(name) for name in expected}
    stats_by_id = {}
    for row in analytics.get("rows", [])[:70]:
        if not isinstance(row, list) or len(row) != len(columns):
            continue
        video_id = str(row[index["video"]] or "")
        if not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id) or video_id in stats_by_id:
            continue
        try:
            views = int(row[index["views"]])
            pct = float(row[index["averageViewPercentage"]])
            shares = int(row[index["shares"]])
        except (ValueError, TypeError, OverflowError):
            continue
        if views < 100 or views > 1000000000 or not math.isfinite(pct) or not 0 < pct <= 1500:
            continue
        if shares < 0 or shares > views:
            continue
        stats_by_id[video_id] = (views, pct, shares)
    title_to_video = {}
    for raw_id, raw_title, raw_date in zip(ids[:80], titles[:80], published[:80]):
        video_id = str(raw_id or "")
        normalized = _title(raw_title)
        if not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id) or not normalized:
            continue
        try:
            date = _utc(raw_date)
        except (ValueError, TypeError):
            continue
        title_to_video.setdefault(normalized, []).append((video_id, date))
    matched = []
    rejected = []
    # Same exact title reused across multiple render runs is ambiguous.
    title_occurrences = {}
    for record in ledger:
        if not isinstance(record, dict) or record.get("account") != scope:
            continue
        for key in ("longTitle", "shortsTitle"):
            title_occurrences[_title(record.get(key))] = title_occurrences.get(
                _title(record.get(key)), 0
            ) + 1
    used_video_ids = set()
    for rec in ledger[-350:]:
        if not isinstance(rec, dict) or rec.get("account") != scope:
            continue
        if rec.get("editingStyle") not in VALID_STYLES:
            continue
        if rec.get("status") != "qc_passed_rendered_not_proof_of_youtube_publication":
            continue
        try:
            rendered = _utc(rec["renderedAt"])
            run_id = str(int(rec["githubRunId"]))
        except (KeyError, ValueError, TypeError, OverflowError):
            continue
        for fmt, key in (("long", "longTitle"), ("shorts", "shortsTitle")):
            name = _title(rec.get(key))
            items = title_to_video.get(name, [])
            if not name or title_occurrences.get(name) != 1 or len(items) != 1:
                rejected.append({"reason": "ambiguous_or_unpublished_title", "format": fmt,
                                 "githubRunId": run_id})
                continue
            video_id, published_at = items[0]
            age_days = (now - published_at).total_seconds() / 86400
            # Publication must occur on/after this rendered version; slight
            # timestamp skew is allowed, but NOT a published video from before.
            if not 7 <= age_days <= 45 or published_at < rendered:
                rejected.append({"reason": "not_mature_or_predates_render", "format": fmt,
                                 "githubRunId": run_id})
                continue
            if video_id in used_video_ids or video_id not in stats_by_id:
                rejected.append({"reason": "missing_or_duplicate_video_metrics",
                                 "format": fmt, "githubRunId": run_id})
                continue
            views, pct, shares = stats_by_id[video_id]
            used_video_ids.add(video_id)
            matched.append({
                "account": scope, "platform": "youtube", "style": rec["editingStyle"],
                "format": fmt, "videoId": video_id, "views": views,
                "average_view_percentage": round(min(100, pct), 3),
                "raw_average_view_percentage": round(pct, 3),
                "shares_per_1000": round(shares / views * 1000, 4),
                "publishedAt": published_at.isoformat(),
                "githubRunId": run_id, "source": f"https://www.youtube.com/watch?v={video_id}",
            })
    by_style = {}
    for item in matched:
        by_style.setdefault((item["platform"], item["style"], item["format"]), []).append(item)
    signals = []
    for (platform, style, fmt), items in sorted(by_style.items()):
        if len(items) < 3:
            continue
        # Compare Long with Long or Shorts with Shorts, not their incomparable
        # average-view-percentage baselines. Average videos equally.
        signals.append({
            "platform": platform, "style": style, "format": fmt, "videos": len(items),
            "published_on": max(x["publishedAt"][:10] for x in items),
            "average_view_percentage": round(sum(x["average_view_percentage"] for x in items) / len(items), 3),
            "shares_per_1000": round(sum(x["shares_per_1000"] for x in items) / len(items), 3),
            "source": items[0]["source"],
            "source_type": "exact_title_id_match_with_qc_render_and_youtube_analytics",
        })
    audit = {
        "account": scope, "generatedAt": now.isoformat(), "matchedVideos": matched,
        "rejected": rejected[-120:], "eligibleGroups": len(signals),
        "limitations": "30-day YouTube Analytics top-50 sample. Exact title/videoId match only; >=7d mature; observational, not causal. Missing/uploaded-with-changed-title videos excluded.",
    }
    return signals, audit


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--scope", choices=sorted(SCOPES), required=True)
    p.add_argument("--ledger", default="data/render_editing_history.json")
    p.add_argument("--signals-dir", default="data")
    p.add_argument("--analytics", required=True)
    p.add_argument("--ids", required=True)
    p.add_argument("--titles", required=True)
    p.add_argument("--published", required=True)
    args = p.parse_args()
    ledgerfile = Path(args.ledger)
    ledger = json.loads(ledgerfile.read_text(encoding="utf-8")) if ledgerfile.is_file() else []
    metrics = json.loads(args.analytics)
    ids, titles, published = (_json_array(value) for value in (args.ids, args.titles, args.published))
    signals, audit = compute_channel_signals(ledger, metrics, ids, titles, published, scope=args.scope)
    out = Path(args.signals_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / ("editing_style_signals_" + args.scope + ".json")).write_text(
        json.dumps(signals, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    (out / ("editing_feedback_audit_" + args.scope + ".json")).write_text(
        json.dumps(audit, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(f"🎞️ Editing feedback {args.scope}: {len(audit['matchedVideos'])} matched published videos; "
          f"{len(signals)} mature 3+ video groups; no guessed trends")


if __name__ == "__main__":
    main()
