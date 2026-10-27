"""Offline narration-synchronised Canva-style editing tests.

The Python editor selects effects from the factual beat/format. Remotion
renders the effects locally, without a paid Canva video timeline API.
"""
import copy
import tempfile
import unittest
from pathlib import Path
from editing_director import attach_editing, validate_editing

ROOT = Path(__file__).resolve().parents[1]


def story_scene(number=2, mood="mystery", pattern="reveal"):
    return {
        "scene_number": number, "narration_chunk": "आखिर क्या हुआ? देखिए असली सच",
        "musicMood": mood, "director": {"entertainmentBeat": pattern},
        "visualBeats": [
            {"beatIndex": 1, "narrationText": "पूरी कथा की शुरुआत", "shotType": "wide"},
            {"beatIndex": 2, "narrationText": "वहां एक बात हुई", "shotType": "medium"},
            {"beatIndex": 3, "narrationText": "असली बात सामने आई", "shotType": "detail",
             "emphasisStyle": "reveal"},
        ],
        "shots": [
            {"file": "establish.mp4", "type": "video", "shotType": "wide",
             "beatIndex": 1, "startSeconds": 0, "endSeconds": 3},
            {"file": "context.jpg", "type": "image", "shotType": "medium",
             "beatIndex": 2, "startSeconds": 3, "endSeconds": 6},
            {"file": "truth.jpg", "type": "image", "shotType": "detail",
             "beatIndex": 3, "startSeconds": 6, "endSeconds": 9},
        ],
    }


def edit(long, short):
    with tempfile.TemporaryDirectory() as tmp:
        return attach_editing(
            long, short, context={"seo_metadata": {
                "long_video_title": "आखिर मंदिर का रहस्य क्या है?"
            }}, report_path=str(Path(tmp) / "edit.json"),
        )


class CanvaStyleEditorTests(unittest.TestCase):
    def test_reveal_is_real_detail_not_generic_slideshow_transition(self):
        scene = story_scene()
        original = copy.deepcopy(scene["shots"])
        report = edit([scene], [])
        self.assertEqual(report["selectedStyle"], "curiosity_reveal")
        self.assertEqual(scene["shots"][-1]["transition"], "masked_reveal")
        self.assertEqual(sum(x["transition"] == "masked_reveal" for x in scene["shots"]), 1)
        self.assertEqual(report["formats"]["long"][0]["maskedReveals"], 1)
        self.assertEqual(
            [(x["file"], x["startSeconds"], x["endSeconds"]) for x in original],
            [(x["file"], x["startSeconds"], x["endSeconds"]) for x in scene["shots"]],
        )
        self.assertFalse(report["subtitlesEnabled"])
        self.assertFalse(any(x.get("editorialLabel") or x.get("documentaryGraphic")
                             for x in scene["shots"]))
        validate_editing([scene])

    def test_at_most_two_reveals_for_long_and_one_for_shorts(self):
        long = [story_scene(x) for x in range(2, 7)]
        short = [story_scene(x) for x in range(1, 6)]
        edit(long, short)
        self.assertEqual(sum(shot["transition"] == "masked_reveal"
                             for scene in long for shot in scene["shots"]), 2)
        self.assertEqual(sum(shot["transition"] == "masked_reveal"
                             for scene in short for shot in scene["shots"]), 1)

    def test_no_evidence_no_mask_transition(self):
        scene = story_scene()
        scene["visualBeats"][-1].pop("emphasisStyle")
        edit([scene], [])
        self.assertNotIn("masked_reveal", [x["transition"] for x in scene["shots"]])

    def test_real_explainer_detail_can_use_soft_focus_pull(self):
        scene = story_scene(mood="devotional", pattern="establish")
        for beat in scene["visualBeats"]:
            beat.pop("emphasisStyle", None)
        with tempfile.TemporaryDirectory() as tmp:
            result = attach_editing(
                [scene], [], context={"seo_metadata": {
                    "long_video_title": "पूजा कैसे करें"
                }}, report_path=str(Path(tmp) / "edit.json"),
            )
        self.assertEqual(result["selectedStyle"], "presenter_explainer")
        self.assertTrue(any(x.get("editFocusPull") for x in scene["shots"]))
        self.assertLessEqual(sum(bool(x.get("editFocusPull")) for x in scene["shots"]), 1)
        validate_editing([scene])

    def test_mask_rejects_unsourced_opening_or_unrelated_wide_shot(self):
        scene = story_scene()
        for shot in scene["shots"]:
            shot["editTreatment"] = "clean"
            shot["transition"] = "cut"
        scene["shots"][0]["transition"] = "masked_reveal"
        with self.assertRaisesRegex(ValueError, "non-first"):
            validate_editing([scene])
        scene["shots"][0]["transition"] = "cut"
        scene["shots"][1]["transition"] = "masked_reveal"
        with self.assertRaisesRegex(ValueError, "non-first"):
            validate_editing([scene])

    def test_renderer_supports_mask_and_stays_subtitle_free(self):
        scene_src = (ROOT / "src/Scene.tsx").read_text()
        director = (ROOT / "editing_director.py").read_text()
        workflow = (ROOT / ".github/workflows/render.yml").read_text()
        self.assertIn("clipPath: window.incomingTransition === 'masked_reveal'", scene_src)
        self.assertIn("outgoingTransition === 'masked_reveal'", scene_src)
        self.assertIn("shot.editFocusPull", scene_src)
        self.assertIn("masked_budget = 2 if name == \"long\" else 1", director)
        self.assertIn("SUBTITLES_ENABLED: 'false'", workflow)
        self.assertIn("EDITORIAL_TEXT_OVERLAYS_ENABLED: 'false'", workflow)
        self.assertIn("DevotionalComposition out/final_video.mp4", workflow)
        self.assertIn("DevotionalShortsComposition out/final_video_shorts.mp4", workflow)
        self.assertIn("out/thumbnail_shorts_final.jpg", workflow)


if __name__ == "__main__":
    unittest.main()
