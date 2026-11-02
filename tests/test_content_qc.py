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
        "seo_metadata": {
            "long_video_title": "तीन मिनट की भक्ति कथा"
        },
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

    def test_rejects_total_below_330_words(self):
        report = validate_payload(_payload([54, 54, 54, 54, 54, 54]))
        self.assertFalse(report["ok"])
        self.assertTrue(any("long_narration_outside_330_430_words" in x for x in report["issues"]))

    def test_rejects_total_above_430_words(self):
        report = validate_payload(_payload([72, 72, 72, 72, 72, 72]))
        self.assertFalse(report["ok"])
        self.assertTrue(any("long_narration_outside_330_430_words" in x for x in report["issues"]))

    def test_allows_uneven_scene_lengths_when_total_contract_is_valid(self):
        # Current production QC intentionally enforces the overall narration
        # range, not a brittle 55-75-word requirement on every scene.
        report = validate_payload(_payload([54, 66, 60, 60, 60, 60]))
        self.assertEqual(report["longNarrationWords"], 360)
        self.assertTrue(report["ok"], report["issues"])


if __name__ == "__main__":
    unittest.main()
