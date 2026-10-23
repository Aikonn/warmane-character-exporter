from datetime import datetime, timedelta, timezone
import unittest

from warmane_exporter.retry_after import parse_retry_after_seconds


class RetryAfterTests(unittest.TestCase):
    def test_parses_integer_seconds(self) -> None:
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.assertEqual(parse_retry_after_seconds("120", now), 120)

    def test_parses_http_date(self) -> None:
        now = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        target = now + timedelta(seconds=75)
        header = target.strftime("%a, %d %b %Y %H:%M:%S GMT")
        self.assertEqual(parse_retry_after_seconds(header, now), 75)

    def test_past_http_date_returns_zero(self) -> None:
        now = datetime(2026, 1, 1, 0, 0, 10, tzinfo=timezone.utc)
        header = "Thu, 01 Jan 2026 00:00:05 GMT"
        self.assertEqual(parse_retry_after_seconds(header, now), 0)


if __name__ == "__main__":
    unittest.main()
