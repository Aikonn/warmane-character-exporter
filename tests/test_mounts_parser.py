import unittest
from pathlib import Path

from warmane_exporter.mounts_parser import MountsError, parse_mounts_page

FIX = Path(__file__).parent / "fixtures" / "real" / "mounts-sample-aikka-onyxia.html"


class MountsTests(unittest.TestCase):
    def test_real_sample(self):
        data = parse_mounts_page(FIX.read_text(encoding="utf-8"))
        self.assertEqual(data["mounts"][0], {"name": "Blue Wind Rider", "item_id": 25475, "npc_id": 17700})
        self.assertEqual(len(data["mounts"]), 2)
        self.assertEqual(data["companions"][0]["name"], "Mojo")

    def test_rejects_other_pages(self):
        with self.assertRaises(MountsError):
            parse_mounts_page("<html></html>")


if __name__ == "__main__":
    unittest.main()
