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
