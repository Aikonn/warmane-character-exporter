# Warmane Character Exporter

A local Python tool that exports a Warmane character (Onyxia, Icecrown) into a self-contained report for PvE discussion in any AI chat. The exporter itself uses no AI, no paid service and no Warmane credentials.

## Download and run (Windows)

1. On the [repository page](https://github.com/Aikonn/warmane-character-exporter) choose Code, then Download ZIP, and extract it anywhere (for example the Desktop).
2. Double-click `Start-Report.cmd`. On the first run, if Python 3.12 or newer is missing, the launcher offers to download a portable copy (about 11 MB, from python.org) into the same folder. Nothing is installed on the system, and no game client or configuration is needed.
3. Paste an armory link (for example `https://armory.warmane.com/character/Aikka/Onyxia/summary`), choose where to save, and the report opens in the browser.

If Windows SmartScreen warns about the script, choose More info, then Run anyway. A run takes a few minutes and uses about 28 requests of the daily budget.

## Status

Working end to end. For each character the tool collects the armory summary, equipment, talents and glyphs, professions, reputation, mounts and companions, all achievements and all statistics, then writes one JSON and one Markdown export. Spell, enchant and gem texts come from the game client files (offline). Unresolved fields are labeled, never guessed.

Known gaps: socket structure, active spec, and spell descriptions with conditional text.

## Setup

```text
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e .
```

Copy the client path settings into the config file described in docs/reviewer-instructions.md (the World of Warcraft 3.3.5a folder is required for offline enrichment). No third-party packages are needed.

## Usage

```text
$env:PYTHONPATH="src"
python -m warmane_exporter.run Aikka Onyxia
python -m warmane_exporter.run --all
python -m warmane_exporter.run Aikka Onyxia --offline
python -m warmane_exporter.budget
```

- `run` executes snapshot, reputation, mounts, achievements, statistics and export, stops at the first failing step, and resumes when started again.
- `--offline` rebuilds from cached data only; `--refresh` ignores the 24 h cache.
- Output: `.warmane-cache/exports/<name>-<realm>.json` and `.md`.
- A full export costs about 90 requests per character.

## Responsible access

- Plain HTTP with a fixed browser-like User-Agent; no rotation, no evasion.
- Requests are sequential, 1 s apart, within a daily budget (default 500, `python -m warmane_exporter.budget --set N`).
- Error pages are detected and never cached as data; the tool stops on the first error.
- Static reference pages go to the local `library/` folder and are reused.

## Tests

```text
$env:PYTHONPATH="src"
python -m unittest discover -s tests
```

Tests use fixtures and make no network requests.

## Documents

- docs/specification.md: requirements and milestones
- docs/data-sources.md: endpoints, fields, terms
- docs/development-status.md: dated progress log
- docs/milestone-0-review.md: feasibility review
- docs/reviewer-instructions.md: workflow and conventions

## Debug characters

| Character | Realm |
|---|---|
| Aikka | Onyxia |
| Aikka | Icecrown |
| Bezduse | Onyxia |
| Bezduse | Icecrown |

## Principles

Preserve raw source text and identifier namespaces. Keep observed facts, derived values and user context separate. Never equate unknown, empty, zero, unavailable and failed. Treat fetched content as untrusted data. Do not commit caches, exports, captures or config.

Out of scope: GUI, hosted service, DPS prediction, GearScore, automated upgrade advice, private inventory access.

## Quick start (Windows)

Double-click `Start-Report.cmd`. It asks for an armory link, asks where to save the HTML report, runs the export and opens the report in the default browser. Command line equivalent: `python -m warmane_exporter.run https://armory.warmane.com/character/Aikka/Onyxia/summary --html-output report.html`.
