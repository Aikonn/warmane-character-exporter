# Development Status (Checkpoint Handoff)

## Scope status
- **Current milestone:** **Milestone 0** (source feasibility investigation) — **incomplete**.
- Requirements baseline remains in [specification.md](./specification.md) and source-tracking details in [data-sources.md](./data-sources.md).

## Implemented at this checkpoint
- Minimal retrieval probe scaffold (offline plan + controlled live modes) in [src/warmane_exporter/](../src/warmane_exporter).
- Offline rendered-DOM summary diagnostic parser (local file input only) in [summary_parser.py](../src/warmane_exporter/summary_parser.py) and [summary_diagnostic.py](../src/warmane_exporter/summary_diagnostic.py).
- Offline rendered-DOM talents diagnostic parser in [talents_parser.py](../src/warmane_exporter/talents_parser.py) with full spec extraction, glyph associations, malformed-rank preservation, and tree-total validation.
- Equipment slot layout inference against standard WotLK paperdoll order in [summary_parser.py](../src/warmane_exporter/summary_parser.py) with validation status, anchor consistency checking, and per-slot inference metadata.
- Fixture-based offline tests (including synthetic 1010/1015 access fixtures, synthetic summary structure, synthetic talents page, and synthetic layout scenarios) under [tests/](../tests).

## Exact local commands (use `.venv` Python explicitly)
```powershell
$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m unittest discover -s tests -v
$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m warmane_exporter.summary_diagnostic "local-captures\aikka-onyxia-summary-dom.html"
```

## Latest verified test result

**Current full-suite status (Copilot-reported local run, not independently executed by reviewer):**
- **106 tests passed, 0 failed**
- Composition: summary parser (12 tests) + transport (7 tests) + checkpoint (1 test) + identity (4 tests) + retry (3 tests) + talents parser (24 tests) + definition diagnostic (55 tests)

**Historical test counts (superseded):**
- 41 tests: talents-parser checkpoint (Local Copilot agent run)
- 55 tests: definition-diagnostic isolated run (before full-suite integration)
- 95 tests: full suite before final ASCII-regex and definition-diagnostic corrections

**Independent Perplexity review (talents parser):**
- Ran uploaded 24 talent-parser tests in isolation: **all 24 passed** ✓
- Verified four acceptance-failure cases now behave correctly:
  1. Talent anchor without `talent-points` div: retained with error marker ✓
  2. Tree without `tree-info` div: `reported_total` null, validation indeterminate ✓
  3. Spec tab without matching container: warning generated ✓
  4. Glyph divs with reordered CSS classes: parse correctly ✓
- Did not re-run: full suite, both real captures' allocations, or independent verification of matched tree totals

**Offline talents-parser increment status:** Accepted after bounded review. Fixes to edge cases verified; no regressions.

