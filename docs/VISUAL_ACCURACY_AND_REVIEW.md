# Story-to-Footage Accuracy: Native Visual Director v2

## Why this gate exists

The Oct 2026 Garba sample promised **three precise dance steps**, but the actual video used generic stock clips tagged `person`, `hands`, and `dancer`. The stock provider's search metadata, CLIP similarity and human-scene relevance scores cannot verify correct footwork. Automated media QC previously passed even when the visual lesson was inaccurate.

## Current default: entirely automatic for *observable cultural stories*

- The generator automatically creates narration-synced scenes from Pexels/Pixabay/Coverr/Wikimedia and AI images.
- The visual selector skips generic one-word stock queries, brings topic-specific scene context forward and uses AI visuals if no relevant stock exists.
- Story agents prioritize exciting, visual, source-verifiable festival stories, cultural comparisons, relatable emotion, human-interest learning and practical **non-demonstration** explanations.
- This DOES NOT ban dance, cooking, yoga or craft as story subjects. A documentary or cultural video explaining *why* Garba gatherings matter can use realistic celebration footage. What it cannot do automatically is claim the footage *teaches an exact move*.

## Physical technique lessons: explicitly verified media required

The deterministic guard in `scripts/visual_evidence.py` detects promises such as "learn three Garba steps", yoga pose instructions, recipe processes or craft tutorials in the title. If it detects them, `generate_assets.py` fails immediately **before paid generation**, unless an explicit `public/verified_action_clips.json` (or `ACTION_DEMONSTRATION_MANIFEST`) exists.

The later `scripts/validate_native_visuals.py` audit requires **human-reviewed MP4 clips matching each actual instructional scene** in *both* Long and Shorts. Approved footage is matched to exact file bytes by SHA-256, scene number and format. It does not accept a search query or an invented model score as confirmation. An approved manifest verifies **provenance, not visual correctness automatically**: the editor still has to inspect the actual motions before approving them. Merely writing `human_reviewed: true` is not sufficient unless an editor genuinely reviewed those clips.

A manifest is an *auditing contract*, not a clip-generation/import mechanism. The current automatic renderer does **not** source or insert human-approved tutorial footage on its own. Until an editor provides a separate verified-media integration, choose observational stories instead of step-by-step promises.

Example illustrative record (not a usable preapproved clip):

```json
{
  "version": 1,
  "reviewed_clips": [
    {
      "category": "dance",
      "format": "shorts",
      "scene": 2,
      "file": "scene_2_b1.mp4",
      "sha256": "<the actual SHA-256 digest of the rendered MP4>",
      "human_reviewed": true,
      "reviewer": "<person who checked this exact motion>",
      "step_label": "two-clap Garba footwork"
    }
  ]
}
```

Each instructional scene must have a matching reviewed shot; an edit to the MP4 invalidates its digest. No script should claim that its technique was verified by automation.

## Release behavior after render

- The standard workflow publishes render outputs **to a GitHub draft release**, not a public release, by default.
- The YouTube upload notification is skipped on automatic Make dispatches.
- A manual `workflow_dispatch` using `review_approved=true` can publish the release and notify the private YouTube uploader. That flag is a deliberate editorial approval, not an AI assessment. Use only after watching the full Long and Short.
- `privacy` defaults to `private`. YouTube Analytics exposure and discoverability require separate approval later.
- Warning: `review_approved=true` in a NEW workflow run recreates the video; this is not currently an action to approve a previous draft release in place. Keep the workflow paused if that is not desired.

## Test coverage

`python -m unittest discover -s tests -p 'test_native_visual_guard.py'`

Tests cover automatic cultural-story allowance, detecting other hands-on instruction categories, excluding generic stock queries, rejecting high-scored but unverified clips, exact SHA-256 matching, missing/forged reviews and scene-level technique checks. The GitHub smoke workflow also validates Python syntax and the default draft-only release / explicit approval requirement.

## Practical editorial choice

Until we have genuinely licensed, demonstrably accurate technique footage, prefer an exciting observational alternative such as regional Navratri celebrations, the human experience of a Garba gathering, authentic Golu collections or Bengali Durga Puja pandal traditions. Viewers should get exactly what the title and opening promise.
