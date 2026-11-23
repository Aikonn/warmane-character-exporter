# Task: raid roster report

Status: stage 1 (pure functions, not-found probe) done 2026-11-15; stage 2 (fetching, CLI) done; stage 3 (transport fix, progress, launcher) done and accepted on the PC 2026-11-15. Task complete. Summary refinements 2026-11-16 (all issues listed with slot names, colored counts) accepted by the owner. Owner decisions are marked (owner).

## Goal

When assembling a raid, paste a list of character names, choose the realm, and get a quick PvE report for every character plus one summary page with a table of all of them.

## Launcher (Start-Report.ps1)

- First dialog gets a third choice: "Raid roster: quick report for a list of characters".
- Roster dialog: multi-line text box (names separated by whitespace or commas; one per line also works), realm drop-down (Onyxia, Icecrown; last used is the default, remembered in .warmane-cache/launcher-realm.txt), "Refresh all" checkbox (unchecked by default), output folder chooser (last used folder remembered in .warmane-cache/launcher-roster-folder.txt; default Downloads).
- The progress window shows "Character N of M: Name" and the existing step progress.
- A Stop button writes `.warmane-cache/stop-request`; the roster checks it before each character and during transport waits. Stopping keeps completed rows, marks the rest `not run` with note "stopped by user", writes and opens the partial summary. The launcher kills the process if it has not ended within 15 seconds.
- When done, the summary page opens in the browser.

## Input cleanup (owner: yes)

- Trim spaces, ignore blank lines and duplicates (case-insensitive).
- Accept "Name-Realm" (a realm suffix that differs from the chosen realm is an input error shown before any request).
- Normalize case to Warmane style: first letter upper, the rest lower.
- Reject names that are not letters only (WotLK names; accented letters allowed) before any request.
- At most 40 names per run (about 120 live requests, inside the daily budget of 500).

## Fetching

- Reuse the quick path: `run_character(..., quick=True)` per character, one character at a time, adaptive 1/3/5 s spacing and the existing request budget. Pacing is shared across the roster run and resets for the next run.
- On a rate limit, keep the cooldown / `Retry-After` wait and retry behavior. Show waits longer than 2 s in progress without advancing the percentage; log each rate-limit event to stderr and to the timing log when enabled.
- Cache age for the roster (owner): reuse cached character data younger than 2 hours; "Refresh all" ignores the cache. Pass the age as a parameter (`max_age_seconds`) through snapshot/fetch; do not change the 15 minute default for single-character runs.
- Before normal execution, compare the three fresh response-cache bodies and the quick export fingerprint. The tool-version hash covers package Python files, bundled definitions, and the optional client-path config and is computed once per roster run. This check does not fetch data or load definitions. If the fingerprint matches, retain the existing per-character report when its HTML fingerprint matches; otherwise copy the matching export HTML. A stale cache entry, missing or mismatched export, or `--refresh` takes the normal quick path.
- When any character needs the normal path, load client data and definitions once for the roster run, share them with each snapshot, and close them after the run. Single-character runs keep their existing per-run loading behavior.
- Errors (owner: ok, to be tuned): a character that does not exist marks its row "not found" and the run continues; an access block, rate limit or budget exhaustion stops the run, and the summary is still written for the characters done so far, with the rest marked "not run".
- Open point for the implementer: how the armory answers for a non-existent character is not yet verified. Check it with one live request (for example a random 12-letter name) and add a sanitized fixture before coding the "not found" branch.

## Output (owner)

