"""Parse a local talents capture and print a compact client-enriched summary.

python -m warmane_exporter.enrich_diagnostic CAPTURE.html [--data-dir DIR] [--config FILE] [--json]
Offline only. Source parser fields are untouched; client facts are under "client".
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .client_definitions import ClientDefinitions
from .config import ConfigError, find_config_path, load_config, resolve_wow_client_dir
from .dbc_parser import DbcError
from .mpq_reader import ClientData, MPQError
from .offline_enrichment import enrich_talents_result
from .talents_parser import parse_talents_capture_file


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("capture")
    parser.add_argument("--data-dir")
    parser.add_argument("--config")
    parser.add_argument("--json", action="store_true", help="Print full enriched JSON")
    args = parser.parse_args(argv)
    try:
        data_dir = Path(args.data_dir) if args.data_dir else (
            resolve_wow_client_dir(load_config(find_config_path(args.config))) / "Data"
        )
        result = parse_talents_capture_file(Path(args.capture))
        with ClientData(data_dir) as client:
            enriched = enrich_talents_result(result, ClientDefinitions(client))
    except (ConfigError, MPQError, DbcError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(enriched, indent=2, ensure_ascii=False))
        return 0
    for spec in enriched["specs"]:
        print(f"spec {spec['source_spec_id']}")
        for tree in spec["trees"]:
            talents = tree["talents"]
            ok = sum(1 for t in talents if t["client"]["resolved"])
            print(f"  tree {tree.get('name')!r}: {ok}/{len(talents)} talents resolved")
            for t in talents:
                c = t["client"]
                if c["resolved"] and t.get("points_spent"):
                    print(f"    {c['name']} {t['points_spent']}/{c['max_rank']}: {c.get('selected_rank_description')}")
    for spec_id, block in enriched["glyphs"].items():
        print(f"glyphs spec {spec_id}")
        for g in block["entries"]:
            c = g["client"]
            print(f"  [{g['category']}] {g['name']!r} -> {c.get('spell_name')!r} slot {c.get('slot_type')}")
    print(f"client_warnings: {len(enriched['client_warnings'])}")
    for w in enriched["client_warnings"]:
        print(f"  - {w}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
