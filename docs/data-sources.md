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
| Primary spec | Tree totals, selected talents/ranks, effect text | Partial | TBD | Rendered-DOM talents capture contains all selected-talent allocations per spec with source spell IDs; effect text absent (candidate rank-discovery mechanism identified for spell resolution; see Findings) |
| Secondary spec | Presence, talents/ranks, source order/identifier | Partial | TBD | Both captured specs (0=Discipline, 1=Holy) fully extracted with allocations; active in-game spec unknown from capture |
| Active spec | Explicit active-state evidence | Not exposed in capture | TBD | In-game active specialization is unknown. Both captured specs and their associated glyphs are included; observed equipment is recorded separately. Tab UI state and display visibility do not indicate in-game active spec. |
| Glyphs | Identifiers, effects, categories, association with each spec | Partial | TBD | Spec-associated glyph identifiers and categories extracted from rendered-DOM (Spec 0: 3 major + 2 minor; Spec 1: 3 major + 3 minor); effect descriptions absent; glyph definition resolution mechanism unknown |
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
| tests/fixtures/synthetic/layout-consistent-with-anchors.html | Synthetic | 2026-10-24 | Onyxia (synthetic title only) | Offline layout-inference tests: consistent 8/8/3 equipment slot layout with Shirt/Tabard explicit anchors | Synthetic structure with all 19 slots, labels, and icon refs; safe to commit |
| tests/fixtures/synthetic/layout-count-mismatch.html | Synthetic | 2026-10-24 | Onyxia (synthetic title only) | Offline layout-inference tests: count mismatch scenario (7 left slots instead of 8) | Synthetic structure to verify unverified status and count validation; safe to commit |
| tests/fixtures/synthetic/layout-anchor-mismatch.html | Synthetic | 2026-10-24 | Onyxia (synthetic title only) | Offline layout-inference tests: anchor-position mismatch (Shirt at left_5, Tabard at left_6 instead of expected left_6/left_7) | Synthetic structure to verify anchor consistency checking; safe to commit |
| tests/fixtures/synthetic/layout-no-anchors.html | Synthetic | 2026-10-24 | Onyxia (synthetic title only) | Offline layout-inference tests: 8/8/3 layout with no explicit slot labels | Synthetic structure to verify unverified status when anchors absent; safe to commit |
| tests/fixtures/synthetic/layout-no-img.html | Synthetic | 2026-10-24 | Onyxia (synthetic title only) | Offline layout-inference tests: icon stem capture with alternating missing `<img>` tags | Synthetic structure to verify null and non-empty icon stem handling; safe to commit |
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

```text
Finding ID: cavernoftime-spell-rank-discovery-2026-10-24
Observed UTC: 2026-10-24 (Copilot controlled requests + user manual screenshots; no embedded timestamps)
Character / realm / source: Aikka / Onyxia / cavernoftime.com spell definition API
Question: How are multi-rank talent effects retrieved? Can selected-rank definitions be resolved from captured talent spell IDs?
Method and request count: 
  Automated: Two controlled live HTTP requests. (1) GET /spell=14748&power=true (redirects allowed; 30-second timeout, 256 KiB cap). (2) GET /spell=14748 (explicit no-redirect handler; 30-second timeout, 512 KiB cap). Both HTTP 200. No retries after success.
  Manual: User-provided browser screenshots of /spell=14769 (normal page) and /spell=55679 (normal page).
Result:
  Automated /spell=14748&power=true: HTTP 200, text/html. Rank 1 tooltip: "Improved Power Word: Shield, Rank 1. Increases the damage absorbed by your Power Word: Shield by 5%."
  Automated /spell=14748: HTTP 200, text/html. Normal definition page; related-spell data identifies Rank 2 as spell 14768, Rank 3 as spell 14769. Unranked entry spell 24191 present in "See Also" (not a rank mapping).
  Manual screenshot /spell=14769: "Improved Power Word: Shield, Rank 3". Full effect: "Increases the damage absorbed by your Power Word: Shield by 15%."
  Manual screenshot /spell=55679: "Glyph of Flash Heal". Full effect: "Reduces the mana cost of your Flash Heal by 10%."
Evidence / fixture: Live probe results (Rank 1 definition, rank-ID mappings) extracted from automated responses. User manual screenshots document Rank 3 definition and one glyph definition. Perplexity visually inspected user screenshots.
Limitations: 
  Automated: ONE talent (14748 Rank 1) verified; Rank 2/3 effects not yet fetched via automation.
  Manual: Rank 3 definition and one glyph definition observed; Rank 2 effect, general coverage across other talents/glyphs, and automated reliability remain unresolved.
  Ruleset compatibility for Rank 3 and glyph effects not established. Unranked entry (24191) shows not all "See Also" entries are rank mappings; heuristic for filtering rank entries not established. Source access/reuse licensing terms remain unchecked. Glyph parameter sensitivity (&power=true vs. normal page) not established.
Implementation consequence: Establishes candidate rank-discovery route for talents: (1) extract spell ID from talent href; (2) fetch Cavernoftime spell page; (3) parse page for related spell entries to identify adjacent rank IDs; (4) fetch each rank's spell ID to retrieve rank-specific definition. Rank 3 (14769) and one glyph (55679) definitions manually confirmed. Automated access and full coverage remain unresolved; ruleset compatibility and source terms require verification.
```

