# Task H: gem quality check and spec-aware major glyph check

Status: open (owner decision 2026-11-19). Applies to `src/warmane_exporter/checks.py` (character PvE report findings) and the roster summary in `src/warmane_exporter/roster.py`.

## 1. Gem quality (new, in `check_gear`)

Data already there: each socketed gem in `item["gem_details"]` has `color` and `quality` (quality name from AzerothCore: `"common"`, `"uncommon"`, `"rare"`, `"epic"`, ...) when the definitions know them; each item has `item_level`.

Rules, per item:
- Skip gems whose `color` is `"meta"` (all meta gems are uncommon).
- Skip empty sockets and gems without a known `quality` (no finding, no guess).
- **Issue** for gems of quality `common` (or `poor`). One finding per item, kind `gem_common`, `count` = number of such gems on the item. Text: `{n} common-quality gem(s): {gem texts joined with "; "}.`
- **Warning** for gems of quality `uncommon` on an item with `item_level >= 251` (ICC gear; add constant `ICC_ITEM_LEVEL = 251`). One finding per item, kind `gem_uncommon`, `count` = number of such gems. Text: `{n} uncommon-quality gem(s) in item level {item_level} gear: {gem texts joined with "; "}.` If `item_level` is unknown, no warning.
- Uncommon gems below item level 251: no finding.
- Gem text is `gem.get("text") or "gem"` (same pattern as the meta finding).

## 2. Major glyphs (change in `check_specs`)

Only at level 80, as now. A spec "has talents" when it has more than 0 points spent (specs with 0 points keep the existing `no_talents` warning and are not checked further).

- Among specs with talents, a spec is "fully glyphed" when it has 3 major glyphs.
- **No spec with talents is fully glyphed**: every spec with talents and fewer than 3 major glyphs gets an **issue**, exactly as now (kind `glyphs`, same text, `count`, `spec_index`).
- **At least one spec is fully glyphed**: every other spec with talents and fewer than 3 major glyphs gets a **warning** instead (kind `glyphs`, `count`, `spec_index`). Text: `{empty} major glyph slot(s) empty ({major} of 3 filled); another specialization has all 3.`

Keep the talent-point check as it is. Finding order stays per spec (talents finding, then glyph finding), so compute the "any spec fully glyphed" flag before the loop.

## 3. Roster summary (`roster.py`)

The roster lists issues only; warnings stay a count.
- Grouped Issues: add a group for `gem_common`, same shape as Empty sockets: `Common gems ({total}):` with details `Head 1, Chest 2`. Place it right after Empty sockets.
- Quick-sum: add `gem_common` to the known kinds; in the `other` part add `1 common gem` / `{n} common gems` (e.g. `Name 5.1k - missing 2 enchants; 3 common gems`), placed before `inactive meta gem`.
- Glyph warnings are not issues, so they no longer count in "Major glyphs empty" or in the quick-sum glyph count. No code change needed for that beyond using `level`.

## 4. Text and docs

- `checks.py` module docstring: mention gem quality and that glyph findings are issues only when no spec is fully glyphed.
- `pve_report.py` "No problems found by these checks (...)" line: add "gem quality".
- `docs/tasks/roster-summary-look.md`: list the new kinds.

## Done when

1. `PYTHONPATH=src python -m unittest discover -s tests` passes (report the count), with new tests in `tests/test_checks.py` for: common gem → issue with count; uncommon gem at ilvl 251 → warning; uncommon gem at ilvl 245 → nothing; uncommon meta gem → nothing; gem with unknown quality → nothing; one spec 3 majors + other spec 2 majors → warning on the other spec only; both specs 2 majors → two issues; spec with 0 points → still only the `no_talents` warning.
2. Roster tests: a `gem_common` issue appears as `Common gems (n): <slot> <count>` in the grouped list and as `n common gems` (`1 common gem`) in the quick-sum line; a glyph warning does not appear in either.
3. Existing finding texts for enchants, sockets, meta, buckle, talents, armor and the glyph issue are unchanged.
4. Progress entry in `docs/COPILOT_NOTES.md` answers points 1-3.
