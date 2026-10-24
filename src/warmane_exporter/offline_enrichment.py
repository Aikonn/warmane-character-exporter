"""Attach client-derived facts to parsed talents output without altering source fields.

Every added value lives under a "client" key. Disagreements between the capture and
the client data are reported in "client_warnings"; nothing is guessed or overwritten.
"""

from __future__ import annotations

import copy
from typing import Any

from .client_definitions import ClientDefinitions


def _as_int(value: Any) -> int | None:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def _enrich_talent(talent: dict[str, Any], defs: ClientDefinitions, warnings: list[str]) -> None:
    spell_id = _as_int(talent.get("source_spell_id"))
    client: dict[str, Any] = {"resolved": False}
    talent["client"] = client
    if spell_id is None:
        warnings.append("talent without numeric source_spell_id")
        return
    info = defs.talent_for_spell(spell_id)
    if info is None:
        warnings.append(f"spell {spell_id}: not a talent rank in client data")
        return
    client.update(
        resolved=True,
        talent_id=info.talent_id,
        tab_id=info.tab_id,
        row=info.row,
        column=info.column,
        rank_spell_ids=list(info.rank_spell_ids),
        max_rank=len(info.rank_spell_ids),
    )
    first = defs.spell(info.rank_spell_ids[0])
    client["name"] = first.name if first else None
    spent = talent.get("points_spent")
    maximum = talent.get("points_max")
    if isinstance(maximum, int) and maximum != len(info.rank_spell_ids):
        warnings.append(f"talent {info.talent_id}: capture max {maximum} != client ranks {len(info.rank_spell_ids)}")
    if isinstance(spent, int) and 1 <= spent <= len(info.rank_spell_ids):
        selected = info.rank_spell_ids[spent - 1]
        spell = defs.spell(selected)
        client["selected_rank_spell_id"] = selected
        client["selected_rank_description"] = spell.description if spell else None


def _enrich_glyph(glyph: dict[str, Any], defs: ClientDefinitions, warnings: list[str]) -> None:
    spell_id = _as_int(glyph.get("source_spell_id"))
    client: dict[str, Any] = {"resolved": False}
    glyph["client"] = client
    if spell_id is None:
        warnings.append("glyph without numeric source_spell_id")
        return
    spell = defs.spell(spell_id)
    if spell is None:
        warnings.append(f"glyph spell {spell_id}: not found in client data")
        return
    props = defs.glyph_for_spell(spell_id)
    client.update(resolved=True, spell_name=spell.name, description=spell.description)
    if props is not None:
        slot = {0: "major", 1: "minor"}.get(props.slot_flags, f"unknown({props.slot_flags})")
        client.update(glyph_id=props.glyph_id, slot_type=slot)
        if slot != glyph.get("category"):
            warnings.append(f"glyph {spell_id}: client slot {slot} != capture category {glyph.get('category')}")
    else:
        warnings.append(f"glyph spell {spell_id}: no GlyphProperties row")


def enrich_talents_result(result: dict[str, Any], defs: ClientDefinitions) -> dict[str, Any]:
    """Return a deep copy of a parse_talents_capture_* result with "client" data added."""
    enriched = copy.deepcopy(result)
    warnings: list[str] = []
    for spec in enriched.get("specs", []):
        for tree in spec.get("trees", []):
            for talent in tree.get("talents", []):
                _enrich_talent(talent, defs, warnings)
    for block in enriched.get("glyphs", {}).values():
        for glyph in block.get("entries", []):
            _enrich_glyph(glyph, defs, warnings)
    enriched["client_warnings"] = warnings
    return enriched
