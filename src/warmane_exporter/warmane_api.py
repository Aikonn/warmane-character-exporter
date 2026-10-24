"""Adapter for the Warmane armory JSON summary endpoint.

Shape verified 2026-10-24 on all four debug characters (see docs/data-sources.md).
The equipment list has no slot index, enchants or gems; those come from the HTML page.
"""

from __future__ import annotations

import json
from urllib.parse import quote

from .identity import SUPPORTED_HOST, SUPPORTED_REALMS

REQUIRED_KEYS = ("name", "realm", "class", "equipment", "talents")


class ApiError(ValueError):
    """The response was not a valid character summary."""


def api_summary_url(name: str, realm: str) -> str:
    realm_canonical = SUPPORTED_REALMS.get(realm.strip().lower())
    if realm_canonical is None:
        raise ValueError("Unsupported realm. Supported realms: Onyxia, Icecrown.")
    if not name.strip():
        raise ValueError("Character name is missing.")
    return f"https://{SUPPORTED_HOST}/api/character/{quote(name.strip(), safe='')}/{realm_canonical}/summary"


def parse_api_summary(text: str) -> dict[str, object]:
    """Validate and normalize a JSON summary body. Raises ApiError otherwise."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ApiError(f"Response is not JSON: {exc.msg}") from exc
    if not isinstance(data, dict):
        raise ApiError("Response JSON is not an object.")
    if "error" in data:
        raise ApiError(f"Source reported an error: {data['error']!r}")
    missing = [key for key in REQUIRED_KEYS if key not in data]
    if missing:
        raise ApiError(f"Missing keys: {', '.join(missing)}")

    warnings: list[str] = []
    items = []
    for raw in data["equipment"]:
        item_id = str(raw.get("item", ""))
        if not item_id.isdigit():
            warnings.append(f"Equipment entry without numeric item id: {raw!r}")
            continue
        items.append({"item_id": int(item_id), "name": raw.get("name", ""), "transmog": raw.get("transmog", "")})

    specs = []
    for tree in data["talents"]:
        points = tree.get("points", [])
        if len(points) != 3:
            warnings.append(f"Talent tree {tree.get('tree')!r} has {len(points)} point values, expected 3.")
        specs.append({"tree": tree.get("tree"), "points": points, "total": sum(int(p) for p in points)})

    return {
        "source": "warmane-json-summary",
        "name": data["name"],
        "realm": data["realm"],
        "level": int(data.get("level", 0) or 0),
        "faction": data.get("faction"),
        "race": data.get("race"),
        "class": data["class"],
        "gender": data.get("gender"),
        "guild": data.get("guild") or None,
        "achievement_points": int(data.get("achievementpoints", 0) or 0),
        "honorable_kills": int(data.get("honorablekills", 0) or 0),
        "equipment": items,
        "talent_trees": specs,
        "professions": data.get("professions", []),
        "pvp_teams": data.get("pvpteams", []),
        "warnings": warnings,
        "limitations": [
            "Equipment has no slot index, enchants or gems.",
            "Talent trees list points per tree only; the active spec is not exposed.",
        ],
    }
