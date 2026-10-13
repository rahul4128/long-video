"""No-network style selection tests; never mistake tutorial thumbnails for demand."""
from datetime import date
import tempfile
import unittest
from pathlib import Path

from editing_style_engine import _recent_signal_winner, select_edit_style, STYLES
from editing_director import attach_editing


def story(title, pattern="establish"):
    return {
        "_meta": {"decisionBasis": "WHY_CLICK=topic clarity"},
        "seo_metadata": {"long_video_title": title}
    }, [{
        "scene_number": 2, "narration_chunk": title,
        "director": {"entertainmentBeat": pattern},
        "visualBeats": [{"beatIndex": 1, "narrationText": title}],
        "shots": [
            {"file": "a.mp4", "type": "video", "beatIndex": 1, "startSeconds": 0, "endSeconds": 2},
            {"file": "b.jpg", "type": "image", "beatIndex": 1, "startSeconds": 2, "endSeconds": 4},
            {"file": "c.jpg", "type": "image", "beatIndex": 1, "startSeconds": 4, "endSeconds": 6},
        ],
    }]


class StyleSelectionTests(unittest.TestCase):
    def test_story_categories_are_distinct(self):
        categories = {
            "festival_energy": "गरबा उत्सव की झांकी",
            "curiosity_reveal": "मंदिर का रहस्य क्या है",
            "presenter_explainer": "माला पूजा कैसे करें",
            "emotional_story": "माँ की करुणा",
            "cinematic_devotional": "सुंदर मंदिर दर्शन",
        }
        for style, title in categories.items():
            with self.subTest(style=style):
                context, scenes = story(title)
                self.assertEqual(select_edit_style(context, scenes)["style"], style)

    def test_make_uses_existing_decision_basis_not_schema_change(self):
        context, scenes = story("मंदिर दर्शन")
        context["_meta"]["decisionBasis"] += "\nEDIT_STYLE=presenter_explainer\nEDIT_STYLE_WHY=question-driven"
        result = select_edit_style(context, scenes)
        self.assertEqual(result["style"], "presenter_explainer")
        self.assertEqual(result["reason"], "script_style_from_existing_make_payload")

    def test_festival_energy_not_imposed_on_emotional_story(self):
        context, scenes = story("माँ की करुणा")
        context["_meta"]["decisionBasis"] += "\nEDIT_STYLE=festival_energy"
        self.assertEqual(select_edit_style(context, scenes)["style"], "emotional_story")

    def test_performance_needs_multiple_fresh_videos_not_one_viral_reel(self):
        one = {"style": "presenter_explainer", "published_on": "2026-10-13",
               "videos": 1, "average_view_percentage": 90, "shares_per_1000": 16,
               "platform": "instagram", "source": "sample"}
        verdict, reason = _recent_signal_winner([one], today=date(2026, 10, 13))
        self.assertIsNone(verdict)
        self.assertEqual(reason, "no_eligible_verified_metrics")
        one["videos"] = 4
        verdict, reason = _recent_signal_winner([one], today=date(2026, 10, 13))
        self.assertEqual(verdict["style"], "presenter_explainer")
        self.assertEqual(reason, "recent_source_reported_multi_video_metric")

    def test_stale_and_unsupported_styles_ignored(self):
        signals = [
            {"style": "glitch_every_second", "published_on": "2026-10-12", "videos": 9,
             "average_view_percentage": 50, "shares_per_1000": 8,
             "source": "test", "platform": "youtube"},
            {"style": "festival_energy", "published_on": "2025-08-01", "videos": 4,
             "average_view_percentage": 80, "shares_per_1000": 8,
             "source": "test", "platform": "youtube"},
        ]
        result, reason = _recent_signal_winner(signals, today=date(2026, 10, 13))
        self.assertIsNone(result)

    def test_editing_director_uses_style_but_preserves_timings(self):
        context, scenes = story("गरबा उत्सव की झांकी", pattern="action")
        s = scenes[0]
        old = [(sh["startSeconds"], sh["endSeconds"]) for sh in s["shots"]]
        with tempfile.TemporaryDirectory() as tmp:
            report = attach_editing(scenes, [], context=context,
                report_path=str(Path(tmp) / "editing.json"))
        self.assertEqual(report["selectedStyle"], "festival_energy")
        self.assertTrue(any(sh["transition"] == "whip_pan" for sh in s["shots"]))
        self.assertEqual(old, [(sh["startSeconds"], sh["endSeconds"]) for sh in s["shots"]])

    def test_curious_reveal_uses_restrained_flash_once(self):
        context, scenes = story("मंदिर का रहस्य क्या है", pattern="reveal")
        with tempfile.TemporaryDirectory() as tmp:
            report = attach_editing(scenes, [], context=context,
                report_path=str(Path(tmp) / "editing.json"))
        self.assertEqual(report["selectedStyle"], "curiosity_reveal")
        self.assertLessEqual(sum(x["transition"] == "flash_cut" for x in scenes[0]["shots"]), 1)
        self.assertTrue(all(x["transition"] in ("flash_cut", "cut", "crossfade", "blur_cut", "whip_pan") for x in scenes[0]["shots"]))


if __name__ == "__main__":
    unittest.main()
