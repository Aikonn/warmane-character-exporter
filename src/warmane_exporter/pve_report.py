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

from .identity import SUPPORTED_REALMS

# Statistics categories that hold boss kill rows, in display order: (id, heading).
PROGRESS_CATEGORIES = (
    (14821, "Classic"), (14822, "The Burning Crusade"), (14823, "Wrath of the Lich King"),
    (14963, "Secrets of Ulduar"), (15021, "Call of the Crusade"), (15062, "Fall of the Lich King"),
)
OVERVIEW_CATEGORY = 14807     # Dungeons & Raids: entered / completed counters
DEATHS_CATEGORY = 125         # Deaths > Dungeons: "Deaths in <raid>"
ACHIEVEMENT_PARENT = 168      # Dungeons & Raids

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
            inst = instances.setdefault(parsed["key"], {"name": parsed["instance"], "bosses": OrderedDict(), "modes": set()})
            mode = (parsed["size"], parsed["heroic"])
            inst["modes"].add(mode)
            inst["bosses"].setdefault(parsed["boss"], {})[mode] = count
        groups.append({"heading": heading, "instances": list(instances.values()), "other": other})
    overview = [{"name": r["name"], "value": r["value"]} for r in (by_id.get(OVERVIEW_CATEGORY) or {}).get("rows", [])]
    deaths = [{"name": r["name"], "value": r["value"]} for r in (by_id.get(DEATHS_CATEGORY) or {}).get("rows", [])
              if r["name"].startswith(("Deaths in", "Total"))]
    return {"groups": groups, "overview": overview, "deaths": deaths}


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
    for cid, name in category_names.items():
        entries = grouped[cid]
        ach_groups.append({
            "category_id": cid, "name": name,
            "earned": sorted([e for e in entries if e["earned"]], key=lambda e: (e.get("earned_date") or "", e["id"])),
            "missing": [e for e in entries if not e["earned"]],
        })
    levels = [e["item_level"] for e in report.get("equipment", [])
              if isinstance(e.get("item_level"), int) and e.get("slot") not in ("Shirt", "Tabard")]
    currencies = [r for c in stats if c["category_id"] == 130 for r in c["rows"]
                  if re.search(r"Emblems? of|Badges? of", r["name"])]
    return {
        "report": report,
        "progression": build_progression(stats),
        "achievement_groups": ach_groups,
        "average_item_level": round(sum(levels) / len(levels), 1) if levels else None,
        "item_level_count": len(levels),
        "currencies": currencies,
    }


# ---------------------------------------------------------------------------- HTML

CSS = """
body{font-family:Segoe UI,Arial,sans-serif;max-width:1100px;margin:1.5em auto;padding:0 1em;color:#111;line-height:1.4}
h1{border-bottom:2px solid #444;padding-bottom:.2em} h2{margin-top:1.8em;border-bottom:1px solid #999}
table{border-collapse:collapse;margin:.6em 0;font-size:.92em} th,td{border:1px solid #bbb;padding:.25em .6em;text-align:left;vertical-align:top}
th{background:#eee} td.n{text-align:right} .muted{color:#555} .note{background:#f6f6f0;border-left:4px solid #aa8;padding:.4em .8em}
details{margin:.4em 0} summary{cursor:pointer}
"""


def _e(value: Any) -> str:
    return escape("" if value is None else str(value))


def _table(headers: list[str], rows: list[list[Any]], numeric_from: int | None = None) -> str:
    head = "".join(f"<th>{_e(h)}</th>" for h in headers)
    body = []
    for row in rows:
        cells = []
        for i, cell in enumerate(row):
            cls = ' class="n"' if numeric_from is not None and i >= numeric_from else ""
            cells.append(f"<td{cls}>{_e(cell)}</td>")
        body.append("<tr>" + "".join(cells) + "</tr>")
    return f"<table><tr>{head}</tr>{''.join(body)}</table>"


def _count_text(value: int | None) -> str:
    return "-" if not value else str(value)


def _gear_section(report: dict[str, Any], average: float | None, count: int) -> str:
    rows = []
    for e in report.get("equipment", []):
        stats = ", ".join(f"+{v} {n}" for n, v in (e.get("stats") or []))
        if e.get("scaling_stats"):
            stats = (stats + " " if stats else "") + "(scaling item: stat values depend on character level)"
        gems = "; ".join(e.get("gems") or [])
        if e.get("sockets_empty"):
            gems += (" " if gems else "") + f"[{e['sockets_empty']} empty socket(s)]"
        item = f"{e.get('name') or '?'} ({e.get('item_id')})"
        if e.get("transmog"):
            item += f", transmog: {e['transmog']}"
        rows.append([e.get("slot"), item, e.get("quality") or "?", e.get("item_level") if e.get("item_level") is not None else "?",
                     stats, e.get("enchant") or "", gems])
    note = ""
    if average is not None:
        note = (f'<p class="muted">Derived: average item level {average} over {count} equipped items '
                "(shirt and tabard excluded). Item level, stats and sockets come from the AzerothCore item database, "
                "not from Warmane; enchants and gems come from the game client files.</p>")
    return "<h2 id=\"gear\">Equipment</h2>" + _table(["Slot", "Item", "Quality", "Item level", "Base stats", "Enchant", "Gems"], rows) + note


