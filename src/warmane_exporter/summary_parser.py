from __future__ import annotations

import re
from html import unescape
from pathlib import Path


def parse_summary_capture_file(path: Path) -> dict[str, object]:
    html = path.read_text(encoding="utf-8")
    return parse_summary_capture_html(html=html, source_name=str(path))


def parse_summary_capture_html(html: str, source_name: str = "<memory>") -> dict[str, object]:
    identity = _parse_identity(html)
    navigation = _parse_navigation(html)
    character_stats = _parse_character_stats(html)
    equipment = _parse_equipment(html)
    specializations = _parse_specializations(html)
    recent_achievements = _parse_recent_achievements(html)
    model_viewer = _parse_model_viewer_items(html)

    ambiguous_slots = [slot for slot in equipment["slots"] if slot.get("slot_name") is None]

    return {
        "parser_mode": "offline_rendered_dom_text_only",
        "source_name": source_name,
        "identity": identity,
        "character_stats": character_stats,
        "equipment": equipment,
        "specializations": {
            "specs": specializations,
            "active_spec_status": "unknown_not_explicit_in_capture",
        },
        "navigation": navigation,
        "recent_achievements": {
            "partial_list_from_summary_capture": True,
            "items": recent_achievements,
        },
        "glyphs": {
            "status": "not_present_in_this_capture",
            "note": "No glyph data was found in this capture; this does not imply the character has no glyphs.",
        },
        "model_viewer_item_ids": {
            "items": model_viewer,
            "note": "Model-viewer identifiers are captured separately and are not treated as equipped item IDs.",
        },
        "unsupported_or_ambiguous": {
            "equipment_slots_without_explicit_labels": len(ambiguous_slots),
            "notes": [
                "Most equipment slots have no explicit textual slot name in this markup; layout position is preserved as evidence.",
                "Navigation links indicate other sections exist but their page content is not captured here.",
            ],
        },
    }


def _parse_identity(html: str) -> dict[str, object]:
    name_match = re.search(
        r'<div class="name">\s*([^<]+?)\s*(?:<span class="guild-name"><a [^>]*>([^<]+)</a></span>)?\s*</div>',
        html,
        flags=re.S,
    )
    level_match = re.search(r'<div class="level-race-class">\s*([^<]+)\s*</div>', html, flags=re.S)

    display_line = _clean_text(level_match.group(1)) if level_match else None
    parsed = {
        "level": None,
        "race_class_realm_display": display_line,
    }
    if display_line:
        m = re.search(r"Level\s+(\d+)\s+(.+)", display_line)
        if m:
            parsed["level"] = int(m.group(1))

    return {
        "name": _clean_text(name_match.group(1)) if name_match else None,
        "guild": _clean_text(name_match.group(2)) if name_match and name_match.group(2) else None,
        "level_race_class_realm_display": display_line,
        "parsed": parsed,
    }


def _parse_navigation(html: str) -> dict[str, object]:
    block_match = re.search(r'<div id="inpage-navigation">\s*<ul>(.*?)</ul>', html, flags=re.S)
    if not block_match:
        return {"links": [], "not_captured_sections": []}

    links = []
    not_captured = []
    for match in re.finditer(r'<a href="([^"]+)"[^>]*>([^<]+)</a>', block_match.group(1), flags=re.S):
        href = unescape(match.group(1))
        label = _clean_text(match.group(2))
        captured_here = label.upper() == "PROFILE"
        links.append({"label": label, "href": href, "captured_in_this_file": captured_here})
        if not captured_here:
            not_captured.append({"label": label, "href": href})

    return {
        "links": links,
        "not_captured_sections": not_captured,
    }


def _parse_character_stats(html: str) -> list[dict[str, object]]:
    block_match = re.search(r'<div class="character-stats">(.*?)</div>\s*</div>\s*<div class="information-right">', html, flags=re.S)
    if not block_match:
        return []

    block = block_match.group(1)
    panels: list[dict[str, object]] = []
    for stub_match in re.finditer(r'<div class="stub(?: [^"]+)?">\s*<div class="text">(.*?)</div>', block, flags=re.S):
        lines = _extract_lines_with_breaks(stub_match.group(1))
        panel = _parse_stats_panel(lines)
        if panel is not None:
            panels.append(panel)
    return panels


def _parse_stats_panel(lines: list[str]) -> dict[str, object] | None:
    if not lines:
        return None

    panel_name = lines[0]
    subsection = panel_name
    entries = []
    for line in lines[1:]:
        if ":" not in line:
            subsection = line
            continue
        label, value = [part.strip() for part in line.split(":", 1)]
        entries.append(
            {
                "subsection": subsection,
                "label": label,
                "displayed_value": value,
                "unit": "%" if value.endswith("%") else None,
            }
        )

    return {
        "panel": panel_name,
        "entries": entries,
        "raw_lines": lines,
    }


