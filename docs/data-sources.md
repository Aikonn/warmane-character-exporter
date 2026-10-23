# Data Sources and Feasibility Investigation

Status: investigation template — no source behavior verified here.

Current Milestone 0 bootstrap note: local offline probe scaffolding and synthetic fixtures may be added before any live request. These local checks do not constitute source verification evidence.

This document tracks where required data comes from, how identifiers are resolved, and what remains unavailable or uncertain. Read [specification.md](specification.md) before implementing collectors.

## 1. Investigation objective

Complete Milestone 0 before building the full exporter:

- Establish which public sources expose the required fields on Onyxia and Icecrown.
- Verify compatibility of item, talent, spell, gem, and enchantment data.
- Build a minimal runnable retrieval probe and a small set of sanitized fixtures.
- Measure request counts and identify cache opportunities.
- Document limitations rather than inventing missing data or endpoints.

The four character URLs below are user-supplied inputs. Previous assistant web-fetch attempts failed; that does not establish why access failed or whether local Python retrieval works. A user-provided screenshot separately showed Cloudflare Error 1015 on an armory search page. No exact rate-limit thresholds are known.

## 2. Debug character matrix

| Test ID | Character | Realm | Input URL | Local retrieval status |
|---|---|---|---|---|
| onyxia-aikka | Aikka | Onyxia | https://armory.warmane.com/character/Aikka/Onyxia/summary | Direct probe blocked (`403 error code: 1010`); offline rendered-DOM capture inspected (partial findings) |
| icecrown-aikka | Aikka | Icecrown | https://armory.warmane.com/character/Aikka/Icecrown/profile | Not tested |
| onyxia-bezduse | Bezduse | Onyxia | https://armory.warmane.com/character/Bezduse/Onyxia/summary | Not tested |
| icecrown-bezduse | Bezduse | Icecrown | https://armory.warmane.com/character/Bezduse/Icecrown/summary | Not tested |

Character identity is `(realm, name)`. Never merge same-name characters across realms. Character contents can change; these are not fixed expected snapshots. Do not infer class, spec, or equipment from a name.

## 3. Evidence and status conventions

Use these investigation statuses:

- `not_investigated`: no direct verification yet.
- `verified`: directly observed and recorded with evidence.
- `partial`: some required data verified, remaining gaps identified.
- `not_exposed`: investigation supports absence from the inspected source; state scope and evidence.
- `blocked`: access failed; field availability remains unknown.
- `incompatible`: source data conflicts with the selected ruleset.

Do not turn a failed request into `not_exposed`. These are investigation labels, separate from runtime section statuses defined in the specification.

For every material finding record:

- UTC observation time, source URL, realm and character where applicable.
- Retrieval method and relevant response status/content type.
- Fixture path or sanitized evidence excerpt.
- Parser/extraction location and identifier namespace.
- Compatibility evidence, limitations, and remaining questions.

Do not record authentication tokens, cookies, personal IP addresses, or unnecessary browser/network metadata.

## 4. Source register

Register each source before relying on it. Public accessibility is not permission to redistribute its data or copy its implementation.

| Source ID | Purpose | URL or discovery basis | Verification | Compatibility / licensing |
|---|---|---|---|---|
| warmane-armory | Character observations and links to related sections | User-supplied character URLs above | Not investigated locally | Access policy and field coverage to check |
| game-data-primary | Item, gem, enchantment, talent, spell definitions | To select from verified candidates | Not selected | Must verify ruleset, identifier mapping, terms and reuse limits |
| game-data-fallback | Optional fallback for unresolved definitions | Only if needed | Not selected | Must not silently mix incompatible data |

Add APIs, tooltip services, or other sources only after discovering and verifying them. Do not assume an official or community API exposes all required fields.

### Source detail template

```text
Source ID:
Purpose:
Base URL / observed request URL:
Discovery evidence:
Public access method:
Terms / robots / usage-policy findings:
Code or dataset license, if relevant:
Ruleset / version / locale:
Identifier namespaces:
Required request parameters:
Response format:
Paging / category traversal:
Rate-limit behavior observed incidentally:
Cache policy:
Fallback behavior:
Verification time and fixtures:
Known limitations:
```

