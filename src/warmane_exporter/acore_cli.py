"""AzerothCore item data: download once, then verify against the Warmane data already collected.

  python -m warmane_exporter.acore_cli fetch [--library library]
  python -m warmane_exporter.acore_cli verify [FILES...] [--library library]

fetch makes one HTTPS request (raw.githubusercontent.com, about 14 MB) and is skipped when the
dump is already in the library. verify reads only local files: with no FILES it checks every
JSON in .warmane-cache/ and tests/fixtures/real/ that contains equipment, comparing item name
(armory JSON summary) and item quality (armory page markup) with AzerothCore.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path
from typing import Any, Iterator

from .acore_items import QUALITY_NAMES, SOURCE_URL, AcoreItems, build_database
from .library import Library

KIND = "acore"
SQL_KEY = "item_template"
DB_NAME = "items.db"


def db_path(library_root: Path) -> Path:
    return Path(library_root) / KIND / DB_NAME


def _download(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "warmane-character-exporter (local tool)"})
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read().decode("utf-8")


def _has_effects(path: Path) -> bool:
    db = AcoreItems(path)
    try:
        return db.has_effects()
    finally:
        db.close()


def fetch(library_root: Path, download=_download) -> tuple[int, bool]:
    """Ensure the item database exists. Returns (item_count, downloaded_now)."""
    library = Library(library_root, version="acore-master-2017")
    sql, live = library.get_or_fetch(KIND, SQL_KEY, SOURCE_URL, download, ext="sql")
    target = db_path(library_root)
    if live or not target.exists() or not _has_effects(target):   # rebuild from the stored dump, no download
        return build_database(sql, target), live
    db = AcoreItems(target)
    try:
        return db.count(), False
    finally:
        db.close()


def observed_items(data: Any) -> Iterator[dict[str, Any]]:
    """Find item observations anywhere in a JSON document.

    Yields {"item_id", "name", "quality"}; name / quality are None when the source lacks them.
    """
    if isinstance(data, dict):
        if isinstance(data.get("equipment"), list) and data["equipment"] and isinstance(data["equipment"][0], dict) \
                and "item" in data["equipment"][0]:
            for entry in data["equipment"]:
                try:
                    yield {"item_id": int(entry["item"]), "name": entry.get("name"), "quality": None}
                except (KeyError, TypeError, ValueError):
                    continue
        reference = data.get("item_reference")
        if isinstance(reference, dict) and "quality" in reference:
            raw = (reference.get("namespaces") or {}).get("item") or reference.get("href_item_id")
            try:
                yield {"item_id": int(raw), "name": reference.get("name"), "quality": reference.get("quality")}
            except (TypeError, ValueError):
                pass
        for value in data.values():
            yield from observed_items(value)
    elif isinstance(data, list):
        for value in data:
            yield from observed_items(value)


def verify_documents(documents: dict[str, Any], db: AcoreItems) -> dict[str, Any]:
    checked = 0
    differences: list[str] = []
    missing: list[str] = []
    seen_ids: set[int] = set()
    for label, document in documents.items():
        for obs in observed_items(document):
            checked += 1
            seen_ids.add(obs["item_id"])
            item = db.item(obs["item_id"])
            if item is None:
                missing.append(f"{label}: item {obs['item_id']} ({obs['name']}) not in AzerothCore")
                continue
            if obs["name"] and obs["name"] != item.name:
                differences.append(f"{label}: item {item.item_id} name '{obs['name']}' != AzerothCore '{item.name}'")
            if obs["quality"] is not None and obs["quality"] != item.quality:
                differences.append(
                    f"{label}: item {item.item_id} quality {QUALITY_NAMES.get(obs['quality'])} != "
                    f"AzerothCore {item.quality_name}"
                )
    return {"observations": checked, "unique_items": len(seen_ids), "missing": missing, "differences": differences}


def _default_files() -> list[Path]:
    found: list[Path] = []
    for folder in (Path(".warmane-cache"), Path("tests/fixtures/real")):
        if folder.exists():
            found.extend(sorted(folder.rglob("*.json")))
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["fetch", "verify"])
    parser.add_argument("files", nargs="*", type=Path)
    parser.add_argument("--library", type=Path, default=Path("library"))
    args = parser.parse_args(argv)

    if args.command == "fetch":
        count, live = fetch(args.library)
        print(f"{count} items in {db_path(args.library)} ({'downloaded now' if live else 'already local, no request made'})")
        return 0

    target = db_path(args.library)
    if not target.exists():
        print("No item database yet. Run: python -m warmane_exporter.acore_cli fetch", file=sys.stderr)
        return 2
    documents: dict[str, Any] = {}
    for path in args.files or _default_files():
        try:
            documents[str(path)] = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
    db = AcoreItems(target)
    try:
        report = verify_documents(documents, db)
    finally:
        db.close()
    print(f"files read: {len(documents)}; item observations: {report['observations']}; unique items: {report['unique_items']}")
    for line in report["missing"] + report["differences"]:
        print("  " + line)
    verdict = "MATCH" if not report["missing"] and not report["differences"] and report["observations"] else "CHECK"
    print(f"result: {verdict} ({len(report['missing'])} missing, {len(report['differences'])} differences)")
    return 0 if verdict == "MATCH" else 1


if __name__ == "__main__":
    raise SystemExit(main())
