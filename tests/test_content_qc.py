"""Regression tests for the approximately 3-minute Long content contract."""
import unittest

from content_qc import validate_payload


def _scene_text(count, marker):
    return " ".join([f"कथा{marker}"] * count)


def _payload(long_counts):
    return {
        "long_video": {
            "scenes": [
                {"text": _scene_text(count, index)}
                for index, count in enumerate(long_counts, start=1)
            ]
        },
        "shorts": {
            "scenes": [
                {"text": " ".join([f"शॉर्ट{index}"] * 14)}
                for index in range(1, 6)
            ]
        },
        "seo_metadata": {},
        "thumbnail": {},
        "_meta": {},
    }


class ThreeMinuteLongContentQCTests(unittest.TestCase):
    def test_accepts_six_scenes_and_360_words(self):
        report = validate_payload(_payload([60, 60, 60, 60, 60, 60]))
        self.assertTrue(report["ok"], report["issues"])
        self.assertEqual(report["longNarrationWords"], 360)
        self.assertEqual(report["shortNarrationWords"], 70)
        self.assertEqual(report["targetLongMinutes"], 3)
        self.assertEqual(report["targetLongSeconds"], [150, 210])

    def test_rejects_total_below_360_words(self):
        report = validate_payload(_payload([59, 59, 59, 59, 59, 59]))
        self.assertFalse(report["ok"])
        self.assertTrue(any("long_narration_outside_360_430_words" in x for x in report["issues"]))

    def test_rejects_total_above_430_words(self):
        report = validate_payload(_payload([72, 72, 72, 72, 72, 72]))
        self.assertFalse(report["ok"])
        self.assertTrue(any("long_narration_outside_360_430_words" in x for x in report["issues"]))

    def test_rejects_scene_outside_55_to_75_even_when_total_is_valid(self):
        report = validate_payload(_payload([54, 66, 60, 60, 60, 60]))
        self.assertEqual(report["longNarrationWords"], 360)
        self.assertFalse(report["ok"])
        self.assertTrue(any("long_scene_1_word_count_outside_55_75" in x for x in report["issues"]))


if __name__ == "__main__":
    unittest.main()