**Rank-discovery mechanism candidate identified:**
- Two controlled live Copilot HTTP requests to cavernoftime.com spell API (exact requests: `/spell=14748&power=true` and `/spell=14748`)
- GET `/spell=14748&power=true` returned HTTP 200: Rank 1 tooltip definition ("Improved Power Word: Shield", 5% effect)
- GET `/spell=14748` (no-redirect handler) returned HTTP 200: normal definition page with Rank 1 effect and related-spell data identifying Rank 2=spell_id 14768 and Rank 3=spell_id 14769
- Unranked related entry (spell_id 24191) present in data; not all "See Also" entries are rank mappings
- **Mechanism candidate:** Extract spell ID from talent href → fetch Cavernoftime spell page → parse related-spell entries for rank IDs → fetch each rank's spell page for definition
- **Verified for:** Only one talent (14748 with 1/3 selected); higher ranks not yet fetched
- **Requires:** Verification across additional talents, glyph mechanism discovery, ruleset compatibility check, source access/reuse terms review
- See [data-sources.md Finding: cavernoftime-spell-rank-discovery-2026-10-24](./data-sources.md#findings-log)

**Enchantment and gem parameter isolation (Cavernoftime):**
- Five controlled item GETs to https://wotlk.cavernoftime.com/item=51178 with parameter variations.
- Base (no params): Meta/Blue socket labels (q0 CSS).
- Ench=3820 isolated: Adds "+30 Spell Power and 20 Critical strike rating" effect text; socket labels unchanged.
- Gems=3627:3879 isolated: Replaces socket labels with two gem-effect descriptions ("+21 Intellect...mana", "+10 All Stats"); socket labels removed.
- Combined: Union of isolated effects.
- **Finding:** Enchantment code 3820 effect text resolved and matches EvoWoW manual screenshot evidence (see below).
- **Limitation:** Gem codes produce joint effect text; per-gem mapping not isolated. Socket bonus activation state unknown. Bonus CSS class (q0→q2) reported earlier but not confirmed in final retained-file verification.
- See [data-sources.md Finding: cavernoftime-enchantment-gem-parameter-isolation-2026-10-24](./data-sources.md#findings-log).

**EvoWoW enchantment lookup verification:**
- One Copilot automated GET to https://wotlk.evowow.com/?enchantment=3820: HTTP 403 Forbidden (access blocked).
- User-provided browser screenshot shows successful manual access: Enchantment ID 3820 explicit; effect "+30 Spell Power and 20 Critical strike rating" matches Cavernoftime output.
- **Finding:** Enchantment ID namespace established via manual evidence; automated access currently blocked. EvoWoW ?enchantment= parameter historically used for both equipment enchantments and gem codes (historical main.py evidence), but gem-code namespace not yet verified.
- **Limitation:** Automated access blocked. Gem code 3627 lookup not attempted. Related-item names do not establish unique item IDs. Source reuse terms unchecked.
- See [data-sources.md Finding: evowow-enchantment-3820-manual-verification-2026-10-24](./data-sources.md#findings-log).

**Equipment slot layout inference (offline):**
- Implemented pure Python function `_validate_and_infer_layout()` in [summary_parser.py](../src/warmane_exporter/summary_parser.py) that validates equipment layout against standard WotLK paperdoll slot order.
- **Layout schema:** Left column (8 slots): Head, Neck, Shoulder, Back, Chest, Shirt, Tabard, Wrist. Right column (8 slots): Hands, Waist, Legs, Feet, Finger 1/2, Trinket 1/2. Bottom row (3 slots): Main Hand, Off Hand, Ranged.
- **Validation status:** "anchors_consistent" only when observed counts match expected (8/8/3 + unknown=0), at least one slot has explicit data-tooltip label, and all explicit labels match expected positions; otherwise "unverified" with issues logged. Bounds-checking prevents out-of-range anchor positions from raising exceptions; out-of-range anchors are recorded with expected_name=null, match=false, and issue noted.
- **Per-slot inference:** Each slot contains `layout_inference` dict with `inferred_slot_name` (name or null), `basis`, `status`, and optional `note` field for Finger/Trinket numbering clarification.
- **Icon stem capture:** Item slots now extract image filename stem (e.g., "inv_helmet_156" from `<img src="...inv_helmet_156.jpg">`) as raw evidence; null if no `<img>` tag present (no error).
- **Test coverage:** 10 new tests covering consistent layout with anchors, count mismatches, anchor mismatches, no anchors, explicit names preservation, Finger/Trinket notes, icon stem capture, out-of-range anchors (no exception), and unknown-group slots. Full suite: 106 tests pass.
- **Evidence from Aikka / Onyxia:** Captured 19 equipped items with consistent 8/8/3 layout, Shirt (left_6) and Tabard (left_7) explicit anchors matching expected positions, anchors_consistent status, all 19 slots inferred with icon stems captured (e.g., inv_helmet_156, inv_belt_52, spell_ice_rune).
- **Limitation:** Layout inference is positional only; does not verify against item inventory-type field definitions or cross-reference with item API definitions. Inference valid only when validators confirm consistency; when unverified, all inferred_slot_name fields are null.
- See diagnostic output in [Equipment layout inference results](#equipment-layout-inference-results) below.

**Milestone 0 status:** **Incomplete** — equipment slot layout now inferred offline; item-to-definition linkage, gem codes, bonus activation, and active spec remain unresolved. Layout validation scaffold provides foundation for future inventory-type verification.

## Equipment layout inference results

**Offline layout-inference test suite (Copilot-reported local run):**
- Executed full test discovery: **106 tests passed, 0 failed** (96 previous + 10 new layout-inference tests); `tests/test_summary_parser.py`: 12 tests, OK
- Layout inference tests: 10 scenarios covering all validation branches (consistent with anchors, count mismatch, anchor mismatch, no anchors, explicit name preservation, Finger/Trinket notes, icon stem capture, out-of-range anchors, unknown-group slots)
- **Synthetic fixtures tested:**
  - `layout-consistent-with-anchors.html`: 8/8/3 layout with Shirt/Tabard anchors → status="anchors_consistent", all 19 inferred names populated
  - `layout-count-mismatch.html`: 7 left slots (mismatch) → status="unverified", all inferred names null
  - `layout-anchor-mismatch.html`: Shirt at left_5 (expect left_6) → status="unverified", issue recorded
  - `layout-no-anchors.html`: 8/8/3 but no explicit labels → status="unverified", issue recorded
  - `layout-no-img.html`: Consistent layout with alternating missing `<img>` tags → icon_stem captured where present, null where missing, no error

**Real-world evidence (Aikka / Onyxia summary capture):**
```
layout_validation: {
  status: "anchors_consistent",
  expected_counts: {left: 8, right: 8, bottom: 3, unknown: 0},
  observed_counts: {left: 8, right: 8, bottom: 3, unknown: 0},
  anchors_checked: [
    {slot_key: "left_6", explicit_label: "Shirt", expected_name: "Shirt", match: true},
    {slot_key: "left_7", explicit_label: "Tabard", expected_name: "Tabard", match: true}
  ],
  issues: null
}

Inferred 19-slot table:
  left_1:    Head        (51178 with icon_stem: inv_helmet_156)
  left_2:    Neck        (50809 with icon_stem: item_icecrownnecklacea)
  left_3:    Shoulder    (50449 with icon_stem: inv_shoulder_119)
  left_4:    Back        (47256 with icon_stem: inv_misc_cape_18)
  left_5:    Chest       (48063 with icon_stem: inv_chest_cloth_73)
  left_6:    Shirt       (empty, icon_stem: null)
  left_7:    Tabard      (empty, icon_stem: null)
  left_8:    Wrist       (47588 with icon_stem: inv_bracer_24b)
  right_1:   Hands       (48067 with icon_stem: inv_gauntlets_55)
  right_2:   Waist       (48054 with icon_stem: inv_belt_52)
  right_3:   Legs        (51262 with icon_stem: inv_pants_cloth_35)
  right_4:   Feet        (51380 with icon_stem: inv_boots_cloth_27)
  right_5:   Finger 1    (50400 with icon_stem: inv_jewelry_ring_85)
  right_6:   Finger 2    (49990 with icon_stem: inv_jewelry_ring_ahnqiraj_05)
  right_7:   Trinket 1   (50358 with icon_stem: inv_misc_ammo_gunpowder_05)
  right_8:   Trinket 2   (45929 with icon_stem: spell_ice_rune)
  bottom_1:  Main Hand   (48039 with icon_stem: inv_mace_103)
  bottom_2:  Off Hand    (45314 with icon_stem: inv_offhand_ulduarraid_d_03)
  bottom_3:  Ranged      (45713 with icon_stem: inv_wand_28)
```

## Access finding (automated retrieval)
- One approved automated request to `Aikka / Onyxia / summary` returned:
  - HTTP **403**
  - body: `error code: 1010`
- Recorded as an **access-block finding**, not character-data absence.
- Automated access for normal retrieval remains unresolved (see [data-sources.md](./data-sources.md)).

## Manual rendered-DOM findings (offline)

### Summary page
- Parsed from local rendered-DOM capture:
  - identity + guild
  - character-sheet displayed sections/values/units
  - equipped item refs with raw `item` / `ench` / `gems` namespaces
  - explicit empty slots (e.g., Shirt/Tabard)
  - two specialization summary point distributions
  - navigation links to uncaptured sections
  - recent achievements as **partial** activity list

### Talents page
- Offline parsed from two local rendered-DOM talent-page captures (spec1 + spec2).
- Both captures substantively identical when normalized.
- **Spec definitions:** Specs identified via `data-spec` DOM attributes (Spec 0=Discipline, Spec 1=Holy). Both specs extracted regardless of visibility state (hidden spec 1 correctly parsed).
- **Talent trees:** Three trees per spec (Discipline/Holy/Shadow) with individual talent nodes, selected ranks as text (e.g., "5/5"), source spell IDs in `href` attributes.
- **Talent point allocations (verified by full (spell_id, points_spent, points_max) tuples):**
  - Spec 0 (Discipline build): 57 points in Discipline tree, 14 in Holy, 0 in Shadow
  - Spec 1 (Holy build): 18 points in Discipline tree, 53 in Holy, 0 in Shadow
  - Both specs' available talent nodes are identical; selected allocations differ per build
- **Tree totals:** Parser compares sum(points_spent) to reported_total. **ALL trees MATCH perfectly** (initial regex failed to capture 4 talents with bare `class="talent-points"`; corrected):
  - Spec 0: Discipline 57/57 ✓, Holy 14/14 ✓, Shadow 0/0 ✓
  - Spec 1: Discipline 18/18 ✓, Holy 53/53 ✓, Shadow 0/0 ✓
- **Glyphs:** Spec 0: 3 major + 2 minor; Spec 1: 3 major + 3 minor. Extracted with category association and spec linkage.
- **Active spec:** NOT determinable from rendered DOM. Tab UI selection state and display visibility do not indicate in-game active spec.
- **Unresolved:** Talent effect text (selected-rank bonuses), glyph effect descriptions, and external definition resolution remain outstanding.

### Talent and glyph definitions (Cavernoftime + manual verification)
- Automated Cavernoftime probes (checkpoint) successfully fetched /spell=14748 and /spell=14748&power=true; Rank 1 definition retrieved and related-spell rank-ID mappings (14768→Rank 2, 14769→Rank 3) identified.
- **Manual verification (user screenshots + Perplexity visual inspection):**
  - Spell 14769 (Improved Power Word: Shield, Rank 3): Effect = "Increases the damage absorbed by your Power Word: Shield by 15%." ✓
  - Spell 55679 (Glyph of Flash Heal): Effect = "Reduces the mana cost of your Flash Heal by 10%." ✓
- **Automated access attempt (this checkpoint):** Two sequential GETs to /spell=14769 and /spell=55679&power=true with default urllib behavior (allowed redirects; 30-second timeout; 3-second inter-request delay).
  - Result: Both HTTP 403 Forbidden. No response content.
  - User-Agent header was "Python-urllib/Investigation" (differed from checkpoint probes).
  - Cause unresolved (IP blocking, session state, header requirements, rate limiting unknown). Second request should not have run after first access denial.
  - Earlier successful fetches remain valid; source automation reliability remains uncertain.
- **Finding:** Rank 3 talent effect and one glyph effect manually verified. Rank 2 effect, general talent/glyph coverage, automated reliability, ruleset compatibility, and source terms remain unresolved.
- See [data-sources.md Finding: cavernoftime-spell-rank-discovery-2026-10-24](./data-sources.md#findings-log) and [Finding: cavernoftime-spell-automated-access-denial-2026-10-24](./data-sources.md#findings-log).

### Definition-source diagnostic tool (offline + --live-once)
- **Implemented:** Minimal diagnostic in [src/warmane_exporter/definition_diagnostic.py](../src/warmane_exporter/definition_diagnostic.py) with reusable transport safeguards.
- **Behavior:** 
  - Default (no args): Offline URL validation and planning only; zero network requests.
  - `--live-once` flag: One controlled HTTP GET with zero retries, respects persisted cooldowns, blocks redirects, 131 KiB body cap, 30-second timeout.
- **URL validation:** HTTPS only; approved hosts (wotlk.cavernoftime.com, wotlk.evowow.com); explicit approved path/query forms with strict parameter whitelisting.
  - Spell/item/enchantment IDs: Positive integers only `[1-9][0-9]*` (no zero, no leading zeros).
  - Gem codes: Nonnegative integers with colon separators `[0-9]+(?::[0-9]+)*` (allows zero placeholders).
  - Rejects: Scheme-less URLs, semicolon parameters, non-ASCII digits, control characters, credentials, non-default ports, fragments.
- **Output:** JSON diagnostic with HTTP status, classification, Content-Type, body-truncation flag, and 500-character excerpt from response (same response, never re-fetched).
- **Test coverage:** 55 tests (offline tests + URL validation rejection/acceptance + body-excerpt capping + main() integration mocking):
  - URL validation: 29 tests (schemes, hosts, IDs, gem codes, control characters, zero-ID rejection, semicolon rejection, non-ASCII digits)
  - Body excerpt: 4 tests (short/exact-limit/exceeds/empty)
  - Offline subprocess: 2 tests (zero HTTP calls in default mode, validation error handling)
  - Main integration: 5 tests (offline zero-calls, live-once success with exact excerpt matching and call count, rate-limit/transient no-retry, cooldown blocking)
  - Results: **55 tests passed, exit code 0** (final Copilot-reported result after ASCII-regex and test correction).
  - Earlier full-suite result: **95 tests passed** (before final small corrections).
- **Implementation note:** One earlier integration test unintentionally attempted live network access; removed and replaced with mocked HTTP coverage to maintain offline-first design.
- **Review:** Perplexity reviewed initial uploaded [definition_diagnostic.py](../src/warmane_exporter/definition_diagnostic.py) and [test_definition_diagnostic.py](../tests/test_definition_diagnostic.py); final ASCII-regex pattern updates and test enhancements were Copilot-reported, not independently executed by reviewer.
- **Status:** Accepted after review. Reusable transport scaffold for future definition-source probes (spell, item, enchantment, gem) now available.

### Limitations
- Rendered-DOM captures may include JavaScript-generated elements or cached tooltip snippets.
- Captures do not prove full progression/achievement/statistics coverage.
- Recent achievements are partial activity list, not complete progression evidence.
- **Automated retrieval reliability unresolved:** Cavernoftime HTTP 403 responses in this session; earlier checkpoint probes succeeded. Cause unknown. Diagnostic tool available for future investigation but safeguards do not resolve source-access blocking.

## Local capture files (kept local, git-ignored)
- `local-captures\aikka-onyxia-summary-dom.html`
- `local-captures\aikka-onyxia-talents-spec1-dom.html`
- `local-captures\aikka-onyxia-talents-spec2-dom.html`

## Open gaps before Milestone 0 completion
- Reliable automated access to Warmane character pages.
- Equipment-slot identity verification: layout inference is anchors_consistent for Aikka/Onyxia, but not verified against item inventory-type definitions (requires approved definition-source access).
- Talent effect text and glyph effect descriptions (not present in current captures; future investigation needed).
- External definition resolution/mapping (items, enchants, gems, talents, glyphs).
- Progression coverage beyond summary recent-activity snippets.

## Next task (if approved)

**Equipped-item code inventory added to data-sources.md (offline). Live verification of candidate requests NOT approved.**

See [data-sources.md § 13a. Equipped-item code inventory — Aikka / Onyxia](./data-sources.md#13a-equipped-item-code-inventory--aikka--onyxia-offline-2026-10-24) for:
- 19-row table (slot_key, inferred_slot_name, item_id, raw ench/gems, status fields, evidence anchors)
- 31 candidate URLs (17 item definitions, 9 unresolved enchantment codes (3820 already resolved), 5 gem codes)
- All URLs passed offline validation; no network requests executed
- Limitations: Layout inference only, gem codes produce joint effect text, socket bonus state unknown

**Remaining Milestone 0 gaps (see [Open gaps before Milestone 0 completion](#open-gaps-before-milestone-0-completion)):**
1. Reliable automated access to Warmane character pages.
2. Equipment-slot identity verification (requires item inventory-type definitions).
3. Talent/glyph effect text retrieval.
4. External definition resolution/mapping.
5. Progression coverage beyond summary activity snippets.

**Proposed next bounded task (not approved):** bounded live check of a small subset of the 31 candidate URLs via definition_diagnostic --live-once, pending source-terms review.

**Resolved items (do not revisit):**
- ~~Talent tree-total mismatches~~ → Parser defects, now fixed. All six trees in both real captures match their reported totals.

## Approval boundary
- **No further live requests are currently approved.**
- Parser refinements must await explicit scope approval in next session.
- Reviewer workflow and handoff rules: see reviewer-instructions.md.

## Current work: offline client data (updated 2026-10-24)
- Terms review result: EvoWoW robots.txt does not disallow item/spell/enchantment pages, but no terms found; Cavernoftime has no robots.txt and "All rights reserved". Both reject non-browser clients (403 / IP block). Automated live access is not established as permitted. AoWoW (Sarjuuk/aowow) is self-hosted, no licence, non-commercial note: not used.
- Decision: read definitions offline from the local 3.3.5a client DBC files inside the MPQ archives. Client path comes from warmane-character-exporter.config (machine-aware, template committed) or --data-dir.
- Committed: machine-aware config loader (config.py, template, tests).
- Copilot's first MPQ/DBC attempt was rejected (wrong header layout and crypto, circular tests, /tmp temp files, lookup by row position). Rewritten by the reviewer: mpq_reader.py (real MPQ layout, known-answer tests for crypt table and table keys, zlib/bzip2, sector and single-unit files, encryption, archive priority), dbc_parser.py (lazy WDBC from bytes, lookup by key in field 0), dbc_diagnostic.py (uses config or --data-dir, --id NAME=KEY, no temp files).
- Test status: 10 new tests pass in the reviewer sandbox on Linux (reviewer-run). Not yet run on the project venv; the reviewer sandbox cannot execute the venv Python.
- Next: user runs on the real client:
  python -m warmane_exporter.dbc_diagnostic --data-dir "E:\Games\World of Warcraft 3.3.5a\Data" --id SpellItemEnchantment.dbc=3820 --id Spell.dbc=14769 --id Spell.dbc=55679 --id Item.dbc=51178
  Then compare the strings against manually verified text, and map field indexes (3.3.5a DBC layouts) in a follow-up.
- Pending: add the terms-review findings and the DBC plan to data-sources.md.
- Rules: see Autonomy in reviewer-instructions.md (push and live data-site requests still need user approval).

## Update: offline definitions verified (2026-10-24)
- Verified on the user's client: enchant 3820, gem codes 3627 and 3879 (enchantment IDs), spells 14769 and 55679, item 51178 (head). Gem codes resolve offline, so live definition requests are no longer needed for enchants, gems, spells and glyph spells.
- Local machine config created for HALL10K (git-ignored). Full suite: 126 tests passed (user-run).
- Open: item names and socket bonuses are not in DBCs; rank mapping for talents (rank N spell IDs) may be resolvable from Spell.dbc/Talent.dbc offline and should be the next check; wire definitions into the probe output.
- Talent rank mapping verified offline (talent 343 via 14748/14768/14769). Live Cavernoftime rank discovery is superseded. Next: glyph lookup (glyph spell to GlyphProperties) and wiring definitions into the talents parser output.

## Update: talents and glyphs verified offline (2026-10-24)
- enrich_diagnostic on the real Aikka capture: all talents and glyphs resolved, 0 client warnings, glyph slot types agree. Full suite: 128 tests passed (user-run).
- Open for Milestone 0: equipment item names (not in DBCs), socket bonuses, tooltip value rendering ($s1 tokens), achievements/statistics enumeration, field-availability matrix, ruleset compatibility check, request counts.

## Update: equipment verified offline (2026-10-24)
- enrich_summary_diagnostic on the real Aikka summary capture: 17/17 items slot-consistent, all enchants and gems resolved, 0 warnings. Full suite: 129 tests passed (user-run).
- Offline client data now covers talents, glyphs, spells, enchants, gems and item slot types. Remaining Milestone 0 gaps are Warmane-side or need other sources: item names/quality/sockets, achievements and statistics enumeration, field-availability matrix across both realms and four debug characters, ruleset compatibility, request counts. Live Warmane requests need user approval.


## Update: Milestone 0 matrix written (2026-10-24)

- Live evidence so far: 7 requests through the user's Chrome (4 JSON summary, achievements page, one achievements POST, statistics page). No blocks.
- data-sources.md section 16 holds the field matrix, access finding, request-cost estimate and checklist status.
- Proposed next: second small live batch (under 10 requests) for the remaining HTML pages and ids, then sanitized fixtures and closing Milestone 0.

## Update: real-response fixtures (2026-10-24)

- tests/fixtures/real/ holds small live samples (two JSON summary responses, a trimmed achievements category, one statistics category) with a README on provenance. tests/test_real_fixtures.py checks their shape.
- Milestone 0 evidence is now complete except a final review pass: remaining items are the review document (what is verified, what is absent, proposed scope changes) and deciding how HTML pages are fetched, since plain scripted HTTP is blocked.

## Update: Milestone 1 started (2026-10-24)

- Milestone 0 evidence is complete (docs/milestone-0-review.md). Fetch strategy: plain HTTP from Python with one fixed browser-compatible header set (no rotation).
- http_client.py: DEFAULT_HEADERS and post_form (XMLHttpRequest-style form POST). transport.py: optional form and referer; the checkpoint key for POST includes the form fields, so resume and duplicate suppression work per category.
- warmane_api.py: URL builder and validating parser for the JSON summary, covered by the real fixtures.
- Next: response cache (SQLite index plus raw files, freshness 15 minutes for character data), then an end-to-end "fetch JSON summary" CLI command using cache and throttling, then the HTML summary and talents fetch.

## Update: cache and fetch command (2026-10-24)

- cache.py: SQLite response cache (key, source, body, fetched_at, sha256, 2 MB body limit). Only validated bodies are stored.
- fetch.py: python -m warmane_exporter.fetch NAME REALM [--refresh] [--offline] [--allow-stale] [--cache-dir DIR]. Fresh cache (15 minutes) is used without a request; error pages and invalid JSON never replace valid cache; stale data is used only with --allow-stale or --offline and is labeled stale-cache. At most one live request per run. Cache and transport state live in git-ignored .warmane-cache/.
- RequestOrchestrator.skip_completed=False for the fetch command, since the cache (not the probe checkpoint) decides whether a request is needed; cooldowns still persist.
- Next: HTML summary fetch (enchants, gems, slots) and talents fetch using the same cache, then combine JSON + HTML + client definitions into the first character snapshot.

## Update: snapshot command (2026-10-24)

- snapshot.py: python -m warmane_exporter.snapshot NAME REALM [--refresh] [--offline] [--allow-stale] [--no-client]. Fetches the JSON summary, HTML summary and talents page (at most 3 live requests, 10 s apart, none when cached), validates each with its parser, optionally enriches from the local client files, and writes .warmane-cache/snapshots/<name>-<realm>-<time>.json (schema character-snapshot/0). Each section reports status, origin and observation time and fails independently; rejected bodies are kept in .warmane-cache/rejected/ for debugging and never enter the cache.
- Untested assumption being checked by the first live run: the HTML parsers were built on rendered-DOM captures; raw HTTP HTML may differ (for example if the page builds parts with scripts). A rejected section shows exactly where.


## Update: snapshot validation on all four characters (2026-10-24)

- Live snapshots of Aikka and Bezduse on Onyxia and Icecrown (3 requests each, 10 s apart, no rate limit, no errors) all pass snapshot_report: raw-HTTP HTML parses with the existing parsers, 16-17 equipped items with slot checks ok, item ids equal the JSON endpoint, 2 talent specs each with 0 warnings and point totals equal to the JSON splits. Death Knight (16 items, sigil in Ranged) and Icecrown pages need no parser changes.
- Milestone 1 is functionally complete (transport, cache, fetch, snapshot). Next: Markdown and JSON character report from a snapshot (Milestone 2), then achievements/statistics fetch.



## Update: spell description rendering (2026-10-24)

- spell_text.py renders Spell.dbc description templates offline (\$s, \$m, \$M, \$d, \$a, \$t, \$o, \$x, \$h, \$n, \$u, \$e, other-spell references, \$/N; and \$*N; prefixes, arithmetic in \$\{...\}, \$l plurals). Spell.dbc field offsets used: proc chance 35, charges 36, duration index 40, stack 49, die sides 74-76, base points 80-82, radius index 92-94, amplitude 98-100, multiple value 101-103, chain targets 104-106; SpellDuration.dbc and SpellRadius.dbc (4 fields each) give duration in ms and radius in yards.
- Verified on real client values: Glyph of Frost Strike 8 Runic Power, Horn of Winter 1 min, Pestilence 5 yards, Vampiric Blood 5 sec, Flash Heal 10 percent, Obliterate 25 percent. All glyphs of the four characters render without markers.
- Not resolvable offline and flagged unresolved (never guessed): conditionals such as \$?s123[a][b], player-stat variables, \$<name> references (for example Lifebloom).
- Snapshots now carry description_rendered / selected_rank_description_rendered with an _unresolved flag; the report prefers rendered text. python -m warmane_exporter.spell_diagnostic [IDS] prints template and result.
- Reviewer Python (.tools) now runs tests and offline commands; 159 tests pass. Next: achievements and statistics parser from the saved category captures, then a small live fetch plan for your approval.



## Update: achievements and statistics parsing, collector (2026-10-24)

- achievements_parser.py parses category POST responses (achievements: id, title, description, points, icon, earned flag, earned date; statistics: description/value rows). Tested on the real fixtures; on local captures category 92 gives 55 entries (24 earned), 96 gives 19, 14861 gives 5.
- collect.py: python -m warmane_exporter.collect NAME REALM [--limit N] [--dry-run] [--offline] [--refresh] [--interval S]. 52 achievement categories (9 top-level plus subcategories, table in code), one POST each, 24 h cache, resumable, --limit caps live requests per run. Output .warmane-cache/collections/. After a complete run it compares summed earned points with the armory total from the latest snapshot.
- fetch_validated accepts form and referer for POST requests; the cache key includes the form fields.
- Statistics collection is not built yet: the statistics sidebar markup (category and subcategory ids) has not been captured, so a one-request discovery fetch of the statistics page is needed first.



## Update: full achievements export verified (2026-10-24)

- Aikka@Onyxia: all 52 achievement categories collected live through the resumable collector (52 POSTs in 6 runs of at most 9, 10 s apart, 60 s between runs, no errors, no rate limit). Result: 1167 unique achievements, 323 earned, no duplicate ids across categories, and the summed earned points equal the armory total exactly (3355).
- This validates the category table and the parser end to end. The earlier header-count difference in category 92 (54 vs 55 entries) is harmless because points reconcile.
- Next: statistics. discover.py (python -m warmane_exporter.discover NAME REALM statistics) fetches one page and stores the raw HTML so the sidebar category ids can be parsed offline.



## Update: statistics, reputation and mounts discovery (2026-10-24)

- Statistics page (3 live requests total with the two below, no errors): the sidebar lists 10 top-level categories and 23 subcategories (data-category / data-subcategory); the table in collect.py matches it exactly (33 ids). collect.py now takes --section statistics (same POST protocol; whether top-level responses omit subcategory rows is verified on the first live run).
- Reputation page is static HTML, no POST: a flat list of 38 factions for Aikka@Onyxia, each with standing class, name, current / maximum, standing text. reputation_parser.py parses all 38 and cross-checks the standing class against its text; tested on a real 6-faction fixture.
- The mounts URL is /character/NAME/REALM/mounts-and-companions (plain /mounts returned the profile page). Other character views: profile, match-history, achievements, talents, statistics, reputation. discover.py view names updated.



## Update: statistics verified, mounts parser, final export (2026-10-24)

- Aikka@Onyxia statistics: all 33 categories collected live (33 POSTs, no errors): 497 rows, no empty values, no duplicate names. A top-level category response contains only its own rows, so subcategories must be requested separately (same as achievements).
- Mounts and companions page is static HTML (two tabs of journal boxes with item id and npc id). mounts_parser.py parses 8 mounts and 4 companions and fails when the box count and parsed count differ.
- export.py merges the newest snapshot, achievements and statistics collections, reputation and mounts pages into .warmane-cache/exports/<name>-<realm>.json and .md, listing any missing section. First export for Aikka@Onyxia is complete and its achievement points match the armory (3355).
- Per-character cost of a complete export: 3 (snapshot) + 52 achievements + 33 statistics + reputation + mounts = 90 live requests, resumable.



## Update: second full export, Bezduse@Onyxia (2026-10-24)

- Death Knight export complete with about 88 live requests (no errors, no rate limit): 52 achievement categories (203 earned of 1163, points 2180 equal the armory total), 33 statistics categories (497 rows), reputation and mounts pages. The export merges without missing sections.
- Pipeline is now validated on two characters of two classes. Remaining for Milestone 6: Aikka@Icecrown and Bezduse@Icecrown.



## Update: all four characters exported (2026-10-24)

- Aikka@Icecrown (1162 achievements, 97 earned, 1005 points) and Bezduse@Icecrown (173 earned, 1785 points) exported completely: about 88 live requests each, no errors, no rate limit, achievement points equal the armory totals for all four characters (3355, 2180, 1005, 1785). Exports in .warmane-cache/exports/.
- Total live requests for the four full exports: about 350 over roughly 2.5 hours at 10 s spacing. Milestone 6 end-to-end validation is met for the data the armory exposes.
- Known remaining gaps: item quality and socket structure (not in armory summary), active spec, professions skill values look unreliable, item detail pages (optional, about 20 requests per character), single-command orchestration of all steps.



## Update: budget, library, single run command (2026-10-24)

- budget.py: shared daily live-request ledger (.warmane-cache/budget.json), default 500 per day, every real HTTP request counts, BudgetExhausted (a ValueError) stops a run before sending. python -m warmane_exporter.budget shows usage; --set N changes today's limit (owner decision). Default spacing between requests is now 3 s (owner decision) for all commands.
- library.py: local Library of static reference pages (items, gems, enchants...), git-ignored folder library/, one file per page plus index.jsonl (url, time, sha256, version); get_or_fetch fetches only on a miss. Nothing is fetched into it yet; a third-party item source still needs a terms review before any request.
- run.py: python -m warmane_exporter.run NAME REALM or --all runs snapshot, reputation, mounts, achievements, statistics and export in order, stops at the first failing step and resumes from the cache.



## Update: item quality found in the armory page (2026-10-24)

- Correction: item quality is present in the character page markup as the CSS class icon-quality<N> (0 poor to 7 heirloom) on every equipped item; the earlier note that quality was unavailable was wrong. summary_parser now stores quality and quality_name per item and the report shows it. Rebuilt for all four characters from cache with no new requests.
- Still unavailable from the armory: socket structure (the rel gems field always lists three positions, 0 meaning no gem, without telling an empty socket from no socket), active spec, reliable profession skill values.
- GitHub Copilot: the account has Copilot Pro with cloud agent and CLI enabled, but the reviewer's GitHub connection rejects agent tasks and has no token for the Copilot CLI, so code generation is not offloaded.


## Update 2026-10-24: professions from the armory page

The JSON summary lists professions unreliably. The summary HTML has two profskills blocks (professions and secondary skills) with current and maximum skill. summary_parser now parses both and the report prefers them. Verified on all four characters.


## Update 2026-10-24: static item, gem and enchant data

No third-party definition site is needed. Enchant and gem texts come from the client SpellItemEnchantment.dbc, spells from Spell.dbc, and item names from the armory JSON summary, which is cached in the Library and SQLite cache. Socket structure and the active spec remain unavailable from any source we use. Next: README and handoff polish.



## Update: AzerothCore item data, first batch of client-independent definitions (2026-10-24)

- Source: github.com/azerothcore/database-wotlk (AGPL-3.0), sql/base/item_template.sql, 38610 items, one 14 MB download. Note: this repository was last updated in January 2017, so it is a frozen 3.3.5a dump, not the current AzerothCore tree. Its spell_dbc.sql holds only AzerothCore custom spells, not the full Spell.dbc, so it is no source for spell, talent or glyph text.
- acore_items.py converts the dump into library/acore/items.db (SQLite, 2 s); acore_cli.py has `fetch` (one request, skipped when already local) and `verify` (local files only).
- Verification against known Warmane data (armory JSON summaries of Aikka@Onyxia and Bezduse@Icecrown): 33 of 33 equipped item names match exactly. `verify` also checks item quality from the page markup of every snapshot in .warmane-cache/ and reports any difference; run it on the PC after `fetch`.
- Gives, without the client: item name, quality, slot, item level, stats, socket colours and socket bonus enchant id (this closes the socket structure gap).
- Still needs the client or another source: texts of enchants, gems and socket bonuses (SpellItemEnchantment ids are not in item_template), and spell, talent and glyph descriptions. Warmane item tooltips are the planned source for the enchant and gem texts.
- Next batches: (2) swappable definition source (client or local cache) wired into enrichment and report, with socket structure shown; (3) Warmane item tooltips into the Library, plus a startup check comparing client and online values.


## Update: swappable definition source (2026-10-24)

- definitions.py: one Definitions object over two optional sources, the game client and the local AzerothCore item database (library/acore/items.db). Item facts prefer the client, then AzerothCore; texts (enchant, gem, spell, talent, glyph) come from the client only until the tooltip source exists. Unknown values stay unresolved.
- snapshot.py loads both (the client is now optional; a missing client no longer disables item enrichment) and prints which sources are active.
- Enrichment adds client.acore per equipped item: name, quality, item level, stats, socket colours, socket bonus enchant id, filled and empty socket counts. Gems beyond the listed sockets produce a warning (extra sockets such as a belt buckle). The report marks empty sockets.
- 192 tests pass. Next: batch 3, Warmane item tooltips into the Library (needs a live probe on the PC, which the cloud session cannot reliably do) and the client-versus-online comparison.


## Update: verified on the PC (2026-10-24)

- acore_cli fetch on the PC: 38610 items. acore_cli verify over 76 local JSON files: 330 item observations, 61 unique items, 0 missing, 0 differences (names from the armory JSON summaries and quality from the page markup). 192 tests pass on Windows; Definitions.close() added so the SQLite file is released (Windows file lock in tests).



## Update: client-independent definitions export (2026-10-24)

- `python -m warmane_exporter.definition_export` writes library/definitions/client-export.json from the client: 2656 enchant/gem texts, 892 talents, 362 glyphs, 2667 spells (rendered descriptions; 135 keep unresolved template parts, 0 render errors). Run on the HD client on the PC; 197 tests pass.
- file_definitions.py reads that file; Definitions uses text sources in order client, export file, and item facts from client then AzerothCore. With the export file and library/acore/items.db present, the exporter no longer needs the game client.
- Not verified: whether the HD client texts equal what Warmane serves (no online source reviewed). Backlog: PvE report profile, direct URL command, export comparison over time.


## Update: PvE report as one HTML file (2026-10-24)

- pve_report.py writes .warmane-cache/exports/<name>-<realm>-pve.html next to the Markdown export (export and run create it automatically; `python -m warmane_exporter.pve_report NAME REALM` rebuilds it offline). One self-contained file: inline CSS, plain tables, no scripts, no external files, all armory text HTML-escaped; also suitable to attach to an AI chat.
- Sections: header, equipment (item level, base stats, enchant, gems, empty sockets), talents and glyphs per specialization with rendered effect text, professions, bosses killed per instance and mode, per-boss kill tables (10/25, normal/heroic; instances split over several categories, such as Vault of Archavon, are merged), entered/completed counters, deaths in raids, dungeon and raid achievements (earned with date, not earned with requirement), emblems, reputation, mounts.
- Decision: comparing exports over time is out of scope. The goal is the character as it is now.
- Known limits: armory difficulty columns sometimes repeat the same number (noted in the report); the active specialization is unknown; item level, stats and sockets come from the 2017 AzerothCore dump, not from Warmane. Verified on the PC with the cached Aikka and Bezduse characters (201 tests pass).


## Update: PvE report refocused on WotLK raiding (2026-10-24)

- Open by default: equipment, talents (per-spec sections collapsed), WotLK raid boss-kill tables (one collapsible table per raid, open), WotLK raid achievements (categories collapsed). Collapsed by default and placed last: WotLK dungeons, Burning Crusade and Classic, unmatched statistics, entered/completed, deaths, and the dungeon/Classic/TBC achievements.
- Removed the "bosses killed per instance and mode" overview table.
- Red warning box: some armory kill counts are known to be wrong. A heroic count equal to the normal count of the same raid size is marked with * (computed automatically; the warning states how many cells were marked).


## Update: PvE report, gems, GearScore, layout (2026-10-24)

- Gems: one gem per line as "+23 Spell Power (epic red)" (quality from AzerothCore gem items, colour from GemProperties.dbc, now part of the definitions export: re-run definition_export once). Empty sockets show "<no gem>". On the belt, the gem beyond the belt's own sockets is shown in the Enchant column as "Belt buckle: ...".
- GearScore (gearscore.py): formula of the GearScoreLite family (TacoTip version, https://github.com/anzz1/TacoTip/blob/master/gearscore.lua): per item floor(((ilvl - A) / B) x slot weight x 1.8618), sum over all items except shirt and tabard, hunter and Titan's Grip adjustments, no penalty for missing enchants. Shown with the average item level and per item. Real check: Aikka@Onyxia item level 249, GearScore 5546 (item levels from AzerothCore).
- "Other dungeon and raid statistics" is one collapsed block placed before the achievements; the achievement table shows "earned / total" and a rounded percentage.


## Item effects and belt buckle

- Item use / equip / proc effects: spell ids come from AzerothCore item_template (spellid_N, spelltrigger_N); the text is the client's rendered spell description, exported by definition_export. Rebuild the item database (acore_cli fetch does it from the stored dump) and re-run definition_export once to get them.
- Belt: a gem beyond the belt's own sockets is the belt buckle gem; the Enchant column shows "Eternal Belt Buckle" and the gem stays in the Gems column. The armory link carries no enchant for the buckle, so it is inferred from the extra gem.

## Socket bonuses, meta gems, stat totals

- gear_bonuses.py: socket bonus active when every socket holds a gem of fitting colour (extra buckle/blacksmith gems ignored); meta gem active when its SpellItemEnchantmentCondition is met by the gem colours of the whole equipped set (orange = red + yellow etc.). Conditions come from the client export (enchant_conditions, 49 rows). That DBC is packed (64-byte records, header says 31 fields), parsed in client_definitions.parse_conditions.
- Stat totals are parsed from the client's texts (plain '+N Stat' parts only); percent effects, procs and weapon enchants are not counted. Item armor is included, inactive socket bonuses and inactive metas are not.

## Set bonuses

- Not taken from the armory tooltip (it does not evaluate them). Static data: set id of each item from AzerothCore item_template (itemset), set name, piece count and bonus spells with thresholds from ItemSet.dbc (exported into client-export.json as item_sets, 475 sets), bonus text from the client's rendered spell description.
- The report counts equipped items per set id (all difficulty variants of a set share one id) and marks each bonus active when the count reaches its threshold. Inactive set bonuses, socket bonuses and meta gems are gray.

## PvE-only fetch and 1 s spacing
- run.py now fetches only what the PvE report reads: 13 of 52 achievement categories (168 and its children) and 9 of 33 statistic categories (14807, the six instance categories, 125, 130). About 28 live requests instead of about 90. `--full` (run.py and collect.py) fetches everything; cached categories are reused.
- Default spacing between requests is now 1 s (owner decision, one character at a time); it was 3 s.
