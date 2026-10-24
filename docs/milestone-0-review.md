# Milestone 0 Review (2026-10-24)

Purpose: summarize what the source investigation established, what it did not, and what scope changes are proposed. Evidence lives in docs/data-sources.md (sections 14 to 16 and the dated findings) and tests/fixtures/real/.

## Verdict

Milestone 0 is feasible for every data area, with one blocking design question (how HTML pages are fetched) and several documented gaps. It is ready for reviewer sign-off once the fetch strategy is chosen.

## What is established

- Character basics, equipment item IDs and names, talent point splits, professions and PvP teams are available from one JSON endpoint per character (/api/character/<Name>/<Realm>/summary). Verified for all four debug characters.
- Enchants, gems, slots, individual talents and glyphs come from the HTML summary and talents pages. Verified on Aikka@Onyxia (all) and on the other three characters for equipment.
- All definition text (enchants, gems, talents, glyphs, spells, item type) is resolved offline from the user's own 3.3.5a client files. No third-party definition site is needed.
- Achievements: one POST per category or subcategory returns earned and locked entries. Statistics: same POST pattern.
- Live access worked for all 16 requests made through the maintainer's own Chrome; no blocks or rate limits.

## What is absent or unknown

- Item quality, stats, socket count and socket bonus: not in the client files or the JSON API.
- Active spec: not exposed.
- Rendered tooltip numbers: spell descriptions are raw templates ($s1 and similar).
- Reputation, mounts, companions and match history: not investigated.
- Statistics: only one category sampled. Achievement header totals differ by one from entry counts in the one category compared.
- HTML pages for Icecrown talents and glyphs, and Onyxia talents for Bezduse, were not captured.
- Profession skill values in the JSON look unreliable for at least one character (skill "1").

## Access finding

Plain scripted HTTP to the HTML pages was blocked earlier (Cloudflare 1010 and a 1015 rate limit). Browser requests worked. Whether the JSON endpoint accepts a plain HTTP client was not tested.

## Cost

Up to about 85 requests per character for a complete export (see data-sources.md). At 10 to 15 seconds between requests that is 15 to 20 minutes per character. Requires throttling, caching, resumable state and an explicit user trigger.

## Proposed scope changes

1. Treat the client DBC files as the definition source, with the path from the config file. Document that a 3.3.5a client is a requirement.
2. Use the JSON endpoint for basics and item names, the HTML pages only for enchants, gems, slots, talents and glyphs.
3. Drop item quality, socket data and active-spec detection from the first release, or mark them as optional and unavailable.
4. Make complete achievement and statistics export an opt-in, slow mode.
5. Fetch strategy for HTML pages (decision pending): see below.

## Fetch strategy options

- A. User-assisted browser capture: the tool provides a small script or instructions to save pages from the user's own logged-in-free browser into a folder; the exporter parses local files. Lowest risk, most manual.
- B. Browser-driven fetcher (an automated local browser with human-like pacing) run by the user. Automated, but needs a browser dependency and may break with site changes.
- C. Plain HTTP for JSON only, plus option A for HTML. Needs one more test of the JSON endpoint without a browser.

Recommendation: C, falling back to A. Option B only if the user wants fully automatic exports.

## Next after sign-off

Milestone 1 should start with the JSON-endpoint adapter and the offline definitions layer already built, then the HTML parsers over locally saved pages.