def _parse_equipment(html: str) -> dict[str, object]:
    block_match = re.search(r'<div class="item-model">(.*?)<div class="model"', html, flags=re.S)
    if not block_match:
        return {"slots": []}
    block = block_match.group(1)

    slot_pattern = re.compile(
        r'(?s)<div class="item-(left|right|bottom)">|<div class="item-slot">\s*(.*?)\s*</div>\s*</div>'
    )
    slots = []
    current_group = "unknown"
    index_by_group: dict[str, int] = {"left": 0, "right": 0, "bottom": 0, "unknown": 0}

    for token in slot_pattern.finditer(block):
        group_name = token.group(1)
        if group_name:
            current_group = group_name
            continue

        chunk = token.group(2) or ""
        index_by_group[current_group] = index_by_group.get(current_group, 0) + 1
        slot_index = index_by_group[current_group]
        slot_key = f"{current_group}_{slot_index}"
        slot = {
            "slot_key": slot_key,
            "evidence": {
                "source": "item-model layout",
                "group": current_group,
                "index_in_group": slot_index,
            },
            "slot_name": None,
            "is_empty": False,
        }

        tooltip_match = re.search(r'data-tooltip="([^"]+)"', chunk)
        if tooltip_match:
            slot["slot_name"] = _clean_text(tooltip_match.group(1))
            slot["is_empty"] = True
            slot["empty_evidence"] = "explicit data-tooltip"
            slots.append(slot)
            continue

        rel_match = re.search(r'rel="([^"]+)"', chunk)
        href_item_match = re.search(r'href="[^"]*item=(\d+)"', chunk)
        if rel_match and href_item_match:
            rel_payload = _parse_rel_payload(rel_match.group(1))
            slot["item_reference"] = {
                "href_item_id": href_item_match.group(1),
                "raw_rel": unescape(rel_match.group(1)),
                "namespaces": rel_payload,
            }
            slot["ambiguity_note"] = "No explicit textual slot name in this markup; layout position preserved."
            slots.append(slot)
            continue

        slot["ambiguity_note"] = "Slot markup was present but item/empty markers were not recognized."
        slots.append(slot)

    return {"slots": slots}


def _parse_rel_payload(rel_payload: str) -> dict[str, object]:
    decoded = unescape(rel_payload)
    values: dict[str, str] = {}
    for token in decoded.split("&"):
        if "=" not in token:
            continue
        key, value = token.split("=", 1)
        values[key] = value

    gems_raw = values.get("gems")
    gem_positions = []
    if gems_raw is not None:
        for idx, gem_token in enumerate(gems_raw.split(":"), start=1):
            gem_positions.append({"position": idx, "raw_value": gem_token})

    return {
        "item": values.get("item"),
        "ench": values.get("ench"),
        "gems": gems_raw,
        "gem_positions": gem_positions,
    }


def _parse_specializations(html: str) -> list[dict[str, object]]:
    block_match = re.search(r'<div class="specialization">(.*?)</div>\s*<div class="clear"></div>\s*<h3>Player vs Player</h3>', html, flags=re.S)
    if not block_match:
        return []

    specs = []
    for match in re.finditer(r'<div class="text">\s*([^<\n]+?)\s*<span class="value">\s*([0-9]+\s*/\s*[0-9]+\s*/\s*[0-9]+)\s*</span>', block_match.group(1), flags=re.S):
        name = _clean_text(match.group(1))
        points_raw = _clean_text(match.group(2))
        points = [int(x.strip()) for x in points_raw.split("/")]
        specs.append(
            {
                "name": name,
                "tree_points_raw": points_raw,
                "tree_points": points,
                "active_status": "unknown_not_explicit_in_capture",
            }
        )
    return specs


def _parse_recent_achievements(html: str) -> list[dict[str, str]]:
    block_match = re.search(r'<div class="recent-activity">(.*?)</div>\s*</div>\s*</div>\s*</div>', html, flags=re.S)
    if not block_match:
        return []

    items = []
    pattern = re.compile(
        r'achievement=(\d+)".*?Earned <span class="name"><a [^>]*>([^<]+)</a></span>.*?achievement <span class="time">([^<]+)</span>',
        flags=re.S,
    )
    for match in pattern.finditer(block_match.group(1)):
        items.append(
            {
                "achievement_id": match.group(1),
                "name": _clean_text(match.group(2)),
                "time_display": _clean_text(match.group(3)),
            }
        )
    return items


def _parse_model_viewer_items(html: str) -> list[dict[str, int]]:
    model_match = re.search(r"var\s+charactermodel\s*=\s*\{(.*?)\};", html, flags=re.S)
    if not model_match:
        return []
    model_block = model_match.group(1)
    if "items:" not in model_block:
        return []
    pairs = []
    for item_match in re.finditer(r"\[(\d+)\s*,\s*(\d+)\]", model_block):
        pairs.append({"viewer_slot_id": int(item_match.group(1)), "viewer_model_item_id": int(item_match.group(2))})
    return pairs


def _extract_lines_with_breaks(fragment: str) -> list[str]:
    normalized = re.sub(r"(?i)<br\s*/?>", "\n", fragment)
    without_tags = re.sub(r"<[^>]+>", "", normalized)
    text = unescape(without_tags)
    lines = [line.strip() for line in text.splitlines()]
    return [line for line in lines if line]


def _clean_text(value: str) -> str:
    text = unescape(value)
    text = re.sub(r"\s+", " ", text)
    return text.strip()
