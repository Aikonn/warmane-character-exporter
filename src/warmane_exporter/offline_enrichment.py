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


def _add_rendered(client: dict[str, Any], key: str, defs: ClientDefinitions, spell_id: int) -> None:
    """Add <key>_rendered (numbers filled in from the client) and <key>_unresolved."""
    rendered = defs.render_spell_description(spell_id)
    if rendered is not None:
        client[f"{key}_rendered"] = rendered.text
        client[f"{key}_unresolved"] = rendered.unresolved


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
        _add_rendered(client, "selected_rank_description", defs, selected)


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
    _add_rendered(client, "description", defs, spell_id)
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


# Inventory types that may legitimately appear in each paperdoll slot (3.3.5a).
SLOT_INVENTORY_TYPES = {
    "Head": {1}, "Neck": {2}, "Shoulder": {3}, "Back": {16}, "Chest": {5, 20},
    "Shirt": {4}, "Tabard": {19}, "Wrist": {9}, "Hands": {10}, "Waist": {6},
    "Legs": {7}, "Feet": {8}, "Finger 1": {11}, "Finger 2": {11},
    "Trinket 1": {12}, "Trinket 2": {12},
    "Main Hand": {13, 17, 21}, "Off Hand": {13, 14, 22, 23},
    "Ranged": {15, 25, 26, 28},
}


def enrich_summary_result(result: dict[str, Any], defs: ClientDefinitions) -> dict[str, Any]:
    """Return a deep copy of a summary parse result with "client" data on equipped items.

    Enchant and gem codes are SpellItemEnchantment IDs (verified); gem code 0 means an
    empty socket. Item names are not available offline.
    """
    enriched = copy.deepcopy(result)
    warnings: list[str] = []
    for slot in enriched.get("equipment", {}).get("slots", []):
        reference = slot.get("item_reference")
        if not reference:
            continue
        ns = reference.get("namespaces", {})
        client: dict[str, Any] = {}
        slot["client"] = client
        item_id = _as_int(ns.get("item") or reference.get("href_item_id"))
        info = defs.item(item_id) if item_id is not None else None
        if info is None:
            warnings.append(f"{slot.get('slot_key')}: item {item_id} not in any definition source")
        else:
            client["item"] = {
                "item_id": info.item_id,
                "class": info.item_class,
                "subclass": info.item_subclass,
                "inventory_type": info.inventory_type_name,
            }
            inferred = (slot.get("layout_inference") or {}).get("inferred_slot_name")
            allowed = SLOT_INVENTORY_TYPES.get(inferred or "")
            if allowed is not None:
                client["slot_check"] = "ok" if info.inventory_type in allowed else "mismatch"
                if client["slot_check"] == "mismatch":
                    warnings.append(
                        f"{slot.get('slot_key')}: item {item_id} is {info.inventory_type_name}, "
                        f"inferred slot is {inferred}"
                    )
        acore_fn = getattr(defs, "acore_item", None)
        acore = acore_fn(item_id) if (acore_fn and item_id is not None) else None
        if acore is not None:
            positions = ns.get("gem_positions", [])
            filled = sum(1 for p in positions if _as_int(p.get("raw_value")))
            client["acore"] = {
                "name": acore.name,
                "quality": acore.quality_name,
                "item_level": acore.item_level,
                "stats": [list(s) for s in acore.stats],
                "sockets": list(acore.sockets),
                "socket_bonus_enchant_id": acore.socket_bonus_enchant_id,
                "gems_filled": filled,
                "sockets_empty": max(len(acore.sockets) - filled, 0),
                "scaling_stats": acore.scaling,
            }
            if filled > len(acore.sockets):
                warnings.append(
                    f"{slot.get('slot_key')}: {filled} gems but AzerothCore lists {len(acore.sockets)} sockets "
                    "(extra socket, for example a belt buckle or blacksmith socket)"
                )
        ench = _as_int(ns.get("ench"))
        if ench:
            text = defs.enchant_text(ench)
            client["enchant"] = {"id": ench, "text": text}
            if text is None:
                warnings.append(f"{slot.get('slot_key')}: enchant {ench} text unresolved (no text source has it)")
        gems = []
        for position in ns.get("gem_positions", []):
            code = _as_int(position.get("raw_value"))
            if not code:
                gems.append({"position": position.get("position"), "id": code or 0, "empty": True})
                continue
            text = defs.enchant_text(code)
            gems.append({"position": position.get("position"), "id": code, "text": text})
            if text is None:
                warnings.append(f"{slot.get('slot_key')}: gem code {code} text unresolved (no text source has it)")
        if gems:
            client["gems"] = gems
    enriched["client_warnings"] = warnings
    return enriched
