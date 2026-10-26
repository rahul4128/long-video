# Canva AI image fallback for full devotional episodes

This is the creator-approved configuration of the
`visual-director-v2` video pipeline.

## Full episode image generation

- Manual "Render Devotional Video" runs default to `use_canva_images=true`.
- Make.com `repository_dispatch` runs also enable the Canva AI provider
  automatically (unless a separate workflow variant overrides this policy).
- Canva is tried **first for missing AI-generated devotional beats**, while
  verified stock footage is still allowed. It can create scene imagery for
  Long and Shorts, plus the two approved thumbnail backgrounds. This does
  **not** create new Instagram videos or extra thumbnails.
- The default `canva_image_max_per_run=80` counts **generation jobs**, not
  their successful image downloads. It is clamped to 1–200 and can be
  overridden by a manual workflow input or the repository variable
  `CANVA_IMAGE_MAX_PER_RUN` for Make dispatch.
- This budget is a safety ceiling, **not** a guarantee of remaining Canva
  AI allowance. Every image job can consume user AI credits. Even a paid
  Canva plan may have API-specific AI limits.

## Cooldowns and quota policy

- `CANVA_IMAGE_MIN_GAP_SECONDS=5` globally paces job creations.
  This stays below Canva's 20-create-per-minute API cap.
- `CANVA_IMAGE_MAX_RETRIES=2` retries temporary HTTP 429 rate limits and
  5xx errors with backoff and bounded Retry-After waiting.
- Retries use the *same idempotency key*, so an accepted job is reused
  instead of creating a duplicate job/credit consumption.
- If Canva reports `credit_quota_cooldown`, the runner waits **only** if
  its documented `cooldown_ends_at` is within
  `CANVA_IMAGE_MAX_COOLDOWN_SECONDS=120`. Larger cooldowns fail safely.
- `credit_quota_exceeded` (actual user AI allowance exhaustion), OAuth
  errors and payment-required errors are never repeatedly retried.
- Job status polling uses its own bounded 429/503 retry; no extra
  image-generation POST is made for polling.
- If images cannot be generated, existing story-image relevance and
  mandatory framing checks still apply. No generic abstract filler or
  misidentified deity is permitted.

## No-credit testing and manual render

Offline regression:
`python -m unittest discover -s tests -p test_canva_image_provider.py -v`

To replay the latest failed story without spending another Make story run:
`reuse_run_id=40281049248`, branch `visual-director-v2`,
`tts_engine=gemini`, `use_canva_images=true`,
`canva_image_max_per_run=80`, `review_approved=false`.

The manual render can **still consume** Gemini TTS/API, stock provider and
Canva credits. Do not rerun repeatedly after a genuine Canva credit quota
rejection; wait for the provider's real quota reset or increase legitimately
available account credits. The system does not create new credits.

Output remains **one YouTube Long, one YouTube Short (reused as Instagram
Reel), and exactly one thumbnail per video**. The horizontal Long may also
be shared to Instagram manually; review aspect-ratio handling there.
