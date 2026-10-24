from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from warmane_exporter.cache import ResponseCache
from warmane_exporter.checkpoint import ProbeCheckpointStore
from warmane_exporter.fetch import fetch_character_summary
from warmane_exporter.http_client import HttpResponse
from warmane_exporter.transport import RequestOrchestrator, TransportConfig

GOOD = Path("tests/fixtures/real/api-summary-aikka-onyxia.json").read_text(encoding="utf-8")


class FakeClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    def get(self, url, connect_timeout, read_timeout):
        self.calls += 1
        return self.responses.pop(0)


def ok(body=GOOD):
    return HttpResponse(status_code=200, headers={}, body_text=body)


class FetchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = TemporaryDirectory()
        root = Path(self.tmp.name)
        self.cache = ResponseCache(root / "c.sqlite")
        self.orch = RequestOrchestrator(
            checkpoint=ProbeCheckpointStore(root / "s.json"),
            config=TransportConfig(jitter_ratio=0.0, max_transient_retries=0, max_rate_limit_retries=0),
            sleep_fn=lambda s: None,
            skip_completed=False,
        )
        self.now = 10_000.0

    def tearDown(self) -> None:
        self.cache.close()
        self.tmp.cleanup()

    def fetch(self, client, **kw):
        return fetch_character_summary("Aikka", "Onyxia", self.cache, self.orch, client,
                                       now_fn=lambda: self.now, **kw)

    def test_live_then_fresh_cache_without_second_request(self) -> None:
        client = FakeClient([ok()])
        first = self.fetch(client)
        second = self.fetch(client)
        self.assertEqual((first.origin, second.origin), ("network", "cache"))
        self.assertEqual(client.calls, 1)

    def test_expired_cache_triggers_request_and_refresh_flag_forces_it(self) -> None:
        client = FakeClient([ok(), ok(), ok()])
        self.fetch(client)
        self.now += 901
        self.assertEqual(self.fetch(client).origin, "network")
        self.assertEqual(self.fetch(client, refresh=True).origin, "network")
        self.assertEqual(client.calls, 3)

    def test_error_page_never_overwrites_valid_cache(self) -> None:
        client = FakeClient([ok(), ok('{"error":"nope"}'), ok("<html>Access denied</html>")])
        self.fetch(client)
        self.now += 2000
        rejected = self.fetch(client)
        self.assertEqual(rejected.status, "failed")
        blocked = self.fetch(client)
        self.assertEqual(blocked.status, "failed")
        stale = self.fetch(FakeClient([]), offline=True)
        self.assertEqual(stale.origin, "stale-cache")
        self.assertEqual(stale.data["name"], "Aikka")

    def test_stale_fallback_only_when_allowed_and_disclosed(self) -> None:
        client = FakeClient([ok(), HttpResponse(status_code=403, headers={}, body_text="forbidden")])
        self.fetch(client)
        self.now += 2000
        client2 = FakeClient([HttpResponse(status_code=403, headers={}, body_text="forbidden")] * 2)
        self.assertEqual(self.fetch(client2).status, "failed")
        result = self.fetch(client2, allow_stale=True)
        self.assertEqual((result.status, result.origin), ("ok", "stale-cache"))
        self.assertIn("stale", result.detail.lower())

    def test_offline_miss_makes_no_request(self) -> None:
        client = FakeClient([])
        result = self.fetch(client, offline=True)
        self.assertEqual(result.status, "offline_miss")
        self.assertEqual(client.calls, 0)


if __name__ == "__main__":
    unittest.main()
