import tempfile
import unittest
from pathlib import Path

from warmane_exporter.acore_cli import fetch, verify_documents
from warmane_exporter.acore_items import AcoreItems, build_database, parse_columns, iter_rows

_COLUMNS = ["entry", "class", "subclass", "name", "Quality", "InventoryType", "ItemLevel", "RequiredLevel",
            "AllowableClass", "AllowableRace", "bonding", "itemset", "socketBonus", "GemProperties", "VerifiedBuild",
            "StatsCount", "ScalingStatDistribution", "ScalingStatValue", "armor", "delay", "MaxDurability"] \
    + [f"stat_type{i}" for i in range(1, 11)] + [f"stat_value{i}" for i in range(1, 11)] \
    + [f"socketColor_{i}" for i in range(1, 4)] + [f"socketContent_{i}" for i in range(1, 4)] \
    + [f"spellid_{i}" for i in range(1, 6)] + [f"spelltrigger_{i}" for i in range(1, 6)]


def _sql(rows):
    cols = "\n".join(f"  `{c}` int NOT NULL," for c in _COLUMNS).replace("`name` int", "`name` varchar(255)")
    body = ",\n".join("(" + ",".join("'" + v + "'" if isinstance(v, str) else str(v) for v in r) + ")" for r in rows)
    return f"DROP TABLE x;\nCREATE TABLE `item_template` \n(\n{cols}\n  PRIMARY KEY (`entry`)\n) ENGINE=InnoDB;\nINSERT INTO `item_template` VALUES \n{body};\n"


def _row(entry, name, quality=4, inv=1, sockets=(2, 8, 0), bonus=3753, stats=((45, 100), (7, 50))):
    values = dict.fromkeys(_COLUMNS, 0)
    values.update(entry=entry, name=name, Quality=quality, InventoryType=inv, socketBonus=bonus, StatsCount=len(stats))
    for i, (t, v) in enumerate(stats, 1):
        values[f"stat_type{i}"], values[f"stat_value{i}"] = t, v
    for i, c in enumerate(sockets, 1):
        values[f"socketColor_{i}"] = c
    return [values[c] for c in _COLUMNS]


class AcoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.sql = _sql([_row(1, "Hood of the Fallen"), _row(2, "Sif\\'s Remembrance", quality=3, sockets=(0, 0, 0))])
        self.path = Path(self.tmp.name) / "items.db"

    def test_parse_escapes_and_columns(self):
        self.assertEqual(parse_columns(self.sql)[0], "entry")
        rows = list(iter_rows(self.sql))
        self.assertEqual(rows[1][_COLUMNS.index("name")], "Sif's Remembrance")

    def test_build_and_lookup(self):
        self.assertEqual(build_database(self.sql, self.path), 2)
        db = AcoreItems(self.path)
        item = db.item(1)
        self.assertEqual((item.name, item.quality_name, item.sockets), ("Hood of the Fallen", "epic", ("red", "blue")))
        self.assertEqual(item.stats, (("spell power", 100), ("stamina", 50)))
        self.assertEqual(db.item(2).sockets, ())
        self.assertIsNone(db.item(99))
        db.close()

    def test_layout_change_is_detected(self):
        with self.assertRaises(ValueError):
            build_database(self.sql.replace("`socketBonus`", "`renamed`"), self.path)

    def test_verify_reports_differences(self):
        build_database(self.sql, self.path)
        db = AcoreItems(self.path)
        docs = {"a": {"equipment": [{"item": "1", "name": "Hood of the Fallen"}, {"item": "2", "name": "Other"},
                                    {"item": "3", "name": "Gone"}]},
                "b": {"x": {"item_reference": {"namespaces": {"item": "1"}, "quality": 3}}}}
        report = verify_documents(docs, db)
        db.close()
        self.assertEqual(report["observations"], 4)
        self.assertEqual(len(report["differences"]), 2)
        self.assertEqual(len(report["missing"]), 1)

    def test_fetch_downloads_once(self):
        calls = []
        def download(url):
            calls.append(url)
            return self.sql
        lib = Path(self.tmp.name) / "library"
        self.assertEqual(fetch(lib, download), (2, True))
        self.assertEqual(fetch(lib, download), (2, False))
        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
