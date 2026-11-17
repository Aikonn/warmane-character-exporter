"""Raid readiness checks for the PvE report (tier 1: objective facts, no stat caps, no best-in-slot lists).

Every finding has ``level``, ``area``, ``text`` and machine-readable ``kind`` fields;
socket, talent and glyph findings also include ``count``, and spec findings include
``spec_index``. The PvE report renders the unchanged ``text`` field.
Issues are things that are almost certainly wrong; warnings may be intentional.
The checks assume a level 80 character; below level 80 the talent point maximum is level - 9 and glyph checks are skipped.
"""
from __future__ import annotations

from typing import Any

# slots that take an enchant for everyone (shoulder and head enchants come from reputation or Inscription, still an issue)
ENCHANT_SLOTS = ("Head", "Shoulder", "Back", "Chest", "Wrist", "Hands", "Legs", "Feet")
WEAPON_TYPES = {"one-hand", "main-hand", "off-hand", "two-hand", "shield"}
RANGED_TYPES = {"ranged", "ranged-right"}           # bows, guns, crossbows (wands, thrown and relics are not enchantable)
ARMOR_SLOTS = ("Head", "Shoulder", "Chest", "Wrist", "Hands", "Waist", "Legs", "Feet")
ARMOR_NAMES = {1: "cloth", 2: "leather", 3: "mail", 4: "plate"}
BEST_ARMOR = {"Priest": 1, "Mage": 1, "Warlock": 1, "Rogue": 2, "Druid": 2, "Hunter": 3, "Shaman": 3,
              "Warrior": 4, "Paladin": 4, "Death Knight": 4}
MAX_MAJOR_GLYPHS = 3
BUCKLE_NAME = "Eternal Belt Buckle"


def _label(item: dict[str, Any]) -> str:
    return f"{item.get('slot')} ({item.get('name') or item.get('item_id') or '?'})"


def _finding(
    level: str,
    area: str,
    text: str,
    kind: str,
    *,
    count: int | None = None,
    spec_index: int | None = None,
) -> dict[str, Any]:
    finding: dict[str, Any] = {"level": level, "area": area, "text": text, "kind": kind}
    if count is not None:
        finding["count"] = count
    if spec_index is not None:
        finding["spec_index"] = spec_index
    return finding


def _gear_finding(
    level: str,
    item: dict[str, Any],
    text: str,
    kind: str,
    *,
    count: int | None = None,
) -> dict[str, Any]:
    finding = _finding(level, _label(item), text, kind, count=count)
    finding["slot"] = item.get("slot")
    return finding


def _has_profession(report: dict[str, Any], name: str) -> bool:
    return any(isinstance(p, dict) and (p.get("name") or "").lower() == name.lower() for p in report.get("professions") or [])


def check_gear(report: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    cls = (report.get("identity") or {}).get("class")
    enchanting = _has_profession(report, "Enchanting")
    for item in report.get("equipment") or []:
        slot = item.get("slot")
        kind = item.get("inventory_type")
        needs = slot in ENCHANT_SLOTS
        if slot in ("Main Hand", "Off Hand"):
            needs = kind in WEAPON_TYPES and cls != "Hunter"      # hunter melee weapons are stat sticks only
        elif slot == "Ranged":
            needs = cls == "Hunter" and kind in RANGED_TYPES
        elif slot in ("Finger 1", "Finger 2"):
            needs = enchanting
        if needs and not item.get("enchant_id") and not item.get("enchant"):
            why = " (the character is an Enchanter)" if slot in ("Finger 1", "Finger 2") else ""
            enchant_kind = "ring_enchant" if slot in ("Finger 1", "Finger 2") else "enchant"
            out.append(_gear_finding("issue", item, f"No enchant{why}.", enchant_kind))
        if item.get("sockets_empty"):
            out.append(_gear_finding(
                "issue", item, f"{item['sockets_empty']} empty gem socket(s).", "sockets",
                count=item["sockets_empty"],
            ))
        for gem, state in zip(item.get("gem_details") or [], item.get("gem_states") or []):
            if state == "inactive":
                out.append(_gear_finding(
                    "issue", item, f"Meta gem is not active: {gem.get('text') or 'meta gem'}.", "meta",
                ))
        if slot == "Waist" and item.get("sockets") is not None and not item.get("buckle"):
            out.append(_gear_finding(
                "issue", item, f"{BUCKLE_NAME} missing (extra gem socket on the belt).", "buckle",
            ))
        best = BEST_ARMOR.get(cls or "")
        sub = item.get("item_subclass")
        if best and slot in ARMOR_SLOTS and item.get("item_class") == 4 and sub in ARMOR_NAMES and sub < best:
            out.append(_gear_finding(
                "warning", item,
                f"{ARMOR_NAMES[sub].capitalize()} armor; a {cls} can wear {ARMOR_NAMES[best]}.",
                "armor",
            ))
    return out


def check_specs(report: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    level = (report.get("identity") or {}).get("level")
    level = level if isinstance(level, int) else 80
    max_points = max(level - 9, 0)
    for spec_index, spec in enumerate(report.get("specializations") or []):
        label = spec.get("label") or "Specialization"
        spent = sum(x for x in spec.get("split") or [] if isinstance(x, int))
        if spent == 0:
            out.append(_finding(
                "warning", label,
                "No talent points spent: dual specialization is probably not purchased, so this "
                "specialization was not checked.",
                "no_talents", spec_index=spec_index,
            ))
            continue
        if spent < max_points:
            unspent = max_points - spent
            out.append(_finding(
                "issue", label, f"{unspent} unspent talent point(s) ({spent} of {max_points} spent).",
                "talents", count=unspent, spec_index=spec_index,
            ))
        if level >= 80:
            major = sum(1 for g in spec.get("glyphs") or [] if g.get("category") == "major")
            if major < MAX_MAJOR_GLYPHS:
                empty = MAX_MAJOR_GLYPHS - major
                out.append(_finding(
                    "issue", label,
                    f"{empty} major glyph slot(s) empty ({major} of {MAX_MAJOR_GLYPHS} filled).",
                    "glyphs", count=empty, spec_index=spec_index,
                ))
    return out


def run_checks(report: dict[str, Any]) -> dict[str, Any]:
    findings = check_gear(report) + check_specs(report)
    return {"issues": [f for f in findings if f["level"] == "issue"],
            "warnings": [f for f in findings if f["level"] == "warning"]}
