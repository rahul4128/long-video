"""No-network tests for shared Shorts release copy and Hindi style."""
import re
from pathlib import Path
import unittest

from scripts.youtube_pack import build, instagram_caption_english
from spoken_hindi_qc import assess_text

ROOT = Path(__file__).resolve().parents[1]


class SharedShortsReleaseTests(unittest.TestCase):
    def test_instagram_uses_same_short_and_english_only_caption(self):
        meta = {
            "shorts_title": "वृंदावन में शिव क्यों बने गोपी?",
            "long_video_title": "शिव की कथा",
            "long_video_description": "वृंदावन में भगवान शिव की कथा",
        }
        pack = build(meta)
        self.assertIn("reuse the YouTube Short (9:16)", pack)
        section = pack.split("## 3. Instagram Reel", 1)[1].split("## 4.", 1)[0]
        self.assertIn("final_video_shorts.mp4", section)
        self.assertNotIn("final_video_instagram.mp4", section)
        caption = instagram_caption_english(meta)
        self.assertIn("Lord Shiva", caption)
        self.assertIn("Vrindavan", caption)
        self.assertIn("#DevotionalStories", caption)
        self.assertNotRegex(caption, r"[\u0900-\u097f]")
        self.assertNotRegex(section, r"[\u0900-\u097f]")

    def test_no_false_generic_krishna_default_in_artwork(self):
        src = (ROOT / "generate_assets.py").read_text(encoding="utf-8")
        self.assertIn("episode_subject = (seo_metadata.get", src)
        self.assertIn("Western models", src)
        self.assertNotIn("Lord Krishna radiant divine aura with glowing Sudarshan Chakra", src)

    def test_workflow_only_renders_youtube_long_and_short(self):
        workflow = (ROOT / ".github/workflows/render.yml").read_text(encoding="utf-8")
        self.assertNotIn("final_video_instagram.mp4", workflow)
        self.assertNotIn("InstagramReelComposition", workflow)
        self.assertIn("DevotionalShortsComposition", workflow)
        self.assertIn("per_segment_gemini_first", workflow)

    def test_colloquial_hindi_check_flags_stiff_words(self):
        result = assess_text("तत्पश्चात राजा ने सभी को अवगत कराया।")
        self.assertTrue(any(f["type"] == "written_only_vocabulary" for f in result["flags"]))
        natural = assess_text("फिर राजा ने सबको बताया कि क्या हुआ था।")
        self.assertFalse(any(f["type"] == "written_only_vocabulary" for f in natural["flags"]))


if __name__ == "__main__":
    unittest.main()
