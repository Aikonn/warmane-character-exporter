"""Export static text definitions from the game client into one small local file.

python -m warmane_exporter.definition_export [--output library/definitions/client-export.json]

After the export the tool needs no game client: FileDefinitions reads this file.
The export also holds the effect spells of weapons and armor listed in the local item database (trinket procs, ring effects).
Content: every SpellItemEnchantment name (enchants, gems, socket bonuses), the gem colour of each gem effect, every talent with its
rank spells, every glyph, and name / rank / description / rendered description of the spells those
reference. Unresolvable template parts stay flagged (rendered_unresolved), never guessed.
The text is the client's own, so it reflects whichever client (stock, HD, custom patch) was used.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any, Iterable

from .client_definitions import (
    ENCHANT_CONDITION, ENCHANT_FIELDS, ENCHANT_NAME, GEMPROP_FIELDS, GLYPH_FIELDS, TALENT_COLUMN, TALENT_FIELDS, TALENT_RANK_COUNT,
    TALENT_RANK_FIRST, TALENT_ROW, TALENT_TAB, ClientDefinitions,
)

SCHEMA = "client-export/1"
DEFAULT_OUTPUT = Path("library/definitions/client-export.json")


def export_definitions(defs: ClientDefinitions, extra_spell_ids: Iterable[int] = ()) -> dict[str, Any]:
    enchant_table = defs._table("SpellItemEnchantment.dbc", ENCHANT_FIELDS)
    enchants: dict[str, str] = {}
    for position in range(len(enchant_table)):
        row = enchant_table.row(position)
        enchants[str(row[0])] = enchant_table.string_at(row[ENCHANT_NAME]) or ""

    gem_table = defs._table("GemProperties.dbc", GEMPROP_FIELDS)
    gem_properties: dict[str, list[int]] = {}
    for position in range(len(gem_table)):
        row = gem_table.row(position)
        if row[1]:
            gem_properties.setdefault(str(row[1]), [row[0], row[4]])

    enchant_conditions: dict[str, list[list[int]]] = {}
    for position in range(len(enchant_table)):
        row = enchant_table.row(position)
        if row[ENCHANT_CONDITION]:
            found = defs.gem_requirements(row[0])
            if found:
                enchant_conditions[str(row[0])] = found

    talent_table = defs._table("Talent.dbc", TALENT_FIELDS)
    talents: list[dict[str, Any]] = []
    spell_ids: set[int] = set()
    for position in range(len(talent_table)):
        row = talent_table.row(position)
        ranks = [s for s in row[TALENT_RANK_FIRST: TALENT_RANK_FIRST + TALENT_RANK_COUNT] if s]
        talents.append({"id": row[0], "tab": row[TALENT_TAB], "row": row[TALENT_ROW],
                        "column": row[TALENT_COLUMN], "ranks": ranks})
        spell_ids.update(ranks)

    glyph_table = defs._table("GlyphProperties.dbc", GLYPH_FIELDS)
    glyphs: list[dict[str, int]] = []
    for position in range(len(glyph_table)):
        row = glyph_table.row(position)
        glyphs.append({"id": row[0], "spell": row[1], "flags": row[2]})
        spell_ids.add(row[1])

    spell_ids.update(extra_spell_ids)
    spells: dict[str, dict[str, Any]] = {}
    for spell_id in sorted(spell_ids):
        info = defs.spell(spell_id)
        if info is None:
            continue
        entry: dict[str, Any] = {"name": info.name, "rank": info.rank, "description": info.description}
        try:
            rendered = defs.render_spell_description(spell_id)
        except Exception as exc:  # one odd spell must not stop the export
            entry["render_error"] = f"{type(exc).__name__}: {exc}"
        else:
            if rendered is not None:
                entry["rendered"] = rendered.text
                entry["rendered_unresolved"] = rendered.unresolved
        spells[str(spell_id)] = entry

    return {
        "schema": SCHEMA,
        "exported_at": time.time(),
        "client_tables": {"enchants": len(enchants), "gem_properties": len(gem_properties), "enchant_conditions": len(enchant_conditions), "talents": len(talents), "glyphs": len(glyphs), "spells": len(spells)},
        "enchants": enchants,
        "gem_properties": gem_properties,
        "enchant_conditions": enchant_conditions,
        "talents": talents,
        "glyphs": glyphs,
        "spells": spells,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)

    from .config import find_config_path, load_config, resolve_wow_client_dir
    from .mpq_reader import ClientData

    data_dir = resolve_wow_client_dir(load_config(find_config_path(None))) / "Data"
    with ClientData(data_dir) as client:
        extra: set[int] = set()
        acore_db = Path("library/acore/items.db")
        if acore_db.exists():
            from .acore_items import AcoreItems
            items = AcoreItems(acore_db)
            try:
                extra = items.effect_spell_ids()
            finally:
                items.close()
        data = export_definitions(ClientDefinitions(client), extra)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, ensure_ascii=False, indent=0), encoding="utf-8")
    spells = data["spells"].values()
    unresolved = sum(1 for s in spells if s.get("rendered_unresolved"))
    errors = sum(1 for s in spells if "render_error" in s)
    print(f"saved {args.output}: {data['client_tables']}; spells with unresolved parts: {unresolved}; render errors: {errors}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
