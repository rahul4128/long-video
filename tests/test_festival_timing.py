"""No-credit regression tests for the festival-date gate.

The October 19 production failure must be rejected without contacting Gemini,
Canva, Make, Google, or any other live service.
"""
from datetime import date
import unittest

from scripts.validate_festival_timing import validate


def sample(*, title="करवा चौथ की तैयारी", scene="करवा चौथ से जुड़ी परंपराओं को समझें।", basis=""):
    return {
        "_meta": {"decisionBasis": basis},
        "seo_metadata": {
            "long_video_title": title,
            "shorts_title": "करवा चौथ की तैयारी कैसे करें?",
            "long_video_description": "परंपराओं और तैयारी की उपयोगी जानकारी।",
        },
        "long_video": {"scenes": [{"text": scene}]},
        "shorts": {"scenes": [{"text": "सही जानकारी और तैयारी से शुरुआत करें।"}]},
        "thumbnail": {"thumbnailText": "एक सरल तैयारी"},
    }


class FestivalDateGateTests(unittest.TestCase):
    def check(self, payload, day="2026-10-19"):
        return validate(payload, publish_date=day)

    def test_oct19_vijayadashami_after_title_is_blocked(self):
        payload = sample(
            title="विजयदशमी के बाद: क्या आपके भीतर बदलाव आया?",
            scene="कल विजयदशमी है। अपनी तैयारी समय से करें।",
            basis="EVENT_DATE: 2026-10-20, DATE_SOURCE: DRIP_PANCHANG",
        )
        report = self.check(payload)
        self.assertFalse(report["ok"], report)
        self.assertTrue(any("already finished" in issue for issue in report["issues"]), report)

    def test_oct19_tomorrow_vijayadashami_is_correct(self):
        self.assertTrue(self.check(sample(
            title="विजयदशमी की तैयारी",
            scene="कल विजयदशमी है। तैयारी का समय आ गया है।"
        ))["ok"])

    def test_oct20_tomorrow_vijayadashami_is_wrong(self):
        r = self.check(sample(
            title="विजयदशमी की तैयारी",
            scene="कल विजयदशमी है। पूजा की तैयारी करें।"
        ), day="2026-10-20")
        self.assertFalse(r["ok"])
        self.assertTrue(any("'tomorrow'" in issue for issue in r["issues"]))

    def test_explicit_today_vijayadashami_must_match_calendar(self):
        p = sample(title="आज विजयदशमी है", scene="आज विजयदशमी है।")
        self.assertFalse(self.check(p, day="2026-10-19")["ok"])
        self.assertTrue(self.check(p, day="2026-10-20")["ok"])

    def test_after_vijayadashami_is_allowed_only_after_event(self):
        p = sample(title="विजयदशमी के बाद नई शुरुआत")
        self.assertFalse(self.check(p, day="2026-10-19")["ok"])
        self.assertTrue(self.check(p, day="2026-10-21")["ok"])

    def test_oct18_false_last_navratri_day_blocked(self):
        p = sample(title="नवरात्रि पर क्या करें?", scene="आज नवरात्रि का अंतिम दिन है।")
        self.assertFalse(self.check(p, day="2026-10-18")["ok"])
        self.assertTrue(self.check(p, day="2026-10-19")["ok"])

    def test_oct19_navratri_nine_days_already_over_is_blocked(self):
        p = sample(scene="नवरात्रि के नौ दिन बीत गए। आगे कैसे बढ़ें?")
        self.assertFalse(self.check(p, day="2026-10-19")["ok"])

    def test_imminent_karwa_chauth_preparation_is_allowed(self):
        p = sample(
            title="करवा चौथ की तैयारी के लिए आसान उपाय",
            scene="करवा चौथ आने वाला है। अभी से तैयारी करें।",
            basis="EVENT_DATE: 2026-10-29, PUBLISH_BEFORE: 2026-10-19",
        )
        self.assertTrue(self.check(p, day="2026-10-19")["ok"])

    def test_wrong_meta_event_date_is_rejected(self):
        p = sample(
            title="करवा चौथ की तैयारी",
            scene="करवा चौथ की परंपरा और पूजा सामग्री।",
            basis="EVENT_DATE: 2026-10-30, DATE_SOURCE: some AI guess",
        )
        self.assertFalse(self.check(p)["ok"])

    def test_evergreen_no_dates_is_allowed(self):
        p = sample(
            title="धैर्य रखने का सबसे सरल तरीका",
            scene="क्या कभी सोचा है कि धैर्य क्यों जरूरी है?",
            basis="",
        )
        self.assertTrue(self.check(p)["ok"])

    def test_published_next_day_uses_explicit_publish_date(self):
        p = sample(title="विजयदशमी के बाद नया संकल्प")
        self.assertFalse(self.check(p, "2026-10-20")["ok"])
        self.assertTrue(self.check(p, "2026-10-21")["ok"])

    def test_invalid_publication_date_fails(self):
        with self.assertRaises(ValueError):
            self.check(sample(), day="20-10-2026")

    def test_relative_claim_without_verified_calendar_fails(self):
        p = sample(title="आज दिवाली है")
        missing_calendar = {"sources": [], "checked_at": "2026-10-09"}
        self.assertFalse(validate(p, publish_date="2026-11-08", calendar=missing_calendar)["ok"])


if __name__ == "__main__":
    unittest.main()
