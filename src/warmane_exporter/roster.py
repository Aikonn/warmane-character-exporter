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
from pathlib import Path
from typing import Any

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
    raise NotImplementedError


def build_row(report: dict[str, Any], report_file: str, from_cache: bool) -> RosterRow:
    """Build an OK row from one character's quick export JSON (schema character-report/0).

    Pure function. Use the same functions the PvE report uses, so the numbers match the
    character's own page: ``gearscore.character_score(report["equipment"], class)`` and
    ``checks.run_checks(report)``. Main tree per specialization is its ``label`` when the
    specialization has points, otherwise "-". first_issue is the text of the first issue.
    """
    raise NotImplementedError


def placeholder_row(name: str, realm: str, status: str, note: str | None = None) -> RosterRow:
    """Row for NOT_FOUND, NOT_RUN or FAILED: name, realm, status, armory link, note."""
    raise NotImplementedError


def sort_rows(rows: list[RosterRow]) -> list[RosterRow]:
    """Sort by name, case-insensitive (owner decision)."""
    raise NotImplementedError


def summary_file_name(now: datetime) -> str:
    """raid-YYYY-MM-DD-HHMM.html for the local time ``now``."""
    raise NotImplementedError


def render_summary(rows: list[RosterRow], realm: str, run_time: datetime) -> str:
    """Self-contained HTML summary page in the style of pve_report (inline CSS, no scripts).

    Header: realm, run time, number of characters, how many came from cache, and how many
    rows are not OK. Table columns, in order: Name, Class, Main trees ("Holy / Discipline"),
    GearScore, Avg item level, Issues, Warnings, First issue, Report (relative link),
    Armory (link), Data age. Every armory-derived text is HTML-escaped.
    """
    raise NotImplementedError


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
