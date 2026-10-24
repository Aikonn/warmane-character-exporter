import unittest

from warmane_exporter.pve_report import build_pve_report, build_progression, parse_progress_row, render_html


def _stats():
    rows = lambda *pairs: [{"name": n, "value": v} for n, v in pairs]
    return [
        {"category_id": 15062, "category": "Fall of the Lich King", "parent": 14807, "rows": rows(
            ("Sindragosa kills (Icecrown 10 player)", "1"), ("Sindragosa kills (Heroic Icecrown 10 player)", "- -"),
            ("Sindragosa kills (Icecrown 25 player)", "2"), ("Sindragosa kills (Heroic Icecrown 25 player)", "- -"),
            ("Victories over the Lich King (Icecrown 25 player)", "1"),
            ("Toravon the Ice Watcher kills (Wintergrasp 10 player)", "- -"), ("Falric kills (Halls of Reflection)", "1"), ("Falric kills (Heroic Halls of Reflection)", "3"),
            ("Weird row without context", "5"), ("Broken kills (Icecrown 10 player)", "n/a"))},
        {"category_id": 14823, "category": "Wrath", "parent": 14807, "rows": rows(
            ("Keristrasza kills (The Nexus)", "14"), ("Keristrasza kills (Heroic Nexus)", "7"),
            ("Malygos kills (10 player)", "14"), ("Sartharion kills (Chamber of the Aspects 25 player)", "12"),
            ("Archavon the Stone Watcher kills (Wintergrasp 10 player)", "4"),
            ("Mal'Ganis defeated (Caverns of Time: Stratholme)", "9"), ("Mal'Ganis defeated (Heroic CoT: Stratholme)", "- -"))},
        {"category_id": 15021, "category": "Call", "parent": 14807, "rows": rows(
            ("Lord Jaraxxus kills (Trial of the Crusader 10 player)", "14"),
            ("Lord Jaraxxus kills (Trial of the Grand Crusader 10 player)", "13"),
            ("Times completed the Trial of the Grand Crusader (25 player)", "12"))},
        {"category_id": 14807, "category": "Dungeons & Raids", "parent": None, "rows": rows(("Total 5-player dungeons entered", "84"))},
        {"category_id": 125, "category": "Dungeons", "parent": 122, "rows": rows(("Deaths in Ulduar", "154"), ("Most deadly boss", "- -"))},
        {"category_id": 130, "category": "Character", "parent": None, "rows": rows(("Emblems of Frost acquired", "311"), ("Gold", "5"))},
    ]


class ParseTests(unittest.TestCase):
    def test_row_parsing(self):
        p = parse_progress_row("Sindragosa kills (Heroic Icecrown 25 player)")
        self.assertEqual((p["boss"], p["instance"], p["size"], p["heroic"]), ("Sindragosa", "Icecrown", 25, True))
        self.assertEqual(parse_progress_row("Malygos kills (10 player)")["instance"], "The Eye of Eternity")
        self.assertIsNone(parse_progress_row("Weird row without context"))
        self.assertIsNone(parse_progress_row("Unknown boss kills (10 player)"))
        grand = parse_progress_row("Lord Jaraxxus kills (Trial of the Grand Crusader 10 player)")
        self.assertEqual((grand["instance"], grand["heroic"]), ("Trial of the Crusader", True))

    def test_progression_groups_normal_and_heroic_names(self):
        prog = build_progression(_stats())
        groups = {g["heading"]: g for g in prog["groups"]}
        wrath = {i["name"]: i for i in groups["Wrath of the Lich King"]["instances"]}
        self.assertIn("The Nexus", wrath)
        self.assertEqual(wrath["The Nexus"]["bosses"]["Keristrasza"], {(None, False): 14, (None, True): 7})
        self.assertEqual(len(wrath["Caverns of Time: Stratholme"]["modes"]), 2)
        self.assertIn("Obsidian Sanctum (Chamber of the Aspects)", wrath)
        voa = wrath["Vault of Archavon (Wintergrasp)"]
        self.assertEqual(set(voa["bosses"]), {"Archavon the Stone Watcher", "Toravon the Ice Watcher"})
        self.assertNotIn("Vault of Archavon (Wintergrasp)", {i["name"] for i in groups["Fall of the Lich King"]["instances"]})
        icc = groups["Fall of the Lich King"]
        self.assertEqual([r["name"] for r in icc["other"]], ["Weird row without context", "Broken kills (Icecrown 10 player)"])
        icc_inst = {i["name"]: i for i in icc["instances"]}["Icecrown"]
        self.assertEqual(icc_inst["bosses"]["Sindragosa"][(10, True)], 0)
        self.assertEqual(icc_inst["bosses"]["Lich King"][(25, False)], 1)
        toc = {i["name"]: i for i in groups["Call of the Crusade"]["instances"]}["Trial of the Crusader"]
        self.assertEqual(toc["bosses"]["Times completed"][(25, True)], 12)
        self.assertEqual(prog["deaths"], [{"name": "Deaths in Ulduar", "value": "154"}])


