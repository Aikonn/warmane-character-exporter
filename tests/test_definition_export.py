import json
import tempfile
import unittest
from pathlib import Path

from warmane_exporter.client_definitions import SpellInfo
from warmane_exporter.definition_export import export_definitions
from warmane_exporter.definitions import Definitions, load_definitions
from warmane_exporter.file_definitions import FileDefinitions
from warmane_exporter.spell_text import Rendered


class FakeTable:
    def __init__(self, rows, strings=None):
        self.rows, self.strings = rows, strings or {}

    def __len__(self):
        return len(self.rows)

    def row(self, i):
        return self.rows[i]

    def string_at(self, offset):
        return self.strings.get(offset)


class FakeDefs:
    def _table(self, name, fields):
        if name == "SpellItemEnchantment.dbc":
            return FakeTable([tuple([3820] + [0] * 13 + [1] + [0] * 23), tuple([3627] + [0] * 13 + [2] + [0] * 23)],
                             {1: "+30 Spell Power", 2: "+20 Crit"})
        if name == "GemProperties.dbc":
            return FakeTable([(1, 3520, 0, 0, 2), (2, 3118, 0, 0, 6), (3, 0, 0, 0, 1)])
        if name == "Talent.dbc":
            return FakeTable([tuple([7, 41, 2, 1, 100, 101] + [0] * 7 + [0] * 10)])
        if name == "GlyphProperties.dbc":
            return FakeTable([(5, 200, 1, 0)])
        raise KeyError(name)

    def spell(self, sid):
        return {100: SpellInfo(100, "Talent", "Rank 1", "Does $s1"), 101: SpellInfo(101, "Talent", "Rank 2", "Does $s1"),
                200: SpellInfo(200, "Glyph of X", "", "Bad $x")}.get(sid)

    def render_spell_description(self, sid):
        if sid == 200:
            raise RuntimeError("boom")
        return Rendered(f"Does {sid}", sid == 101)


class ExportTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.data = export_definitions(FakeDefs())
        (self.root / "definitions").mkdir()
        (self.root / "definitions" / "client-export.json").write_text(json.dumps(self.data), encoding="utf-8")

    def test_export_content(self):
        self.assertEqual(self.data["enchants"], {"3820": "+30 Spell Power", "3627": "+20 Crit"})
        self.assertEqual(self.data["client_tables"], {"enchants": 2, "gem_properties": 2, "enchant_conditions": 0, "talents": 1, "glyphs": 1, "spells": 3})
        self.assertIn("render_error", self.data["spells"]["200"])
        self.assertTrue(self.data["spells"]["101"]["rendered_unresolved"])

    def test_file_definitions_roundtrip(self):
        f = FileDefinitions(self.root / "definitions" / "client-export.json")
        self.assertEqual(f.enchant_text(3820), "+30 Spell Power")
        self.assertIsNone(f.enchant_text(1))
        self.assertEqual(f.talent_for_spell(101).rank_spell_ids, (100, 101))
        self.assertEqual(f.glyph_for_spell(200).slot_flags, 1)
        self.assertEqual(f.render_spell_description(101).unresolved, True)
        self.assertIsNone(f.render_spell_description(200))
        self.assertEqual(f.spell(100).rank, "Rank 1")

    def test_definitions_use_file_without_client(self):
        defs = load_definitions(None, self.root)
        self.assertEqual(defs.source_names, ["export-file"])
        self.assertEqual(defs.enchant_text(3627), "+20 Crit")
        self.assertIsNone(defs.item(1))

    def test_client_wins_over_file(self):
        class Client:
            def enchant_text(self, i):
                return "client text"
            def spell(self, i): return None
            def render_spell_description(self, i): return None
            def talent_for_spell(self, i): return None
            def glyph_for_spell(self, i): return None
        defs = Definitions(Client(), None, FileDefinitions(self.root / "definitions" / "client-export.json"))
        self.assertEqual(defs.enchant_text(3820), "client text")
        self.assertEqual(defs.talent_for_spell(100).talent_id, 7)  # falls through to the file

    def test_gem_info_colour_and_quality(self):
        from test_acore_items import _COLUMNS, _row, _sql
        from warmane_exporter.acore_items import build_database
        row = _row(40113, "Runed Cardinal Ruby", quality=4)
        row[_COLUMNS.index("class")], row[_COLUMNS.index("GemProperties")] = 3, 1
        cheap = _row(39999, "Runed Scarlet Ruby", quality=3)
        cheap[_COLUMNS.index("class")], cheap[_COLUMNS.index("GemProperties")] = 3, 1
        build_database(_sql([row, cheap]), self.root / "acore" / "items.db")
        defs = load_definitions(None, self.root)
        self.addCleanup(defs.close)
        self.assertEqual(defs.gem_info(3520), {"color": "red", "quality": "epic"})
        self.assertEqual(defs.gem_info(3118), {"color": "orange", "quality": None})   # no gem item known
        self.assertIsNone(defs.gem_info(1))

    def test_wrong_schema_rejected(self):
        bad = self.root / "bad.json"
        bad.write_text(json.dumps({"schema": "x"}), encoding="utf-8")
        with self.assertRaises(ValueError):
            FileDefinitions(bad)


if __name__ == "__main__":
    unittest.main()
