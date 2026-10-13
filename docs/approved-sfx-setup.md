# Approved sound effects for devotional videos

The pipeline already uses Freesound (CC0-only) and FFmpeg synthetic fallbacks. An optional **approved local library** is now checked first by `sfx_engine.py`. Nothing changes unless `APPROVED_SFX_DIR` is configured.

1. Download a few individual sound effects yourself from https://mixkit.co/free-sound-effects/ . Check each item's **Sound Effects Free License**, or use verified CC0 effects. Do not scrape or mass-download Mixkit.
2. Store the approved files in a private directory on the build runner or in a secured artifact. Do not distribute raw Mixkit files as a standalone asset pack.
3. Create `manifest.json` in that directory, e.g.:

```json
{
  "temple_bell": {
    "file": "temple-bell.wav",
    "license": "Mixkit Sound Effects Free License",
    "source_url": "https://mixkit.co/free-sound-effects/"
  }
}
```

Use the **actual individual source page URL** instead of the example category URL before enabling an asset. Only the following license labels are accepted: `Mixkit Sound Effects Free License`, `CC0 1.0`.

4. Set `APPROVED_SFX_DIR` to the absolute directory path for the `generate_assets.py` job. On GitHub-hosted runners, an external approved library must be restored into the job before that step; environment variables alone do not transfer files.
5. Test a private render and listen to the result before enabling the library routinely. If a file is missing, the existing Freesound/FFmpeg fallback remains active.

Pexels footage search is already present in `generate_assets.py`. Set the existing `PEXELS_API_KEY` repository secret for API use. Cite Pexels and creators when possible, and check rate limits. No new API key was created by this change.

This opt-in feature does not publish to YouTube or activate Make scenarios.
