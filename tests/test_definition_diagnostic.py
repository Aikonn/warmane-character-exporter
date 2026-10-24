from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from warmane_exporter.definition_diagnostic import validate_definition_url, _truncate_body_excerpt
from warmane_exporter.checkpoint import ProbeCheckpointStore
from warmane_exporter.http_client import HttpResponse
from warmane_exporter.transport import RequestOrchestrator, TransportConfig


class DefinitionUrlValidationTests(unittest.TestCase):
    def test_rejects_http_scheme(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            validate_definition_url("http://wotlk.cavernoftime.com/spell=14769")
        self.assertIn("https", str(ctx.exception))

    def test_rejects_non_approved_host(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            validate_definition_url("https://example.com/spell=14769")
        self.assertIn("Unsupported host", str(ctx.exception))

    def test_rejects_credentials(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            validate_definition_url("https://user:pass@wotlk.cavernoftime.com/spell=14769")
        self.assertIn("Credentials", str(ctx.exception))

    def test_rejects_non_default_port(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            validate_definition_url("https://wotlk.cavernoftime.com:8443/spell=14769")
        self.assertIn("Non-default ports", str(ctx.exception))

    def test_rejects_fragment(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            validate_definition_url("https://wotlk.cavernoftime.com/spell=14769#section")
        self.assertIn("fragments", str(ctx.exception))

    def test_rejects_control_characters_in_path(self) -> None:
        # Control characters in the middle of the path value get caught
        with self.assertRaises(ValueError) as ctx:
            validate_definition_url("https://wotlk.cavernoftime.com/spell=1\x004769")
        self.assertIn("control characters", str(ctx.exception))

    def test_rejects_trailing_newline(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            validate_definition_url("https://wotlk.cavernoftime.com/spell=14769\n")
        self.assertIn("whitespace or control", str(ctx.exception))

    def test_rejects_trailing_tab(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            validate_definition_url("https://wotlk.cavernoftime.com/spell=14769\t")
        self.assertIn("whitespace or control", str(ctx.exception))

    def test_rejects_embedded_tab(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            validate_definition_url("https://wotlk.cavernoftime.com/spe\tll=14769")
        self.assertIn("whitespace or control", str(ctx.exception))

    def test_rejects_embedded_newline(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            validate_definition_url("https://wotlk.cavernoftime.com/spe\nll=14769")
        self.assertIn("whitespace or control", str(ctx.exception))

    def test_rejects_leading_space(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            validate_definition_url(" https://wotlk.cavernoftime.com/spell=14769")
        self.assertIn("whitespace or control", str(ctx.exception))

    def test_rejects_embedded_nul(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            validate_definition_url("https://wotlk.cavernoftime.com/spell=1\x004769")
        self.assertIn("control characters", str(ctx.exception))

    def test_rejects_embedded_del(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            validate_definition_url("https://wotlk.cavernoftime.com/spell=1\x7f4769")
        self.assertIn("control characters", str(ctx.exception))

    def test_accepts_cavernoftime_spell_basic(self) -> None:
        url = validate_definition_url("https://wotlk.cavernoftime.com/spell=14769")
        self.assertEqual(url, "https://wotlk.cavernoftime.com/spell=14769")

    def test_accepts_cavernoftime_spell_with_power_true(self) -> None:
        url = validate_definition_url("https://wotlk.cavernoftime.com/spell=14769&power=true")
        self.assertEqual(url, "https://wotlk.cavernoftime.com/spell=14769&power=true")

    def test_accepts_cavernoftime_item_basic(self) -> None:
        url = validate_definition_url("https://wotlk.cavernoftime.com/item=51178")
        self.assertEqual(url, "https://wotlk.cavernoftime.com/item=51178")

    def test_accepts_cavernoftime_item_with_power_true(self) -> None:
        url = validate_definition_url("https://wotlk.cavernoftime.com/item=51178&power=true")
        self.assertEqual(url, "https://wotlk.cavernoftime.com/item=51178&power=true")

    def test_accepts_cavernoftime_item_with_ench(self) -> None:
        url = validate_definition_url("https://wotlk.cavernoftime.com/item=51178&power=true&ench=3820")
        self.assertEqual(url, "https://wotlk.cavernoftime.com/item=51178&power=true&ench=3820")

    def test_accepts_cavernoftime_item_with_gems(self) -> None:
        url = validate_definition_url("https://wotlk.cavernoftime.com/item=51178&power=true&gems=3627:3879")
        self.assertEqual(url, "https://wotlk.cavernoftime.com/item=51178&power=true&gems=3627:3879")

    def test_accepts_cavernoftime_item_with_ench_and_gems(self) -> None:
        url = validate_definition_url("https://wotlk.cavernoftime.com/item=51178&power=true&ench=3820&gems=3627:3879")
        self.assertEqual(url, "https://wotlk.cavernoftime.com/item=51178&power=true&ench=3820&gems=3627:3879")

    def test_accepts_evowow_enchantment(self) -> None:
        url = validate_definition_url("https://wotlk.evowow.com/?enchantment=3820")
        self.assertEqual(url, "https://wotlk.evowow.com/?enchantment=3820")

    def test_rejects_cavernoftime_invalid_spell_form(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            validate_definition_url("https://wotlk.cavernoftime.com/spell=abc")
        self.assertIn("Unsupported", str(ctx.exception))

    def test_rejects_cavernoftime_unknown_parameter(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            validate_definition_url("https://wotlk.cavernoftime.com/spell=14769&unknown=value")
        self.assertIn("Unsupported", str(ctx.exception))

    def test_rejects_evowow_invalid_form(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            validate_definition_url("https://wotlk.evowow.com/?enchantment=abc")
        self.assertIn("Unsupported", str(ctx.exception))

    def test_rejects_scheme_less_url(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            validate_definition_url("wotlk.cavernoftime.com/spell=14769")
        self.assertIn("explicit https://", str(ctx.exception))

    def test_rejects_cavernoftime_zero_spell_id(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            validate_definition_url("https://wotlk.cavernoftime.com/spell=0")
        self.assertIn("Unsupported", str(ctx.exception))

    def test_rejects_cavernoftime_zero_item_id(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            validate_definition_url("https://wotlk.cavernoftime.com/item=0")
        self.assertIn("Unsupported", str(ctx.exception))

    def test_rejects_cavernoftime_zero_ench_id(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            validate_definition_url("https://wotlk.cavernoftime.com/item=51178&power=true&ench=0")
        self.assertIn("Unsupported", str(ctx.exception))

    def test_rejects_evowow_zero_enchantment_id(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            validate_definition_url("https://wotlk.evowow.com/?enchantment=0")
        self.assertIn("Unsupported", str(ctx.exception))

    def test_rejects_semicolon_suffix_parameter(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            validate_definition_url("https://wotlk.cavernoftime.com/spell=14769;foo=bar")
        self.assertIn("parameters", str(ctx.exception))
        with self.assertRaises(ValueError):
            validate_definition_url("")

    def test_rejects_whitespace_only_url(self) -> None:
        with self.assertRaises(ValueError):
            validate_definition_url("   ")

    def test_rejects_url_without_path_or_query(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            validate_definition_url("https://wotlk.cavernoftime.com")
        self.assertIn("must include a path or query", str(ctx.exception))

    def test_accepts_cavernoftime_gem_code_zero(self) -> None:
        # Zero is a valid nonnegative integer
        url = validate_definition_url("https://wotlk.cavernoftime.com/item=51178&power=true&gems=0")
        self.assertEqual(url, "https://wotlk.cavernoftime.com/item=51178&power=true&gems=0")

    def test_accepts_cavernoftime_gem_code_zero_in_pair(self) -> None:
        url = validate_definition_url("https://wotlk.cavernoftime.com/item=51178&power=true&gems=0:3627")
        self.assertEqual(url, "https://wotlk.cavernoftime.com/item=51178&power=true&gems=0:3627")

    def test_accepts_cavernoftime_gem_code_nonzero_first(self) -> None:
        url = validate_definition_url("https://wotlk.cavernoftime.com/item=51178&power=true&gems=3627:0")
        self.assertEqual(url, "https://wotlk.cavernoftime.com/item=51178&power=true&gems=3627:0")

    def test_accepts_cavernoftime_gem_code_all_zeros(self) -> None:
        url = validate_definition_url("https://wotlk.cavernoftime.com/item=51178&power=true&gems=0:0")
        self.assertEqual(url, "https://wotlk.cavernoftime.com/item=51178&power=true&gems=0:0")

    def test_rejects_non_ascii_digits_in_ids_and_gems(self) -> None:
        """Parameterized test: reject non-ASCII digit characters."""
        # Test cases: (URL, description)
        cases = [
            ("https://wotlk.cavernoftime.com/spell=１４７６９", "fullwidth digit in spell ID"),  # U+FF11 U+FF14 ... (fullwidth)
            ("https://wotlk.cavernoftime.com/item=３６２７", "fullwidth digits in gem code"),  # fullwidth digits
        ]
        for url, description in cases:
            with self.subTest(description=description, url=url):
                with self.assertRaises(ValueError):
                    validate_definition_url(url)


class BodyExcerptTests(unittest.TestCase):
    def test_excerpt_short_body(self) -> None:
        body = "short"
        excerpt = _truncate_body_excerpt(body, max_chars=500)
        self.assertEqual(excerpt, "short")

    def test_excerpt_exactly_limit(self) -> None:
        body = "x" * 500
        excerpt = _truncate_body_excerpt(body, max_chars=500)
        self.assertEqual(excerpt, body)
        self.assertEqual(len(excerpt), 500)

    def test_excerpt_exceeds_limit(self) -> None:
        body = "x" * 600
        excerpt = _truncate_body_excerpt(body, max_chars=500)
        self.assertEqual(excerpt, "x" * 500)
        self.assertEqual(len(excerpt), 500)

    def test_excerpt_empty(self) -> None:
        body = ""
        excerpt = _truncate_body_excerpt(body, max_chars=500)
        self.assertEqual(excerpt, "")


class DefinitionDiagnosticOfflineTests(unittest.TestCase):
    def test_offline_validation_error_produces_output(self) -> None:
        import subprocess
        import sys
        result = subprocess.run(
            [sys.executable, "-m", "warmane_exporter.definition_diagnostic", "http://invalid.com/path"],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent.parent.parent),
            env={"PYTHONPATH": str(Path(__file__).parent.parent / "src")},
        )
        self.assertEqual(result.returncode, 0)
        output = json.loads(result.stdout)
        self.assertEqual(output["mode"], "offline_validation")
        self.assertIn("validation_error", output)

    def test_offline_plan_zero_network_calls(self) -> None:
        import subprocess
        import sys
        result = subprocess.run(
            [sys.executable, "-m", "warmane_exporter.definition_diagnostic", "https://wotlk.cavernoftime.com/spell=14769"],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent.parent.parent),
            env={"PYTHONPATH": str(Path(__file__).parent.parent / "src")},
        )
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        output = json.loads(result.stdout)
        self.assertEqual(output["mode"], "offline_plan")
        self.assertNotIn("result", output)



class FakeClient:
    def __init__(self, responses: list) -> None:
        self.responses = responses
        self.calls = 0

    def get(self, url: str, connect_timeout: float, read_timeout: float):
        if self.calls >= len(self.responses):
            raise AssertionError("No more fake responses configured.")
        response = self.responses[self.calls]
        self.calls += 1
        return response


class DefinitionDiagnosticLiveTests(unittest.TestCase):
    def test_live_once_success_includes_body_excerpt(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            store = ProbeCheckpointStore(path=Path(tmp_dir) / "checkpoint.json")
            config = TransportConfig(
                max_rate_limit_retries=0,
                max_transient_retries=0,
            )
            orchestrator = RequestOrchestrator(
                checkpoint=store,
                config=config,
            )
            response = HttpResponse(
                status_code=200,
                headers={"Content-Type": "text/html"},
                body_text="<html>test content</html>",
            )
            client = FakeClient(responses=[response])
            result = orchestrator.execute_single_request(
                url="https://wotlk.cavernoftime.com/spell=14769",
                client=client,
            )
            self.assertEqual(result.status, "success")
            self.assertEqual(result.response_status, 200)
            self.assertEqual(client.calls, 1)

    def test_live_once_access_denial_no_retry(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            store = ProbeCheckpointStore(path=Path(tmp_dir) / "checkpoint.json")
            config = TransportConfig(
                max_rate_limit_retries=0,
                max_transient_retries=0,
            )
            orchestrator = RequestOrchestrator(
                checkpoint=store,
                config=config,
            )
            response = HttpResponse(
                status_code=403,
                headers={},
                body_text="error code: 1010",
            )
            client = FakeClient(responses=[response])
            result = orchestrator.execute_single_request(
                url="https://wotlk.cavernoftime.com/spell=14769",
                client=client,
            )
            self.assertEqual(result.status, "failed_client_signature_blocked")
            self.assertEqual(result.response_status, 403)
            self.assertEqual(client.calls, 1)

    def test_live_once_transient_error_no_retry(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            store = ProbeCheckpointStore(path=Path(tmp_dir) / "checkpoint.json")
            config = TransportConfig(
                max_rate_limit_retries=0,
                max_transient_retries=0,
            )
            orchestrator = RequestOrchestrator(
                checkpoint=store,
                config=config,
            )
            response = HttpResponse(
                status_code=500,
                headers={},
                body_text="internal server error",
            )
            client = FakeClient(responses=[response])
            result = orchestrator.execute_single_request(
                url="https://wotlk.cavernoftime.com/spell=14769",
                client=client,
            )
            self.assertEqual(result.classification, "transient_error")
            self.assertEqual(client.calls, 1)

    def test_live_once_rate_limit_no_retry(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            store = ProbeCheckpointStore(path=Path(tmp_dir) / "checkpoint.json")
            config = TransportConfig(
                max_rate_limit_retries=0,
                max_transient_retries=0,
            )
            orchestrator = RequestOrchestrator(
                checkpoint=store,
                config=config,
            )
            response = HttpResponse(
                status_code=429,
                headers={"Retry-After": "60"},
                body_text="too many requests",
            )
            client = FakeClient(responses=[response])
            result = orchestrator.execute_single_request(
                url="https://wotlk.cavernoftime.com/spell=14769",
                client=client,
            )
            self.assertEqual(result.classification, "rate_limited")
            self.assertEqual(client.calls, 1)

    def test_live_once_with_persisted_cooldown_blocks_request(self) -> None:
        from time import time
        with TemporaryDirectory() as tmp_dir:
            store = ProbeCheckpointStore(path=Path(tmp_dir) / "checkpoint.json")
            future_time = time() + 100  # 100 seconds in future
            store.set_cooldown_until("wotlk.cavernoftime.com", future_time)
            
            config = TransportConfig(
                max_rate_limit_retries=0,
                max_transient_retries=0,
            )
            
            sleeps = []
            def mock_sleep(seconds):
                sleeps.append(seconds)
            
            orchestrator = RequestOrchestrator(
                checkpoint=store,
                config=config,
                sleep_fn=mock_sleep,
            )
            response = HttpResponse(
                status_code=200,
                headers={},
                body_text="ok",
            )
            client = FakeClient(responses=[response])
            result = orchestrator.execute_single_request(
                url="https://wotlk.cavernoftime.com/spell=14769",
                client=client,
            )
            self.assertTrue(len(sleeps) > 0)

    def test_body_excerpt_truncated_response(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            store = ProbeCheckpointStore(path=Path(tmp_dir) / "checkpoint.json")
            config = TransportConfig(
                max_rate_limit_retries=0,
                max_transient_retries=0,
            )
            orchestrator = RequestOrchestrator(
                checkpoint=store,
                config=config,
            )
            large_body = "x" * 200000
            response = HttpResponse(
                status_code=200,
                headers={"Content-Type": "text/html"},
                body_text=large_body,
                body_truncated=True,
                body_bytes_captured=131072,
            )
            client = FakeClient(responses=[response])
            result = orchestrator.execute_single_request(
                url="https://wotlk.cavernoftime.com/spell=14769",
                client=client,
            )
            self.assertEqual(result.status, "success")
            self.assertEqual(result.body_truncated, True)
            excerpt = _truncate_body_excerpt(result.body_text, max_chars=500)
            self.assertLessEqual(len(excerpt), 500)

    def test_live_once_no_redirects_with_308(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            store = ProbeCheckpointStore(path=Path(tmp_dir) / "checkpoint.json")
            config = TransportConfig(
                max_rate_limit_retries=0,
                max_transient_retries=0,
            )
            orchestrator = RequestOrchestrator(
                checkpoint=store,
                config=config,
            )
            response = HttpResponse(
                status_code=308,
                headers={"Location": "https://example.com/"},
                body_text="",
            )
            client = FakeClient(responses=[response])
            result = orchestrator.execute_single_request(
                url="https://wotlk.cavernoftime.com/spell=14769",
                client=client,
            )
            self.assertEqual(result.classification, "redirect")
            self.assertEqual(client.calls, 1)


class DefinitionDiagnosticMainIntegrationTests(unittest.TestCase):
    """Integration tests invoking main() with patched argv and mocked HTTP."""

    def test_main_offline_default_zero_network_calls(self) -> None:
        """Offline default should make zero HTTP calls."""
        import sys
        from unittest.mock import patch
        from warmane_exporter.definition_diagnostic import main
        
        with TemporaryDirectory() as tmp_dir:
            checkpoint_path = Path(tmp_dir) / "checkpoint.json"
            with patch.object(sys, 'argv', [
                'definition_diagnostic',
                'https://wotlk.cavernoftime.com/spell=14769',
                '--checkpoint', str(checkpoint_path),
            ]):
                with patch('warmane_exporter.definition_diagnostic.UrllibHttpClient') as mock_client_class:
                    mock_client = mock_client_class.return_value
                    mock_client.get = lambda url, **kw: self.fail("HTTP client should not be called in offline mode")
                    
                    with patch('sys.stdout', new_callable=lambda: __import__('io').StringIO()) as mock_stdout:
                        with patch('builtins.print') as mock_print:
                            main()
                            # Verify print was called (output produced)
                            self.assertTrue(mock_print.called)

    def test_main_live_once_with_success_response_includes_excerpt(self) -> None:
        """Live-once with success should include body excerpt capped at 500 chars."""
        import sys
        from unittest.mock import patch, MagicMock
        from warmane_exporter.definition_diagnostic import main
        
        with TemporaryDirectory() as tmp_dir:
            checkpoint_path = Path(tmp_dir) / "checkpoint.json"
            
            # Mock the HTTP response with body larger than 500 chars
            body_text = "<html>" + "x" * 600 + "</html>"  # Total: 612 chars
            expected_excerpt = body_text[:500]  # First 500 characters
            mock_response = HttpResponse(
                status_code=200,
                headers={"Content-Type": "text/html"},
                body_text=body_text,
            )
            
            mock_client = MagicMock()
            mock_client.get.return_value = mock_response
            
            with patch.object(sys, 'argv', [
                'definition_diagnostic',
                'https://wotlk.cavernoftime.com/spell=14769',
                '--checkpoint', str(checkpoint_path),
                '--live-once',
            ]):
                with patch('warmane_exporter.definition_diagnostic.UrllibHttpClient', return_value=mock_client):
                    with patch('builtins.print') as mock_print:
                        main()
                        
                        # Verify exactly one HTTP call
                        self.assertEqual(mock_client.get.call_count, 1)
                        
                        # Extract the printed JSON output
                        self.assertTrue(mock_print.called)
                        printed_json = mock_print.call_args[0][0]
                        output = json.loads(printed_json)
                        
                        # Verify body excerpt is capped at 500 characters
                        self.assertIn("result", output)
                        self.assertIn("body_excerpt", output["result"])
                        excerpt = output["result"]["body_excerpt"]
                        self.assertLessEqual(len(excerpt), 500)
                        self.assertEqual(excerpt, expected_excerpt)

    def test_main_live_once_rate_limit_no_retry(self) -> None:
        """Live-once with rate limit (429) should make exactly one call, no retry."""
        import sys
        from unittest.mock import patch, MagicMock
        from warmane_exporter.definition_diagnostic import main
        
        with TemporaryDirectory() as tmp_dir:
            checkpoint_path = Path(tmp_dir) / "checkpoint.json"
            
            mock_response = HttpResponse(
                status_code=429,
                headers={"Retry-After": "60"},
                body_text="too many requests",
            )
            
            mock_client = MagicMock()
            mock_client.get.return_value = mock_response
            
            with patch.object(sys, 'argv', [
                'definition_diagnostic',
                'https://wotlk.cavernoftime.com/spell=14769',
                '--checkpoint', str(checkpoint_path),
                '--live-once',
            ]):
                with patch('warmane_exporter.definition_diagnostic.UrllibHttpClient', return_value=mock_client):
                    with patch('builtins.print') as mock_print:
                        main()
                        
                        # Verify exactly one HTTP call
                        self.assertEqual(mock_client.get.call_count, 1)
                        
                        printed_json = mock_print.call_args[0][0]
                        output = json.loads(printed_json)
                        self.assertEqual(output["mode"], "live_once")

    def test_main_live_once_transient_error_no_retry(self) -> None:
        """Live-once with transient error (500) should make exactly one call, no retry."""
        import sys
        from unittest.mock import patch, MagicMock
        from warmane_exporter.definition_diagnostic import main
        
        with TemporaryDirectory() as tmp_dir:
            checkpoint_path = Path(tmp_dir) / "checkpoint.json"
            
            mock_response = HttpResponse(
                status_code=500,
                headers={},
                body_text="internal server error",
            )
            
            mock_client = MagicMock()
            mock_client.get.return_value = mock_response
            
            with patch.object(sys, 'argv', [
                'definition_diagnostic',
                'https://wotlk.cavernoftime.com/spell=14769',
                '--checkpoint', str(checkpoint_path),
                '--live-once',
            ]):
                with patch('warmane_exporter.definition_diagnostic.UrllibHttpClient', return_value=mock_client):
                    with patch('builtins.print') as mock_print:
                        main()
                        
                        # Verify exactly one HTTP call
                        self.assertEqual(mock_client.get.call_count, 1)
                        
                        printed_json = mock_print.call_args[0][0]
                        output = json.loads(printed_json)
                        self.assertEqual(output["mode"], "live_once")

    def test_main_live_once_persisted_cooldown_blocks_request(self) -> None:
        """Live-once with existing cooldown should report blocked_by_cooldown and make zero HTTP calls."""
        import sys
        from time import time
        from unittest.mock import patch, MagicMock
        from warmane_exporter.definition_diagnostic import main
        
        with TemporaryDirectory() as tmp_dir:
            checkpoint_path = Path(tmp_dir) / "checkpoint.json"
            
            # Set up a persisted cooldown
            store = ProbeCheckpointStore(path=checkpoint_path)
            future_time = time() + 100
            store.set_cooldown_until("wotlk.cavernoftime.com", future_time)
            
            mock_client = MagicMock()
            mock_client.get.side_effect = AssertionError("HTTP client should not be called when cooldown is active")
            
            with patch.object(sys, 'argv', [
                'definition_diagnostic',
                'https://wotlk.cavernoftime.com/spell=14769',
                '--checkpoint', str(checkpoint_path),
                '--live-once',
            ]):
                with patch('warmane_exporter.definition_diagnostic.UrllibHttpClient', return_value=mock_client):
                    with patch('builtins.print') as mock_print:
                        main()
                        
                        # Verify zero HTTP calls
                        self.assertEqual(mock_client.get.call_count, 0)
                        
                        printed_json = mock_print.call_args[0][0]
                        output = json.loads(printed_json)
                        self.assertIn("result", output)
                        self.assertEqual(output["result"]["status"], "blocked_by_cooldown")


if __name__ == "__main__":
    unittest.main()