def _spec_section(report: dict[str, Any]) -> str:
    out = ["<h2 id=\"specs\">Talents and glyphs</h2>",
           f"<p>Active specialization: {_e(report.get('active_specialization'))}.</p>"]
    for spec in report.get("specializations", []):
        out.append(f"<h3>{_e(spec.get('label'))} ({_e('/'.join(str(x) for x in spec.get('split', [])))})</h3>")
        for tree in spec.get("talent_detail", []):
            if not tree["talents"]:
                continue
            rows = [[t["name"] or "?", f"{t['spent']}/{t['max']}", t["description"] or ""] for t in tree["talents"]]
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


def _progress_section(progress: dict[str, Any]) -> str:
    out = ["<h2 id=\"progress\">Dungeon and raid progression</h2>",
           '<p class="note">Source: armory statistics. These are lifetime kill counters for this character, not current lockouts. '
           "A dash means the armory shows no entry (never killed or not tracked). "
           "Boss kill counts include every difficulty shown in the column header.</p>"]
    # at-a-glance table
    glance = []
    for group in progress["groups"]:
        for inst in group["instances"]:
            modes = _sorted_modes(inst["modes"])
            cells = []
            for mode in modes:
                killed = sum(1 for b in inst["bosses"].values() if b.get(mode, 0) > 0)
                total = sum(1 for b in inst["bosses"].values() if mode in b)
                cells.append(f"{_mode_label(mode)}: {killed}/{total}")
            glance.append([group["heading"], inst["name"], "; ".join(cells)])
    out.append("<h3>Bosses killed per instance and mode</h3>")
    out.append(_table(["Expansion", "Instance", "Bosses with at least one kill"], glance))
    if progress["overview"]:
        out.append("<h3>Entered and completed</h3>")
        out.append(_table(["Statistic", "Value"], [[r["name"], r["value"]] for r in progress["overview"]]))
    for group in progress["groups"]:
        out.append(f"<h3>{_e(group['heading'])}</h3>")
        for inst in group["instances"]:
            modes = _sorted_modes(inst["modes"])
            rows = [[boss] + [_count_text(counts.get(m)) if m in counts else "n/a" for m in modes]
                    for boss, counts in inst["bosses"].items()]
            out.append(f"<h4>{_e(inst['name'])}</h4>")
            out.append(_table(["Boss"] + [_mode_label(m) for m in modes], rows, numeric_from=1))
        if group["other"]:
            out.append("<details><summary>Rows not matched to an instance</summary>"
                       + _table(["Statistic", "Value"], [[r["name"], r["value"]] for r in group["other"]]) + "</details>")
    if progress["deaths"]:
        out.append("<h3>Deaths in dungeons and raids</h3>")
        out.append(_table(["Statistic", "Value"], [[r["name"], r["value"]] for r in progress["deaths"]]))
    return "".join(out)


def _achievement_section(groups: list[dict[str, Any]]) -> str:
    out = ["<h2 id=\"achievements\">Dungeon and raid achievements</h2>"]
    if not groups:
        return out[0] + "<p>No achievement data collected.</p>"
    out.append(_table(["Category", "Earned", "Total"], [[g["name"], len(g["earned"]), len(g["earned"]) + len(g["missing"])] for g in groups],
                      numeric_from=1))
    for g in groups:
        total = len(g["earned"]) + len(g["missing"])
        out.append(f"<details><summary><b>{_e(g['name'])}</b>: {len(g['earned'])} of {total} earned</summary>")
        if g["earned"]:
            out.append("<h4>Earned</h4>" + _table(["Achievement", "Points", "Date"],
                       [[a["title"], a.get("points"), a.get("earned_date")] for a in g["earned"]]))
        if g["missing"]:
            out.append("<h4>Not earned</h4>" + _table(["Achievement", "Points", "Requirement"],
                       [[a["title"], a.get("points"), a.get("description")] for a in g["missing"]]))
        out.append("</details>")
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


def render_html(pve: dict[str, Any]) -> str:
    report = pve["report"]
    ident = report["identity"]
    taken = report.get("snapshot_time")
    when = datetime.fromtimestamp(taken, timezone.utc).strftime("%Y-%m-%d %H:%M UTC") if isinstance(taken, (int, float)) else "unknown"
    title = f"{ident.get('name')} - {ident.get('realm')} - PvE report"
    toc = "".join(f'<li><a href="#{a}">{_e(t)}</a></li>' for a, t in (
        ("gear", "Equipment"), ("specs", "Talents and glyphs"), ("progress", "Dungeon and raid progression"),
        ("achievements", "Dungeon and raid achievements"), ("currency", "Badges and emblems"), ("rep", "Reputation"), ("mounts", "Mounts")))
    missing = report.get("missing_sections") or []
    parts = [
        f"<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><title>{_e(title)}</title><style>{CSS}</style></head><body>",
        f"<h1>{_e(ident.get('name'))} - {_e(ident.get('realm'))}</h1>",
        f"<p>Level {_e(ident.get('level'))} {_e(ident.get('race'))} {_e(ident.get('class'))} ({_e(ident.get('faction'))}), "
        f"guild: {_e(ident.get('guild') or 'none')}. Achievement points: {_e(ident.get('achievement_points'))}.</p>",
        f"<p class=\"muted\">Data from the Warmane armory, snapshot taken {_e(when)}. This is a read-only record of the character as it is, "
        "intended for PvE discussion. Values the armory does not expose are marked unknown, never guessed "
        "(for example the active specialization).</p>",
        f"<ul>{toc}</ul>",
        _gear_section(report, pve["average_item_level"], pve["item_level_count"]),
        _spec_section(report),
        _progress_section(pve["progression"]),
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