## 5. Field-availability matrix

Update realm coverage separately. Where characters differ within one realm, name those differences in the evidence column. `TBD` means uninvestigated, not unavailable.

| Data group | Required investigation | Onyxia | Icecrown | Source / evidence / limitations |
|---|---|---|---|---|
| Identity | Name, realm, class, race, level, faction, guild, title | Partial | TBD | Rendered-DOM capture contains name/guild/level-race-class-realm text; faction/title not observed in inspected capture |
| Character sheet | Attributes, resources, combat/defensive values, labels and units | Partial | TBD | Rendered-DOM capture contains Melee/Ranged/Spell/Defense/Resistances sections with displayed values/units |
| Equipment | All ruleset slots, empties, equipped item identifiers | Partial | TBD | Rendered-DOM capture contains item references and explicit Shirt/Tabard empty slots; many slot names are layout-position only |
| Item definitions | Level, quality, type, requirements, stats, armor/weapon fields | TBD | TBD | TBD |
| Item effects | Equip/use/proc text, restrictions, cooldowns | TBD | TBD | TBD |
| Sockets | Colors, added sockets, socket-bonus text | TBD | TBD | TBD |
| Gems | Raw codes, verified IDs, names, colors, quality, effects | Partial | TBD | Raw gem codes present in `rel` payloads and tooltip-script URLs; no definition verification from this offline capture alone |
| Meta gems | Requirement text; source of activation state if any | TBD | TBD | TBD |
| Enchantments | Raw codes, namespaces, resolved effect text | Partial | TBD | Raw enchantment codes present in `rel` payloads and tooltip-script URLs; no definition verification from this offline capture alone |
| Sets | Membership, thresholds, bonus descriptions | TBD | TBD | TBD |
| Primary spec | Tree totals, selected talents/ranks, effect text | Partial | TBD | Rendered-DOM capture contains specialization summary totals only (for one spec entry), not talent-by-talent selections |
| Secondary spec | Presence, talents/ranks, source order/identifier | Partial | TBD | Rendered-DOM capture shows two specialization summary entries; detail pages not captured |
| Active spec | Explicit active-state evidence | Not exposed in capture | TBD | No explicit active-spec marker observed in inspected rendered-DOM capture |
| Glyphs | Identifiers, effects, categories, association with each spec | Not exposed in capture | TBD | No glyph records found in this capture; this is not evidence that the character has no glyphs |
| Professions | Names and skill levels | TBD | TBD | TBD |
| Reputation | Standing/progress and verified PvE relevance | TBD | TBD | TBD |
| Achievements | IDs, categories, dates, points, completion and criteria | Partial | TBD | Recent-activity achievements with IDs/names/time text are present; not a full achievements-page traversal |
| Statistics | IDs, category paths, values, units, encounter associations | Not captured | TBD | Statistics page link present, but statistics-page content not captured |
| PvE selection | Category enumeration, identifier mappings and coverage | TBD | TBD | TBD |

## 6. Investigation procedure

### A. Establish safe retrieval

1. Implement or reuse the specification's pacing, timeout, and bounded-retry policy before traversing categories.
2. Retrieve one supplied character page and inspect its response before attempting further requests.
3. Distinguish actual character content from access-error pages, redirects, and unexpected layouts.
4. Save a sanitized successful fixture and relevant response metadata.
5. If blocked, preserve progress and pause. Do not repeatedly reload or intentionally provoke a block.

A blocking response is itself a useful finding, but not proof that all other methods or fields are unavailable.

### B. Discover character data

1. Inspect public HTML, embedded data, and links.
2. If necessary, inspect public requests made by the normal browser page.
3. Record exact observed request parameters and field meanings.
4. Validate `/summary` and `/profile` input normalization without assuming both render identical HTML.
5. Repeat targeted checks across the remaining characters and both realms, reusing cached definitions.

