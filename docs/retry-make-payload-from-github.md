# Retry failed devotional renders without rerunning Make / Gemini

The approved story can be cached as a GitHub artifact **before** code validation or any external visual/TTS generation. A new GitHub workflow_dispatch can then pick up that same approved script using only the prior GitHub run ID.

## One-time recovery for the old failed run #162 (38494884403)

This run was created **before** the payload-cache feature. Its REST run metadata has no original input body and its artifact listing is empty. The old run ID therefore **cannot** be used with `reuse_run_id`. Also, using GitHub's "Re-run failed jobs" reuses the *old source commit* and does not apply new code fixes.

The complete original story **is still in Make's successful execution data**, subject to Make's log retention:

1. Open the oflifepart31 Video Generator scenario **7889870** and its successful execution **bfa21f8a5c9e431c956a0ab86c7d8edc** (October 14, 2026).
2. Inspect module **5 (JSON / Create JSON)** and copy its COMPLETE output field named `json`. This is the existing GitHub dispatch envelope, which contains `ref`, `inputs.payload` (approved script), and `inputs.pipeline`. Alternatively, module **3** output `json` holds just the story.
3. Open **Actions → Render Devotional Video (Long + Shorts) → Run workflow**, select branch `visual-director-v2`. Paste the copied JSON into `payload`. Use `pipeline=visual-director-v2-oflifepart31`. Set `preflight_only=true` and `review_approved=false`.
4. This test-only run archives `approved-story-<new-run-id>` before doing Python and TypeScript preflight; it does not generate videos or consume Make/Gemini tokens. It also does not publish to YouTube.
5. After the preflight finishes, start another **new** GitHub workflow run on `visual-director-v2` with `payload` blank, `reuse_run_id=<new-run-id>`, `preflight_only=false`, `review_approved=false`. This runs a full Long + Shorts generation with the **same saved approved script** and **current GitHub code**, without rerunning Make.
6. Future failed full renders can be retried by starting yet another new run with the most recent `approved-story-<id>` artifact. Artifacts retain 14 days by default.

**Privacy**: The approved script is saved to this repository's GitHub Actions artifacts. It is not a credential store. Never include OAuth refresh tokens, API keys, private contact details or passwords inside a script payload.

## Cheaper initial checks (no story needed)

Run `.github/workflows/ci-preflight.yml` from Actions on the branch; or set `preflight_only=true` and leave `payload` blank in `render.yml`. This checks Python, audio, editing, TypeScript and Remotion component imports; *no* AI generation is invoked.

## What it saves

- **Make.com credits:** no re-run of the generator's 18 modules
- **Gemini quota/tokens:** no repeat story research, challenge, critique, final judge or script QA
- **GPU:** not used; GitHub runners are CPU-only
- **GitHub runner time:** early failing code tests stop *before* expensive asset/video jobs
- **AI media/TTS credits:** skipped on preflight-only runs. A full retry still generates media unless the corresponding assets from an earlier successful assets stage are reused separately.

Rerunning an old GitHub job is different from a new workflow run using a cached payload; the latter is necessary to obtain the corrected code.

## Review gate

Normal Make dispatch and manual replay default to draft review releases; Make/YouTube publication is not approved unless the user explicitly enables `review_approved=true` in a separate, intentional dispatch. Cached replays with `review_approved=true` are rejected at preflight to avoid accidental auto-publishing.
