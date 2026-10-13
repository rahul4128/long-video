# P0 production finishing: Final audio mastering and color continuity

Branch: \`visual-director-v2\`. Primary Make scenario stays **paused**; no generation runs are started by these commits.

## Final audio mastering (both Long and Shorts)

The previous pipeline mastered individual Kokoro narration segments but not the *rendered combination* of voice, dynamic music and SFX.

New \`scripts/master_final_audio.py\` executes **after Remotion rendering and before the video artifact is uploaded**:
1. Confirm final MP4 has both audio and video streams, valid duration and audible integrated loudness.
2. Run FFmpeg \`loudnorm\` to aim for **-16 LUFS / -1.5 dBTP**, encoding the **audio only to AAC**, with \`-c:v copy\`.
3. Verify the resulting file's audio loudness and true peak using a separate FFmpeg pass; reject silent or >11-second internal-silence problems, large duration changes or missing streams.
4. Generate \`out/audio_master_long.json\` and \`out/audio_master_shorts.json\`. Only on success atomically replace the video with the mastered version.
5. Media-QC downloads the *actual* mastered videos and independently measures them again with \`scripts/validate_final_audio.py\`, before any review release is created.
6. The draft release includes both audio audit JSON files as assets, along with the final mastered MP4s.

Tolerance: -19 to -13 LUFS and true peak <= -0.75 dBTP, leaving room for source dynamics and AAC encoding variability. No AI speech re-synthesis, vocal style substitution, GPU or paid API. Music licensing and manual review requirements remain unchanged.

**This controls whole-program loudness**, but cannot prove perfect creative dialogue-to-music intelligibility from a single numerical measure. Listen during final QC.

## Color and continuity (Long + Shorts)

\`color_continuity.py\` samples only one **36x36 pixel** frame per unique selected source with a maximum of 3 FFmpeg sampling workers. It computes episode-specific median brightness and color spread for each output format and attaches bounded, non-destructive \`shot.colorCorrection\` values:

- Brightness correction from **0.92 to 1.08**.
- Saturation correction from **0.95 to 1.05**.
- Extreme low-key / bright scenes remain unchanged to preserve devotional intent.
- Sudden adjacent-shot brightness shifts and strong red-blue white-balance differences are flagged in \`out/color_continuity_report.json\`.
- This is **not a full chromatic white-balance recalibration** or automatic shot recognition. It deliberately flags major color casts instead of inaccurately changing the deity's skin/ornament colors.
- Remotion applies restrained correction via CSS to the existing source footage and images; original source files are untouched.
- \`scripts/validate_color_continuity.py\` verifies the report and correction limits before renders.

Scripts are CPU-only and require no new keys, software subscription or GPU. Existing 16:9/9:16 framing QC and story/deity identity QC remain in place.

## CI and rollback

Regression tests:
- \`tests/test_color_continuity.py\`: synthetic photographs, bounded corrections, intentionally dark images, unsafe media paths and disable switch.
- \`tests/test_master_final_audio.py\`: synthetic video+audio processing, unchanged video codec/duration, final audio metrics and silent-audio rejection.

Repo variable \`COLOR_MATCH_ENABLED=false\` disables the per-shot color-match pass and its render props, with no effect on narrative video editing. Final audio mastering is required for both rendered outputs by default. To disable audio mastering for an isolated debugging run, revert the mastering workflow commit rather than bypassing downstream media QC.

## Next test

1. Keep Primary Make scenario paused until ready, then manually trigger as previously planned.
2. Check \`color_continuity_report.json\`, both \`audio_master_*.json\` and existing visual/music/editing audit reports.
3. Play the first five seconds, climax and ending, listening for steady narration level and clean music ducking.
4. Watch for overcorrection and unrelated abrupt color shifts in neighboring shots. A flagged extreme color mismatch should be reviewed rather than masked by aggressive filters.
5. Only approve publication after listening/viewing the outputs and checking source music rights.

No actual end-to-end Long/Shorts video render has been executed by these commits. The tests are configured to run on the next GitHub Actions execution.
