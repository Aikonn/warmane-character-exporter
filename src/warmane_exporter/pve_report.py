"""PvE report as one self-contained HTML file (double-click to read, or attach to an AI chat).

python -m warmane_exporter.pve_report NAME REALM [--cache-dir DIR] [--output FILE]

Offline: reads .warmane-cache/exports/<name>-<realm>.json written by warmane_exporter.export and
writes <name>-<realm>-pve.html next to it. No scripts, no external files or images; plain tables.
Everything shown is an observed value from the armory or a labeled derived value; "-" means the
armory shows no entry for that statistic. Text from the armory is HTML-escaped.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import OrderedDict
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any

from .gearscore import character_score
from .snapshot import character_page_url
from .report import BELT_BUCKLE
from .identity import SUPPORTED_REALMS

# Statistics categories that hold boss kill rows, in display order: (id, heading).
PROGRESS_CATEGORIES = (
    (14821, "Classic"), (14822, "The Burning Crusade"), (14823, "Wrath of the Lich King"),
    (14963, "Secrets of Ulduar"), (15021, "Call of the Crusade"), (15062, "Fall of the Lich King"),
)
OLDER_HEADINGS = ("Classic", "The Burning Crusade")
OVERVIEW_CATEGORY = 14807     # Dungeons & Raids: entered / completed counters
DEATHS_CATEGORY = 125         # Deaths > Dungeons: "Deaths in <raid>"
ACHIEVEMENT_PARENT = 168      # Dungeons & Raids

ACHIEVEMENT_ORDER = (
    "Dungeons & Raids", "Classic", "The Burning Crusade", "Lich King Dungeon", "Lich King Heroic",
    "Lich King 10-Player Raid", "Lich King 25-Player Raid", "Secrets of Ulduar 10", "Secrets of Ulduar 25",
    "Call of the Crusade 10", "Call of the Crusade 25", "Fall of the Lich King 10", "Fall of the Lich King 25",
)
BOSS_INSTANCE = {"Malygos": "The Eye of Eternity"}
# Instance names differ between normal and heroic rows (Warmane wording). Key = lower case without "the ".
KEY_FIX = {"ahn'kahet: the old kingdom": "ahn'kahet", "cot: stratholme": "caverns of time: stratholme",
           "chamber of the aspects": "obsidian sanctum", "wintergrasp": "vault of archavon"}
DISPLAY = {"ahn'kahet": "Ahn'kahet: The Old Kingdom", "caverns of time: stratholme": "Caverns of Time: Stratholme",
           "obsidian sanctum": "Obsidian Sanctum (Chamber of the Aspects)", "vault of archavon": "Vault of Archavon (Wintergrasp)",
           "nexus": "The Nexus"}
_ROW = re.compile(r"^(?P<label>.+?) \((?P<ctx>[^()]+)\)$")
_VERB = re.compile(r"\s+(kills|victories|defeated|rescues|escapes)$")
_NONE = {"- -", "-", ""}


def _count(value: Any) -> int | None:
    """Armory counters: digits -> int, '- -' -> 0 meaning no entry; anything else -> None (unparsed)."""
    text = str(value).strip().replace(",", "")
    if text in _NONE:
        return 0
    return int(text) if text.isdigit() else None


def instance_key(name: str) -> str:
    key = name.strip().lower()
    key = key[4:] if key.startswith("the ") else key
    return KEY_FIX.get(key, key)


def parse_progress_row(name: str) -> dict[str, Any] | None:
    """Split a statistics row such as 'Sindragosa kills (Heroic Icecrown 25 player)'.

    Returns {boss, instance, key, size, heroic} or None when the row does not follow the pattern.
    """
    match = _ROW.match(name)
    if not match:
        return None
    label, ctx = match.group("label"), match.group("ctx")
    heroic = bool(re.search(r"Heroic|Grand Crusader", f"{label} {ctx}"))
    size_match = re.search(r"(\d+) player", ctx)
    size = int(size_match.group(1)) if size_match else None
    instance = re.sub(r"\s*\d+ player", "", re.sub(r"\bHeroic\s+", "", ctx)).strip()
    instance = instance.replace("Trial of the Grand Crusader", "Trial of the Crusader")
    boss = _VERB.sub("", label)
    boss = re.sub(r"^Victories over (the )?", "", boss)
    completion = re.match(r"^Times completed the (.+)$", boss)
    if completion:
        boss, instance = "Times completed", completion.group(1).replace("Trial of the Grand Crusader", "Trial of the Crusader")
    if not instance:
        instance = BOSS_INSTANCE.get(boss, "")
    if not instance:
        return None
    key = instance_key(instance)
    return {"boss": boss, "instance": DISPLAY.get(key, instance), "key": key, "size": size, "heroic": heroic}


def build_progression(statistics: list[dict[str, Any]]) -> dict[str, Any]:
    by_id = {c["category_id"]: c for c in statistics}
    groups = []
    all_instances: dict[str, dict[str, Any]] = {}   # an instance spread over several categories (Vault of Archavon) is merged
    for category_id, heading in PROGRESS_CATEGORIES:
        category = by_id.get(category_id)
        if category is None:
            continue
        instances: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
        other = []
        for row in category["rows"]:
            parsed = parse_progress_row(row["name"])
            count = _count(row["value"])
            if parsed is None or count is None:
                other.append({"name": row["name"], "value": row["value"]})
                continue
            inst = all_instances.get(parsed["key"])
            if inst is None:
                inst = all_instances[parsed["key"]] = {"name": parsed["instance"], "bosses": OrderedDict(), "modes": set()}
                instances[parsed["key"]] = inst
            mode = (parsed["size"], parsed["heroic"])
            inst["modes"].add(mode)
            inst["bosses"].setdefault(parsed["boss"], {})[mode] = count
        groups.append({"heading": heading, "instances": list(instances.values()), "other": other})
    wotlk_raids, wotlk_dungeons, older = [], [], []
    for group in groups:
        for inst in group["instances"]:
            if group["heading"] in OLDER_HEADINGS:
                older.append(inst)
            elif any(size in (10, 25) for size, _ in inst["modes"]):
                wotlk_raids.append(inst)
            else:
                wotlk_dungeons.append(inst)
    overview = [{"name": r["name"], "value": r["value"]} for r in (by_id.get(OVERVIEW_CATEGORY) or {}).get("rows", [])]
    deaths = [{"name": r["name"], "value": r["value"]} for r in (by_id.get(DEATHS_CATEGORY) or {}).get("rows", [])
              if r["name"].startswith(("Deaths in", "Total"))]
    return {"groups": groups, "wotlk_raids": wotlk_raids, "wotlk_dungeons": wotlk_dungeons, "older": older,
            "overview": overview, "deaths": deaths}


def _mode_label(mode: tuple[int | None, bool]) -> str:
    size, heroic = mode
    base = f"{size}-player " if size else ""
    return f"{base}{'heroic' if heroic else 'normal'}"


def _sorted_modes(modes: set) -> list[tuple[int | None, bool]]:
    return sorted(modes, key=lambda m: (m[0] or 0, m[1]))


def build_pve_report(report: dict[str, Any]) -> dict[str, Any]:
    stats = report.get("statistics") or []
    achievements = (report.get("achievements") or {}).get("entries") or []
    category_names: "OrderedDict[int, str]" = OrderedDict()
    grouped: dict[int, list[dict[str, Any]]] = {}
    for entry in achievements:
        if entry.get("parent_category_id") == ACHIEVEMENT_PARENT or entry.get("category_id") == ACHIEVEMENT_PARENT:
            cid = entry["category_id"]
            category_names.setdefault(cid, entry["category"])
            grouped.setdefault(cid, []).append(entry)
    ach_groups = []
    order = {n: i for i, n in enumerate(ACHIEVEMENT_ORDER)}
    for cid, name in sorted(category_names.items(), key=lambda kv: order.get(kv[1], len(order))):
        entries = grouped[cid]
        ach_groups.append({
            "category_id": cid, "name": name,
            "earned": sorted([e for e in entries if e["earned"]], key=lambda e: (e.get("earned_date") or "", e["id"])),
            "missing": [e for e in entries if not e["earned"]],
        })
    score = character_score(report.get("equipment", []), (report.get("identity") or {}).get("class"))
    currencies = [r for c in stats if c["category_id"] == 130 for r in c["rows"]
                  if re.search(r"Emblems? of|Badges? of", r["name"])]
    return {
        "report": report,
        "progression": build_progression(stats),
        "achievement_groups": ach_groups,
        "gearscore": score,
        "currencies": currencies,
    }


# ---------------------------------------------------------------------------- HTML

CSS = """
body{font-family:Segoe UI,Arial,sans-serif;max-width:1100px;margin:1.5em auto;padding:0 1em;color:#111;line-height:1.4}
h1{border-bottom:2px solid #444;padding-bottom:.2em} h2{margin-top:1.8em;border-bottom:1px solid #999}
table{border-collapse:collapse;margin:.6em 0;font-size:.92em} th,td{border:1px solid #bbb;padding:.25em .6em;text-align:left;vertical-align:top}
th{background:#eee} td.n{text-align:right} .muted{color:#555} .off{color:#888} .note{background:#f6f6f0;border-left:4px solid #aa8;padding:.4em .8em}
.warn{background:#fde8e8;border:1px solid #c33;border-left:6px solid #b00;color:#600;padding:.5em .9em;margin:.6em 0}
details{margin:.4em 0} details.big{margin-top:1.8em;border-bottom:1px solid #999} details.big>summary{list-style-position:inside} details.big>summary>h2{display:inline;margin:0;border:0} summary{cursor:pointer}
"""


def _e(value: Any) -> str:
    return escape("" if value is None else str(value))


class Html(str):
    """Markup that is already escaped (item links)."""


def _cell(value: Any) -> str:
    return str(value) if isinstance(value, Html) else _e(value)


def _table(headers: list[str], rows: list[list[Any]], numeric_from: int | None = None) -> str:
    head = "".join(f"<th>{_e(h)}</th>" for h in headers)
    body = []
    for row in rows:
        cells = []
        for i, cell in enumerate(row):
            cls = ' class="n"' if numeric_from is not None and i >= numeric_from else ""
            text = "<br>".join(_cell(c) for c in cell) if isinstance(cell, (list, tuple)) else _cell(cell)
            cells.append(f"<td{cls}>{text}</td>")
        body.append("<tr>" + "".join(cells) + "</tr>")
    return f"<table><tr>{head}</tr>{''.join(body)}</table>"


def _count_text(value: int | None) -> str:
    return "-" if not value else str(value)


ITEM_URL = "https://wotlk.cavernoftime.com/item={}"


def _bonus_text(value: int) -> str:
    return f"+{value}"


def _off(text: str) -> Html:
    return Html(f'<span class="off">{_e(text)}</span>')


def _set_html(report: dict[str, Any]) -> str:
    sets = report.get("set_bonuses") or []
    if not sets:
        return ""
    parts = ["<h3>Set bonuses</h3>"]
    for entry in sets:
        lines = [f"<b>{_e(entry['name'])} ({entry['equipped']}/{entry['size']})</b>"]
        for b in entry["bonuses"]:
            state = "active" if b["active"] else "inactive"
            line = _e(f"({b['threshold']}) Set: {b['text'] or 'text unavailable'} ({state})")
            lines.append(line if b["active"] else f'<span class="off">{line}</span>')
        parts.append("<p>" + "<br>".join(lines) + "</p>")
    return "".join(parts)


def _gear_section(report: dict[str, Any], score: dict[str, Any]) -> str:
    rows = []
    for e in report.get("equipment", []):
        lines = []
        if e.get("armor"):
            lines.append(f"+{e['armor']} armor")
        lines.extend(f"+{v} {n}" for n, v in (e.get("stats") or []))
        if e.get("scaling_stats"):
            lines.append("(scaling item: stat values depend on character level)")
        info = e.get("socket_bonus_info")
        if info:
            state = {True: "active", False: "inactive"}.get(info["active"], "unknown")
            line = f"Socket bonus ({state}): {info['text']}"
            lines.append(_off(line) if info["active"] is False else line)
        lines.extend(f"{x['trigger']}: {x['text']}" for x in e.get("effects") or [])
        # base stats stay on one line, everything after them starts on a new line
        stat_count = len(lines) - len(e.get("effects") or []) - (1 if info else 0)
        if stat_count > 1:
            lines[:stat_count] = [", ".join(lines[:stat_count])]
        if e.get("gem_lines") is not None and (e.get("gem_lines") or e.get("sockets") is not None):
            gems = [_off(g) if g.endswith("(inactive)") else g for g in e["gem_lines"]]
        else:
            gems = list(e.get("gems") or [])
        enchant = [e["enchant"]] if e.get("enchant") else []
        if e.get("buckle"):
            enchant.append(BELT_BUCKLE)
        label = f"{e.get('name') or '?'} ({e.get('item_id')})"
        if e.get("item_id"):
            label = Html(f'<a href="{_e(ITEM_URL.format(e["item_id"]))}">{_e(e.get("name") or "?")}</a> ({e["item_id"]})')
        if e.get("transmog"):
            label = Html(str(label) + _e(f", transmog: {e['transmog']}")) if isinstance(label, Html) else label + f", transmog: {e['transmog']}"
        item_score_value = score["per_item"].get(e.get("slot"))
        rows.append([e.get("slot"), label, e.get("quality") or "?", e.get("item_level") if e.get("item_level") is not None else "?",
                     item_score_value if item_score_value is not None else "", lines, enchant, gems])
    totals = report.get("bonus_totals") or {}
    totals_html = ""
    if totals:
        totals_html = ("<h3>Total base stat bonuses from gear, gems and enchants</h3>"
                       + _table(["Stat", "Bonus"], [[n, _bonus_text(v)] for n, v in totals.items()])
                       + '<p class="muted">Sum of item base stats, armor, enchants, gems, active socket bonuses and active meta gems. '
                         "Special effects (procs, use effects, percent bonuses, weapon enchants such as Mongoose) are not counted; "
                         "stat values of scaling items are not counted.</p>")
    note = ""
    if score["gearscore"] is not None:
        extra = f" Adjustments applied: {', '.join(score['adjustments'])}." if score["adjustments"] else ""
        note = (f'<p>Derived: average item level <b>{score["average_item_level"]}</b> and GearScore <b>{score["gearscore"]}</b> '
                f'over {score["items"]} equipped items (shirt and tabard excluded).</p>'
                '<p class="muted">GearScore is calculated per item as floor(((item level - A) / B) x slot weight x 1.8618), '
                "summed over all items, with the formula of the GearScoreLite family of addons (TacoTip version). "
                "It does not subtract anything for missing enchants or gems."
                f"{extra} Item level, stats and sockets come from the AzerothCore item database, not from Warmane; "
                "enchants and gems come from the game client files.</p>")
    elif score["items"] or score["unknown_items"]:
        note = (f'<p class="muted">Average item level and GearScore not calculated: item level data is missing for '
                f'{score["unknown_items"]} item(s). Run the AzerothCore fetch and rebuild the snapshot.</p>')
    return ("<h2 id=\"gear\">Equipment</h2>"
            + _table(["Slot", "Item", "Quality", "Item level", "GearScore", "Base stats and special effects", "Enchant", "Gems"], rows) + _set_html(report) + note + totals_html)


def _spec_section(report: dict[str, Any]) -> str:
    out = ["<h2 id=\"specs\">Talents and glyphs</h2>",
           f"<p>Active specialization: {_e(report.get('active_specialization'))}.</p>"]
    for spec in report.get("specializations", []):
        out.append(f"<h3>{_e(spec.get('label'))} ({_e('/'.join(str(x) for x in spec.get('split', [])))})</h3>")
        for tree in spec.get("talent_detail", []):
            if not tree["talents"]:
                continue
            rows = [[t["name"] or "?", f"{t['spent']}/{t['max']}",
                      (t["description"] or "") + (" [placeholder not resolved]" if "$" in (t["description"] or "") else "")]
                     for t in tree["talents"]]
            out.append(f"<details><summary>{_e(tree['tree'])}: {_e(tree['points'])} points</summary>"
                       + _table(["Talent", "Rank", "Effect at current rank"], rows) + "</details>")
        glyphs = [[g.get("category"), g.get("name"), g.get("effect") or ""] for g in spec.get("glyphs", [])]
        if glyphs:
            out.append(_table(["Glyph type", "Glyph", "Effect"], glyphs))
    profs = report.get("professions") or []
    if profs:
        out.append("<h3>Professions</h3>")
        out.append(_table(["Profession", "Skill", "Maximum"], [[p.get("name"), p.get("skill"), p.get("maximum", "")] for p in profs
                                                                if isinstance(p, dict)]))
    return "".join(out)


def suspect_cells(inst: dict[str, Any]) -> set[tuple[str, tuple[int | None, bool]]]:
    """(boss, heroic mode) pairs whose heroic count equals the normal count of the same size (and is above 0)."""
    found = set()
    for boss, counts in inst["bosses"].items():
        for (size, heroic), value in counts.items():
            if heroic and value and counts.get((size, False)) == value:
                found.add((boss, (size, heroic)))
    return found


def _instance_table(inst: dict[str, Any], heading: bool = True) -> str:
    modes = _sorted_modes(inst["modes"])
    suspects = suspect_cells(inst)
    rows = []
    for boss, counts in inst["bosses"].items():
        row = [boss]
        for mode in modes:
            if mode not in counts:
                row.append("n/a")
            else:
                row.append(_count_text(counts[mode]) + (" *" if (boss, mode) in suspects else ""))
        rows.append(row)
    return (f"<h4>{_e(inst['name'])}</h4>" if heading else "") + _table(["Boss"] + [_mode_label(m) for m in modes], rows, numeric_from=1)


def _stat_table(rows: list[dict[str, Any]]) -> str:
    return _table(["Statistic", "Value"], [[r["name"], r["value"]] for r in rows])


def _progress_section(progress: dict[str, Any]) -> str:
    suspect_total = sum(len(suspect_cells(i)) for key in ("wotlk_raids", "wotlk_dungeons", "older") for i in progress[key])
    raid_suspects = sum(len(suspect_cells(i)) for i in progress["wotlk_raids"])
    out = ["<h2 id=\"progress\">WotLK raid progression: boss kills</h2>",
           '<div class="warn"><b>Warning: some armory kill counts are known to be wrong.</b> '
           "These are lifetime kill counters for this character, not current lockouts, shown exactly as the armory reports them. "
           "The armory often fails to separate difficulties, so a heroic count that equals the normal count of the same raid size "
           "is most likely wrong: treat it as unreliable. Such cells are marked with * "
           f"({raid_suspects} in the raid tables below, {suspect_total} in the whole report). "
           "A dash means the armory shows no entry. Instances spread over several statistic categories "
           "(Vault of Archavon) are merged into one table.</div>"]
    for inst in progress["wotlk_raids"]:
        out.append(f"<details open><summary><b>{_e(inst['name'])}</b></summary>{_instance_table(inst, heading=False)}</details>")
    if not progress["wotlk_raids"]:
        out.append("<p>No WotLK raid statistics were collected.</p>")
    return "".join(out)


def _other_content_section(progress: dict[str, Any]) -> str:
    """Collapsed sections: WotLK dungeons, older content, counters, deaths. Placed last in the report."""
    out = ["<details id=\"other\" class=\"big\"><summary><h2>Other dungeon and raid statistics</h2></summary>",
           "<p class=\"muted\">The armory warning above applies here too (* marks suspect heroic counts).</p>"]
    if progress["wotlk_dungeons"]:
        out.append("<details><summary><b>WotLK dungeons</b></summary>" + "".join(_instance_table(i) for i in progress["wotlk_dungeons"]) + "</details>")
    if progress["older"]:
        out.append("<details><summary><b>Burning Crusade and Classic</b></summary>" + "".join(_instance_table(i) for i in progress["older"]) + "</details>")
    other_rows = [r for g in progress["groups"] for r in g["other"]]
    if other_rows:
        out.append("<details><summary><b>Statistics not matched to an instance</b></summary>" + _stat_table(other_rows) + "</details>")
    if progress["overview"]:
        out.append("<details><summary><b>Entered and completed</b></summary>" + _stat_table(progress["overview"]) + "</details>")
    if progress["deaths"]:
        out.append("<details><summary><b>Deaths in dungeons and raids</b></summary>" + _stat_table(progress["deaths"]) + "</details>")
    out.append("</details>")
    return "".join(out)


def _percent(part: int, total: int) -> str:
    return f"{int(100 * part / total + 0.5)}%" if total else "-"


def _achievement_block(g: dict[str, Any]) -> str:
    total = len(g["earned"]) + len(g["missing"])
    out = [f"<details><summary><b>{_e(g['name'])}</b>: {len(g['earned'])} of {total} earned</summary>"]
    if g["earned"]:
        out.append("<h4>Earned</h4>" + _table(["Achievement", "Points", "Date"],
                   [[a["title"], a.get("points"), a.get("earned_date")] for a in g["earned"]]))
    if g["missing"]:
        out.append("<h4>Not earned</h4>" + _table(["Achievement", "Points", "Requirement"],
                   [[a["title"], a.get("points"), a.get("description")] for a in g["missing"]]))
    out.append("</details>")
    return "".join(out)


def _achievement_section(groups: list[dict[str, Any]]) -> str:
    out = ["<h2 id=\"achievements\">WotLK raid achievements</h2>"]
    if not groups:
        return out[0] + "<p>No achievement data collected.</p>"
    raid_names = set(ACHIEVEMENT_ORDER[5:])
    raid = [g for g in groups if g["name"] in raid_names]
    rest = [g for g in groups if g["name"] not in raid_names]
    out.append(_table(["Category", "Earned", "Percent"], [[g["name"], f"{len(g['earned'])} / {len(g['earned']) + len(g['missing'])}",
                                                          _percent(len(g["earned"]), len(g["earned"]) + len(g["missing"]))]
                                                         for g in raid + rest], numeric_from=1))
    out.extend(_achievement_block(g) for g in raid)
    if rest:
        out.append("<details><summary><b>Dungeon, heroic dungeon, Classic and Burning Crusade achievements</b></summary>"
                   + "".join(_achievement_block(g) for g in rest) + "</details>")
    return "".join(out)


def _other_section(pve: dict[str, Any]) -> str:
    report = pve["report"]
    out = []
    if pve["currencies"]:
        out.append("<h2 id=\"currency\">Badges and emblems</h2>" + _table(["Statistic", "Value"], [[r["name"], r["value"]] for r in pve["currencies"]]))
    rep = report.get("reputation") or []
    if rep:
        out.append("<h2 id=\"rep\">Reputation</h2>" + _table(["Faction", "Standing", "Progress"],
                   [[r["faction"], r["standing"], f"{r['current']} / {r['maximum']}"] for r in rep]))
    mounts = report.get("mounts") or []
    if mounts:
        out.append("<h2 id=\"mounts\">Mounts</h2><p>" + _e(", ".join(m["name"] for m in mounts)) + "</p>")
    return "".join(out)


def _armory_link(ident: dict[str, Any]) -> str:
    try:
        url = character_page_url(str(ident.get("name") or ""), str(ident.get("realm") or ""), "summary")
    except ValueError:
        return ""
    return f'<p>Armory: <a href="{_e(url)}">{_e(url)}</a></p>'


def render_html(pve: dict[str, Any]) -> str:
    report = pve["report"]
    ident = report["identity"]
    taken = report.get("snapshot_time")
    when = datetime.fromtimestamp(taken, timezone.utc).strftime("%Y-%m-%d %H:%M UTC") if isinstance(taken, (int, float)) else "unknown"
    title = f"{ident.get('name')} - {ident.get('realm')} - PvE report"
    toc = "".join(f'<li><a href="#{a}">{_e(t)}</a></li>' for a, t in (
        ("gear", "Equipment"), ("specs", "Talents and glyphs"), ("progress", "WotLK raid progression: boss kills"),
        ("other", "Other dungeon and raid statistics"), ("achievements", "WotLK raid achievements"),
        ("currency", "Badges and emblems"), ("rep", "Reputation"), ("mounts", "Mounts")))
    missing = report.get("missing_sections") or []
    parts = [
        f"<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><title>{_e(title)}</title><style>{CSS}</style></head><body>",
        f"<h1>{_e(ident.get('name'))} - {_e(ident.get('realm'))}</h1>",
        _armory_link(ident),
        f"<p>Level {_e(ident.get('level'))} {_e(ident.get('race'))} {_e(ident.get('class'))} ({_e(ident.get('faction'))}), "
        f"guild: {_e(ident.get('guild') or 'none')}. Achievement points: {_e(ident.get('achievement_points'))}.</p>",
        f"<p class=\"muted\">Data from the Warmane armory, snapshot taken {_e(when)}. This is a read-only record of the character as it is, "
        "intended for PvE discussion. Values the armory does not expose are marked unknown, never guessed "
        "(for example the active specialization).</p>",
        f"<ul>{toc}</ul>",
        _gear_section(report, pve["gearscore"]),
        _spec_section(report),
        _progress_section(pve["progression"]),
        _other_content_section(pve["progression"]),
        _achievement_section(pve["achievement_groups"]),
        _other_section(pve),
    ]
    if missing:
        parts.append(f"<h2>Missing sections</h2><p>{_e(', '.join(missing))}</p>")
    parts.append("</body></html>\n")
    return "".join(parts)


def write_html(report: dict[str, Any], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_html(build_pve_report(report)), encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("name")
    parser.add_argument("realm")
    parser.add_argument("--cache-dir", default=".warmane-cache")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(argv)
    stem = f"{args.name.lower()}-{SUPPORTED_REALMS[args.realm.strip().lower()].lower()}"
    source = Path(args.cache_dir) / "exports" / f"{stem}.json"
    if not source.exists():
        print(f"No export for {args.name}@{args.realm}; run: python -m warmane_exporter.export {args.name} {args.realm}")
        return 1
    report = json.loads(source.read_text(encoding="utf-8"))
    out = write_html(report, args.output or source.with_name(f"{stem}-pve.html"))
    print(f"saved: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
