#!/usr/bin/env python3
"""Persist the *actual* render editor style for later verified YouTube attribution.

This file is updated only after BOTH video renders and media QC succeeded.
It records no user tokens, channel credentials or analytics. YouTube matching
must separately verify exact video titles, timestamps and video IDs.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re

ALLOWED = {
    "cinematic_devotional", "curiosity_reveal", "presenter_explainer",
    "emotional_story", "festival_energy",
}
SCOPES = {"oflifepart31", "primary"}


def scope_from_pipeline(pipeline):
    value = str(pipeline or "").strip().lower()
    for name in SCOPES:
        if value == "visual-director-v2-" + name:
            return name
    return None


def append_actual_style(ledger, metadata, report, *, run_id, scope, now=None):
    if scope not in SCOPES:
        return False, "unattributed_account_scope"
    if not report.get("enabled") or report.get("selectedStyle") not in ALLOWED:
        return False, "editorial_style_not_applied"
    correlation = str(metadata.get("correlationId") or "").strip()
    long_title = str(metadata.get("long_video_title") or "").strip()
    short_title = str(metadata.get("shorts_title") or "").strip()
    if not 3 <= len(correlation) <= 140 or not re.fullmatch(r"[\w.-]+", correlation):
        return False, "missing_or_untrusted_correlation_id"
    if not 5 <= len(long_title) <= 240 or not 5 <= len(short_title) <= 240:
        return False, "missing_episode_titles"
    run_id = str(run_id or "").strip()
    if not re.fullmatch(r"[0-9]{4,20}", run_id):
        return False, "missing_github_run_id"
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("Render timestamp must have a timezone")
    moment = now.astimezone(timezone.utc).isoformat(timespec="seconds")
    entry = {
        "account": scope,
        "githubRunId": run_id,
        "correlationId": correlation,
        "renderedAt": moment,
        "editingStyle": report["selectedStyle"],
        "editingVersion": report.get("editorVersion"),
        "longTitle": long_title,
        "shortsTitle": short_title,
        "status": "qc_passed_rendered_not_proof_of_youtube_publication",
    }
    rows = json.loads(ledger.read_text(encoding="utf-8")) if ledger.is_file() else []
    if not isinstance(rows, list):
        raise ValueError("Render-attribution ledger must be a JSON list")
    for i, old in enumerate(rows):
        if not isinstance(old, dict):
            continue
        if old.get("account") == scope and old.get("correlationId") == correlation:
            if str(old.get("githubRunId")) != run_id:
                raise ValueError("Conflicting render correlation; explicit review required")
            rows[i] = entry
            break
    else:
        rows.append(entry)
    ledger.parent.mkdir(parents=True, exist_ok=True)
    ledger.write_text(json.dumps(rows[-350:], ensure_ascii=False, indent=2)+"\n",
                      encoding="utf-8")
    return True, entry


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--metadata", required=True)
    p.add_argument("--editing", required=True)
    p.add_argument("--pipeline", required=True)
    p.add_argument("--run-id", required=True)
    p.add_argument("--ledger", default="data/render_editing_history.json")
    args = p.parse_args()
    scope = scope_from_pipeline(args.pipeline)
    meta = json.loads(Path(args.metadata).read_text(encoding="utf-8"))
    report = json.loads(Path(args.editing).read_text(encoding="utf-8"))
    success, reason = append_actual_style(
        Path(args.ledger), meta, report, run_id=args.run_id, scope=scope
    )
    if not success:
        print(f"⚠️ Cannot attribute this render to measured editing analytics: {reason}")
    else:
        print(f"🎞️ Saved actual editor style for GitHub run {args.run_id} / {scope}")


if __name__ == "__main__":
    main()