```text
Finding ID: cavernoftime-spell-automated-access-denial-2026-10-24
Observed UTC: 2026-10-24 02:45 GMT
Character / realm / source: Talent 14769, Glyph 55679 / cavernoftime.com
Question: Do higher-rank talent effects and glyph definitions remain retrievable via automated Cavernoftime spell page fetches after successful earlier probes?
Method and request count: Two sequential GET requests (stdlib urllib.urlopen, 30-second timeout, 512 KiB+ cap, 3-second inter-request delay): (1) /spell=14769 (normal page); (2) /spell=55679&power=true (tooltip form). Default urllib behavior allowed redirects; redirect history and actual underlying request count not retained.
Result: Both requests returned HTTP 403 Forbidden. No response body content retrieved. User-Agent header was "Python-urllib/Investigation" (differed from earlier successful probes).
Evidence / fixture: Request metadata and HTTP response codes only; no response content to file.
Limitations: 
  Cause unresolved: Cannot determine whether blocking is due to IP-based access control, session state, specific header requirements, rate limiting, or other factors.
  Changed condition: User-Agent header differed from earlier successful probes (checkpoint used unspecified headers; this attempt used "Python-urllib/Investigation").
  Second request should not have run following first request's access denial.
  Earlier checkpoint documented successful /spell=14748 and /spell=14748&power=true fetches; those findings remain valid within their recorded scope.
Implementation consequence: Cavernoftime automated access currently unavailable for these spell IDs. Manual verification (user screenshots) provides the definitions; automated retrieval route is blocked pending investigation of access conditions or alternative sources.
Observed UTC: 2026-10-24 (Copilot retained-file verification; no embedded timestamp)
Character / realm / source: Item 51178 / Cavernoftime item tooltip API
Question: Do enchantment (ench=) and gem codes (gems=) parameters independently resolve effect text? How do individual parameters contribute to equipped-instance tooltips?
Method and request count: Five sequential item GET requests to https://wotlk.cavernoftime.com/item=51178 with varying parameters: (1) combined ench=3820&gems=3627:3879, (2) base (no params), (3) ench=3820 only, (4) gems=3627:3879 only. All HTTP 200, no redirects, 30-second timeout, 512 KiB+ cap. No retries. Retained responses saved to temporary files and verified via local file checks (no reconstruction).
Result:
  Base (no params): Explicit socket type labels "Meta Socket" and "Blue Socket" (q0 CSS class). No enchantment effect line. No gem-effect descriptions.
  Ench=3820 isolated: Adds effect text "+30 Spell Power and 20 Critical strike rating." (q2 CSS). Socket labels REMAIN "Meta Socket" and "Blue Socket" (unchanged). No gem effects added.
  Gems=3627:3879 isolated: Replaces socket labels with two gem-effect descriptions: "+21 Intellect and Chance to restore mana on spellcast" and "+10 All Stats" (both q1 CSS class with background icon URLs). No enchantment line added.
  Combined ench=3820&gems=3627:3879: Enchantment effect line + gem-effect descriptions (union of isolated variants).
Evidence / fixture: Actual retained response files verified: response_base.txt (1950 bytes), response_ench_only.txt (2029 bytes), response_gems_only.txt (2228 bytes). File-based presence checks performed; excerpts extracted from saved content.
Limitations: Tested on ONE item (51178) with ONE enchantment code and ONE gem-code pair. Individual gem codes (3627, 3879) produce joint effect text; per-gem mapping not isolated. Socket-bonus CSS class (q0 vs. q2) was reported in earlier response excerpts but not confirmed by final retained-file verification—do not claim verified. Socket bonus activation state unknown. Meta socket requirement not explicitly stated; meta label present only when socket is unfilled. No verification of bonus activation rules or conditional effects.
Implementation consequence: Cavernoftime item parameter API successfully resolves enchantment and gem effect text to readable descriptions for this item/parameter set. Enchantment ID 3820 → "+30 Spell Power and 20 Critical strike rating" (confirmed). Gem codes 3627:3879 → two effect descriptions (confirmed). Socket type labels are explicit in base response (Meta, Blue). Gem-code namespace (distinct from enchantment IDs or overlapping) and individual gem item identities remain unresolved. No item-ID or spell-ID mappings generated. Effect-text resolution confirmed; definition-lookup capability not established.
```

