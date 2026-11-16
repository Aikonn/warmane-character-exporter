from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest import mock
from contextlib import redirect_stderr
import io

from warmane_exporter.budget import BudgetExhausted
from warmane_exporter.cache import ResponseCache
from warmane_exporter.checkpoint import ProbeCheckpointStore
from warmane_exporter.http_client import HttpResponse
from warmane_exporter.snapshot import build_snapshot, character_page_url
from warmane_exporter.timing import TimingLog, activate
from warmane_exporter.transport import RequestOrchestrator, TransportConfig

FIX = Path("tests/fixtures")
JSON_BODY = (FIX / "real/api-summary-aikka-onyxia.json").read_text(encoding="utf-8")
SUMMARY = (FIX / "synthetic/layout-consistent-with-anchors.html").read_text(encoding="utf-8")
TALENTS = (FIX / "synthetic/talents-page-dom-synthetic.html").read_text(encoding="utf-8")
NOT_FOUND = (FIX / "real/api-summary-not-found-onyxia.json").read_text(encoding="utf-8")


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
        timing_log = TimingLog(self.root / "timing")
        with activate(timing_log), redirect_stderr(io.StringIO()):
            again = build_snapshot("Aikka", "Onyxia", self.cache, self.orch, client, now_fn=lambda: 5100.0)
        self.assertEqual(len(client.urls), 3)
        self.assertEqual({s["origin"] for s in again["sections"].values()}, {"cache"})
        self.assertIn("Client definitions not applied (no client data).", snap["notes"])
        self.assertGreater(timing_log.totals["Aikka@Onyxia | cache lookup / network fetch"], 0)

    def test_snapshot_output_is_identical_for_equivalent_per_run_and_shared_definitions(self):
        class EmptyDefinitions:
            acore = None

            def __getattr__(self, _name):
                return lambda *_args, **_kwargs: None

        first_cache = ResponseCache(self.root / "per-run.sqlite")
        second_cache = ResponseCache(self.root / "shared.sqlite")
        first_client = RoutingClient({
            "/api/character/Aikka/Onyxia/summary": JSON_BODY,
            "/character/Aikka/Onyxia/summary": SUMMARY,
            "/character/Aikka/Onyxia/talents": TALENTS,
        })
        second_client = RoutingClient(dict(first_client.bodies))
        try:
            per_run = build_snapshot(
                "Aikka", "Onyxia", first_cache, self.orch, first_client,
                defs=EmptyDefinitions(), now_fn=lambda: 5000.0,
            )
            shared = EmptyDefinitions()
            roster = build_snapshot(
                "Aikka", "Onyxia", second_cache, self.orch, second_client,
                defs=shared, now_fn=lambda: 5000.0,
            )
        finally:
            first_cache.close()
            second_cache.close()

        self.assertEqual(per_run, roster)

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

    def test_verified_not_found_stops_after_json_and_is_not_cached(self) -> None:
        client = RoutingClient({"/api/character/Qzxqzxqzxqzx/Onyxia/summary": NOT_FOUND})
        snap = build_snapshot("Qzxqzxqzxqzx", "Onyxia", self.cache, self.orch, client)
        self.assertEqual(len(client.urls), 1)
        self.assertEqual(snap["sections"]["json_summary"]["status"], "not_found")
        self.assertEqual(snap["sections"]["html_summary"]["status"], "not_run")
        self.assertEqual(snap["sections"]["talents"]["status"], "not_run")
        self.assertIsNone(self.cache.get(
            "warmane-json-summary|https://armory.warmane.com/api/character/Qzxqzxqzxqzx/Onyxia/summary"
        ))

    def test_access_block_stops_remaining_snapshot_requests(self):
        class BlockedClient:
            def __init__(self):
                self.calls = 0

            def get(self, url, connect_timeout, read_timeout):
                self.calls += 1
                return HttpResponse(status_code=200, headers={}, body_text="Error code: 1010")

        client = BlockedClient()
        snap = build_snapshot("Aikka", "Onyxia", self.cache, self.orch, client)
        self.assertEqual(client.calls, 1)
        self.assertEqual(snap["sections"]["json_summary"]["status"], "failed_access_blocked")
        self.assertEqual(snap["sections"]["html_summary"]["status"], "not_run")
        self.assertEqual(snap["sections"]["talents"]["status"], "not_run")

    def test_snapshot_cli_passes_max_age_minutes_to_fetch_path(self):
        complete = {
            "generated_at": 100.0,
            "character": {"realm": "Onyxia"},
            "complete": True,
            "sections": {
                key: {"status": "ok", "origin": "cache", "detail": ""}
                for key in ("json_summary", "html_summary", "talents")
            },
        }
        timing_log = TimingLog(self.root / "timing")
        with activate(timing_log), redirect_stderr(io.StringIO()), \
             mock.patch("warmane_exporter.definitions.load_definitions", return_value=None), \
             mock.patch("warmane_exporter.snapshot.budgeted_client"), \
             mock.patch("warmane_exporter.snapshot.build_snapshot", return_value=complete) as build:
            code = __import__("warmane_exporter.snapshot", fromlist=["main"]).main([
                "Aikka", "Onyxia", "--cache-dir", str(self.root / "cli-cache"),
                "--no-client", "--max-age-minutes", "120",
            ])
        self.assertEqual(code, 0)
        self.assertEqual(build.call_args.kwargs["max_age_seconds"], 7200)
        self.assertIn("Aikka@Onyxia | definition loading", timing_log.totals)
        self.assertIn("Aikka@Onyxia | snapshot build and save", timing_log.totals)

    def test_snapshot_cli_returns_four_for_budget_exhaustion(self):
        snapshot_module = __import__("warmane_exporter.snapshot", fromlist=["main"])
        with mock.patch("warmane_exporter.definitions.load_definitions", return_value=None), \
             mock.patch("warmane_exporter.snapshot.budgeted_client"), \
             mock.patch("warmane_exporter.snapshot.build_snapshot", side_effect=BudgetExhausted("spent")):
            code = snapshot_module.main([
                "Aikka", "Onyxia", "--cache-dir", str(self.root / "budget-cache"), "--no-client",
            ])
        self.assertEqual(code, 4)

    def test_snapshot_cli_maps_not_found_and_access_block_exit_codes(self):
        snapshot_module = __import__("warmane_exporter.snapshot", fromlist=["main"])
        common_patches = (
            mock.patch("warmane_exporter.definitions.load_definitions", return_value=None),
            mock.patch("warmane_exporter.snapshot.budgeted_client"),
        )
        not_found = {"sections": {"json_summary": {"status": "not_found"}}}
        with common_patches[0], common_patches[1], \
             mock.patch("warmane_exporter.snapshot.build_snapshot", return_value=not_found):
            code = snapshot_module.main([
                "Absent", "Onyxia", "--cache-dir", str(self.root / "not-found-cache"), "--no-client",
            ])
        self.assertEqual(code, 3)

        blocked = {
            "generated_at": 100.0,
            "character": {"realm": "Onyxia"},
            "complete": False,
            "sections": {
                "json_summary": {"status": "failed_access_blocked", "origin": "none", "detail": ""},
                "html_summary": {"status": "not_run", "origin": "none", "detail": ""},
                "talents": {"status": "not_run", "origin": "none", "detail": ""},
            },
        }
        with common_patches[0], common_patches[1], \
             mock.patch("warmane_exporter.snapshot.build_snapshot", return_value=blocked):
            code = snapshot_module.main([
                "Aikka", "Onyxia", "--cache-dir", str(self.root / "blocked-cache"), "--no-client",
            ])
        self.assertEqual(code, 4)


if __name__ == "__main__":
    unittest.main()
