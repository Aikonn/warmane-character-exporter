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
        self.assertEqual(r["issues"][0]["slot"], "Head")

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
        result = run_checks(report(eq))
        found = texts(result, "issues")
        self.assertEqual(len(found), 3)
        self.assertTrue(any("2 empty gem" in f for f in found))
        self.assertTrue(any("Meta gem is not active" in f for f in found))
        self.assertTrue(any("Eternal Belt Buckle missing" in f for f in found))
        self.assertEqual({finding["slot"] for finding in result["issues"]}, {"Chest", "Head", "Waist"})

    def test_belt_without_socket_data_is_not_judged(self):
        self.assertEqual(run_checks(report([item("Waist", "waist", sockets=None)]))["issues"], [])

    def test_armor_type_is_only_a_warning(self):
        eq = [item("Chest", item_subclass=2), item("Back", "back", item_subclass=1), item("Head", "head", item_subclass=4)]
        r = run_checks(report(eq))
        self.assertEqual(r["issues"], [])
        self.assertEqual(len(r["warnings"]), 1)
        self.assertIn("Leather armor; a Warrior can wear plate", r["warnings"][0]["text"])
        self.assertEqual(r["warnings"][0]["slot"], "Chest")

    def test_common_quality_gems_are_one_issue_per_item(self):
        gems = [
            {"id": 1, "quality": "common", "color": "red", "text": "Weak Ruby"},
            {"id": 2, "quality": "poor", "color": "blue", "text": "Rough Sapphire"},
            {"id": 3, "quality": "poor", "color": "yellow"},
        ]
        result = run_checks(report([item("Head", gem_details=gems)]))

        self.assertEqual(len(result["issues"]), 1)
        finding = result["issues"][0]
        self.assertEqual((finding["kind"], finding["count"], finding["slot"]), ("gem_common", 3, "Head"))
        self.assertEqual(finding["text"], "3 common-quality gem(s): Weak Ruby; Rough Sapphire; gem.")

    def test_uncommon_gem_in_icc_gear_is_a_warning(self):
        gem = {"id": 1, "quality": "uncommon", "color": "red", "text": "Uncommon Ruby"}
        result = run_checks(report([item("Head", item_level=251, gem_details=[gem])]))

        self.assertEqual(result["issues"], [])
        self.assertEqual(len(result["warnings"]), 1)
        finding = result["warnings"][0]
        self.assertEqual((finding["kind"], finding["count"]), ("gem_uncommon", 1))
        self.assertEqual(
            finding["text"],
            "1 uncommon-quality gem(s) in item level 251 gear: Uncommon Ruby.",
        )

    def test_uncommon_gem_below_icc_level_has_no_finding(self):
        gem = {"id": 1, "quality": "uncommon", "color": "red", "text": "Uncommon Ruby"}
        for item_level in (245, None):
            with self.subTest(item_level=item_level):
                result = run_checks(report([item("Head", item_level=item_level, gem_details=[gem])]))
                self.assertEqual((result["issues"], result["warnings"]), ([], []))

    def test_uncommon_meta_gem_and_unknown_quality_have_no_finding(self):
        gems = [
            {"id": 1, "quality": "uncommon", "color": "meta", "text": "Uncommon Meta"},
            {"id": 2, "quality": None, "color": "red", "text": "Unknown Quality"},
            {"id": 0, "empty": True, "quality": "common", "color": "red", "text": "Empty socket"},
        ]
        result = run_checks(report([item("Head", item_level=264, gem_details=gems)]))
        self.assertEqual((result["issues"], result["warnings"]), ([], []))


