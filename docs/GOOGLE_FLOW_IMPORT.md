# Using Google Flow MP4s in the existing YouTube pipeline

This is an **optional**, zero-GPU video import. Google Flow does not connect directly
to GitHub Actions through this repository. A user (or a separately operated
ChatGPT Work browser session) must first **generate and save** the MP4s and
upload them to a **GitHub Release** in this repository.

## First safe sample (private YouTube upload only)

1. In ChatGPT Work, sign in to https://flow.google.com/ and open your project.
   Ask it to create **one meaningful ritual/action video hook for the Long**
   (16:9) and **one for Shorts** (9:16). Check that both clips represent the
   day's approved Hindi script accurately. Use only available Free credits.
2. Download the MP4s as **hook-long.mp4** and **hook-shorts.mp4**.
3. On https://github.com/rahul4128/long-video/releases select **Draft a
   new release**, choose an unused tag such as **flow-2026-10-09-sample**,
   attach those two MP4 files, and publish the release. The video URLs
   should look like:

   https://github.com/rahul4128/long-video/releases/download/flow-2026-10-09-sample/hook-long.mp4

4. Once this change is merged to **office-make-clone**, open
   https://github.com/rahul4128/long-video/actions/workflows/render.yml,
   select **Run workflow**, branch **office-make-clone**, and populate:

   * **payload**: your existing approved Make render JSON (same format as
     before; never paste secrets). Using "{}" invokes an old test-script
     fallback and is not a realistic festival video test.
   * **flow_clips_json**: paste JSON below, updating the release tag and
     filenames to your saved clips.
   * **flow_clips_strict**: **true** for the first test, to fail visibly
     if a clip is unavailable instead of silently falling back.
   * **privacy**: **private** for a sample upload, if the Make YouTube
     publishing webhook is configured.

5. Open the resulting Action. In **generated-assets-<run-id>**, inspect
   **out/flow_clip_report.json**; verify both applied entries. The Remotion
   render uses these files from **public/images** and preserves original
   narration, subtitles, thumbnails and remaining shots. Check that the
   final video looks correct before publishing publicly.

### Flow clip JSON

    {
      "long": [
        {"scene": 1, "url": "https://github.com/rahul4128/long-video/releases/download/flow-2026-10-09-sample/hook-long.mp4"}
      ],
      "shorts": [
        {"scene": 1, "url": "https://github.com/rahul4128/long-video/releases/download/flow-2026-10-09-sample/hook-shorts.mp4"}
      ]
    }

The clip replaces the first visual shot of the selected scene, not the
complete voiceover or video. Later visuals stay unchanged. Clips are muted,
resized/cropped to 1280x720 (Long) or 720x1280 (Shorts), and encoded as
H.264 MP4 by FFmpeg. Clips should be 2–45 seconds long and under 100 MB;
a 5–10 second clip is usually enough for an engaging hook.

## Subsequent daily automated Make dispatches

Make's existing repository_dispatch can optionally include a **flow_clips**
object in client_payload with the JSON structure above. Without this
field, there is **no behavior change** and original visuals are used.
Make/ChatGPT Work currently do not automatically upload Flow clips to
the Release; the availability of new clips must be established first.
Never reuse yesterday's Flow URL for a different festival/episode.

Only URLs from the repo's **own GitHub Release** are accepted; URLs
pointing to arbitrary domains are rejected. The import is CPU-only.
The normal render workflow still controls publishing; it does **not**
automatically wait for Work or Flow video generation to finish.

## Verification without Google Flow

There is a separate **Test Google Flow Clip Import** workflow. It
produces synthetic video locally with FFmpeg, exercises import and
scene selection, checks fallback behavior, and **does not upload to
YouTube or use Google/Make credits**.
