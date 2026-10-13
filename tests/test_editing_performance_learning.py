"""Source-labeled editing history must not hallucinate trend scores."""
from datetime import date
import tempfile
import unittest
from pathlib import Path
from scripts.build_editing_style_signals import summarize
from editing_style_engine import select_edit_style


class StyleLearningTests(unittest.TestCase):
    @staticmethod
    def rows(n=3):
        return [{
            "video_id": f"real-video-{i}", "platform":"instagram",
            "editing_style":"presenter_explainer",
            "published_on":"2026-10-12", "views":400+i*20,
            "shares":10+i, "video_duration_seconds":60,
            "average_view_duration_seconds":40+i,
            "evidence_url":f"https://example.org/reports/creator/video-{i}",
        } for i in range(n)]

    def test_minimum_three_distinct_videos(self):
        self.assertEqual(summarize(self.rows(2),now=date(2026,10,13)),[])
        data=summarize(self.rows(),now=date(2026,10,13))
        self.assertEqual(len(data),1)
        self.assertEqual(data[0]["videos"],3)
        self.assertGreater(data[0]["average_view_percentage"],60)

    def test_reject_duplicates_missing_evidence_old_stats(self):
        old=self.rows()[0].copy()
        old["video_id"]="old"
        old["published_on"]="2025-10-12"
        duplicate=self.rows()[0].copy()
        denied=self.rows()[0].copy()
        denied["video_id"]="not-evidenced"
        denied["evidence_url"]=""
        self.assertEqual(summarize([self.rows()[0],duplicate,old,denied],
                                   now=date(2026,10,13)),[])

    def test_no_data_never_claims_trend(self):
        with tempfile.TemporaryDirectory() as tmp:
            # Empty repository history leaves the story-based selector intact.
            result=select_edit_style({"seo_metadata":{"long_video_title":"मंदिर का रहस्य"}},[])
            self.assertEqual(result["style"],"curiosity_reveal")
            self.assertEqual(result["trend_claim"],"not_verified")


if __name__ == "__main__":
    unittest.main()
