from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from warmane_exporter.checkpoint import ProbeCheckpointStore
from warmane_exporter.http_client import DEFAULT_HEADERS, HttpResponse, UrllibHttpClient
from warmane_exporter.transport import RequestOrchestrator, TransportConfig
from warmane_exporter.warmane_api import ApiError, api_summary_url, parse_api_summary

REAL = Path("tests/fixtures/real")


class ApiParserTests(unittest.TestCase):
    def test_url_building(self) -> None:
        self.assertEqual(
            api_summary_url("Aikka", "onyxia"),
            "https://armory.warmane.com/api/character/Aikka/Onyxia/summary",
        )
        with self.assertRaises(ValueError):
            api_summary_url("Aikka", "Lordaeron")

    def test_real_priest_fixture(self) -> None:
        result = parse_api_summary((REAL / "api-summary-aikka-onyxia.json").read_text(encoding="utf-8"))
        self.assertEqual(result["class"], "Priest")
        self.assertEqual(len(result["equipment"]), 17)
        self.assertEqual(result["equipment"][0]["item_id"], 51178)
        self.assertEqual([t["total"] for t in result["talent_trees"]], [71, 71])
        self.assertEqual(result["warnings"], [])

    def test_real_death_knight_fixture_empty_guild(self) -> None:
        result = parse_api_summary((REAL / "api-summary-bezduse-icecrown.json").read_text(encoding="utf-8"))
        self.assertIsNone(result["guild"])
        self.assertEqual(len(result["equipment"]), 16)
        self.assertEqual(result["pvp_teams"], [])

    def test_rejects_error_and_garbage(self) -> None:
        for body in ('{"error":"Character not found"}', "<html>Error 1015</html>", "[]", '{"name":"x"}'):
            with self.assertRaises(ApiError):
                parse_api_summary(body)


class ClientAndTransportTests(unittest.TestCase):
    def test_default_headers_are_fixed_browser_compatible(self) -> None:
        self.assertIn("Mozilla/5.0", DEFAULT_HEADERS["User-Agent"])
        client = UrllibHttpClient()
        self.assertEqual(client.headers["User-Agent"], DEFAULT_HEADERS["User-Agent"])
        self.assertIsNot(client.headers, DEFAULT_HEADERS)

    def test_post_form_is_dispatched_and_checkpoint_key_includes_form(self) -> None:
        calls = []

        class FakeClient:
            def post_form(self, url, form, connect_timeout, read_timeout, referer=None):
                calls.append((url, dict(form), referer))
                return HttpResponse(status_code=200, headers={}, body_text=json.dumps({"content": "<div/>"}))

        with TemporaryDirectory() as tmp:
            store = ProbeCheckpointStore(path=Path(tmp) / "cp.json")
            orch = RequestOrchestrator(checkpoint=store, config=TransportConfig(jitter_ratio=0.0),
                                       sleep_fn=lambda s: None)
            url = "https://armory.warmane.com/character/Aikka/Onyxia/achievements"
            first = orch.execute_single_request(url, FakeClient(), form={"category": "92"}, referer=url)
            other = orch.execute_single_request(url, FakeClient(), form={"category": "96"}, referer=url)
            again = orch.execute_single_request(url, FakeClient(), form={"category": "92"}, referer=url)
        self.assertEqual(first.status, "success")
        self.assertEqual(other.status, "success")
        self.assertEqual(again.status, "skipped_completed")
        self.assertEqual([c[1] for c in calls], [{"category": "92"}, {"category": "96"}])


if __name__ == "__main__":
    unittest.main()