```text
Finding ID: evowow-enchantment-3820-manual-verification-2026-10-24
Observed UTC: User screenshot provided; no automated retrieval timestamp
Character / realm / source: EvoWoW WOTLK enchantment lookup (https://wotlk.evowow.com/?enchantment=3820)
Question: Does historical EvoWoW enchantment lookup provide enchantment ID and effect resolution? (User's old main.py sent both equipment enchantments and gem codes through EvoWoW ?enchantment= parameter.)
Method and request count: One Copilot automated GET attempt to https://wotlk.evowow.com/?enchantment=3820 (HTTP 403 Forbidden, access denied; no content). User-provided browser screenshot of the same URL showing successful manual access.
Result:
  Automated Copilot fetch: HTTP 403 Forbidden. No page content retrieved.
  User screenshot (manual browser access): Page title/heading shows "+30 Spell Power and 20 Critical strike rating." Quick Facts section displays "Enchantment ID: 3820". Effect details: Spell power Value 30; Critical strike rating Value 20. "Used by Item (3)" section lists multiple related items (Arcanum of Burning Mysteries entries noted; unique item IDs not extracted from screenshot).
Evidence / fixture: User-provided screenshot; Copilot 403 response (no content). No sanitized fixture created (copyrighted content). Screenshot evidence shows explicit enchantment_id namespace and matching effect text.
Limitations: Automated access currently blocked (403); manual access requires browser navigation. Gem-code 3627 lookup not attempted (investigation halted per safeguards after automated access failure). Related-item links visible in screenshot do not establish unique item IDs. EvoWoW data reuse terms and licensing unchecked. Historical main.py evidence shows ?enchantment= parameter used for both equipment enchantments and gem codes; gem-code namespace (whether distinct or overlapping with enchantment_id) not yet verified against EvoWoW. No per-gem (3627 vs 3879) isolation observed.
Implementation consequence: EvoWoW enchantment_id 3820 explicitly maps to the same effect text as Cavernoftime ("+30 Spell Power and 20 Critical strike rating"). Source namespace established: enchantment_id. Automated access currently unavailable; manual verification feasible. Gem-code namespace remains unresolved; requires separate investigation of EvoWoW gem lookups or alternative source. Historical script design (conflating ench codes and gem codes in single parameter) suggests possible namespace overlap, but no current evidence.
```

```text
Finding ID: armory-onyxia-aikka-equipment-slot-layout-inference-2026-10-24
Observed UTC: 2026-10-24 (offline analysis of existing local capture)
Character / realm / source: Aikka / Onyxia / local rendered-DOM capture of summary page
Question: Can equipment slot layout be inferred offline from DOM position, and are explicit slot labels (Shirt, Tabard) reliable anchors for validating the standard WotLK paperdoll slot order?
Method and request count: Offline layout validation and inference using pure Python function `_validate_and_infer_layout()` on 19 captured equipment slots; zero network requests.
Result: Equipment layout in rendered-DOM summary is consistent with standard WotLK paperdoll order: 8 left-column slots, 8 right-column slots, 3 bottom-row slots, total 19 slots. Two explicit labels (Shirt, Tabard) are present and match expected positions:
- left_6: explicit label "Shirt" matches expected "Shirt" ✓
- left_7: explicit label "Tabard" matches expected "Tabard" ✓
Observed counts equal expected counts (8/8/3). Layout validation status: "anchors_consistent". All 19 slot positions were inferred against standard order:
- Left: Head, Neck, Shoulder, Back, Chest, Shirt, Tabard, Wrist
- Right: Hands, Waist, Legs, Feet, Finger 1, Finger 2, Trinket 1, Trinket 2
- Bottom: Main Hand, Off Hand, Ranged

Icon image filenames (stems) were captured as raw evidence where `<img>` tags are present; empty slots (Shirt, Tabard) have null icon stems. Examples: inv_helmet_156 (Head), inv_belt_52 (Waist), inv_misc_cape_18 (Back), inv_jewelry_ring_85 (Finger 1), spell_ice_rune (Trinket 2).

Evidence / fixture: local-captures/aikka-onyxia-summary-dom.html (ignored), 5 synthetic fixtures (layout-consistent-with-anchors.html, layout-count-mismatch.html, layout-anchor-mismatch.html, layout-no-anchors.html, layout-no-img.html).
Limitations: Layout inference is positional only; does not verify slot identity against item inventory-type definitions, game-data tables, or other external references. Inference is valid only when validators confirm consistency (8/8/3 counts + unknown=0 + all explicit labels match expected names). When validation status is "unverified" (count mismatch, unknown group slots, no anchors, or anchor mismatch), all inferred_slot_name values are null; this is a deliberate design choice to distinguish positional layout from verified slot identity. Bounds-checking prevents out-of-range anchor positions from raising exceptions; out-of-range anchors are recorded with expected_name=null, match=false, and an issue noted.
Implementation consequence: Added `STANDARD_WOTLK_LAYOUT` constant and `_validate_and_infer_layout()` pure function to summary_parser.py. Function returns `layout_validation` dict containing expected_counts (with unknown: 0), observed_counts (with unknown), anchors_checked, status ("anchors_consistent" or "unverified"), issues (list of issues if unverified), and note (explanation of inference limitations). Each slot dict contains `layout_inference` subdict with inferred_slot_name (name or null), basis ("standard_wotlk_paperdoll_order"), status (inherits validation status), and optional note field for Finger/Trinket slots explaining that numbering reflects layout order only. Icon stems are captured in slot["item_reference"]["icon_stem"] as raw evidence (null if no `<img>` tag). 10 new layout-inference tests cover all validation branches: consistent layout with anchors (all 19 inferred), count mismatch (all inferred names null), anchor mismatch (all null with issue), no anchors (all null with issue), out-of-range anchors (no exception, issue recorded), unknown-group slots (unverified), explicit names never overwritten, Finger/Trinket order notes present, icon stem capture with exact assertion, icon stem capture with at least-one null and at least-one non-empty. Full suite: 106 tests pass.
```

## 13a. Equipped-item code inventory — Aikka / Onyxia (offline, 2026-10-24)

**Diagnostic command:** `$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m warmane_exporter.summary_diagnostic "local-captures\aikka-onyxia-summary-dom.html"`
**Exit code:** 0

**19-slot table (left_1..left_8, right_1..right_8, bottom_1..bottom_3):**

