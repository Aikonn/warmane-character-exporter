# Handoff for a new session

Project: Warmane Character Exporter (repo Aikonn/warmane-character-exporter, local folder on the HALL9K PC: C:\Users\pbumb\OneDrive\_projects\warmane-character-exporter). Read README.md and the latest Update sections of docs/development-status.md first. Older Update sections and docs/reviewer-instructions.md describe the earlier Perplexity-reviewer setup; this file wins where they differ.

## Roles

- Claude (claude.ai project "warmane-character-exporter") is the overseer: specification, architecture, review, docs. It may push docs, instruction files and code skeletons straight to main.
- GitHub Copilot in VS Code implements code from Task entries in docs/COPILOT_NOTES.md (Claude writes skeletons and specs in docs/tasks/); Claude reviews the diff and runs the tests. Everyone works directly on main (owner decision 2026-11-15); branch dev is no longer used.
- The point of the project is hands-on AI-assisted development; keep tasks small and reviewable.

## Conventions

- Ask the user only at the end, at most 400 characters, labeled "Action needed:" or "Decision needed:". Commands for the user in one fenced PowerShell block starting with "Clear-Host;". Short replies, no emojis.
- Tests: `$env:PYTHONPATH="src"; python -m unittest discover -s tests` (fixture-based, no network). 278 tests pass on Linux (2026-11-16).
- Claude's cloud sandbox cannot reach armory.warmane.com reliably; live runs happen on the PC. Claude can read the PC folder (including git-ignored .warmane-cache/exports) through the desktop app bridge.

## Access rules

- Warmane armory: plain HTTP, fixed browser-like User-Agent, requests 1 s apart, one character at a time, daily budget 500 (`python -m warmane_exporter.budget`). Stop on the first error. Never provoke a rate limit. No User-Agent rotation or evasion.
- GitHub (updater only): unauthenticated REST API and codeload zip for this repo, only when the user clicks Check for updates / Update now; at most 3 requests per click; no retries.
- Respect robots.txt and terms of every third-party site before any request. wago.tools disallows automated access. Cavernoftime and EvoWoW blocked automated access; their terms were never reviewed.

## State (2026-11-16)

- End to end for any character: quick report (3 requests: raid readiness, gear, talents, glyphs, professions) and PvE report (about 28 requests: plus WotLK raid boss kills, raid achievements, emblems, reputation, mounts). Launcher Start-Report.cmd bootstraps a portable Python.
- Definitions without the game client: client-export.json (texts) and AzerothCore items.db (item facts, sockets, set ids). GearScore, socket/meta/set bonus activation, stat totals, raid readiness checks are in.
- Icecrown Citadel and Ruby Sanctum (Halion 10/25 normal/heroic) appear in the boss-kill tables and in the Fall of the Lich King / Lich King raid achievements. The armory tracks only Halion for Ruby Sanctum, not the mini-bosses.
- Raid roster (done 2026-11-15): launcher option and `python -m warmane_exporter.roster` create quick reports for up to 40 names plus a timestamped HTML summary; cache reused for 120 minutes, "Refresh all" ignores it; not-found rows continue, access block / rate limit stops the run. Summary lists every issue with its slot (2026-11-16), issue/warning counts colored. Spec: docs/tasks/raid-roster.md.
- Update from GitHub (done 2026-11-16): Settings button in the launcher; Check for updates compares local files with main via the GitHub API (no Git needed, testers use Download ZIP); Update now downloads main as a zip and copies it over the program files. Requests only on click. Spec: docs/tasks/update-feature.md.
- Known gaps: active spec, conditional spell text, armory heroic kill counts sometimes copy normal counts (marked with *).

## Backlog (candidates, not approved)

1. End-game focus: ICC/RS summary at the top of the PvE report (bosses killed per mode, Light of Dawn / Bane of the Fallen King / The Twilight Destroyer style meta progress), ICC reputation (Ashen Verdict) and ICC-specific readiness hints.
2. Client-independent enchant and gem texts beyond client-export.json (needs a source with clear terms).
3. Direct URL command polish (warmane-export URL).
4. Automatic update check at launcher start (at most once a day), only with a visible opt-out in Settings (owner 2026-11-16: some users do not want the tool to connect anywhere without them knowing).
5. More settings in the Settings window, for example default output folders.