Use ordinary HTTP retrieval if sufficient. Browser automation requires a documented reason and must not be used to bypass access controls. Do not commit browser profiles or exported session credentials.

### C. Resolve one complete equipment chain

For a representative equipped item, trace:

```text
character slot
  -> raw equipped-item reference
  -> verified base item definition
  -> raw gem references -> verified gem definitions
  -> raw enchantment reference -> verified enchantment definition
  -> sockets, socket-bonus text, and set descriptions where applicable
```

Record identifier transformations and evidence. If no debug character supplies a needed example, mark the test gap; use a labeled synthetic fixture or an independently verified public example rather than pretending the field was tested.

### D. Verify specs and glyphs

Determine how specs are enumerated, whether active state is explicit, how selected talent ranks map to effect text, and how glyphs associate with each spec. Do not assume the second spec is absent because only one was initially displayed. Do not associate observed gear with both specs without evidence.

### E. Trace progression traversal

Determine how achievement/statistic categories, subcategories, criteria, and pagination are exposed. Count requests before planning broad traversal. Verify instance, encounter, difficulty, and group-size associations where possible. Preserve raw records before grouping them.

### F. Publish findings

Update this document, the fixture manifest, and the open-question list. Identify a minimal viable collection path and distinguish implementation gaps from genuine source limitations. Propose material scope changes for review rather than silently changing the specification.

## 7. Ruleset and compatibility decisions

Realm names alone are not sufficient proof that every external definition is compatible. Never use current retail data as an automatic fallback.

| Realm / dataset profile | Selected dataset and version | Compatibility evidence | Open issues | Decision status |
|---|---|---|---|---|
| Onyxia | TBD | TBD | TBD | Pending |
| Icecrown | TBD | TBD | TBD | Pending |

For a proposed dataset, compare representative item stats/effects, talent trees/ranks, glyph effects, gem/enchantment mappings, and equipment-slot definitions. Record conflicts explicitly. Cache keys must distinguish ruleset/dataset versions.

## 8. Identifier mapping register

| Raw source field | Actual namespace | Target definition | Mapping evidence | Status |
|---|---|---|---|---|
| Equipped item reference | TBD | Item definition | TBD | Not investigated |
| Gem tooltip parameter | TBD; do not assume item ID | Gem definition | TBD | Not investigated |
| Enchantment parameter | TBD; do not assume spell/item ID | Enchantment effect | TBD | Not investigated |
| Talent reference | TBD | Talent and selected-rank effect | TBD | Not investigated |
| Glyph reference | TBD | Glyph and effect | TBD | Not investigated |
| Achievement/statistic reference | TBD | Progression source record | TBD | Not investigated |

Retain original codes even after resolution. An unresolved identifier is valid partial data, not a reason to invent a name or drop the equipment slot.

## 9. PvE filtering and grouping

Maintain versioned selection rules rather than relying on name keywords alone.

For each selected category/identifier record:

- Source and ruleset.
- Original category path or identifier.
- Inclusion reason and mapping version.
- Verified instance/encounter/difficulty/group-size associations.
- Coverage limitations and unclassified records.

Store achievements and statistics separately in JSON even if they appear together in a report. Do not sum overlapping achievements and counters as independent clears. Missing dates, absent counters, and failed category requests must not become zero progress.

Reputation relevance requires its own verified mapping to PvE equipment, enchants, or access. Do not assume every faction is relevant or invent requirements.

## 10. Request budget and cache findings

Measure request counts without deliberately load-testing any source. Counts are observations for particular fixtures/runs, not promises about future behavior.

| Operation | Host / source | Requests observed | Reusable cache content | Uncertainty |
|---|---|---|---|---|
| Character identity and sheet | TBD | TBD | Character observation | TBD |
| Equipment references | TBD | TBD | Character observation | TBD |
| Specs and glyphs | TBD | TBD | Observation plus definitions | TBD |
| Item/gem/enchantment definitions | TBD | TBD | Ruleset-specific definitions | TBD |
| Achievement traversal | TBD | TBD | Observation and category definitions | TBD |
| Statistic traversal | TBD | TBD | Observation and category definitions | TBD |
| Relevant reputation | TBD | TBD | Observation plus relevance mapping | TBD |

