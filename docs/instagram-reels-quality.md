# Instagram release: reuse the existing YouTube Short

As requested by the creator, Instagram must NOT generate a second video,
narration, separate thumbnail or extra scene images. Use the existing
1080x1920 YouTube Short file final_video_shorts.mp4, and select the
thumbnail_shorts_final.jpg image as the manually reviewed Instagram cover.

The GitHub draft release's upload guide includes a standalone English-only
Instagram caption with English hashtags and a Follow/Save/Share CTA.
Hindi remains in the spoken video and YouTube-facing title/description, using
natural day-to-day words for viewers in India.

No Instagram API posting is automatic. Inspect the 9:16 crop, captions,
deity identity and spoken narrator changes before posting.

Pros: no duplicate rendering or narration credits, simple cross-posting.
Con: YouTube-optimized caption safe areas may overlap Instagram controls;
check the Reel preview before uploading. Use neutral spoken CTA in the
shared video.

Tests:
python -m unittest discover -s tests -p 'test_instagram_release_caption.py' -v
