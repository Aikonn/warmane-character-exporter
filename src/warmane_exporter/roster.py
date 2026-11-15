"""Raid roster: quick PvE report for a list of characters plus one summary page.

python -m warmane_exporter.roster --realm Onyxia --names-file names.txt --output-dir DIR [--refresh] [--max-age-minutes 120]

Specification: docs/tasks/raid-roster.md. For each name the quick path of run.py is used
(3 live requests, none when the cache is younger than --max-age-minutes). Each character's
quick report is copied into DIR as <name>-<realm>-quick-pve.html and a summary page
raid-YYYY-MM-DD-HHMM.html is written next to them. Everything goes into DIR, no subfolder.
"""

from __future__ import annotations

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
    first_issue: str | None = None
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
    specialization has points, otherwise "-". first_issue is the text of the first issue.
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
        first_issue=issues[0]["text"] if issues else None,
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
    GearScore, Avg item level, Issues, Warnings, First issue, Report (relative link),
    Armory (link), Data age. Every armory-derived text is HTML-escaped.
    """
    cached_count = sum(row.from_cache is True for row in rows)
    not_ok_count = sum(row.status != OK for row in rows)
    headings = (
        "Name", "Class", "Main trees", "GearScore", "Avg item level", "Issues", "Warnings",
        "First issue", "Report", "Armory", "Data age",
    )
    table_rows: list[str] = []
    for row in sort_rows(rows):
        armory = (
            f'<a href="{escape(row.armory_url, quote=True)}">Armory</a>'
            if row.armory_url else ""
        )
        if row.status != OK:
            cells = [escape(row.name), *([""] * 8), armory, ""]
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
            cells = [
                escape(row.name),
                escape(row.class_name or ""),
                escape(" / ".join(row.main_trees)),
                "" if row.gearscore is None else str(row.gearscore),
                "" if row.average_item_level is None else f"{row.average_item_level:g}",
                "" if row.issues is None else str(row.issues),
                "" if row.warnings is None else str(row.warnings),
                escape(row.first_issue or ""),
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
    raise NotImplementedError


def main(argv: list[str] | None = None) -> int:
    """CLI: --realm (required, one of REALMS), --names-file or --names (comma separated),
    --output-dir (required), --cache-dir, --refresh, --max-age-minutes.

    Prints the summary path as the last line: "summary: <path>" (the launcher opens it).
    Exit 0 when the summary was written (even with NOT_FOUND / FAILED rows), 1 when the run
    stopped early (summary still written), 2 for input errors (nothing fetched).
    """
    raise NotImplementedError


if __name__ == "__main__":
    raise SystemExit(main())
