# Handoff for a new session

Project: Warmane Character Exporter (repo Aikonn/warmane-character-exporter, local folder E:\Skydrive\_projects\warmane-character-exporter). Read README.md, docs/reviewer-instructions.md and the latest Update sections of docs/development-status.md first.

## Role and autonomy

- The assistant drives the project. Do not ask for approval of each step. Work on the dev branch, open pull requests, never push main. The user merges.
- Ask the user only at the very end, in at most 400 characters, labeled "Action needed:" (the user must do something) or "Decision needed:" (a real choice).
- Commands for the user go in one fenced code block starting with "Clear-Host;". Keep replies short; no emojis, no exclamation points.
- Offloading code generation to GitHub Copilot is not possible from the cloud sandbox.

## Workflow

- On the PC, commit on branch dev using the identity of the last commit (git -c user.name -c user.email; never change git config). Run tests with the embeddable Python in .tools\python312 (see reviewer-instructions.md).
- Transfer: git format-patch -1 --stdout on the PC, apply with git am in a cloud clone of the repo, push dev (never force push), open a PR with gh, then reset the PC to origin/dev.
- Check that the commit exists before resetting the PC. A reset before committing once lost work.

## Access rules

- Warmane armory: plain HTTP, fixed browser-like User-Agent, requests 1 s apart (owner decision, single character), daily budget 500 (python -m warmane_exporter.budget). Stop on the first error. Never provoke a rate limit. No User-Agent rotation or evasion.
- Respect robots.txt and terms of every third-party site before any request. wago.tools disallows automated access in robots.txt. Cavernoftime and EvoWoW blocked automated access earlier and their terms were never reviewed.

## State

Export works end to end for Aikka and Bezduse on Onyxia and Icecrown (python -m warmane_exporter.run NAME REALM). Spell, enchant and gem texts currently come from the local game client files (MPQ/DBC). Known gaps: active spec, conditional spell text. Item facts and socket structure now come from the AzerothCore item database (python -m warmane_exporter.acore_cli fetch, then verify) through definitions.py; the game client is optional and still the only source of enchant, gem, spell, talent and glyph texts.

## Backlog

1. Client-independent texts for enchants and gems. Open finding: the armory item tooltips load from wotlk.cavernoftime.com (rel="item=ID&ench=..&gems=.."), not from a Warmane endpoint, so the earlier plan of Warmane tooltips is unverified; Cavernoftime terms were never reviewed and it blocked automated access before. Options: review its terms, or find a SpellItemEnchantment name list with a clear licence. Then the client-versus-online comparison.
2. PvE report profile with dungeon and raid progression grouping.
3. Direct URL command (warmane-export URL).
4. Comparison of exports over time.
