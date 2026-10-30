"""Regression tests for final Long/Short media duration and word limits."""
import unittest

import qc


class ThreeMinuteLongMediaQCTests(unittest.TestCase):
    def test_long_video_uses_three_minute_word_range(self):
        self.assertEqual(
            qc.DURATION_RULES[qc.LONG_PATH],
            ("public/props.json", "long video", 360, 430, 360, 430),
        )

    def test_long_video_uses_three_minute_runtime_window(self):
        self.assertEqual(qc.ABSOLUTE_DURATION_SECONDS[qc.LONG_PATH], (150, 210))

    def test_shorts_contract_is_unchanged(self):
        self.assertEqual(
            qc.DURATION_RULES[qc.SHORTS_PATH],
            ("public/props_shorts.json", "Short", 15, 200, 70, 110),
        )
        self.assertEqual(qc.ABSOLUTE_DURATION_SECONDS[qc.SHORTS_PATH], (25, 60))


if __name__ == "__main__":
    unittest.main()