class HtmlTests(unittest.TestCase):
    def setUp(self):
        self.report = {
            "identity": {"name": "A<b>", "realm": "Onyxia", "level": 80, "race": "Blood Elf", "class": "Priest", "faction": "Horde",
                         "guild": None, "achievement_points": 10},
            "snapshot_time": 1792846391, "active_specialization": "unknown (not exposed by Warmane)",
            "bonus_totals": {"Stamina": 5, "Spell Power": 30},
            "equipment": [
                {"slot": "Head", "item_id": 1, "name": "Hood", "quality": "epic", "item_level": 264, "stats": [["stamina", 5]],
                 "enchant": "+30 Spell Power", "gems": ["+10 All Stats"], "sockets_empty": 1, "transmog": "", "inventory_type": "head",
                 "sockets": ["meta", "blue"], "gem_lines": ["+10 All Stats (epic blue)", "<no gem>"], "buckle": False, "effects": [], "socket_bonus_info": {"text": "+9 Stamina", "active": False}},
                {"slot": "Waist", "item_id": 3, "name": "Belt", "quality": "epic", "item_level": 245, "stats": [], "enchant": None,
                 "gems": [], "inventory_type": "waist", "sockets": ["yellow"], "gem_lines": ["+12 Spell Power (epic yellow)", "+12 Spell Power (epic red)"],
                 "buckle": True, "gem_states": [], "effects": [{"trigger": "Equip", "spell": 9, "text": "Your spell casts have a chance to grant 304 mana per 5 sec for 15 sec."}]},
                {"slot": "Shirt", "item_id": 2, "name": "Shirt", "quality": "common", "item_level": 1, "stats": [], "gems": []}],
            "specializations": [{"label": "Discipline", "split": [57, 14, 0], "glyphs": [], "talent_detail": [
                {"tree": "Discipline", "points": 57, "talents": [{"name": "Penance", "spent": 1, "max": 1, "description": "Heals"}]}]}],
            "professions": [{"name": "Tailoring", "skill": 427, "maximum": 450}],
            "statistics": _stats(),
            "achievements": {"entries": [
                {"id": 1, "title": "Ulduar <10>", "points": 10, "earned": True, "earned_date": "2026-01-01", "category_id": 14961,
                 "category": "Secrets of Ulduar 10", "parent_category_id": 168, "description": ""},
                {"id": 2, "title": "Not yet", "points": 25, "earned": False, "earned_date": None, "category_id": 14961,
                 "category": "Secrets of Ulduar 10", "parent_category_id": 168, "description": "Do the thing"},
                {"id": 3, "title": "Other", "points": 5, "earned": True, "earned_date": "2025-01-01", "category_id": 92,
                 "category": "General", "parent_category_id": None, "description": ""}]},
            "reputation": [{"faction": "Argent Crusade", "standing": "Exalted", "current": 999, "maximum": 999}],
            "mounts": [{"name": "Wind Rider", "item_id": 1, "npc_id": 2}], "missing_sections": [],
        }

    def test_content_and_escaping(self):
        pve = build_pve_report(self.report)
        self.assertEqual((pve["gearscore"]["average_item_level"], pve["gearscore"]["items"]), (254, 2))
        self.assertEqual([r["name"] for r in pve["currencies"]], ["Emblems of Frost acquired"])
        self.assertEqual(len(pve["achievement_groups"]), 1)
        html = render_html(pve)
        for needle in ("<!doctype html>", "A&lt;b&gt;", "Ulduar &lt;10&gt;", "&lt;no gem&gt;", "+12 Spell Power (epic yellow)", "Eternal Belt Buckle", "Equip: Your spell casts have a chance to grant 304 mana per 5 sec for 15 sec.", "Base stats and special effects", "Socket bonus (inactive): +9 Stamina", "Total base stat bonuses", "<td>Spell Power</td><td>+30</td>", "https://wotlk.cavernoftime.com/item=1", "GearScore", "Penance", "Do the thing",
                       "Sindragosa", "heroic", "Warning: some armory kill counts", "Argent Crusade", "Wind Rider", "2026-"):
            self.assertIn(needle, html)
        self.assertNotIn("Ulduar <10>", html)  # raw armory text is never injected
        self.assertNotIn("<h1>A<b>", html)
        self.assertNotIn("<script", html)
        self.assertEqual(html.count("http"), 3)   # only the item links; no scripts, styles or images are loaded from the web

    def test_minimal_report_does_not_crash(self):
        html = render_html(build_pve_report({"identity": {"name": "X", "realm": "Icecrown"}, "missing_sections": ["statistics"]}))
        self.assertIn("Missing sections", html)


if __name__ == "__main__":
    unittest.main()


