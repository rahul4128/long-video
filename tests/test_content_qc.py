"""Pre-render content-QC tests for the 8–12 minute Long + Short pair."""
import unittest

from content_qc import validate_payload


def payload(long_words_per_scene=180, short_words_per_scene=18, short_scene_count=5):
    long_scenes = []
    for index in range(6):
        text = " ".join([f"दृश्य{index + 1}"] + ["कथा"] * (long_words_per_scene - 1))
        long_scenes.append({"text": text, "mediaType": "ai_image", "imagePrompt": "एक ही कथा का सटीक दृश्य"})
    short_scenes = [
        {"text": " ".join(["प्रसंग"] * short_words_per_scene)}
        for _ in range(short_scene_count)
    ]
    return {
        "long_video": {"scenes": long_scenes},
        "shorts": {"scenes": short_scenes},
        "seo_metadata": {
            "long_video_title": "पौराणिक कथा का अनसुना प्रसंग",
            "shorts_title": "इस कथा में आगे क्या हुआ?",
            "long_video_description": "यह कथा एक खास सवाल का जवाब देती है।",
            "shorts_description": "इस छोटे प्रसंग का जवाब सुनिए।",
            "tags": ["puranik katha", "hindi mythology"],
            "hashtags": ["#Mythology", "#Katha"],
            "thumbnailText": "अनसुना प्रसंग",
            "titleVariants": ["पहला शीर्षक", "दूसरा शीर्षक", "तीसरा शीर्षक"],
            "thumbnailConcepts": [
                {"visualSubject": "पात्र", "emotionAction": "आश्चर्य", "composition": "क्लोजअप", "text": "अनसुना प्रसंग"}
                for _ in range(3)
            ],
            "primaryKeyword": "puranik katha",
            "secondaryKeywords": ["hindi mythology", "ancient story", "devotional story", "puran", "katha"],
            "cta": "आपकी राय क्या है? कमेंट में बताइए।",
        },
        "_meta": {
            "content_role": "discovery",
            "experiment_hypothesis": "एक नया कथा-कोण दर्शकों को रोकेगा।",
            "next_episode_angle": "अगला संबंधित प्रसंग",
            "retention_adaptation": "हर दृश्य में नया खुलासा",
            "experiment_id": "test_episode_1",
            "shorts_funnel_hook": "इस कथा का जवाब",
            "long_video_continuation": "पूरी कथा का गहरा अर्थ",
            "entertainment_angle": "कथा में भावनात्मक मोड़",
            "fun_with_fact_angle": "दिलचस्प सांस्कृतिक संदर्भ",
            "decisionBasis": "PLAYLIST_NAME=पौराणिक कथाएँ और अनसुने प्रसंग | Hindi Mythology Stories",
        },
        "thumbnail": {"thumbnailText": "अनसुना प्रसंग"},
    }


class ContentLengthTests(unittest.TestCase):
    def test_1080_word_long_and_90_word_short_pass_length_gates(self):
        report = validate_payload(payload())
        self.assertTrue(report["ok"], report["issues"])
        self.assertEqual(report["longNarrationWords"], 1080)
        self.assertEqual(report["shortNarrationWords"], 90)
        self.assertEqual(report["targetLongMinutes"], [8, 12])

    def test_short_must_have_exactly_five_scenes(self):
        report = validate_payload(payload(short_scene_count=4))
        self.assertFalse(report["ok"])
        self.assertIn("short_scene_count_must_be_5:4", report["issues"])

    def test_long_below_900_words_is_blocked(self):
        report = validate_payload(payload(long_words_per_scene=100))
        self.assertFalse(report["ok"])
        self.assertIn("long_narration_too_short:600_words_minimum_900", report["issues"])


if __name__ == "__main__":
    unittest.main()
