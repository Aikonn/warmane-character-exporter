"""Sanity checks for the real-response fixtures (Milestone 0 evidence)."""

import json
import re
import unittest
from pathlib import Path

REAL = Path("tests/fixtures/real")


class RealFixtureTests(unittest.TestCase):
    def test_api_summary_shape(self) -> None:
        for name in ("api-summary-aikka-onyxia.json", "api-summary-bezduse-icecrown.json"):
            data = json.loads((REAL / name).read_text(encoding="utf-8"))
            for key in ("name", "realm", "class", "equipment", "talents", "professions", "pvpteams"):
                self.assertIn(key, data, name)
            for item in data["equipment"]:
                self.assertEqual(set(item), {"name", "item", "transmog"})
                self.assertTrue(item["item"].isdigit())
            for tree in data["talents"]:
                self.assertEqual(len(tree["points"]), 3)

    def test_achievement_sample_has_earned_and_locked(self) -> None:
        html = json.loads((REAL / "achievements-92-sample-aikka-onyxia.json").read_text(encoding="utf-8"))["content"]
        self.assertEqual(len(re.findall(r'class="achievement locked"', html)), 2)
        self.assertEqual(len(re.findall(r"Earned \d\d/\d\d/\d{4}", html)), 2)
        self.assertEqual(html.count('class="title"'), 4)

    def test_statistics_sample_is_description_value_table(self) -> None:
        html = json.loads((REAL / "statistics-130-aikka-onyxia.json").read_text(encoding="utf-8"))["content"]
        self.assertIn("Talent tree respecs", html)


if __name__ == "__main__":
    unittest.main()