"""One command for the whole export of one or all known characters.

python -m warmane_exporter.run NAME REALM          one character
python -m warmane_exporter.run LINK                an armory link, e.g. https://armory.warmane.com/character/Aikka/Onyxia/summary
python -m warmane_exporter.run --all               Aikka and Bezduse on Onyxia and Icecrown
Options: --full (all achievement and statistic categories; the default fetches only what the PvE report uses), --html-output FILE (copy the PvE report there), --refresh (ignore the 24 h cache), --offline (no requests, only rebuild the export)

Steps per character: snapshot, reputation page, mounts page, achievements, statistics, export.
Every live request is counted against the daily budget (python -m warmane_exporter.budget) and
spaced 1 s apart. The run stops at the first failing step; run it again to continue, because
everything already fetched is served from the cache.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from . import collect, discover, export, progress, snapshot
from .identity import parse_character_link

ALL_CHARACTERS = (("Aikka", "Onyxia"), ("Aikka", "Icecrown"), ("Bezduse", "Onyxia"), ("Bezduse", "Icecrown"))


def steps(name: str, realm: str, cache_dir: str, refresh: bool, offline: bool, full: bool = False) -> list[tuple[str, object, list[str]]]:
    common = ["--cache-dir", cache_dir]
    flags = (["--refresh"] if refresh else []) + (["--offline"] if offline else [])
    coll_flags = flags + (["--full"] if full else [])
    plan: list[tuple[str, object, list[str]]] = []
    if not offline:
        plan.append(("snapshot", snapshot.main, [name, realm, *common, *flags]))
        for view in ("reputation", "mounts-and-companions"):
            plan.append((view, discover.main, [name, realm, view, *common] + (["--refresh"] if refresh else [])))
        for section in ("achievements", "statistics"):
            plan.append((section, collect.main, [name, realm, "--section", section, *common, *coll_flags]))
    plan.append(("export", export.main, [name, realm, *common]))
    return plan


STEP_TEXT = {
    "snapshot": "Reading character summary and talents",
    "reputation": "Reading reputation",
    "mounts-and-companions": "Reading mounts and companions",
    "export": "Building the report",
}


def step_units(label: str, full: bool = False) -> int:
    """Progress units of a step; the achievement and statistics steps count one per category and report it themselves."""
    return {"snapshot": 3, "achievements": len(collect.categories_for("achievements", full)), "statistics": len(collect.categories_for("statistics", full))}.get(label, 1)


def run_character(name: str, realm: str, cache_dir: str, refresh: bool, offline: bool, full: bool = False) -> bool:
    print(f"== {name}@{realm}")
    plan = steps(name, realm, cache_dir, refresh, offline, full)
    progress.start(sum(step_units(label, full) for label, _, _ in plan), f"Starting {name} ({realm})")
    for label, entry, argv in plan:
        print(f"-- {label}")
        progress.note(STEP_TEXT.get(label, label))
        code = entry(argv)  # type: ignore[operator]
        if code != 0:
            print(f"Stopped at step '{label}' (exit code {code}). Run the same command again to continue.")
            return False
        if label not in ("achievements", "statistics"):
            progress.advance(f"{STEP_TEXT.get(label, label)}: done", step_units(label, full))
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("name", nargs="?", help="character name, or an armory link such as https://armory.warmane.com/character/Aikka/Onyxia/summary")
    parser.add_argument("realm", nargs="?")
    parser.add_argument("--html-output", type=Path, help="also copy the PvE report HTML to this file")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--cache-dir", default=".warmane-cache")
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--full", action="store_true", help="fetch all achievement and statistic categories, not only those the PvE report uses")
    args = parser.parse_args(argv)
    if args.all:
        targets = ALL_CHARACTERS
    elif args.name and args.realm:
        targets = ((args.name, args.realm),)
    elif args.name and not args.realm:
        try:
            identity = parse_character_link(args.name)
        except ValueError as exc:
            print(f"Not a usable armory link: {exc}")
            print("Expected something like https://armory.warmane.com/character/Aikka/Onyxia/summary")
            return 2
        targets = ((identity.name, identity.realm),)
    else:
        parser.error("give NAME REALM, an armory link, or --all")
    if args.html_output and len(targets) != 1:
        parser.error("--html-output works with one character")
    for name, realm in targets:
        if not run_character(name, realm, args.cache_dir, args.refresh, args.offline, args.full):
            return 1
        if args.html_output:
            source = Path(args.cache_dir) / "exports" / f"{name.lower()}-{realm.lower()}-pve.html"
            try:
                args.html_output.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, args.html_output)
            except OSError as exc:
                print(f"Could not save the report to {args.html_output}: {exc}")
                print(f"The report is still available at: {source}")
                return 1
            print(f"copied report to: {args.html_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
