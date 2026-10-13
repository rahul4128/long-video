"""Synthetic audio mastering tests, no user footage or external dependencies."""
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from scripts.master_final_audio import master, _probe


def generate(path, silent=False):
    audio = ("anullsrc=channel_layout=stereo:sample_rate=48000"
             if silent else "sine=frequency=220:sample_rate=48000")
    subprocess.run([
        "ffmpeg", "-y", "-v", "error",
        "-f", "lavfi", "-i", "color=c=navy:s=320x180:r=24:d=3",
        "-f", "lavfi", "-i", audio,
        "-t", "3", "-c:v", "mpeg4", "-q:v", "7",
        "-c:a", "aac", "-b:a", "96k", str(path),
    ], check=True, capture_output=True, timeout=45)


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),
                     "FFmpeg tooling required")
class AudioMasterTests(unittest.TestCase):
    def test_master_preserves_video_track_and_measures_final_mix(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src, dst = root / "source.mp4", root / "master.mp4"
            generate(src)
            report = master(src, dst, root / "report.json")
            self.assertEqual(report["status"], "passed")
            self.assertTrue(dst.is_file())
            self.assertEqual(_probe(src)["video"]["codec_name"], _probe(dst)["video"]["codec_name"])
            self.assertAlmostEqual(_probe(src)["duration"], _probe(dst)["duration"], delta=.65)
            self.assertLessEqual(report["after"]["true_peak_dbtp"], -.75)
            self.assertGreaterEqual(report["after"]["integrated_lufs"], -19)
            self.assertLessEqual(report["after"]["integrated_lufs"], -13)

    def test_silent_audio_is_not_fake_normalized(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "silent.mp4"
            generate(src, silent=True)
            with self.assertRaises(ValueError):
                master(src, root / "master.mp4", root / "report.json")


if __name__ == "__main__":
    unittest.main()
