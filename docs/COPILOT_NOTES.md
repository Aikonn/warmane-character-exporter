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

### 2026-11-23 · Task · I: Roster accepts names on one line
Module: roster.py (`parse_names` only), tests/test_roster.py, README.md, docs/tasks/raid-roster.md

Owner request (2026-11-23): the roster input must also accept all names on one line separated by spaces, with any extra spaces or tabs at the end, e.g. `Hyacinthus Uzbudu Nitkov Renoster Dutchflower Madoxx Denerriss Ypestis Sofla Aikka   `. Split each line on whitespace and commas (`raw_line.replace(",", " ").split()`) and run every part through the existing checks (realm suffix, letters only, case normalisation, de-duplication, 40-name limit). Error messages keep the line number. One name per line must keep working. Known trade-off: `Alice - Onyxia` (spaces around the dash) now gives errors; `Alice-Onyxia` still works.

Done when:
1. `parse_names` accepts the example line above (30 trailing spaces included) and returns the 10 names with no errors; a mixed input with spaces, a comma, a tab, a `Name-Onyxia` part and a duplicate is covered by a new test.
2. The existing test that used `"Two Words"` as a bad name uses a still-invalid name such as `"Two_Words"`.
3. The docstring, README.md and docs/tasks/raid-roster.md no longer say "one name per line" only.
4. `PYTHONPATH=src python -m unittest discover -s tests` passes.

### 2026-11-19 · Task · H: Gem quality check and spec-aware major glyph check
Module: checks.py, roster.py, pve_report.py (one text line), tests

Owner decisions (2026-11-19): common-quality gems are an issue; uncommon gems in item level 251+ gear are a warning; meta gems are excluded. Missing major glyphs are an issue only when no spec has all 3; once one spec has all 3, other specs with talent points and fewer than 3 major glyphs get a warning. Full spec: `docs/tasks/gem-quality-and-glyphs.md`.

Done when: the "Done when" points 1-4 in `docs/tasks/gem-quality-and-glyphs.md` hold.

## Resolved

### 2026-11-17 · Issue · Windows system theme check pending
Module: character PvE report tests

The full suite passes (315 tests), and the quick/full fixture HTML is unchanged outside `<style>`. Both reports rendered with expected light and dark colors in browser `prefers-color-scheme` emulation. Windows' global appearance setting was not toggled, so task G's point 4 remains unverified.

### 2026-11-17 · Task · G: Dark and light theme for character reports
Module: pve_report.py (CSS only), tests

Owner decision (2026-11-17): character reports get a dark version that follows the system setting, same palette as the roster summary; no class colouring. Exact CSS and checks: `docs/tasks/report-dark-theme.md`.

Done when: the "Done when" points 1-4 in `docs/tasks/report-dark-theme.md` hold.

**Claude:** Accepted task G (2026-11-18). 315 tests OK (1 skipped) in the cloud clone. The owner checked the character reports with the Windows light/dark setting and they work as wished, so point 4 holds.

Older entries: `docs/COPILOT_NOTES_ARCHIVE.md`.
