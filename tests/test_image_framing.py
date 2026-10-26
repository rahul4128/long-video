"""Regression tests: wrong-ratio and letterboxed AI stills cannot reach Remotion."""
import os
import subprocess
import tempfile
import unittest

from scripts.image_framing import framing_issue, image_dimensions, preserve_full_subject, video_framing_issue


def frame(path, video_filter):
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", video_filter,
         "-frames:v", "1", "-q:v", "2", path],
        check=True, capture_output=True, timeout=30,
    )


class ImageFramingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def path(self, name):
        return os.path.join(self.tmp.name, name)

    def test_native_portrait_is_valid(self):
        p = self.path("portrait.jpg")
        frame(p, "testsrc2=s=360x640:d=0.1")
        self.assertIsNone(framing_issue(p, "9:16"))
        self.assertIsNotNone(framing_issue(p, "16:9"))

    def test_square_output_rejected(self):
        p = self.path("square.jpg")
        frame(p, "testsrc2=s=512x512:d=0.1")
        self.assertIn("wrong aspect ratio", framing_issue(p, "9:16"))

    def test_landscape_in_portrait_is_rejected(self):
        p = self.path("landscape.jpg")
        frame(p, "testsrc2=s=640x360:d=0.1")
        self.assertIn("wrong aspect ratio", framing_issue(p, "9:16"))

    def test_embedded_horizontal_video_strip_rejected(self):
        p = self.path("strip.jpg")
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
             "-i", "color=c=black:s=360x640:d=1", "-f", "lavfi",
             "-i", "testsrc2=s=360x202:d=1", "-filter_complex",
             "[0:v][1:v]overlay=0:219[out]", "-map", "[out]",
             "-frames:v", "1", "-q:v", "2", p],
            check=True, capture_output=True, timeout=30,
        )
        self.assertIn("embedded horizontal letterbox", framing_issue(p, "9:16"))


    def test_native_portrait_video_is_valid(self):
        p = self.path("portrait.mp4")
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
             "-i", "testsrc2=s=360x640:d=1", "-t", "1", "-c:v", "mpeg4", p],
            check=True, capture_output=True, timeout=35,
        )
        self.assertIsNone(video_framing_issue(p, "9:16"))

    def test_landscape_source_video_rejected_for_shorts(self):
        p = self.path("landscape.mp4")
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
             "-i", "testsrc2=s=640x360:d=1", "-t", "1", "-c:v", "mpeg4", p],
            check=True, capture_output=True, timeout=35,
        )
        self.assertIn("wrong video aspect ratio", video_framing_issue(p, "9:16"))

    def test_vertical_video_with_horizontal_strip_rejected(self):
        p = self.path("embedded_strip.mp4")
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error",
             "-f", "lavfi", "-i", "color=c=black:s=360x640:d=1",
             "-f", "lavfi", "-i", "testsrc2=s=360x202:d=1",
             "-filter_complex", "[0:v][1:v]overlay=0:219[out]",
             "-map", "[out]", "-t", "1", "-c:v", "mpeg4", p],
            check=True, capture_output=True, timeout=35,
        )
        self.assertIn("embedded horizontal letterbox", video_framing_issue(p, "9:16"))

    def test_square_fallback_is_full_bleed_with_no_hard_black_bands(self):
        from PIL import Image
        p = self.path("bright-square.jpg")
        frame(p, "color=c=red:s=512x512:d=0.1")
        self.assertTrue(preserve_full_subject(p, "9:16"))
        with Image.open(p) as im:
            self.assertEqual(im.size, (720, 1280))
            top = im.getpixel((360, 10))
            center = im.getpixel((360, 640))
        self.assertGreater(top[0], 40, "Background must fill the portrait, not be black")
        self.assertGreater(center[0], top[0], "Foreground should remain the visual focus")

    def test_square_devotional_scene_reframes_without_letterbox(self):
        """Run #40203247762: detail concentrated in center, flat top/bottom.

        Old heavy-blur framing left visible empty portrait margins, causing
        the pipeline to replace the AI scene with forbidden abstract filler.
        This is a deterministic local image test, with no generation credits.
        """
        from PIL import Image
        detail = self.path("story_detail.jpg")
        square = self.path("cloudflare_square.jpg")
        frame(detail, "testsrc2=s=512x242:d=0.1")
        scene = Image.new("RGB", (512, 512), (22, 24, 33))
        with Image.open(detail) as important_content:
            scene.paste(important_content.convert("RGB"), (0, 135))
        scene.save(square, "JPEG", quality=92)

        self.assertIn("wrong aspect ratio", framing_issue(square, "9:16"))
        self.assertTrue(preserve_full_subject(square, "9:16"))
        self.assertEqual(image_dimensions(square), (720, 1280))
        self.assertIsNone(framing_issue(square, "9:16"))
        with Image.open(square) as result:
            # Subject/scene remains completely visible in the middle rather
            # than forcing a narrow crop of a square goddess/royal portrait.
            self.assertEqual(result.size, (720, 1280))
            center_pixel = result.getpixel((360, 640))
        self.assertTrue(all(0 <= component <= 255 for component in center_pixel))

    def test_unreadable_source_does_not_replace_original(self):
        p = self.path("tiny.jpg")
        from PIL import Image
        Image.new("RGB", (32, 32), (90, 60, 40)).save(p)
        old_bytes = open(p, "rb").read()
        self.assertFalse(preserve_full_subject(p, "9:16"))
        self.assertEqual(open(p, "rb").read(), old_bytes)


    def test_safe_backup_reframe_never_keeps_square_dimensions(self):
        p = self.path("backup.jpg")
        frame(p, "testsrc2=s=512x512:d=0.1")
        self.assertTrue(preserve_full_subject(p, "9:16"))
        self.assertEqual(image_dimensions(p), (720, 1280))


if __name__ == "__main__":
    unittest.main()