Record cache hit/miss counts, observation interval, and total network requests for each probe run. Follow the configurable defaults in the specification until there is evidence to propose a change. Do not represent those defaults as Warmane's published limits.

## 11. Error handling evidence

Cover these cases with saved sanitized or synthetic fixtures:

- Successful character and definition responses.
- HTTP rate-limit responses and Cloudflare 1015-style HTML.
- `Retry-After` delay and HTTP-date forms.
- Unexpected content type or page structure.
- Missing character or definition.
- Transient transport/server failure.
- Unresolved identifiers and partial category traversal.

A Cloudflare page error code must not be assumed to be the HTTP status code. Error-page detection must work before parsing or updating valid cache entries.

Label synthetic fixtures as synthetic. Do not claim they demonstrate live site behavior. Tests must not intentionally generate a live block.

## 12. Fixture manifest

Use small fixtures under `tests/fixtures/` and document them:

| Fixture | Source / synthetic | Captured UTC | Realm / ruleset | Purpose | Sanitization / reuse notes |
|---|---|---|---|---|---|
| tests/fixtures/synthetic/cloudflare-1010-access-denied-synthetic.json | Synthetic | N/A | Synthetic | Offline classification tests for Cloudflare 1010-style access denial | Minimal fields only (`status`, `Content-Type`, body text) |
| tests/fixtures/synthetic/summary-page-dom-synthetic.html | Synthetic | N/A | Synthetic | Offline parser tests for identity, stats, equipment rel namespaces, specializations, navigation links, and recent activity | Synthetic content modeled on observed structure; safe to commit |
| tests/fixtures/synthetic/talents-page-dom-synthetic.html | Synthetic | N/A | Synthetic | Offline parser tests for spec tabs, talent trees, selected talents, malformed ranks, glyph blocks, and tree-total validation | Minimal two-spec structure with glyphs and mixed selected/unselected talents; safe to commit |
| local-captures/aikka-onyxia-summary-dom.html | Manual local capture (ignored) | User-provided local file | Onyxia rendered DOM | Offline structural investigation only | Raw capture remains git-ignored pending reuse/licensing decision |
| local-captures/aikka-onyxia-talents-spec1-dom.html | Manual local capture (ignored) | User-provided local file | Onyxia rendered DOM | Offline talents structure investigation; substantively identical to spec2 | Raw capture remains git-ignored; offline parser verified against both without live requests |
| local-captures/aikka-onyxia-talents-spec2-dom.html | Manual local capture (ignored) | User-provided local file | Onyxia rendered DOM | Offline talents structure investigation; substantively identical to spec1 | Raw capture remains git-ignored; offline parser verified against both without live requests |

Do not commit full browser sessions, cookies, tokens, IP addresses, or unnecessarily large captures. Check whether source terms allow committing captured content; if not, use permitted minimal excerpts or labeled synthetic equivalents. Fixtures must preserve the structures necessary for their tests.

## 13. Findings log

Append dated, evidence-backed findings here. Keep guesses in open questions instead.

```text
Finding ID:
Observed UTC:
Character / realm / source:
Question:
Method and request count:
Result:
Evidence / fixture:
Limitations:
Implementation consequence:
```

```text
Finding ID: armory-onyxia-aikka-2026-10-23-access-block-1010
Observed UTC: 2026-10-23 20:51:24 GMT (from response Date header)
Character / realm / source: Aikka / Onyxia / warmane-armory
Question: Is initial character-page retrieval available for source inspection?
Method and request count: Single direct GET probe, 1 attempt, no retry, no redirect following.
Result: Access blocked before character content retrieval. HTTP 403, Content-Type text/plain; charset=UTF-8, body `error code: 1010`.
Evidence / fixture: Live probe result recorded in findings log (response summary retained in docs); synthetic test fixture at tests/fixtures/synthetic/cloudflare-1010-access-denied-synthetic.json
Limitations: No character fields could be inspected; this is an access finding, not a character-data absence finding.
Implementation consequence: Classify this response as `client_signature_blocked` (non-retryable for current run path) and keep character fields as unverified.
```

