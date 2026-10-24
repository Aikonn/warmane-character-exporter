"""One command for the whole export of one or all known characters.

python -m warmane_exporter.run NAME REALM          one character
python -m warmane_exporter.run --all               Aikka and Bezduse on Onyxia and Icecrown
Options: --refresh (ignore the 24 h cache), --offline (no requests, only rebuild the export)

Steps per character: snapshot, reputation page, mounts page, achievements, statistics, export.
Every live request is counted against the daily budget (python -m warmane_exporter.budget) and
spaced 3 s apart. The run stops at the first failing step; run it again to continue, because
everything already fetched is served from the cache.
"""

from __future__ import annotations

import argparse
import sys

from . import collect, discover, export, snapshot

ALL_CHARACTERS = (("Aikka", "Onyxia"), ("Aikka", "Icecrown"), ("Bezduse", "Onyxia"), ("Bezduse", "Icecrown"))


def steps(name: str, realm: str, cache_dir: str, refresh: bool, offline: bool) -> list[tuple[str, object, list[str]]]:
    common = ["--cache-dir", cache_dir]
    flags = (["--refresh"] if refresh else []) + (["--offline"] if offline else [])
    plan: list[tuple[str, object, list[str]]] = []
    if not offline:
        plan.append(("snapshot", snapshot.main, [name, realm, *common, *flags]))
        for view in ("reputation", "mounts-and-companions"):
            plan.append((view, discover.main, [name, realm, view, *common] + (["--refresh"] if refresh else [])))
        for section in ("achievements", "statistics"):
            plan.append((section, collect.main, [name, realm, "--section", section, *common, *flags]))
    plan.append(("export", export.main, [name, realm, *common]))
    return plan


def run_character(name: str, realm: str, cache_dir: str, refresh: bool, offline: bool) -> bool:
    print(f"== {name}@{realm}")
    for label, entry, argv in steps(name, realm, cache_dir, refresh, offline):
        print(f"-- {label}")
        code = entry(argv)  # type: ignore[operator]
        if code != 0:
            print(f"Stopped at step '{label}' (exit code {code}). Run the same command again to continue.")
            return False
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("name", nargs="?")
    parser.add_argument("realm", nargs="?")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--cache-dir", default=".warmane-cache")
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args(argv)
    if args.all:
        targets = ALL_CHARACTERS
    elif args.name and args.realm:
        targets = ((args.name, args.realm),)
    else:
        parser.error("give NAME REALM or --all")
    for name, realm in targets:
        if not run_character(name, realm, args.cache_dir, args.refresh, args.offline):
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
