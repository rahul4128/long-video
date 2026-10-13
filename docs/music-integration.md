# Free music director — visual-director-v2

## What changed

The existing Make.com Visual Director scenario dispatches to this GitHub branch already, so **no Make scenario edits or new API keys** are needed. After narration and visual selection, \`generate_assets.py\` calls \`music_engine.attach_music(...)\`. The selector infers each scene's tone from its existing director and visual-beat metadata and writes a verified MP3 to \`public/audio/music/\`. Remotion attaches it to the corresponding scene, fades it at scene boundaries and ducks it while the narrator is speaking. The video is still review-only by default.

Sources are tried in this order:
1. Openverse audio search; accept ONLY exact CC0 records with source URL.
2. Wikimedia Commons search; accept ONLY recordings whose file metadata says CC0 1.0 and links to the CC0 declaration.
3. An **approved manual music library**, checked for source, explicit commercial cross-platform rights, and SHA256.
4. Original synthetic ambient pads built entirely with FFmpeg (no third-party recording).

**No Freesound API or automated Mixkit/YouTube scraping.** YouTube Audio Library downloads require YouTube Studio and aren't automatically treated as cleared for Instagram. Mixkit's free *music* license permits monetized YouTube and Instagram/social posts, but downloads need to be individually reviewed/approved. Remote CC0 labels do not guarantee a particular recording isn't mislicensed or Content ID claimed. Review the tracks and evidence **before publishing**.

## Approved Mixkit or CC0 files (optional)

Add individual audio files (MP3, WAV, OGG, FLAC; max 14 MB) and a manifest at \`public/audio/music/approved/manifest.json\`, or point \`APPROVED_MUSIC_DIR\` to a directory with the same structure. Example:

\`\`\`json
[
  {
    "file": "approved_flute.mp3",
    "title": "Verified flute instrumental",
    "creator": "Recorded credit",
    "source_url": "https://mixkit.co/free-stock-music/",
    "license": "Mixkit Stock Music Free License",
    "license_url": "https://mixkit.co/license/modal/musicFree/",
    "platforms": ["youtube", "instagram"],
    "moods": ["devotional", "emotional"],
    "approved": true,
    "sha256": "REPLACE_WITH_ACTUAL_LOWERCASE_64_CHARACTER_SHA256"
  }
]
\`\`\`

Use the direct **recording/source page**, not just a generic catalog URL. To compute a hash, run:

\`\`\`bash
sha256sum public/audio/music/approved/approved_flute.mp3
\`\`\`

For CC0 tracks use \`"license": "CC0-1.0"\` and \`"license_url": "https://creativecommons.org/publicdomain/zero/1.0/"\`. Do **not** mark CC BY, CC BY-NC or "free to listen" as CC0, or add any unverified track. The SHA256 prevents a different recording from silently inheriting an approved license.

## Settings

- \`MUSIC_REMOTE_DISCOVERY_ENABLED=true\` (default): enable live CC0 discovery; caps 6 searches and 9 media attempts total, and falls back offline if network/rate limits interfere.
- \`MUSIC_REMOTE_DISCOVERY_ENABLED=false\`: select verified local library first; otherwise generate original tonal music without any network calls.
- \`APPROVED_MUSIC_DIR\`: optional absolute/path-to-local approved directory (default \`public/audio/music/approved\`).
- \`out/music_license_report.json\`: each selected track's source, claimed license, SHA256, duration and which Long/Shorts scenes use it. Included as an asset in the draft GitHub Release.
- \`out/metadata.json\` / \`out/youtube_pack.md\`: rights review notice and music/source details.

## Tomorrow's test

1. Run the Primary **Devotional Long Video Generator v2 - Visual Director Test** scenario that dispatches to \`visual-director-v2\`.
2. In GitHub Actions, confirm **Check music licensing and mood selector regressions** and **Validate music files, copyright evidence and scene coverage** pass.
3. Download \`music_license_report.json\` from the draft release; listen to the selected score, confirm it is instrumental, check source claims and the license for both YouTube + Instagram.
4. Review video at the hook, middle and ending: no loud music over Kokoro, scene transitions are smooth, SFX are distinguishable.
5. Publish only after completing licensing, audio/video and Content ID review. A source's CC0 declaration reduces risk but is not a guaranteed clearance.

The Make scenarios remain paused until you choose to run them. The existing sound-effects subsystem, subtitles, story decisions, thumbnails, and video QC are preserved.