| slot_key | inferred_slot_name | item_id | ench (raw) | gems (raw) | item status | ench status | gems status | evidence |
|---|---|---|---|---|---|---|---|---|
| left_1 | Head | 51178 | 3820 | 3627:3879:0 | unresolved | resolved | partial | [cavernoftime-enchantment-gem-parameter-isolation-2026-10-24](#findings-log) |
| left_2 | Neck | 50809 | — | 3520:0:0 | unresolved | n/a | unresolved | none |
| left_3 | Shoulder | 50449 | 3810 | 3520:3520:0 | unresolved | unresolved | unresolved | none |
| left_4 | Back | 47256 | 3728 | — | unresolved | unresolved | n/a | none |
| left_5 | Chest | 48063 | 3832 | 3118:3118:0 | unresolved | unresolved | unresolved | none |
| left_6 | Shirt | — | — | — | n/a | n/a | n/a | none |
| left_7 | Tabard | — | — | — | n/a | n/a | n/a | none |
| left_8 | Wrist | 47588 | 2326 | 3520:0:0 | unresolved | unresolved | unresolved | none |
| right_1 | Hands | 48067 | 3246 | 3448:0:0 | unresolved | unresolved | unresolved | none |
| right_2 | Waist | 48054 | — | 3118:3118:0 | unresolved | n/a | unresolved | none |
| right_3 | Legs | 51262 | 3872 | 3520:3520:0 | unresolved | unresolved | unresolved | none |
| right_4 | Feet | 51380 | 3232 | 3520:3520:0 | unresolved | unresolved | unresolved | none |
| right_5 | Finger 1 | 50400 | 3840 | 3448:0:0 | unresolved | unresolved | unresolved | none |
| right_6 | Finger 2 | 49990 | 3840 | 3520:0:0 | unresolved | unresolved | unresolved | none |
| right_7 | Trinket 1 | 50358 | — | — | unresolved | n/a | n/a | none |
| right_8 | Trinket 2 | 45929 | — | — | unresolved | n/a | n/a | none |
| bottom_1 | Main Hand | 48039 | 3834 | 3520:0:0 | unresolved | unresolved | unresolved | none |
| bottom_2 | Off Hand | 45314 | — | — | unresolved | n/a | n/a | none |
| bottom_3 | Ranged | 45713 | — | — | unresolved | n/a | n/a | none |

**Status legend:**
- `resolved`: Definition is confirmed via existing findings documented in this log.
- `partial`: Some aspects confirmed; others unresolved (e.g., gems 3627:3879 — joint effect text only; per-gem mapping not isolated).
- `unresolved`: No definition verification performed; identifier and namespace exist but definition unknown.
- `n/a`: Slot is empty or parameter not applicable.

**Status justifications:**

- **Ench 3820 = resolved:** Confirmed via [cavernoftime-enchantment-gem-parameter-isolation-2026-10-24](#findings-log) live isolation (→ "+30 Spell Power and 20 Critical strike rating") and [evowow-enchantment-3820-manual-verification-2026-10-24](#findings-log) (manual screenshot: effect text matches). Cavernoftime isolation finding also provides evidence that ench=3820 parameter independently resolves on this item.
- **Gems 3627:3879 = partial:** Joint effect text confirmed via [cavernoftime-enchantment-gem-parameter-isolation-2026-10-24](#findings-log) (gems=3627:3879 parameter returns two effect descriptions). Per-gem individual effect mappings NOT isolated; gem code 3627 not looked up on EvoWoW; socket-bonus activation state unknown.
- **Item IDs = unresolved for all 19:** Layout inference is positional only; inventory-type field definitions not available from offline capture. Identifiers are observed in `item` namespace of `rel` payloads but not verified against item definition sources.
- **All other ench/gems codes = unresolved:** No definition verification performed for these codes in existing findings.

### Candidate live requests (NOT approved)

The following URLs would close unresolved items. All URLs validated in offline mode using `definition_diagnostic.py` default (no --live-once flag).

**Item definition requests (17 unique item IDs):**
```
https://wotlk.cavernoftime.com/item=45314&power=true      [PASS]
https://wotlk.cavernoftime.com/item=45713&power=true      [PASS]
https://wotlk.cavernoftime.com/item=45929&power=true      [PASS]
https://wotlk.cavernoftime.com/item=47256&power=true      [PASS]
https://wotlk.cavernoftime.com/item=47588&power=true      [PASS]
https://wotlk.cavernoftime.com/item=48039&power=true      [PASS]
https://wotlk.cavernoftime.com/item=48054&power=true      [PASS]
https://wotlk.cavernoftime.com/item=48063&power=true      [PASS]
https://wotlk.cavernoftime.com/item=48067&power=true      [PASS]
https://wotlk.cavernoftime.com/item=49990&power=true      [PASS]
https://wotlk.cavernoftime.com/item=50358&power=true      [PASS]
https://wotlk.cavernoftime.com/item=50400&power=true      [PASS]
https://wotlk.cavernoftime.com/item=50449&power=true      [PASS]
https://wotlk.cavernoftime.com/item=50809&power=true      [PASS]
https://wotlk.cavernoftime.com/item=51178&power=true      [PASS]
https://wotlk.cavernoftime.com/item=51262&power=true      [PASS]
https://wotlk.cavernoftime.com/item=51380&power=true      [PASS]
```

**Enchantment effect-text requests (10 unique ench codes; 3820 already resolved):**
```
https://wotlk.cavernoftime.com/item=51178&power=true&ench=2326      [PASS]
https://wotlk.cavernoftime.com/item=51178&power=true&ench=3232      [PASS]
https://wotlk.cavernoftime.com/item=51178&power=true&ench=3246      [PASS]
https://wotlk.cavernoftime.com/item=51178&power=true&ench=3728      [PASS]
https://wotlk.cavernoftime.com/item=51178&power=true&ench=3810      [PASS]
https://wotlk.cavernoftime.com/item=51178&power=true&ench=3832      [PASS]
https://wotlk.cavernoftime.com/item=51178&power=true&ench=3834      [PASS]
https://wotlk.cavernoftime.com/item=51178&power=true&ench=3840      [PASS]
https://wotlk.cavernoftime.com/item=51178&power=true&ench=3872      [PASS]
```

**Gem effect-text requests (5 unique gem codes; 3627 and 3879 in joint pair from table, tested individually):**
```
https://wotlk.cavernoftime.com/item=51178&power=true&gems=3118      [PASS]
https://wotlk.cavernoftime.com/item=51178&power=true&gems=3448      [PASS]
https://wotlk.cavernoftime.com/item=51178&power=true&gems=3520      [PASS]
https://wotlk.cavernoftime.com/item=51178&power=true&gems=3627      [PASS]
https://wotlk.cavernoftime.com/item=51178&power=true&gems=3879      [PASS]
```

**Summary:**
- Total requests: 31 unique URLs
- Per-host breakdown: wotlk.cavernoftime.com (31)
- Validation status: All 31 URLs passed offline validation (no network requests executed)
- URL form validation was performed in offline mode only. No --live-once requests executed. Validator rejects URLs that do not match approved Cavernoftime patterns (positive-integer item/ench IDs; nonnegative gem codes with colon separators).

### Limitations

- **Slot names inferred positionally; item IDs are raw values from the capture:** Layout inference assigns names from standard WotLK paperdoll order based on position; no game-data verification of inventory-type definitions.
- **Gem codes produce joint effect text:** Cavernoftime gem= parameter returns combined gem descriptions; per-gem individual mapping not isolated from this data source.
- **Socket bonus state unknown:** No evidence of socket-bonus activation rules or conditional effects discovered in captured data or existing findings.
- **Ench/gem coverage incomplete:** Only Ench 3820 resolved; 9 additional ench codes and 5 gem codes remain unverified.

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


## Offline client DBC data (verified 2026-10-24)

Status: verified against the local 3.3.5a (build 12340) client by the user running dbc_diagnostic.

- Source: DBC tables inside the client MPQ archives (patch archives override base ones). No network access, no third-party site.
- Verified field indexes (uint32 fields, key in field 0; strings are offsets into the table string block):
  - SpellItemEnchantment.dbc (38 fields): name enUS = field 14. Enchant 3820 = "+30 Spell Power and 20 Critical strike rating." (matches manual evidence).
  - Spell.dbc (234 fields): name enUS = 136, rank enUS = 153, description enUS = 170. Spell 14769 = "Improved Power Word: Shield", Rank 3. Spell 55679 = "Glyph of Flash Heal".
  - Item.dbc (8 fields): class = 1, subclass = 2, inventory type = 6. Item 51178 = armor, cloth, inventory type 1 (head).
- Not available offline: item names, and the item-to-gem-property mapping (3.3.5a keeps these in the item cache, not in DBC files). Gem item definitions still need another source or manual evidence.
- Earlier live-site findings: EvoWoW robots.txt does not disallow item/spell/enchantment pages but no terms were found; Cavernoftime has no robots.txt and states "All rights reserved". Both reject non-browser clients. Automated live access is not established as permitted.
- Client path comes from warmane-character-exporter.config (not committed) or --data-dir.

### Finding: gem-codes-are-enchantment-ids-2026-10-24

Status: verified offline against the local 3.3.5a client (user-run output).

- Gem codes seen in the Cavernoftime parameter test (3627, 3879) are SpellItemEnchantment IDs, not item IDs. Offline lookup: 3627 = "+21 Intellect and Chance to restore mana on spellcast", 3879 = "+10 All Stats". This matches the Cavernoftime joint effect text, and each gem is now resolved individually.
- Weapon/armor enchant 3820 resolves to "+30 Spell Power and 20 Critical strike rating."
- Raw spell descriptions keep template tokens (for example $s1) and may lack spaces where the web page inserts markup (for example "yourPower Word: Shield"). Treat description text as raw; do not claim rendered tooltip text.
- Consequence: enchant and gem text no longer needs any live definition site. Remaining unresolved: item names, socket bonuses and the gem item-to-enchant mapping, in case a source reports gem item IDs.

### Finding: talent-rank-spells-offline-2026-10-24

Status: verified offline against the local 3.3.5a client (user-run output).

- Talent.dbc (23 fields): tab = field 1, row = 2, column = 3, rank spell IDs = fields 4..12 (zero = unused).
- Spells 14748, 14768 and 14769 all resolve to talent 343 (tab 201, row 2, column 2) with ranks [14748, 14768, 14769]. This matches the earlier Cavernoftime rank discovery for Improved Power Word: Shield, so live rank discovery is no longer needed.

### Finding: talents-and-glyphs-offline-enrichment-2026-10-24

Status: verified against the real capture aikka-onyxia-talents-spec1-dom.html and the local 3.3.5a client (user-run output).

- Both specs in the capture: every talent resolved to a client talent (Discipline 28/28, Holy 27/27, Shadow 27/27 per spec), with rank spell IDs and the selected-rank description.
- All 11 glyphs resolved by spell ID; GlyphProperties.dbc slot flags (0 major, 1 minor) agreed with the capture category for every glyph. GlyphProperties.dbc has 4 fields: ID, SpellID, GlyphSlotFlags, SpellIconID.
- client_warnings: 0. The capture's source_spell_id works as a talent rank spell ID and as a glyph spell ID.
- Limitation: spell descriptions are raw templates ($s1, $d, $/1000;s1, conditionals). Rendering numeric values needs Spell.dbc effect and duration data and is not implemented; do not present raw templates as final tooltip text.
- Limitation: the capture shows which talents have points; the in-game active spec cannot be determined from the capture.

### Finding: equipment-offline-enrichment-2026-10-24

Status: verified against the real capture aikka-onyxia-summary-dom.html and the local 3.3.5a client (user-run output).

- 17 equipped items: each item ID resolved in Item.dbc and its inventory type fit the layout-inferred paperdoll slot (head, neck, shoulder, back, chest/robe, wrist, hands, waist, legs, feet, finger x2, trinket x2, main-hand, held-in-off-hand, ranged). This independently supports the standard-order slot inference.
- Every ench= code and every nonzero gems= code resolved as a SpellItemEnchantment ID (examples: 3520 = "+23 Spell Power", 3118 = "+12 Spell Power", 3728 = "Darkglow Embroidery"). client_warnings: 0.
- Gem code 0 is reported as an empty position. The rel payload always lists three positions, so "empty" cannot distinguish an unfilled socket from a socket that does not exist; the number of real sockets is unknown (it needs item socket data, which is not in Item.dbc).
- Not available offline: item names, item quality, socket count and socket bonus, item stats.


### Finding: warmane-json-api-live-2026-10-24

Status: verified by 4 live GET requests (user-approved, one per character, 15 s apart, via the user's own Chrome; no blocks, no rate limit). Raw responses saved to git-ignored local-captures/api-<name>-<realm>-summary.json.

- Endpoint: https://armory.warmane.com/api/character/<Name>/<Realm>/summary returns JSON (HTTP OK in a normal browser). It is the source for item names, which the client DBCs lack.
- Fields: name, realm, online, level, faction, gender, race, racemask, class, classmask, honorablekills, guild, achievementpoints, equipment[] (name, item id, transmog), talents[] (tree name, points per tree, two entries for dual spec), professions[] (name, skill), pvpteams[].
- Equipment lists only non-empty slots and carries NO slot index, NO enchant, NO gems. Slot must come from Item.dbc inventory type or from the HTML summary. Enchants and gems still require the HTML summary rel payload.
- Aikka@Onyxia: all 17 item IDs match the saved HTML capture in the same order. Talent point splits are given per tree but without an active-spec marker.
- Both realms and both characters answered (Bezduse 16 items, Aikka@Icecrown 17 items; empty professions/pvpteams/guild appear as [] or "").
- Request cost: 1 request per character for JSON basics; HTML summary and talents pages are still needed for enchants, gems, talents and glyphs.
- Not yet probed live: achievements, statistics, HTML pages from a plain HTTP client (earlier scripted request got Cloudflare 1010).

### Finding: achievements-statistics-structure-2026-10-24

Status: verified by 3 further live requests (user-approved; achievements page GET, one category POST, statistics page GET; 12 s apart; user's Chrome; no blocks). Total live requests this session: 7. Raw captures in git-ignored local-captures/.

- Achievements page (/character/<Name>/<Realm>/achievements) shows per-category totals only (Aikka@Onyxia: 323 / 1058; General 24/54, Quests 5/49, Exploration 3/70, PvP 14/166, Dungeons and Raids 249/458, Professions 6/75, Reputation 12/45, World Events 4/141, Feats of Strength 6). Each category is loaded by POST to the same URL with form field category=<id> and returns JSON {"content": "<html>"}.
- Top-level category ids: General 92, Quests 96, Exploration 97, Player vs. Player 95, Dungeons and Raids 168; subcategories use the same POST with a subcategory id (for example Quests: Classic 14861, TBC 14862, WotLK 14863). Full id list is in the page's data-category and data-subcategory attributes. Professions, Reputation, World Events and Feats ids still to be read.
- Category 92 response (about 30 KB, 54 achievements): each entry has id (id="ach6"), points, icon URL, title, description and a date ("Earned MM/DD/YYYY"). Whether unearned entries are included, and the exact markup for them, needs checking in the saved file.
- Statistics page (/statistics): sidebar categories with ids (Character 130, Combat 141, Kills 128, Deaths 122, Quests 133, Dungeons and Raids 14807, Skills 132, Travel 134, Social 131, Player vs. Player 21, with subcategories) and a name-and-value summary list; unset values appear as "- -".
- Estimated full export cost for one character via the site: about 9 achievement POSTs plus statistics category loads, in addition to the pages already known. Needs a throttled, resumable run; do not fetch all at once.

### Finding: achievements-locked-entries-2026-10-24

Status: verified offline against the saved category 92 response (no new requests).

- The response includes unearned achievements: markup class="achievement locked" (no date div), earned ones class="achievement" with a "Earned MM/DD/YYYY" date. Category 92 held 24 earned and 31 locked entries (55 total) while the page header said 24 / 54, so the entry count can differ by one from the header total; the parser must report both and warn on mismatch rather than assume equality.
- One POST per category therefore yields both the earned and the full achievement list.


## 16. Milestone 0 field-availability matrix and status (2026-10-24)

Status legend: verified = seen in real data; partial = seen for some characters or incompletely; not tested = no evidence yet; blocked = access failed.

### Field matrix

| Field | Best source found | Status | Notes |
|---|---|---|---|
| Name, realm, level, faction, race, class, gender, guild | JSON summary API | verified (4 of 4 characters) | Also in HTML summary |
| Achievement points, honorable kills | JSON summary API | verified (4 of 4) | |
| Equipped item IDs and names | JSON summary API | verified (4 of 4) | Names only here; no slot index, empty slots omitted |
| Equipment slot | HTML summary layout, cross-checked with Item.dbc inventory type | verified (Aikka@Onyxia, 17 of 17) | Not tested on other characters |
| Enchants and gems | HTML summary rel payload; text from SpellItemEnchantment.dbc | verified (Aikka@Onyxia) | Socket count and bonus unknown |
| Item quality, stats, sockets | none found | absent | Not in DBCs or JSON API |
| Talent points per tree | JSON summary API | verified (4 of 4) | Both specs, no active-spec marker |
| Individual talents and ranks | HTML talents page; definitions from Talent.dbc/Spell.dbc | verified (Aikka@Onyxia, both specs) | Not tested on other characters |
| Glyphs | HTML talents page; GlyphProperties.dbc | verified (Aikka@Onyxia) | |
| Active spec | none | absent | Not in JSON or rendered DOM |
| Professions and skill | JSON summary API | verified (4 of 4) | Skill values look inconsistent for one character (Bezduse@Onyxia, skill "1"); treat as unreliable |
| PvP teams | JSON summary API | verified (4 of 4) | |
| Achievements (earned and locked) | POST category=<id> on /achievements | partial (1 category, Aikka@Onyxia) | Header total differs by one from entry count |
| Statistics | /statistics page, category sidebar | partial (summary text only, Aikka@Onyxia) | Per-category loads not tested |
| Reputation, mounts, companions, match history | pages exist in the armory menu | not tested | |
| Icecrown HTML pages | not fetched | not tested | Only JSON API tested on Icecrown |

### Access finding

- Plain scripted HTTP to the HTML pages was blocked (Cloudflare 1010 and a 1015 rate limit seen earlier). The user's own Chrome worked for every request (7 live requests total, none blocked).
- Consequence: the exporter cannot assume a plain HTTP client for HTML pages. Options to evaluate in a later milestone: user-driven browser session, a browser-based fetcher run by the user, or accepting the JSON API only where a script client is allowed (not tested).

### Request-cost estimate per character (not yet measured end to end)

- JSON summary: 1
- HTML summary: 1; talents: 1 to 2 (spec switch may need a second load)
- Achievements: 1 page + about 9 category POSTs (subcategories may add more)
- Statistics: 1 page + about 10 category loads (not tested)
- Total: roughly 25 to 35 requests per character. Needs a throttled, resumable run with caching; do not run in one burst.

### Checklist status (section 15)

- Done or substantially done: client DBC offline definitions; equipment-to-definition chain; dual-spec and glyph findings; access terms review; request-cost estimate.
- Partial: field matrix (three characters lack HTML-page evidence); progression traversal (achievements/statistics only sampled); ruleset compatibility (client build 12340 matches the Warmane data seen, no mismatch found, but no explicit realm ruleset comparison done).
- Open: sanitized fixtures committed to the repo (captures are local and git-ignored); plain-HTTP viability; rate-limit safeguards verified under real conditions; statistics category structure; Professions, Reputation, World Events and Feats achievement ids.

### Proposed next step

Complete the remaining Milestone 0 gaps with a small second live batch (under 10 requests): Aikka@Icecrown and Bezduse HTML summary pages, one statistics category POST, and the remaining achievement category ids. Then build sanitized fixtures from saved captures and close Milestone 0 for review.


### Finding: live-batch-2-2026-10-24

Status: verified by 6 further live requests through the user's Chrome (3 HTML summary pages, achievements page, statistics page, one statistics POST; 12 s apart; no blocks). Total live requests this session: 13. Rendered DOM saved git-ignored as local-captures/<name>-<realm>-summary-dom.html.

- HTML summary pages loaded for Bezduse@Onyxia, Bezduse@Icecrown and Aikka@Icecrown. Item link counts (16, 16, 17) equal the JSON API equipment counts for the same characters. Offline enrichment run on these captures is pending (user-run).
- Complete achievement category ids (POST field category, subcategory ids as listed by the page): General 92; Quests 96 (14861 Classic, 14862 TBC, 14863 WotLK); Exploration 97 (14777 Eastern Kingdoms, 14778 Kalimdor, 14779 Outland, 14780 Northrend); Player vs. Player 95 (165 Arena, 14801 AV, 14802 AB, 14803 EotS, 14804 WSG, 14881 SotA, 14901 Wintergrasp, 15003 IoC); Dungeons and Raids 168 (14808, 14805, 14806, 14921, 14922, 14923, 14961, 14962, 15001, 15002, 15041, 15042); Professions 169 (170 Cooking, 171 Fishing, 172 First Aid); Reputation 201 (14864, 14865, 14866); World Events 155 (160, 187, 159, 163, 161, 162, 158, 14981, 156, 14941); Feats of Strength 81. Full list saved locally in aikka-onyxia-achievement-categories.json.
- Whether a top-level category POST already returns its subcategories' entries is not yet established (category 92 has no subcategories). The first test on a category with subcategories decides whether a full export needs about 9 or about 50 achievement requests.
- Statistics: POST with the same category field works (category=130 returned a JSON {"content": html} with a Description/Value table, about 2 KB; values such as "Talent tree respecs 8"). The statistics sidebar has about 30 category and subcategory ids, so a full statistics export is about 10 to 30 requests per character.
- Revised request estimate per character: roughly 30 to 90 requests depending on subcategory behaviour. Needs throttling, caching and resumability; a full export of four characters should be an explicit, user-triggered, slow run.


### Finding: summary-captures-other-characters-2026-10-24

Status: verified by user-run enrich_summary_diagnostic on the three batch-2 captures (client_warnings: 0 for all).

- Every enchant and nonzero gem code on Bezduse@Onyxia, Bezduse@Icecrown and Aikka@Icecrown resolved from SpellItemEnchantment.dbc. Aikka@Icecrown passed the inventory-type slot check for all 17 items (Main Hand one-hand, Off Hand shield, Ranged relic).
- Bug found and fixed: the Bezduse captures showed no inferred slot names (slot check = None). Cause: Warmane labels the empty off-hand slot "Off-Hand", the layout table expects "Off Hand", so the anchor check failed and inference was disabled. Label comparison now ignores case and hyphen/space differences (summary_parser._labels_match, unit tested). Re-verification of the Bezduse captures is pending (user-run).
- Layout facts: a two-hand weapon occupies Main Hand and leaves Off Hand empty (empty slot carries data-tooltip="Off-Hand"); a death knight sigil sits in the Ranged slot (relic inventory type).
- Same slot-label strictness was the only blocker; item IDs and enchant/gem payloads parsed identically across Priest, Death Knight and Paladin.


### Finding: achievements-subcategories-are-separate-2026-10-24

Status: verified by 3 further live requests (achievements page, POST category=96, POST category=14861; 12 s apart; user's Chrome; no blocks). Total live requests this session: 16.

- Subcategory ids are posted in the same field (the page calls loadAchievements(subcategoryId) with a POST of category=<id>).
- A top-level category response does NOT contain its subcategories: category 96 (Quests) returned 19 entries (14 locked); subcategory 14861 (Quests, Classic) returned 5 entries (all locked). The page header says Quests has 49 achievements, so the remainder lives in the other subcategories.
- Consequence: a full achievement export needs one POST per top-level category plus one per subcategory: 9 top-level plus about 42 subcategories, so roughly 50 achievement requests per character.
- Revised total per character: about 1 JSON, 1 summary, 1 to 2 talents, 1 achievements page, about 50 achievement POSTs, 1 statistics page, up to about 30 statistics POSTs, so up to about 85 requests. At a polite pace of one request every 10 to 15 seconds this is 15 to 20 minutes per character. A full export must be explicit, throttled, cached and resumable, and never run on a schedule without a user action.
- Open: whether the header total is the sum of the top-level and subcategory entries (needs a second subcategory sample to confirm; not required for feasibility).


### Finding: plain-http-works-2026-10-24

Status: verified by user-run requests from the project's own Python (urllib, browser-like User-Agent and Accept-Language headers) and Windows curl.

- JSON endpoint: Python 200 (1601 bytes) and curl 200, identical to the browser response.
- HTML summary page: 200, 31607 bytes, 17 item links (matches the browser capture). Talents page: 200, 72135 bytes, 6 data-spec markers. Achievements category POST (category=92 with X-Requested-With, Referer, Origin headers): 200, 30346 bytes, identical size to the browser response, JSON with a content key.
- Therefore a plain HTTP client works for JSON, HTML and POST requests when it sends a browser-like User-Agent. The earlier 403 error 1010 came from default client headers. No cookies or browser were needed for these requests.
- Windows PowerShell 5.1 under the reviewer sandbox account failed with a closed connection (environment issue, not a site block); the exporter should use Python, not PowerShell, for requests.
- Approximate total live requests this session: 25, no rate limit hit. Pacing used: 12 to 15 s between requests. A conservative default of at least 10 s with jitter is kept for the exporter.
- Probe script: scripts/probe_plain_http.py (3 requests, 15 s apart).


### Finding: first-live-snapshot-2026-10-24

Status: verified by a user-run snapshot of Aikka@Onyxia (2 live HTML requests plus a fresh JSON cache entry; no blocks).

- The existing HTML summary and talents parsers, built on rendered-DOM captures, accept the raw HTML a plain HTTP client receives. Both sections validated without changes.
- Offline consistency: layout anchors_consistent, 17 equipped items with slot_check ok for all, 0 client warnings; item IDs equal the JSON endpoint's; talents 2 specs x 3 trees, 0 warnings; reported tree totals (57/14/0 and 18/53/0) equal the JSON point splits. The snapshot file was about 245 KB.
- Tool: python -m warmane_exporter.snapshot_report FILE.json repeats these cross-checks offline for any saved snapshot.
