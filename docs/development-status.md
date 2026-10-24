# Development Status (Checkpoint Handoff)

## Scope status
- **Current milestone:** **Milestone 0** (source feasibility investigation) — **incomplete**.
- Requirements baseline remains in [specification.md](./specification.md) and source-tracking details in [data-sources.md](./data-sources.md).

## Implemented at this checkpoint
- Minimal retrieval probe scaffold (offline plan + controlled live modes) in [src/warmane_exporter/](../src/warmane_exporter).
- Offline rendered-DOM summary diagnostic parser (local file input only) in [summary_parser.py](../src/warmane_exporter/summary_parser.py) and [summary_diagnostic.py](../src/warmane_exporter/summary_diagnostic.py).
- **NEW:** Offline rendered-DOM talents diagnostic parser in [talents_parser.py](../src/warmane_exporter/talents_parser.py) with full spec extraction, glyph associations, malformed-rank preservation, and tree-total validation.
- Fixture-based offline tests (including synthetic 1010/1015 access fixtures, synthetic summary structure, and synthetic talents page) under [tests/](../tests).

## Exact local commands (use `.venv` Python explicitly)
```powershell
$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m unittest discover -s tests -v
$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m warmane_exporter.summary_diagnostic "local-captures\aikka-onyxia-summary-dom.html"
```

## Latest verified test result

**Local Copilot agent run:**
- Executed full offline test suite: **41 tests passed, 0 failed**
- Composition: summary parser (2 tests) + transport (7 tests) + checkpoint (1 test) + identity (4 tests) + retry (3 tests) + **talents parser (24 tests)**
- Talents parser includes 4 new regression tests for edge cases: missing rank elements, trees without tree-info, tabs without containers, glyph class reordering
- Both real captured talent pages (spec1 + spec2) parsed correctly with all tree totals matching reported values

**Independent Perplexity review:**
- Ran uploaded 24 talent-parser tests in isolation: **all 24 passed** ✓
- Verified four acceptance-failure cases now behave correctly:
  1. Talent anchor without `talent-points` div: retained with error marker ✓
  2. Tree without `tree-info` div: `reported_total` null, validation indeterminate ✓
  3. Spec tab without matching container: warning generated ✓
  4. Glyph divs with reordered CSS classes: parse correctly ✓
- Did not re-run: full suite, both real captures' allocations, or independent verification of matched tree totals

**Offline talents-parser increment status:** Accepted after bounded review. Fixes to edge cases verified; no regressions.

