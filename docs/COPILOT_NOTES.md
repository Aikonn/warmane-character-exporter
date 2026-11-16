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

### 2026-11-16 · Task · Updater: fix the launcher restart flag
Module: Start-Report.ps1, docs/tasks/update-feature.md (spec text already updated)

1. Do not assign `$script:` variables inside `.GetNewClosure()` script blocks. In `Read-Link` create `$shared = @{ Restart = $false }`, pass it to `Show-Settings $form $shared`, set `$shared.Restart = $true` in the Update click handler (a hashtable is shared by reference), and after `$form.ShowDialog()` returns in `Read-Link` set `$script:restartLauncher = $shared.Restart` (Read-Link is a normal function, so `$script:` works there). Grep the launcher for other `$script:` assignments inside `GetNewClosure()` blocks and fix them the same way.
2. Success message: "Updated. The launcher will now restart. If it does not open, start Start-Report.cmd again."
3. Fallback only if point 1 still gives no new window on the PC: message "Updated. Please start Start-Report.cmd again.", close, no `Start-Process`; note it in Progress and change the spec line.

Done when: PowerShell parser check passes; `python -m unittest discover -s tests` passes (counts); on the PC, a Download ZIP copy one commit behind, Settings > Check > Update now shows the message, the launcher closes and opens again by itself (or, with the fallback, closes and opens fine when started by hand), and Check then says "Up to date".

### 2026-11-16 · Issue · Owner-PC updater acceptance pending
Module: src/warmane_exporter/updater.py, Start-Report.ps1

Implementation, 12 focused updater tests, the 278-test offline suite, and the PowerShell parser check pass. Owner-PC checks confirm a Git clone shows the clone message with Update now disabled, and a fresh ZIP shows "Up to date" rather than "git_clone". Older ZIPs predate the updater and cannot check for updates. A PC Update now run found one changed file, but the restart raised `ExitException`: `exit 0` ran inside a WinForms click callback. The callback now closes both dialogs and defers restart/exit to the top level. Re-test Update now; the owner tests with his brother.

Owner-PC follow-up: updating the same ZIP copy again showed an error, but after closing and reopening it, Check for updates reported "Up to date". The running launcher still used the old script while the update copied the fix; this notes change enables a fresh test with the fixed launcher. The successful restart remains unverified.

**Claude:** Code accepted except the restart (2026-11-16): reviewed the diff of `updater.py`, `test_updater.py`, `Start-Report.ps1` and README; 278 tests OK in the cloud clone (1 skipped). Zip checks (unsafe paths, symlinks, one top folder, required files), protected paths and the temp-file copy match the spec. Stays open until the restart task above passes on the PC.

### 2026-11-16 · Task · Update from GitHub: updater module and Settings window
Module: src/warmane_exporter/updater.py, Start-Report.ps1, README.md

Spec: `docs/tasks/update-feature.md`. Skeleton with docstrings: `updater.py`. No live requests to GitHub in tests (inject `http_get`); one manual `check` run on the PC is allowed.

1. Implement every function in `updater.py` as its docstring and the spec say.
2. Tests in `tests/test_updater.py` as listed in the spec (Tests section), no network.
3. Launcher: "⚙ Settings" button on the main dialog and the `Show-Settings` window (spec, Launcher section). Single-character and roster flows unchanged.
4. README: short "Updating" section (Settings > Check for updates > Update now; manual update = Download ZIP again and extract over the folder; a Git clone uses git pull).

Done when: points 1-4 hold; `python -m unittest discover -s tests` passes (report counts and the new test names); on the PC, in your Git clone, Settings > Check for updates shows the Git clone text and Update now stays disabled; `python -m warmane_exporter.updater check` run in a copy made with Download ZIP of an older commit prints `update_available` with the expected files (paste the JSON, shortened). The owner tests Update now with his brother.

**Claude:** Points 1, 2 and 4 accepted and the Git clone check passed on the PC; point 3 stays open for the restart (see the restart task).

## Resolved

### 2026-11-16 · Proposal · Close after update instead of restarting
Module: Start-Report.ps1, docs/tasks/update-feature.md

Owner-PC retest with the fixed launcher: no error appeared and the application closed, but no new instance launched. The owner suggests telling the user to relaunch the application manually after a successful update, then closing it, instead of automatically restarting.

Done when: Claude reviews the proposed change; if accepted, the success message asks the user to relaunch and the launcher closes without starting a new instance.

**Claude:** Root cause found (2026-11-16), so the restart stays, with a fallback. In `Show-Settings` the Update click handler is a `.GetNewClosure()` script block. A closure runs in its own dynamic module, so `$script:restartLauncher = $true` sets a variable in that module, not in Start-Report.ps1. The top-level flag stays `$false`, `Read-Link` returns `$null`, and the launcher exits normally: no error, no new instance, exactly what the PC showed. The ExitException before was the same scope issue. Fix in the Task below. If the restart still does not open a window on the PC after the fix, switch to the owner's proposal (close and ask to relaunch) in the same task without asking again.



### 2026-11-15 · Progress · Raid roster, stage 3 implementation
Module: `transport.py`, `roster.py`, `run.py`, `Start-Report.ps1`

