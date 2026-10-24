import tempfile
import unittest
from pathlib import Path

from test_acore_items import _row, _sql

from warmane_exporter.acore_items import AcoreItems, build_database
from warmane_exporter.definitions import Definitions, load_definitions
from warmane_exporter.offline_enrichment import enrich_summary_result
from warmane_exporter.report import build_report, render_markdown


class DefinitionsTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.lib = Path(tmp.name)
        build_database(_sql([_row(1, "Hood", inv=1, sockets=(1, 8, 0)), _row(2, "Ring", inv=11, sockets=(0, 0, 0))]),
                       self.lib / "acore" / "items.db")

    def _defs(self):
        defs = load_definitions(None, self.lib)
        self.addCleanup(defs.close)
        return defs

    def _summary(self, gems):
        return {"equipment": {"slots": [{
            "slot_key": "left_0", "is_empty": False,
            "layout_inference": {"inferred_slot_name": "Head"},
            "item_reference": {"href_item_id": "1", "quality": 4, "quality_name": "epic",
                               "namespaces": {"item": "1", "ench": "0",
                                              "gem_positions": [{"position": i, "raw_value": g} for i, g in enumerate(gems)]}},
        }]}}

    def test_none_without_sources(self):
        self.assertIsNone(load_definitions(None, self.lib / "missing"))
        with self.assertRaises(ValueError):
            Definitions()

    def test_acore_only_enrichment_and_report(self):
        defs = self._defs()
        self.assertEqual(defs.source_names, ["acore"])
        out = enrich_summary_result(self._summary(["3", "0", "0"]), defs)
        client = out["equipment"]["slots"][0]["client"]
        self.assertEqual(client["item"]["inventory_type"], "head")
        self.assertEqual(client["slot_check"], "ok")
        self.assertEqual(client["acore"]["sockets"], ["meta", "blue"])
        self.assertEqual((client["acore"]["gems_filled"], client["acore"]["sockets_empty"]), (1, 1))
        self.assertEqual(out["client_warnings"], ["left_0: gem code 3 text unresolved (no text source has it)"])

    def test_extra_gem_is_warned_not_hidden(self):
        defs = self._defs()
        out = enrich_summary_result(self._summary(["3", "4", "5"]), defs)
        self.assertEqual(out["equipment"]["slots"][0]["client"]["acore"]["sockets_empty"], 0)
        self.assertTrue(any("extra socket" in w for w in out["client_warnings"]))

    def test_unknown_item_is_reported(self):
        defs = self._defs()
        summary = self._summary(["0", "0", "0"])
        summary["equipment"]["slots"][0]["item_reference"]["namespaces"]["item"] = "999"
        out = enrich_summary_result(summary, defs)
        self.assertTrue(any("not in any definition source" in w for w in out["client_warnings"]))

    def test_report_shows_empty_sockets(self):
        defs = self._defs()
        html = enrich_summary_result(self._summary(["0", "0", "0"]), defs)
        snap = {"sections": {"html_summary": {"data": html, "status": "ok"}, "json_summary": {"data": {}}}}
        text = render_markdown(build_report(snap))
        self.assertIn("2 empty socket(s)", text)

    def test_item_effects_from_spell_descriptions(self):
        from test_acore_items import _COLUMNS
        from warmane_exporter.spell_text import Rendered
        row = _row(5, "Dust", inv=12, sockets=(0, 0, 0))
        row[_COLUMNS.index("spellid_1")], row[_COLUMNS.index("spelltrigger_1")] = 77, 1
        row[_COLUMNS.index("spellid_2")], row[_COLUMNS.index("spelltrigger_2")] = 78, 0
        row[_COLUMNS.index("class")] = 4
        path = self.lib / "acore" / "effects.db"
        build_database(_sql([row]), path)

        class Texts:
            def render_spell_description(self, spell_id):
                return Rendered("Grants 304 mana per 5 sec.", False) if spell_id == 77 else None
            def spell(self, spell_id):
                return None
            def __getattr__(self, name):
                return lambda key: None

        defs = Definitions(acore=AcoreItems(path), file=Texts())
        self.addCleanup(defs.close)
        self.assertEqual(defs.acore_item(5).spells, ((77, 1), (78, 0)))
        self.assertEqual(defs.acore.effect_spell_ids(), {77, 78})
        summary = self._summary(["0"])
        summary["equipment"]["slots"][0]["item_reference"]["namespaces"]["item"] = "5"
        out = enrich_summary_result(summary, defs)
        effects = out["equipment"]["slots"][0]["client"]["acore"]["effects"]
        self.assertEqual(effects, [{"trigger": "Equip", "spell": 77, "text": "Grants 304 mana per 5 sec."}])
        self.assertTrue(any("spell 78 has no description" in w for w in out["client_warnings"]))

    def test_item_set_from_item_template(self):
        from test_acore_items import _COLUMNS
        from warmane_exporter.spell_text import Rendered
        rows = []
        for entry in (5, 6, 7):
            row = _row(entry, f"Piece{entry}", inv=1, sockets=(0, 0, 0))
            row[_COLUMNS.index("itemset")] = 9
            rows.append(row)
        path = self.lib / "acore" / "sets.db"
        build_database(_sql(rows), path)

        class Texts:
            def item_set(self, set_id):
                return {"id": 9, "name": "Test Raiment", "items": [5], "bonuses": [[2, 77], [4, 78]]} if set_id == 9 else None
            def render_spell_description(self, spell_id):
                return Rendered("Bonus text.", False) if spell_id == 77 else None
            def spell(self, spell_id):
                return None
            def enchant_text(self, enchant_id):
                return None

        defs = Definitions(acore=AcoreItems(path), file=Texts())
        self.addCleanup(defs.close)
        summary = self._summary([])
        summary["equipment"]["slots"][0]["item_reference"]["namespaces"]["item"] = "5"
        out = enrich_summary_result(summary, defs)
        info = out["equipment"]["slots"][0]["client"]["set"]
        self.assertEqual((info["name"], info["size"]), ("Test Raiment", 3))
        self.assertEqual(info["bonuses"][0], {"threshold": 2, "spell": 77, "text": "Bonus text."})
        self.assertIsNone(info["bonuses"][1]["text"])
        self.assertTrue(any("set bonus spell 78" in w for w in out["client_warnings"]))


if __name__ == "__main__":
    unittest.main()
