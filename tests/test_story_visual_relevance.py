"""Regression for actual irrelevant scenes in oflifepart31 Kushmanda video.

Tests metadata evidence and beat query generation; no networking or paid media
is needed. A crisp stock clip must not bypass actual narration relevance.
"""
import unittest

from scripts.visual_relevance_gate import (
    strong_stock_match, visual_relevance_issues,
    named_deity_requires_verified_footage,
)
from director import _build_queries
from visual_qc import prioritized_repair_tasks


def candidate(semantic, entity, overall=.78, similarity=.31):
    return {
        "type": "video", "source": "pexels", "selectionScore": overall,
        "scoreBreakdown": {
            "semantic": semantic, "entity_action": entity, "quality": 1.0,
            "motion": 1.0, "continuity": 1.0,
            "novelty": 1.0, "composition": 1.0,
        },
        "clipSimilarity": similarity, "visualContractStrict": False,
    }


class StoryFirstStockTests(unittest.TestCase):
    def test_visual_repairs_prioritize_missing_beats_in_later_scenes(self):
        report = {"scenes": [
            {"repairTargets": [
                {"beatIndex": 1, "priority": 60, "reason": "shot_too_long"},
                {"beatIndex": 2, "priority": 35, "reason": "excessive_ai_fallback"},
            ]},
            {"repairTargets": [
                {"beatIndex": 1, "priority": 35, "reason": "excessive_ai_fallback"},
            ]},
            {"repairTargets": [
                {"beatIndex": 3, "priority": 100, "reason": "missing_beat_visual"},
            ]},
            {"repairTargets": [
                {"beatIndex": 4, "priority": 100, "reason": "missing_beat_visual"},
            ]},
        ]}
        tasks = prioritized_repair_tasks(report)
        self.assertEqual(
            [(i, t["reason"]) for i, t in tasks[:2]],
            [(2, "missing_beat_visual"), (3, "missing_beat_visual")],
        )
        self.assertEqual(tasks[-1][1]["reason"], "excessive_ai_fallback")

    def test_high_resolution_great_transition_cannot_rescue_wrong_action(self):
        good_looking_wrong_person = candidate(.77, 0.0, .90)
        passed, reason = strong_stock_match(good_looking_wrong_person)
        self.assertFalse(passed)
        self.assertEqual(reason, "subject_or_action_mismatch")

    def test_shiny_but_unrelated_subject_is_rejected(self):
        passed, why = strong_stock_match(candidate(.10, .95, .81))
        self.assertFalse(passed)
        self.assertEqual(why, "narration_semantic_mismatch")

    def test_preview_similarity_too_low_is_rejected(self):
        passed, why = strong_stock_match(candidate(.75, .80, .88, .21))
        self.assertFalse(passed)
        self.assertEqual(why, "preview_image_weak_narration_match")

    def test_believable_observable_scene_is_accepted(self):
        passed, reason = strong_stock_match(candidate(.72, .80, .78, .32))
        self.assertTrue(passed)
        self.assertEqual(reason, "narration_and_subject_supported")

    def test_missing_score_is_not_accepted_as_verified_stock(self):
        passed, why = strong_stock_match({
            "type": "video", "source": "pixabay", "selectionScore": 1.0
        })
        self.assertFalse(passed)
        self.assertEqual(why, "legacy_not_scored")

    def test_emergency_abstract_fillers_never_sneak_into_final_video(self):
        data = [{"shots": [
            {"type": "image", "source": "local_atmosphere_fallback",
             "beatIndex": 2, "file": "generic-brown.jpg"},
            candidate(.65, .85, .81),
        ]}]
        problems = visual_relevance_issues(data, "Long")
        self.assertEqual(len(problems), 1)
        self.assertEqual(problems[0]["reason"], "emergency_placeholder_not_story_footage")

    def test_failed_stock_in_existing_video_reports_beats(self):
        data = [{"shots": [candidate(.275, 1.0, .6656, .2254)]}]
        issues = visual_relevance_issues(data, "Long")
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0]["beat"], None)
        self.assertEqual(issues[0]["reason"], "narration_semantic_mismatch")

    def test_ai_image_has_no_fake_semantic_guarantee(self):
        issues = visual_relevance_issues([{"shots": [{
            "type": "image", "source": "ai_image", "file": "scene_x.jpg"
        }]}], "Shorts")
        self.assertFalse(issues)

    def test_hindi_concept_becomes_specific_visible_indian_context(self):
        q = _build_queries({
            "videoSearchQuery": "person feeling tired",
            "imagePrompt": "A person with fasting fatigue",
        }, ["उपवास", "से", "थकान"], "person", "narrative moment", "story environment")
        self.assertTrue(q)
        self.assertIn("Indian", q[0])
        self.assertNotEqual(q[0].casefold(), "person")

    def test_goddess_identity_does_not_turn_into_generic_temple(self):
        q = _build_queries({
            "videoSearchQuery": "woman in temple",
            "imagePrompt": "Goddess Kushmanda",
        }, ["माँ", "कूष्मांडा", "की", "पूजा"], "Goddess Kushmanda",
            "reveal", "temple")
        self.assertTrue(any("कूष्मांडा" in s or "kushmanda" in s.lower() for s in q))
        self.assertFalse(any(s == "woman in temple" for s in q))

    def test_shiva_footage_is_not_verified_kushmanda_stock(self):
        self.assertTrue(named_deity_requires_verified_footage(
            {"narrationText": "कूष्मांडा माता ब्रह्मांडीय ऊर्जा का स्रोत हैं"},
            "Goddess Kushmanda radiant"))
        self.assertTrue(named_deity_requires_verified_footage(
            {"subject": "Lord Shiva"}, "blue Hindu deity"))
        self.assertFalse(named_deity_requires_verified_footage(
            {"narrationText": "पानी पिएं और ताजे फल लें"},
            "glass of water and Indian fruit thali"))

    def test_not_all_unknown_topics_become_generic_people(self):
        q = _build_queries({
            "videoSearchQuery": "person",
            "imagePrompt": "Unidentified philosophical idea",
        }, ["अद्भुत", "रहस्य"], "person", "narrative moment", "story environment")
        self.assertEqual(q, [])


if __name__ == "__main__":
    unittest.main()
