"""Regression for post-mastering .mastered.mp4 -> final MP4 rename.

The validator must still reject missing reports, incorrect sources, bad status,
duration drift, and actual out-of-range loudness. No video generation required.
"""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import validate_final_audio


class MasteredArtifactValidatorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "out").mkdir()
        self.names = (
            ("long", "final_video.mp4", "audio_master_long.json"),
            ("shorts", "final_video_shorts.mp4", "audio_master_shorts.json"),
        )
        for kind, name, report_name in self.names:
            (self.root / "out" / name).write_bytes(b"synthetic-reference")
            (self.root / "out" / report_name).write_text(json.dumps({
                "status": "passed", "source": name,
                "output": Path(name).stem + ".mastered.mp4", "duration": 92.5,
            }), encoding="utf-8")

    def run_check(self, *, lufs=-16.0, peak=-2.0, duration=92.5):
        with patch.object(validate_final_audio, "_probe", return_value={"duration": duration}):
            with patch.object(validate_final_audio, "_loudness", return_value={
                "integrated_lufs": lufs, "true_peak_dbtp": peak}):
                return validate_final_audio.inspect(self.root)

    def test_accepts_renamed_mastered_video_for_both_formats(self):
        self.assertTrue(self.run_check())

    def test_accepts_final_filename_when_report_has_been_updated(self):
        for _, name, report_name in self.names:
            report_path = self.root / "out" / report_name
            document = json.loads(report_path.read_text())
            document["output"] = name
            report_path.write_text(json.dumps(document))
        self.assertTrue(self.run_check())

    def test_rejects_wrong_mastered_source(self):
        p = self.root / "out" / self.names[0][2]
        data = json.loads(p.read_text())
        data["source"] = "unrelated-video.mp4"
        p.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, "missing successful audio master"):
            self.run_check()

    def test_rejects_invalid_report_status_or_output(self):
        p = self.root / "out" / self.names[1][2]
        data = json.loads(p.read_text())
        data["status"] = "error"
        p.write_text(json.dumps(data))
        with self.assertRaises(ValueError):
            self.run_check()
        data["status"] = "passed"
        data["output"] = "other.mastered.mp4"
        p.write_text(json.dumps(data))
        with self.assertRaises(ValueError):
            self.run_check()

    def test_rejects_actual_peak_loudness_and_duration_failures(self):
        with self.assertRaisesRegex(ValueError, "outside quality window"):
            self.run_check(peak=0.0)
        with self.assertRaisesRegex(ValueError, "outside quality window"):
            self.run_check(lufs=-28.0)
        with self.assertRaisesRegex(ValueError, "duration differs"):
            self.run_check(duration=98.0)


if __name__ == "__main__":
    unittest.main()
