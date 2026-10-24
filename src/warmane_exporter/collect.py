"""Collect achievement categories for one character (throttled, cached, resumable).

python -m warmane_exporter.collect NAME REALM [--limit N] [--dry-run] [--offline]
                                   [--refresh] [--interval SECONDS]

One POST per category; every validated response is cached for 24 hours, so an interrupted or
limited run continues where it stopped. --limit caps LIVE requests per run (cache hits are
free). Nothing is fetched with --dry-run or --offline. Result: .warmane-cache/collections/.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from time import time
from typing import Any

from .achievements_parser import CategoryError, parse_achievements_response, parse_statistics_response
from .budget import DEFAULT_INTERVAL_SECONDS, BudgetExhausted, budgeted_client
from .cache import ResponseCache
from .checkpoint import ProbeCheckpointStore
from .http_client import UrllibHttpClient
from . import progress
from .identity import SUPPORTED_REALMS
from .snapshot import character_page_url, fetch_validated
from .transport import RequestOrchestrator, TransportConfig

COLLECTION_SCHEMA = "character-collection/0"
COLLECTION_MAX_AGE_SECONDS = 24 * 3600

# Category ids observed on the achievements page sidebar (Aikka@Onyxia, 2026-10-24).
# (id, name, parent_id). A top-level category response does NOT include its subcategories.
ACHIEVEMENT_CATEGORIES: tuple[tuple[int, str, int | None], ...] = (
    (92, "General", None),
    (96, "Quests", None), (14861, "Classic", 96), (14862, "The Burning Crusade", 96),
    (14863, "Wrath of the Lich King", 96),
    (97, "Exploration", None), (14777, "Eastern Kingdoms", 97), (14778, "Kalimdor", 97),
    (14779, "Outland", 97), (14780, "Northrend", 97),
    (95, "Player vs. Player", None), (165, "Arena", 95), (14801, "Alterac Valley", 95),
    (14802, "Arathi Basin", 95), (14803, "Eye of the Storm", 95), (14804, "Warsong Gulch", 95),
    (14881, "Strand of the Ancients", 95), (14901, "Wintergrasp", 95), (15003, "Isle of Conquest", 95),
    (168, "Dungeons & Raids", None), (14808, "Classic", 168), (14805, "The Burning Crusade", 168),
    (14806, "Lich King Dungeon", 168), (14921, "Lich King Heroic", 168),
    (14922, "Lich King 10-Player Raid", 168), (14923, "Lich King 25-Player Raid", 168),
    (14961, "Secrets of Ulduar 10", 168), (14962, "Secrets of Ulduar 25", 168),
    (15001, "Call of the Crusade 10", 168), (15002, "Call of the Crusade 25", 168),
    (15041, "Fall of the Lich King 10", 168), (15042, "Fall of the Lich King 25", 168),
    (169, "Professions", None), (170, "Cooking", 169), (171, "Fishing", 169), (172, "First Aid", 169),
    (201, "Reputation", None), (14864, "Classic", 201), (14865, "The Burning Crusade", 201),
    (14866, "Wrath of the Lich King", 201),
    (155, "World Events", None), (160, "Lunar Festival", 155), (187, "Love is in the Air", 155),
    (159, "Noblegarden", 155), (163, "Children's Week", 155), (161, "Midsummer", 155),
    (162, "Brewfest", 155), (158, "Hallow's End", 155), (14981, "Pilgrim's Bounty", 155),
    (156, "Winter Veil", 155), (14941, "Argent Tournament", 155),
    (81, "Feats of Strength", None),
)


def _validate(text: str) -> dict[str, Any]:
    return {"entries": parse_achievements_response(text)}


# Statistics sidebar of /statistics (Aikka@Onyxia, 2026-10-24): (id, name, parent_id).
STATISTIC_CATEGORIES: tuple[tuple[int, str, int | None], ...] = (
    (130, "Character", None), (140, "Wealth", 130), (145, "Consumables", 130),
    (147, "Reputation", 130), (191, "Gear", 130),
    (141, "Combat", None),
    (128, "Kills", None), (135, "Creatures", 128), (136, "Honorable Kills", 128), (137, "Killing Blows", 128),
    (122, "Deaths", None), (123, "Arenas", 122), (124, "Battlegrounds", 122), (125, "Dungeons", 122),
    (126, "World", 122), (127, "Resurrection", 122),
    (133, "Quests", None),
    (14807, "Dungeons & Raids", None), (14821, "Classic", 14807), (14822, "The Burning Crusade", 14807),
    (14823, "Wrath of the Lich King", 14807), (14963, "Secrets of Ulduar", 14807),
    (15021, "Call of the Crusade", 14807), (15062, "Fall of the Lich King", 14807),
    (132, "Skills", None), (178, "Secondary Skills", 132), (173, "Professions", 132),
    (134, "Travel", None), (131, "Social", None),
    (21, "Player vs. Player", None), (152, "Rated Arenas", 21), (153, "Battlegrounds", 21), (154, "World", 21),
)


def _validate_statistics(text: str) -> dict[str, Any]:
    return {"entries": parse_statistics_response(text)}


_VALIDATORS = {"achievements": _validate, "statistics": _validate_statistics}


def summarize(categories: list[dict[str, Any]]) -> dict[str, Any]:
    """Totals over unique achievement ids (an id seen in two categories counts once)."""
    seen: dict[int, dict[str, Any]] = {}
    duplicates: list[int] = []
    for category in categories:
        for entry in category.get("entries") or []:
            if entry["id"] in seen:
                duplicates.append(entry["id"])
            else:
                seen[entry["id"]] = entry
    earned = [e for e in seen.values() if e["earned"]]
    return {
        "unique_achievements": len(seen),
        "earned": len(earned),
        "earned_points": sum(e["points"] or 0 for e in earned),
        "duplicate_ids": sorted(set(duplicates)),
        "categories_ok": sum(1 for c in categories if c["status"] == "ok"),
        "categories_total": len(categories),
    }


def collect_achievements(
    name: str, realm: str, cache: ResponseCache, orchestrator: RequestOrchestrator, client,
    *, limit: int | None = None, dry_run: bool = False, offline: bool = False,
    refresh: bool = False, reject_dir: Path | None = None,
    categories: tuple[tuple[int, str, int | None], ...] | None = None, section: str = "achievements",
) -> dict[str, Any]:
    url = character_page_url(name, realm, section)
    categories = categories or (STATISTIC_CATEGORIES if section == "statistics" else ACHIEVEMENT_CATEGORIES)
    live = 0
    results: list[dict[str, Any]] = []
    label = "Achievements" if section == "achievements" else "Statistics"
    for position, (cat_id, cat_name, parent) in enumerate(categories, 1):
        progress.note(f"{label}: {cat_name} ({position} of {len(categories)})")
        record: dict[str, Any] = {"id": cat_id, "name": cat_name, "parent": parent}
        form = {"category": str(cat_id)}
        source = section
        key_probe = cache.get(f"{source}|{url}|category={cat_id}")
        cached_fresh = key_probe is not None and not refresh and key_probe.age_seconds(time()) <= COLLECTION_MAX_AGE_SECONDS
        needs_live = not cached_fresh and not offline
        if dry_run:
            record.update(status="planned", origin="cache" if cached_fresh else ("live" if needs_live else "none"),
                          entries=None)
        elif needs_live and limit is not None and live >= limit:
            record.update(status="deferred", origin="none", entries=None,
                          detail="Live request limit reached; run again to continue.")
        else:
            result = fetch_validated(
                url, source, _VALIDATORS[section], cache, orchestrator, client,
                refresh=refresh, offline=offline, allow_stale=offline,
                max_age_seconds=COLLECTION_MAX_AGE_SECONDS, reject_dir=reject_dir,
                form=form, referer=url,
            )
            if result.origin == "network":
                live += 1
            record.update(status=result.status, origin=result.origin, observed_at=result.observed_at,
                          detail=result.detail,
                          entries=result.data["entries"] if result.data else None)
        results.append(record)
        progress.advance(f"{label}: {cat_name} done ({position} of {len(categories)})")
    complete = all(r["status"] == "ok" for r in results)
    return {
        "schema": COLLECTION_SCHEMA,
        "section": section,
        "generated_at": time(),
        "character": {"name": name, "realm": SUPPORTED_REALMS[realm.strip().lower()]},
        "live_requests": live,
        "complete": complete,
        "summary": summarize(results) if section == "achievements" else summarize_rows(results),
        "categories": results,
    }


def _latest_snapshot_points(cache_dir: Path, name: str, realm: str) -> int | None:
    pattern = f"{name.lower()}-{SUPPORTED_REALMS[realm.strip().lower()].lower()}-*.json"
    files = sorted((cache_dir / "snapshots").glob(pattern))
    if not files:
        return None
    try:
        snap = json.loads(files[-1].read_text(encoding="utf-8"))
        return snap["sections"]["json_summary"]["data"]["achievement_points"]
    except (KeyError, TypeError, ValueError, OSError):
        return None


def summarize_rows(categories: list[dict[str, Any]]) -> dict[str, Any]:
    rows = sum(len(c.get("entries") or []) for c in categories)
    return {
        "rows": rows,
        "categories_ok": sum(1 for c in categories if c["status"] == "ok"),
        "categories_total": len(categories),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("name")
    parser.add_argument("realm")
    parser.add_argument("--section", choices=("achievements", "statistics"), default="achievements")
    parser.add_argument("--cache-dir", default=".warmane-cache")
    parser.add_argument("--limit", type=int, default=None, help="maximum live requests this run")
    parser.add_argument("--interval", type=float, default=DEFAULT_INTERVAL_SECONDS)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args(argv)

    cache_dir = Path(args.cache_dir)
    cache = ResponseCache(cache_dir / "responses.sqlite")
    orchestrator = RequestOrchestrator(
        checkpoint=ProbeCheckpointStore(path=cache_dir / "transport-state.json"),
        config=TransportConfig(min_request_interval_seconds=args.interval),
        skip_completed=False,
    )
    try:
        collection = collect_achievements(
            args.name, args.realm, cache, orchestrator, budgeted_client(cache_dir),
            limit=args.limit, dry_run=args.dry_run, offline=args.offline, refresh=args.refresh,
            reject_dir=cache_dir / "rejected", section=args.section,
        )
    except (ValueError, CategoryError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    finally:
        cache.close()

    for c in collection["categories"]:
        count = "" if c["entries"] is None else f" {len(c['entries'])} entries"
        print(f"{c['id']:>6} {c['name']}: {c['status']} ({c['origin']}){count}")
    summary = collection["summary"]
    print(f"live requests: {collection['live_requests']}; categories ok: {summary['categories_ok']}/{summary['categories_total']}")
    if not args.dry_run:
        if args.section == "achievements":
            expected = _latest_snapshot_points(cache_dir, args.name, args.realm)
            print(f"earned: {summary['earned']} of {summary['unique_achievements']}; earned points: {summary['earned_points']}"
                  + ("" if expected is None else f"; armory total: {expected}"))
            print(f"duplicate ids across categories: {summary['duplicate_ids']}")
        else:
            print(f"statistic rows: {summary['rows']}")
        out_dir = cache_dir / "collections"
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / f"{args.name.lower()}-{collection['character']['realm'].lower()}-{args.section}-{int(collection['generated_at'])}.json"
        out.write_text(json.dumps(collection, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"complete: {collection['complete']}\nsaved: {out}")
    return 0 if args.dry_run or collection["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
