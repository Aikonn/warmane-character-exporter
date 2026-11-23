"""Raid roster: quick PvE report for a list of characters plus one summary page.

python -m warmane_exporter.roster --realm Onyxia --names-file names.txt --output-dir DIR [--refresh] [--max-age-minutes 120] [--timing]

Specification: docs/tasks/raid-roster.md. For each name the quick path of run.py is used
(3 live requests, none when the cache is younger than --max-age-minutes). Each character's
quick report is copied into DIR as <name>-<realm>-quick-pve.html and a summary page
raid-YYYY-MM-DD-HHMM.html is written next to them. Everything goes into DIR, no subfolder.
Timing is opt-in with --timing or WARMANE_TIMING=1; it is written to stderr and
.warmane-cache/timing-YYYYMMDD-HHMM.log.
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

from .cache import ResponseCache
from .checks import run_checks
from .fingerprint import cached_fingerprint, html_fingerprint, tool_version_hash
from .gearscore import character_score
from .timing import TimingLog, activate, timed, timing_requested
from .transport import StopRequested, reset_run_pacing

REALMS = ("Onyxia", "Icecrown")
MAX_NAMES = 40
DEFAULT_MAX_AGE_MINUTES = 120
ARMORY_URL = "https://armory.warmane.com/character/{name}/{realm}/summary"
STOP_NOTE = "Stopped roster: access block, rate limit, or request budget exhausted."
USER_STOP_NOTE = "stopped by user"
CLASS_STYLES = {
    "death knight": ("c-death-knight", "#C41F3B"),
    "druid": ("c-druid", "#FF7D0A"),
    "hunter": ("c-hunter", "#ABD473"),
    "mage": ("c-mage", "#69CCF0"),
    "paladin": ("c-paladin", "#F58CBA"),
    "priest": ("c-priest", "#FFFFFF"),
    "rogue": ("c-rogue", "#FFF569"),
    "shaman": ("c-shaman", "#0070DE"),
    "warlock": ("c-warlock", "#9482C9"),
    "warrior": ("c-warrior", "#C79C6E"),
}

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
    issue_findings: list[dict[str, Any]] = field(default_factory=list)
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

    - Split each line on whitespace and commas; ignore blank lines.
    - "Name-Realm" is accepted; a realm part that differs from ``realm`` (case-insensitive)
      is an error for that part.
    - Names must be letters only (accented letters allowed, as WotLK allows them);
      anything else is an error for that part.
    - Normalize to Warmane style: first letter upper case, the rest lower case.
    - Drop duplicates (case-insensitive), keep the first occurrence and input order.
    - More than MAX_NAMES distinct names is an error (names stay empty in that case).
    Errors name the line number and the offending part.
    """
    canonical_realm = _canonical_realm(realm)
    if canonical_realm is None:
        return RosterInput(errors=[f"Unsupported realm: {realm!r}. Supported realms: {', '.join(REALMS)}."])

    names: list[str] = []
    errors: list[str] = []
    seen: set[str] = set()
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        for part in raw_line.replace(",", " ").split():
            name = part
            if "-" in part:
                name, suffix = part.rsplit("-", 1)
                if suffix.casefold() != canonical_realm.casefold():
                    errors.append(
                        f"Line {line_number}: {part!r} specifies a different realm; expected {canonical_realm}."
                    )
                    continue

            name = normalize("NFC", name)
            if not name or not name.isalpha():
                errors.append(f"Line {line_number}: {part!r} must contain letters only.")
                continue

            normalized = name[0].upper() + name[1:].lower()
            key = normalized.casefold()
            if key not in seen:
                names.append(normalized)
                seen.add(key)
                if len(names) > MAX_NAMES:
                    return RosterInput(errors=[
                        f"Line {line_number}: {part!r} exceeds the limit of {MAX_NAMES} distinct names."
                    ])

    return RosterInput(names=names, errors=errors)


