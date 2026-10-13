"""Conditional editing skills are available, but never fabricated from unrelated footage."""
import copy
import unittest
from editing_director import validate_editing


def scene():
    return {"scene_number": 2, "shots": [
        {"file": "before.jpg", "type": "image", "editTreatment": "clean", "transition": "cut"},
        {"file": "after.jpg", "type": "image", "editTreatment": "clean", "transition": "crossfade"},
    ]}


class ConditionalSkillsTests(unittest.TestCase):
    def test_verified_pair_of_actual_assets_passes(self):
        s = scene()
        s["shots"][1].update({
            "comparisonApproved": True, "comparisonBeforeFile": "before.jpg",
            "comparisonAfterFile": "after.jpg",
        })
        validate_editing([s])

    def test_unapproved_or_mismatched_comparison_fails(self):
        s = scene()
        s["shots"][1].update({
            "comparisonApproved": False, "comparisonBeforeFile": "before.jpg",
            "comparisonAfterFile": "after.jpg",
        })
        with self.assertRaises(ValueError):
            validate_editing([s])
        s["shots"][1]["comparisonApproved"] = True
        s["shots"][1]["comparisonAfterFile"] = "invented.png"
        with self.assertRaises(ValueError):
            validate_editing([s])

    def test_explicit_privacy_mask_passes(self):
        s = scene()
        s["shots"][0]["privacyApproved"] = True
        s["shots"][0]["privacyBlurBoxes"] = [{"x": .1, "y": .2, "width": .2, "height": .1}]
        validate_editing([s])

    def test_mask_with_no_approval_fails(self):
        s = scene()
        s["shots"][0]["privacyBlurBoxes"] = [{"x": .1, "y": .2, "width": .2, "height": .1}]
        with self.assertRaises(ValueError):
            validate_editing([s])

    def test_mask_exceeding_frame_fails(self):
        s = scene()
        s["shots"][0]["privacyApproved"] = True
        s["shots"][0]["privacyBlurBoxes"] = [{"x": .8, "y": .2, "width": .4, "height": .1}]
        with self.assertRaises(ValueError):
            validate_editing([s])


if __name__ == "__main__":
    unittest.main()
