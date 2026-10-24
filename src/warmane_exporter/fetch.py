"""Fetch a character's JSON summary with cache, throttling and provenance.

python -m warmane_exporter.fetch NAME REALM [--refresh] [--offline] [--allow-stale]
Makes at most one live request per run (none when the cache is fresh or --offline).
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from time import time
from typing import Callable

from .budget import DEFAULT_INTERVAL_SECONDS, BudgetExhausted, budgeted_client
from .cache import ResponseCache
from .checkpoint import ProbeCheckpointStore
from .http_client import UrllibHttpClient
from .transport import RequestOrchestrator
from .warmane_api import ApiError, api_summary_url, parse_api_summary

CHARACTER_MAX_AGE_SECONDS = 15 * 60
SOURCE = "warmane-json-summary"


@dataclass
class FetchResult:
    status: str  # ok | offline_miss | failed
    data: dict[str, object] | None
    origin: str  # network | cache | stale-cache | none
    observed_at: float | None
    detail: str


def fetch_character_summary(
    name: str,
    realm: str,
    cache: ResponseCache,
    orchestrator: RequestOrchestrator,
    client,
    now_fn: Callable[[], float] = time,
    refresh: bool = False,
    offline: bool = False,
    allow_stale: bool = False,
    max_age_seconds: float = CHARACTER_MAX_AGE_SECONDS,
) -> FetchResult:
    url = api_summary_url(name, realm)
    key = f"{SOURCE}|{url}"
    entry = cache.get(key)
    now = now_fn()

    if entry is not None and not refresh and entry.age_seconds(now) <= max_age_seconds:
        return FetchResult("ok", parse_api_summary(entry.body), "cache", entry.fetched_at, "Fresh cache entry used.")

    if offline:
        if entry is not None:
            return FetchResult(
                "ok", parse_api_summary(entry.body), "stale-cache", entry.fetched_at,
                f"Offline mode: cached data is {int(entry.age_seconds(now))} s old.",
            )
        return FetchResult("offline_miss", None, "none", None, "Offline mode and nothing cached.")

    result = orchestrator.execute_single_request(url=url, client=client)
    if result.status == "success":
        try:
            parsed = parse_api_summary(result.body_text)
        except ApiError as exc:
            return _fallback(entry, now, allow_stale, f"Response rejected, cache not updated: {exc}")
        cache.put(key, SOURCE, result.body_text, now_fn())
        return FetchResult("ok", parsed, "network", now_fn(), "Fetched live.")
    return _fallback(entry, now, allow_stale, f"Request failed: {result.status} ({result.detail})")


def _fallback(entry, now: float, allow_stale: bool, detail: str) -> FetchResult:
    if entry is not None and allow_stale:
        return FetchResult(
            "ok", parse_api_summary(entry.body), "stale-cache", entry.fetched_at,
            f"{detail} Using stale cache ({int(entry.age_seconds(now))} s old).",
        )
    return FetchResult("failed", None, "none", None, detail)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("name")
    parser.add_argument("realm")
    parser.add_argument("--cache-dir", default=".warmane-cache")
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--allow-stale", action="store_true")
    args = parser.parse_args(argv)

    cache_dir = Path(args.cache_dir)
    cache = ResponseCache(cache_dir / "responses.sqlite")
    checkpoint = ProbeCheckpointStore(path=cache_dir / "transport-state.json")
    orchestrator = RequestOrchestrator(checkpoint=checkpoint, skip_completed=False)
    try:
        result = fetch_character_summary(
            args.name, args.realm, cache, orchestrator, budgeted_client(cache_dir),
            refresh=args.refresh, offline=args.offline, allow_stale=args.allow_stale,
        )
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    finally:
        cache.close()

    out = {
        "status": result.status,
        "origin": result.origin,
        "observed_at": result.observed_at,
        "detail": result.detail,
        "character": result.data,
    }
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0 if result.status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
