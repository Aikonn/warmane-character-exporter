"""Build a character snapshot from the JSON summary, HTML summary and talents pages.

python -m warmane_exporter.snapshot NAME REALM [--refresh] [--offline] [--allow-stale] [--no-client]

Live requests: at most 3 (one per source), spaced by the transport interval (10 s here),
none when the cache is fresh or --offline. Each section succeeds or fails on its own and
carries its origin (network, cache, stale-cache) and observation time.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from time import time
from typing import Any, Callable
from urllib.parse import quote

from .budget import DEFAULT_INTERVAL_SECONDS, BudgetExhausted, budgeted_client
from .cache import ResponseCache
from .checkpoint import ProbeCheckpointStore
from .fetch import CHARACTER_MAX_AGE_SECONDS, FetchResult
from .http_client import UrllibHttpClient
from .identity import SUPPORTED_HOST, SUPPORTED_REALMS
from .summary_parser import parse_summary_capture_html
from .talents_parser import parse_talents_capture_html
from .transport import RequestOrchestrator, TransportConfig
from .warmane_api import api_summary_url, parse_api_summary

SNAPSHOT_SCHEMA = "character-snapshot/0"
SNAPSHOT_INTERVAL_SECONDS = DEFAULT_INTERVAL_SECONDS


def _validate_summary_html(text: str) -> dict[str, Any]:
    result = parse_summary_capture_html(text, source_name="live-summary")
    slots = result.get("equipment", {}).get("slots", [])  # type: ignore[union-attr]
    if not slots:
        raise ValueError("Summary page has no equipment slots.")
    return result


def _validate_talents_html(text: str) -> dict[str, Any]:
    result = parse_talents_capture_html(text, source_name="live-talents")
    if result.get("error") or not result.get("specs"):
        raise ValueError(f"Talents page rejected: {result.get('error') or 'no specs'}")
    return result


def fetch_validated(
    url: str,
    source: str,
    validate: Callable[[str], dict[str, Any]],
    cache: ResponseCache,
    orchestrator: RequestOrchestrator,
    client,
    now_fn: Callable[[], float] = time,
    refresh: bool = False,
    offline: bool = False,
    allow_stale: bool = False,
    max_age_seconds: float = CHARACTER_MAX_AGE_SECONDS,
    reject_dir: Path | None = None,
    form: dict[str, str] | None = None,
    referer: str | None = None,
) -> FetchResult:
    key = f"{source}|{url}" + ("" if form is None else "|" + "&".join(f"{k}={v}" for k, v in sorted(form.items())))
    entry = cache.get(key)
    now = now_fn()

    def from_entry(origin: str, detail: str) -> FetchResult:
        return FetchResult("ok", validate(entry.body), origin, entry.fetched_at, detail)

    if entry is not None and not refresh and entry.age_seconds(now) <= max_age_seconds:
        return from_entry("cache", "Fresh cache entry used.")
    if offline:
        if entry is not None:
            return from_entry("stale-cache", f"Offline mode: cached data is {int(entry.age_seconds(now))} s old.")
        return FetchResult("offline_miss", None, "none", None, "Offline mode and nothing cached.")

    result = orchestrator.execute_single_request(url=url, client=client, form=form, referer=referer)
    if result.status == "success":
        try:
            parsed = validate(result.body_text)
        except ValueError as exc:
            if reject_dir is not None:
                reject_dir.mkdir(parents=True, exist_ok=True)
                (reject_dir / f"{source}-{int(now)}.txt").write_text(result.body_text, encoding="utf-8")
            detail = f"Response rejected, cache not updated: {exc}"
        else:
            cache.put(key, source, result.body_text, now_fn())
            return FetchResult("ok", parsed, "network", now_fn(), "Fetched live.")
    else:
        detail = f"Request failed: {result.status} ({result.detail})"
    if entry is not None and allow_stale:
        return from_entry("stale-cache", f"{detail} Using stale cache ({int(entry.age_seconds(now))} s old).")
    return FetchResult("failed", None, "none", None, detail)


def character_page_url(name: str, realm: str, view: str) -> str:
    canonical = SUPPORTED_REALMS.get(realm.strip().lower())
    if canonical is None:
        raise ValueError("Unsupported realm. Supported realms: Onyxia, Icecrown.")
    return f"https://{SUPPORTED_HOST}/character/{quote(name.strip(), safe='')}/{canonical}/{view}"


def _section(result: FetchResult) -> dict[str, Any]:
    return {
        "status": result.status,
        "origin": result.origin,
        "observed_at": result.observed_at,
        "detail": result.detail,
        "data": result.data,
    }


def build_snapshot(
    name: str,
    realm: str,
    cache: ResponseCache,
    orchestrator: RequestOrchestrator,
    client,
    defs=None,
    now_fn: Callable[[], float] = time,
    reject_dir: Path | None = None,
    **options: Any,
) -> dict[str, Any]:
    common = dict(cache=cache, orchestrator=orchestrator, client=client, now_fn=now_fn,
                  reject_dir=reject_dir, **options)
    json_res = fetch_validated(api_summary_url(name, realm), "warmane-json-summary", parse_api_summary, **common)
    html_res = fetch_validated(character_page_url(name, realm, "summary"), "warmane-html-summary",
                               _validate_summary_html, **common)
    talents_res = fetch_validated(character_page_url(name, realm, "talents"), "warmane-html-talents",
                                  _validate_talents_html, **common)

    notes: list[str] = []
    if defs is not None:
        from .offline_enrichment import enrich_summary_result, enrich_talents_result

        if html_res.data is not None:
            html_res.data = enrich_summary_result(html_res.data, defs)
        if talents_res.data is not None:
            talents_res.data = enrich_talents_result(talents_res.data, defs)
    else:
        notes.append("Client definitions not applied (no client data).")

    sections = {"json_summary": _section(json_res), "html_summary": _section(html_res),
                "talents": _section(talents_res)}
    ok_count = sum(1 for s in sections.values() if s["status"] == "ok")
    return {
        "schema": SNAPSHOT_SCHEMA,
        "generated_at": now_fn(),
        "character": {"name": name, "realm": SUPPORTED_REALMS[realm.strip().lower()]},
        "complete": ok_count == len(sections),
        "notes": notes,
        "sections": sections,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("name")
    parser.add_argument("realm")
    parser.add_argument("--cache-dir", default=".warmane-cache")
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--allow-stale", action="store_true")
    parser.add_argument("--no-client", action="store_true", help="skip offline client enrichment")
    args = parser.parse_args(argv)

    cache_dir = Path(args.cache_dir)
    cache = ResponseCache(cache_dir / "responses.sqlite")
    orchestrator = RequestOrchestrator(
        checkpoint=ProbeCheckpointStore(path=cache_dir / "transport-state.json"),
        config=TransportConfig(min_request_interval_seconds=SNAPSHOT_INTERVAL_SECONDS),
        skip_completed=False,
    )

    defs_ctx = None
    client_defs = None
    if not args.no_client:
        try:
            from .client_definitions import ClientDefinitions
            from .config import find_config_path, load_config, resolve_wow_client_dir
            from .mpq_reader import ClientData

            data_dir = resolve_wow_client_dir(load_config(find_config_path(None))) / "Data"
            defs_ctx = ClientData(data_dir)
            client_defs = ClientDefinitions(defs_ctx.__enter__())
        except Exception as exc:  # the client is optional; continue with other sources
            print(f"Note: game client unavailable ({exc}).", file=sys.stderr)
            client_defs = None
    from .definitions import load_definitions

    defs = load_definitions(client_defs, Path("library"))
    if defs is None:
        print("Note: no definition source (no client, no library/acore/items.db; run acore_cli fetch).", file=sys.stderr)
    else:
        print("Definition sources: " + ", ".join(defs.source_names), file=sys.stderr)

    try:
        snapshot = build_snapshot(
            args.name, args.realm, cache, orchestrator, budgeted_client(cache_dir), defs=defs,
            reject_dir=cache_dir / "rejected",
            refresh=args.refresh, offline=args.offline, allow_stale=args.allow_stale,
        )
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    finally:
        cache.close()
        if defs_ctx is not None:
            defs_ctx.__exit__(None, None, None)

    out_dir = cache_dir / "snapshots"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = int(snapshot["generated_at"])
    out_path = out_dir / f"{args.name.lower()}-{snapshot['character']['realm'].lower()}-{stamp}.json"
    out_path.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False), encoding="utf-8")
    for key, section in snapshot["sections"].items():
        print(f"{key}: {section['status']} ({section['origin']}) {section['detail']}")
    print(f"complete: {snapshot['complete']}")
    print(f"saved: {out_path}")
    return 0 if snapshot["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
