# P1 storytelling and adaptive editing: 2026-10-13

## Scope

Branch: \`visual-director-v2\`. Existing Primary Make story scenario 7722792 remains paused, with only its Final Judge (51) and Script QA (911) prompts updated. Kokoro, subtitles, sound/music, visual identity checks, image framing, original 6 Long / 5 Shorts scene contract and review-only releases remain unchanged.

## 1. Conversational spoken Hindi, with independent QA

- Module 51 writes short, spoken, everyday Hindi with relatable examples, natural pauses, straightforward questions and immediate Sanskrit-term explanations. It must preserve source facts and avoid imitating a named person's voice.
- Module 911 independently rejects textbook-style, excessively abstract or unexplained narration using **existing** decision/issue keys.
- \`spoken_hindi_qc.py\` runs before expensive TTS/media retrieval. It reports long sentences, formal vocabulary and unexplained terms in \`out/spoken_hindi_report.json\` but never changes narrated words, source claims or subtitle timings. Report travels to draft review release.
- Optional repo variable \`SPOKEN_HINDI_STRICT=true\` fails truly extreme spoken sentences. Default is advisory to avoid blocking culturally accurate proper nouns/quotes.
- Regression: \`tests/test_p1_storytelling.py\`.

## 2. Documentary visual explanation and narration-synchronous motion graphics

- \`editing_director.py\` gives each existing shot a grounded purpose: reveal payoff, question setup, evidence detail, scene-establishing context or narrated support. Shot order, timing, source media and real video asset sourcing are unchanged.
- \`src/DocumentaryGraphic.tsx\` adds three CPU-only animations: **question**, **explainer step progress**, **key point**. At most one card per scene.
- Every text label is copied/shortened only from the narration-linked visual beat. No invented dates, deities, historical proof, ritual benefits or fake "before/after" illustrations.
- The first hook stays clear; subtitles occupy the lower region; graphics show briefly near the top. Existing \`EditorialAccent\` is suppressed when the richer graphic is used, preventing duplicate cards.
- \`src/Scene.tsx\` renders the chosen graphic inside the shot's own Sequence. \`src/types.ts\` defines the new safe fields. \`editing_qc_report.json\` lists graphic counts and editorial shot reasons.
- Tests verify no fabricated graphics, no extra per-scene overlays, no changes to shot timing, and true progression bounds.

## 3. Performance-informed editing style — evidence-only scaffolding

The Make **YouTube Performance Sync** Primary scenario 7434108 currently has status \`error\`. Most recent failures were YouTube OAuth connection verification HTTP 400 before any operations; prior runs also hit Gemini model request quotas. Do not activate or assert successful syncing until the owner reconnects YouTube and the scenario runs successfully.

The P1 repository side can ingest actual style-labeled per-video metrics:

- \`data/editing_style_signals.json\` begins as an **empty array**.
- \`scripts/build_editing_style_signals.py\` accepts actual records with:
  \`video_id, platform, editing_style, published_on, views, shares, video_duration_seconds, average_view_duration_seconds, evidence_url\`.
- It excludes unsupported categories, expired data, unrealistic measurements, duplicate videos and missing source records; requires at least **three** recent distinct videos of a given style and platform with nontrivial view counts.
- Writes \`data/editing_style_signals.json\` for \`editing_style_engine.py\`. When empty, the director uses the story/content fit, **not imaginary editing trends**.
- Story-prompt signals in Make remain topic demand only. Analytics source reported metrics still require human confirmation of provenance and comparable length/topic.
- Tests: \`tests/test_editing_performance_learning.py\`.

This provides a working intake route, **not a live end-to-end analytics connector**. Mapping styles to YouTube video IDs after approved publication, validating the YouTube connection, and feeding Performance Sync results are pending.

## Tomorrow's test

1. From the paused Primary Make scenario, manually run a private/review-only story only when ready.
2. Check Python tests: \`test_p1_storytelling.py\` and \`test_editing_performance_learning.py\`. Verify Remotion's actual Long and Shorts renders; no smoke test has been executed yet.
3. Download \`spoken_hindi_report.json\` and \`editing_qc_report.json\` from the draft release. Check first-listen Hindi clarity, graphics legibility, shots that match words, music ducking, and audio/color QC.
4. Inspect video titles, music rights, accurate deity imagery and factual claims before upload.
5. Repair/reconnect YouTube Performance Sync separately; no new Make credentials were added in this patch.

## Not claimed / further optional work

Not a 1:1 remake of the Instagram editor. No GPU-intensive motion tracking, computer-vision-driven object keyframes, auto-trusted archive footage or guaranteed editing trend discovery. New story graphics are intentionally limited by the approved narration, and the final product needs a rendered-video quality review.