def build_row(report: dict[str, Any], report_file: str, from_cache: bool) -> RosterRow:
    """Build an OK row from one character's quick export JSON (schema character-report/0).

    Pure function. Use the same functions the PvE report uses, so the numbers match the
    character's own page: ``gearscore.character_score(report["equipment"], class)`` and
    ``checks.run_checks(report)``. Main tree per specialization is the named tree with the
    most reported points, otherwise "-"; when per-tree names are unavailable, fall back to
    the specialization label. Pad to two entries when fewer specs are present. Keep the
    structured issue findings from ``run_checks`` for grouped display and quick-sum copying.
    """
    identity = report["identity"]
    name = identity["name"]
    realm = identity["realm"]
    class_name = identity.get("class")
    score = character_score(report["equipment"], class_name)
    findings = run_checks(report)
    snapshot_time = report.get("snapshot_time")
    data_time = float(snapshot_time) if isinstance(snapshot_time, (int, float)) else None
    main_trees = []
    for spec in report.get("specializations") or []:
        split = spec.get("split") or []
        if not any(isinstance(points, int) and points > 0 for points in split):
            main_trees.append("-")
            continue

        tree_names = spec.get("trees") or [
            tree.get("tree") for tree in spec.get("talent_detail") or []
        ]
        main_index = max(
            (index for index, points in enumerate(split) if isinstance(points, int)),
            key=lambda index: split[index],
            default=None,
        )
        main_tree = (
            tree_names[main_index]
            if main_index is not None and main_index < len(tree_names)
            else None
        )
        main_trees.append(main_tree or spec.get("label") or "-")
    main_trees.extend("-" for _ in range(max(0, 2 - len(main_trees))))
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
        issue_findings=issues,
        report_file=report_file,
        armory_url=_armory_url(name, realm),
        data_time=data_time,
        from_cache=from_cache,
    )


def group_issues(issues: list[dict[str, Any]]) -> list[tuple[str, str]]:
    """Return grouped issue-label/detail lines, preserving equipment and spec order."""
    grouped: list[tuple[str, str]] = []
    consumed: set[int] = set()

    def collect_slots(kind: str) -> list[tuple[int, dict[str, Any]]]:
        return [
            (index, issue)
            for index, issue in enumerate(issues)
            if issue.get("kind") == kind and issue.get("slot") is not None
        ]

    def append_slot_group(kind: str, label: str) -> None:
        selected = collect_slots(kind)
        if not selected:
            return
        slots = [str(issue["slot"]) for _, issue in selected]
        count = len(selected)
        grouped.append((f"{label} ({count}):", ", ".join(slots)))
        consumed.update(index for index, _ in selected)

    append_slot_group("enchant", "No enchant")
    append_slot_group("ring_enchant", "No ring enchant (Enchanter)")

    socket_counts: dict[str, int] = {}
    socket_indices: list[int] = []
    for index, issue in collect_slots("sockets"):
        count = issue.get("count")
        if not isinstance(count, int) or isinstance(count, bool) or count <= 0:
            continue
        slot = str(issue["slot"])
        socket_counts[slot] = socket_counts.get(slot, 0) + count
        socket_indices.append(index)
    if socket_indices:
        socket_total = sum(socket_counts.values())
        socket_details = ", ".join(
            f"{slot} {count}" for slot, count in socket_counts.items()
        )
        grouped.append((f"Empty sockets ({socket_total}):", socket_details))
        consumed.update(socket_indices)

    common_gem_counts: dict[str, int] = {}
    common_gem_indices: list[int] = []
    for index, issue in collect_slots("gem_common"):
        count = issue.get("count")
        if not isinstance(count, int) or isinstance(count, bool) or count <= 0:
            continue
        slot = str(issue["slot"])
        common_gem_counts[slot] = common_gem_counts.get(slot, 0) + count
        common_gem_indices.append(index)
    if common_gem_indices:
        common_gem_total = sum(common_gem_counts.values())
        common_gem_details = ", ".join(
            f"{slot} {count}" for slot, count in common_gem_counts.items()
        )
        grouped.append((f"Common gems ({common_gem_total}):", common_gem_details))
        consumed.update(common_gem_indices)

    meta_slots: list[str] = []
    meta_indices: list[int] = []
    for index, issue in collect_slots("meta"):
        slot = str(issue["slot"])
        if slot not in meta_slots:
            meta_slots.append(slot)
        meta_indices.append(index)
    if meta_indices:
        grouped.append(("Meta gem not active:", ", ".join(meta_slots)))
        consumed.update(meta_indices)

    buckle_indices = [
        index for index, issue in enumerate(issues) if issue.get("kind") == "buckle"
    ]
    if buckle_indices:
        grouped.append(("Belt buckle missing", ""))
        consumed.update(buckle_indices)

    def append_spec_group(kind: str, label: str) -> None:
        totals: dict[int, int] = {}
        selected_indices: list[int] = []
        for index, issue in enumerate(issues):
            spec_index = issue.get("spec_index")
            count = issue.get("count")
            if (
                issue.get("kind") == kind
                and isinstance(spec_index, int) and not isinstance(spec_index, bool) and spec_index >= 0
                and isinstance(count, int) and not isinstance(count, bool) and count > 0
            ):
                totals[spec_index] = totals.get(spec_index, 0) + count
                selected_indices.append(index)
        if totals:
            details = ", ".join(
                f"Spec{spec_index + 1} {count}" for spec_index, count in sorted(totals.items())
            )
            grouped.append((label, details))
            consumed.update(selected_indices)

    append_spec_group("talents", "Unspent talent points:")
    append_spec_group("glyphs", "Major glyphs empty:")

    for index, issue in enumerate(issues):
        if index in consumed:
            continue
        text = str(issue.get("text") or "")
        slot = issue.get("slot")
        grouped.append((f"{slot}:" if slot is not None else "", text))
    return grouped


