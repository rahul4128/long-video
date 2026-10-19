"""Offline fixed-date tests: no Make credits, no external network, no Canva."""
import unittest
from scripts.festival_date_gate import validate_festival_date_claims


def story(title, narration, shorts="", description=""):
    return {
        "seo_metadata": {
            "long_video_title": title, "shorts_title": shorts or title,
            "long_video_description": description,
        },
        "long_video": {"scenes": [{"text": narration}]},
        "shorts": {"scenes": [{"text": narration}]},
        "thumbnail": {"thumbnailText": "उत्सव की सीख"},
    }


class FestivalDateGateTests(unittest.TestCase):
    def check(self, title, narration, day="2026-10-19", **kwargs):
        return validate_festival_date_claims(
            story(title, narration, **kwargs), publish_date=day
        )

    def test_oct19_vijayadashami_after_vs_tomorrow_is_blocked(self):
        report = self.check(
            "विजयदशमी के बाद: क्या आपके भीतर बदलाव आया?",
            "कल विजयदशमी है। अहंकार पर विजय का अर्थ समझिए।",
        )
        self.assertFalse(report["ok"])
        self.assertTrue(any("after" in x for x in report["issues"]))

    def test_oct19_tomorrow_vijayadashami_is_valid(self):
        report = self.check(
            "कल विजयदशमी है: क्या सीखें?",
            "कल विजयदशमी है। तैयारी करिए।",
        )
        self.assertTrue(report["ok"], report["issues"])

    def test_oct19_vijayadashami_today_is_blocked(self):
        report = self.check("आज विजयदशमी है", "आज विजयदशमी है।")
        self.assertFalse(report["ok"])

    def test_oct20_today_vijayadashami_is_valid(self):
        report = self.check(
            "आज विजयदशमी है", "आज विजयदशमी है।", day="2026-10-20",
        )
        self.assertTrue(report["ok"], report["issues"])

    def test_future_puja_preparation_is_allowed(self):
        report = self.check(
            "करवा चौथ की तैयारी कैसे करें?",
            "करवा चौथ आने वाली है, पूजा की थाली तैयार करें।",
        )
        self.assertTrue(report["ok"], report["issues"])

    def test_after_festival_allowed_only_from_next_day(self):
        report = self.check(
            "विजयदशमी के बाद क्या सीखें?",
            "विजयदशमी के बाद भी अच्छी आदतें बनाएं।",
            day="2026-10-21",
        )
        self.assertTrue(report["ok"], report["issues"])

    def test_rerun_on_new_day_revalidates_relative_claims(self):
        report = self.check(
            "कल विजयदशमी है", "कल विजयदशमी है।", day="2026-10-20",
        )
        self.assertFalse(report["ok"])

    def test_unverified_final_navratri_day_claim_is_blocked(self):
        report = self.check(
            "आज नवरात्रि का अंतिम दिन है",
            "आज नवरात्रि का अंतिम दिन है।",
        )
        self.assertFalse(report["ok"])

    def test_evergreen_nonfestival_story_not_blocked(self):
        report = self.check(
            "भक्ति और धैर्य का संबंध",
            "एक बूढ़े आदमी ने धैर्य की बात कही।",
        )
        self.assertTrue(report["ok"], report["issues"])
        self.assertEqual(report["relative_claims"], [])

    def test_short_description_also_checked(self):
        report = self.check(
            "कल विजयदशमी है",
            "कल विजयदशमी है।",
            description="आज विजयदशमी है।",
        )
        self.assertFalse(report["ok"])
        self.assertTrue(any("long description" in x for x in report["issues"]))


if __name__ == "__main__":
    unittest.main()
