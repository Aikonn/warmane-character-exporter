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

### 2026-11-17 · Task · F: Roster summary look (theme, grouped issues, quick-sum copy)
Module: roster.py, checks.py, tests, docs/tasks/raid-roster.md

Owner decisions (2026-11-17). Full spec: `docs/tasks/roster-summary-look.md`; reference mockup: `docs/tasks/roster-summary-mockup.html` (its "Mockup only" switch is not part of the product).

Summary: follow the system light/dark setting (dark = class-coloured name and class text, light = class-tinted rows); "Main trees" heading becomes "Spec1 / Spec2"; Report and Armory columns merge into the Name cell (name links the report, small armory icon); grouped Issues list using a new `kind` field on findings; per-character copy button in the Issues count cell copying one chat line like `Name 4.8k - missing 10 enchants, 11 gems, buckle`; Data age shown relative ("58 min ago") while still sorting on the timestamp.

Done when: the "Done when" points 1-7 in `docs/tasks/roster-summary-look.md` hold.

## Resolved

(none)

Older entries: `docs/COPILOT_NOTES_ARCHIVE.md`.
