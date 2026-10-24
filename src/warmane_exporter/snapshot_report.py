"""Offline consistency report for saved character snapshots.

python -m warmane_exporter.snapshot_report SNAPSHOT.json [SNAPSHOT.json ...]
No network access. Exit code 1 when any check fails.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


def _item_id(slot: dict[str, Any]) -> int | None:
    client_item = (slot.get("client") or {}).get("item") or {}
    raw = client_item.get("item_id") or (slot.get("item_reference") or {}).get("href_item_id")
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def check_snapshot(snapshot: dict[str, Any]) -> tuple[list[str], bool]:
    lines: list[str] = []
    ok = True
    character = snapshot.get("character", {})
    lines.append(f"{character.get('name')}@{character.get('realm')} complete={snapshot.get('complete')}")
    sections = snapshot.get("sections", {})
    for key, section in sections.items():
        lines.append(f"  {key}: {section.get('status')} ({section.get('origin')})")
        if section.get("status") != "ok":
            ok = False
            lines.append(f"    detail: {section.get('detail')}")

    json_data = (sections.get("json_summary") or {}).get("data")
    html_data = (sections.get("html_summary") or {}).get("data")
    talents = (sections.get("talents") or {}).get("data")

    if html_data:
        slots = [s for s in html_data.get("equipment", {}).get("slots", []) if s.get("item_reference")]
        layout = html_data.get("equipment", {}).get("layout_validation", {}).get("status")
        checks = Counter((s.get("client") or {}).get("slot_check") for s in slots)
        warnings = html_data.get("client_warnings") or []
        lines.append(f"  html equipment: {len(slots)} items, layout={layout}, slot_check={dict(checks)}, "
                     f"client_warnings={len(warnings)}")
        if layout != "anchors_consistent" or checks.get("mismatch") or warnings:
            ok = False
        if json_data:
            html_ids = sorted(i for i in (_item_id(s) for s in slots) if i is not None)
            json_ids = sorted(e["item_id"] for e in json_data.get("equipment", []))
            same = html_ids == json_ids
            lines.append(f"  item ids JSON vs HTML: {'match' if same else 'MISMATCH'} ({len(json_ids)} vs {len(html_ids)})")
            ok = ok and same

    if talents:
        specs = talents.get("specs", [])
        wcount = len(talents.get("warnings") or [])
        cwcount = len(talents.get("client_warnings") or [])
        lines.append(f"  talents: {len(specs)} specs, warnings={wcount}, client_warnings={cwcount}")
        if wcount or cwcount:
            ok = False
        if json_data:
            html_totals = sorted(tuple(t.get("reported_total") for t in spec.get("trees", [])) for spec in specs)
            json_totals = sorted(tuple(int(p) for p in tree["points"]) for tree in json_data.get("talent_trees", []))
            same = html_totals == json_totals
            lines.append(f"  talent point totals JSON vs HTML: {'match' if same else 'MISMATCH'} "
                         f"{json_totals} vs {html_totals}")
            ok = ok and same
    lines.append(f"  RESULT: {'PASS' if ok else 'FAIL'}")
    return lines, ok


def main(argv: list[str] | None = None) -> int:
    paths = (argv if argv is not None else sys.argv[1:])
    if not paths:
        print("Usage: python -m warmane_exporter.snapshot_report SNAPSHOT.json [...]", file=sys.stderr)
        return 2
    all_ok = True
    for path in paths:
        snapshot = json.loads(Path(path).read_text(encoding="utf-8"))
        lines, ok = check_snapshot(snapshot)
        print("\n".join(lines))
        all_ok = all_ok and ok
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
