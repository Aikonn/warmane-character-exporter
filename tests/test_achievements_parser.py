import json
import unittest
from pathlib import Path

from warmane_exporter.achievements_parser import (
    CategoryError, parse_achievements_response, parse_statistics_response,
)

FIX = Path(__file__).parent / "fixtures" / "real"


class CategoryParserTests(unittest.TestCase):
    def test_achievements_real_sample(self):
        entries = parse_achievements_response((FIX / "achievements-92-sample-aikka-onyxia.json").read_text(encoding="utf-8"))
        self.assertEqual([e["id"] for e in entries], [6, 7, 705, 16])
        self.assertEqual(entries[0]["title"], "Level 10")
        self.assertTrue(entries[0]["earned"])
        self.assertEqual(entries[0]["earned_date"], "2025-02-22")
        self.assertEqual(entries[0]["points"], 10)
        self.assertFalse(entries[2]["earned"])
        self.assertIsNone(entries[2]["earned_date"])
        self.assertEqual(entries[2]["points"], 25)

    def test_statistics_real_sample(self):
        rows = parse_statistics_response((FIX / "statistics-130-aikka-onyxia.json").read_text(encoding="utf-8"))
        self.assertEqual(rows[0], {"name": "Talent tree respecs", "value": "8"})
        self.assertEqual(len(rows), 7)

    def test_rejects_wrong_bodies(self):
        for bad in ("<html>blocked</html>", json.dumps({"x": 1}), json.dumps({"content": "<p>hi</p>"})):
            with self.assertRaises(CategoryError):
                parse_achievements_response(bad)
            with self.assertRaises(CategoryError):
                parse_statistics_response(bad)


if __name__ == "__main__":
    unittest.main()