class SpecChecks(unittest.TestCase):
    def test_unspent_points_and_missing_major_glyph(self):
        spec = {"label": "Spec 1", "split": [50, 20, 0], "glyphs": [{"category": "major"}] * 2}
        r = run_checks(report([], specs=[spec]))
        self.assertEqual(len(r["issues"]), 2)
        self.assertNotIn("slot", r["issues"][0])

    def test_empty_second_spec_is_a_warning_not_issues(self):
        spec2 = {"label": "Spec 2", "split": [0, 0, 0], "glyphs": []}
        r = run_checks(report([], specs=[report([])["specializations"][0], spec2]))
        self.assertEqual(r["issues"], [])
        self.assertEqual(len(r["warnings"]), 1)
        self.assertIn("dual specialization", r["warnings"][0]["text"])

    def test_both_specs_checked_the_same(self):
        bad = {"label": "Spec 2", "split": [30, 10, 0], "glyphs": [{"category": "major"}]}
        self.assertEqual(len(run_checks(report([], specs=[bad]))["issues"]), 2)

    def test_missing_glyphs_are_warnings_when_another_spec_is_fully_glyphed(self):
        complete = {"label": "Spec 1", "split": [50, 21, 0], "glyphs": [{"category": "major"}] * 3}
        incomplete = {"label": "Spec 2", "split": [50, 21, 0], "glyphs": [{"category": "major"}] * 2}

        result = run_checks(report([], specs=[complete, incomplete]))

        self.assertEqual(result["issues"], [])
        self.assertEqual(
            [(finding["kind"], finding["count"], finding["spec_index"], finding["text"])
             for finding in result["warnings"]],
            [("glyphs", 1, 1, "1 major glyph slot(s) empty (2 of 3 filled); another specialization has all 3.")],
        )

    def test_missing_glyphs_are_issues_when_no_spec_is_fully_glyphed(self):
        specs = [
            {"label": "Spec 1", "split": [50, 21, 0], "glyphs": [{"category": "major"}] * 2},
            {"label": "Spec 2", "split": [50, 21, 0], "glyphs": [{"category": "major"}] * 2},
        ]

        result = run_checks(report([], specs=specs))

        self.assertEqual(result["warnings"], [])
        self.assertEqual(
            [(finding["level"], finding["kind"], finding["count"], finding["spec_index"], finding["text"])
             for finding in result["issues"]],
            [
                ("issue", "glyphs", 1, 0, "1 major glyph slot(s) empty (2 of 3 filled)."),
                ("issue", "glyphs", 1, 1, "1 major glyph slot(s) empty (2 of 3 filled)."),
            ],
        )

    def test_spec_without_talents_only_gets_no_talents_warning(self):
        empty = {"label": "Spec 1", "split": [0, 0, 0], "glyphs": [{"category": "major"}] * 2}
        result = run_checks(report([], specs=[empty]))

        self.assertEqual(result["issues"], [])
        self.assertEqual([finding["kind"] for finding in result["warnings"]], ["no_talents"])

    def test_findings_include_kinds_counts_and_spec_indices(self):
        specs = [
            {"label": "Spec 1", "split": [50, 19, 0], "glyphs": [{"category": "major"}] * 2},
            {"label": "Spec 2", "split": [50, 20, 0], "glyphs": [{"category": "major"}]},
            {"label": "Spec 3", "split": [0, 0, 0], "glyphs": []},
        ]
        equipment = [
            item(
                "Head", "head", enchant_id=None, enchant=None, sockets_empty=2,
                gem_details=[{"text": "Meta"}], gem_states=["inactive"],
            ),
            item("Finger 1", "finger", enchant_id=None, enchant=None),
            item("Waist", "waist", sockets=["Blue"], buckle=False),
            item("Chest", item_subclass=2),
        ]

        result = run_checks(report(
            equipment, professions=["Enchanting"], specs=specs,
        ))
        all_findings = result["issues"] + result["warnings"]
        self.assertTrue(all("kind" in finding for finding in all_findings))
        by_kind = {finding["kind"]: finding for finding in all_findings}
        self.assertEqual(by_kind["enchant"]["slot"], "Head")
        self.assertEqual(by_kind["ring_enchant"]["slot"], "Finger 1")
        self.assertEqual((by_kind["sockets"]["count"], by_kind["sockets"]["slot"]), (2, "Head"))
        self.assertEqual(by_kind["meta"]["slot"], "Head")
        self.assertEqual(by_kind["buckle"]["slot"], "Waist")
        self.assertEqual(by_kind["armor"]["level"], "warning")
        self.assertEqual(
            [(finding["count"], finding["spec_index"]) for finding in result["issues"]
             if finding["kind"] == "talents"],
            [(2, 0), (1, 1)],
        )
        self.assertEqual(
            [(finding["count"], finding["spec_index"]) for finding in result["issues"]
             if finding["kind"] == "glyphs"],
            [(1, 0), (2, 1)],
        )
        self.assertEqual(by_kind["no_talents"]["spec_index"], 2)
