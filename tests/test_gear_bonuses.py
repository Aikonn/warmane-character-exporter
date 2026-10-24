import unittest

from warmane_exporter.client_definitions import parse_conditions
from warmane_exporter.gear_bonuses import analyze, set_bonuses, parse_bonus, requirements_met


def gem(text, color, **extra):
    return {"id": 1, "text": text, "color": color, **extra}


class BonusTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(parse_bonus("+37 Stamina and +20 Defense Rating"), {"Stamina": 37, "Defense Rating": 20})
        self.assertEqual(parse_bonus("+2% Threat and 10 Parry Rating"), {"Parry Rating": 10})
        self.assertEqual(parse_bonus("+10 All Stats"), {s: 10 for s in ("Strength", "Agility", "Stamina", "Intellect", "Spirit")})
        self.assertEqual(parse_bonus("+30 Spell Power and 20 Critical strike rating."), {"Spell Power": 30, "Critical Strike Rating": 20})
        self.assertEqual(parse_bonus("+2 mana every 5 sec."), {"Mana per 5 sec": 2})
        self.assertEqual(parse_bonus("Mongoose"), {})
        self.assertEqual(parse_bonus("+21 Intellect and Chance to restore mana on spellcast"), {"Intellect": 21})

    def test_requirements(self):
        counts = {1: 1, 2: 0, 3: 2, 4: 3}
        self.assertTrue(requirements_met([[4, 5, 0, 2]], counts))          # at least 2 blue
        self.assertFalse(requirements_met([[2, 5, 0, 1]], counts))         # at least 1 red
        self.assertTrue(requirements_met([[4, 3, 0, 2]], counts))          # more than 2 blue
        self.assertTrue(requirements_met([[3, 2, 4, 0]], counts))          # fewer yellow than blue
        self.assertTrue(requirements_met([[4, 3, 3, 0]], counts))          # more blue than yellow
        self.assertIsNone(requirements_met([[4, 9, 0, 2]], counts))

    def test_parse_conditions(self):
        import struct
        def record(cid, colors, comps, compare, values):
            pad = lambda x: list(x) + [0] * (5 - len(x))
            return struct.pack("<I5B5I5B5B5I5B", cid, *pad(colors), *[0] * 5, *pad(comps), *pad(compare), *pad(values), *[0] * 5)
        data = b"WDBC" + struct.pack("<IIII", 2, 31, 64, 1) + record(31, [3, 2], [5, 5], [], [2, 1]) + record(34, [2], [3], [4], []) + b"\0"
        self.assertEqual(parse_conditions(data), {31: [[3, 5, 0, 2], [2, 5, 0, 1]], 34: [[2, 3, 4, 0]]})

    def test_analyze(self):
        meta = gem("+32 Stamina and 2% Increased Armor Value from Items", "meta", requirements=[[4, 5, 0, 2]])
        head = {"slot": "Head", "stats": [["stamina", 100]], "armor": 50, "sockets": ["meta", "blue"], "socket_bonus": "+9 Stamina",
                "enchant": "+30 Stamina", "gem_details": [meta, gem("+30 Stamina", "blue")]}
        hands = {"slot": "Hands", "stats": [["spell power", 70]], "sockets": ["red"], "socket_bonus": "+4 Spell Power",
                 "gem_details": [gem("+23 Spell Power", "blue")]}
        belt = {"slot": "Waist", "stats": [], "sockets": ["yellow"], "socket_bonus": "+5 Spirit",
                "gem_details": [gem("+10 Spirit", "yellow"), {"position": 1, "id": 0, "empty": True}]}
        result = analyze([head, hands, belt])
        # blue gems: head blue + hands blue = 2 -> meta active; head bonus active, hands bonus inactive (blue in red socket)
        self.assertEqual(head["gem_states"], ["active", None])
        self.assertEqual(head["socket_bonus_info"]["active"], True)
        self.assertEqual(hands["socket_bonus_info"]["active"], False)
        self.assertEqual(belt["socket_bonus_info"]["active"], True)
        t = result["totals"]
        self.assertEqual(t["Stamina"], 100 + 30 + 30 + 32 + 9)
        self.assertEqual((t["Spell Power"], t["Spirit"], t["Armor"]), (70 + 23, 15, 50))
        self.assertEqual(list(t)[0], "Spirit" if False else "Stamina")
        hands["gem_details"][0] = gem("+23 Spell Power", "red")
        meta_inactive = analyze([head, hands])
        self.assertEqual(head["gem_states"], ["inactive", None])
        self.assertEqual(meta_inactive["totals"]["Stamina"], 100 + 30 + 30 + 9)

    def test_empty_socket_inactive(self):
        item = {"slot": "Head", "sockets": ["red"], "socket_bonus": "+4 Spell Power", "gem_details": [{"id": 0, "empty": True}]}
        analyze([item])
        self.assertFalse(item["socket_bonus_info"]["active"])

    def test_set_bonuses(self):
        info = {"id": 9, "name": "Test Raiment", "size": 5,
                "bonuses": [{"threshold": 2, "text": "A"}, {"threshold": 4, "text": "B"}]}
        equipment = [{"set": info}, {"set": info}, {"set": info}, {"set": None}]
        result = set_bonuses(equipment)
        self.assertEqual(len(result), 1)
        self.assertEqual((result[0]["equipped"], [b["active"] for b in result[0]["bonuses"]]), (3, [True, False]))
        self.assertEqual(set_bonuses([{}]), [])


if __name__ == "__main__":
    unittest.main()