def quick_sum(row: RosterRow) -> str | None:
    """Return one chat line for an OK row with issues, otherwise None."""
    if row.status != OK or not row.issue_findings:
        return None

    enchant_count = sum(issue.get("kind") in ("enchant", "ring_enchant") for issue in row.issue_findings)
    gem_count = 0
    glyph_count = 0
    talent_count = 0
    common_gem_count = 0
    for issue in row.issue_findings:
        count = issue.get("count")
        if not isinstance(count, int) or isinstance(count, bool) or count <= 0:
            continue
        if issue.get("kind") == "sockets":
            gem_count += count
        elif issue.get("kind") == "gem_common":
            common_gem_count += count
        elif issue.get("kind") == "glyphs":
            glyph_count += count
        elif issue.get("kind") == "talents":
            talent_count += count

    missing: list[str] = []
    if enchant_count:
        missing.append(f"{enchant_count} enchant{'s' if enchant_count != 1 else ''}")
    if gem_count:
        missing.append(f"{gem_count} gem{'s' if gem_count != 1 else ''}")
    if any(issue.get("kind") == "buckle" for issue in row.issue_findings):
        missing.append("buckle")
    if glyph_count:
        missing.append(f"{glyph_count} glyph{'s' if glyph_count != 1 else ''}")

    known_kinds = {"enchant", "ring_enchant", "sockets", "gem_common", "buckle", "glyphs", "talents", "meta"}
    other_count = 0
    for issue in row.issue_findings:
        kind = issue.get("kind")
        count = issue.get("count")
        has_count = isinstance(count, int) and not isinstance(count, bool) and count > 0
        if kind not in known_kinds or (kind in ("sockets", "gem_common", "glyphs", "talents") and not has_count):
            other_count += 1
    other: list[str] = []
    if talent_count:
        other.append(f"{talent_count} unspent talent{'s' if talent_count != 1 else ''}")
    if common_gem_count:
        other.append(f"{common_gem_count} common gem{'s' if common_gem_count != 1 else ''}")
    if any(issue.get("kind") == "meta" for issue in row.issue_findings):
        other.append("inactive meta gem")
    if other_count:
        other.append(f"{other_count} other")

    score = "?" if row.gearscore is None else f"{row.gearscore // 100 / 10:.1f}k"
    prefix = f"{row.name} {score}"
    if missing:
        message = f"{prefix} - missing {', '.join(missing)}"
        if other:
            message += f"; {', '.join(other)}"
    elif other:
        message = f"{prefix} - {', '.join(other)}"
    else:
        message = prefix
    return message


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


