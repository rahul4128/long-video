"""Free offline contract tests: no Gemini, Canva, YouTube, or render job."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.build_instagram_reel import compact_hook, rejection_reasons, topic_hashtags, build
from scripts.validate_instagram_reel import validate


class InstagramContentTests(unittest.TestCase):
    def setUp(self):
        self.props = {
            "title": "वृंदावन में शिव बने गोपी",
            "hookText": "शिव गोपी क्यों बने?",
            "scenes": [
                {"narration_chunk": "वृंदावन में शिव गोपी क्यों बने? यही उस कथा का सवाल है।",
                 "durationInSeconds": 13},
                {"narration_chunk": "कथा कहती है कि शिवजी का प्रेम भाव प्रकट हुआ।",
                 "durationInSeconds": 17},
            ],
        }
        self.meta = {"shorts_title": "वृंदावन में शिव बने गोपी"}

    def test_hindi_words_are_never_split_through_matras(self):
        cover = compact_hook("शिव गोपी क्यों बने?")
        self.assertEqual(cover.replace("\n", " "), "शिव गोपी क्यों बने?")
        self.assertLessEqual(len(cover.split("\n")), 2)
        self.assertTrue(all(len(line) <= 18 for line in cover.splitlines()))

    def test_too_long_text_fails_instead_of_clipping(self):
        with self.assertRaises(ValueError):
            compact_hook("अतिशयअतिशयअतिशयअतिशय बहुत सुंदर कहानी")

    def test_mythology_katha_passes_text_guard(self):
        self.assertEqual(rejection_reasons(self.props, self.meta)[0], [])

    def test_youtube_subscribe_voice_cannot_be_reused_as_instagram(self):
        self.props["scenes"][0]["narration_chunk"] += " सब्सक्राइब करें।"
        self.assertIn("youtube_subscribe_spoken_in_instagram_audio",
                      rejection_reasons(self.props, self.meta)[0])

    def test_generic_fasting_advice_rejected_as_off_niche(self):
        self.meta["shorts_title"] = "सरगी में क्या न खाएं?"
        self.assertIn("generic_festival_wellness_not_mythology_story",
                      rejection_reasons(self.props, self.meta)[0])

    def test_duration_over_40_seconds_requires_review(self):
        self.props["scenes"][1]["durationInSeconds"] = 35
        self.assertIn("outside_preferred_20_to_40_second_window",
                      rejection_reasons(self.props, self.meta)[0])

    def test_hashtags_are_topic_specific_with_limit(self):
        tags = topic_hashtags("वृंदावन में कृष्ण और शिव की कथा")
        self.assertIn("#कृष्णकथा", tags)
        self.assertTrue(3 <= len(tags) <= 5)

    def test_builder_does_not_create_publish_ready_on_missing_media(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "public").mkdir()
            (root / "out").mkdir()
            (root / "public/props_shorts.json").write_text(
                json.dumps(self.props, ensure_ascii=False), encoding="utf-8")
            (root / "out/metadata.json").write_text(
                json.dumps(self.meta, ensure_ascii=False), encoding="utf-8")
            state = build(root)
            self.assertEqual(state["status"], "review_required")
            self.assertIn("cover_requires_verified_replacement", state["reasons"])
            self.assertFalse((root / "public/props_instagram.json").exists())
            self.assertTrue((root / "out/instagram_post.txt").exists())
            self.assertFalse(state["automatic_publish"])

    def test_validator_fails_closed_on_horizontal_video(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            status = root / "status.json"
            status.write_text(json.dumps({"status": "ready_for_manual_review", "reasons": []}))
            with patch("scripts.validate_instagram_reel.probe", return_value={
                "streams": [{"codec_type": "video", "width": 1920, "height": 1080},
                            {"codec_type": "audio"}], "format": {"duration": 30}
            }):
                with self.assertRaisesRegex(ValueError, "portrait"):
                    validate(root / "video.mp4", root / "cover.jpg", status)


if __name__ == "__main__":
    unittest.main()
