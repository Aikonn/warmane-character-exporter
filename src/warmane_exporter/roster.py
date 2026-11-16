"""Raid roster: quick PvE report for a list of characters plus one summary page.

python -m warmane_exporter.roster --realm Onyxia --names-file names.txt --output-dir DIR [--refresh] [--max-age-minutes 120]

Specification: docs/tasks/raid-roster.md. For each name the quick path of run.py is used
(3 live requests, none when the cache is younger than --max-age-minutes). Each character's
quick report is copied into DIR as <name>-<realm>-quick-pve.html and a summary page
raid-YYYY-MM-DD-HHMM.html is written next to them. Everything goes into DIR, no subfolder.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any
from unicodedata import normalize
from urllib.parse import quote

from .checks import run_checks
from .gearscore import character_score

REALMS = ("Onyxia", "Icecrown")
MAX_NAMES = 40
DEFAULT_MAX_AGE_MINUTES = 120
ARMORY_URL = "https://armory.warmane.com/character/{name}/{realm}/summary"
STOP_NOTE = "Stopped roster: access block, rate limit, or request budget exhausted."

# Row status values.
OK = "ok"
NOT_FOUND = "not found"   # the armory says the character does not exist; the run continues
NOT_RUN = "not run"       # the run stopped (block, rate limit, budget) before this character
FAILED = "failed"         # any other per-character failure; the run continues


@dataclass
class RosterInput:
    """Result of parse_names: the cleaned names in input order, and readable errors."""
    names: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass
class RosterRow:
    """One line of the summary table. Cells that are unknown for a status other than OK stay None."""
    name: str
    realm: str
    status: str
    class_name: str | None = None
    main_trees: list[str] = field(default_factory=list)   # per specialization, "-" when it has no points
    gearscore: int | None = None
    average_item_level: float | None = None
    issues: int | None = None
    warnings: int | None = None
    issue_texts: list[str] = field(default_factory=list)
    report_file: str | None = None      # file name relative to the output folder
    armory_url: str = ""
    data_time: float | None = None      # snapshot_time of the export (epoch seconds)
    from_cache: bool | None = None
    note: str | None = None             # short reason for NOT_FOUND / NOT_RUN / FAILED


def _canonical_realm(realm: str) -> str | None:
    return next((supported for supported in REALMS if supported.casefold() == realm.strip().casefold()), None)


def _armory_url(name: str, realm: str) -> str:
    canonical_realm = _canonical_realm(realm)
    if canonical_realm is None:
        raise ValueError(f"Unsupported realm: {realm!r}. Supported realms: {', '.join(REALMS)}.")
    return ARMORY_URL.format(name=quote(name, safe=""), realm=canonical_realm)


def parse_names(text: str, realm: str) -> RosterInput:
    """Clean the pasted list. Pure function, no I/O.

    - One name per line; trim spaces; ignore blank lines.
    - "Name-Realm" is accepted; a realm part that differs from ``realm`` (case-insensitive)
      is an error for that line.
    - Names must be letters only (accented letters allowed, as WotLK allows them);
      anything else is an error for that line.
    - Normalize to Warmane style: first letter upper case, the rest lower case.
    - Drop duplicates (case-insensitive), keep the first occurrence and input order.
    - More than MAX_NAMES distinct names is an error (names stay empty in that case).
    Errors name the line number and the offending text.
    """
    canonical_realm = _canonical_realm(realm)
    if canonical_realm is None:
        return RosterInput(errors=[f"Unsupported realm: {realm!r}. Supported realms: {', '.join(REALMS)}."])

    names: list[str] = []
    errors: list[str] = []
    seen: set[str] = set()
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue

        name = line
        if "-" in line:
            name, suffix = line.rsplit("-", 1)
            if suffix.strip().casefold() != canonical_realm.casefold():
                errors.append(f"Line {line_number}: {line!r} specifies a different realm; expected {canonical_realm}.")
                continue

        name = normalize("NFC", name.strip())
        if not name or not name.isalpha():
            errors.append(f"Line {line_number}: {line!r} must contain letters only.")
            continue

        normalized = name[0].upper() + name[1:].lower()
        key = normalized.casefold()
        if key not in seen:
            names.append(normalized)
            seen.add(key)
            if len(names) > MAX_NAMES:
                return RosterInput(errors=[
                    f"Line {line_number}: {line!r} exceeds the limit of {MAX_NAMES} distinct names."
                ])

    return RosterInput(names=names, errors=errors)


def build_row(report: dict[str, Any], report_file: str, from_cache: bool) -> RosterRow:
    """Build an OK row from one character's quick export JSON (schema character-report/0).

    Pure function. Use the same functions the PvE report uses, so the numbers match the
    character's own page: ``gearscore.character_score(report["equipment"], class)`` and
    ``checks.run_checks(report)``. Main tree per specialization is its ``label`` when the
    specialization has points, otherwise "-". issue_texts contains all issue texts in
    ``run_checks`` order.
    """
    identity = report["identity"]
    name = identity["name"]
    realm = identity["realm"]
    class_name = identity.get("class")
    score = character_score(report["equipment"], class_name)
    findings = run_checks(report)
    snapshot_time = report.get("snapshot_time")
    data_time = float(snapshot_time) if isinstance(snapshot_time, (int, float)) else None
    main_trees = [
        spec.get("label") or "-"
        if sum(points for points in (spec.get("split") or []) if isinstance(points, int)) > 0
        else "-"
        for spec in report.get("specializations") or []
    ]
    issues = findings["issues"]
    return RosterRow(
        name=name,
        realm=realm,
        status=OK,
        class_name=class_name,
        main_trees=main_trees,
        gearscore=score["gearscore"],
        average_item_level=score["average_item_level"],
        issues=len(issues),
        warnings=len(findings["warnings"]),
        issue_texts=[issue["text"] for issue in issues],
        report_file=report_file,
        armory_url=_armory_url(name, realm),
        data_time=data_time,
        from_cache=from_cache,
    )


def placeholder_row(name: str, realm: str, status: str, note: str | None = None) -> RosterRow:
    """Row for NOT_FOUND, NOT_RUN or FAILED: name, realm, status, armory link, note."""
    if status not in (NOT_FOUND, NOT_RUN, FAILED):
        raise ValueError(f"Unsupported placeholder status: {status!r}.")
    return RosterRow(
        name=name,
        realm=realm,
        status=status,
        armory_url=_armory_url(name, realm),
        note=note,
    )


def sort_rows(rows: list[RosterRow]) -> list[RosterRow]:
    """Sort by name, case-insensitive (owner decision)."""
    return sorted(rows, key=lambda row: row.name.casefold())


def summary_file_name(now: datetime) -> str:
    """raid-YYYY-MM-DD-HHMM.html for the local time ``now``."""
    return now.strftime("raid-%Y-%m-%d-%H%M.html")


def render_summary(rows: list[RosterRow], realm: str, run_time: datetime) -> str:
    """Self-contained HTML summary page in the style of pve_report (inline CSS, no scripts).

    Header: realm, run time, number of characters, how many came from cache, and how many
    rows are not OK. Table columns, in order: Name, Class, Main trees ("Holy / Discipline"),
    GearScore, Avg item level, Issues, Warnings, Issues list, Report (relative link),
    Armory (link), Data age. Every armory-derived text is HTML-escaped.
    """
    cached_count = sum(row.from_cache is True for row in rows)
    not_ok_count = sum(row.status != OK for row in rows)
    headings = (
        "Name", "Class", "Main trees", "GearScore", "Avg item level", "Issues", "Warnings",
        "Issues list", "Report", "Armory", "Data age",
    )

    def count_cell(value: int | None, color_class: str) -> str:
        if value is None:
            return ""
        if value == 0:
            return "0"
        classes = [color_class]
        if value >= 4:
            classes.append("count-high")
        return f'<span class="{" ".join(classes)}">{value}</span>'

    table_rows: list[str] = []
    for row in sort_rows(rows):
        armory = (
            f'<a href="{escape(row.armory_url, quote=True)}">Armory</a>'
            if row.armory_url else ""
        )
        if row.status != OK:
            reason = row.note or row.status
            status_note = f'<span class="status">{escape(row.status)}: {escape(reason)}</span>'
            cells = [escape(row.name), *([""] * 6), status_note, "", armory, ""]
        else:
            report_link = (
                f'<a href="{escape(row.report_file, quote=True)}">Open</a>'
                if row.report_file else ""
            )
            data_age = ""
            if row.from_cache is True and row.data_time is not None:
                cached_at = datetime.fromtimestamp(row.data_time).strftime("%Y-%m-%d %H:%M")
                data_age = f"cached at {cached_at}"
            elif row.from_cache is False:
                data_age = "fresh"
            issue_list = ""
            if row.issue_texts:
                issue_list = (
                    '<ul class="issues">'
                    + "".join(f"<li>{escape(text)}</li>" for text in row.issue_texts)
                    + "</ul>"
                )
            cells = [
                escape(row.name),
                escape(row.class_name or ""),
                escape(" / ".join(row.main_trees)),
                "" if row.gearscore is None else str(row.gearscore),
                "" if row.average_item_level is None else f"{row.average_item_level:g}",
                count_cell(row.issues, "count-issue"),
                count_cell(row.warnings, "count-warn"),
                issue_list,
                report_link,
                armory,
                escape(data_age),
            ]
        table_rows.append("<tr>" + "".join(f"<td>{cell}</td>" for cell in cells) + "</tr>")

    table_head = "".join(f"<th>{heading}</th>" for heading in headings)
    return (
        "<!doctype html>\n<html lang=\"en\">\n<head>\n"
        '<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>Raid roster - {escape(realm)}</title>\n"
        "<style>"
        "body{font-family:Segoe UI,Arial,sans-serif;max-width:1400px;margin:1.5em auto;padding:0 1em;color:#111;line-height:1.4}"
        "h1{border-bottom:2px solid #444;padding-bottom:.2em}"
        "table{border-collapse:collapse;width:100%;margin:.6em 0;font-size:.92em}"
        "th,td{border:1px solid #bbb;padding:.35em .6em;text-align:left;vertical-align:top}"
        "th{background:#eee}"
        ".status{color:#666;font-style:italic}"
        ".issues{font-size:.8em;margin:.1em 0;padding-left:1.2em}"
        ".count-issue{color:#b00020}.count-warn{color:#a65a00}.count-high{font-weight:700}"
        "</style>\n</head>\n<body>\n"
        f"<h1>Raid roster - {escape(realm)}</h1>\n"
        f"<p>Run time: {escape(run_time.strftime('%Y-%m-%d %H:%M'))}; "
        f"characters: {len(rows)}; from cache: {cached_count}; not OK: {not_ok_count}.</p>\n"
        "<table>\n<thead><tr>" + table_head + "</tr></thead>\n<tbody>\n"
        + "\n".join(table_rows)
        + "\n</tbody>\n</table>\n</body>\n</html>\n"
    )


def run_roster(names: list[str], realm: str, output_dir: Path, cache_dir: str,
               refresh: bool, max_age_minutes: int) -> tuple[list[RosterRow], Path]:
    """Run the quick report for each name in order, then write the summary.

    - One character at a time through the quick path of run.py, with the cache age passed
      down to the snapshot step (snapshot gets a --max-age-minutes option; the single
      character default of 15 minutes stays unchanged).
    - Progress lines: "Character N of M: Name" via progress.note, plus the existing steps.
    - Character does not exist: NOT_FOUND row, continue. Access block, rate limit or
      BudgetExhausted: stop; remaining names become NOT_RUN rows. Other failure: FAILED row,
      continue.
    - Copy each quick report HTML into output_dir (overwrite), write the summary there
      atomically (temp name, then rename). Returns the rows and the summary path.
    """
    from . import run
    from .progress import note, start

    cache_path = Path(cache_dir)
    exports_dir = cache_path / "exports"
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    rows: list[RosterRow] = []
    stopped = False

    start(4 * len(names), "Starting raid roster")
    for index, name in enumerate(names, start=1):
        if stopped:
            rows.append(placeholder_row(name, realm, NOT_RUN, "An earlier character stopped the roster."))
            continue

        note(f"Character {index} of {len(names)}: {name}")
        code = run.run_character(
            name, realm, str(cache_path), refresh, False, quick=True,
            max_age_minutes=max_age_minutes, start_progress=False,
        )
        if code == 3:
            rows.append(placeholder_row(name, realm, NOT_FOUND, "Character does not exist."))
            continue
        if code == 4:
            rows.append(placeholder_row(name, realm, FAILED, STOP_NOTE))
            stopped = True
            continue
        if code != 0:
            rows.append(placeholder_row(name, realm, FAILED, f"Character run failed (exit code {code})."))
            continue

        stem = f"{name.lower()}-{realm.lower()}-quick"
        report_path = exports_dir / f"{stem}.json"
        html_path = exports_dir / f"{stem}-pve.html"
        target_html = output_dir / html_path.name
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
            snapshot_paths = sorted(
                (cache_path / "snapshots").glob(f"{name.lower()}-{realm.lower()}-*.json"),
                key=lambda path: path.stat().st_mtime,
            )
            if not snapshot_paths:
                raise FileNotFoundError(f"No snapshot found for {name}@{realm}.")
            snapshot_data = json.loads(snapshot_paths[-1].read_text(encoding="utf-8"))
            sections = snapshot_data["sections"]
            from_cache = all(
                sections[key]["origin"] == "cache"
                for key in ("json_summary", "html_summary", "talents")
            )
            row = build_row(report, target_html.name, from_cache)
            if not html_path.is_file():
                raise FileNotFoundError(f"Quick report HTML is missing for {name}@{realm}.")
            if html_path.resolve() != target_html.resolve():
                shutil.copyfile(html_path, target_html)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            print(f"Could not assemble roster row for {name}: {exc}", file=sys.stderr)
            rows.append(placeholder_row(name, realm, FAILED, f"Could not build report row: {exc}"))
            continue
        rows.append(row)

    run_time = datetime.now()
    summary_path = output_dir / summary_file_name(run_time)
    rendered = render_summary(rows, realm, run_time)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", newline="", dir=output_dir,
        prefix=f".{summary_path.name}.", suffix=".tmp", delete=False,
    ) as temporary:
        temporary.write(rendered)
        temporary_path = Path(temporary.name)
    try:
        temporary_path.replace(summary_path)
    except OSError:
        try:
            temporary_path.unlink()
        except FileNotFoundError:
            pass
        raise
    return rows, summary_path


def main(argv: list[str] | None = None) -> int:
    """CLI: --realm (required, one of REALMS), --names-file or --names (comma separated),
    --output-dir (required), --cache-dir, --refresh, --max-age-minutes.

    Prints the summary path as the last line: "summary: <path>" (the launcher opens it).
    Exit 0 when the summary was written (even with NOT_FOUND / FAILED rows), 1 when the run
    stopped early (summary still written), 2 for input errors (nothing fetched).
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--realm", required=True, help=f"realm: {', '.join(REALMS)}")
    inputs = parser.add_mutually_exclusive_group()
    inputs.add_argument("--names-file", type=Path)
    inputs.add_argument("--names", help="comma-separated character names")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--cache-dir", default=".warmane-cache")
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--max-age-minutes", type=int, default=DEFAULT_MAX_AGE_MINUTES)
    args = parser.parse_args(argv)

    canonical_realm = _canonical_realm(args.realm)
    if canonical_realm is None:
        print(f"Error: unsupported realm {args.realm!r}; choose {', '.join(REALMS)}.", file=sys.stderr)
        return 2
    if args.max_age_minutes < 0:
        print("Error: --max-age-minutes must be zero or greater.", file=sys.stderr)
        return 2
    if args.names_file is None and args.names is None:
        print("Error: provide --names-file or --names.", file=sys.stderr)
        return 2
    try:
        names_text = (
            args.names_file.read_text(encoding="utf-8")
            if args.names_file is not None
            else args.names.replace(",", "\n")
        )
    except OSError as exc:
        print(f"Error reading names file: {exc}", file=sys.stderr)
        return 2
    parsed = parse_names(names_text, canonical_realm)
    if parsed.errors or not parsed.names:
        for error in parsed.errors:
            print(f"Error: {error}", file=sys.stderr)
        if not parsed.names:
            print("Error: provide at least one valid character name.", file=sys.stderr)
        return 2

    try:
        rows, summary_path = run_roster(
            parsed.names, canonical_realm, args.output_dir, args.cache_dir,
            args.refresh, args.max_age_minutes,
        )
    except OSError as exc:
        print(f"Error writing roster output: {exc}", file=sys.stderr)
        return 1
    print(f"summary: {summary_path}")
    return 1 if any(row.note == STOP_NOTE for row in rows) else 0


if __name__ == "__main__":
    raise SystemExit(main())
