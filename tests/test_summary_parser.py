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


class LayoutInferenceTests(unittest.TestCase):
    """Tests for equipment slot layout inference against standard WotLK paperdoll order."""

    def test_consistent_layout_with_anchors_infers_all_slots(self) -> None:
        """Standard 8/8/3 layout with Shirt/Tabard anchors should infer all 19 slots."""
        html = Path("tests/fixtures/synthetic/layout-consistent-with-anchors.html").read_text(encoding="utf-8")
        result = parse_summary_capture_html(html, source_name="synthetic-layout-consistent")
        
        validation = result["equipment"]["layout_validation"]
        self.assertEqual(validation["status"], "anchors_consistent")
        self.assertEqual(validation["observed_counts"], {"left": 8, "right": 8, "bottom": 3, "unknown": 0})
        self.assertEqual(len(validation["anchors_checked"]), 2)
        self.assertTrue(all(a["match"] for a in validation["anchors_checked"]))
        
        # All slots should have inferred names
        for slot in result["equipment"]["slots"]:
            self.assertIsNotNone(slot["layout_inference"]["inferred_slot_name"])
            self.assertEqual(slot["layout_inference"]["status"], "anchors_consistent")
        
        # Verify specific inferred names
        left_slots = [s for s in result["equipment"]["slots"] if s["evidence"]["group"] == "left"]
        self.assertEqual(left_slots[0]["layout_inference"]["inferred_slot_name"], "Head")
        self.assertEqual(left_slots[5]["layout_inference"]["inferred_slot_name"], "Shirt")
        self.assertEqual(left_slots[6]["layout_inference"]["inferred_slot_name"], "Tabard")

    def test_count_mismatch_leaves_all_slots_unverified(self) -> None:
        """Count mismatch (7 left instead of 8) should leave all slots unverified with null inferred names."""
        html = Path("tests/fixtures/synthetic/layout-count-mismatch.html").read_text(encoding="utf-8")
        result = parse_summary_capture_html(html, source_name="synthetic-layout-mismatch")
        
        validation = result["equipment"]["layout_validation"]
        self.assertEqual(validation["status"], "unverified")
        self.assertEqual(validation["observed_counts"]["left"], 7)
        self.assertIsNotNone(validation["issues"])
        self.assertTrue(any("count mismatch" in str(i) for i in validation["issues"]))
        
        # All slots should have null inferred names when unverified
        for slot in result["equipment"]["slots"]:
            self.assertIsNone(slot["layout_inference"]["inferred_slot_name"])
            self.assertEqual(slot["layout_inference"]["status"], "unverified")

    def test_hyphenated_off_hand_label_matches_layout(self) -> None:
        """Warmane labels the empty off-hand slot 'Off-Hand'; it must match 'Off Hand'."""
        from warmane_exporter.summary_parser import _labels_match

        self.assertTrue(_labels_match("Off-Hand", "Off Hand"))
        self.assertTrue(_labels_match("off hand", "Off Hand"))
        self.assertFalse(_labels_match("Main Hand", "Off Hand"))
        self.assertFalse(_labels_match(None, "Off Hand"))

    def test_anchor_mismatch_marks_unverified_with_issue(self) -> None:
        """Anchor mismatch (Shirt at left_5 instead of left_6) should mark unverified with issue."""
        html = Path("tests/fixtures/synthetic/layout-anchor-mismatch.html").read_text(encoding="utf-8")
        result = parse_summary_capture_html(html, source_name="synthetic-layout-anchor-mismatch")
        
        validation = result["equipment"]["layout_validation"]
        self.assertEqual(validation["status"], "unverified")
        self.assertIsNotNone(validation["issues"])
        self.assertTrue(any("Shirt" in str(i) and "Chest" in str(i) for i in validation["issues"]))
        
        # All slots should be unverified
        for slot in result["equipment"]["slots"]:
            self.assertIsNone(slot["layout_inference"]["inferred_slot_name"])
            self.assertEqual(slot["layout_inference"]["status"], "unverified")

    def test_no_anchors_marks_unverified(self) -> None:
        """No explicit anchors should mark layout as unverified."""
        html = Path("tests/fixtures/synthetic/layout-no-anchors.html").read_text(encoding="utf-8")
        result = parse_summary_capture_html(html, source_name="synthetic-layout-no-anchors")
        
        validation = result["equipment"]["layout_validation"]
        self.assertEqual(validation["status"], "unverified")
        self.assertEqual(len(validation["anchors_checked"]), 0)
        self.assertIsNotNone(validation["issues"])
        self.assertTrue(any("No slots with explicit labels" in str(i) for i in validation["issues"]))
        
        # All slots should be unverified despite correct counts
        for slot in result["equipment"]["slots"]:
            self.assertIsNone(slot["layout_inference"]["inferred_slot_name"])

    def test_explicit_slot_names_never_overwritten(self) -> None:
        """Explicit slot_name from data-tooltip should never be overwritten by inference."""
        html = Path("tests/fixtures/synthetic/layout-consistent-with-anchors.html").read_text(encoding="utf-8")
        result = parse_summary_capture_html(html, source_name="synthetic-layout-test")
        
        empty_slots = [s for s in result["equipment"]["slots"] if s["is_empty"]]
        for slot in empty_slots:
            self.assertIsNotNone(slot["slot_name"])
            self.assertTrue(slot["is_empty"])
            # slot_name should remain the explicit value, not be overwritten
            self.assertIn(slot["slot_name"], ["Shirt", "Tabard"])
        
        # Also verify non-empty slots keep slot_name None while having inferred name
        non_empty_slots = [s for s in result["equipment"]["slots"] if "item_reference" in s]
        for slot in non_empty_slots:
            self.assertIsNone(slot["slot_name"], f"Non-empty slot {slot.get('slot_key')} should have slot_name=None")
            self.assertIsNotNone(slot["layout_inference"]["inferred_slot_name"], f"Slot {slot.get('slot_key')} should have inferred_slot_name")

    def test_out_of_range_anchor_marks_unverified_no_exception(self) -> None:
        """Anchor with out-of-range position (left_9 when max is 8) should be detected, recorded, and mark unverified without raising."""
        # SYNTHETIC FIXTURE: 9 left slots with explicit label at left_9
        html = """<!-- SYNTHETIC: 9 left slots, label at left_9 (out of range) -->
<html><body>
<div id="character-sheet"><div id="character-profile"><div class="information-left">
<div class="item-model">
<div class="item-left">
  <div class="item-slot"><div class="icon-quality"><a href="http://wotlk.cavernoftime.com/item=10001" rel="item=10001"></a></div></div>
  <div class="item-slot"><div class="icon-quality"><a href="http://wotlk.cavernoftime.com/item=10002" rel="item=10002"></a></div></div>
  <div class="item-slot"><div class="icon-quality"><a href="http://wotlk.cavernoftime.com/item=10003" rel="item=10003"></a></div></div>
  <div class="item-slot"><div class="icon-quality"><a href="http://wotlk.cavernoftime.com/item=10004" rel="item=10004"></a></div></div>
  <div class="item-slot"><div class="icon-quality"><a href="http://wotlk.cavernoftime.com/item=10005" rel="item=10005"></a></div></div>
  <div class="item-slot"><div class="icon-quality tooltip" data-tooltip="Shirt"><a href="#self"></a></div></div>
  <div class="item-slot"><div class="icon-quality tooltip" data-tooltip="Tabard"><a href="#self"></a></div></div>
  <div class="item-slot"><div class="icon-quality"><a href="http://wotlk.cavernoftime.com/item=10008" rel="item=10008"></a></div></div>
  <div class="item-slot"><div class="icon-quality tooltip" data-tooltip="Unreachable"><a href="#self"></a></div></div>
</div>
<div class="item-right">
  <div class="item-slot"><div class="icon-quality"><a href="http://wotlk.cavernoftime.com/item=20001" rel="item=20001"></a></div></div>
  <div class="item-slot"><div class="icon-quality"><a href="http://wotlk.cavernoftime.com/item=20002" rel="item=20002"></a></div></div>
  <div class="item-slot"><div class="icon-quality"><a href="http://wotlk.cavernoftime.com/item=20003" rel="item=20003"></a></div></div>
  <div class="item-slot"><div class="icon-quality"><a href="http://wotlk.cavernoftime.com/item=20004" rel="item=20004"></a></div></div>
  <div class="item-slot"><div class="icon-quality"><a href="http://wotlk.cavernoftime.com/item=20005" rel="item=20005"></a></div></div>
  <div class="item-slot"><div class="icon-quality"><a href="http://wotlk.cavernoftime.com/item=20006" rel="item=20006"></a></div></div>
  <div class="item-slot"><div class="icon-quality"><a href="http://wotlk.cavernoftime.com/item=20007" rel="item=20007"></a></div></div>
  <div class="item-slot"><div class="icon-quality"><a href="http://wotlk.cavernoftime.com/item=20008" rel="item=20008"></a></div></div>
</div>
<div class="item-bottom">
  <div class="item-slot"><div class="icon-quality"><a href="http://wotlk.cavernoftime.com/item=30001" rel="item=30001"></a></div></div>
  <div class="item-slot"><div class="icon-quality"><a href="http://wotlk.cavernoftime.com/item=30002" rel="item=30002"></a></div></div>
  <div class="item-slot"><div class="icon-quality"><a href="http://wotlk.cavernoftime.com/item=30003" rel="item=30003"></a></div></div>
</div>
</div><div class="model"><script>var charactermodel = {items: [[1,64160]]};</script></div>
</div></div></div>
</body></html>"""
        result = parse_summary_capture_html(html, source_name="synthetic-out-of-range")
        
        validation = result["equipment"]["layout_validation"]
        self.assertEqual(validation["status"], "unverified")
        self.assertEqual(validation["observed_counts"]["left"], 9)
        self.assertIsNotNone(validation["issues"])
        self.assertTrue(any("count mismatch" in str(i) for i in validation["issues"]))
        self.assertTrue(any("out-of-range" in str(i) for i in validation["issues"]))
        
        # All slots should be unverified, no exception raised
        for slot in result["equipment"]["slots"]:
            self.assertIsNone(slot["layout_inference"]["inferred_slot_name"])

    def test_unknown_group_slot_marks_unverified(self) -> None:
        """Slot markup before any item-left/right/bottom group should create unknown group count and mark unverified."""
        # SYNTHETIC FIXTURE: one slot in unknown group (before item-left), then 8/8/3 layout
        html = """<!-- SYNTHETIC: slot markup before item-left div -->
<html><body>
<div id="character-sheet"><div id="character-profile"><div class="information-left">
<div class="item-model">
  <div class="item-slot"><div class="icon-quality"><a href="http://wotlk.cavernoftime.com/item=99999" rel="item=99999"></a></div></div>
  <div class="item-left">
    <div class="item-slot"><div class="icon-quality"><a href="http://wotlk.cavernoftime.com/item=10001" rel="item=10001"></a></div></div>
    <div class="item-slot"><div class="icon-quality"><a href="http://wotlk.cavernoftime.com/item=10002" rel="item=10002"></a></div></div>
    <div class="item-slot"><div class="icon-quality"><a href="http://wotlk.cavernoftime.com/item=10003" rel="item=10003"></a></div></div>
    <div class="item-slot"><div class="icon-quality"><a href="http://wotlk.cavernoftime.com/item=10004" rel="item=10004"></a></div></div>
    <div class="item-slot"><div class="icon-quality"><a href="http://wotlk.cavernoftime.com/item=10005" rel="item=10005"></a></div></div>
    <div class="item-slot"><div class="icon-quality tooltip" data-tooltip="Shirt"><a href="#self"></a></div></div>
    <div class="item-slot"><div class="icon-quality tooltip" data-tooltip="Tabard"><a href="#self"></a></div></div>
    <div class="item-slot"><div class="icon-quality"><a href="http://wotlk.cavernoftime.com/item=10008" rel="item=10008"></a></div></div>
  </div>
  <div class="item-right">
    <div class="item-slot"><div class="icon-quality"><a href="http://wotlk.cavernoftime.com/item=20001" rel="item=20001"></a></div></div>
    <div class="item-slot"><div class="icon-quality"><a href="http://wotlk.cavernoftime.com/item=20002" rel="item=20002"></a></div></div>
    <div class="item-slot"><div class="icon-quality"><a href="http://wotlk.cavernoftime.com/item=20003" rel="item=20003"></a></div></div>
    <div class="item-slot"><div class="icon-quality"><a href="http://wotlk.cavernoftime.com/item=20004" rel="item=20004"></a></div></div>
    <div class="item-slot"><div class="icon-quality"><a href="http://wotlk.cavernoftime.com/item=20005" rel="item=20005"></a></div></div>
    <div class="item-slot"><div class="icon-quality"><a href="http://wotlk.cavernoftime.com/item=20006" rel="item=20006"></a></div></div>
    <div class="item-slot"><div class="icon-quality"><a href="http://wotlk.cavernoftime.com/item=20007" rel="item=20007"></a></div></div>
    <div class="item-slot"><div class="icon-quality"><a href="http://wotlk.cavernoftime.com/item=20008" rel="item=20008"></a></div></div>
  </div>
  <div class="item-bottom">
    <div class="item-slot"><div class="icon-quality"><a href="http://wotlk.cavernoftime.com/item=30001" rel="item=30001"></a></div></div>
    <div class="item-slot"><div class="icon-quality"><a href="http://wotlk.cavernoftime.com/item=30002" rel="item=30002"></a></div></div>
    <div class="item-slot"><div class="icon-quality"><a href="http://wotlk.cavernoftime.com/item=30003" rel="item=30003"></a></div></div>
  </div>
</div>
<div class="model"><script>var charactermodel = {items: [[1,64160]]};</script></div>
</div></div></div>
</body></html>"""
        result = parse_summary_capture_html(html, source_name="synthetic-unknown-group")
        
        validation = result["equipment"]["layout_validation"]
        self.assertEqual(validation["status"], "unverified")
        self.assertEqual(validation["observed_counts"]["unknown"], 1)
        self.assertIsNotNone(validation["issues"])
        self.assertTrue(any("unknown group" in str(i) for i in validation["issues"]))
        
        # All slots should be unverified
        for slot in result["equipment"]["slots"]:
            self.assertIsNone(slot["layout_inference"]["inferred_slot_name"])

    def test_finger_and_trinket_slots_have_order_note(self) -> None:
        """Finger and Trinket slots should include a note about layout order numbering."""
        html = Path("tests/fixtures/synthetic/layout-consistent-with-anchors.html").read_text(encoding="utf-8")
        result = parse_summary_capture_html(html, source_name="synthetic-layout-test")
        
        right_slots = [s for s in result["equipment"]["slots"] if s["evidence"]["group"] == "right"]
        finger_slots = [s for s in right_slots if "Finger" in s["layout_inference"].get("inferred_slot_name", "")]
        trinket_slots = [s for s in right_slots if "Trinket" in s["layout_inference"].get("inferred_slot_name", "")]
        
        for slot in finger_slots + trinket_slots:
            self.assertIn("note", slot["layout_inference"])
            self.assertIn("layout order only", slot["layout_inference"]["note"])

    def test_icon_stem_captured_from_img_src(self) -> None:
        """Icon stem should be captured from item <img src> attribute."""
        html = Path("tests/fixtures/synthetic/layout-consistent-with-anchors.html").read_text(encoding="utf-8")
        result = parse_summary_capture_html(html, source_name="synthetic-layout-test")
        
        items_with_refs = [s for s in result["equipment"]["slots"] if "item_reference" in s]
        self.assertGreater(len(items_with_refs), 0)
        
        # Find Head slot (left_1) and verify its icon stem is captured
        head_slot = next((s for s in items_with_refs if s.get("slot_key") == "left_1"), None)
        self.assertIsNotNone(head_slot)
        self.assertEqual(head_slot["item_reference"]["icon_stem"], "inv_helmet_156")

    def test_missing_img_src_yields_null_icon_stem(self) -> None:
        """Missing or malformed <img> should result in null icon_stem, not error."""
        html = Path("tests/fixtures/synthetic/layout-no-img.html").read_text(encoding="utf-8")
        result = parse_summary_capture_html(html, source_name="synthetic-layout-no-img")
        
        items_with_refs = [s for s in result["equipment"]["slots"] if "item_reference" in s]
        self.assertGreater(len(items_with_refs), 0)
        
        # Should have at least one null icon_stem and at least one non-empty icon_stem
        icon_stems = [s["item_reference"].get("icon_stem") for s in items_with_refs]
        self.assertTrue(any(stem is None for stem in icon_stems), "Expected at least one null icon_stem")
        self.assertTrue(any(stem is not None and len(stem) > 0 for stem in icon_stems), "Expected at least one non-empty icon_stem")


if __name__ == "__main__":
    unittest.main()

