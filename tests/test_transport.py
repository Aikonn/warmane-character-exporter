from pathlib import Path
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from tempfile import TemporaryDirectory
import json
import unittest
import os
from unittest import mock

from warmane_exporter import progress
from warmane_exporter.checkpoint import ProbeCheckpointStore
from warmane_exporter.http_client import HttpResponse
from warmane_exporter.timing import TimingLog, activate
from warmane_exporter.transport import (
    RequestOrchestrator,
    StopRequested,
    TransportConfig,
    classify_response,
    reset_run_pacing,
)


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
    def setUp(self) -> None:
        reset_run_pacing()

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

    def test_classifies_access_denial_content_even_with_success_http_status(self) -> None:
        response = HttpResponse(status_code=200, headers={}, body_text="Error code: 1010")
        self.assertEqual(classify_response(response), "client_signature_blocked")

    def test_403_block_marker_wins_over_rate_limit_marker(self) -> None:
        response = HttpResponse(
            status_code=403,
            headers={},
            body_text="error code: 1010; too many requests",
        )
        self.assertEqual(classify_response(response), "client_signature_blocked")

    def test_200_armory_text_with_access_denied_is_success(self) -> None:
        body = (
            '<html><body><div id="character-sheet">'
            "Guild name: Access Denied"
            "</div></body></html>"
        )
        response = HttpResponse(status_code=200, headers={}, body_text=body)
        self.assertEqual(classify_response(response), "success")

    def test_200_cloudflare_1010_page_with_armory_markup_is_success(self) -> None:
        body = (
            '<html><body><div id="character-sheet">'
            "error code: 1010 " + ("x" * 2048) + "</div></body></html>"
        )
        response = HttpResponse(status_code=200, headers={}, body_text=body)
        self.assertEqual(classify_response(response), "success")

    def test_truncated_1010_body_with_armory_markup_is_not_treated_as_short(self) -> None:
        body = '<html><body><div id="character-sheet">error code: 1010</div></body></html>'
        response = HttpResponse(
            status_code=200,
            headers={},
            body_text=body,
            body_truncated=True,
            body_bytes_captured=len(body.encode("utf-8")),
        )
        self.assertEqual(classify_response(response), "success")

    def test_200_cloudflare_1010_page_without_armory_markup_is_blocked(self) -> None:
        body = "<html><body>error code: 1010 " + ("x" * 2048) + "</body></html>"
        response = HttpResponse(status_code=200, headers={}, body_text=body)
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
            self.assertGreaterEqual(sum(clock.sleeps), 60.0)

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

    def test_adaptive_spacing_is_shared_across_characters_and_resets_per_run(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            clock = FakeClock(start=1_000.0)
            pacing = reset_run_pacing()
            config = TransportConfig(cooldown_schedule_seconds=(3,), jitter_ratio=0.0)

            def orchestrator(index: int) -> RequestOrchestrator:
                return RequestOrchestrator(
                    checkpoint=ProbeCheckpointStore(path=Path(tmp_dir) / f"checkpoint-{index}.json"),
                    config=config,
                    now_fn=clock.now,
                    sleep_fn=clock.sleep,
                    random_fn=lambda: 0.0,
                    skip_completed=False,
                )

            first_character = orchestrator(1)
            first_result = first_character.execute_single_request(
                "https://armory.warmane.com/character/Alice/Onyxia/summary",
                FakeClient([
                    HttpResponse(429, {}, "too many requests"),
                    HttpResponse(200, {}, "ok"),
                ]),
            )
            self.assertEqual(first_result.status, "success")
            self.assertEqual((pacing.rate_limit_events, pacing.spacing_seconds), (1, 3.0))
            first_wait_count = len(clock.sleeps)

            second_character = orchestrator(2)
            for index in range(3):
                result = second_character.execute_single_request(
                    f"https://armory.warmane.com/character/Bob/Onyxia/talents?attempt={index}",
                    FakeClient([
                        HttpResponse(429, {}, "too many requests"),
                        HttpResponse(200, {}, "ok"),
                    ]),
                )
                self.assertEqual(result.status, "success")
                if index == 0:
                    self.assertEqual(clock.sleeps[first_wait_count:first_wait_count + 3], [1.0] * 3)
            self.assertEqual((pacing.rate_limit_events, pacing.spacing_seconds), (4, 5.0))

            clock.sleeps.clear()
            result = second_character.execute_single_request(
                "https://armory.warmane.com/character/Bob/Onyxia/reputation",
                FakeClient([HttpResponse(200, {}, "ok")]),
            )
            self.assertEqual(result.status, "success")
            self.assertGreaterEqual(sum(clock.sleeps), 5.0)

            next_run = reset_run_pacing()
            self.assertEqual((next_run.rate_limit_events, next_run.spacing_seconds), (0, 1.0))

    def test_long_rate_limit_wait_reports_progress_and_logs_one_event(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            reset_run_pacing()
            clock = FakeClock(start=1_000.0)
            orchestrator = RequestOrchestrator(
                checkpoint=ProbeCheckpointStore(path=Path(tmp_dir) / "checkpoint.json"),
                config=TransportConfig(cooldown_schedule_seconds=(12,), jitter_ratio=0.0),
                now_fn=clock.now,
                sleep_fn=clock.sleep,
                random_fn=lambda: 0.0,
                skip_completed=False,
            )
            stdout = StringIO()
            stderr = StringIO()
            with (
                mock.patch.dict(os.environ, {"WARMANE_PROGRESS": "1"}),
                redirect_stdout(stdout),
                redirect_stderr(stderr),
                activate(TimingLog(Path(tmp_dir))),
            ):
                progress.start(4, "Starting")
                result = orchestrator.execute_single_request(
                    "https://armory.warmane.com/character/Alice/Onyxia/summary",
                    FakeClient([
                        HttpResponse(429, {}, "too many requests"),
                        HttpResponse(200, {}, "ok"),
                    ]),
                )

            self.assertEqual(result.status, "success")
            progress_lines = [
                line for line in stdout.getvalue().splitlines() if line.startswith("PROGRESS|")
            ]
            self.assertEqual(
                [line.split("|", 2)[1] for line in progress_lines],
                ["0", "0", "0", "0"],
            )
            self.assertIn("Armory rate limit: waiting 12 s", progress_lines[1])
            self.assertIn("Armory rate limit: waiting 7 s", progress_lines[2])
            self.assertIn("Armory rate limit: waiting 2 s", progress_lines[3])
            event = "rate limit: summary; wait 12 s; spacing now 3 s"
            self.assertEqual(stderr.getvalue().count(event), 1)
            timing_lines = list(Path(tmp_dir).glob("timing-*.log"))
            self.assertEqual(len(timing_lines), 1)
            self.assertEqual(timing_lines[0].read_text(encoding="utf-8").count(event), 1)

    def test_stop_request_interrupts_a_cooldown_wait(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            stop_file = Path(tmp_dir) / "stop-request"
            clock = FakeClock(start=1_000.0)

            def request_stop(seconds: float) -> None:
                clock.sleep(seconds)
                stop_file.write_text("stop", encoding="utf-8")

            pacing = reset_run_pacing(stop_file)
            orchestrator = RequestOrchestrator(
                checkpoint=ProbeCheckpointStore(path=Path(tmp_dir) / "checkpoint.json"),
                config=TransportConfig(cooldown_schedule_seconds=(60,), jitter_ratio=0.0),
                now_fn=clock.now,
                sleep_fn=request_stop,
                random_fn=lambda: 0.0,
                skip_completed=False,
            )
            client = FakeClient([HttpResponse(429, {}, "too many requests")])
            with self.assertRaises(StopRequested):
                orchestrator.execute_single_request(
                    "https://armory.warmane.com/character/Alice/Onyxia/summary",
                    client,
                )
            self.assertEqual(client.calls, 1)
            self.assertEqual(pacing.rate_limit_events, 1)


if __name__ == "__main__":
    unittest.main()
