"""Cheap tests for GitHub-only replay, without Make tokens or video generation."""
import json
import tempfile
from pathlib import Path
import unittest

from scripts.preflight_payload import prepare


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