1. Transport classification now prioritizes a 403 block marker over rate-limit markers; a 2xx response is blocked for Cloudflare 1010 only when short (under 2 KB and not truncated) or missing known armory-page markup. "Access Denied" alone remains success on a 2xx response. Covered by `test_403_block_marker_wins_over_rate_limit_marker`, `test_200_armory_text_with_access_denied_is_success`, `test_classifies_access_denial_content_even_with_success_http_status`, `test_200_cloudflare_1010_page_with_armory_markup_is_success`, `test_200_cloudflare_1010_page_without_armory_markup_is_blocked`, and `test_truncated_1010_body_with_armory_markup_is_not_treated_as_short`.
2. Roster progress starts once at 4 units per character, notes each character before its run, and does not reset inside `run_character`. `test_progress_percent_never_decreases_across_two_characters` and `test_run_character_can_join_existing_progress` pass.
3. The launcher now has the roster choice/dialog, remembers realm and output folder, writes UTF-8 names under `.tools\tmp`, passes quoted paths and refresh, shows the roster title/progress, opens the last summary line on exit 0/1, and reopens input on exit 2 with names retained. Single-character flow remains on the existing path. PowerShell parser check: OK.

Verification: `PYTHONPATH=src python -m unittest discover -s tests` — 266 tests, OK. `git -c core.whitespace=cr-at-eol diff --check` — clean.
Follow-up: `Start-Report.ps1` now removes trailing separators from non-root output paths and represents filesystem roots with a `.` component (for example, `D:\.`) before quoting the CLI argument. PowerShell parser and output-path checks passed, including a path with spaces and an accented character. Owner-PC acceptance remains open because the final summary contents were not provided; no live requests were made.
Owner-PC launcher headers (user-provided):

```text
Run time: 2026-11-15 22:16; characters: 3; from cache: 1; not OK: 1.
Run time: 2026-11-15 22:19; characters: 3; from cache: 2; not OK: 1.
```
No live requests were made by the assistant.

**Proposal:** `run_character` gained a final `start_progress=True` parameter so roster runs can share one progress total while single-character callers retain the existing default behavior.

**Claude:** Code accepted (2026-11-15): reviewed the diff, 266 tests OK in the cloud clone; transport fix and `start_progress` proposal accepted. Stays open pending confirmation of the summary contents. The launcher still needs to handle output folders ending in a backslash: do not leave a raw `\` immediately before the closing quote in `--output-dir`; normalize a drive root such as `D:\` to `D:\.` (not `D:`) before building the command line.

**Claude:** Accepted (2026-11-15). Reviewed the follow-up diff (`Start-Report.ps1` output-path normalization): drive root becomes `D:\.`, other paths lose the trailing `\`; empty folder is still rejected by the dialog. 266 tests OK in the cloud clone (1 skipped). The two PC header lines meet Done when (3 characters, 1 not OK = 2 OK + not found; second run from cache: 2). Raid roster is complete. Minor, no action needed now: an output folder with invalid path characters makes `GetFullPath` throw before the progress window; a later polish can catch it and reopen the dialog.

### 2026-11-15 · Task · Raid roster, stage 3: transport fix, roster progress, launcher
Module: transport.py, roster.py, progress.py, Start-Report.ps1

Spec: `docs/tasks/raid-roster.md` (Launcher). No live requests needed; the owner tests on the PC.

1. `classify_response`: restore the earlier order (403 + block marker = blocked before the rate checks). On a 2xx status, treat only a Cloudflare error page as blocked: "error code: 1010" present and the body short (under 2 KB) or without the armory page markup; never on "access denied" alone. Tests: 200 armory-like page containing "Access Denied" in text stays success; 200 short "error code: 1010" body is blocked; existing tests keep passing.
2. Roster progress: one overall percent across all characters (each character = 4 units: 3 snapshot + export), and `progress.note("Character N of M: Name")` before each character. `run_character` must not reset the overall percent when called from the roster (for example a parameter that skips `progress.start`). Test with WARMANE_PROGRESS set: percent never goes down over a 2-character mocked run.
3. Launcher (`Start-Report.ps1`):
   - First dialog: third radio "Raid roster: quick report for a list of characters". Remember the mode as today ("roster"). When chosen, the armory link box is not required.
   - Roster dialog: multi-line text box (one name per line, paste-friendly, scroll bars), realm drop-down Onyxia / Icecrown (last used, `.warmane-cache/launcher-realm.txt`), "Refresh all" checkbox (unchecked), output folder field with Browse (FolderBrowserDialog; last used in `.warmane-cache/launcher-roster-folder.txt`, default Downloads), buttons Create reports / Cancel.
   - Before starting Python: write the names to a UTF-8 temp file in `.tools\tmp`; run `-m warmane_exporter.roster --realm R --names-file F --output-dir D` (+ `--refresh`). Quote paths (spaces, accented letters).
   - Progress window as today; title "Creating raid roster reports (N characters, Realm)".
   - Exit 0 or 1: open the path from the last "summary: " line in the browser; on 1 also show a short message that the run stopped early and why (last stderr line). Exit 2: show the input errors (stderr) and reopen the roster dialog with the text kept.
   - Single-character modes unchanged.

Done when: points 1-3 hold; `python -m unittest discover -s tests` passes (report counts); on the PC a launcher run with 3 names (Aikka, Bezduse, Qzxqzxqzxqzx) on Onyxia opens a summary with 2 OK rows and 1 not found, and a second run within 2 hours shows "from cache: 2" in the header (paste both header lines in Progress).

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

**Claude:** Accepted (2026-11-15) with two follow-ups in stage 3. Reviewed the diff; 259 tests OK in the cloud clone; the PC run meets Done when. Proposal on `run_character` returning the exit code: accepted. Note for next time: leave your Progress entry and my Task in **Open**; I move them to Resolved after review.
- Regression risk in `transport.classify_response`: the block markers now match on any status, and "access denied" is plain text that can appear on a normal 200 page (guild name, item or achievement text). That would stop every command with exit 4. Fix in stage 3, point 1.
- `run_roster` does not emit "Character N of M: Name", and each `run_character` restarts the percent at 0. Stage 3, point 2.

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
