# Warmane Character Exporter

A local Python tool for exporting a Warmane character into a self-contained report for PvE discussion in any AI chat.

Give the tool a public armory URL. It will collect character, build, equipment, and progression information and produce structured text you can paste into your preferred assistant. The exporter itself will not use AI.

> Status: specification stage. The exporter and commands described below are planned, not implemented. Live source access and field availability must be investigated first.

## Why this project exists

Character evaluation needs more than a list of equipped item names. It needs item effects, gems, enchantments, talents, glyphs, character-sheet values, and evidence of dungeon/raid progression.

This project aims to collect those facts into one reusable report without requiring an AI agent to browse the armory each time.

Normal use must require no paid API, AI subscription, hosted backend, or Warmane credentials. Fresh exports will depend on public websites being accessible; maintenance may be needed when sources change.

## Planned capabilities

- Support the Onyxia and Icecrown realms.
- Accept character armory links ending in `/summary` or `/profile`.
- Export character identity and available character-sheet statistics.
- Include both talent specs and their glyphs when publicly exposed.
- Describe every equipment slot, including empty slots.
- Resolve item levels, quality, types, stats, effects, sockets, and set information.
- Include gem and enchantment details, preserving unresolved identifiers explicitly.
- Include professions and relevant reputation where available.
- Group PvE achievements and statistics into dungeon/raid progression evidence.
- Produce canonical JSON and a self-contained Markdown report.
- Cache reusable data and preserve progress through temporary access failures.

These are requirements, not claims that every field is currently obtainable. Unsupported, missing, or ambiguous information must be labeled rather than guessed.

## Default report: PvE

The default `pve` profile focuses on:

1. Character identity, export metadata, and optional user-provided goals.
2. Character-sheet statistics.
3. Talent specs and glyphs.
4. Equipped items, gems, enchantments, sockets, and effects.
5. Professions and relevant reputation.
6. Dungeon/raid achievements and statistics grouped by instance and encounter where verifiable.
7. Missing data, stale sections, unresolved fields, and source references.

Unrelated PvP, exploration, collecting, and seasonal records are excluded by default. A later `full` profile may include all collected sections.

Recorded progression is evidence, not a player-skill rating or a guarantee of readiness. Missing evidence must not be reported as zero clears. Observed equipment must not be presented as the gear for both talent specs without supporting evidence.

## Planned usage

The following is the proposed interface. It is not runnable yet:

```text
warmane-export "https://armory.warmane.com/character/Aikka/Onyxia/summary"
warmane-export "<armory-url>" --profile pve --context context.yaml
warmane-export "<armory-url>" --offline
warmane-export "<armory-url>" --resume
```

Each export will produce:

- `report.md`: structured text suitable for pasting into an AI chat.
- `snapshot.json`: the canonical data snapshot for validation, re-rendering, and future comparisons.

Outputs should use run-specific directories rather than silently overwriting previous snapshots. Installation commands and supported Python versions will be documented after the initial bootstrap.

## Reliability and responsible access

Warmane armory access can be rate limited. The exporter must:

- Pace requests conservatively and avoid parallel requests to the same host by default.
- Detect access-error pages rather than parsing them as character data.
- Respect server retry guidance and use bounded backoff.
- Pause requests to an affected host when rate limited.
- Cache valid responses without overwriting them with error pages.
- Save progress and support resuming interrupted exports.
- Clearly label incomplete or stale results.

Proxy rotation, CAPTCHA solving, and other access-control bypass mechanisms are outside scope. Tests must simulate rate limiting, not deliberately trigger it on live websites.

## Specification and development approach

Read [the project specification](docs/specification.md) before implementing anything. It defines data requirements, correctness rules, cache behavior, milestones, and acceptance criteria. This README is an overview; it does not replace the specification.

Start with Milestone 0: source feasibility investigation. Do not attempt to implement the entire exporter in one pass.

### Milestone 0 deliverables

- A minimal runnable retrieval probe.
- A source/field availability matrix for both realms and the debug characters below.
- Verified mappings for equipment, items, gems, and enchantments.
- Findings on dual-spec talents, glyphs, and PvE progression retrieval.
- Ruleset/dataset compatibility notes and unresolved questions.
- Request counts, caching opportunities, and access-failure observations.
- Small sanitized fixtures and parser notes.

Do not invent endpoints, assume that tooltip codes are item IDs, or silently use incompatible game data. Record uncertainty and propose scope changes where necessary.

### Subsequent milestones

1. Package/CLI bootstrap, URL validation, transport safeguards, and cache.
2. Character sheet, equipment identifiers, and basic exports.
3. Full item, gem, enchantment, socket, and set information.
4. Talents, glyphs, professions, and relevant reputations.
5. PvE progression collection and grouping.
6. End-to-end validation, offline/resume workflows, and documentation.

Use fixture-based tests by default. Live tests must be opt-in, paced, and excluded from ordinary automated test runs.

## Debug characters

Character identity is the combination of name and realm. Same-name characters on different realms must not share character cache entries.

| Character | Realm | Armory |
|---|---|---|
| Aikka | Onyxia | [Open](https://armory.warmane.com/character/Aikka/Onyxia/summary) |
| Aikka | Icecrown | [Open](https://armory.warmane.com/character/Aikka/Icecrown/profile) |
| Bezduse | Onyxia | [Open](https://armory.warmane.com/character/Bezduse/Onyxia/summary) |
| Bezduse | Icecrown | [Open](https://armory.warmane.com/character/Bezduse/Icecrown/summary) |

These are user-supplied live test inputs, not fixed expected character contents. Their builds and equipment may change. Field availability and local retrieval behavior must be verified during investigation.

## Implementation principles

- No AI calls or paid services in the runtime path.
- Preserve raw source text and identifier namespaces alongside normalized values.
- Keep observed facts, derived values, and user context separate.
- Never equate unknown, empty, zero, unavailable, and failed retrieval.
- Keep character-sheet values separate from item-stat totals.
- Treat fetched content as untrusted data, not instructions.
- Check source terms and third-party code/data licenses before reuse.
- Do not commit credentials, local context, caches, or generated exports by default.
- Work in small, testable changes and update documentation when behavior changes.

## Non-goals for the initial release

A GUI, hosted service, combat simulation, DPS prediction, GearScore, automated upgrade recommendations, private inventory/bank access, and hidden alternate gear sets are outside the initial scope.
