"""Offline DBC diagnostic: inspect tables straight from the client MPQs.

python -m warmane_exporter.dbc_diagnostic [DATA_DIR] [NAME.dbc ...] [--id NAME.dbc=KEY] ...
DATA_DIR defaults to the Data folder under the machine-aware config.
No network access. Field meanings are NOT interpreted; values are raw.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import ConfigError, find_config_path, load_config, resolve_wow_client_dir
from .client_definitions import ClientDefinitions
from .dbc_parser import DbcError, DbcTable
from .mpq_reader import ClientData, MPQError

DEFAULT_DBCS = ["SpellItemEnchantment.dbc", "Spell.dbc", "Item.dbc"]


def _dbc_path(name: str) -> str:
    return name if "\\" in name or "/" in name else f"DBFilesClient\\{name}"


def _load(client: ClientData, name: str) -> tuple[DbcTable, Path] | None:
    found = client.read(_dbc_path(name))
    if found is None:
        print(f"[NOTFOUND] {name}")
        return None
    data, archive = found
    try:
        return DbcTable(data), archive
    except DbcError as exc:
        print(f"[ERROR] {name} ({archive.name}): {exc}")
        return None


def _print_row(table: DbcTable, row: tuple[int, ...], label: str) -> None:
    print(f"  {label}:")
    for index, value in enumerate(row):
        text = table.string_at(value)
        extra = f"  -> {text!r}" if text else ""
        print(f"    [{index:3}] {value}{extra}")


def _resolve_data_dir(arg: str | None, config_arg: str | None) -> Path:
    if arg:
        return Path(arg)
    return resolve_wow_client_dir(load_config(find_config_path(config_arg))) / "Data"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data-dir", help="Client Data folder (default: from config)")
    parser.add_argument("--config", help="Config file path")
    parser.add_argument("--locale", default="enUS")
    parser.add_argument("--id", action="append", default=[], metavar="NAME=KEY",
                        help="Print the row whose field 0 equals KEY, e.g. Spell.dbc=14769")
    parser.add_argument("--enchant", type=int, action="append", default=[], metavar="ID",
                        help="Print SpellItemEnchantment text for ID (repeatable)")
    parser.add_argument("--spell", type=int, action="append", default=[], metavar="ID",
                        help="Print spell name, rank and description for ID (repeatable)")
    parser.add_argument("--talent", type=int, action="append", default=[], metavar="SPELL_ID",
                        help="Print talent rank spell IDs for any rank spell ID (repeatable)")
    parser.add_argument("--item", type=int, action="append", default=[], metavar="ID",
                        help="Print item class, subclass and inventory type for ID (repeatable)")
    parser.add_argument("names", nargs="*", help="DBC names (default: a small set)")
    args = parser.parse_args(argv)

    try:
        data_dir = _resolve_data_dir(args.data_dir, args.config)
        client = ClientData(data_dir, args.locale)
    except (ConfigError, MPQError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    with client:
        for path, reason in client.skipped:
            print(f"[SKIPPED] {path.name}: {reason}")
        lookups = []
        for item in args.id:
            name, sep, key = item.partition("=")
            if not sep or not key.isdigit():
                print(f"Error: --id expects NAME=KEY, got {item!r}", file=sys.stderr)
                return 1
            lookups.append((name, int(key)))
        compact = args.enchant or args.spell or args.item or args.talent
        names = args.names or ([] if lookups or compact else DEFAULT_DBCS)
        try:
            if compact:
                defs = ClientDefinitions(client)
                for key in args.enchant:
                    print(f"enchant {key}: {defs.enchant_text(key)!r}")
                for key in args.spell:
                    info = defs.spell(key)
                    print(f"spell {key}: " + (f"{info.name!r} {info.rank!r} {info.description!r}" if info else "None"))
                for key in args.talent:
                    info = defs.talent_for_spell(key)
                    print(f"talent via spell {key}: " + (
                        f"talent {info.talent_id} tab {info.tab_id} row {info.row} col {info.column} ranks {list(info.rank_spell_ids)}"
                        if info else "None"))
                for key in args.item:
                    info = defs.item(key)
                    print(f"item {key}: " + (f"class {info.item_class} subclass {info.item_subclass} slot {info.inventory_type_name}" if info else "None"))
            for name in names:
                loaded = _load(client, name)
                if loaded:
                    table, archive = loaded
                    h = table.header
                    print(f"[OK] {name} from {archive.name}: {h.record_count} records, "
                          f"{h.field_count} fields, strings {h.string_block_size} bytes")
                    for i in range(min(3, len(table))):
                        print(f"    row {i}: {table.row(i)[:8]}...")
            for name, key in lookups:
                loaded = _load(client, name)
                if loaded:
                    row = loaded[0].find(key)
                    if row is None:
                        print(f"[NOKEY] {name} has no row with key {key}")
                    else:
                        _print_row(loaded[0], row, f"{name} key {key} (from {loaded[1].name})")
        except (MPQError, DbcError) as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
