import unittest

from warmane_exporter.checks import run_checks


def item(slot, kind="chest", **kw):
    base = {"slot": slot, "name": f"Item {slot}", "item_id": 1, "inventory_type": kind, "enchant_id": 99, "enchant": "x",
            "sockets_empty": 0, "gem_details": [], "gem_states": [], "sockets": [], "buckle": False,
            "item_class": 4, "item_subclass": 4}
    base.update(kw)
    return base


def report(equipment, cls="Warrior", level=80, professions=(), specs=None):
    if specs is None:
        specs = [{"label": "Spec 1", "split": [50, 21, 0], "glyphs": [{"category": "major"}] * 3 + [{"category": "minor"}] * 3}]
    return {"identity": {"class": cls, "level": level}, "equipment": equipment,
            "professions": [{"name": p} for p in professions], "specializations": specs}


def texts(result, level):
    return [f["area"] + ": " + f["text"] for f in result[level]]


class GearChecks(unittest.TestCase):
    def test_clean_character_has_no_findings(self):
        r = run_checks(report([item("Head", "head"), item("Waist", "waist", sockets=["Blue"], buckle=True)]))
        self.assertEqual((r["issues"], r["warnings"]), ([], []))

    def test_missing_enchant_and_exempt_slots(self):
        eq = [item("Head", "head", enchant_id=None, enchant=None), item("Neck", "neck", enchant_id=None, enchant=None),
              item("Trinket 1", "trinket", enchant_id=None, enchant=None)]
        r = run_checks(report(eq))
        self.assertEqual(len(r["issues"]), 1)
        self.assertIn("No enchant", r["issues"][0]["text"])

    def test_rings_only_for_enchanters(self):
        ring = [item("Finger 1", "finger", enchant_id=None, enchant=None)]
        self.assertEqual(run_checks(report(ring))["issues"], [])
        self.assertEqual(len(run_checks(report(ring, professions=["Enchanting"]))["issues"]), 1)

    def test_hunter_needs_ranged_not_melee_weapon_enchant(self):
        eq = [item("Main Hand", "two-hand", enchant_id=None, enchant=None),
              item("Ranged", "ranged", enchant_id=None, enchant=None)]
        self.assertEqual(len(run_checks(report(eq, cls="Hunter"))["issues"]), 1)
        wand = [item("Ranged", "ranged", enchant_id=None, enchant=None)]
        self.assertEqual(run_checks(report(wand, cls="Mage"))["issues"], [])

    def test_empty_socket_inactive_meta_and_buckle(self):
        eq = [item("Chest", sockets_empty=2),
              item("Head", "head", gem_details=[{"text": "meta"}], gem_states=["inactive"]),
              item("Waist", "waist", sockets=["Red"], buckle=False)]
        found = texts(run_checks(report(eq)), "issues")
        self.assertEqual(len(found), 3)
        self.assertTrue(any("2 empty gem" in f for f in found))
        self.assertTrue(any("Meta gem is not active" in f for f in found))
        self.assertTrue(any("Eternal Belt Buckle missing" in f for f in found))

    def test_belt_without_socket_data_is_not_judged(self):
        self.assertEqual(run_checks(report([item("Waist", "waist", sockets=None)]))["issues"], [])

    def test_armor_type_is_only_a_warning(self):
        eq = [item("Chest", item_subclass=2), item("Back", "back", item_subclass=1), item("Head", "head", item_subclass=4)]
        r = run_checks(report(eq))
        self.assertEqual(r["issues"], [])
        self.assertEqual(len(r["warnings"]), 1)
        self.assertIn("Leather armor; a Warrior can wear plate", r["warnings"][0]["text"])


class SpecChecks(unittest.TestCase):
    def test_unspent_points_and_missing_major_glyph(self):
        spec = {"label": "Spec 1", "split": [50, 20, 0], "glyphs": [{"category": "major"}] * 2}
        r = run_checks(report([], specs=[spec]))
        self.assertEqual(len(r["issues"]), 2)

    def test_empty_second_spec_is_a_warning_not_issues(self):
        spec2 = {"label": "Spec 2", "split": [0, 0, 0], "glyphs": []}
        r = run_checks(report([], specs=[report([])["specializations"][0], spec2]))
        self.assertEqual(r["issues"], [])
        self.assertEqual(len(r["warnings"]), 1)
        self.assertIn("dual specialization", r["warnings"][0]["text"])

    def test_both_specs_checked_the_same(self):
        bad = {"label": "Spec 2", "split": [30, 10, 0], "glyphs": [{"category": "major"}]}
        self.assertEqual(len(run_checks(report([], specs=[bad]))["issues"]), 2)
