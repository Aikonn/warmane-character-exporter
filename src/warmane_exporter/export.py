"""Merge everything collected for one character into a final report (offline).

python -m warmane_exporter.export NAME REALM [--cache-dir DIR] [--output-dir DIR]

Reads the newest files in .warmane-cache: snapshots/, collections/ (achievements, statistics) and
discovery/ (reputation and mounts pages). Writes <name>-<realm>.json and .md. Missing parts are
reported as missing in the output, never invented.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .identity import SUPPORTED_REALMS
from .mounts_parser import parse_mounts_page
from .report import build_report, render_markdown
from .reputation_parser import parse_reputation_page
from .collect import summarize


def _newest(directory: Path, pattern: str) -> Path | None:
    files = sorted(directory.glob(pattern), key=lambda p: p.stat().st_mtime)
    return files[-1] if files else None


def _load(path: Path | None) -> dict[str, Any] | None:
    return json.loads(path.read_text(encoding="utf-8")) if path else None


def build_full_report(
    snapshot: dict[str, Any],
    achievements: dict[str, Any] | None,
    statistics: dict[str, Any] | None,
    reputation_html: str | None,
    mounts_html: str | None,
) -> dict[str, Any]:
    report = build_report(snapshot)
    missing: list[str] = []

    if achievements and achievements.get("complete"):
        seen: dict[int, dict[str, Any]] = {}
        by_category = []
        for cat in achievements["categories"]:
            for entry in cat["entries"]:
                seen.setdefault(entry["id"], {**entry, "category_id": cat["id"], "category": cat["name"], "parent_category_id": cat["parent"]})
        top = {c["id"]: c["name"] for c in achievements["categories"] if c["parent"] is None}
        for top_id, top_name in top.items():
            members = [a for a in seen.values() if (a["parent_category_id"] or a["category_id"]) == top_id]
            by_category.append({"category": top_name, "earned": sum(a["earned"] for a in members), "total": len(members),
                                "points": sum(a["points"] or 0 for a in members if a["earned"])})
        report["achievements"] = {
            "summary": summarize(achievements["categories"]),
            "by_top_category": by_category,
            "entries": sorted(seen.values(), key=lambda a: (a["category_id"], a["id"])),
        }
        armory = report["identity"].get("achievement_points")
        report["achievements"]["points_match_armory"] = armory == report["achievements"]["summary"]["earned_points"]
    else:
        missing.append("achievements")

    if statistics and statistics.get("complete"):
        report["statistics"] = [
            {"category_id": c["id"], "category": c["name"], "parent": c["parent"], "rows": c["entries"]}
            for c in statistics["categories"]
        ]
    else:
        missing.append("statistics")

    if reputation_html:
        report["reputation"] = parse_reputation_page(reputation_html)
    else:
        missing.append("reputation")

    if mounts_html:
        report.update(parse_mounts_page(mounts_html))
    else:
        missing.extend(["mounts", "companions"])

    report["missing_sections"] = missing
    return report


def render_full_markdown(report: dict[str, Any]) -> str:
    out = [render_markdown(report).rstrip("\n"), ""]
    ach = report.get("achievements")
    if ach:
        s = ach["summary"]
        out += ["## Achievements", "",
                f"{s['earned']} of {s['unique_achievements']} earned, {s['earned_points']} points"
                f" (armory total matches: {ach['points_match_armory']})", "",
                "| Category | Earned | Total | Points |", "|---|---|---|---|"]
        out += [f"| {c['category']} | {c['earned']} | {c['total']} | {c['points']} |" for c in ach["by_top_category"]]
        out.append("")
        out += ["### Earned achievements", ""]
        for a in ach["entries"]:
            if a["earned"]:
                out.append(f"- {a['title']} ({a['points']} pts, {a['earned_date']}) - {a['category']}")
        out.append("")
    if report.get("statistics"):
        out += ["## Statistics", ""]
        for c in report["statistics"]:
            indent = "###" if c["parent"] is None else "####"
            out += [f"{indent} {c['category']}", ""]
            out += [f"- {r['name']}: {r['value']}" for r in c["rows"]]
            out.append("")
    if report.get("reputation"):
        out += ["## Reputation", "", "| Faction | Standing | Progress |", "|---|---|---|"]
        out += [f"| {r['faction']} | {r['standing']} | {r['current']} / {r['maximum']} |" for r in report["reputation"]]
        out.append("")
    for key, title in (("mounts", "Mounts"), ("companions", "Companions")):
        if key in report:
            out += [f"## {title}", ""] + [f"- {m['name']} (item {m['item_id']})" for m in report[key]] + [""]
    if report["missing_sections"]:
        out += ["## Missing sections", "", ", ".join(report["missing_sections"]), ""]
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("name")
    parser.add_argument("realm")
    parser.add_argument("--cache-dir", default=".warmane-cache")
    parser.add_argument("--output-dir", default=None)
    args = parser.parse_args(argv)

    realm = SUPPORTED_REALMS[args.realm.strip().lower()]
    stem = f"{args.name.lower()}-{realm.lower()}"
    cache_dir = Path(args.cache_dir)
    snapshot_path = _newest(cache_dir / "snapshots", f"{stem}-*.json")
    if snapshot_path is None:
        print(f"No snapshot for {args.name}@{realm}; run the snapshot command first.")
        return 1

    def page(view: str) -> str | None:
        path = cache_dir / "discovery" / f"{stem}-{view}.html"
        return path.read_text(encoding="utf-8") if path.exists() else None

    report = build_full_report(
        _load(snapshot_path),
        _load(_newest(cache_dir / "collections", f"{stem}-achievements-*.json")),
        _load(_newest(cache_dir / "collections", f"{stem}-statistics-*.json")),
        page("reputation"), page("mounts-and-companions"),
    )
    out_dir = Path(args.output_dir) if args.output_dir else cache_dir / "exports"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{stem}.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    (out_dir / f"{stem}.md").write_text(render_full_markdown(report), encoding="utf-8")
    from .pve_report import write_html

    html_path = write_html(report, out_dir / f"{stem}-pve.html")
    print(f"snapshot: {snapshot_path.name}")
    print(f"missing sections: {report['missing_sections'] or 'none'}")
    if "achievements" in report:
        print(f"achievement points match armory: {report['achievements']['points_match_armory']}")
    print(f"saved: {out_dir / (stem + '.md')}")
    print(f"saved: {html_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
