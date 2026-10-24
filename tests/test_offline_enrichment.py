import tempfile
import unittest
from pathlib import Path

from warmane_exporter.client_definitions import ClientDefinitions
from warmane_exporter.mpq_reader import ClientData
from warmane_exporter.offline_enrichment import enrich_talents_result

try:
    from tests.test_mpq_dbc import build_dbc, build_mpq
except ImportError:
    from test_mpq_dbc import build_dbc, build_mpq


def _row(fields, values):
    return tuple(values.get(i, 0) for i in range(fields))


class EnrichmentTests(unittest.TestCase):
    def _defs(self) -> ClientDefinitions:
        strings = b"\x00Improved PWS\x00Rank 1 text\x00Rank 2 text\x00Glyph of Flash Heal\x00Cost down\x00"
        spell = build_dbc([
            _row(234, {0: 14748, 136: 1, 170: 14}),
            _row(234, {0: 14768, 136: 1, 170: 26}),
            _row(234, {0: 55679, 136: 38, 170: 57}),
        ], strings)
        talent = build_dbc([_row(23, {0: 343, 1: 201, 2: 2, 3: 2, 4: 14748, 5: 14768})])
        glyph = build_dbc([_row(4, {0: 9, 1: 55679, 2: 0})])
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        (Path(tmp.name) / "patch-3.MPQ").write_bytes(build_mpq({
            "DBFilesClient\\Spell.dbc": spell,
            "DBFilesClient\\Talent.dbc": talent,
            "DBFilesClient\\GlyphProperties.dbc": glyph,
        }))
        client = ClientData(tmp.name)
        self.addCleanup(client.close)
        return ClientDefinitions(client)

    def test_enrich(self) -> None:
        result = {
            "specs": [{"trees": [{"talents": [
                {"source_spell_id": "14768", "points_spent": 2, "points_max": 2},
                {"source_spell_id": "999", "points_spent": 1, "points_max": 1},
            ]}]}],
            "glyphs": {"0": {"entries": [
                {"category": "major", "source_spell_id": "55679", "name": "Flash Heal"},
                {"category": "minor", "source_spell_id": "55679", "name": "Flash Heal"},
            ]}},
        }
        before = repr(result)
        out = enrich_talents_result(result, self._defs())
        self.assertEqual(repr(result), before)  # input untouched
        t0, t1 = out["specs"][0]["trees"][0]["talents"]
        self.assertEqual(t0["client"]["talent_id"], 343)
        self.assertEqual(t0["client"]["selected_rank_spell_id"], 14768)
        self.assertEqual(t0["client"]["selected_rank_description"], "Rank 2 text")
        self.assertEqual(t0["client"]["name"], "Improved PWS")
        self.assertFalse(t1["client"]["resolved"])
        g0, g1 = out["glyphs"]["0"]["entries"]
        self.assertEqual(g0["client"]["slot_type"], "major")
        self.assertEqual(g0["client"]["spell_name"], "Glyph of Flash Heal")
        warnings = out["client_warnings"]
        self.assertTrue(any("999" in w for w in warnings))
        self.assertTrue(any("client slot major != capture category minor" in w for w in warnings))


if __name__ == "__main__":
    unittest.main()