**NEW — Rank-discovery mechanism candidate identified:**
- Two controlled live Copilot HTTP requests to cavernoftime.com spell API (exact requests: `/spell=14748&power=true` and `/spell=14748`)
- GET `/spell=14748&power=true` returned HTTP 200: Rank 1 tooltip definition ("Improved Power Word: Shield", 5% effect)
- GET `/spell=14748` (no-redirect handler) returned HTTP 200: normal definition page with Rank 1 effect and related-spell data identifying Rank 2=spell_id 14768 and Rank 3=spell_id 14769
- Unranked related entry (spell_id 24191) present in data; not all "See Also" entries are rank mappings
- **Mechanism candidate:** Extract spell ID from talent href → fetch Cavernoftime spell page → parse related-spell entries for rank IDs → fetch each rank's spell page for definition
- **Verified for:** Only one talent (14748 with 1/3 selected); higher ranks not yet fetched
- **Requires:** Verification across additional talents, glyph mechanism discovery, ruleset compatibility check, source access/reuse terms review
- See [data-sources.md Finding: cavernoftime-spell-rank-discovery-2026-10-24](./data-sources.md#findings-log)

**NEW — Enchantment and gem parameter isolation (Cavernoftime):**
- Five controlled item GETs to https://wotlk.cavernoftime.com/item=51178 with parameter variations.
- Base (no params): Meta/Blue socket labels (q0 CSS).
- Ench=3820 isolated: Adds "+30 Spell Power and 20 Critical strike rating" effect text; socket labels unchanged.
- Gems=3627:3879 isolated: Replaces socket labels with two gem-effect descriptions ("+21 Intellect...mana", "+10 All Stats"); socket labels removed.
- Combined: Union of isolated effects.
- **Finding:** Enchantment code 3820 effect text resolved and matches EvoWoW manual screenshot evidence (see below).
- **Limitation:** Gem codes produce joint effect text; per-gem mapping not isolated. Socket bonus activation state unknown. Bonus CSS class (q0→q2) reported earlier but not confirmed in final retained-file verification.
- See [data-sources.md Finding: cavernoftime-enchantment-gem-parameter-isolation-2026-10-24](./data-sources.md#findings-log).

**NEW — EvoWoW enchantment lookup verification:**
- One Copilot automated GET to https://wotlk.evowow.com/?enchantment=3820: HTTP 403 Forbidden (access blocked).
- User-provided browser screenshot shows successful manual access: Enchantment ID 3820 explicit; effect "+30 Spell Power and 20 Critical strike rating" matches Cavernoftime output.
- **Finding:** Enchantment ID namespace established via manual evidence; automated access currently blocked. EvoWoW ?enchantment= parameter historically used for both equipment enchantments and gem codes (historical main.py evidence), but gem-code namespace not yet verified.
- **Limitation:** Automated access blocked. Gem code 3627 lookup not attempted. Related-item names do not establish unique item IDs. Source reuse terms unchecked.
- See [data-sources.md Finding: evowow-enchantment-3820-manual-verification-2026-10-24](./data-sources.md#findings-log).

**Milestone 0 status:** **Incomplete** — equipment-to-definition chain partially explored; gem codes, bonus activation, and active spec remain unresolved.

## Access finding (automated retrieval)
- One approved automated request to `Aikka / Onyxia / summary` returned:
  - HTTP **403**
  - body: `error code: 1010`
- Recorded as an **access-block finding**, not character-data absence.
- Automated access for normal retrieval remains unresolved (see [data-sources.md](./data-sources.md)).

## Manual rendered-DOM findings (offline)

### Summary page (from previous checkpoint)
- Parsed from local rendered-DOM capture:
  - identity + guild
  - character-sheet displayed sections/values/units
  - equipped item refs with raw `item` / `ench` / `gems` namespaces
  - explicit empty slots (e.g., Shirt/Tabard)
  - two specialization summary point distributions
  - navigation links to uncaptured sections
  - recent achievements as **partial** activity list

### **NEW — Talents page**
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

### Limitations
- Rendered-DOM captures may include JavaScript-generated elements or cached tooltip snippets.
- Captures do not prove full progression/achievement/statistics coverage.
- Recent achievements are partial activity list, not complete progression evidence.

## Local capture files (kept local, git-ignored)
- `local-captures\aikka-onyxia-summary-dom.html`
- **NEW:** `local-captures\aikka-onyxia-talents-spec1-dom.html`
- **NEW:** `local-captures\aikka-onyxia-talents-spec2-dom.html`

## Open gaps before Milestone 0 completion
- Reliable automated access to Warmane character pages.
- Equipment-slot mapping certainty (layout-position ambiguity for many slots).
- Talent effect text and glyph effect descriptions (not present in current captures; future investigation needed).
- External definition resolution/mapping (items, enchants, gems, talents, glyphs).
- Progression coverage beyond summary recent-activity snippets.

## Next task (if approved)

**No next implementation or live investigation is approved yet.**

Proposed next session workflow:
1. Review remaining Milestone 0 gaps (see section below).
2. Propose one bounded offline or live investigation for user approval.
3. Document scope, safeguards, and expected findings before execution.

**Resolved items (do not revisit):**
- ~~Talent tree-total mismatches~~ → Parser defects, now fixed. All six trees in both real captures match their reported totals.

## Approval boundary
- **No further live requests are currently approved.**
- Parser refinements must await explicit scope approval in next session.
