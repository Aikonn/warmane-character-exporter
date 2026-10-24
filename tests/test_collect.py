import json
import tempfile
import unittest
from pathlib import Path

from warmane_exporter.cache import ResponseCache
from warmane_exporter.collect import ACHIEVEMENT_CATEGORIES, collect_achievements, summarize
from warmane_exporter.transport import RequestOrchestrator, TransportConfig
from warmane_exporter.checkpoint import ProbeCheckpointStore

FIX = Path(__file__).parent / "fixtures" / "real" / "achievements-92-sample-aikka-onyxia.json"
SMALL = ACHIEVEMENT_CATEGORIES[:3]


class FakeResponse:
    def __init__(self, text):
        self.status_code, self.body_text, self.headers = 200, text, {}
        self.final_url = "x"


class FakeOrch:
    def __init__(self):
        self.calls = []

    def execute_single_request(self, url, client, form=None, referer=None):
        self.calls.append(form)

        class R:
            status = "success"
            detail = ""
            body_text = FIX.read_text(encoding="utf-8")
        return R()


class CollectTests(unittest.TestCase):
    def test_limit_defers_and_resume_uses_cache(self):
        with tempfile.TemporaryDirectory() as d:
            cache = ResponseCache(Path(d) / "c.sqlite")
            orch = FakeOrch()
            first = collect_achievements("Aikka", "Onyxia", cache, orch, None, limit=2, categories=SMALL)
            self.assertEqual(first["live_requests"], 2)
            self.assertEqual([c["status"] for c in first["categories"]], ["ok", "ok", "deferred"])
            self.assertFalse(first["complete"])
            second = collect_achievements("Aikka", "Onyxia", cache, orch, None, limit=2, categories=SMALL)
            self.assertEqual(second["live_requests"], 1)
            self.assertTrue(second["complete"])
            self.assertEqual(len(orch.calls), 3)
            self.assertEqual(orch.calls[0], {"category": "92"})
            cache.close()

    def test_dry_run_and_offline_make_no_requests(self):
        with tempfile.TemporaryDirectory() as d:
            cache = ResponseCache(Path(d) / "c.sqlite")
            orch = FakeOrch()
            plan = collect_achievements("Aikka", "Onyxia", cache, orch, None, dry_run=True, categories=SMALL)
            self.assertEqual([c["origin"] for c in plan["categories"]], ["live"] * 3)
            off = collect_achievements("Aikka", "Onyxia", cache, orch, None, offline=True, categories=SMALL)
            self.assertEqual(orch.calls, [])
            self.assertEqual(off["categories"][0]["status"], "offline_miss")
            cache.close()

    def test_summary_counts_unique(self):
        e = {"id": 1, "earned": True, "points": 10}
        s = summarize([{"status": "ok", "entries": [e]}, {"status": "ok", "entries": [e, {"id": 2, "earned": False, "points": 5}]}])
        self.assertEqual((s["unique_achievements"], s["earned"], s["earned_points"], s["duplicate_ids"]), (2, 1, 10, [1]))

    def test_category_table_is_unique(self):
        ids = [c[0] for c in ACHIEVEMENT_CATEGORIES]
        self.assertEqual(len(ids), len(set(ids)))


if __name__ == "__main__":
    unittest.main()
