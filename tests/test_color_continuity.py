"""Offline, synthetic, no-dependency tests for bounded color matching."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from color_continuity import _sample, inspect_shots, validate_corrections


def ppm(path, rgb):
    # FFmpeg supports the PPM format natively; no Pillow dependency needed.
    path.write_bytes(b"P6\n36 36\n255\n" + bytes(rgb) * (36 * 36))


class ColorContinuityTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg required")
    def test_bounded_matches_preserve_footage_and_timing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ppm(root / "dark.ppm", (73, 67, 65))
            ppm(root / "light.ppm", (180, 175, 171))
            scenes = [{"scene_number": 1, "shots": [
                {"file": "dark.ppm", "type": "image", "startSeconds": 0, "endSeconds": 2},
                {"file": "light.ppm", "type": "image", "startSeconds": 2, "endSeconds": 4},
            ]}]
            report = inspect_shots(scenes, [], media_root=root,
                                   report_path=root / "colors.json")
            self.assertEqual(report["samples"], 2)
            self.assertEqual(report["formats"]["long"]["shotCount"], 2)
            validate_corrections(scenes)
            for shot in scenes[0]["shots"]:
                self.assertLessEqual(shot["colorCorrection"]["brightness"], 1.08)
                self.assertGreaterEqual(shot["colorCorrection"]["brightness"], .92)
            self.assertEqual(scenes[0]["shots"][1]["startSeconds"], 2)
            self.assertTrue((root / "colors.json").exists())

    @unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg required")
    def test_dark_atmosphere_protected_and_warned(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "temple.ppm"
            ppm(p, (8, 9, 10))
            scenes = [{"scene_number": 1, "shots": [
                {"file": p.name, "type": "image"},
            ]}]
            result = inspect_shots(scenes, [], media_root=tmp,
                                   report_path=Path(tmp) / "report.json")
            self.assertEqual(scenes[0]["shots"][0]["colorCorrection"]["brightness"], 1.0)
            self.assertTrue(any("artistic_or_extreme_lighting_preserved" in w["codes"]
                                for w in result["warnings"]))

    @unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg required")
    def test_large_exposure_jump_uses_soft_transition_without_brightening_dark_art(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ppm(root / "dark.ppm", (10, 11, 12))
            ppm(root / "bright.ppm", (210, 200, 191))
            shots = [
                {"file": "dark.ppm", "type": "image", "transition": "cut"},
                {"file": "bright.ppm", "type": "image", "transition": "cut"},
            ]
            report = inspect_shots(
                [{"scene_number": 1, "shots": shots}], [],
                media_root=root, report_path=root / "report.json",
            )
            self.assertEqual(shots[0]["colorCorrection"]["brightness"], 1.0)
            self.assertEqual(shots[1]["transition"], "crossfade")
            self.assertTrue(any(m["type"] == "high_contrast_cut_softened" for m in report["mitigations"]))
            self.assertTrue(any(
                "artistic_or_extreme_lighting_preserved" in warning["codes"]
                for warning in report["warnings"]
            ))

    def test_untrusted_parent_path_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            scenes = [{"scene_number": 1, "shots": [{"file": "../secret.jpg", "type": "image"}]}]
            report = inspect_shots(scenes, [], media_root=tmp,
                                   report_path=Path(tmp) / "report.json")
            self.assertEqual(report["samples"], 0)
            self.assertEqual(scenes[0]["shots"][0]["colorCorrection"]["brightness"], 1.0)

    def test_invalid_values_fail(self):
        with self.assertRaises(ValueError):
            validate_corrections([{"shots": [{"colorCorrection": {"brightness": 2, "saturation": 1}}]}])

    def test_disable_preserves_original_shots(self):
        with tempfile.TemporaryDirectory() as tmp:
            shots = [{"file": "not_there.jpg", "type": "image"}]
            report = inspect_shots([{"shots": shots}], [], media_root=tmp,
                                   report_path=Path(tmp) / "report.json", enabled=False)
            self.assertFalse(report["enabled"])
            self.assertNotIn("colorCorrection", shots[0])


if __name__ == "__main__":
    unittest.main()
