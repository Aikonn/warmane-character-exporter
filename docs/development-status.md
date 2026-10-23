# Development Status (Checkpoint Handoff)

## Scope status
- **Current milestone:** **Milestone 0** (source feasibility investigation) — **incomplete**.
- Requirements baseline remains in [specification.md](./specification.md) and source-tracking details in [data-sources.md](./data-sources.md).

## Implemented at this checkpoint
- Minimal retrieval probe scaffold (offline plan + controlled live modes) in [src/warmane_exporter/](../src/warmane_exporter).
- Offline rendered-DOM summary diagnostic parser (local file input only) in [summary_parser.py](../src/warmane_exporter/summary_parser.py) and [summary_diagnostic.py](../src/warmane_exporter/summary_diagnostic.py).
- Fixture-based offline tests (including synthetic 1010/1015 access fixtures and synthetic summary structure) under [tests/](../tests).

## Exact local commands (use `.venv` Python explicitly)
```powershell
$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m unittest discover -s tests -v
$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m warmane_exporter.summary_diagnostic "local-captures\aikka-onyxia-summary-dom.html"
```

## Latest verified test result
- Last verified run: **17 tests passed, 0 failed** using `.venv` Python and offline-only tests.

## Access finding (automated retrieval)
- One approved automated request to `Aikka / Onyxia / summary` returned:
  - HTTP **403**
  - body: `error code: 1010`
- Recorded as an **access-block finding**, not character-data absence.
- Automated access for normal retrieval remains unresolved (see [data-sources.md](./data-sources.md)).

## Manual rendered-DOM findings (offline)
- Parsed from local rendered-DOM capture:
  - identity + guild
  - character-sheet displayed sections/values/units
  - equipped item refs with raw `item` / `ench` / `gems` namespaces
  - explicit empty slots (e.g., Shirt/Tabard)
  - two specialization summary point distributions
  - navigation links to uncaptured sections
  - recent achievements as **partial** activity list
- Limitations:
  - rendered-DOM may include JavaScript-generated elements
  - does not prove full talents/glyphs/statistics/reputation coverage
  - recent achievements are not complete progression evidence

## Local capture files (kept local, git-ignored)
- `local-captures\aikka-onyxia-summary-dom.html`

## Open gaps before Milestone 0 completion
- Reliable automated access to Warmane character pages.
- Equipment-slot mapping certainty (layout-position ambiguity for many slots).
- Full talents + glyph extraction (beyond summary specialization totals).
- External definition resolution/mapping (items, enchants, gems, effects).
- Progression coverage beyond summary recent-activity snippets.

## Next task (approved direction)
- Inspect manually captured **talents pages** offline and extend parser/tests accordingly.

## Approval boundary
- **No further live requests are currently approved.**
