"""No-network tests for shared Shorts release copy and Hindi style."""
import re
from pathlib import Path
import unittest

from scripts.youtube_pack import build, instagram_caption_english
from spoken_hindi_qc import assess_text

ROOT = Path(__file__).resolve().parents[1]


class SharedShortsReleaseTests(unittest.TestCase):
    def test_instagram_uses_generated_episode_captions_and_dynamic_keywords(self):
        meta = {
            "shorts_title": "करवा चौथ की कथा: वीरवती के साथ क्या हुआ?",
            "long_video_title": "करवा चौथ व्रत कथा और वीरवती की कहानी",
            "long_video_description": "A long-form retelling of Veervati's Karva Chauth story, exploring the tradition and its central turning point.",
            "shorts_description": "A short retelling of Veervati's first Karva Chauth and the moment the story turns.",
            "instagram_caption": "Veervati's first Karva Chauth takes an unexpected turn when she believes the moon has risen. What happens next is the heart of this traditional vrat katha.",
            "instagram_long_caption": "Discover the story of Veervati and the Karva Chauth vrat katha. This full retelling follows the choices, belief, and turning point behind the familiar tradition.",
            "hashtags": ["#KarvaChauth", "#VratKatha", "#IndianMythology", "#DevotionalStories"],
            "primaryKeyword": "Karva Chauth vrat katha",
            "secondaryKeywords": ["Veervati story", "Karva Chauth tradition"],
        }
        pack = build(meta)
        self.assertIn("reuse both original YouTube videos", pack)
        section = pack.split("## 3. Instagram — reuse both original YouTube videos", 1)[1].split("## 4.", 1)[0]
        self.assertIn("final_video_shorts.mp4", section)
        self.assertIn("final_video.mp4", section)
        self.assertIn("thumbnail_shorts_final.jpg", section)
        self.assertIn("thumbnail.jpg", section)
        self.assertNotIn("final_video_instagram.mp4", section)
        caption = instagram_caption_english(meta)
        self.assertIn("Veervati's first Karva Chauth takes an unexpected turn", caption)
        self.assertIn("#KarvaChauth", caption)
        self.assertIn("#VratKatha", caption)
        self.assertNotIn("A short devotional story", caption)
        self.assertNotIn("Watch till the end for the complete moment", caption)
        full_caption = instagram_caption_english(meta, long_video=True)
        self.assertIn("full retelling follows the choices", full_caption)
        self.assertNotIn("Behind the Karva Chauth tradition is a katha", full_caption)
        self.assertIn("16:9 is horizontal, not native 9:16", section)

    def test_old_episode_fallback_uses_dynamic_description_not_boilerplate(self):
        meta = {
            "shorts_title": "करवा चौथ की कथा",
            "shorts_description": "Veervati hears that the moon has risen, but the story takes a painful turn.",
            "hashtags": ["#KarvaChauth", "#VeervatiKatha"],
            "primaryKeyword": "Karva Chauth story",
        }
        caption = instagram_caption_english(meta)
        self.assertIn("Veervati hears that the moon has risen", caption)
        self.assertIn("#KarvaChauth", caption)
        self.assertIn("#VeervatiKatha", caption)
        self.assertNotIn("Watch till the end for the complete moment", caption)

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
