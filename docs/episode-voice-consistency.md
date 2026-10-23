# PR A1 — one narrator for the entire Long + Shorts episode

## Contract

- Voice engine selection is all-or-nothing for ALL narration chunks in one
  GitHub run. If any later Gemini scene exhausts quota, discard staged Gemini
  files and synthesize every Long and Shorts chunk using one fallback engine.
- Gemini -> Kokoro -> Edge; Kokoro/auto -> Edge; IndicF5 -> Edge; Edge fails
  closed. No TTS engine ever falls back from within an individual scene.
- MP3 + word-boundary data are cached with SHA256 of normalized spoken text,
  audio beat, engine, model and voice settings. A changed voice invalidates
  the cache. Successful but uncommitted Gemini chunks can be reused in a
  future run; they must never appear in an episode using a fallback voice.
- A cache hit still verifies file size/audio duration. A corrupt cache entry
  regenerates that clip.
- A machine-readable audit at out/voice_episode_report.json records the
  selected engine, the number of chunks, character count, cache hits and
  sanitized fallback reasons. Video metadata includes narrationVoice.
- The Actions workflow refuses to proceed to rendering unless the audit
  reports one engine, no mixing and every chunk synthesized successfully.
  Review-only/draft publication settings have NOT changed.

## Quota limitations and cost controls

Gemini does not provide a dependable remaining free-tier quota in this Make
workflow. Preflight therefore estimates the exact number of *uncached*
Long+Shorts chunks and characters and compares it to configured limits
(GEMINI_TTS_MAX_REQUESTS and GEMINI_TTS_MAX_API_ATTEMPTS). Optional
GEMINI_TTS_DAILY_REMAINING is supported if the operator knows that value.
This is NOT a live quota guarantee. If Gemini fails at any point, the
episode is reconstructed using one fallback voice; partial Gemini audio
is not published. This can cost more CPU time, but protects listening quality.

GitHub actions/cache/restore and /save keep the content-addressed cache
between replay runs. This costs GitHub cache storage; clear old Actions
caches if needed. No API calls are made merely by running unit tests.

## Zero-credit test command

Run on this PR branch:

    python -m unittest discover -s tests -p 'test_episode_voice.py' -v

The tests use fake audio and do not contact Gemini, Canva, Edge or HuggingFace.
They cover a failure in the final Shorts chunk, budget preflight, known
daily cap, replays, voice invalidation, Kokoro -> Edge whole-episode failover
and final fail-closed behavior.

Safe workflow test WITHOUT synthesis or render (only preflight; it does
not test live engine runtime):

- Workflow: Render Devotional Video (Long + Shorts)
- Ref: this PR branch for review (or merged visual-director-v2).
- reuse_run_id: 39934556546
- preflight_only: true
- use_canva_images: false
- gemini_tts_smoke_only: false
- canva_smoke_only: false
- review_approved: false

To test the real voice runtime after review, rerun a saved story on the
merged branch, with use_canva_images=false and review_approved=false.
This will create media and may use external image/TTS credits: **obtain
explicit approval first**.

## Listen for / inspect

1. No abrupt timbre changes between Long scenes or at a Shorts boundary.
2. Voice pronunciation and pacing remain consistent from first to last
   narration line (especially the old shorts_chunk_5 failure point).
3. out/voice_episode_report.json: one engine, mixed_engines=false.
4. All audio files are valid rather than silent placeholders.
5. Replay cache hits should rise when model, voice and text are unchanged.

## Deferred — next reviewed PRs

- Same-script 30-second *local* A/B voice samples for Indic Parler-TTS
  and IndicF5, CPU runtime measurement, voice selection by listening.
  These are NOT generated in this PR (and no paid API used).
- Voice/music sidechain, de-essing and -14 LUFS / -1 dBTP mastering,
  with measured mastering QC.
- Cross-render content strategy, caption alignment, thumbnail brand
  template and release-wide episode_report.json.

## Pro / con

Pro: the five-second Gemini quota failure can no longer silently switch
the narrator in the same video. Cache avoids repeating successfully
generated clips when returning to the same model/voice/text.

Con: if the first engine fails late, the entire episode is synthesized
again, which consumes extra CPU time and potentially fallback bandwidth.
The strict contract also rejects silent placeholder narration.
