# Handoff for a new session

Project: Warmane Character Exporter (repo Aikonn/warmane-character-exporter, local folder on the HALL9K PC: C:\Users\pbumb\OneDrive\_projects\warmane-character-exporter). Read README.md and the latest Update sections of docs/development-status.md first. Older Update sections and docs/reviewer-instructions.md describe the earlier Perplexity-reviewer setup; this file wins where they differ.

## Roles

- Claude (claude.ai project "warmane-character-exporter") is the overseer: specification, architecture, review, docs. It may push docs, instruction files and code skeletons straight to main.
- GitHub Copilot in VS Code implements larger code changes from bounded task notes; Claude reviews the diff. Code changes go through branch dev and a pull request; the user merges.
- The point of the project is hands-on AI-assisted development; keep tasks small and reviewable.

## Conventions

- Ask the user only at the end, at most 400 characters, labeled "Action needed:" or "Decision needed:". Commands for the user in one fenced PowerShell block starting with "Clear-Host;". Short replies, no emojis.
- Tests: `$env:PYTHONPATH="src"; python -m unittest discover -s tests` (fixture-based, no network). 237 tests pass on Linux at 458809e.
- Claude's cloud sandbox cannot reach armory.warmane.com reliably; live runs happen on the PC. Claude can read the PC folder (including git-ignored .warmane-cache/exports) through the desktop app bridge.

## Access rules

- Warmane armory: plain HTTP, fixed browser-like User-Agent, requests 1 s apart, one character at a time, daily budget 500 (`python -m warmane_exporter.budget`). Stop on the first error. Never provoke a rate limit. No User-Agent rotation or evasion.
- Respect robots.txt and terms of every third-party site before any request. wago.tools disallows automated access. Cavernoftime and EvoWoW blocked automated access; their terms were never reviewed.

## State (2026-11-15)

- End to end for any character: quick report (3 requests: raid readiness, gear, talents, glyphs, professions) and PvE report (about 28 requests: plus WotLK raid boss kills, raid achievements, emblems, reputation, mounts). Launcher Start-Report.cmd bootstraps a portable Python.
- Definitions without the game client: client-export.json (texts) and AzerothCore items.db (item facts, sockets, set ids). GearScore, socket/meta/set bonus activation, stat totals, raid readiness checks are in.
- Icecrown Citadel and Ruby Sanctum (Halion 10/25 normal/heroic) appear in the boss-kill tables and in the Fall of the Lich King / Lich King raid achievements. The armory tracks only Halion for Ruby Sanctum, not the mini-bosses.
- Known gaps: active spec, conditional spell text, armory heroic kill counts sometimes copy normal counts (marked with *).

## Backlog (candidates, not approved)

1. End-game focus: ICC/RS summary at the top of the PvE report (bosses killed per mode, Light of Dawn / Bane of the Fallen King / The Twilight Destroyer style meta progress), ICC reputation (Ashen Verdict) and ICC-specific readiness hints.
2. Client-independent enchant and gem texts beyond client-export.json (needs a source with clear terms).
3. Direct URL command polish (warmane-export URL).
