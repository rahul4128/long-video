# Gemini Hindi Narration — oflifepart31

This is an opt-in voice upgrade for the GitHub CPU-only renderer.
It preserves existing scene timing, visual matching, Remotion editing, Kokoro,
Edge-TTS, thumbnail, Canva fallback, and human review controls.

## Make.com

The **Devotional Long Video Generator v2 - Visual Director Test - oflifepart31**
scenario, module **5** (workflow_dispatch body), passes:
- `tts_engine: "gemini"`
- `use_canva_images: true`
- `canva_image_max_per_run: "1"`

The Make schema `629392` includes the optional `tts_engine` field.
No Gemini voice audio is synthesized by Make itself: the GitHub workflow does it.

## One required GitHub secret

Visit: https://github.com/rahul4128/long-video/settings/secrets/actions

Set **GEMINI_API_KEY** to a Gemini Developer API key from
https://aistudio.google.com/apikey (do not paste it into logs or chat).
The Make.com Gemini connection does not automatically supply this key to GitHub.

A missing key, exhausted free-tier daily quota, 401/403/404, malformed or missing audio,
or FFmpeg failure falls back to local **Kokoro**, then **Edge-TTS**.
Temporary HTTP 429/503 rate limits get up to 2 additional requests after bounded
cooldowns (20s, then 40s; respecting Retry-After, max 90s).
Requests are serialized with a 6-second minimum gap by default.
A confirmed DAILY quota is **not retried**. After retry failure, later scenes
fall back to Kokoro/Edge instead of looping. Narrator continuity across scenes
still needs human review if Gemini ran out partway through the video.

## Low-cost smoke test (recommended before a full video)

Visit https://github.com/rahul4128/long-video/actions/workflows/render.yml

1. Run workflow on **visual-director-v2**.
2. Choose `gemini_tts_smoke_only=true` and `canva_smoke_only=false`.
3. Run once: it requests **one** short Hindi audio sample, not a full video.
4. Open the completed job's `gemini-hindi-voice-<run_id>` artifact; listen to
   `gemini_tts_smoke.mp3` and evaluate Hindi pronunciation, pacing and emotion.
5. If it fails because of `missing_key`, set the secret and retry a **new**
   workflow run. 429/503 temporary rate limits cool down automatically.
   A daily quota error requires waiting for Google's quota reset.

The smoke step never creates a YouTube upload and never calls Make.

## Configuration

- `AUDIO_TTS_ENGINE=gemini` (Make passes this via workflow_dispatch `tts_engine`)
- `GEMINI_TTS_MODEL=gemini-3.8-flash-tts` (repo variable, optional)
- `GEMINI_TTS_VOICE=Kore` (repo variable, optional; can change after listening)
- `GEMINI_TTS_MAX_REQUESTS=12` (repo variable, optional, scene cap <=40)
- `GEMINI_TTS_MAX_API_ATTEMPTS=18` (hard cap incl. retries, maximum 50)
- `GEMINI_TTS_MAX_RETRIES=2` (additional attempts per scene, maximum 3)
- `GEMINI_TTS_COOLDOWN_SECONDS=20` (20s/40s exponential by default)
- `GEMINI_TTS_MIN_GAP_SECONDS=6` (spaces API requests to reduce bursts)
- `GEMINI_TTS_STYLE` optional voice direction (defaults to Hindi cinematic devotional narrator)

GitHub settings for variables:
https://github.com/rahul4128/long-video/settings/variables/actions

To choose lower latency / potentially cheaper generation, set
`GEMINI_TTS_MODEL=gemini-3.8-flash-lite-tts`.
For explicit Kokoro or Edge-only output, send `tts_engine=kokoro` or
`tts_engine=edge` instead of Gemini.

The output stays MP3 at 24kHz and existing approximate word timing is used
for Gemini/Kokoro. Review exact spoken subtitles before release. Free tier
limits are model/project dependent; do not assume unlimited free narration.

Official schema: https://ai.google.dev/gemini-api/docs/speech-generation
Pricing: https://ai.google.dev/gemini-api/docs/pricing

## Canva token recovery

Canva is **OAuth, not an ordinary API key**. These GitHub Action secrets have
different roles: `CANVA_CLIENT_ID` and `CANVA_CLIENT_SECRET` identify the app;
`CANVA_REFRESH_TOKEN` is **single-use** and must rotate on each refresh;
`REPO_SECRETS_TOKEN` lets the workflow update the rotated GitHub secret.

If you see `invalid_grant: Token lineage has been revoked`, the stored token
cannot be repaired by waiting or retrying.

1. On Ubuntu in the repository, run `node scripts/canva_oauth.js` with the
   SAME Canva client ID and client secret already configured in GitHub.
2. Authorize the Canva app in the local browser.
3. Save the **NEW** refresh token in GitHub Actions Secrets under
   `CANVA_REFRESH_TOKEN`: https://github.com/rahul4128/long-video/settings/secrets/actions
   Never paste secrets into chat or commit them.
4. For a low-cost test, run `canva_smoke_only=true` on `visual-director-v2`;
   this uses one Canva image credit and verifies the token exchange.
5. Do not start multiple renders that use an older token snapshot.

With Canva image fallback enabled, the asset-generation job now refreshes
Canva **once**, rotates the GitHub secret, and passes an **encrypted short-lived
access token** to the finishing job through a one-day GitHub Actions artifact.
Finishing decrypts it using the existing `REPO_SECRETS_TOKEN`; it does not
attempt to refresh the same original single-use token again.
No plaintext token is written to artifacts. If Canva fallback was not enabled,
finishing may refresh normally.

A completely revoked Canva token still needs a NEW interactive OAuth
authorization: no existing API key or code change can override that.

Official docs: https://www.canva.dev/docs/apps/rest-apis/authentication/
