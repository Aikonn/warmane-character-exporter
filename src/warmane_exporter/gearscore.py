"""GearScore, computed the way the GearScoreLite family of addons does (TacoTip version for WotLK).

Per item: floor(((item level - A) / B) * slot modifier * 1.8618 * quality scale), where (A, B) depend on
rarity (the "above item level 120" table is used for every WotLK item), the slot modifier on the
inventory type, and legendary items count as epic times 1.3. The character's GearScore is the floor of
the sum over all equipped items except shirt and tabard. Adjustments in the addon: hunters count melee
weapons x0.3164 and the ranged weapon x5.3224, and dual two-handers (Titan's Grip) count x0.5 each.
This version does not subtract anything for missing enchants or gems.
Reference: https://github.com/anzz1/TacoTip/blob/master/gearscore.lua
Item level comes from the AzerothCore item data, not from Warmane.
"""

from __future__ import annotations

from math import floor
from typing import Any

SCALE = 1.8618
FORMULA_HIGH = {4: (91.45, 0.65), 3: (81.375, 0.8125), 2: (73.0, 1.0)}      # item level above 120
FORMULA_LOW = {4: (26.0, 1.2), 3: (0.75, 1.8), 2: (8.0, 2.0), 1: (0.0, 2.25)}
SLOT_MOD = {
    "head": 1.0, "neck": 0.5625, "shoulder": 0.75, "chest": 1.0, "robe": 1.0, "waist": 0.75, "legs": 1.0, "feet": 0.75,
    "wrist": 0.5625, "hands": 0.75, "finger": 0.5625, "trinket": 0.5625, "back": 0.5625,
    "one-hand": 1.0, "main-hand": 1.0, "off-hand": 1.0, "shield": 1.0, "held-in-off-hand": 1.0, "two-hand": 2.0,
    "ranged": 0.3164, "thrown": 0.3164, "ranged-right": 0.3164, "relic": 0.3164,
}
RARITY = {"poor": 0, "common": 1, "uncommon": 2, "rare": 3, "epic": 4, "legendary": 5, "artifact": 6, "heirloom": 7}
EXCLUDED_SLOTS = ("Shirt", "Tabard")


def item_score(quality: str | None, item_level: int | None, inventory_type: str | None) -> tuple[int, int] | None:
    """(GearScore, counted item level) for one item, or None when the data needed is missing."""
    rarity = RARITY.get((quality or "").lower())
    if rarity is None or item_level is None or inventory_type not in SLOT_MOD:
        return None
    quality_scale, level = 1.0, float(item_level)
    if rarity == 5:
        quality_scale, rarity = 1.3, 4
    elif rarity in (0, 1):
        quality_scale, rarity = 0.005, 2
    elif rarity == 7:
        rarity, level = 3, 187.05
    if not 2 <= rarity <= 4:
        return 0, int(level)
    a, b = (FORMULA_HIGH if level > 120 else FORMULA_LOW)[rarity]
    score = floor(((level - a) / b) * SLOT_MOD[inventory_type] * SCALE * quality_scale)
    return max(score, 0), 0 if level == 187.05 else int(level)


def character_score(equipment: list[dict[str, Any]], class_name: str | None) -> dict[str, Any]:
    """GearScore and average item level of the equipment list built by report.build_report."""
    hunter = (class_name or "").lower() == "hunter"
    by_slot = {e.get("slot"): e for e in equipment}
    main, off = by_slot.get("Main Hand"), by_slot.get("Off Hand")
    titan = 1.0
    if main and off and "two-hand" in (main.get("inventory_type"), off.get("inventory_type")):
        titan = 0.5
    total, levels, counted, unknown, per_item = 0.0, 0, 0, 0, {}
    for e in equipment:
        slot = e.get("slot")
        if slot in EXCLUDED_SLOTS:
            continue
        scored = item_score(e.get("quality"), e.get("item_level"), e.get("inventory_type"))
        if scored is None:
            unknown += 1
            continue
        score, level = scored
        if hunter:
            if slot in ("Main Hand", "Off Hand"):
                score = score * 0.3164
            elif slot == "Ranged":
                score = score * 5.3224
        if slot in ("Main Hand", "Off Hand"):
            score = score * titan
        per_item[slot] = floor(score)
        total += score
        levels += level
        counted += 1
    return {
        "gearscore": floor(total) if counted and not unknown else None,
        "average_item_level": floor(levels / counted) if counted and not unknown else None,
        "items": counted, "unknown_items": unknown, "per_item": per_item,
        "adjustments": [x for x, on in (("hunter weapon weights", hunter), ("Titan's Grip x0.5", titan != 1.0)) if on],
    }
