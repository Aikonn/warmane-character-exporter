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
        defs = load_definitions(None, self.lib)
        self.assertEqual(defs.source_names, ["acore"])
        out = enrich_summary_result(self._summary(["3", "0", "0"]), defs)
        client = out["equipment"]["slots"][0]["client"]
        self.assertEqual(client["item"]["inventory_type"], "head")
        self.assertEqual(client["slot_check"], "ok")
        self.assertEqual(client["acore"]["sockets"], ["meta", "blue"])
        self.assertEqual((client["acore"]["gems_filled"], client["acore"]["sockets_empty"]), (1, 1))
        self.assertEqual(out["client_warnings"], ["left_0: gem code 3 text unresolved (no text source has it)"])

    def test_extra_gem_is_warned_not_hidden(self):
        defs = load_definitions(None, self.lib)
        out = enrich_summary_result(self._summary(["3", "4", "5"]), defs)
        self.assertEqual(out["equipment"]["slots"][0]["client"]["acore"]["sockets_empty"], 0)
        self.assertTrue(any("extra socket" in w for w in out["client_warnings"]))

    def test_unknown_item_is_reported(self):
        defs = load_definitions(None, self.lib)
        summary = self._summary(["0", "0", "0"])
        summary["equipment"]["slots"][0]["item_reference"]["namespaces"]["item"] = "999"
        out = enrich_summary_result(summary, defs)
        self.assertTrue(any("not in any definition source" in w for w in out["client_warnings"]))

    def test_report_shows_empty_sockets(self):
        defs = load_definitions(None, self.lib)
        html = enrich_summary_result(self._summary(["0", "0", "0"]), defs)
        snap = {"sections": {"html_summary": {"data": html, "status": "ok"}, "json_summary": {"data": {}}}}
        text = render_markdown(build_report(snap))
        self.assertIn("2 empty socket(s)", text)


if __name__ == "__main__":
    unittest.main()
