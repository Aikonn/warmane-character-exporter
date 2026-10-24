import unittest
from types import SimpleNamespace

from warmane_exporter.offline_enrichment import SLOT_INVENTORY_TYPES, _verify_layout_by_item_types
from warmane_exporter.summary_parser import STANDARD_WOTLK_LAYOUT

COUNTS = {"left": 8, "right": 8, "bottom": 3, "unknown": 0}


def equipment(swap=False):
    slots, items = [], {}
    n = 100
    for group, names in STANDARD_WOTLK_LAYOUT.items():
        for i, name in enumerate(names, 1):
            n += 1
            items[n] = min(SLOT_INVENTORY_TYPES[name])
            slots.append({"slot_key": f"{group}_{i}", "evidence": {"group": group, "index_in_group": i},
                          "item_reference": {"href_item_id": str(n), "namespaces": {}}})
    if swap:
        items[101] = 2   # a neck item where the head item should be
    return {"slots": slots, "layout_validation": {"status": "unverified", "anchors_checked": [],
            "observed_counts": COUNTS, "expected_counts": COUNTS, "issues": ["No slots with explicit labels found"]}}, items


class Defs:
    def __init__(self, items):
        self.items = items

    def item(self, item_id):
        return SimpleNamespace(inventory_type=self.items[item_id])


class LayoutByTypesTests(unittest.TestCase):
    def test_names_slots_when_all_item_types_fit(self):
        eq, items = equipment()
        _verify_layout_by_item_types(eq, Defs(items))
        self.assertEqual(eq["layout_validation"]["status"], "item_types_consistent")
        self.assertEqual(eq["slots"][0]["layout_inference"]["inferred_slot_name"], "Head")
        self.assertEqual(eq["slots"][-1]["layout_inference"]["inferred_slot_name"], "Ranged")

    def test_stays_unverified_when_a_type_does_not_fit(self):
        eq, items = equipment(swap=True)
        _verify_layout_by_item_types(eq, Defs(items))
        self.assertEqual(eq["layout_validation"]["status"], "unverified")
        self.assertNotIn("layout_inference", eq["slots"][0])
