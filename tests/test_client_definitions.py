import struct
import tempfile
import unittest
from pathlib import Path

from warmane_exporter.client_definitions import ClientDefinitions
from warmane_exporter.dbc_parser import DbcError
from warmane_exporter.mpq_reader import ClientData

try:
    from tests.test_mpq_dbc import build_dbc, build_mpq
except ImportError:  # run via discover with tests/ as top-level
    from test_mpq_dbc import build_dbc, build_mpq


def _row(fields: int, values: dict[int, int]) -> tuple[int, ...]:
    return tuple(values.get(i, 0) for i in range(fields))


class DefinitionsTests(unittest.TestCase):
    def _client(self, files: dict[str, bytes]) -> ClientData:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        (Path(tmp.name) / "patch-3.MPQ").write_bytes(build_mpq(files))
        client = ClientData(tmp.name)
        self.addCleanup(client.close)
        return client

    def test_lookups(self) -> None:
        strings = b"\x00+30 Spell Power\x00Glyph of Flash Heal\x00Rank 3\x00Reduces cost\x00"
        enchant = build_dbc([_row(38, {0: 3820, 14: 1})], strings)
        spell = build_dbc([_row(234, {0: 55679, 136: 17, 153: 37, 170: 44})], strings)
        item = build_dbc([_row(8, {0: 51178, 1: 4, 2: 1, 6: 1})])
        client = self._client({
            "DBFilesClient\\SpellItemEnchantment.dbc": enchant,
            "DBFilesClient\\Spell.dbc": spell,
            "DBFilesClient\\Item.dbc": item,
        })
        defs = ClientDefinitions(client)
        self.assertEqual(defs.enchant_text(3820), "+30 Spell Power")
        self.assertIsNone(defs.enchant_text(1))
        info = defs.spell(55679)
        self.assertEqual((info.name, info.rank, info.description),
                         ("Glyph of Flash Heal", "Rank 3", "Reduces cost"))
        self.assertIsNone(defs.spell(1))
        it = defs.item(51178)
        self.assertEqual((it.item_class, it.item_subclass, it.inventory_type_name), (4, 1, "head"))
        self.assertIsNone(defs.item(2))

    def test_talent_ranks(self) -> None:
        talent = build_dbc([
            _row(23, {0: 100, 1: 7, 2: 1, 3: 2, 4: 14748, 5: 14768, 6: 14769}),
            _row(23, {0: 101, 1: 7, 2: 0, 3: 0, 4: 555}),
        ])
        defs = ClientDefinitions(self._client({"DBFilesClient\\Talent.dbc": talent}))
        info = defs.talent_for_spell(14768)
        self.assertEqual(info.talent_id, 100)
        self.assertEqual(info.rank_spell_ids, (14748, 14768, 14769))
        self.assertEqual((info.tab_id, info.row, info.column), (7, 1, 2))
        self.assertEqual(defs.talent_for_spell(555).rank_spell_ids, (555,))
        self.assertIsNone(defs.talent_for_spell(1))

    def test_wrong_layout_and_missing_table(self) -> None:
        client = self._client({"DBFilesClient\\Item.dbc": build_dbc([(1, 2, 3)])})
        defs = ClientDefinitions(client)
        with self.assertRaisesRegex(DbcError, "not a 3.3.5a"):
            defs.item(1)
        with self.assertRaisesRegex(DbcError, "not found"):
            defs.spell(1)


if __name__ == "__main__":
    unittest.main()
