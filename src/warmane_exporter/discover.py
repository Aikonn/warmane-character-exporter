"""Fetch one character page once and keep the raw HTML for offline analysis.

python -m warmane_exporter.discover NAME REALM VIEW   (VIEW: statistics, mounts-and-companions, reputation, ...)

One live request (cached for 24 hours); the raw page goes to .warmane-cache/discovery/.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .budget import DEFAULT_INTERVAL_SECONDS, BudgetExhausted, budgeted_client
from .cache import ResponseCache
from .checkpoint import ProbeCheckpointStore
from .http_client import UrllibHttpClient
from .snapshot import character_page_url, fetch_validated
from .transport import RequestOrchestrator, TransportConfig

KNOWN_VIEWS = ("statistics", "achievements", "mounts-and-companions", "reputation", "match-history", "talents", "profile")


def _validate(text: str) -> dict:
    if "<html" not in text.lower() and "<div" not in text.lower():
        raise ValueError("Body does not look like an HTML page")
    return {"length": len(text)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("name")
    parser.add_argument("realm")
    parser.add_argument("view", choices=KNOWN_VIEWS)
    parser.add_argument("--cache-dir", default=".warmane-cache")
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args(argv)

    cache_dir = Path(args.cache_dir)
    cache = ResponseCache(cache_dir / "responses.sqlite")
    orchestrator = RequestOrchestrator(
        checkpoint=ProbeCheckpointStore(path=cache_dir / "transport-state.json"),
        config=TransportConfig(min_request_interval_seconds=DEFAULT_INTERVAL_SECONDS),
        skip_completed=False,
    )
    try:
        url = character_page_url(args.name, args.realm, args.view)
        result = fetch_validated(url, f"page-{args.view}", _validate, cache, orchestrator, budgeted_client(cache_dir),
                                 refresh=args.refresh, max_age_seconds=24 * 3600,
                                 reject_dir=cache_dir / "rejected")
        entry = cache.get(f"page-{args.view}|{url}")
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    finally:
        cache.close()
    print(f"{args.view}: {result.status} ({result.origin}) {result.detail}")
    if result.status != "ok" or entry is None:
        return 1
    out_dir = cache_dir / "discovery"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{args.name.lower()}-{args.realm.lower()}-{args.view}.html"
    out.write_text(entry.body, encoding="utf-8")
    print(f"saved: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
