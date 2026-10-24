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

    def test_wrong_layout_and_missing_table(self) -> None:
        client = self._client({"DBFilesClient\\Item.dbc": build_dbc([(1, 2, 3)])})
        defs = ClientDefinitions(client)
        with self.assertRaisesRegex(DbcError, "not a 3.3.5a"):
            defs.item(1)
        with self.assertRaisesRegex(DbcError, "not found"):
            defs.spell(1)


if __name__ == "__main__":
    unittest.main()
