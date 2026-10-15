# Canva AI image fallback — visual-director-v2

This optional fallback runs **after** Pexels/Pixabay/Coverr retrieval and the
existing Hugging Face / Pollinations / Cloudflare image attempts. It runs
**before** the existing framing gate, storyboard review and Remotion renders.
No placeholder is allowed to silently pass the narrative visual QC gate.

Canva Connect Image Generation is a preview API; generation requires an
authenticated Canva user with the `asset:write` OAuth scope and consumes the
user's Canva AI credits. The app may also receive `permission_denied` if
image generation is not enabled for that Canva integration.

## Safe one-image test (no Make, no YouTube, no videos)

1. Open GitHub → **Actions** → **Render Devotional Video (Long + Shorts)** →
   **Run workflow**, select `visual-director-v2`.
2. Turn **canva_smoke_only** on, leave all other optional flags off, and run.
3. Download the `canva-smoke-image-<run_id>` artifact to visually check
   composition. The test has one Canva generation request only. It does not
   run preflight, story generation, narration, render, media QC or publishing.
4. If Canva auth fails, check `CANVA_CLIENT_ID`, `CANVA_CLIENT_SECRET`,
   `CANVA_REFRESH_TOKEN`, and `REPO_SECRETS_TOKEN` in GitHub Actions
   Secrets. Do not paste them into a chat or a log. The refresh token rotates.
5. If the API returns `missing_scope`, authorize `asset:write` again.
   If it returns `permission_denied` / `Image generation is not enabled`,
   verify feature availability for the specific Canva integration.

Alternative: the standalone `Canva Scene Image Smoke` workflow exists on
this feature branch, but GitHub typically only registers newly added manual
workflows once they are on the repository default branch; the existing Render
workflow option above avoids that limitation.

## Opt-in for manual full render

Use **Run workflow** on `visual-director-v2`; set `use_canva_images=true` and
`canva_image_max_per_run=1` for a credit-bounded first test. The other
generation providers still run before Canva. Set `review_approved=false` and
`privacy=private` to prevent public YouTube publication. Review outputs
and quota before raising the Canva limit.

## Enable for scheduled/Make dispatches

GitHub → Settings → Secrets and variables → Actions → **Variables**:

- `CANVA_IMAGE_FALLBACK_ENABLED=true`
- `CANVA_IMAGE_MAX_PER_RUN=1` initially, then adjust only after a reviewed
  credit/cost test

Use variables for non-secret toggles only. Tokens remain in encrypted Secrets.
The production workflow refreshes Canva OAuth inside the `generate-assets`
job (rather than waiting until post-render Canva finishing).

The image cap is shared across all concurrent Long, Shorts and thumbnail
generation tasks in one run. Once exhausted, the existing fail-closed quality
behavior continues rather than replacing accurate scenes with generic artwork.
Each output is downloaded immediately and converted to a real JPEG/PNG file;
signed Canva URLs are never stored as permanent scene sources.

## Offline test

`python -m unittest discover -s tests -p 'test_canva_image_provider.py' -v`

The CI preflight includes these tests. The tests do not call Canva or consume
credits.
