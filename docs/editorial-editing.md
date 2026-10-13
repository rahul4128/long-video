# Documentary-style editing director (CPU-only)

The Visual Director now prepares a **narration-aware editorial cut plan** in \`editing_director.py\` after the media clips, story timing, and music are available. Remotion reads shot metadata in \`src/Scene.tsx\` and renders additional motion/treatment, documentary annotations (\`src/EditorialAccent.tsx\`), and dynamic word emphasis (\`src/Subtitles.tsx\`).

## Editing grammar

| Story reason | Editing instruction | Why it is useful |
| --- | --- | --- |
| First 0–2 seconds | First visual is visible immediately; no black fade; hook overlay retained | Viewer sees a clear promise without intro delay |
| Question/curiosity | Clean cuts with brief, derived-from-script editorial label (when available) | Emphasizes what viewer should notice |
| Visual evidence/detail | Purposeful closer framing and reduced motion | Explains an object/action rather than random motion |
| Revelation/climax | One restrained blur-cut and small push, not constant random transitions | Adds a meaningful pattern break |
| Emotional/peaceful moment | A gentle hold/low-motion treatment | Makes silence or pauses intentional |
| Normal explanation | Mostly clean cuts, few crossfades | Reduces "AI template" look |
| Subtitles | Small chunks with per-word spoken emphasis | Better comprehension on mobile |

Existing SFX, licensed music, Hindi/Kokoro narration, beat-specific footage retrieval, media licensing, visual QC, and 9:16/16:9 protections are unchanged. Effects use CSS transforms, simple gradients, typography and the existing Remotion/FFmpeg runner; **no GPU, paid plugin, video API or new Make module** is needed.

## Safeguards

- All overlays are taken from the *actual narrated script*: the editor does not hallucinate scriptures, ritual claims, quotes, or facts.
- Never change the source clips, narration text or synchronized shot boundaries in this stage.
- At most one new editorial label and one reveal blur-cut per scene.
- Don't create an annotation when the selected beat already has the existing \`emphasisText\`.
- Don't place a new overlay over the first opening hook.
- Movie-style text placement avoids the bottom caption region.
- Report: \`out/editing_qc_report.json\`; bundled with generated assets and included in the draft GitHub Release.
- Workflow tests: \`tests/test_editing_director.py\`; runtime gate: \`scripts/validate_editing.py\`.
- Repo variable \`EDITORIAL_EDITING_ENABLED=true\` by default; set to \`false\` to return to legacy shot-edit planning, without deleting existing media/caption features.

## Tomorrow's test (do not run automatically)

Trigger your existing Primary Make scenario **Devotional Long Video Generator v2 - Visual Director Test**. It already dispatches GitHub \`render.yml\` on \`visual-director-v2\`.

1. Confirm Python syntax check, test_editing_director, and \`Validate narration-led editing and caption budgets\` pass.
2. Download \`editing_qc_report.json\` from the **draft review Release**, alongside the videos, music license audit, and QC report.
3. Watch the first frame, the 5–10 second hook, a normal explanation, the climax and closing of **both** Long and Shorts. Verify captions are correctly timed and readable, no unnecessary annotations obscure deities or evidence, and sound effects aren't overpowering the voice.
4. Compare the new short to the prior one: hook retention, average watch time, saved/shares/reposts and comments after enough reach. Do not compare views alone.

This is not an exact copy of the Instagram reference: the linked Reel's actual frames were inaccessible in this chat. The delivered look is an original, documentary-inspired editing grammar for your devotional stories, not a frame-for-frame reproduction.