```text
Finding ID: armory-onyxia-aikka-rendered-dom-offline-parse-2026-10-23
Observed UTC: Local offline inspection time (capture timestamp not embedded as source last-update)
Character / realm / source: Aikka / Onyxia / local rendered-DOM capture of summary page
Question: Which required fields are directly visible in one summary rendered-DOM capture without network access?
Method and request count: Offline text parsing of local-captures/aikka-onyxia-summary-dom.html; zero network requests.
Result: Identity, character-stats text, item `rel` payloads (item/ench/gems), explicit empty Shirt/Tabard slots, two specialization summary point distributions, nav links to other sections, and recent achievement activity snippets were observable.
Evidence / fixture: local-captures/aikka-onyxia-summary-dom.html (ignored), tests/fixtures/synthetic/summary-page-dom-synthetic.html, parser output from offline diagnostic command.
Limitations: Capture may include JavaScript-generated elements; full talents/glyphs/statistics/reputation/achievement traversal not captured here. Recent activity is explicitly partial.
Implementation consequence: Added offline summary-capture parser mode that preserves raw namespaces and reports ambiguity instead of guessing slot names.
```

```text
Finding ID: armory-onyxia-aikka-talents-offline-parse-2026-10-23
Observed UTC: Local offline inspection time (capture timestamp not embedded as source last-update)
Character / realm / source: Aikka / Onyxia / local rendered-DOM captures of talents page
Question: How are multiple talent specs, selected talents, glyphs, and spec-to-glyph associations represented in the rendered DOM? Is active in-game spec explicit?
Method and request count: Offline text parsing of two local-captures/aikka-onyxia-talents-spec1-dom.html and local-captures/aikka-onyxia-talents-spec2-dom.html; zero network requests per capture. Parser initially used regex-based extraction but was refactored to use stdlib HTMLParser for structural robustness. Final implementation uses HTMLParser for spec containers, talent trees, and talent nodes; HTMLParser also used for spec tabs and glyph blocks with unordered CSS-class handling. Parser validates talent-rank text format (X/Y), preserves raw_rank_text for all nodes, retains malformed nodes with error markers, and detects missing structural elements (tree-info, talent-points divs, spec tabs without matching containers). Tree-total validation compares sum(points_spent) against reported_total; validation becomes indeterminate if any talent has a parse error or if tree-info is missing.
Result: Both captures are substantively identical across all specs, trees, and individual talent allocations. Specs are keyed by `data-spec` attributes (0=Discipline, 1=Holy). Each spec container holds three talent trees (Discipline, Holy, Shadow) with individual talent nodes. Selected ranks are represented as text (e.g., "5/5" means 5 points spent out of 5 maximum). Source spell IDs are extracted from `href` attributes.

Talent point allocations verified by comparing (source_spell_id, points_spent, points_max) tuples. **All tree totals MATCH reported values:**

| Spec | Tree | Node count | Selected nodes | Sum(points_spent) | Reported total | Validation |
|---|---|---|---|---|---|---|
| 0 (Discipline) | Discipline | 28 | 22 | 57 | 57 | ✓ MATCH |
| 0 (Discipline) | Holy | 27 | 5 | 14 | 14 | ✓ MATCH |
| 0 (Discipline) | Shadow | 27 | 0 | 0 | 0 | ✓ MATCH |
| 1 (Holy) | Discipline | 28 | 7 | 18 | 18 | ✓ MATCH |
| 1 (Holy) | Holy | 27 | 19 | 53 | 53 | ✓ MATCH |
| 1 (Holy) | Shadow | 27 | 0 | 0 | 0 | ✓ MATCH |

Both Discipline and Holy trees have identical available talent nodes across specs (28 nodes each; each tree in each spec has all talents available). However, each spec has different selected talent allocations: Spec 0 (Discipline focus) allocates 57+14+0=71 total points; Spec 1 (Holy focus) allocates 18+53+0=71 total points. Both specializations use all 71 available talent points.

Glyphs are organized by spec in separate blocks (major/minor categories) with spell IDs and names. Spec 0: 3 major + 2 minor; Spec 1: 3 major + 3 minor. Active in-game spec is NOT explicit in rendered DOM; tab UI selection state and display visibility do not indicate in-game active spec.

Evidence / fixture: local-captures/aikka-onyxia-talents-spec1-dom.html (ignored), local-captures/aikka-onyxia-talents-spec2-dom.html (ignored), tests/fixtures/synthetic/talents-page-dom-synthetic.html, talents_parser.py offline diagnostic output.
Limitations: Rendered DOM only; JavaScript-generated or lazy-loaded elements may not be present. Talent effect text (selected-rank bonuses, etc.) is not embedded in these captures. Glyph effect descriptions are absent from these captures (future investigation needed).
Implementation consequence: Added offline talents-capture parser (talents_parser.py) using stdlib HTMLParser for robust structural extraction. Parser extracts all specs regardless of visibility, preserves source spell IDs with raw href attributes, reports active-spec as "unknown_not_determined_from_capture", validates tree totals by comparing sum(points_spent) to reported_total (validation is indeterminate if any talent has rank_parse_error or tree-info is missing). Parser handles four edge cases: (1) talent anchors without talent-points divs are retained with null ranks and error marker; (2) trees without tree-info divs have null reported_total and indeterminate validation; (3) spec tabs without matching containers generate warnings; (4) glyph divs with reordered CSS classes (e.g., "major glyph" vs "glyph major") are correctly parsed. Handles malformed rank text (missing slash separator, out-of-range values) with error preservation. Distinguishes selected (points_spent > 0) vs. unselected (points_spent = 0) talents. 24 offline tests cover hidden/visible specs, rank validation, glyph associations, error cases, edge-case regression tests, and container boundary verification. All tree totals in both real captures MATCH reported values; both captures extract identically.
```

