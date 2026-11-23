# Warmane Character Exporter

A local Python tool that exports a Warmane character (Onyxia, Icecrown) into a self-contained report for PvE discussion in any AI chat. The exporter itself uses no AI, no paid service and no Warmane credentials.

## Download and run (Windows)

1. On the [repository page](https://github.com/Aikonn/warmane-character-exporter) choose Code, then Download ZIP, and extract it anywhere (for example the Desktop).
2. Double-click `Start-Report.cmd`. On the first run, if Python 3.12 or newer is missing, the launcher offers to download a portable copy (about 11 MB, from python.org) into the same folder. Nothing is installed on the system, and no game client or configuration is needed.
3. Paste an armory link (for example `https://armory.warmane.com/character/Aikka/Onyxia/summary`), pick Quick report (gear, talents, glyphs, professions and raid readiness; only 3 requests) or Full PvE report, choose where to save, and the report opens in the browser. Or choose Raid roster to paste names separated by spaces, tabs or commas (one per line also works) and create quick reports plus a system-themed summary with grouped issues, per-character copy messages and relative data ages for Onyxia or Icecrown.

If Windows SmartScreen warns about the script, choose More info, then Run anyway. A run takes a few minutes and uses about 28 requests of the daily budget.

## Status

Working end to end. For each character the tool collects the armory summary, equipment, talents and glyphs, professions, reputation, mounts and companions, all achievements and all statistics, then writes one JSON and one Markdown export. Spell, talent, glyph, enchant and gem texts come from the bundled `library/definitions/client-export.json`; item facts and socket structure from the bundled AzerothCore item database. The game client is optional. Unresolved fields are labeled, never guessed.

Known gaps: active spec, and spell descriptions with conditional text.

## Setup

```text
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e .
```

No third-party packages are needed. The 3.3.5a game client is optional; it is only needed to regenerate `client-export.json` (`python -m warmane_exporter.definition_export`, client path from `warmane-character-exporter.config`, see the template).

## Usage

```text
$env:PYTHONPATH="src"
python -m warmane_exporter.run Aikka Onyxia
python -m warmane_exporter.run --all
python -m warmane_exporter.run Aikka Onyxia --offline
python -m warmane_exporter.budget
python -m warmane_exporter.roster --realm Onyxia --names Aikka,Bezduse --output-dir "$HOME\Downloads"
```

- `run` executes snapshot, reputation, mounts, achievements, statistics and export, stops at the first failing step, and resumes when started again.
- `--offline` rebuilds from cached data only; `--refresh` ignores the 24 h cache.
- `roster` creates one quick report per name and a timestamped HTML summary; cached character data is reused for up to 120 minutes by default.
- Live requests start 1 s apart; rate limits trigger the existing cooldown/retry and raise spacing to 3 s after the first event, then 5 s after three further events in that run. Long waits are shown in the progress window and rate-limit events are logged.
- The progress window's Stop button stops a roster cleanly and opens its partial summary; for a single-character run it asks for confirmation and stops the process. A roster summary records rate-limit waits and final spacing when applicable.
- For roster performance measurements, pass `--timing` or set `WARMANE_TIMING=1`; step timings go to stderr and `.warmane-cache/timing-YYYYMMDD-HHMM.log`.
- Output: `.warmane-cache/exports/<name>-<realm>.json` and `.md`.
- A PvE export costs about 28 requests per character, a quick report 3, `--full` about 90.

## Updating

Open **Settings > Check for updates**, then choose **Update now** when an update is available. The updater is available in Download ZIP copies; it preserves reports, cache, settings and portable Python. To update manually, download the ZIP again and extract it over the existing folder. In a Git clone, use `git pull`.

## Responsible access

- Plain HTTP with a fixed browser-like User-Agent; no rotation, no evasion.
- Requests are sequential with adaptive 1/3/5 s spacing, within a daily budget (default 500, `python -m warmane_exporter.budget --set N`).
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

Out of scope: hosted service, DPS prediction, automated upgrade advice, private inventory access. GearScore (GearScoreLite formula) and raid readiness checks are informational only.

## Quick start (Windows)

Double-click `Start-Report.cmd`. It offers single-character reports and a raid-roster option, runs the export and opens the HTML report or roster summary in the default browser. Command line equivalent for one character: `python -m warmane_exporter.run https://armory.warmane.com/character/Aikka/Onyxia/summary --html-output report.html`.

## License

GNU Affero General Public License v3.0 (see LICENSE). The bundled item database in `library/acore/items.db` is derived from the AzerothCore database (AGPL-3.0). `library/definitions/client-export.json` contains spell, enchant and gem texts extracted from the World of Warcraft 3.3.5a client, which remain Blizzard material.