def _preflight_character(
    name: str,
    realm: str,
    response_cache: ResponseCache,
    exports_dir: Path,
    output_dir: Path,
    tool_version: str,
    max_age_seconds: int,
) -> tuple[str, RosterRow | None]:
    fingerprint = cached_fingerprint(
        response_cache, name, realm, tool_version, max_age_seconds=max_age_seconds,
    )
    if fingerprint is None:
        return "run", None

    stem = f"{name.lower()}-{realm.lower()}-quick"
    report_path = exports_dir / f"{stem}.json"
    source_html = exports_dir / f"{stem}-pve.html"
    target_html = output_dir / source_html.name
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if not isinstance(report, dict):
            return "run", None
        if report.get("fingerprint") != fingerprint:
            return "run", None
        row = build_row(report, target_html.name, from_cache=True)
        if html_fingerprint(target_html) == fingerprint:
            return "skip", row
        if html_fingerprint(source_html) == fingerprint:
            return "copy", row
    except (OSError, UnicodeError, ValueError, KeyError, TypeError):
        pass
    return "run", None


def summary_file_name(now: datetime) -> str:
    """raid-YYYY-MM-DD-HHMM.html for the local time ``now``."""
    return now.strftime("raid-%Y-%m-%d-%H%M.html")


def render_summary(
    rows: list[RosterRow],
    realm: str,
    run_time: datetime,
    rate_limit_waits: int = 0,
    final_spacing_seconds: float = 1.0,
) -> str:
    """Render a self-contained, system-themed HTML roster summary."""
    cached_count = sum(row.from_cache is True for row in rows)
    not_ok_count = sum(row.status != OK for row in rows)
    headings = (
        ("Name", "text"), ("Class", "text"), ("Spec1 / Spec2", "text"),
        ("GearScore", "num"), ("Avg item level", "num"), ("Issues", "num"),
        ("Warnings", "num"), ("Issues list", None), ("Data age", "num"),
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

    def sortable_cell(content: str, sort_key: str, cell_class: str | None = None) -> str:
        class_attr = f' class="{cell_class}"' if cell_class else ""
        return f'<td{class_attr} data-sort="{escape(sort_key, quote=True)}">{content}</td>'

    def armory_link(row: RosterRow) -> str:
        if not row.armory_url:
            return ""
        aria_label = escape(f"Armory for {row.name}", quote=True)
        return (
            f'<a class="armory" href="{escape(row.armory_url, quote=True)}" title="Armory" '
            f'aria-label="{aria_label}" target="_blank" rel="noopener">'
            '<svg viewBox="0 0 16 16" width="12" height="12" aria-hidden="true">'
            '<path d="M9 2h5v5M14 2 7 9M12 9v4a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1h4" '
            'fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>'
            "</svg></a>"
        )

    def class_tint(color: str) -> str:
        if color == "#FFFFFF":
            return "#EDEDED"
        channels = [int(color[index:index + 2], 16) for index in (1, 3, 5)]
        return "#" + "".join(
            f"{round(255 - (255 - channel) * 0.22):02X}" for channel in channels
        )

    table_rows: list[str] = []
    for row in sort_rows(rows):
        name_sort = row.name.casefold()
        armory = armory_link(row)
        if row.status != OK:
            reason = row.note or row.status
            status_note = f'<span class="status">{escape(row.status)}: {escape(reason)}</span>'
            name_cell = (
                f'<td class="name-cell" data-sort="{escape(name_sort, quote=True)}">'
                f'{escape(row.name)}{armory}</td>'
            )
            cells = [name_cell, *(sortable_cell("", "") for _ in range(6)),
                     f"<td>{status_note}</td>", sortable_cell("", "")]
            row_class = "not-ok"
        else:
            name = (
                f'<a class="name" href="{escape(row.report_file, quote=True)}">{escape(row.name)}</a>'
                if row.report_file else escape(row.name)
            )
            class_style = CLASS_STYLES.get((row.class_name or "").casefold())
            class_name = escape(row.class_name or "")
            data_age = ""
            age_title = ""
            age_attrs = ""
            if row.data_time is not None and row.from_cache is not None:
                timestamp = datetime.fromtimestamp(row.data_time).strftime("%Y-%m-%d %H:%M")
                state = "cache" if row.from_cache else "fresh"
                freshness = "from cache" if row.from_cache else "fresh"
                data_age = f"{timestamp} ({freshness})"
                age_title = f' title="{escape(data_age, quote=True)}"'
                age_attrs = (
                    f' data-age="{escape(str(row.data_time), quote=True)}"'
                    f' data-state="{state}"'
                )
            issue_list = ""
            grouped = group_issues(row.issue_findings)
            if grouped:
                issue_list = (
                    '<div class="issues">'
                    + "".join(
                        "<div>"
                        + (f'<span class="lbl">{escape(label)}</span>' if label else "")
                        + (f" {escape(detail)}" if label and detail else escape(detail))
                        + "</div>"
                        for label, detail in grouped
                    )
                    + "</div>"
                )
            quick_message = quick_sum(row)
            issue_count = count_cell(row.issues, "count-issue")
            if quick_message is not None:
                button = (
                    '<button type="button" class="copy" title="Copy quick-sum message" '
                    f'aria-label="Copy quick-sum message for {escape(row.name, quote=True)}" '
                    f'data-quick-sum="{escape(quick_message, quote=True)}">'
                    '<svg viewBox="0 0 16 16" width="13" height="13" aria-hidden="true">'
                    '<rect x="5" y="5" width="9" height="9" rx="1.5" fill="none" '
                    'stroke="currentColor" stroke-width="1.5"/>'
                    '<path d="M11 5V3.5A1.5 1.5 0 0 0 9.5 2h-6A1.5 1.5 0 0 0 2 3.5v6A1.5 1.5 0 0 0 3.5 11H5" '
                    'fill="none" stroke="currentColor" stroke-width="1.5"/>'
                    "</svg></button>"
                )
                issue_count = button + issue_count
            row_class = class_style[0] if class_style else ""
            row_class_attr = f' class="{row_class}"' if row_class else ""
            cells = [
                f'<td class="name-cell" data-sort="{escape(name_sort, quote=True)}">'
                f'{name}{armory}</td>',
                sortable_cell(
                    f'<span class="cls-label">{class_name}</span>' if class_name else "",
                    (row.class_name or "").casefold(),
                    "cls",
                ),
                sortable_cell(
                    escape(" / ".join(row.main_trees)),
                    " / ".join(row.main_trees).casefold(),
                    "spec",
                ),
                sortable_cell(
                    "" if row.gearscore is None else str(row.gearscore),
                    "" if row.gearscore is None else str(row.gearscore),
                    "num",
                ),
                sortable_cell(
                    "" if row.average_item_level is None else f"{row.average_item_level:g}",
                    "" if row.average_item_level is None else str(row.average_item_level),
                    "num",
                ),
                sortable_cell(
                    issue_count,
                    "" if row.issues is None else str(row.issues),
                    "num",
                ),
                sortable_cell(
                    count_cell(row.warnings, "count-warn"),
                    "" if row.warnings is None else str(row.warnings),
                    "num",
                ),
                f"<td>{issue_list}</td>",
                f'<td class="age" data-sort="{escape("" if not data_age else str(row.data_time), quote=True)}"'
                f'{age_attrs}{age_title}>{escape(data_age)}</td>',
            ]
        row_class_attr = ' class="not-ok"' if row.status != OK else row_class_attr
        table_rows.append(f"<tr{row_class_attr}>" + "".join(cells) + "</tr>")

    table_head = "".join(
        f'<th class="sortable" data-type="{sort_type}">{heading}</th>'
        if sort_type is not None else f"<th>{heading}</th>"
        for heading, sort_type in headings
    )
    class_style_rules = "".join(
        f".{css_class}{{--class-color:{color};--class-tint:{class_tint(color)}}}"
        for css_class, color in CLASS_STYLES.values()
    )
    class_cells = ",".join(f"tr.{css_class} td" for css_class, _ in CLASS_STYLES.values())
    class_labels = ",".join(
        selector
        for css_class, _ in CLASS_STYLES.values()
        for selector in (f"tr.{css_class} .name", f"tr.{css_class} .cls-label")
    )
    rate_limit_summary = (
        f"; rate-limit waits: {rate_limit_waits}, spacing {final_spacing_seconds:g} s"
        if rate_limit_waits
        else ""
    )
    sort_script = """<script>
const headers = document.querySelectorAll("th.sortable");
const body = document.querySelector("tbody");
let activeHeader = null;
let descending = false;
function sortRows(column, type, reverse) {
  const rows = Array.from(body.rows);
  rows.sort((a, b) => {
    const aBad = a.classList.contains("not-ok");
    const bBad = b.classList.contains("not-ok");
    if (aBad !== bBad) return aBad ? 1 : -1;
    if (aBad) return a.cells[0].dataset.sort.localeCompare(b.cells[0].dataset.sort);
    const av = a.cells[column].dataset.sort || "";
    const bv = b.cells[column].dataset.sort || "";
    if (!av || !bv) return av ? -1 : bv ? 1 : 0;
    const order = type === "num" ? Number(av) - Number(bv) : av.localeCompare(bv);
    return reverse ? -order : order;
  });
  rows.forEach(row => body.appendChild(row));
}
sortRows(0, "text", false);
headers.forEach(header => header.addEventListener("click", () => {
  descending = activeHeader === header ? !descending : false;
  activeHeader = header;
  sortRows(header.cellIndex, header.dataset.type, descending);
  headers.forEach(item => {
    item.removeAttribute("aria-sort");
    const marker = item.querySelector(".sort-marker");
    if (marker) marker.remove();
  });
  header.setAttribute("aria-sort", descending ? "descending" : "ascending");
  const marker = document.createElement("span");
  marker.className = "sort-marker";
  marker.textContent = descending ? " ▼" : " ▲";
  header.appendChild(marker);
}));
const viewedAt = Date.now() / 1000;
document.querySelectorAll("td.age[data-age]").forEach(cell => {
  const age = Math.max(0, viewedAt - Number(cell.dataset.age));
  let text;
  if (age < 90) text = "just now";
  else if (age < 3600) text = `${Math.floor(age / 60)} min ago`;
  else if (age < 36 * 3600) text = `${Math.floor(age / 3600)} h ago`;
  else text = `${Math.floor(age / 86400)} d ago`;
  if (cell.dataset.state === "cache") text += " (cache)";
  cell.textContent = text;
});
async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch (error) {
    const textarea = document.createElement("textarea");
    textarea.value = text;
    textarea.style.position = "fixed";
    textarea.style.opacity = "0";
    try {
      document.body.appendChild(textarea);
      textarea.select();
      return document.execCommand("copy");
    } catch (fallbackError) {
      return false;
    } finally {
      textarea.remove();
    }
  }
}
document.querySelectorAll("button.copy").forEach(button => {
  let resetTimer;
  button.addEventListener("click", async () => {
    const copied = await copyText(button.dataset.quickSum || "");
    button.classList.toggle("copied", copied);
    button.title = copied ? "Copied" : "Copy failed";
    window.clearTimeout(resetTimer);
    resetTimer = window.setTimeout(() => {
      button.classList.remove("copied");
      button.title = "Copy quick-sum message";
    }, 1500);
  });
});
</script>"""
    return (
        "<!doctype html>\n<html lang=\"en\">\n<head>\n"
        '<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>Raid roster - {escape(realm)}</title>\n"
        "<style>"
        ":root{--bg:#ffffff;--fg:#111111;--muted:#666666;--border:#c4c4c4;--head:#eeeeee;"
        "--link:#0b57d0;--issue:#b00020;--warn:#a65a00;--lbl:#555555;"
        "--copied:#2e9d4f;color-scheme:light}"
        "@media(prefers-color-scheme:dark){:root{--bg:#16181d;--fg:#e4e6ea;--muted:#9aa0a6;"
        "--border:#383d46;--head:#22262d;--link:#8ab4f8;--issue:#ff6b7f;--warn:#f0a24a;"
        "--lbl:#a8adb5;--copied:#2e9d4f;color-scheme:dark}}"
        "body{font-family:Segoe UI,Arial,sans-serif;max-width:1400px;margin:1.5em auto;padding:0 1em;"
        "background:var(--bg);color:var(--fg);line-height:1.4}"
        "a{color:var(--link)}h1{border-bottom:2px solid var(--border);padding-bottom:.2em}"
        ".meta{color:var(--muted)}.name{color:var(--fg)}"
        "table{border-collapse:collapse;width:100%;margin:.6em 0;font-size:.92em}"
        "th,td{border:1px solid var(--border);padding:.35em .6em;text-align:left;vertical-align:top}"
        "th{background:var(--head)}.sortable{cursor:pointer;user-select:none}.num{text-align:right}"
        ".status{color:var(--muted);font-style:italic}.issues{font-size:.85em}"
        ".issues .lbl{color:var(--lbl);font-weight:600}"
        ".count-issue{color:var(--issue)}.count-warn{color:var(--warn)}.count-high{font-weight:700}"
        ".name-cell,.cls,.spec{white-space:nowrap}.name{font-weight:600;text-decoration:none}"
        ".name:hover{text-decoration:underline}.armory{margin-left:.45em;color:var(--muted);vertical-align:-1px}"
        ".armory:hover{color:var(--link)}.age{white-space:nowrap;color:var(--muted)}"
        + class_style_rules
        + class_cells + "{background:var(--class-tint)}"
        + "@media(prefers-color-scheme:dark){"
        + class_cells + "{background:none}"
        + class_labels + "{color:var(--class-color)}}"
        + "button.copy{float:left;padding:0 .2em;margin-right:.4em;border:1px solid transparent;"
        "background:none;color:var(--muted);line-height:1;vertical-align:middle;cursor:pointer}"
        "button.copy:hover{border-color:var(--border);color:var(--link)}"
        "button.copy.copied{color:var(--copied);border-color:var(--copied)}"
        + "</style>\n</head>\n<body>\n"
        f"<h1>Raid roster - {escape(realm)}</h1>\n"
        f'<p class="meta">Run time: {escape(run_time.strftime("%Y-%m-%d %H:%M"))}; '
        f"characters: {len(rows)}; from cache: {cached_count}; not OK: {not_ok_count}"
        f"{rate_limit_summary}.</p>\n"
        "<table>\n<thead><tr>" + table_head + "</tr></thead>\n<tbody>\n"
        + "\n".join(table_rows)
        + "\n</tbody>\n</table>\n" + sort_script + "\n</body>\n</html>\n"
    )


def run_roster(names: list[str], realm: str, output_dir: Path, cache_dir: str,
               refresh: bool, max_age_minutes: int, timing: bool = False) -> tuple[list[RosterRow], Path]:
    """Run the quick report for each name in order, then write the summary.

    - One character at a time through the quick path of run.py, with the cache age passed
      down to the snapshot step (snapshot gets a --max-age-minutes option; the single
      character default of 15 minutes stays unchanged).
    - Progress lines: "Character N of M: Name" via progress.note, plus the existing steps.
    - Unchanged reports with fresh source cache entries are skipped; missing or stale output
      HTML is copied from the export when its fingerprint still matches.
    - Client data and definitions are loaded once only if a character needs a normal run.
    - Character does not exist: NOT_FOUND row, continue. Access block, rate limit or
      BudgetExhausted: stop; remaining names become NOT_RUN rows. Other failure: FAILED row,
      continue.
    - Copy each quick report HTML into output_dir (overwrite), write the summary there
      atomically (temp name, then rename). Returns the rows and the summary path.
    - With ``timing`` or WARMANE_TIMING=1, log per-character steps and total run time to
      stderr and timing-YYYYMMDD-HHMM.log in cache_dir.
    """
    cache_path = Path(cache_dir)
    log = TimingLog(cache_path) if timing_requested(timing) else None
    with activate(log):
        with timed("total run"):
            return _run_roster(names, realm, output_dir, cache_path, refresh, max_age_minutes)


def _run_roster(names: list[str], realm: str, output_dir: Path, cache_path: Path,
                refresh: bool, max_age_minutes: int) -> tuple[list[RosterRow], Path]:
    from . import run
    from . import snapshot
    from .progress import advance, note, start

    stop_request = cache_path / "stop-request"
    stop_request.unlink(missing_ok=True)
    pacing = reset_run_pacing(stop_request)
    exports_dir = cache_path / "exports"
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    rows: list[RosterRow] = []
    stopped = False
    stopped_by_user = False
    tool_version = tool_version_hash()
    preflight: list[tuple[str, RosterRow | None]] = []
    if refresh:
        preflight = [("run", None) for _ in names]
    else:
        response_cache = ResponseCache(cache_path / "responses.sqlite")
        try:
            preflight = [
                _preflight_character(
                    name, realm, response_cache, exports_dir, output_dir, tool_version,
                    max_age_minutes * 60,
                )
                for name in names
            ]
        finally:
            response_cache.close()
    needs_normal_path = any(action == "run" for action, _ in preflight)
    defs = None
    defs_ctx = None

    start(4 * len(names), "Starting raid roster")
    try:
        if needs_normal_path:
            with timed("definition loading"):
                defs, defs_ctx = snapshot.load_definition_sources()

        for index, name in enumerate(names, start=1):
            with timed(f"{name}@{realm} | total per character"):
                if stopped_by_user:
                    rows.append(placeholder_row(name, realm, NOT_RUN, USER_STOP_NOTE))
                    continue
                if stop_request.exists():
                    rows.append(placeholder_row(name, realm, NOT_RUN, USER_STOP_NOTE))
                    stopped_by_user = True
                    continue
                if stopped:
                    rows.append(placeholder_row(name, realm, NOT_RUN, "An earlier character stopped the roster."))
                    continue

                action, cached_row = preflight[index - 1]
                stem = f"{name.lower()}-{realm.lower()}-quick"
                html_path = exports_dir / f"{stem}-pve.html"
                target_html = output_dir / html_path.name
                if action in ("skip", "copy") and cached_row is not None:
                    note(f"Character {index} of {len(names)}: {name} (unchanged, skipped)")
                    if action == "copy":
                        try:
                            with timed(f"{name}@{realm} | copy to output folder"):
                                if html_path.resolve() != target_html.resolve():
                                    shutil.copyfile(html_path, target_html)
                        except OSError as exc:
                            print(f"Could not copy quick report for {name}: {exc}", file=sys.stderr)
                            rows.append(placeholder_row(name, realm, FAILED, f"Could not copy report: {exc}"))
                            advance(f"{name}: skipped", 4)
                            continue
                    rows.append(cached_row)
                    advance(f"{name}: unchanged, skipped", 4)
                    continue

                note(f"Character {index} of {len(names)}: {name}")
                try:
                    code = run.run_character(
                        name, realm, str(cache_path), refresh, False, quick=True,
                        max_age_minutes=max_age_minutes, start_progress=False,
                        defs=defs, definitions_preloaded=True, tool_version=tool_version,
                    )
                except StopRequested:
                    rows.append(placeholder_row(name, realm, NOT_RUN, USER_STOP_NOTE))
                    stopped_by_user = True
                    continue
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

                report_path = exports_dir / f"{stem}.json"
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
                    with timed(f"{name}@{realm} | copy to output folder"):
                        if html_path.resolve() != target_html.resolve():
                            shutil.copyfile(html_path, target_html)
                except (OSError, UnicodeError, ValueError, KeyError, TypeError) as exc:
                    print(f"Could not assemble roster row for {name}: {exc}", file=sys.stderr)
                    rows.append(placeholder_row(name, realm, FAILED, f"Could not build report row: {exc}"))
                    continue
                rows.append(row)

        run_time = datetime.now()
        summary_path = output_dir / summary_file_name(run_time)
        with timed("summary rendering"):
            rendered = render_summary(
                rows, realm, run_time, pacing.rate_limit_events, pacing.spacing_seconds,
            )
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
    finally:
        if needs_normal_path:
            snapshot.close_definition_sources(defs, defs_ctx)


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
    parser.add_argument("--timing", action="store_true", help="log roster step timings to stderr and the cache directory")
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
            args.refresh, args.max_age_minutes, timing=args.timing,
        )
    except OSError as exc:
        print(f"Error writing roster output: {exc}", file=sys.stderr)
        return 1
    print(f"summary: {summary_path}")
    return 1 if any(row.note == STOP_NOTE for row in rows) else 0


if __name__ == "__main__":
    raise SystemExit(main())
