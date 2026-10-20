#!/usr/bin/env python3
"""Cache an approved Make episode *before* any paid media generation.

A new workflow_dispatch may specify reuse_run_id instead of payload, allowing
a fresh checkout of the updated GitHub branch without invoking Gemini again.
Cache only the user-approved story JSON, not credentials or output secrets.
"""
import hashlib
import json
import os
from pathlib import Path
import re

from scripts.festival_date_gate import validate_festival_date_claims


def prepare(env=None, replay_path=None):
    env = env or os.environ
    previous = str(env.get("REPLAY_RUN_ID") or "").strip()
    story_file = str(env.get("STORY_FILE") or "").strip()
    if previous and story_file:
        raise ValueError("Choose either reuse_run_id or story_file, not both")
    if previous:
        if not re.fullmatch(r"\d{4,20}", previous):
            raise ValueError("reuse_run_id must be a GitHub run number ID")
        if str(env.get("REVIEW_APPROVED") or "false").lower() == "true":
            raise ValueError("Reused story must remain review-only; publication needs separate approval")
        source = Path(replay_path or "out/reused/replay_inputs.json")
        if not source.is_file():
            raise ValueError("Source run has no saved payload artifact. Export the past Make payload once.")
        doc = json.loads(source.read_text(encoding="utf-8"))
        if not isinstance(doc, dict) or str(doc.get("version")) != "1":
            raise ValueError("Invalid replay artifact version")
        payload_string = doc.get("payload")
        pipeline = doc.get("pipeline")
        source_run = previous
        verified = doc.get("payload_sha256")
    else:
        pipeline = env.get("NEW_PIPELINE", "")
        source_run = None
        verified = None
        if story_file:
            # Read only reviewed episode JSON from this repository, never
            # arbitrary user-supplied filesystem paths (secrets/traversal).
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,118}\\.json", story_file):
                raise ValueError("story_file must be a .json filename in data/replay_stories")
            if str(env.get("REVIEW_APPROVED") or "false").lower() == "true":
                raise ValueError("A stored story_file is review-only; separate publication approval is required")
            story_path = Path(__file__).resolve().parents[1] / "data" / "replay_stories" / story_file
            if not story_path.is_file():
                raise ValueError(f"Story file not found in data/replay_stories: {story_file}")
            payload_string = story_path.read_text(encoding="utf-8")
        else:
            payload_string = env.get("NEW_DISPATCH_PAYLOAD", "")

    if not isinstance(payload_string, str) or not 20 <= len(payload_string) <= 250000:
        raise ValueError(
            "No complete story JSON available. Paste the full payload or select story_file "
            "from data/replay_stories (avoid copying truncated JSON)."
        )
    try:
        episode = json.loads(payload_string)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Incomplete/invalid story JSON: {len(payload_string)} characters received, "
            f"error near character {exc.pos}. Do not paste a shortened code preview; "
            "use story_file for a verified repository copy."
        ) from exc
    # Accept either Make module 3's raw story JSON or module 5's complete
    # GitHub workflow_dispatch envelope. Reusing module 5 also preserves the
    # original account label without any additional Make/Gemini execution.
    if isinstance(episode, dict) and isinstance(episode.get("inputs"), dict):
        inputs = episode["inputs"]
        inner = inputs.get("payload")
        if isinstance(inner, str):
            episode = json.loads(inner)
        elif isinstance(inner, dict):
            episode = inner
        else:
            raise ValueError("Make GitHub envelope does not contain a valid story")
        original_pipeline = inputs.get("pipeline")
        if isinstance(original_pipeline, str) and original_pipeline:
            pipeline = original_pipeline
    if isinstance(episode, dict) and isinstance(episode.get("payload"), dict):
        # Repository dispatch content is often {payload: {...}}, but our
        # workflow_dispatch normally already passes only the script as JSON.
        episode = episode["payload"]
    if not isinstance(episode, dict):
        raise ValueError("Episode is not a JSON object")
    for fmt in ("long_video", "shorts"):
        item = episode.get(fmt)
        if not isinstance(item, dict) or not isinstance(item.get("scenes"), list) or not item["scenes"]:
            raise ValueError("Approved story is missing complete " + fmt + ".scenes")
    seo = episode.get("seo_metadata")
    if not isinstance(seo, dict) or not seo.get("long_video_title") or not seo.get("shorts_title"):
        raise ValueError("Approved story must have both title fields")
    if not isinstance(pipeline, str) or not re.fullmatch(r"[A-Za-z0-9_-]{3,80}", pipeline):
        raise ValueError("Invalid or missing original pipeline label")
    # Hard gate before ANY paid TTS/images or render. A previously cached story
    # is rechecked on each run because 'today/tomorrow/after' can become stale.
    # The date is set by runner/explicit operator, never from LLM-generated copy.
    date_check = validate_festival_date_claims(
        episode, publish_date=str(env.get("PUBLICATION_DATE_IST") or "").strip() or None
    )
    if not date_check["ok"]:
        detail = "; ".join(date_check["issues"][:6])
        raise ValueError(
            f"Festival-date preflight BLOCKED for {date_check['publish_date_ist']}: {detail}. "
            "Revise the date-sensitive story and obtain QA approval before paid rendering."
        )
    if not pipeline.startswith("visual-director-v2-"):
        # Manual tests may have other labels; do not assign them a measured
        # channel style unless the original Make run was explicitly scoped.
        print("This pipeline has no source-verified editing-performance scope.")

    approved_json = json.dumps(episode, ensure_ascii=False, separators=(",", ":"))
    digest = hashlib.sha256(approved_json.encode("utf-8")).hexdigest()
    if verified and digest != verified:
        raise ValueError("Cached payload SHA-256 does not match; refusing replay")
    archive = {
        "version": 1, "pipeline": pipeline,
        "payload": approved_json, "payload_sha256": digest,
        "source_run_id": source_run,
        "festival_date_check": date_check,
    }
    return archive


def main():
    item = prepare()
    out = Path("out/replay_inputs.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(item, ensure_ascii=False), encoding="utf-8")
    Path("out/festival_date_qc.json").write_text(
        json.dumps(item["festival_date_check"], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print("Festival-date preflight: PASS for " + item["festival_date_check"]["publish_date_ist"])
    output_file = os.environ.get("GITHUB_OUTPUT")
    if output_file:
        with open(output_file, "a", encoding="utf-8") as fh:
            fh.write("pipeline=" + item["pipeline"] + "\n")
    print(f"Approved story is cached for GitHub-only retries; SHA-256 {item['payload_sha256'][:14]}, "
          f"pipeline {item['pipeline']}. No Gemini calls.")


if __name__ == "__main__":
    main()
