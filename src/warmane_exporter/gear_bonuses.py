"""Socket bonuses, meta gem activation and total stat bonuses of an equipped set.

Works on the equipment list built by report.build_report. Stat values come from the texts of gems,
enchants and socket bonuses (the client's own wording, for example '+23 Spell Power' or '+10 Strength and
+10 Hit Rating'); parts that are not a plain number plus stat name (percent effects, procs, 'Mongoose')
are not counted. Meta gem requirements come from SpellItemEnchantmentCondition (exported from the client):
colour numbers 1 meta, 2 red, 3 yellow, 4 blue; comparators 2 '<', 3 '>', 5 '>='.
"""

from __future__ import annotations

import re
from typing import Any

PRIMARY = ("Strength", "Agility", "Stamina", "Intellect", "Spirit")
COLOR_BITS = {"meta": {1}, "red": {2}, "yellow": {3}, "blue": {4}, "orange": {2, 3}, "purple": {2, 4}, "green": {3, 4},
              "prismatic": {2, 3, 4}}
SOCKET_COLOR = {"meta": 1, "red": 2, "yellow": 3, "blue": 4}
ALIASES = {
    "crit rating": "Critical Strike Rating", "critical strike rating": "Critical Strike Rating",
    "mana regeneration": "Mana per 5 sec", "mana per 5 sec": "Mana per 5 sec",
    "spell crit rating": "Spell Critical Strike Rating", "melee crit rating": "Melee Critical Strike Rating",
    "ranged crit rating": "Ranged Critical Strike Rating",
}
_PART = re.compile(r"^\+?(\d+)\s+([A-Za-z][A-Za-z ]*?)\.?$")
_MP5 = re.compile(r"^\+?(\d+)\s+mana every 5 sec\.?$", re.I)


def stat_name(name: str) -> str:
    low = " ".join(name.lower().split())
    if low in ALIASES:
        return ALIASES[low]
    return " ".join(w.capitalize() for w in low.split())


def parse_bonus(text: str | None) -> dict[str, int]:
    """Plain numeric stats of a gem, enchant or socket bonus text; everything else is ignored."""
    totals: dict[str, int] = {}
    for part in re.split(r"\s+and\s+", text or ""):
        part = part.strip()
        if "%" in part:
            continue
        mp5 = _MP5.match(part)
        if mp5:
            totals["Mana per 5 sec"] = totals.get("Mana per 5 sec", 0) + int(mp5.group(1))
            continue
        found = _PART.match(part)
        if not found:
            continue
        amount, name = int(found.group(1)), found.group(2)
        if name.lower() in ("all stats", "all stat"):
            for stat in PRIMARY:
                totals[stat] = totals.get(stat, 0) + amount
            continue
        key = stat_name(name)
        totals[key] = totals.get(key, 0) + amount
    return totals


def _is_filled(gem: dict[str, Any]) -> bool:
    return not gem.get("empty") and bool(gem.get("id"))


def gem_colors(gem: dict[str, Any]) -> set[int] | None:
    return COLOR_BITS.get(gem.get("color") or "")


def _color_counts(equipment: list[dict[str, Any]]) -> dict[int, int]:
    counts = {1: 0, 2: 0, 3: 0, 4: 0}
    for item in equipment:
        for gem in item.get("gem_details") or []:
            if _is_filled(gem):
                for bit in gem_colors(gem) or ():
                    counts[bit] += 1
    return counts


def requirements_met(requirements: list[list[int]], counts: dict[int, int]) -> bool | None:
    """True / False, or None when a comparator or colour is not understood."""
    for color, comparator, compare_color, value in requirements:
        if color not in counts or (compare_color and compare_color not in counts):
            return None
        left = counts[color]
        right = counts[compare_color] if compare_color else value
        if comparator == 2:
            ok = left < right
        elif comparator == 3:
            ok = left > right
        elif comparator == 5:
            ok = left >= right
        else:
            return None
        if not ok:
            return False
    return True


def socket_bonus_state(item: dict[str, Any]) -> bool | None:
    """Whether every socket holds a gem of a fitting colour; None when a gem colour is unknown."""
    sockets = item.get("sockets") or []
    gems = item.get("gem_details") or []
    result: bool | None = True
    for index, socket in enumerate(sockets):
        wanted = SOCKET_COLOR.get(socket)
        gem = gems[index] if index < len(gems) else None
        if gem is None or not _is_filled(gem):
            return False
        colors = gem_colors(gem)
        if colors is None or wanted is None:
            result = None
        elif wanted not in colors:
            return False
    return result


def analyze(equipment: list[dict[str, Any]]) -> dict[str, Any]:
    """Annotate each item with socket_bonus_info and gem_states, and return the total bonuses.

    Adds to every item: 'socket_bonus_info' ({text, active}) or None, 'gem_states' (per gem: 'active', 'inactive' or None;
    only meta gems get a state). Returns {'totals': {stat: value}, 'warnings': [...]}.
    """
    counts = _color_counts(equipment)
    totals: dict[str, int] = {}
    warnings: list[str] = []

    def add(stats: dict[str, int]) -> None:
        for key, value in stats.items():
            totals[key] = totals.get(key, 0) + value

    for item in equipment:
        if not item.get("scaling_stats"):
            add({stat_name(n): v for n, v in (item.get("stats") or [])})
        if item.get("armor"):
            add({"Armor": item["armor"]})
        add(parse_bonus(item.get("enchant")))
        states: list[str | None] = []
        for gem in item.get("gem_details") or []:
            state = None
            if _is_filled(gem):
                if gem.get("color") == "meta":
                    met = requirements_met(gem["requirements"], counts) if gem.get("requirements") else None
                    state = None if met is None else ("active" if met else "inactive")
                    if met is None:
                        warnings.append(f"{item.get('slot')}: meta gem requirements unknown, effect counted")
                    if met is not False:
                        add(parse_bonus(gem.get("text")))
                else:
                    add(parse_bonus(gem.get("text")))
            states.append(state)
        item["gem_states"] = states
        info = None
        if item.get("socket_bonus"):
            active = socket_bonus_state(item)
            info = {"text": item["socket_bonus"], "active": active}
            if active is not False:
                add(parse_bonus(item["socket_bonus"]))
        item["socket_bonus_info"] = info
    ordered = {k: totals[k] for k in PRIMARY if k in totals}
    ordered.update({k: totals[k] for k in sorted(totals) if k not in PRIMARY})
    return {"totals": ordered, "warnings": warnings}
