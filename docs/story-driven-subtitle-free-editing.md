# Creator-led, subtitle-free devotional editing (Oct 27, 2026)

Reference: https://www.youtube.com/watch?v=1vzda4uh7nA — a general Canva editing course.
Its useful production principles are trim/split, order shots, layer audio and imagery,
vary transitions, control image looks and export. They are **editing techniques**,
not a new automatic platform or evidence of audience-retention performance.

## Pipeline and limitations

Canva Connect is already used for AI still images, assets, thumbnails and
optional finishing/review. It does not supply a documented general-purpose
multi-track video timeline edit API for programmatically cutting an arbitrary
daily narrated MP4. Keep the reliable, CPU-only Remotion/FFmpeg renderer as
the deterministic **editor**; do not claim the GitHub workflow edits the Canva
web timeline. Do not add Google Flow, paid editors, GPU dependencies or
independent Instagram renders.

## Editorial policy

- FIRST FRAME: exact narration-relevant subject on screen immediately, with
  only the existing brief 1.8-second title hook. No greeting or slow branding.
- HOOK/QUESTION: a quick camera acceleration and clean cut at narration beat,
  where the verified visual actually shows the question's subject.
- EXPLANATION: measured motion, varied real B-roll/detail/wide shot types.
  More random transitions are **not** more professional.
- CLIMAX: one properly supported transition/sound punctuation, with a specific
  payoff shot; a calm emotional reveal gets space to breathe.
- EMOTION: slow, restrained push/pan and voice-first music ducking, never
  generic swooshes that bury an important narrative moment.
- STORY VARIATION: the Python editor's style selector already chooses
  cinematic/curiosity/explainer/emotional/festival energy from each video's
  verified premise and existing performance evidence. The new per-shot
  `editRhythm` is quick/measured/linger and records `editReason`.
  Timeline follows real TTS word/beat boundaries. No random cut spamming or
  invented action footage.
- NO SUBTITLES: `SUBTITLES_ENABLED=false` in the production workflow and
  explicit `showSubtitles=false` in both generated Remotion props.
  `EDITORIAL_TEXT_OVERLAYS_ENABLED=false` removes repeating documentary
  text cards. The opening **hook** and the two thumbnail text overlays remain;
  neither is a transcript subtitle. If requested later, explicitly opt in.
- Keep exactly one 16:9 Long and one 9:16 Short and one thumbnail for each;
  same outputs can be posted manually to YouTube and Instagram.
- Before publish: inspect hook / middle / reveal / ending; correct mismatched
  goddess/iconography or unsupported factual claims. Video review is required.
  No algorithm guarantees human-level editing or retention.

## Checks

Run no-credit preflight:
`python -m unittest discover -s tests -p 'test_story_driven_edit.py' -v`
plus `npx tsc --noEmit` in the CI workflow.
Full render uses media/TTS quotas. Keep `review_approved=false` and don't
automatically publish unreviewed videos.
