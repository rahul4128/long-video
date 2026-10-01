# Puchu & Pihu — manual upload workflow

Primary Make scenario 7709916 fetches episode history, generates a Hindi story package with Gemini, parses JSON, and dispatches the existing render.yml workflow with ref=puchu-pihu-manual. All implementation changes live on that separate branch.

The renderer uses original procedural 2D lovebirds, expressive eyes, beak movement during dialogue, wing movement, bobbing, props and backgrounds. This is simple limited animation, not generative cinematic video or phoneme-accurate lip sync. Character appearance stays fixed. Scene counts vary with the script.

Kokoro provides three Hindi voices locally on the GitHub CPU runner. Output duration follows measured audio, never the model's declared duration. Content QC rejects Romanized Hindi, short scripts, missing speaker IDs and duplicate lines. Media QC checks actual duration, dimensions and audio streams. A failed QC does not produce a finished package.

Download the puchu-pihu-manual artifact from the completed GitHub Actions run. It contains a ZIP with long_story.mp4 (1280×720), short_reel.mp4 (1080×1920), one shared thumbnail.jpg, two Hindi SRT files, story.json, metadata.json, upload_pack.md and QC reports. The Short is also the Instagram Reel. Nothing uploads to social media.

The optional Canva step uses existing CANVA_CLIENT_ID, CANVA_CLIENT_SECRET, CANVA_REFRESH_TOKEN and REPO_SECRETS_TOKEN repository secrets. Refresh token rotation is serialized with the existing canva-token-rotation concurrency group. The new rotated token is persisted through the established secret rotation script. If Canva authentication or upload fails, downloadable files remain available and can be imported manually. It uploads the two finished videos and creates one editable shared-thumbnail design; Canva does not generate daily cinematic character animation in this workflow.

Completed episode summaries are kept in episodes_history.txt on this branch, capped at the latest 60. This avoids the Make data-store organization-context failure. Daily Make activation should happen after a complete end-to-end render passes.

Review both videos, voice pronunciation, caption placement, character actions and thumbnail crop before manual publishing. Inspect available Make/Gemini/GitHub quotas; the workflow uses the services' existing allowances and cannot guarantee unlimited free operation.

Current validation: Python compilation, workflow YAML parsing, malformed payload rejection and both landscape/vertical encoder smoke tests passed. Gemini 2.5 Flash generation and JSON parsing passed in the isolated prototype. Full production narration, Hindi font output, Canva upload and Actions artifacts await the Primary Make GitHub credential authorization; first full test failed at history fetch with HTTP 401. Final daily scenario is inactive pending that test.
