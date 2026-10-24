from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from warmane_exporter.cache import ResponseCache
from warmane_exporter.checkpoint import ProbeCheckpointStore
from warmane_exporter.http_client import HttpResponse
from warmane_exporter.snapshot import build_snapshot, character_page_url
from warmane_exporter.transport import RequestOrchestrator, TransportConfig

FIX = Path("tests/fixtures")
JSON_BODY = (FIX / "real/api-summary-aikka-onyxia.json").read_text(encoding="utf-8")
SUMMARY = (FIX / "synthetic/layout-consistent-with-anchors.html").read_text(encoding="utf-8")
TALENTS = (FIX / "synthetic/talents-page-dom-synthetic.html").read_text(encoding="utf-8")


class RoutingClient:
    def __init__(self, bodies):
        self.bodies = bodies
        self.urls = []

    def get(self, url, connect_timeout, read_timeout):
        self.urls.append(url)
        for suffix, body in self.bodies.items():
            if url.endswith(suffix):
                return HttpResponse(status_code=200, headers={}, body_text=body)
        raise AssertionError(url)


class SnapshotTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = TemporaryDirectory()
        root = Path(self.tmp.name)
        self.cache = ResponseCache(root / "c.sqlite")
        self.orch = RequestOrchestrator(
            checkpoint=ProbeCheckpointStore(root / "s.json"),
            config=TransportConfig(jitter_ratio=0.0, max_transient_retries=0, max_rate_limit_retries=0),
            sleep_fn=lambda s: None, skip_completed=False,
        )
        self.root = root

    def tearDown(self) -> None:
        self.cache.close()
        self.tmp.cleanup()

    def test_urls(self) -> None:
        self.assertEqual(character_page_url("Aikka", "icecrown", "talents"),
                         "https://armory.warmane.com/character/Aikka/Icecrown/talents")

    def test_full_snapshot_three_requests_then_cache(self) -> None:
        client = RoutingClient({})
        client.bodies = {"/api/character/Aikka/Onyxia/summary": JSON_BODY,
                         "/character/Aikka/Onyxia/summary": SUMMARY,
                         "/character/Aikka/Onyxia/talents": TALENTS}
        snap = build_snapshot("Aikka", "Onyxia", self.cache, self.orch, client, now_fn=lambda: 5000.0)
        self.assertTrue(snap["complete"], snap["sections"])
        self.assertEqual(len(client.urls), 3)
        again = build_snapshot("Aikka", "Onyxia", self.cache, self.orch, client, now_fn=lambda: 5100.0)
        self.assertEqual(len(client.urls), 3)
        self.assertEqual({s["origin"] for s in again["sections"].values()}, {"cache"})
        self.assertIn("Client definitions not applied (no client data).", snap["notes"])

    def test_invalid_html_fails_only_that_section_and_is_saved_for_debugging(self) -> None:
        client = RoutingClient({})
        client.bodies = {"/api/character/Aikka/Onyxia/summary": JSON_BODY,
                         "/character/Aikka/Onyxia/summary": "<html>no equipment here</html>",
                         "/character/Aikka/Onyxia/talents": TALENTS}
        rejects = self.root / "rejected"
        snap = build_snapshot("Aikka", "Onyxia", self.cache, self.orch, client,
                              now_fn=lambda: 5000.0, reject_dir=rejects)
        self.assertFalse(snap["complete"])
        self.assertEqual(snap["sections"]["json_summary"]["status"], "ok")
        self.assertEqual(snap["sections"]["html_summary"]["status"], "failed")
        self.assertEqual(snap["sections"]["talents"]["status"], "ok")
        self.assertEqual(len(list(rejects.glob("*.txt"))), 1)
        self.assertIsNone(self.cache.get("warmane-html-summary|https://armory.warmane.com/character/Aikka/Onyxia/summary"))


if __name__ == "__main__":
    unittest.main()
