# Velvet Bunny Instagram Reel upgrade

## Automated fixes for future Reels

1. Dedicated Remotion Instagram composition: native 1080x1920 (9:16), sourced from the already selected portrait Shorts assets, never the 1920x1080 long.
2. Noto Sans Devanagari and Chromium rendering for text rather than naive FFmpeg drawtext.
3. Safe-area captions: 250px top / 330px bottom / approximately 84px side margins; karaoke grouped in 4-word phrases.
4. Hook and cover: 2–4 complete Hindi words, max 18 characters per line and two lines, preserving conjuncts/matras.
5. Instagram cover source: QC-approved first portrait scene, cropped with FFmpeg to 1080x1920. Visually inspect deity/source accuracy.
6. Visible hook in the first rendered frame and platform-specific end card: फॉलो • सेव • शेयर.
7. Scripted niche guard rejects generic diet/fasting self-help topics rather than narrating the origin katha.
8. Reject spoken YouTube-only Subscribe in Instagram narration.
9. Target 20–40 seconds; withhold overlong/too-short reels for editorial revision rather than cutting a story mid-sentence.
10. Topic-specific Hindi caption and 3–5 tags with no AI, Canva or Instagram API calls.
11. Verify Instagram video and cover dimensions, audio track and duration before attaching them to the review-only draft release.

## Existing account: manual fixes not reachable through GitHub

This code will not automatically change an old reel, account bio, Highlights, pinned Reel, or replies to past comments.

Suggested bio:
📖 रामायण • महाभारत • देवी-देवताओं की कथाएँ
🎬 हर Reel में एक नई कथा
▶ पूरी कथा YouTube पर

Replace the raw long YouTube URL in the bio with a properly labelled link using Instagram's profile links UI. Add Highlights named नवरात्रि, रामायण, कथाएँ, श्लोक. Pin 3 niche-relevant Reels. Consider archiving or deprioritizing clearly off-niche content, but do not bulk-delete without reviewing the impact.

At Instagram upload select instagram_cover.jpg manually and ensure both the cover crop and video are safe in the profile grid. Use instagram_post.txt as a starting caption. Reply personally to comments, for example: जय माता दी 🙏 आपको इस कथा का कौन-सा भाग सबसे अच्छा लगा?

## Free tests and tomorrow's planned manual review

No production render, model API, Canva or Make run was triggered for this PR. Tomorrow, after reviewing PR #6 (voice) and the Instagram PR, run local offline tests:

    python -m unittest discover -s tests -p 'test_instagram_reel.py' -v
    python -m unittest discover -s tests -p 'test_episode_voice.py' -v

The GitHub render workflow supports saved-story preflight (no media generation): reuse_run_id=39934556546, preflight_only=true, use_canva_images=false, canva_smoke_only=false, gemini_tts_smoke_only=false and review_approved=false.

A full render may still use stock, image generation, TTS and/or Canva credits. It has NOT been scheduled or approved here.

## Pros and cons

Pro: full-screen portrait, Hindi-safe graphics and stronger topical consistency are enforced through a separate Instagram QC gate without affecting YouTube Long and Shorts.

Con: some episodes will be marked review_required and deliberately NOT create an Instagram Reel if their duration, spoken CTA, hook or cover is poor. The extra Remotion video export consumes GitHub CPU even when the same scene assets are reused. No code can guarantee more followers without measuring real outcomes.

Review the first 2 seconds, first visual, 30-second retention, saves, shares, and follows per 1000 views over comparable post-publication windows. Instagram's distribution cannot be guaranteed.
