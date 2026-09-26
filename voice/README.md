# Your own narration voice (optional, IndicF5)

Put two files here to narrate every video in **your own voice** instead of the Edge AI voice:

- `ref.wav` — 10–15 seconds of YOU reading a calm story line in Hindi. Quiet room, phone mic 15 cm away, no music, mono WAV.
- `ref.txt` — the exact Hindi words you spoke in `ref.wav`, nothing else.

Then in GitHub → Settings → Secrets and variables → Actions → **Variables**, set `AUDIO_TTS_ENGINE` = `indicf5`.

Notes:
- Use only your own voice (or someone who gave written consent).
- On GitHub's free CPU runner this adds roughly 15–30 minutes per run. If anything fails, the run automatically falls back to the Edge voice.
- You must accept the model terms once at https://huggingface.co/ai4bharat/IndicF5 with the Hugging Face account whose token is in the `HUGGINGFACE_API_KEY` secret.