- Everything goes into the one folder the user selected; no subfolder.
- Per character: `<name>-<realm>-quick-pve.html` (same file as today's quick report; a later run overwrites it).
- Quick export JSON stores its content fingerprint in `fingerprint`; the PvE report stores the same value in a `warmane-fingerprint` meta tag. These fields are also written for single-character reports; they do not change visible report content.
- Summary: `raid-YYYY-MM-DD-HHMM.html` (local time of the run).
- New CLI entry point so it works without the launcher, for example:
  `python -m warmane_exporter.roster --realm Onyxia --names-file names.txt --output-dir DIR [--refresh] [--max-age-minutes 120]`

## Summary page

Same style as the other reports: one self-contained HTML file, inline CSS, all armory text HTML-escaped, no external files. Exception (owner, 2026-11-16): the roster summary carries one small inline script for click-to-sort columns; character reports stay script-free.

Columns: Name, Class, Spec1 / Spec2, GearScore, Average item level, Issues, Warnings,
Issues list, Data age. Spec1 / Spec2 remains the named talent tree with the most points
per specialization (for example "Holy / Discipline"); "-" means no points or an unavailable
second specialization. The name links to the local quick report when present, with a small
external-link icon for https://armory.warmane.com/character/NAME/REALM/summary beside it.
Non-OK rows show a plain name and the Armory icon. The Name, Class and Spec1 / Spec2 cells
do not wrap.

- Class styling follows the operating system light/dark setting. Light mode tints every cell
  in an OK row with the class tint; dark mode uses the class color for the name and class
  text without tinting the row. Unknown classes and non-OK rows have no class styling.

| Class | WotLK color | Light tint |
|---|---|---|
| Death Knight | `#C41F3B` | `#F2CED4` |
| Druid | `#FF7D0A` | `#FFE2C9` |
| Hunter | `#ABD473` | `#EDF6E0` |
| Mage | `#69CCF0` | `#DEF4FC` |
| Paladin | `#F58CBA` | `#FDE6F0` |
| Priest | `#FFFFFF` | `#EDEDED` |
| Rogue | `#FFF569` | `#FFFDDE` |
| Shaman | `#0070DE` | `#C7E0F8` |
| Warlock | `#9482C9` | `#E7E4F3` |
| Warrior | `#C79C6E` | `#F3E9DF` |

- Issues count remains the number of findings. The Issues list groups findings by kind,
  retaining slot order: missing enchants, Enchanter ring enchants, empty sockets (total and
  per-slot count), inactive meta gems, belt buckle, unspent talent points per spec, empty
  major glyphs per spec, then other issue text (with a slot prefix when available). Group
  labels are visually distinguished and all source text is HTML-escaped.
- An OK row with issues has a copy icon in the Issues count cell. It copies one chat line:
  missing enchant, gem, buckle and glyph totals, followed by unspent talents, inactive meta
  and other issues. Clipboard API use falls back to a hidden textarea for local `file://`
  pages; the icon briefly confirms a successful copy.
- Data age shows `YYYY-MM-DD HH:MM (from cache)` or `YYYY-MM-DD HH:MM (fresh)` without
  JavaScript, and relative age (`just now`, minutes, hours or days ago) with JavaScript.
  Cached relative ages include `(cache)`. The original text remains in the cell's title and
  the sortable value remains the snapshot epoch.

- Without JavaScript, rows are sorted by name (owner).
- In the summary only, Name, Class, Spec1 / Spec2, GearScore, Avg item level, Issues,
  Warnings and Data age are clickable sort columns. Each click sorts ascending; clicking the active
  column again sorts descending. The active heading shows ▲ or ▼, text compares
  case-insensitively, numeric values compare numerically, and empty values stay last.
- When JavaScript is enabled, non-OK rows stay at the bottom in name order regardless of
  the selected sort. Sortable headers use a pointer cursor. The page has one small inline
  script at the end of `<body>` and makes no network requests; character reports remain
  script-free.
- Non-zero issue counts are red, non-zero warning counts are orange, and counts of 4 or more are bold; zero counts stay plain. Use CSS classes, not inline styles.
- Rows with status "not found", "not run" or "failed" keep the name and armory icon and show the status and reason in the Issues list column (marked muted italic); other cells empty.
- Header line: realm, run time, number of characters, how many came from cache.
- If rate limits occurred, include the number of rate-limit waits and final request spacing.
- Professions are not shown (owner).

## Structure

- `roster.py`: input parsing (pure, tested), orchestration loop, summary row building from each character's quick export JSON (pure, tested), HTML rendering.
- The roster CLI accepts `--timing` or `WARMANE_TIMING=1` to report definition loading,
  cache/network fetch, snapshot build/save, JSON/Markdown/PvE HTML export, output copy,
  per-character and run totals, and summary rendering to stderr and the cache timing log.
- Reuse `checks.run_checks` and `gearscore.character_score` results already in the quick export; do not recompute differently.
- Tests: input cleanup cases, row building from a fixture export, sorting, not-found and not-run rows, HTML escaping. No network in tests.

## Not in scope

- Role detection (the active specialization is unknown to the armory).
- Mixed realms in one run.
- Full PvE reports for a roster.
