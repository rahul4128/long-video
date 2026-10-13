# Adaptive editing skills — devotional video pipeline

## Status / scope

Branch: \`visual-director-v2\`. Existing Primary Make scenario **7722792** remains paused. The upstream council adds \`EDIT_STYLE=...\` and \`EDIT_STYLE_WHY=...\` to its **existing** \`_meta.decisionBasis\`, without modifying the story JSON mapping, scene counts or factual sources. \`generate_assets.py\` passes the existing JSON payload to \`editing_director.attach_editing(context=payload)\`, which selects one edit style per episode and applies a variation per actual narration beat.

A screenshot of a tutorial channel **shows editing techniques, not empirical evidence of what is trending**. The current Make YouTube search finds **devotional topic demand**, not editing trends. Style selection is dynamically **story- and audience-matched**, but a trend claim is only allowed when validated recent aggregate editing-performance data is explicitly provided.

## Style presets (select only one principal style per video)

| Style | When | Editing |
| --- | --- | --- |
| \`cinematic_devotional\` | Calm temple/devotional material | Warm image grade, clean B-roll, restrained transitions, unobtrusive captions |
| \`curiosity_reveal\` | Authentic mystery / sourced revelation | Short hook, a single warm flash accent at main pivot, spotlight focus, kinetic text and sound punctuation |
| \`presenter_explainer\` | Ritual/context explanation, practical question | Clearly ordered B-roll, detail inserts, focus captions, subtle spotlight blur |
| \`emotional_story\` | Personal struggle, devotion or compassion | Longer visual holds, low-motion shots, soft transitions, calm captions |
| \`festival_energy\` | Genuine action, gathering or festive celebration | Controlled whip-pan pivot, modest higher saturation, lively shot progression, focused captions |

The style applies to Long and Shorts from the same story without fabricating new narration, royalty-free footage, or cultural facts. Each scene contains the chosen \`editStyle\` and caption style; each shot carries actual \`transition\`, \`editTreatment\` and optional effects. The edit plan cannot alter shot source files or TTS timestamps.

## Editing skills by implementation state

**Automatic now:**
- Narration-matched B-roll (already in Visual Director), clean cuts, subtle pan and push, action/detail framing
- Visual hook from frame 1 and existing animated \`HookOverlay\`
- Dynamic chapter/detail/reveal pacing, kinetic short text and word-highlight captions
- Carefully budgeted crossfade, blur cut, whip-pan and soft warm flash accent (not uncontrolled strobe)
- Spotlight background blur for explanatory/question shots, consistent restrained color grading
- Mood-aware music, ducking under the storyteller, and beat-timed SFX (existing)
- Source/license/image/audio/edit QC, metadata and draft review-only video release

**Conditional, manual/verified evidence required:**
- Before/after split-screen: a shot has \`comparisonApproved=true\`, plus \`comparisonBeforeFile\` and \`comparisonAfterFile\` naming **two distinct existing still images in that same scene**. Not activated for unrelated scenes or images.
- Privacy/face region blur: a shot has \`privacyApproved=true\` and \`privacyBlurBoxes=[{"x":0.2,"y":0.15,"width":0.12,"height":0.15}]\` with relative normalized coordinates. These are **static, reviewed regions**, **not automatic face detection or tracking**. Review moving faces separately.

**Not provided by the screenshots or current infrastructure:** GPU-heavy motion tracking, automatic face tracking, genuine 3D compositing, CapCut template import, unlicensed trendy songs, and unverified automatic style popularity discovery. Do not claim these are integrated. Adding them would need a separate verified footage/tool evaluation.

## Real performance evidence, never guesses

\`editing_style_engine.py\` accepts optional \`_meta.editing_style_signals\` in the GitHub payload. Each record must contain \`style\`, \`published_on\` (YYYY-MM-DD), \`videos\` (at least 3 comparable videos), \`average_view_percentage\`, \`shares_per_1000\`, \`platform\` (\`youtube\` or \`instagram\`), and \`source\`. Records older than 45 days, implausible metrics, and unknown styles are discarded. Only a **compatible** style is allowed to influence the creative director. Existing Make scenario currently does NOT populate this structured optional field, so \`trend_claim\` will be \`not_verified\` until a real style-level performance sync is mapped.

Views/likes/watch seconds alone cannot prove a particular edit effect improved retention. Compare A/B videos with enough samples and normalize for topic, duration, traffic source and posting time.

## Audit and rollback

- \`out/editing_qc_report.json\`: selected style, selection evidence, allowed skills and actual per-scene effects
- \`out/music_license_report.json\`: licensed music origin, hashes and review warning
- \`EDITORIAL_EDITING_ENABLED=false\`: disables metadata-based adaptive edit treatments without disturbing narration, B-roll or established visuals
- Python offline checks \`test_editing_director.py\`, \`test_editing_style_engine.py\`, \`test_verified_edit_skills.py\`; validation \`scripts/validate_editing.py\` before rendering

## Tomorrow's manual test

1. Trigger the **Primary** scenario (still paused) with a factually suitable episode; do not publish automatically.
2. Inspect the GitHub Actions status and \`editing_qc_report.json\`. Check which style, transitions and captions were truly selected.
3. Watch first 5 seconds, ordinary explanation, climax/reveal, last 10 seconds, and both formats. Watch for caption overlap, edge blur artifacts, irrelevant B-roll, clipping, too many SFX and mismatched comparison sources.
4. Compare audience retention (especially first 3/10/30 seconds), saves/shares, average percentage viewed, and rewatches against earlier episodes with comparable length and topic. Keep the styles that actually perform—not whichever screenshot looks flashy.

This is an original, narrator-led editing toolkit inspired by the shared editing-topic screenshots. No access to tutorial reel frames was required; do not present it as an exact replication of those creators' edits.
