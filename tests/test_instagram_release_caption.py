"""No-network tests for shared Shorts release copy and Hindi style."""
import re
from pathlib import Path
import unittest

from scripts.youtube_pack import _append_missing_hashtags, build, instagram_caption_english, recommend_playlist
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

    def test_playlist_mapping_uses_exact_existing_and_new_channel_names(self):
        cases = [
            ("करवा चौथ 2026: चाँद न दिखे तो व्रत कैसे खोलें?", "करवा चौथ 2026: कथा, सरगी और व्रत नियम | Karwa Chauth 2026", "EXISTS"),
            ("गरुड़ पुराण में पितृ पक्ष का महत्व", "गरुड़ पुराण और पितृ पक्ष | Garud Puran, Pitru Paksha", "EXISTS"),
            ("छठ पूजा में सूर्य को अर्घ्य क्यों दिया जाता है?", "छठ पूजा: कथा, अर्घ्य और परंपरा | Chhath Puja Hindi", "CREATE"),
            ("तुलसी विवाह की पौराणिक कथा", "तुलसी विवाह और देवउठनी एकादशी | Tulsi Vivah Katha", "CREATE"),
            ("काशी की देव दीपावली का महत्व", "देव दीपावली और कार्तिक पूर्णिमा | Dev Deepawali Hindi", "CREATE"),
            ("महाभारत में कर्ण का दान", "महाभारत: धर्म, कर्म और कथाएँ | Mahabharat Stories Hindi", "EXISTS"),
            ("हनुमान जी की अनसुनी कथा", "हनुमान जी की कथाएँ और रहस्य | Hanuman Katha Hindi", "CREATE"),
        ]
        for title, expected, status in cases:
            chosen = recommend_playlist({"long_video_title": title})
            self.assertEqual(chosen["name"], expected)
            self.assertTrue(chosen["status"].startswith(status))

    def test_short_is_added_to_topic_and_shorts_collection(self):
        chosen = recommend_playlist(
            {"long_video_title": "श्रीकृष्ण लीला: वृंदावन का प्रसंग"},
            is_short=True,
        )
        self.assertEqual(chosen["name"], "श्रीकृष्ण लीला और वृंदावन | Krishna Leela, Vrindavan")
        self.assertEqual(chosen["also_add_to"], "पौराणिक Shorts: छोटी कथा, बड़ा अर्थ | Mythology Shorts Hindi")

    def test_upload_pack_contains_exact_playlist_names_and_fixed_instagram_link(self):
        pack = build({
            "long_video_title": "छठ पूजा में सूर्य को अर्घ्य क्यों दिया जाता है?",
            "shorts_title": "छठ में अर्घ्य क्यों देते हैं?",
            "long_video_description": "छठ पूजा की परंपरा और सूर्य अर्घ्य का अर्थ सरल हिंदी में।",
            "shorts_description": "छठ में सूर्य अर्घ्य की परंपरा का अर्थ जानिए।",
            "instagram_caption": "Chhath Puja honours the setting and rising sun through a family tradition of gratitude.",
            "instagram_long_caption": "Explore the meaning of Chhath Puja and the tradition of offering arghya to the sun.",
            "hashtags": ["#ChhathPuja", "#ChhathiMaiya", "#IndianTraditions"],
        })
        self.assertIn("छठ पूजा: कथा, अर्घ्य और परंपरा | Chhath Puja Hindi", pack)
        self.assertIn("CREATE BEFORE UPLOAD", pack)
        self.assertIn("https://www.instagram.com/velvet_bunny.vb/", pack)
        self.assertNotIn("[PASTE YOUTUBE URL]", pack)
        self.assertNotIn("VIDEO_ID", pack)

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

    def test_youtube_descriptions_append_only_missing_episode_hashtags(self):
        tags = ["#KarvaChauth", "#VratKatha", "#IndianMythology"]
        long_desc = _append_missing_hashtags(
            "Veervati's Karva Chauth story.\n\n#KarvaChauth", tags
        )
        short_desc = _append_missing_hashtags(
            "A short retelling of the vrat katha.\n\n#vratkatha", tags
        )
        self.assertEqual(long_desc.lower().count("#karvachauth"), 1)
        self.assertEqual(long_desc.lower().count("#vratkatha"), 1)
        self.assertEqual(long_desc.lower().count("#indianmythology"), 1)
        self.assertEqual(short_desc.lower().count("#vratkatha"), 1)
        self.assertEqual(short_desc.lower().count("#karvachauth"), 1)
        self.assertEqual(short_desc.lower().count("#indianmythology"), 1)

    def test_missing_english_copy_fails_closed_instead_of_keyword_template(self):
        meta = {
            "shorts_title": "करवा चौथ की कथा",
            "shorts_description": "करवा चौथ की कथा में फिर क्या हुआ?",
            "long_video_description": "यह करवा चौथ की पारंपरिक कथा है।",
            "primaryKeyword": "Karva Chauth vrat katha",
            "secondaryKeywords": ["Veervati story", "Karva Chauth tradition"],
            "hashtags": ["#KarvaChauth", "#VratKatha"],
        }
        self.assertEqual(instagram_caption_english(meta), "")
        self.assertEqual(instagram_caption_english(meta, long_video=True), "")
        meta["instagram_caption"] = "#KarvaChauth #VratKatha"
        self.assertEqual(instagram_caption_english(meta), "")

    def test_generic_legacy_caption_is_rejected_not_reused(self):
        meta = {
            "shorts_title": "करवा चौथ की कथा",
            "instagram_caption": "A short devotional story about Karva Chauth. Watch till the end for the complete moment.",
            "instagram_long_caption": "Discover this devotional story about Karva Chauth.",
            "shorts_description": "करवा चौथ की कथा में फिर क्या हुआ?",
            "long_video_description": "यह करवा चौथ की पारंपरिक कथा है।",
            "hashtags": ["#KarvaChauth", "#VratKatha"],
        }
        for legacy_caption in (
            "A short devotional story about Karva Chauth. Watch till the end for the complete moment.",
            "Step into a devotional story from Vrindavan and follow the moment that gives this tale its meaning.",
            "This devotional tale of Lord Krishna brings a memorable moment from his stories to life.",
        ):
            meta["instagram_caption"] = legacy_caption
            meta["instagram_long_caption"] = legacy_caption
            self.assertEqual(instagram_caption_english(meta), "")
            self.assertEqual(instagram_caption_english(meta, long_video=True), "")
        pack = build(meta)
        self.assertIn("CAPTION NOT GENERATED", pack)
        self.assertNotIn("Watch till the end for the complete moment", pack)

    def test_pack_uses_generated_instagram_captions_and_does_not_duplicate_youtube_tags(self):
        meta = {
            "shorts_title": "करवा चौथ की कथा",
            "long_video_title": "करवा चौथ व्रत कथा",
            "long_video_description": "A detailed Karva Chauth story.\n\n#KarvaChauth",
            "shorts_description": "Veervati hears that the moon has risen.\n\n#VratKatha",
            "instagram_caption": "Veervati's first Karva Chauth takes an unexpected turn. What happens next is the heart of this traditional vrat katha.",
            "instagram_long_caption": "Explore Veervati's story and the meaning behind the Karva Chauth vrat katha.",
            "hashtags": ["#KarvaChauth", "#VratKatha", "#IndianMythology"],
            "tags": ["Karva Chauth", "Veervati"],
        }
        pack = build(meta)
        self.assertIn("Veervati's first Karva Chauth takes an unexpected turn", pack)
        fence = chr(96) * 3
        long_desc = pack.split("**Description** (chapters included)", 1)[1].split(fence, 2)[1]
        short_section = pack.split("## 2. Short", 1)[1]
        short_desc = short_section.split("**Description**", 1)[1].split(fence, 2)[1]
        self.assertEqual(long_desc.lower().count("#karvachauth"), 1)
        self.assertEqual(long_desc.lower().count("#vratkatha"), 1)
        self.assertEqual(short_desc.lower().count("#karvachauth"), 1)
        self.assertEqual(short_desc.lower().count("#vratkatha"), 1)
        self.assertIn("Explore Veervati's story and the meaning behind the Karva Chauth vrat katha.", pack)

    def test_missing_english_story_copy_does_not_create_a_generic_instagram_caption(self):
        meta = {
            "shorts_title": "करवा चौथ की कथा",
            "long_video_title": "करवा चौथ व्रत कथा",
            "shorts_description": "करवा चौथ की कथा में फिर क्या हुआ?",
            "long_video_description": "यह करवा चौथ की पारंपरिक कथा है।",
        }
        self.assertEqual(instagram_caption_english(meta), "")
        self.assertEqual(instagram_caption_english(meta, long_video=True), "")
        pack = build(meta)
        self.assertIn("CAPTION NOT GENERATED", pack)
        self.assertNotIn("A short devotional story about", pack)
        self.assertNotIn("Watch till the end for the complete moment", pack)

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
        self.assertIn("append_missing_tags($meta[0].long_video_description // $meta[0].description // $meta[0].long_video_title; $meta[0].hashtags)", workflow)
        self.assertIn("append_missing_tags($meta[0].shorts_description // $meta[0].long_video_description // $meta[0].shorts_title // $meta[0].long_video_title; $meta[0].hashtags)", workflow)

    def test_colloquial_hindi_check_flags_stiff_words(self):
        result = assess_text("तत्पश्चात राजा ने सभी को अवगत कराया।")
        self.assertTrue(any(f["type"] == "written_only_vocabulary" for f in result["flags"]))
        natural = assess_text("फिर राजा ने सबको बताया कि क्या हुआ था।")
        self.assertFalse(any(f["type"] == "written_only_vocabulary" for f in natural["flags"]))


if __name__ == "__main__":
    unittest.main()
