# Task: raid roster report

Status: stage 1 (pure functions, not-found probe) done 2026-11-15; stage 2 (fetching, CLI) done; stage 3 (transport fix, progress, launcher) assigned. Owner decisions are marked (owner).

## Goal

When assembling a raid, paste a list of character names, choose the realm, and get a quick PvE report for every character plus one summary page with a table of all of them.

## Launcher (Start-Report.ps1)

- First dialog gets a third choice: "Raid roster: quick report for a list of characters".
- Roster dialog: multi-line text box (one name per line), realm drop-down (Onyxia, Icecrown; last used is the default, remembered in .warmane-cache/launcher-realm.txt), "Refresh all" checkbox (unchecked by default), output folder chooser (last used folder remembered in .warmane-cache/launcher-roster-folder.txt; default Downloads).
- The progress window shows "Character N of M: Name" and the existing step progress.
- When done, the summary page opens in the browser.

## Input cleanup (owner: yes)

- Trim spaces, ignore blank lines and duplicates (case-insensitive).
- Accept "Name-Realm" (a realm suffix that differs from the chosen realm is an input error shown before any request).
- Normalize case to Warmane style: first letter upper, the rest lower.
- Reject names that are not letters only (WotLK names; accented letters allowed) before any request.
- At most 40 names per run (about 120 live requests, inside the daily budget of 500).

## Fetching

- Reuse the quick path: `run_character(..., quick=True)` per character, one character at a time, existing 1 s spacing and budget.
- Cache age for the roster (owner): reuse cached character data younger than 2 hours; "Refresh all" ignores the cache. Pass the age as a parameter (`max_age_seconds`) through snapshot/fetch; do not change the 15 minute default for single-character runs.
- Errors (owner: ok, to be tuned): a character that does not exist marks its row "not found" and the run continues; an access block, rate limit or budget exhaustion stops the run, and the summary is still written for the characters done so far, with the rest marked "not run".
- Open point for the implementer: how the armory answers for a non-existent character is not yet verified. Check it with one live request (for example a random 12-letter name) and add a sanitized fixture before coding the "not found" branch.

## Output (owner)

- Everything goes into the one folder the user selected; no subfolder.
- Per character: `<name>-<realm>-quick-pve.html` (same file as today's quick report; a later run overwrites it).
- Summary: `raid-YYYY-MM-DD-HHMM.html` (local time of the run).
- New CLI entry point so it works without the launcher, for example:
  `python -m warmane_exporter.roster --realm Onyxia --names-file names.txt --output-dir DIR [--refresh] [--max-age-minutes 120]`

## Summary page

Same style as the other reports: one self-contained HTML file, inline CSS, no scripts, all armory text HTML-escaped.

Columns:
1. Name
2. Class
3. Main tree per specialization: the talent tree with the most points, for example "Holy / Discipline"; "-" for a specialization with no points (owner: tree names, no point numbers)
4. GearScore
5. Average item level
6. Issues (count)
7. Warnings (count)
8. First issue as short text (empty when none)
9. Report: relative link to the local quick report file
10. Armory: link to https://armory.warmane.com/character/NAME/REALM/summary
11. Data age (cached at, or "fresh")

- Rows sorted by name (owner).
- Rows with status "not found", "not run" or "failed" keep the name and armory link and show the status and reason in the First issue column (marked gray italic); other cells empty.
- Header line: realm, run time, number of characters, how many came from cache.
- Professions are not shown (owner).

## Structure

- `roster.py`: input parsing (pure, tested), orchestration loop, summary row building from each character's quick export JSON (pure, tested), HTML rendering.
- Reuse `checks.run_checks` and `gearscore.character_score` results already in the quick export; do not recompute differently.
- Tests: input cleanup cases, row building from a fixture export, sorting, not-found and not-run rows, HTML escaping. No network in tests.

## Not in scope

- Role detection (the active specialization is unknown to the armory).
- Mixed realms in one run.
- Full PvE reports for a roster.
