# Instagram release: reuse the existing YouTube Short

As requested by the creator, Instagram must NOT generate a second video,
narration, separate thumbnail or extra scene images. Use the existing
1080x1920 YouTube Short file final_video_shorts.mp4, and select the
thumbnail_shorts_final.jpg image as the manually reviewed Instagram cover.

The GitHub draft release's upload guide and the optional Reel pack use the
same caption builder. The AI must supply separate, story-specific English
Instagram captions for the Short/Reel and Long video, with the approved primary
keyword, relevant secondary keywords and episode-specific hashtags. The packer
must preserve that copy instead of replacing it with a topic template. Older
cached episodes may fall back to an English episode description or keyword; it
must never leak a Hindi caption or fabricate story details.

Hindi remains in the spoken video and YouTube-facing title/description, using
natural day-to-day words for viewers in India. YouTube description hashtags
are de-duplicated against the existing description before upload.

No Instagram API posting is automatic. Inspect the 9:16 crop, captions,
deity identity and spoken narrator changes before posting.

Pros: no duplicate rendering or narration credits, simple cross-posting.
Con: YouTube-optimized caption safe areas may overlap Instagram controls;
check the Reel preview before uploading. Use neutral spoken CTA in the
shared video.

Tests:
python -m unittest discover -s tests -p 'test_instagram_release_caption.py' -v
