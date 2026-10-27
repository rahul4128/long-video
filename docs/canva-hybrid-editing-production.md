# Canva + Remotion hybrid editor — production rollout 2026-10-27

**Goal:** Improve day-to-day visual engagement without burning Canva credits
on unverified templates, violating devotional image relevance, or publishing
unedited duplicates.

## Why a hybrid is better for today's run

- Canva Connect provides AI/generated stills, asset uploads, existing
  design autofill and asynchronous export. Canva design autofill accepts
  image/video assets where a design already has appropriate labeled fields.
- User's existing "Hindi devotional video master template" (DAHWRaFNz_Y)
  is ONE 1080x1920 page and exposes TITLE, SUBTITLE, VISUAL; it is **not**
  a multi-beat animated edit template. It is also vertical-only.
- Canva's visual editor, animations and manual multi-track assembly are not
  a general unattended timeline-edit REST API. Do not overwrite or secretly
  mutate the existing design, use its SUBTITLE data field, or export a
  static template as proof of dynamic cinematic editing.
- Therefore keep **Canva images + source-specific visual prompts** and use
  **CPU Remotion+FFmpeg** to apply reusable Canva-style visual techniques
  to each real narration beat.
- Avoid an extra Canva API job, clone, new design, upload or export during
  today's video. No new credentials or recurring paid editor.

## New automated original editing techniques

| Technique | Dynamic selection | Bound | Renderer |
| --- | --- | --- | --- |
| Masked close-up reveal | Actual story climax/reveal, mystery style, evidence beat labeled reveal/climax or specific emphasis, verified detail/close-up | At most 2 per Long, 1 per Short; at most 1 per scene | CPU CSS clip-path in Scene.tsx |
| Cinematic focus pull | Selected real detail or close-up in curiosity or practical explainer | At most one focus per scene; 1.8px blur, ~0.35s, then sharp | CPU CSS filter |
| Quick/measured/linger camera rhythm | Real TTS question, action, explanation or emotion | Already budgeted/implemented; does not change shot times | Remotion interpolation |
| Beat-timed B-roll / music / SFX | Existing actual narration timing + verified assets | Existing editorial/QC limits | Remotion/FFmpeg |
| No subtitles | Creator explicitly disabled them | Both Long and Short; opening brief hook allowed | Props and production preflight |

The mask reveals only the **next approved media clip** from under a previous
clip. It does not generate fake historical footage, independently identify
religious figures, or synthesize unsourced before/after claims. If the story
doesn't have an appropriate reveal, the editor uses ordinary clean cuts.

## Output and QC

- Exactly one 16:9 Long MP4 and one 9:16 Short MP4, reused on YouTube and
  Instagram; two thumbnails total.
- No automatic burned-in transcript subtitles or recurrent text cards.
- Strict real image/video relevance, correct deity iconography, framing,
  date claims, and audio/story QCs remain required.
- Videos still require manual visual approval; editing diversity alone
  does not guarantee audience watch time or monetization.
- Feature can be seen in `out/editing_qc_report.json`: each scene now
  logs `maskedReveals`, `focusPulls`, edit rhythms and used skills.
- Offline tests include `tests/test_canva_style_editor.py`,
  TypeScript `npx tsc --noEmit`, and the existing full suite.

## Future fully animated Canva templates (NOT enabled yet)

When the creator provides approved multi-page animated Canva designs with
separate fillable video/image fields, a future *opt-in* path may:
upload approved assets -> verify template dataset -> autofill cloned design
(`create_from_design`) -> export MP4 -> verify size/audio/rights ->
pass to Remotion as a narrated cutaway, with automatic fallback.
Do not rely on that future feature for today's video. Verify plan-specific
Canva APIs, quota and existing OAuth scopes before enabling it.
