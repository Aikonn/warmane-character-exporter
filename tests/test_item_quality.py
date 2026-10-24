import unittest
from pathlib import Path

from warmane_exporter.summary_parser import parse_summary_capture_file

CAPTURE = Path(__file__).resolve().parents[1] / "local-captures" / "bezduse-onyxia-summary-dom.html"


@unittest.skipUnless(CAPTURE.exists(), "local capture not available (git-ignored)")
class QualityTests(unittest.TestCase):
    def test_every_item_has_quality(self):
        parsed = parse_summary_capture_file(CAPTURE)
        slots = [s for s in parsed["equipment"]["slots"] if not s["is_empty"]]
        self.assertTrue(slots)
        for slot in slots:
            ref = slot["item_reference"]
            self.assertIn(ref["quality"], range(0, 8))
            self.assertTrue(ref["quality_name"])
        self.assertEqual(slots[0]["item_reference"]["quality_name"], "epic")


if __name__ == "__main__":
    unittest.main()
