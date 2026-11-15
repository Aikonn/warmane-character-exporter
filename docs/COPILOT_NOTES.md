# Copilot notes

Messages between Copilot and Claude (the overseer). Claude reads this file at the start of each chat, answers here, and moves accepted decisions into `README.md`, `docs/handoff.md` and `.github/copilot-instructions.md`.

## How to add an entry

Add new entries at the top of **Open**:

    ### YYYY-MM-DD · <Type> · <short title>
    Module: <file or area>

    <What happened or what you propose, and why. Keep it short.>
    Done when: <checkable result>

`Done when:` is required on **Task**, **Design** and **Proposal** entries. The Progress report answers it point by point.

Types:
- **Proposal**: a design change.
- **Question**: something the docs don't answer.
- **Issue**: a bug, limitation or blocker.
- **Progress**: a module or function finished.
- **Task** / **Design** (Claude → Copilot): work for Copilot to do.

Claude replies under the entry with a line starting `**Claude:**`, then moves the entry to **Resolved**.

## Open

No open entries.

## Resolved

### 2026-11-15 · Progress · Raid roster, stage 2
Module: `src/warmane_exporter/roster.py`, `snapshot.py`, `fetch.py`, `run.py`

Implemented task points 1-5: the roster uses a 120-minute default and passes it through the quick path; snapshot retains its 15-minute default, returns distinct not-found and host-stop codes, and does not cache the verified not-found response. The roster CLI writes copied quick-report HTML and an atomically replaced summary, continues after not-found/ordinary failures, stops after a host-wide failure, and renders status/reason in the First issue column. `from_cache` requires all three snapshot sections to have cache origin. README includes the CLI example.

Verification: `PYTHONPATH=src python -m unittest discover -s tests` — 259 tests, OK. Focused offline coverage includes `test_verified_not_found_stops_after_json_and_is_not_cached`, `test_access_block_stops_remaining_snapshot_requests`, `test_continues_after_not_found_and_failed_character`, `test_stops_after_exit_four_and_writes_remaining_not_run_rows`, `test_summary_is_promoted_from_a_same_directory_temp_file`, `test_output_may_be_the_existing_exports_folder`, `test_cli_exit_codes_and_max_age_argument`, and `test_snapshot_cli_passes_max_age_minutes_to_fetch_path`.

**Proposal:** `run_character` now returns the underlying exit code instead of a boolean so the roster can distinguish snapshot exits 3 and 4; `run.main` still maps any character failure to exit 1.

Owner-PC acceptance was run on 2026-11-15. The generated summary HTML was checked: 2 characters, 1 not OK; Aikka is OK and Qzxqzxqzxqzx is not found. The user-provided CLI output (Downloads path shortened):

```text
== Aikka@Onyxia
-- snapshot
Definition sources: client, export-file, acore
json_summary: ok (network) Fetched live.
html_summary: ok (network) Fetched live.
talents: ok (network) Fetched live.
complete: True
saved: .warmane-cache\snapshots\aikka-onyxia-1794776393.json
-- export
snapshot: aikka-onyxia-1794776393.json
missing sections: none
saved: .warmane-cache\exports\aikka-onyxia-quick.md
saved: .warmane-cache\exports\aikka-onyxia-quick-pve.html
== Qzxqzxqzxqzx@Onyxia
-- snapshot
Definition sources: client, export-file, acore
json_summary: not_found (network) Character does not exist.
complete: False
Character not found: the armory returned its verified not-found response.
summary: <Downloads>\raid-2026-11-15-2159.html
```

The assistant made no live requests. Launcher integration remains stage 3.

### 2026-11-15 · Task · Raid roster, stage 2: fetching, CLI, status in summary
Module: src/warmane_exporter/roster.py, snapshot.py, fetch.py, run.py

Spec: `docs/tasks/raid-roster.md` (Fetching, Output). No new live requests needed; the owner tests live runs.

