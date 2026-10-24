"""Daily live-request budget shared by every command that talks to the network.

The ledger is a small JSON file (.warmane-cache/budget.json). Each real HTTP request counts one,
whatever the command. When the daily limit is reached the client raises BudgetExhausted before
sending anything, so a run stops cleanly and can be continued after the owner raises the limit.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

DEFAULT_DAILY_LIMIT = 500
DEFAULT_INTERVAL_SECONDS = 3.0


class BudgetExhausted(ValueError):
    pass


class BudgetLedger:
    def __init__(self, path: Path, daily_limit: int = DEFAULT_DAILY_LIMIT, today=date.today):
        self.path, self.daily_limit, self._today = Path(path), daily_limit, today

    def _read(self) -> dict[str, Any]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
        if data.get("date") != self._today().isoformat():
            data = {"date": self._today().isoformat(), "used": 0, "limit": None}
        return data

    @property
    def limit(self) -> int:
        override = self._read().get("limit")
        return int(override) if override else self.daily_limit

    @property
    def used(self) -> int:
        return int(self._read()["used"])

    @property
    def remaining(self) -> int:
        return max(self.limit - self.used, 0)

    def set_limit(self, limit: int) -> None:
        data = self._read()
        data["limit"] = int(limit)
        self._write(data)

    def charge(self) -> None:
        data = self._read()
        limit = int(data.get("limit") or self.daily_limit)
        if data["used"] >= limit:
            raise BudgetExhausted(
                f"Daily live-request budget used up ({data['used']} of {limit}). "
                "Raise it with: python -m warmane_exporter.budget --set N")
        data["used"] += 1
        self._write(data)

    def _write(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")


class BudgetedHttpClient:
    """Wraps an HTTP client; charges the ledger before every request."""

    def __init__(self, inner, ledger: BudgetLedger):
        self._inner, self._ledger = inner, ledger

    def get(self, *args, **kwargs):
        self._ledger.charge()
        return self._inner.get(*args, **kwargs)

    def post_form(self, *args, **kwargs):
        self._ledger.charge()
        return self._inner.post_form(*args, **kwargs)


def budgeted_client(cache_dir: Path):
    """Real HTTP client whose every request is counted against the daily budget."""
    from .http_client import UrllibHttpClient

    return BudgetedHttpClient(UrllibHttpClient(), BudgetLedger(Path(cache_dir) / "budget.json"))


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Show or change today's live-request budget.")
    parser.add_argument("--cache-dir", default=".warmane-cache")
    parser.add_argument("--set", type=int, default=None, metavar="N", help="set today's limit")
    args = parser.parse_args(argv)
    ledger = BudgetLedger(Path(args.cache_dir) / "budget.json")
    if args.set is not None:
        ledger.set_limit(args.set)
    print(f"used {ledger.used} of {ledger.limit} today; remaining {ledger.remaining}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