## 14. Open questions

1. Which required fields are exposed on each realm and character?
2. Are ordinary HTTP requests sufficient?
3. ~~How are secondary specs, glyphs, and active-state flags represented?~~ **PARTIALLY RESOLVED (Milestone 0):** Multiple talent specs are exposed via `data-spec` DOM attributes. Glyphs are associated with specs in separate blocks. Active in-game spec is NOT explicit in rendered DOM (tab selection and visibility state do not reliably indicate in-game active spec). Character-selection UI state and in-game active spec are distinct; the latter remains unknown from capture inspection alone.
4. What are the real namespaces of gem and enchantment codes?
5. Which external definitions are compatible, available, and permitted for intended use?
6. How many requests are needed to enumerate PvE achievement/statistic categories?
7. What portion of progression grouping and reputation relevance can be verified?
8. What source limitations require a specification change?
9. What allowed/manual capture workflow can provide inspectable character HTML evidence when direct probe access is blocked?
10. Are talent effect text and glyph effect descriptions embedded in the rendered-DOM talent page, or are they loaded asynchronously/via tooltip service?

## 15. Milestone 0 completion checklist

- [ ] Retrieval probe is runnable with documented setup and commands.
- [ ] Rate-limit safeguards are present before multi-page collection.
- [ ] All four character inputs have been tested or have a recorded access limitation.
- [ ] Field matrix distinguishes verified, partial, absent, blocked, and uninvestigated data.
- [ ] At least one equipment-to-definition chain is verified; missing test coverage is explicit.
- [ ] Dual-spec and glyph findings are recorded without unsupported assumptions.
- [ ] Ruleset/dataset compatibility and identifier mappings are documented.
- [ ] Progression traversal, filtering coverage, and request costs are described.
- [ ] Fixtures are sanitized, attributable, and appropriately reusable.
- [ ] Access terms and relevant licenses have been checked.
- [ ] Remaining gaps and proposed scope changes are listed for review.
- [ ] No full exporter, optimization engine, AI runtime dependency, or bypass mechanism was added prematurely.
