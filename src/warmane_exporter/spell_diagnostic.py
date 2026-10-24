"""Print rendered descriptions for sample spells from the real client (offline).

python -m warmane_exporter.spell_diagnostic [SPELL_ID ...]
"""

from __future__ import annotations

import sys

from .client_definitions import ClientDefinitions
from .config import find_config_path, load_config, resolve_wow_client_dir
from .mpq_reader import ClientData

SAMPLES = (58647, 58680, 59309, 63334, 55679, 14769, 58676, 54925, 48450)


def main(argv: list[str] | None = None) -> int:
    args = [int(a) for a in (argv if argv is not None else sys.argv[1:])] or list(SAMPLES)
    data_dir = resolve_wow_client_dir(load_config(find_config_path(None))) / "Data"
    with ClientData(data_dir) as client:
        defs = ClientDefinitions(client)
        for sid in args:
            info = defs.spell(sid)
            print(f"{sid} {info.name if info else None!r}")
            rendered = defs.render_spell_description(sid)
            if rendered:
                print(f"  template: {info.description}")
                print(f"  rendered: {rendered.text}")
                print(f"  unresolved={rendered.unresolved} notes={rendered.notes}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
