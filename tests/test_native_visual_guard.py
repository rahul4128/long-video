import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from validate_native_visuals import (
    _requires_precise_action_footage,
    validate_tutorial_visual_evidence,
)


class NativeTutorialVisualTests(unittest.TestCase):
    def test_culture_stories_not_banned(self):
        self.assertFalse(_requires_precise_action_footage([
            "एक नवरात्रि, तीन अनोखे जश्न: गरबा, गोलू और पंडाल"
        ]))
        validate_tutorial_visual_evidence(
            ["गुजरात में गरबा उत्सव क्यों मनाते हैं?"], None
        )

    def test_step_tutorial_requires_specific_visual_proof(self):
        titles = [
            "गरबा में भीड़ से अलग कैसे दिखें? सरल और शानदार 3 स्टेप्स!",
            "गरबा के आसान स्टेप्स",
        ]
        report = {
            "long": [{"shots": [
                {"type": "video", "queryUsed": "person", "selectionScore": 0.7},
                {"type": "video", "queryUsed": "hands", "selectionScore": 0.78},
                {"type": "video", "queryUsed": "dancer", "selectionScore": 0.82},
            ]}],
            "shorts": [{"shots": [
                {"type": "video", "queryUsed": "dancer", "selectionScore": 0.75}
            ]}],
        }
        self.assertTrue(_requires_precise_action_footage(titles))
        with self.assertRaisesRegex(ValueError, "precise dance steps"):
            validate_tutorial_visual_evidence(titles, report)

    def test_precise_relevant_footage_passes_initial_guard(self):
        titles = ["Learn 3 Garba dance steps", "Garba footwork"]
        shots = [{"type": "video", "queryUsed": "garba dance steps",
                  "selectionScore": 0.82} for _ in range(2)]
        report = {
            "long": [{"shots": shots}],
            "shorts": [{"shots": shots}],
        }
        validate_tutorial_visual_evidence(titles, report)


if __name__ == "__main__":
    unittest.main()
