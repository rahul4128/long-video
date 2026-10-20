"""Cheap tests for GitHub-only replay, without Make tokens or video generation."""
import json
import tempfile
from pathlib import Path
import unittest

from scripts.preflight_payload import prepare
from scripts.validate_festival_timing import validate as validate_festival_timing


def story():
    return {
        "long_video": {"scenes": [{"text": "यह हमारे पुराने मंदिर की कथा है"}]},
        "shorts": {"scenes": [{"text": "सवाल यही है"}]},
        "seo_metadata": {
            "long_video_title": "रहस्यमयी मंदिर की नई कथा",
            "shorts_title": "क्या है इस मंदिर का सच?"
        },
        "correlationId": "verified-10214",
    }


class PreflightPayloadTests(unittest.TestCase):
    def test_workflow_calls_preflight_as_module(self):
        # Running `python scripts/preflight_payload.py` changes sys.path[0] to
        # scripts/ and breaks `from scripts.festival_date_gate import ...`.
        workflow = (Path(__file__).resolve().parents[1] / ".github" /
                    "workflows" / "render.yml").read_text(encoding="utf-8")
        self.assertIn("run: python -m scripts.preflight_payload", workflow)
        self.assertNotIn("run: python scripts/preflight_payload.py", workflow)

    def test_manual_story_file_option_replaces_large_payload_paste(self):
        workflow = (Path(__file__).resolve().parents[1] / ".github" /
                    "workflows" / "render.yml").read_text(encoding="utf-8")
        self.assertIn("      story_file:", workflow)
        self.assertIn("STORY_FILE: ${{ inputs.story_file || '' }}", workflow)
        self.assertIn("inputs.story_file != ''", workflow)

    def test_short_at_filename_reference_works_in_legacy_payload_field(self):
        result = prepare({
            "NEW_DISPATCH_PAYLOAD": "@vijayadashami_2026_10_20_review.json",
            "NEW_PIPELINE": "visual-director-v2-oflifepart31",
            "PUBLICATION_DATE_IST": "2026-10-20",
            "REVIEW_APPROVED": "false",
        })
        episode = json.loads(result["payload"])
        self.assertEqual(episode["seo_metadata"]["shorts_title"],
                         "दशहरे पर शस्त्र पूजा की अनदेखी परंपरा")
        self.assertTrue(result["festival_date_check"]["ok"])

    def test_short_at_filename_reference_never_bypasses_path_safety(self):
        with self.assertRaisesRegex(ValueError, "story_file must be"):
            prepare({"NEW_DISPATCH_PAYLOAD": "@../../secrets.json",
                     "NEW_PIPELINE": "visual-director-v2-oflifepart31"})

    def test_october_review_story_replays_without_make_credits(self):
        checked = prepare({
            "STORY_FILE": "vijayadashami_2026_10_20_review.json",
            "NEW_PIPELINE": "visual-director-v2-oflifepart31",
            "PUBLICATION_DATE_IST": "2026-10-20",
            "REVIEW_APPROVED": "false",
        })
        episode = json.loads(checked["payload"])
        self.assertEqual(len(episode["long_video"]["scenes"]), 6)
        self.assertEqual(len(episode["shorts"]["scenes"]), 5)
        self.assertTrue(checked["festival_date_check"]["ok"])
        # October 20 run #183 failed at the *second* independent date gate,
        # despite passing preflight_payload's first calendar validation.
        second_date_gate = validate_festival_timing(episode, publish_date="2026-10-20")
        self.assertTrue(second_date_gate["ok"], second_date_gate["issues"])
        self.assertEqual(checked["pipeline"], "visual-director-v2-oflifepart31")
        self.assertFalse(checked["source_run_id"])

    def test_saved_story_has_no_packaging_or_spoken_hindi_warnings(self):
        from content_qc import validate_payload
        from spoken_hindi_qc import assess_scenes
        checked = prepare({
            "STORY_FILE": "vijayadashami_2026_10_20_review.json",
            "NEW_PIPELINE": "visual-director-v2-oflifepart31",
            "PUBLICATION_DATE_IST": "2026-10-20",
            "REVIEW_APPROVED": "false",
        })
        story = json.loads(checked["payload"])
        packaging = validate_payload(story)
        self.assertTrue(packaging["ok"])
        for code in (
            "thumbnail_hook_too_long",
            "thumbnail_concepts_should_be_exactly_3",
            "missing_or_invalid_content_role",
        ):
            self.assertNotIn(code, packaging["warnings"])
        narration = assess_scenes(
            story["long_video"]["scenes"], story["shorts"]["scenes"],
            report_path=Path(checked["cache_dir"]) / "spoken_hindi_test.json",
        )
        self.assertEqual(narration["status"], "clear")

    def test_original_uncorrected_story_remains_blocked_by_dates(self):
        with self.assertRaisesRegex(ValueError, "Festival-date preflight BLOCKED"):
            prepare({
                "STORY_FILE": "vijayadashami_2026_10_20_original.json",
                "NEW_PIPELINE": "visual-director-v2-oflifepart31",
                "PUBLICATION_DATE_IST": "2026-10-20",
            })

    def test_story_file_input_cannot_escape_repository_folder(self):
        for filename in ("../../.git/config", "../secrets.json", "/tmp/test.json", "bad.json/"):
            with self.subTest(filename=filename):
                with self.assertRaisesRegex(ValueError, "story_file must be"):
                    prepare({"STORY_FILE": filename, "NEW_PIPELINE": "visual-director-v2-oflifepart31"})

    def test_story_file_input_never_automatically_publishes(self):
        with self.assertRaisesRegex(ValueError, "review-only"):
            prepare({
                "STORY_FILE": "vijayadashami_2026_10_20_review.json",
                "REVIEW_APPROVED": "true",
                "NEW_PIPELINE": "visual-director-v2-oflifepart31",
            })

    def test_truncated_payload_reports_recovery_hint(self):
        with self.assertRaisesRegex(ValueError, "story_file"):
            prepare({
                "NEW_DISPATCH_PAYLOAD": '{"seo":{"thumbnailText":"' + "x" * 1000,
                "NEW_PIPELINE": "visual-director-v2-oflifepart31",
            })

    def test_raw_make_story_is_cached(self):
        src = json.dumps(story(), ensure_ascii=False)
        x = prepare({"NEW_DISPATCH_PAYLOAD": src, "NEW_PIPELINE": "visual-director-v2-oflifepart31"})
        self.assertEqual(json.loads(x["payload"])["correlationId"], "verified-10214")
        self.assertEqual(x["pipeline"], "visual-director-v2-oflifepart31")
        self.assertEqual(len(x["payload_sha256"]), 64)

    def test_make_github_dispatch_envelope_preserves_scope(self):
        envelope = {"ref":"visual-director-v2", "inputs": {
            "payload":json.dumps(story(), ensure_ascii=False),
            "pipeline":"visual-director-v2-oflifepart31",
            "qc_verdict":"PASS",
        }}
        x = prepare({"NEW_DISPATCH_PAYLOAD":json.dumps(envelope,ensure_ascii=False),
                     "NEW_PIPELINE":"canva-updated-flow"})
        self.assertEqual(x["pipeline"], "visual-director-v2-oflifepart31")

    def test_replay_uses_same_script_and_hash(self):
        first = prepare({"NEW_DISPATCH_PAYLOAD":json.dumps(story(),ensure_ascii=False),
                         "NEW_PIPELINE":"visual-director-v2-oflifepart31"})
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "replay_inputs.json"
            p.write_text(json.dumps(first), encoding="utf-8")
            x = prepare({"REPLAY_RUN_ID":"38494884403","REVIEW_APPROVED":"false"},replay_path=p)
            self.assertEqual(first["payload_sha256"], x["payload_sha256"])
            self.assertEqual(first["payload"], x["payload"])

    def test_replay_cannot_be_automatically_published(self):
        with self.assertRaises(ValueError):
            prepare({"REPLAY_RUN_ID":"38494884403","REVIEW_APPROVED":"true"})

    def test_missing_scenes_and_no_payload_fails(self):
        with self.assertRaises(ValueError):
            prepare({"NEW_DISPATCH_PAYLOAD":"{}","NEW_PIPELINE":"visual-director-v2-oflifepart31"})
        with self.assertRaises(ValueError):
            prepare({"REPLAY_RUN_ID":"38494884403","REVIEW_APPROVED":"false"},
                    replay_path="nonexistent-story-file.json")


if __name__=="__main__":
    unittest.main()
