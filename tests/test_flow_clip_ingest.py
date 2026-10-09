"""Smoke tests for Google Flow clip injection; zero network / Gemini usage."""
import io
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from scripts import flow_clip_ingest as ingest


class TestFlowImport(unittest.TestCase):
    def test_reject_external_urls(self):
        with self.assertRaises(ValueError):
            ingest.validate_release_url("https://evil.example/video.mp4")
        with self.assertRaises(ValueError):
            ingest.validate_release_url("http://github.com/rahul4128/long-video/releases/download/test/clip.mp4")
        self.assertEqual(
            ingest.validate_release_url(
                "https://github.com/rahul4128/long-video/releases/download/flow-2026-10-09/hook.mp4"
            ),
            "https://github.com/rahul4128/long-video/releases/download/flow-2026-10-09/hook.mp4",
        )

    def test_clip_applied_and_existing_narration_preserved(self):
        for binary in ("ffmpeg", "ffprobe"):
            if not shutil.which(binary):
                self.fail(f"REQUIRED binary unavailable: {binary}; the video-insertion smoke test must never skip")
        with tempfile.TemporaryDirectory() as tmp:
            original = Path.cwd()
            os.chdir(tmp)
            try:
                Path("public").mkdir()
                Path("public/props.json").write_text(
                    json.dumps({"scenes": [
                        {"scene_number": 1, "durationInSeconds": 15,
                         "narration_chunk": "आज की पूजा",
                         "shots": [{"type": "image", "file": "original1.jpg"},
                                   {"type": "video", "file": "original2.mp4"}]},
                        {"scene_number": 2, "shots": [{"type": "image", "file": "untouched.jpg"}]}
                    ]}, ensure_ascii=False),
                    encoding="utf-8",
                )
                Path("public/props_shorts.json").write_text(json.dumps(
                    {"scenes": [{"scene_number": 1, "shots": [
                        {"type": "image", "file": "old_short.jpg"}]}]}
                ), encoding="utf-8")
                fake = Path(tmp) / "fake.mp4"
                subprocess.run([
                    "ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi",
                    "-i", "testsrc=size=640x360:rate=30", "-t", "3",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", str(fake),
                ], check=True)
                url = "https://github.com/rahul4128/long-video/releases/download/flow-sample/hook.mp4"
                def fake_download(_url, output):
                    shutil.copyfile(fake, output)
                with patch.object(ingest, "download_release", fake_download):
                    report = ingest.run({"long": [{"scene": 1, "url": url}],
                                         "shorts": [{"scene": 1, "url": url}]}, strict=True)
                self.assertEqual(len(report["applied"]), 2)
                self.assertFalse(report["failed"])
                for fmt, props_file in (("long", "public/props.json"),
                                        ("shorts", "public/props_shorts.json")):
                    scenes = json.loads(Path(props_file).read_text())["scenes"]
                    self.assertEqual(scenes[0]["shots"][0]["file"], f"flow_{fmt}_scene_1.mp4")
                    self.assertEqual(scenes[0]["shots"][0]["type"], "video")
                    output = Path(f"public/images/flow_{fmt}_scene_1.mp4")
                    self.assertTrue(output.is_file())
                    probe = json.loads(subprocess.check_output([
                        "ffprobe", "-v", "error", "-select_streams", "v:0",
                        "-show_entries", "stream=width,height,codec_name",
                        "-of", "json", str(output),
                    ], text=True))
                    stream = probe["streams"][0]
                    self.assertEqual(stream["codec_name"], "h264")
                    self.assertEqual(
                        (stream["width"], stream["height"]),
                        (1280, 720) if fmt == "long" else (720, 1280),
                    )
                long_scene = json.loads(Path("public/props.json").read_text())["scenes"]
                self.assertEqual(long_scene[0]["narration_chunk"], "आज की पूजा")
                self.assertEqual(long_scene[0]["shots"][1]["file"], "original2.mp4")
                self.assertEqual(long_scene[1]["shots"][0]["file"], "untouched.jpg")
                self.assertEqual(
                    json.loads(Path("out/flow_clip_report.json").read_text())["failed"], []
                )
            finally:
                os.chdir(original)

    def test_bad_video_falls_back_when_not_strict(self):
        with tempfile.TemporaryDirectory() as tmp:
            original = Path.cwd()
            os.chdir(tmp)
            try:
                Path("public").mkdir()
                Path("public/props.json").write_text(json.dumps(
                    {"scenes": [{"scene_number": 1, "shots": [
                        {"type": "image", "file": "original.jpg"}]}]}))
                Path("public/props_shorts.json").write_text('{"scenes":[]}')
                manifest = {"long": [{"scene": 1, "url":
                    "https://github.com/rahul4128/long-video/releases/download/flow-test/bad.mp4"}]}
                # The 404 is deliberate: verify fallback without emitting
                # a misleading GitHub Actions warning for expected behavior.
                with patch.object(ingest, "download_release", side_effect=ValueError("404")):
                    output = io.StringIO()
                    with redirect_stdout(output):
                        report = ingest.run(manifest, strict=False)
                self.assertIn("404", output.getvalue())
                self.assertEqual(len(report["failed"]), 1)
                scenes = json.loads(Path("public/props.json").read_text())["scenes"]
                self.assertEqual(scenes[0]["shots"][0]["file"], "original.jpg")
            finally:
                os.chdir(original)


if __name__ == "__main__":
    unittest.main()
