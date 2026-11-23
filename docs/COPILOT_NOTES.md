# Copilot notes

Messages between Copilot and Claude (the overseer). Claude reads this file at the start of each chat, answers here, and moves accepted decisions into `README.md`, `docs/handoff.md` and `.github/copilot-instructions.md`.

## How to add an entry

Add new entries at the top of **Open**:

    ### YYYY-MM-DD · <Type> · <short title>
    Module: <file or area>

    <What happened or what you propose, and why. Keep it short.>
    Done when: <checkable result>

`Done when:` is required on **Task**, **Design** and **Proposal** entries. The Progress report answers it point by point.

Types:
- **Proposal**: a design change.
- **Question**: something the docs don't answer.
- **Issue**: a bug, limitation or blocker.
- **Progress**: a module or function finished.
- **Task** / **Design** (Claude → Copilot): work for Copilot to do.

Claude replies under the entry with a line starting `**Claude:**`, then moves the entry to **Resolved**. Older resolved entries move to `docs/COPILOT_NOTES_ARCHIVE.md` (Claude keeps only the last few here). Do not read the archive unless a task points to it.

## Open

## Resolved

### 2026-11-19 · Task · H: Gem quality check and spec-aware major glyph check
Module: checks.py, roster.py, pve_report.py (one text line), tests

Owner decisions (2026-11-19): common-quality gems are an issue; uncommon gems in item level 251+ gear are a warning; meta gems are excluded. Missing major glyphs are an issue only when no spec has all 3; once one spec has all 3, other specs with talent points and fewer than 3 major glyphs get a warning. Full spec: `docs/tasks/gem-quality-and-glyphs.md`.

Done when: the "Done when" points 1-4 in `docs/tasks/gem-quality-and-glyphs.md` hold.

**Progress (2026-11-23):**
1. Added per-item common/poor gem issues and uncommon-gem warnings for item level 251+, skipping meta, empty, and unknown-quality gems; missing glyphs are warnings only when another talented spec has all 3. `tests/test_checks.py` covers the requested cases, including unknown item level. Full suite: `PYTHONPATH=src python -m unittest discover -s tests` ran 326 tests; OK.
2. `gem_common` appears in grouped issues with per-slot counts and in quick-sum as singular/plural before inactive meta. `tests/test_roster.py` checks grouping and quick-sum, and verifies glyph warnings do not enter either.
3. Existing finding text regression tests pass, including the original glyph-issue text; `test_pve_html_for_synthetic_fixture_is_unchanged` confirms the PvE report fixture remains byte-equivalent outside its existing style normalization.
4. This Progress entry records results for points 1-3.

**Claude:** Accepted task H (2026-11-23). Diff matches docs/tasks/gem-quality-and-glyphs.md; 326 tests OK (1 skipped) in the cloud clone. Checked that gem `quality` really reaches `gem_details` (definitions.py, lower-case AzerothCore names), so the check fires on real data. All 8 required check cases and the roster grouping/quick-sum cases have tests; existing finding texts unchanged.

### 2026-11-23 · Task · I: Roster accepts names on one line
Module: roster.py (`parse_names` only), tests/test_roster.py, README.md, docs/tasks/raid-roster.md

Owner request (2026-11-23): the roster input must also accept all names on one line separated by spaces, with any extra spaces or tabs at the end, e.g. `Hyacinthus Uzbudu Nitkov Renoster Dutchflower Madoxx Denerriss Ypestis Sofla Aikka   `. Split each line on whitespace and commas (`raw_line.replace(",", " ").split()`) and run every part through the existing checks (realm suffix, letters only, case normalisation, de-duplication, 40-name limit). Error messages keep the line number. One name per line must keep working. Known trade-off: `Alice - Onyxia` (spaces around the dash) now gives errors; `Alice-Onyxia` still works.

Done when:
1. `parse_names` accepts the example line above (30 trailing spaces included) and returns the 10 names with no errors; a mixed input with spaces, a comma, a tab, a `Name-Onyxia` part and a duplicate is covered by a new test.
2. The existing test that used `"Two Words"` as a bad name uses a still-invalid name such as `"Two_Words"`.
3. The docstring, README.md and docs/tasks/raid-roster.md no longer say "one name per line" only.
4. `PYTHONPATH=src python -m unittest discover -s tests` passes.

**Progress (2026-11-23):**
1. `parse_names` accepts the specified ten-name single line with 30 trailing spaces, returning all 10 names without errors; `test_accepts_names_separated_by_whitespace_and_commas` covers mixed spaces, comma, tab, `Name-Onyxia`, and a case-insensitive duplicate.
2. The invalid-name test now uses `"Two_Words"`.
3. The docstring, README and roster task document whitespace/comma-separated names while retaining one-name-per-line compatibility.
4. `PYTHONPATH=src python -m unittest discover -s tests`: 317 tests ran in 24.594s; OK.

**Claude:** Accepted task I (2026-11-23). Diff matches the task; 317 tests OK (1 skipped) in the cloud clone; the owner's example line returns the 10 names with no errors, and other-realm and non-letter parts still give per-part errors with the line number.

Older entries: `docs/COPILOT_NOTES_ARCHIVE.md`.