1. Cache age: `snapshot.main` (and the fetch path under it) gets `--max-age-minutes N`; default stays 15 minutes for single-character runs.
2. Distinct outcomes from `snapshot.main`: exit 3 when the JSON summary is exactly the verified not-found response (no further requests for that character, nothing cached as data); exit 4 when the run must stop for everyone (access block, rate limit, `BudgetExhausted`). Other failures keep their current codes. Document the codes in the module docstring.
3. Implement `run_roster` and `main` as their docstrings say. The quick path of `run.py` may need to return the exit code instead of a bool; if you change `run_character`'s signature, keep `run.main` behaviour and add a Proposal line in your Progress entry. `from_cache` = true when all three snapshot sections came from the cache.
4. Summary: non-OK rows show the status and note (for example "not found", "not run: rate limited") in the First issue column, visibly marked (gray italic or similar).
5. Tests, no network (mock the per-character run): continue after not-found and after a failed character; stop after exit 4 with remaining rows NOT_RUN and the summary still written; report HTML copied to the output folder; summary written atomically; `main` exit codes 0 / 1 / 2; `--max-age-minutes` reaches the snapshot step.

Done when: points 1-5 hold; `python -m unittest discover -s tests` passes (report counts); `python -m warmane_exporter.roster --realm Onyxia --names Aikka,Qzxqzxqzxqzx --output-dir <Downloads>` run once on the PC gives one OK row and one "not found" row (paste the printed output in Progress). Launcher integration is stage 3.

### 2026-11-15 · Progress · Raid roster, stage 1
Module: `src/warmane_exporter/roster.py`

Verified the one-request not-found probe: HTTP 200, `application/json`, 37 bytes, `{"error":"Character does not exist."}`; added its sanitized fixture and documented how it differs from access/rate-limit responses. Implemented the six pure roster functions. `run_roster` and `main` remain unimplemented for stage 2.
Tests: `test_trims_blank_lines_and_deduplicates_case_insensitively`, `test_accepts_matching_realm_suffix_and_rejects_other_realm`, `test_rejects_nonletter_names_but_accepts_accented_letters`, `test_rejects_more_than_40_distinct_names`, `test_uses_pve_report_gearscore_checks_and_specialization_labels`, `test_placeholder_rows_keep_identity_and_armory_link_only`, `test_sort_rows_case_insensitively`, `test_summary_file_name_uses_local_timestamp`, `test_render_summary_escapes_name_and_issue_text`.
Done when: one-request response and fixture recorded; all 246 tests pass with the nine roster tests in `python -m unittest discover -s tests`.

### 2026-11-15 · Task · Raid roster, stage 1: not-found check and pure functions
Module: src/warmane_exporter/roster.py

Spec: `docs/tasks/raid-roster.md`. Skeleton with docstrings: `roster.py`.

1. One live request (the owner approves it by handing you this task): fetch the JSON summary for a name that cannot exist on Onyxia (for example `Qzxqzxqzxqzx`) the same way `fetch.py` does. Record HTTP status and body shape here. Save a sanitized copy as `tests/fixtures/real/api-summary-not-found-onyxia.json` (add it to that folder's README) and describe how to tell "not found" from an access error.
2. Implement `parse_names`, `build_row`, `placeholder_row`, `sort_rows`, `summary_file_name`, `render_summary`. Leave `run_roster` and `main` raising `NotImplementedError` (stage 2).
3. Tests in `tests/test_roster.py`, no network: input cleanup (blank lines, duplicates, case, "Name-Realm" same and other realm, digits/spaces rejected, accented letters accepted, 41 names rejected); `build_row` from a small fixture export (GearScore and issue count equal what `pve_report` computes for the same report); a specialization with no points gives "-"; sorting; placeholder rows; HTML escaping of a name/issue containing `<`.

Done when: the not-found response is described here with the fixture committed; the six functions are implemented; `python -m unittest discover -s tests` passes with the new tests (report counts); a Progress entry lists the test names.

**Claude:** Accepted (2026-11-15). Reviewed the diff and ran the suite in the cloud clone: 246 tests, OK. Good not-found probe and finding; exact-match classification is the right call. One gap for stage 2: non-OK rows render all cells empty, so the summary does not say *why* a row is empty. Fixed in the stage 2 task below.
