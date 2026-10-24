"""Render a character snapshot as Markdown or compact JSON.

python -m warmane_exporter.report SNAPSHOT.json [--format md|json] [--output FILE]
Offline only: reads a snapshot written by warmane_exporter.snapshot.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def _section_data(snapshot: dict[str, Any], name: str) -> dict[str, Any]:
    section = snapshot.get("sections", {}).get(name) or {}
    return section.get("data") or {}


def _glyph_effect(client: Any) -> str | None:
    """Prefer the rendered text; fall back to the raw template only when nothing better exists."""
    if not isinstance(client, dict):
        return None
    return client.get("description_rendered") or client.get("description")


def build_report(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Merge snapshot sections into one plain report structure."""
    summary = _section_data(snapshot, "json_summary")
    html = _section_data(snapshot, "html_summary")
    talents = _section_data(snapshot, "talents")
    names = {int(i["item_id"]): i.get("name", "") for i in summary.get("equipment", []) if i.get("item_id") is not None}
    transmog = {int(i["item_id"]): i.get("transmog", "") for i in summary.get("equipment", []) if i.get("item_id") is not None}

    equipment = []
    for slot in html.get("equipment", {}).get("slots", []):
        if slot.get("is_empty"):
            continue
        ref = slot.get("item_reference") or {}
        raw_id = ref.get("href_item_id")
        item_id = int(raw_id) if raw_id and str(raw_id).isdigit() else None
        client = slot.get("client") or {}
        gems = [g.get("text") for g in client.get("gems", []) if isinstance(g, dict) and g.get("text")]
        total_gems = len([g for g in client.get("gems", []) if isinstance(g, dict)])
        equipment.append({
            "slot": (slot.get("layout_inference") or {}).get("inferred_slot_name") or slot.get("slot_name") or slot.get("slot_key"),
            "item_id": item_id,
            "quality": ref.get("quality_name"),
            "name": names.get(item_id, ""),
            "transmog": transmog.get(item_id, ""),
            "enchant": (client.get("enchant") or {}).get("text"),
            "gems": gems,
            "gem_slots_seen": total_gems,
            "item_level": (client.get("acore") or {}).get("item_level"),
            "stats": (client.get("acore") or {}).get("stats"),
            "scaling_stats": (client.get("acore") or {}).get("scaling_stats"),
            "sockets": (client.get("acore") or {}).get("sockets"),
            "sockets_empty": (client.get("acore") or {}).get("sockets_empty"),
        })

    specs = []
    for spec in talents.get("specs", []):
        glyph_block = (talents.get("glyphs") or {}).get(str(spec.get("source_spec_id"))) or {}
        specs.append({
            "label": spec.get("label"),
            "split": [t.get("reported_total") for t in spec.get("trees", [])],
            "trees": [t.get("name") for t in spec.get("trees", [])],
            "talent_detail": [
                {"tree": t.get("name"), "points": t.get("reported_total"), "talents": [
                    {"name": (x.get("client") or {}).get("name"), "spent": x.get("points_spent"),
                     "max": x.get("points_max"), "row": (x.get("client") or {}).get("row"),
                     "column": (x.get("client") or {}).get("column"),
                     "description": (x.get("client") or {}).get("selected_rank_description_rendered")
                     or (x.get("client") or {}).get("selected_rank_description")}
                    for x in t.get("talents", []) if isinstance(x.get("points_spent"), int) and x["points_spent"] > 0]}
                for t in spec.get("trees", [])],
            "glyphs": [
                {"category": g.get("category"), "name": g.get("name"),
                 "effect": _glyph_effect(g.get("client"))}
                for g in glyph_block.get("entries", [])
            ],
        })

    return {
        "schema": "character-report/0",
        "generated_from": snapshot.get("schema"),
        "snapshot_time": snapshot.get("generated_at"),
        "identity": {k: summary.get(k) for k in (
            "name", "realm", "level", "faction", "race", "class", "gender", "guild",
            "achievement_points", "honorable_kills")},
        "equipment": equipment,
        "specializations": specs,
        "active_specialization": "unknown (not exposed by Warmane)",
        "professions": html.get("professions") if html.get("professions") is not None else summary.get("professions"),
        "sections": {n: (s or {}).get("status") for n, s in snapshot.get("sections", {}).items()},
    }


def render_markdown(report: dict[str, Any]) -> str:
    ident = report["identity"]
    lines = [
        f"# {ident.get('name')} - {ident.get('realm')}",
        "",
        f"{ident.get('level')} {ident.get('race')} {ident.get('class')} ({ident.get('faction')}), "
        f"guild: {ident.get('guild') or 'none'}",
        "",
        f"Achievement points: {ident.get('achievement_points')}; honorable kills: {ident.get('honorable_kills')}",
        "",
        "## Equipment",
        "",
        "| Slot | Item | Enchant | Gems |",
        "|---|---|---|---|",
    ]
    for e in report["equipment"]:
        item = f"{e['name'] or '?'} ({e['item_id']}, {e.get('quality') or 'quality unknown'})"
        if e.get("transmog"):
            item += f", transmog: {e['transmog']}"
        gems = "; ".join(e["gems"])
        if e.get("sockets_empty"):
            gems += (" " if gems else "") + f"[{e['sockets_empty']} empty socket(s)]"
        lines.append(f"| {e['slot']} | {item} | {e['enchant'] or ''} | {gems} |")
    lines += ["", "## Specializations", "", f"Active specialization: {report['active_specialization']}", ""]
    for s in report["specializations"]:
        split = "/".join(str(x) for x in s["split"])
        lines.append(f"### {s['label']} ({split})")
        lines.append("")
        for g in s["glyphs"]:
            effect = f": {g['effect']}" if g.get("effect") else ""
            lines.append(f"- {g['category']} glyph: {g['name']}{effect}")
        lines.append("")
    if report.get("professions"):
        lines += ["## Professions", "", "```json", json.dumps(report["professions"], ensure_ascii=False), "```", ""]
    lines.append(f"Snapshot taken: {report['snapshot_time']}. Sections: " + ", ".join(f"{k}={v}" for k, v in report["sections"].items()))
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render a character snapshot as Markdown or JSON.")
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("--format", choices=("md", "json"), default="md")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(argv)
    snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
    report = build_report(snapshot)
    text = render_markdown(report) if args.format == "md" else json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
        print(f"saved: {args.output}")
    else:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
