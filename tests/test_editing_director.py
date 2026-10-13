"""Offline regressions for documentary video-edit direction."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from editing_director import (
    _short_phrase, attach_editing, validate_editing,
)


def scene(number=2, pattern="reveal", mood="revelation"):
    beats = [
        {"beatIndex": 1, "narrationText": "अब ये बात समझिए", "shotType": "wide"},
        {"beatIndex": 2, "narrationText": "लेकिन इसमें छिपा है सच", "shotType": "detail"},
        {"beatIndex": 3, "narrationText": "आखिर इसका जवाब क्या है", "shotType": "close_up"},
    ]
    return {
        "scene_number": number, "narration_chunk": "लेकिन इसमें छिपा है सच?",
        "musicMood": mood, "director": {"entertainmentBeat": pattern},
        "visualBeats": beats,
        "shots": [
            {"file": "real_1.mp4", "type": "video", "shotType": "wide",
             "beatIndex": 1, "startSeconds": 0, "endSeconds": 3},
            {"file": "ai_2.png", "type": "image", "shotType": "detail",
             "beatIndex": 2, "startSeconds": 3, "endSeconds": 6},
            {"file": "real_3.mp4", "type": "video", "shotType": "close_up",
             "beatIndex": 3, "startSeconds": 6, "endSeconds": 9},
        ],
    }


class EditDirectorTests(unittest.TestCase):
    def test_phrase_is_verbatim_short_not_hallucinated(self):
        text = "लेकिन इसमें छिपा है सच"
        phrase = _short_phrase(text)
        self.assertTrue(phrase)
        self.assertIn(phrase, text)
        self.assertLessEqual(len(phrase), 36)

    def test_reveal_edits_have_one_focus_and_one_typography_card(self):
        s = scene()
        original_timings = [
            (sh["startSeconds"], sh["endSeconds"], sh["file"]) for sh in s["shots"]
        ]
        with tempfile.TemporaryDirectory() as tmp:
            report = attach_editing([s], [], report_path=str(Path(tmp) / "edit.json"))
            self.assertTrue(report["enabled"])
            self.assertTrue((Path(tmp) / "edit.json").is_file())
            self.assertEqual(len([x for x in s["shots"] if x["editTreatment"] == "impact"]), 1)
            self.assertEqual(len([x for x in s["shots"] if x["transition"] == "blur_cut"]), 1)
            self.assertLessEqual(len([x for x in s["shots"] if x.get("editorialLabel")]), 1)
            self.assertEqual(
                original_timings,
                [(sh["startSeconds"], sh["endSeconds"], sh["file"]) for sh in s["shots"]],
            )
            validate_editing([s])

    def test_no_duplicate_typography_with_subtitles_emphasis(self):
        s = scene()
        s["visualBeats"][1]["emphasisText"] = "छिपा सच"
        with tempfile.TemporaryDirectory() as tmp:
            attach_editing([s], [], report_path=str(Path(tmp) / "edit.json"))
        self.assertEqual(s["shots"][1]["editTreatment"], "impact")
        self.assertNotIn("editorialLabel", s["shots"][1])

    def test_opening_hook_never_overlaid_by_card(self):
        s = scene(number=1, pattern="hook")
        with tempfile.TemporaryDirectory() as tmp:
            attach_editing([], [s], report_path=str(Path(tmp) / "edit.json"))
        self.assertFalse(any(sh.get("editorialLabel") for sh in s["shots"]))

    def test_calm_scene_prefers_clean_cuts_and_soft_close(self):
        s = scene(pattern="establish", mood="devotional")
        s["narration_chunk"] = "शांति और श्रद्धा का वातावरण"
        with tempfile.TemporaryDirectory() as tmp:
            attach_editing([s], [], report_path=str(Path(tmp) / "edit.json"))
        self.assertEqual(s["shots"][0]["transition"], "cut")
        self.assertEqual(s["shots"][-1]["transition"], "crossfade")
        self.assertFalse(any(sh["transition"] == "blur_cut" for sh in s["shots"]))

    def test_missing_shots_fails_before_render(self):
        with self.assertRaises(ValueError):
            validate_editing([{"scene_number": 3, "shots": []}])

    def test_disabled_does_not_touch_old_shots(self):
        s = scene()
        original = copy.deepcopy(s)
        with tempfile.TemporaryDirectory() as tmp:
            report = attach_editing([s], [], report_path=str(Path(tmp) / "edit.json"), enabled=False)
        self.assertFalse(report["enabled"])
        self.assertEqual(s, original)


if __name__ == "__main__":
    unittest.main()
