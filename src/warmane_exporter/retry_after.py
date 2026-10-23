from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime


def parse_retry_after_seconds(value: str | None, now_utc: datetime) -> int | None:
    if value is None:
        return None

    raw = value.strip()
    if not raw:
        return None

    if raw.isdigit():
        return max(0, int(raw))

    parsed = parsedate_to_datetime(raw)
    if parsed is None:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    seconds = int((parsed - now_utc).total_seconds())
    return max(0, seconds)
