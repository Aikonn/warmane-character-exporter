from pathlib import Path
import unittest

from warmane_exporter.summary_parser import parse_summary_capture_html


class SummaryParserTests(unittest.TestCase):
    def test_parses_summary_capture_structure(self) -> None:
        html = Path("tests/fixtures/synthetic/summary-page-dom-synthetic.html").read_text(encoding="utf-8")
        result = parse_summary_capture_html(html, source_name="synthetic-summary")

        self.assertEqual(result["parser_mode"], "offline_rendered_dom_text_only")
        self.assertEqual(result["identity"]["name"], "Demo")
        self.assertEqual(result["identity"]["guild"], "Test Guild")
        self.assertIn("Level 80", result["identity"]["level_race_class_realm_display"])

        not_captured = result["navigation"]["not_captured_sections"]
        labels = [item["label"] for item in not_captured]
        self.assertIn("ACHIEVEMENTS", labels)
        self.assertIn("TALENTS", labels)
        self.assertIn("STATISTICS", labels)

        equipment_slots = result["equipment"]["slots"]
        self.assertGreaterEqual(len(equipment_slots), 3)
        first = equipment_slots[0]
        self.assertEqual(first["item_reference"]["namespaces"]["item"], "11111")
        self.assertEqual(first["item_reference"]["namespaces"]["ench"], "3820")
        self.assertEqual(first["item_reference"]["namespaces"]["gems"], "3627:3879:0")
        self.assertEqual(
            [entry["raw_value"] for entry in first["item_reference"]["namespaces"]["gem_positions"]],
            ["3627", "3879", "0"],
        )

        empty_slots = [slot for slot in equipment_slots if slot["is_empty"]]
        self.assertEqual({slot["slot_name"] for slot in empty_slots}, {"Shirt", "Tabard"})

        specs = result["specializations"]["specs"]
        self.assertEqual(len(specs), 2)
        self.assertEqual(specs[0]["name"], "Discipline")
        self.assertEqual(specs[0]["tree_points"], [57, 14, 0])
        self.assertEqual(specs[1]["name"], "Holy")
        self.assertEqual(specs[1]["tree_points"], [18, 53, 0])
        self.assertEqual(result["specializations"]["active_spec_status"], "unknown_not_explicit_in_capture")

        self.assertEqual(result["glyphs"]["status"], "not_present_in_this_capture")

        recent = result["recent_achievements"]
        self.assertTrue(recent["partial_list_from_summary_capture"])
        self.assertEqual(recent["items"][0]["achievement_id"], "4610")

        viewer_items = result["model_viewer_item_ids"]["items"]
        self.assertEqual(viewer_items[0]["viewer_slot_id"], 1)
        self.assertEqual(viewer_items[0]["viewer_model_item_id"], 64160)

    def test_stats_preserve_display_values_and_units(self) -> None:
        html = Path("tests/fixtures/synthetic/summary-page-dom-synthetic.html").read_text(encoding="utf-8")
        result = parse_summary_capture_html(html, source_name="synthetic-summary")
        panels = result["character_stats"]
        melee_panel = next(panel for panel in panels if panel["panel"] == "Melee")
        crit_entry = next(entry for entry in melee_panel["entries"] if entry["label"] == "Critical")
        self.assertEqual(crit_entry["displayed_value"], "16.46%")
        self.assertEqual(crit_entry["unit"], "%")

        damage_entry = next(entry for entry in melee_panel["entries"] if entry["label"] == "Damage")
        self.assertEqual(damage_entry["displayed_value"], "103 - 316")
        self.assertIsNone(damage_entry["unit"])


if __name__ == "__main__":
    unittest.main()
