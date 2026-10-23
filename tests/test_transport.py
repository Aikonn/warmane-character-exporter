from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from warmane_exporter.checkpoint import ProbeCheckpointStore
from warmane_exporter.http_client import HttpResponse
from warmane_exporter.transport import RequestOrchestrator, TransportConfig, classify_response


class FakeClock:
    def __init__(self, start: float) -> None:
        self.current = start
        self.sleeps: list[float] = []

    def now(self) -> float:
        return self.current

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.current += seconds


class FakeClient:
    def __init__(self, responses: list[HttpResponse]) -> None:
        self.responses = responses
        self.calls = 0

    def get(self, url: str, connect_timeout: float, read_timeout: float) -> HttpResponse:
        _ = (url, connect_timeout, read_timeout)
        if self.calls >= len(self.responses):
            raise AssertionError("No more fake responses configured.")
        response = self.responses[self.calls]
        self.calls += 1
        return response


class TransportTests(unittest.TestCase):
    def test_classifies_cloudflare_1010_access_denial_from_fixture(self) -> None:
        fixture = json.loads(
            Path("tests/fixtures/synthetic/cloudflare-1010-access-denied-synthetic.json").read_text(
                encoding="utf-8"
            )
        )
        response = HttpResponse(
            status_code=fixture["status"],
            headers=fixture["headers"],
            body_text=fixture["body_text"],
            body_truncated=fixture["body_truncated"],
            body_bytes_captured=fixture["body_bytes_captured"],
        )
        self.assertEqual(classify_response(response), "client_signature_blocked")

    def test_classifies_cloudflare_1015_html(self) -> None:
        fixture = Path("tests/fixtures/synthetic/cloudflare-1015-synthetic.html").read_text(encoding="utf-8")
        response = HttpResponse(status_code=200, headers={}, body_text=fixture)
        self.assertEqual(classify_response(response), "rate_limited")

    def test_retry_after_enforced_without_real_sleep(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            store = ProbeCheckpointStore(path=Path(tmp_dir) / "checkpoint.json")
            clock = FakeClock(start=1_000.0)
            config = TransportConfig(
                cooldown_schedule_seconds=(60,),
                jitter_ratio=0.0,
                max_rate_limit_retries=1,
            )
            orchestrator = RequestOrchestrator(
                checkpoint=store,
                config=config,
                now_fn=clock.now,
                sleep_fn=clock.sleep,
                random_fn=lambda: 0.0,
            )
            responses = [
                HttpResponse(status_code=429, headers={"Retry-After": "5"}, body_text=""),
                HttpResponse(status_code=200, headers={}, body_text="<html>ok</html>"),
            ]
            client = FakeClient(responses=responses)
            result = orchestrator.execute_single_request(
                url="https://armory.warmane.com/character/Aikka/Onyxia/summary",
                client=client,
            )

            self.assertEqual(result.status, "success")
            self.assertEqual(result.attempts, 2)
            self.assertIn(60.0, clock.sleeps)

    def test_redirect_is_classified_and_not_retried(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            store = ProbeCheckpointStore(path=Path(tmp_dir) / "checkpoint.json")
            clock = FakeClock(start=1_000.0)
            config = TransportConfig(
                max_rate_limit_retries=0,
                max_transient_retries=0,
                jitter_ratio=0.0,
            )
            orchestrator = RequestOrchestrator(
                checkpoint=store,
                config=config,
                now_fn=clock.now,
                sleep_fn=clock.sleep,
                random_fn=lambda: 0.0,
            )
            client = FakeClient(
                [HttpResponse(status_code=302, headers={"Location": "https://example.com"}, body_text="redirect")]
            )
            result = orchestrator.execute_single_request(
                url="https://armory.warmane.com/character/Aikka/Onyxia/summary",
                client=client,
            )
            self.assertEqual(result.status, "failed_redirect")
            self.assertEqual(result.attempts, 1)
            self.assertEqual(client.calls, 1)

    def test_rate_limit_sets_cooldown_even_without_retry(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            store = ProbeCheckpointStore(path=Path(tmp_dir) / "checkpoint.json")
            clock = FakeClock(start=1_000.0)
            config = TransportConfig(
                max_rate_limit_retries=0,
                max_transient_retries=0,
                cooldown_schedule_seconds=(60,),
                jitter_ratio=0.0,
            )
            orchestrator = RequestOrchestrator(
                checkpoint=store,
                config=config,
                now_fn=clock.now,
                sleep_fn=clock.sleep,
                random_fn=lambda: 0.0,
            )
            client = FakeClient([HttpResponse(status_code=429, headers={"Retry-After": "5"}, body_text="")])
            result = orchestrator.execute_single_request(
                url="https://armory.warmane.com/character/Aikka/Onyxia/summary",
                client=client,
            )
            self.assertEqual(result.status, "failed_rate_limited")
            self.assertEqual(result.attempts, 1)
            self.assertEqual(client.calls, 1)
            cooldown_until = store.get_cooldown_until("armory.warmane.com")
            self.assertEqual(cooldown_until, 1060.0)

    def test_completed_request_not_repeated_after_restart(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "checkpoint.json"
            config = TransportConfig(jitter_ratio=0.0)
            clock = FakeClock(start=2_000.0)
            first_store = ProbeCheckpointStore(path=path)
            first = RequestOrchestrator(
                checkpoint=first_store,
                config=config,
                now_fn=clock.now,
                sleep_fn=clock.sleep,
                random_fn=lambda: 0.0,
            )
            first_client = FakeClient([HttpResponse(status_code=200, headers={}, body_text="<html>ok</html>")])
            first_result = first.execute_single_request(
                url="https://armory.warmane.com/character/Aikka/Onyxia/summary",
                client=first_client,
            )
            self.assertEqual(first_result.status, "success")
            self.assertEqual(first_client.calls, 1)

            second_store = ProbeCheckpointStore(path=path)
            second = RequestOrchestrator(
                checkpoint=second_store,
                config=config,
                now_fn=clock.now,
                sleep_fn=clock.sleep,
                random_fn=lambda: 0.0,
            )
            second_client = FakeClient([HttpResponse(status_code=500, headers={}, body_text="boom")])
            second_result = second.execute_single_request(
                url="https://armory.warmane.com/character/Aikka/Onyxia/summary",
                client=second_client,
            )
            self.assertEqual(second_result.status, "skipped_completed")
            self.assertEqual(second_client.calls, 0)

    def test_1010_block_is_non_retryable_and_not_rate_limited(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            store = ProbeCheckpointStore(path=Path(tmp_dir) / "checkpoint.json")
            clock = FakeClock(start=1_000.0)
            config = TransportConfig(
                max_rate_limit_retries=3,
                max_transient_retries=2,
                cooldown_schedule_seconds=(60,),
                jitter_ratio=0.0,
            )
            orchestrator = RequestOrchestrator(
                checkpoint=store,
                config=config,
                now_fn=clock.now,
                sleep_fn=clock.sleep,
                random_fn=lambda: 0.0,
            )
            client = FakeClient(
                [
                    HttpResponse(
                        status_code=403,
                        headers={"Content-Type": "text/plain; charset=UTF-8"},
                        body_text="error code: 1010\n",
                    )
                ]
            )
            result = orchestrator.execute_single_request(
                url="https://armory.warmane.com/character/Aikka/Onyxia/summary",
                client=client,
            )
            self.assertEqual(result.status, "failed_client_signature_blocked")
            self.assertEqual(result.classification, "client_signature_blocked")
            self.assertEqual(result.attempts, 1)
            self.assertEqual(client.calls, 1)
            self.assertIsNone(store.get_cooldown_until("armory.warmane.com"))


if __name__ == "__main__":
    unittest.main()
