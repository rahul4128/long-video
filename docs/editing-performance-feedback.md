# Closed-loop video editing style feedback (Primary + oflifepart31)

## What happens after a successful render

1. Primary and oflifepart31 Make Devotional Generators dispatch to \`visual-director-v2\` and label their workflows with \`visual-director-v2-primary\` or \`visual-director-v2-oflifepart31\`.
2. GitHub's generate-assets stage chooses an editing style from verified story context and optional previously measured evidence.
3. Remotion renders Long and Shorts, then independent media QC verifies sound, visuals and final MP4 files.
4. **Only after media QC passes**, \`scripts/render_style_attribution.py\` saves the actual editing style, exact Long/Shorts titles, correlationId, GitHub run ID and UTC render date in \`data/render_editing_history.json\`. This is **not** proof of a YouTube publication.
5. Each account's existing YouTube Performance Sync continues to run normal analytics and update its own content-history record. After module 112, new native Make JSON serializers (129–132) prepare actual 30-day YouTube Analytics rows (114) and the ID/title/publication metadata from YouTube Data API (111).
6. Make module 127 builds an automatically escaped JSON envelope, and module 128 sends it to GitHub workflow \`.github/workflows/editing-feedback.yml\` via the existing account's GitHub connection.
7. The feedback workflow runs \`scripts/ingest_editing_feedback.py\`. It joins only **exact normalized video titles** and unique 11-character YouTube IDs to successfully rendered GitHub-attributed titles. The video must have been published after the render, be 7–45 days mature, and have >=100 real views. Duplicate titles and unmapped IDs are rejected.
8. Signals are calculated separately for Long and Shorts and require >=3 distinct mature videos per style. Metrics come from YouTube Analytics' \`averageViewPercentage\`, \`views\`, \`shares\`; average view percentage over 100 from Shorts rewatches is capped to 100 for comparison and raw value is retained in the audit.
9. Results are persisted separately: \`data/editing_style_signals_primary.json\`, \`data/editing_style_signals_oflifepart31.json\`. Audit trails \`data/editing_feedback_audit_*.json\` explain exactly which videos matched and which were excluded.
10. On the next video, \`editing_style_engine.py\` loads its account-specific signals; *only* story-compatible styles may influence the edit. No three-video group means no style recommendation, just the narrator/story preset.

## Important honesty and limitations

- This fixes the **data path and structural attribution**. It does not manufacture historical style labels for old videos. Early runs may show 0 eligible groups, correctly, until three new, comparable videos mature.
- Manually changed YouTube titles, videos published before the render, videos outside the current top-50 YouTube Analytics sample, and ambiguous repeated titles will be excluded. These conditions are intentional fail-safe checks.
- YouTube Analytics is observational, not proof that the editing style caused retention changes. The recommendation must preserve story-topic fit, devotional imagery and factual sourcing.
- These are **two account scopes** even if they access the same channel; source inputs must be independently verified before any cross-channel conclusion.
- Performance Sync now uses 4 additional Make \`Transform to JSON\` modules plus one JSON builder and one GitHub call. It costs more Make operations; it does not introduce a new paid media API.
- The GitHub feedback workflow is **review-data only**; it does not trigger video generation, Make activation, YouTube upload, or automated publication.
- No fresh GitHub action has run from this integration yet; verify the first feedback job's results and Make's JSON output on a controlled run.

## First-run acceptance tests

1. Manually run **Performance Sync oflifepart31 7889997** once after the user confirms operations/limits. It should complete modules 129, 130, 131, 132, 127 and 128. The 201/204 GitHub dispatch response means *accepted*, not feedback-computed success.
2. Inspect \`editing-feedback.yml\` run for successful data parsing, then review \`editing_feedback_audit_oflifepart31.json\` and \`editing_style_signals_oflifepart31.json\`.
3. A zero-match/zero-group result is valid before any new QC-passed videos with a measured style are actually published and matured.
4. Generate one Long + Shorts test in account 7889870 with review approval false. Inspect \`editing_qc_report.json\` and the ledger after both final media QC jobs succeed. Do not publish automatically.
5. Re-run Performance Sync 7+ days after a legitimately published video, and evaluate at least three similar videos per style before drawing conclusions.
6. Repeat independently for Primary if needed. Both Make scenarios remain inactive/paused until manually run.

## Reversibility

- To stop **learning** while retaining story editing, remove/disable the Make Github handoff 128; the old Performance Sync still updates content-history.
- To ignore style learning at render time, set GitHub repository variable \`EDITING_METRICS_SCOPE=none\` only if the workflow input environment override is removed, or temporarily empty the channel-scoped signals JSON file. The default story-based style remains.
- Never hand-edit the audit into claiming unobserved results.
