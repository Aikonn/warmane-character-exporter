import unittest

from warmane_exporter.report import build_report, render_markdown

SNAP = {
    "schema": "character-snapshot/0",
    "generated_at": "t",
    "sections": {
        "json_summary": {"status": "ok", "data": {
            "name": "X", "realm": "Onyxia", "level": 80, "faction": "Horde", "race": "Orc", "class": "Priest",
            "guild": "G", "achievement_points": 1, "honorable_kills": 2,
            "equipment": [{"item_id": 5, "name": "Helm", "transmog": ""}]}},
        "html_summary": {"status": "ok", "data": {"equipment": {"slots": [
            {"is_empty": False, "item_reference": {"href_item_id": "5", "quality_name": "epic"},
             "layout_inference": {"inferred_slot_name": "Head"},
             "client": {"enchant": {"text": "+1 Stam"}, "gems": [{"position": 1, "id": 9, "text": "+2 Int"}, {"position": 2, "id": 0, "empty": True}]}},
            {"is_empty": True}]}}},
        "talents": {"status": "ok", "data": {
            "specs": [{"source_spec_id": "0", "label": "Holy", "trees": [{"name": "Discipline", "reported_total": 1}, {"name": "Holy", "reported_total": 70}]}],
            "glyphs": {"0": {"entries": [{"category": "major", "name": "Glyph of X", "client": {"description": "Does X"}}]}}}},
    },
}


class ReportTests(unittest.TestCase):
    def test_build_report_merges_sections(self):
        r = build_report(SNAP)
        self.assertEqual(len(r["equipment"]), 1)
        e = r["equipment"][0]
        self.assertEqual((e["slot"], e["name"], e["enchant"], e["gems"]), ("Head", "Helm", "+1 Stam", ["+2 Int"]))
        self.assertEqual(r["specializations"][0]["split"], [1, 70])
        self.assertEqual(r["specializations"][0]["glyphs"][0]["effect"], "Does X")

    def test_markdown_contains_key_facts(self):
        md = render_markdown(build_report(SNAP))
        for needle in ("# X - Onyxia", "| Head | Helm (5, epic) | +1 Stam | +2 Int |", "### Holy (1/70)", "Glyph of X"):
            self.assertIn(needle, md)

    def test_missing_sections_do_not_crash(self):
        r = build_report({"schema": "s", "sections": {}})
        self.assertEqual(r["equipment"], [])
        render_markdown(r)


if __name__ == "__main__":
    unittest.main()