class GearScoreTests(unittest.TestCase):
    def test_item_formula(self):
        from warmane_exporter.gearscore import item_score
        self.assertEqual(item_score("epic", 264, "head"), (494, 264))        # floor((264-91.45)/0.65*1*1.8618)
        self.assertEqual(item_score("epic", 245, "two-hand"), (floor_((245 - 91.45) / 0.65 * 2 * 1.8618), 245))
        self.assertEqual(item_score("rare", 200, "waist")[0], floor_((200 - 81.375) / 0.8125 * 0.75 * 1.8618))
        self.assertEqual(item_score("legendary", 284, "two-hand")[0], floor_((284 - 91.45) / 0.65 * 2 * 1.8618 * 1.3))
        self.assertEqual(item_score("heirloom", 1, "chest"), (floor_((187.05 - 81.375) / 0.8125 * 1.8618), 0))
        self.assertEqual(item_score("epic", 10, "head")[0], 0)                # never negative
        self.assertIsNone(item_score("epic", None, "head"))
        self.assertIsNone(item_score("epic", 200, "bag"))

    def test_character_adjustments(self):
        from warmane_exporter.gearscore import character_score
        gear = [{"slot": "Main Hand", "quality": "epic", "item_level": 245, "inventory_type": "two-hand"},
                {"slot": "Off Hand", "quality": "epic", "item_level": 245, "inventory_type": "two-hand"},
                {"slot": "Shirt", "quality": "epic", "item_level": 245, "inventory_type": "shirt"}]
        one = floor_((245 - 91.45) / 0.65 * 2 * 1.8618)
        titan = character_score(gear, "Warrior")
        self.assertEqual((titan["gearscore"], titan["items"], titan["adjustments"]), (floor_(one * 0.5 * 2), 2, ["Titan's Grip x0.5"]))
        gear[1]["inventory_type"] = "off-hand"
        hunter = character_score([{"slot": "Ranged", "quality": "epic", "item_level": 245, "inventory_type": "ranged"}], "Hunter")
        self.assertEqual(hunter["gearscore"], floor_(floor_((245 - 91.45) / 0.65 * 0.3164 * 1.8618) * 5.3224))
        missing = character_score([{"slot": "Head", "quality": "epic", "item_level": None, "inventory_type": "head"}], "Priest")
        self.assertIsNone(missing["gearscore"])


def floor_(x):
    import math
    return math.floor(x)


class GemColumnTests(unittest.TestCase):
    def test_columns(self):
        from warmane_exporter.report import gem_columns
        red = {"text": "+23 Spell Power", "id": 3520, "quality": "epic", "color": "red"}
        empty = {"id": 0, "empty": True}
        lines, buckle = gem_columns("Waist", [red, red, empty], ["yellow"])
        self.assertEqual((lines, buckle), (["+23 Spell Power (epic red)", "+23 Spell Power (epic red)"], True))
        lines, buckle = gem_columns("Head", [red, empty, empty], ["meta", "blue"])
        self.assertEqual((lines, buckle), (["+23 Spell Power (epic red)", "<no gem>"], False))
        lines, buckle = gem_columns("Hands", [{"text": "+9 Stamina", "id": 1}, red, empty], ["red"])
        self.assertEqual(lines, ["+9 Stamina", "+23 Spell Power (epic red)"])      # extra socket, no tags known
        self.assertEqual(gem_columns("Waist", [red, red], None), (["+23 Spell Power (epic red)", "+23 Spell Power (epic red)"], False))


class SuspectTests(unittest.TestCase):
    def test_equal_heroic_count_is_marked(self):
        from warmane_exporter.pve_report import suspect_cells
        prog = build_progression(_stats() + [{"category_id": 14963, "category": "U", "parent": 14807, "rows": [
            {"name": "Ignis kills (Ulduar 10 player)", "value": "13"}, {"name": "Ignis kills (Heroic Ulduar 10 player)", "value": "13"},
            {"name": "Ignis kills (Ulduar 25 player)", "value": "5"}, {"name": "Ignis kills (Heroic Ulduar 25 player)", "value": "- -"}]}])
        ulduar = [i for i in prog["wotlk_raids"] if i["name"] == "Ulduar"][0]
        self.assertEqual(suspect_cells(ulduar), {("Ignis", (10, True))})
        self.assertIn("Ulduar", {i["name"] for i in prog["wotlk_raids"]})
        self.assertIn("The Nexus", {i["name"] for i in prog["wotlk_dungeons"]})

    def test_sections_and_removed_table(self):
        html = render_html(build_pve_report(HtmlTests("test_content_and_escaping").report if False else _full_report()))
        self.assertNotIn("Bosses killed per instance and mode", html)
        self.assertIn("<details open>", html)
        self.assertLess(html.index("WotLK raid progression"), html.index("Other dungeon and raid statistics</h2>"))
        self.assertLess(html.index("Other dungeon and raid statistics</h2>"), html.index("WotLK raid achievements</h2>"))
        self.assertNotIn("Collapsed by default", html)
        self.assertIn("<th>Percent</th>", html)
        self.assertIn("1 / 2", html)
        self.assertIn("50%", html)
        self.assertIn('class="warn"', html)


def _full_report():
    t = HtmlTests("test_content_and_escaping")
    t.setUp()
    return t.report
