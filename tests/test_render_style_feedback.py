"""Offline P2 verification of real render attribution and measured editing feedback."""
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest

from scripts.render_style_attribution import append_actual_style, scope_from_pipeline
from scripts.ingest_editing_feedback import compute_channel_signals


NOW = datetime(2026, 11, 1, tzinfo=timezone.utc)


def evidence(count=3, account="oflifepart31"):
    ledger, ids, titles, published, rows = [], [], [], [], []
    for index in range(count):
        render = {
            "account": account, "githubRunId": str(10001 + index),
            "correlationId": f"run-{index}", "renderedAt": "2026-10-10T10:00:00+00:00",
            "editingStyle": "presenter_explainer",
            "longTitle": f"मंदिर की कथा {index}",
            "shortsTitle": f"कथा का छोटा उत्तर {index}",
            "status": "qc_passed_rendered_not_proof_of_youtube_publication",
        }
        ledger.append(render)
        for fmt, title in (("long", render["longTitle"]), ("shorts", render["shortsTitle"])):
            vid = "v" + str(index * 2 + (fmt == "shorts")).zfill(10)
            ids.append(vid)
            titles.append(title)
            published.append("2026-10-15T11:00:00Z")
            rows.append([vid, 450, 55 + index, 8])
    analytics = {
        "kind": "youtubeAnalytics#resultTable",
        "columnHeaders": [{"name": n} for n in (
            "video", "views", "averageViewPercentage", "shares"
        )],
        "rows": rows,
    }
    return ledger, analytics, ids, titles, published


class RenderAttributionTests(unittest.TestCase):
    def test_scope_and_persisted_identity(self):
        self.assertEqual(scope_from_pipeline("visual-director-v2-oflifepart31"),
                         "oflifepart31")
        self.assertEqual(scope_from_pipeline("visual-director-v2"),
                         None)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ledger.json"
            info = {"correlationId": "run-123", "long_video_title": "क्या है प्राचीन मंदिर का अर्थ?",
                    "shorts_title": "क्या है इस मंदिर का अर्थ?"}
            report = {"enabled": True, "selectedStyle": "presenter_explainer",
                      "editorVersion": 2}
            ok, record = append_actual_style(
                path, info, report, run_id=12345, scope="oflifepart31", now=NOW
            )
            self.assertTrue(ok)
            self.assertEqual(record["editingStyle"], "presenter_explainer")
            self.assertEqual(json.loads(path.read_text())[0]["correlationId"], "run-123")
            ok, unused = append_actual_style(
                path, info, report, run_id=12345, scope="oflifepart31", now=NOW
            )
            self.assertTrue(ok)
            self.assertEqual(len(json.loads(path.read_text())), 1)

    def test_conflicting_story_rerender_is_quarantined_not_fatal(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "history.json"
            info = {
                "correlationId": "already-rendered-story",
                "long_video_title": "दशहरे के दिन शस्त्र पूजा क्यों होती है?",
                "shorts_title": "शस्त्र पूजा का अर्थ",
            }
            report = {"enabled": True, "selectedStyle": "presenter_explainer"}
            saved, original = append_actual_style(
                ledger, info, report, run_id=39382937625, scope="oflifepart31", now=NOW)
            self.assertTrue(saved)
            saved2, reason = append_actual_style(
                ledger, info, report, run_id=39430769405, scope="oflifepart31", now=NOW)
            self.assertFalse(saved2)
            self.assertEqual(reason, "conflicting_render_correlation_requires_review")
            self.assertEqual(json.loads(ledger.read_text()), [original])

    def test_reject_unattributed_renders(self):
        with tempfile.TemporaryDirectory() as tmp:
            success, reason = append_actual_style(
                Path(tmp) / "ledger", {"correlationId": "run-8"},
                {"enabled": True, "selectedStyle": "presenter_explainer"},
                run_id=10012, scope=None
            )
            self.assertFalse(success)
            self.assertEqual(reason, "unattributed_account_scope")


class AnalyticsAttributionTests(unittest.TestCase):
    def test_only_own_account_and_mature_exact_matches(self):
        args = evidence()
        signals, audit = compute_channel_signals(*args, scope="oflifepart31", now=NOW)
        self.assertEqual(len(audit["matchedVideos"]), 6)
        self.assertEqual(len(signals), 2)
        self.assertEqual({s["format"] for s in signals}, {"shorts", "long"})
        self.assertEqual({s["videos"] for s in signals}, {3})
        others, _ = compute_channel_signals(*args, scope="primary", now=NOW)
        self.assertEqual(others, [])

    def test_insufficient_sample_and_immature_uploads(self):
        args = evidence(2)
        signals, audit = compute_channel_signals(*args, scope="oflifepart31", now=NOW)
        self.assertEqual(signals, [])
        self.assertEqual(len(audit["matchedVideos"]), 4)
        args = evidence()
        too_soon = ["2026-10-31T00:00:00Z"] * len(args[2])
        signals, audit = compute_channel_signals(
            args[0], args[1], args[2], args[3], too_soon,
            scope="oflifepart31", now=NOW
        )
        self.assertFalse(signals)
        self.assertEqual(audit["matchedVideos"], [])

    def test_reused_title_and_video_from_before_render_do_not_learn(self):
        ledger, analytics, ids, titles, published = evidence()
        ledger[1]["longTitle"] = ledger[0]["longTitle"]
        signals, audit = compute_channel_signals(
            ledger, analytics, ids, titles, published, scope="oflifepart31", now=NOW
        )
        self.assertEqual(len([x for x in audit["matchedVideos"] if x["format"]=="long"]), 1)
        self.assertFalse(any(x["format"]=="long" for x in signals))
        old = ["2026-10-09T08:00:00Z"] * len(ids)
        other, _ = compute_channel_signals(
            *evidence()[:3], titles, old, scope="oflifepart31", now=NOW
        )
        self.assertFalse(other)


if __name__ == "__main__":
    unittest.main()
