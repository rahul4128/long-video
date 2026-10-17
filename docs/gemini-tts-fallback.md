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

A missing key, exhausted free-tier quota, 401/403/404, malformed or missing audio,
or FFmpeg failure falls back to local **Kokoro**, then **Edge-TTS**.
Quota/credential failures stop further Gemini attempts in the same renderer job.

## Low-cost smoke test (recommended before a full video)

Visit https://github.com/rahul4128/long-video/actions/workflows/render.yml

1. Run workflow on **visual-director-v2**.
2. Choose `gemini_tts_smoke_only=true` and `canva_smoke_only=false`.
3. Run once: it requests **one** short Hindi audio sample, not a full video.
4. Open the completed job's `gemini-hindi-voice-<run_id>` artifact; listen to
   `gemini_tts_smoke.mp3` and evaluate Hindi pronunciation, pacing and emotion.
5. If it fails because of `missing_key`, set the secret and retry a **new**
   workflow run. If a 429 occurs, wait for quota reset; do not keep retrying.

The smoke step never creates a YouTube upload and never calls Make.

## Configuration

- `AUDIO_TTS_ENGINE=gemini` (Make passes this via workflow_dispatch `tts_engine`)
- `GEMINI_TTS_MODEL=gemini-3.8-flash-tts` (repo variable, optional)
- `GEMINI_TTS_VOICE=Kore` (repo variable, optional; can change after listening)
- `GEMINI_TTS_MAX_REQUESTS=12` (repo variable, optional, hard cap <=40)
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
