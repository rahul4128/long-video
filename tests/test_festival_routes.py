"""Deterministic checks for source-linked Indian festival topic routing."""
import json
import re
import unittest
from datetime import date, timedelta
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data/festival_routes_2026.json"


class FestivalRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.feed = json.loads(DATA.read_text(encoding="utf-8"))
        cls.daily = cls.feed["daily"]

    def test_dates_are_valid_source_linked_and_current(self):
        dates = sorted(self.daily)
        self.assertEqual(dates[0], self.feed["coverage_start"])
        self.assertEqual(dates[-1], self.feed["coverage_end"])
        for day, route in self.daily.items():
            self.assertEqual(day, date.fromisoformat(day).isoformat())
            self.assertEqual(day, route["date_ist"])
            self.assertEqual(route["priority"], "FESTIVAL_FIRST")
            self.assertTrue(route["source_url"].startswith("https://"))
            self.assertIn(route["phase"], {"PREPARATION", "ACTIVE", "FINAL_DAY"})
            self.assertGreaterEqual(len(route["candidate_angles"]), 2)
            self.assertTrue(route["title_regex"])
            self.assertGreaterEqual(date.fromisoformat(route["festival_end"]),
                                    date.fromisoformat(day) if route["phase"] != "PREPARATION"
                                    else date.fromisoformat(route["festival_start"]))
            self.assertTrue(route["festival_id"])

    def test_navratri_preparation_to_vijayadashami(self):
        for day, phase in [("2026-10-09", "PREPARATION"),
                           ("2026-10-11", "ACTIVE"),
                           ("2026-10-19", "FINAL_DAY")]:
            route = self.daily[day]
            self.assertEqual(route["festival_id"], "sharad-navratri-2026")
            self.assertEqual(route["phase"], phase)
            self.assertTrue(any("गरबा" in x or "डांडिया" in x
                                for x in route["candidate_angles"]))
        self.assertEqual(self.daily["2026-10-20"]["festival_id"], "vijayadashami-2026")
        self.assertEqual(self.daily["2026-10-21"]["festival_id"], "karwa-chauth-2026")

    def test_routes_accept_youth_entertainment_not_generic_evergreen(self):
        regex = self.daily["2026-10-09"]["title_regex"]
        self.assertTrue(re.search(regex, "गरबा के 3 आसान स्टेप्स सीखें"))
        self.assertTrue(re.search(regex, "नवरात्रि में घर की तैयारी"))
        self.assertTrue(re.search(regex, "Garba For Beginners"))
        self.assertIsNone(re.search(regex, "दैनिक पूजा के गुप्त नियम: क्या फल मिल रहा है"))
        self.assertIsNone(re.search(regex, "प्राचीन मंदिर के खंभे का रहस्य"))

    def test_multi_day_chhath_until_last_day(self):
        expected = [(13,"ACTIVE"),(14,"ACTIVE"),(15,"ACTIVE"),(16,"FINAL_DAY")]
        for d, phase in expected:
            route=self.daily[f"2026-11-{d:02d}"]
            self.assertEqual(route["festival_id"],"chhath-2026")
            self.assertEqual(route["phase"],phase)
        self.assertEqual(self.daily["2026-11-17"]["festival_id"],"tulsi-vivah-2026")

    def test_end_of_verified_feed_is_explicit(self):
        self.assertEqual(self.feed["year"],2026)
        self.assertEqual(self.feed["timezone"],"Asia/Kolkata")
        self.assertEqual(self.feed["fallback"]["priority"],"EVERGREEN_OR_VERIFY")
        self.assertNotIn("2027-10-09",self.daily)
        self.assertTrue(all(x["source"].startswith("https://")
                            for x in self.feed["sources"]))


if __name__ == "__main__":
    unittest.main()
