import unittest
from pathlib import Path

from test_report import SNAP
from warmane_exporter.export import build_full_report, render_full_markdown

FIX = Path(__file__).parent / "fixtures" / "real"


class ExportTests(unittest.TestCase):
    def test_missing_parts_are_listed_not_invented(self):
        r = build_full_report(SNAP, None, None, None, None)
        self.assertEqual(r["missing_sections"], ["achievements", "statistics", "reputation", "mounts", "companions"])
        self.assertIn("## Missing sections", render_full_markdown(r))

    def test_full_merge(self):
        ach = {"complete": True, "categories": [
            {"id": 92, "name": "General", "parent": None, "status": "ok", "entries": [
                {"id": 6, "title": "Level 10", "points": 10, "earned": True, "earned_date": "2025-02-22"}]},
            {"id": 14861, "name": "Classic", "parent": 96, "status": "ok", "entries": []}]}
        stats = {"complete": True, "categories": [{"id": 130, "name": "Character", "parent": None, "status": "ok",
                                                   "entries": [{"name": "Respecs", "value": "8"}]}]}
        rep = (FIX / "reputation-sample-aikka-onyxia.html").read_text(encoding="utf-8")
        mounts = (FIX / "mounts-sample-aikka-onyxia.html").read_text(encoding="utf-8")
        r = build_full_report(SNAP, ach, stats, rep, mounts)
        self.assertEqual(r["missing_sections"], [])
        self.assertEqual(r["achievements"]["summary"]["earned_points"], 10)
        md = render_full_markdown(r)
        for needle in ("## Achievements", "- Respecs: 8", "## Reputation", "Blue Wind Rider", "Mojo"):
            self.assertIn(needle, md)


if __name__ == "__main__":
    unittest.main()
