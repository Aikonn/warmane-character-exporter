"""Parse a local summary capture and print client-enriched equipment.

python -m warmane_exporter.enrich_summary_diagnostic CAPTURE.html [--data-dir DIR] [--config FILE]
Offline only.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .client_definitions import ClientDefinitions
from .config import ConfigError, find_config_path, load_config, resolve_wow_client_dir
from .dbc_parser import DbcError
from .mpq_reader import ClientData, MPQError
from .offline_enrichment import enrich_summary_result
from .summary_parser import parse_summary_capture_file


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("capture")
    parser.add_argument("--data-dir")
    parser.add_argument("--config")
    args = parser.parse_args(argv)
    try:
        data_dir = Path(args.data_dir) if args.data_dir else (
            resolve_wow_client_dir(load_config(find_config_path(args.config))) / "Data"
        )
        result = parse_summary_capture_file(Path(args.capture))
        with ClientData(data_dir) as client:
            enriched = enrich_summary_result(result, ClientDefinitions(client))
    except (ConfigError, MPQError, DbcError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    for slot in enriched["equipment"]["slots"]:
        c = slot.get("client")
        if not c:
            print(f"{slot['slot_key']}: empty/unrecognized ({slot.get('slot_name')})")
            continue
        inferred = (slot.get("layout_inference") or {}).get("inferred_slot_name")
        item = c.get("item", {})
        print(f"{slot['slot_key']} [{inferred}] item {item.get('item_id')} "
              f"{item.get('inventory_type')} check={c.get('slot_check')}")
        if "enchant" in c:
            print(f"    enchant {c['enchant']['id']}: {c['enchant']['text']}")
        for gem in c.get("gems", []):
            print(f"    gem {gem['position']}: " + ("empty" if gem.get("empty") else f"{gem['id']}: {gem['text']}"))
    print(f"client_warnings: {len(enriched['client_warnings'])}")
    for w in enriched["client_warnings"]:
        print(f"  - {w}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
