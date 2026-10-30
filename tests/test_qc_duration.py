"""Regression tests for 8–12 minute Long and standalone Short media QC."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import qc


class MediaDurationTests(unittest.TestCase):
    def _props(self, path, scene_count, words_per_scene, duration):
        scenes = [
            {
                "durationInSeconds": duration / scene_count,
                "narration_chunk": " ".join(["कथा"] * words_per_scene),
            }
            for _ in range(scene_count)
        ]
        path.write_text(json.dumps({"scenes": scenes}, ensure_ascii=False), encoding="utf-8")

    def test_eight_to_twelve_minute_long_and_short_targets_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            long_props = root / "long.json"
            short_props = root / "short.json"
            self._props(long_props, 6, 200, 600)
            self._props(short_props, 5, 18, 45)
            rules = {
                qc.LONG_PATH: (str(long_props), "long video", 900, 1650, 1050, 1450),
                qc.SHORTS_PATH: (str(short_props), "Short", 15, 200, 70, 110),
            }
            with patch.dict(qc.DURATION_RULES, rules):
                self.assertTrue(qc.check_duration({}, qc.LONG_PATH, 600))
                self.assertTrue(qc.check_duration({}, qc.SHORTS_PATH, 45))

    def test_long_video_under_eight_minutes_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            props = Path(tmp) / "long.json"
            self._props(props, 6, 200, 420)
            rules = {qc.LONG_PATH: (str(props), "long video", 900, 1650, 1050, 1450)}
            with patch.dict(qc.DURATION_RULES, rules):
                report = {}
                self.assertFalse(qc.check_duration(report, qc.LONG_PATH, 420))
                self.assertIn("required 480-720s", report["durationError"])

    def test_word_count_limits_are_independent_of_render_duration(self):
        with tempfile.TemporaryDirectory() as tmp:
            props = Path(tmp) / "long.json"
            self._props(props, 6, 100, 600)
            rules = {qc.LONG_PATH: (str(props), "long video", 900, 1650, 1050, 1450)}
            with patch.dict(qc.DURATION_RULES, rules):
                report = {}
                self.assertFalse(qc.check_duration(report, qc.LONG_PATH, 600))
                self.assertEqual(report["narrationWords"], 600)


if __name__ == "__main__":
    unittest.main()
