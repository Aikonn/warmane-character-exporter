import tempfile
import unittest
from datetime import date
from pathlib import Path

from warmane_exporter.budget import BudgetedHttpClient, BudgetExhausted, BudgetLedger
from warmane_exporter.library import Library


class Inner:
    def __init__(self):
        self.calls = 0

    def get(self, *a, **k):
        self.calls += 1
        return "ok"

    post_form = get


class BudgetTests(unittest.TestCase):
    def test_limit_stops_before_sending(self):
        with tempfile.TemporaryDirectory() as d:
            ledger = BudgetLedger(Path(d) / "b.json", daily_limit=2)
            inner = Inner()
            client = BudgetedHttpClient(inner, ledger)
            client.get("u")
            client.post_form("u")
            with self.assertRaises(BudgetExhausted):
                client.get("u")
            self.assertEqual(inner.calls, 2)
            self.assertEqual((ledger.used, ledger.remaining), (2, 0))

    def test_override_and_new_day_reset(self):
        with tempfile.TemporaryDirectory() as d:
            day = [date(2026, 10, 24)]
            ledger = BudgetLedger(Path(d) / "b.json", daily_limit=1, today=lambda: day[0])
            ledger.charge()
            ledger.set_limit(3)
            ledger.charge()
            self.assertEqual(ledger.remaining, 1)
            day[0] = date(2026, 10, 25)
            self.assertEqual((ledger.used, ledger.limit), (0, 1))


class LibraryTests(unittest.TestCase):
    def test_fetch_once_then_reuse(self):
        with tempfile.TemporaryDirectory() as d:
            lib = Library(Path(d) / "library")
            calls = []

            def fetch(url):
                calls.append(url)
                return "<html>item</html>"

            text, live = lib.get_or_fetch("item", 50761, "http://x/item=50761", fetch)
            self.assertTrue(live)
            text2, live2 = lib.get_or_fetch("item", 50761, "http://x/item=50761", fetch)
            self.assertFalse(live2)
            self.assertEqual((text, text2, len(calls)), ("<html>item</html>", "<html>item</html>", 1))
            index = (Path(d) / "library" / "index.jsonl").read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(index), 1)

    def test_unsafe_keys_are_sanitised(self):
        with tempfile.TemporaryDirectory() as d:
            lib = Library(Path(d))
            path = lib.put("../etc", "a/b", "x", "u")
            self.assertTrue(str(path).startswith(str(Path(d))))


if __name__ == "__main__":
    unittest.main()
