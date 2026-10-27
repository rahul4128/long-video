"""Offline tests: story-driven motion and creator's subtitle-free preference.

No Canva calls, Gemini calls, videos rendered, publishing or credits.
"""
import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from editing_director import attach_editing, validate_editing

ROOT = Path(__file__).resolve().parents[1]


def make_scene(pattern, mood="devotional", scene_number=2):
    return {
        "scene_number": scene_number,
        "narration_chunk": "लेकिन फिर अचानक उन्हें असली वजह समझ आई",
        "musicMood": mood,
        "director": {"entertainmentBeat": pattern},
        "visualBeats": [
            {"beatIndex": 1, "shotType": "wide", "narrationText": "सामने एक दृश्य था"},
            {"beatIndex": 2, "shotType": "close_up", "narrationText": "फिर क्या हुआ"},
            {"beatIndex": 3, "shotType": "detail", "narrationText": "यही असल सच है",
             "emphasisStyle": "reveal"},
        ],
        "shots": [
            {"file": "wide.mp4", "type": "video", "shotType": "wide",
             "beatIndex": 1, "startSeconds": 0, "endSeconds": 3},
            {"file": "close.jpg", "type": "image", "shotType": "close_up",
             "beatIndex": 2, "startSeconds": 3, "endSeconds": 6},
            {"file": "truth.jpg", "type": "image", "shotType": "detail",
             "beatIndex": 3, "startSeconds": 6, "endSeconds": 9},
        ],
    }


class StoryDrivenEditTests(unittest.TestCase):
    def test_long_and_short_have_no_subtitles_by_default(self):
        for path in ("src/DevotionalComposition.tsx", "src/DevotionalShortsComposition.tsx"):
            src = (ROOT / path).read_text(encoding="utf-8")
            self.assertIn("showSubtitles = false", src)
            self.assertIn("{showSubtitles && (", src)
            self.assertNotIn("<Subtitles\n", src.split("{showSubtitles && (", 1)[0])
        generator = (ROOT / "generate_assets.py").read_text(encoding="utf-8")
        self.assertIn('os.getenv("SUBTITLES_ENABLED", "false")', generator)
        self.assertEqual(generator.count('"showSubtitles": subtitles_enabled'), 2)
        workflow = (ROOT / ".github/workflows/render.yml").read_text(encoding="utf-8")
        self.assertIn("SUBTITLES_ENABLED: 'false'", workflow)
        self.assertIn("EDITORIAL_TEXT_OVERLAYS_ENABLED: 'false'", workflow)

    def test_emotional_reveal_lingers_and_quick_hook_uses_own_pace(self):
        long_scene = make_scene("reveal", "emotional")
        short_scene = make_scene("hook", scene_number=1)
        first_long = copy.deepcopy(long_scene["shots"])
        first_short = copy.deepcopy(short_scene["shots"])
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {
                "EDITORIAL_TEXT_OVERLAYS_ENABLED": "false",
        }):
            report = attach_editing([long_scene], [short_scene],
                                    report_path=str(Path(folder) / "edit.json"))
        self.assertFalse(report["subtitlesEnabled"])
        self.assertFalse(report["textCardsEnabled"])
        self.assertEqual(long_scene["shots"][-1]["editRhythm"], "linger")
        self.assertEqual(short_scene["shots"][0]["editRhythm"], "quick")
        for scene in (long_scene, short_scene):
            validate_editing([scene])
            self.assertTrue(all(shot.get("editReason") for shot in scene["shots"]))
            self.assertFalse(any(shot.get("editorialLabel") or shot.get("documentaryGraphic")
                                 for shot in scene["shots"]))
        for before, after in ((first_long, long_scene["shots"]),
                              (first_short, short_scene["shots"])):
            self.assertEqual(
                [(x["file"], x["startSeconds"], x["endSeconds"]) for x in before],
                [(x["file"], x["startSeconds"], x["endSeconds"]) for x in after],
            )

    def test_motion_and_audio_are_still_narration_led(self):
        renderer = (ROOT / "src/Scene.tsx").read_text(encoding="utf-8")
        self.assertIn("shot.editRhythm || 'measured'", renderer)
        self.assertIn("easing: motionCurve", renderer)
        self.assertIn("scene.words || []", renderer)
        self.assertIn("shot.startSeconds", renderer)
        self.assertIn("shot.endSeconds", renderer)
        long = (ROOT / ".github/workflows/render.yml").read_text()
        self.assertIn("DevotionalComposition out/final_video.mp4", long)
        self.assertIn("DevotionalShortsComposition out/final_video_shorts.mp4", long)
        self.assertNotIn("final_video_instagram.mp4", long)
        self.assertIn("out/thumbnail.jpg", long)
        self.assertIn("out/thumbnail_shorts_final.jpg", long)


if __name__ == "__main__":
    unittest.main()
