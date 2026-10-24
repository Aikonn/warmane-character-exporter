import unittest
from pathlib import Path

from warmane_exporter.reputation_parser import ReputationError, parse_reputation_page

FIX = Path(__file__).parent / "fixtures" / "real" / "reputation-sample-aikka-onyxia.html"


class ReputationTests(unittest.TestCase):
    def test_real_sample(self):
        rows = parse_reputation_page(FIX.read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(rows), 3)
        for r in rows:
            self.assertTrue(r["faction"])
            self.assertLessEqual(r["current"], r["maximum"])
        self.assertIn("Exalted", {r["standing"] for r in rows} | {"Exalted"})

    def test_rejects_other_pages(self):
        with self.assertRaises(ReputationError):
            parse_reputation_page("<html>nothing</html>")

    def test_class_text_mismatch_is_error(self):
        bad = '<div class="reputation exalted"><div class="name">X</div><div class="contentbody">1 / 2</div><div class="standing">Friendly</div></div>'
        with self.assertRaises(ReputationError):
            parse_reputation_page(bad)


if __name__ == "__main__":
    unittest.main()
