"""Regression tests for the Garba visual-mismatch false PASS."""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from validate_native_visuals import (
    _requires_precise_action_footage,
    validate_tutorial_visual_evidence,
)
from visual_evidence import (
    detect_instructional_category,
    is_generic_stock_query,
    validate_demonstration_evidence,
)


class NativeTutorialVisualTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.manifest = self.root / "approved_clips.json"
        self.title = "गरबा में भीड़ से अलग कैसे दिखें? सरल और शानदार 3 स्टेप्स!"
        self.shorts = "गरबा के आसान स्टेप्स"

    def tearDown(self):
        self.tmp.cleanup()

    def test_cultural_celebration_works_automatically(self):
        title = "एक नवरात्रि, तीन अनोखे जश्न: गरबा, गोलू और पंडाल"
        self.assertFalse(_requires_precise_action_footage([title]))
        validate_tutorial_visual_evidence([title], None)
        self.assertFalse(detect_instructional_category(["गुजरात में गरबा उत्सव क्यों मनाते हैं?"]))

    def test_other_hands_on_promises_are_detected(self):
        self.assertEqual(detect_instructional_category(["Learn yoga pose steps"]), "fitness")
        self.assertEqual(detect_instructional_category(["Cooking recipe step by step"]), "cooking")
        self.assertEqual(detect_instructional_category(["Learn origami craft tutorial"]), "craft")

    def test_generic_stock_queries_are_excluded(self):
        self.assertTrue(is_generic_stock_query(" person "))
        self.assertTrue(is_generic_stock_query("HANDS"))
        self.assertTrue(is_generic_stock_query("dancer"))
        self.assertFalse(is_generic_stock_query("authentic garba dance footwork Gujarat"))

    def test_specific_query_and_high_clip_score_are_not_proof(self):
        """This passed incorrectly before; now it must fail closed."""
        report = {
            "long": [{"shots": [{"type": "video", "queryUsed": "garba dance steps",
                                   "selectionScore": 0.99} for _ in range(3)]}],
            "shorts": [{"shots": [{"type": "video", "queryUsed": "garba dance steps",
                                     "selectionScore": 0.99}]}],
        }
        long = [{"text": "पहला गरबा स्टेप सीखें",
                 "shots": [{"type": "video", "file": "fake.mp4"}]}]
        shorts = [{"text": "तीन गरबा स्टेप सीखें",
                   "shots": [{"type": "video", "file": "fake.mp4"}]}]
        with self.assertRaisesRegex(ValueError, "verified demonstration footage"):
            validate_tutorial_visual_evidence(
                [self.title, self.shorts], report,
                long_scenes=long, shorts_scenes=shorts,
                manifest_path=self.manifest, media_root=self.root,
            )

    def prepare(self):
        media = self.root / "actual-demo.mp4"
        media.write_bytes(b"human-reviewed-video-demo-contents")
        digest = hashlib.sha256(media.read_bytes()).hexdigest()
        manifest = {"version": 1, "reviewed_clips": [
            {"file": "actual-demo.mp4", "format": fmt, "scene": 1,
             "category": "dance", "sha256": digest, "reviewer": "human editor",
             "human_reviewed": True, "step_label": "two-clap garba footwork"}
            for fmt in ("long", "shorts")
        ]}
        self.manifest.write_text(json.dumps(manifest))
        scenes = [{"text": "ये दो गरबा स्टेप सीखें",
                   "shots": [{"type": "video", "file": "actual-demo.mp4"}]}]
        return scenes, scenes

    def test_verified_exact_file_passes_review_contract(self):
        long, short = self.prepare()
        validate_tutorial_visual_evidence(
            [self.title], {}, long_scenes=long, shorts_scenes=short,
            manifest_path=self.manifest, media_root=self.root,
        )

    def test_same_search_query_but_wrong_bytes_rejected(self):
        long, short = self.prepare()
        (self.root / "actual-demo.mp4").write_bytes(b"replaced-generic-person-stock")
        with self.assertRaisesRegex(ValueError, "hash differs"):
            validate_demonstration_evidence(
                [self.title], long, short, {}, self.manifest, self.root,
            )

    def test_wrong_scene_or_unreviewed_clip_rejected(self):
        long, short = self.prepare()
        data = json.loads(self.manifest.read_text())
        data["reviewed_clips"][0]["human_reviewed"] = False
        self.manifest.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, "human-reviewed provenance"):
            validate_demonstration_evidence(
                [self.title], long, short, {}, self.manifest, self.root,
            )

    def test_every_narrated_instruction_scene_needs_matching_approved_clip(self):
        long, short = self.prepare()
        long.append({"text": "अब अगला गरबा स्टेप सीखिए",
                     "shots": [{"type": "video", "file": "unverified.mp4"}]})
        with self.assertRaisesRegex(ValueError, "long scene 2"):
            validate_demonstration_evidence(
                [self.title], long, short, {}, self.manifest, self.root,
            )


if __name__ == "__main__":
    unittest.main()
