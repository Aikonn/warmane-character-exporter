# Task: update from GitHub (Settings window)

Status: designed 2026-11-16, waiting for implementation. Owner decisions are marked (owner).

## Goal

The owner makes quick changes and asks others (his brother) to test them. A tester with a Download ZIP copy must be able to check for a newer version and update with one click, without Git and without downloading the zip by hand.

## Decisions

- Git is not needed (owner: testers use Download ZIP). The update downloads branch `main` as a zip from GitHub, exactly what Download ZIP gives. There are no releases.
- Settings is a button on the main dialog that opens a separate Settings window, not a tab (owner). The Settings window has one group per topic; "Updates" is the only one for now. Later groups (for example default output folders) go below it.
- No automatic check at start for now (owner). Every request to GitHub happens only when the user clicks a button. A later automatic check (at most once a day) needs an opt-out setting that is visible in the Settings window, because some users do not want the tool to connect anywhere without them knowing (owner).
- A folder that is a Git clone (has `.git`) is never overwritten: Check works, Update now is disabled with the text "This folder is a Git clone. Use git pull."

## Requests (third-party site rules)

Only on a button click, unauthenticated, header `User-Agent: warmane-character-exporter-updater`, 20 s timeout, no retries:

- Check = 2 requests to the GitHub REST API:
  - `GET https://api.github.com/repos/Aikonn/warmane-character-exporter/commits/main` (sha, committer date, first line of the message)
  - `GET https://api.github.com/repos/Aikonn/warmane-character-exporter/git/trees/<sha>?recursive=1` (path + blob sha of every file)
- Update = Check again + 1 download: `https://codeload.github.com/Aikonn/warmane-character-exporter/zip/<sha>` (the exact commit that was checked, not "whatever main is now").
- GitHub allows 60 unauthenticated API requests per hour per IP. HTTP 403/429 with `X-RateLimit-Remaining: 0` is reported as "GitHub request limit reached, try again in an hour" (no retry).

## How "differs" is decided

No version file. For every blob in the tree, compute the Git blob hash of the local file (`sha1(b"blob " + str(len(data)).encode() + b"\0" + data)`) and compare with the tree's sha. GitHub zips contain the bytes as stored in the repo, so a fresh Download ZIP copy matches exactly.

- **changed**: local file exists, hash differs.
- **missing**: in the tree, not on disk.
- **stale**: on disk under `src/` or `tests/`, not in the tree (ignore `__pycache__` folders and `*.pyc`). Only these two folders are fully owned by the repo.
- Status `up_to_date` when all three lists are empty, otherwise `update_available`.

For a Git clone: read the local HEAD commit from `.git` (`HEAD` → `refs/heads/<branch>` file or `packed-refs`); status `git_clone` with `behind = local_sha != latest_sha`. File hashes are not compared (core.autocrlf changes the bytes on Windows).

## Applying an update

1. Refuse (exit 2) when the folder is a Git clone.
2. Run the check. If up to date, do nothing (exit 0, "Already up to date").
3. Download the zip for the checked sha into `.tools/update/` (delete that folder first).
4. Extract to `.tools/update/extract/`. Reject the zip (nothing copied) when: any member is absolute or contains `..`; there is not exactly one top folder; `src/warmane_exporter/__init__.py` or `Start-Report.ps1` is missing under it.
5. Copy every file of the top folder to the program folder, each through a temp file in the same folder and `os.replace`. Never write under `.git/`, `.tools/`, `.warmane-cache/`, or to `warmane-character-exporter.config` (the zip never contains them; check anyway).
6. Delete the **stale** files (only under `src/` and `tests/`).
7. Delete `.tools/update/`. Print the result; exit 0.

Kept as they are: `.tools` (portable Python, temp), `.warmane-cache`, the config file, git-ignored files under `library/`, report output folders.

If a copy fails part way, stop, report which file failed, and tell the user to use the manual update (Download ZIP and extract over the folder). No rollback.

`Start-Report.ps1` may be overwritten while it runs: PowerShell has already parsed the script. After a successful update the launcher starts `Start-Report.vbs` again and exits.

## CLI

```
python -m warmane_exporter.updater check
python -m warmane_exporter.updater apply
```

Both print one JSON object on stdout (UTF-8) and nothing else:

```json
{"status": "update_available", "message": "4 files differ from the latest version.",
 "latest": {"sha": "d4e5f6a...", "date": "2026-11-16T10:12:00Z", "message": "Fix roster progress"},
 "changed": ["src/warmane_exporter/roster.py"], "missing": [], "stale": [],
 "local_sha": null, "behind": null}
```

`status` is one of `up_to_date`, `update_available`, `git_clone`, `updated`, `error`. Exit codes: 0 success (any check result, or update done / nothing to do), 1 error (network, rate limit, bad zip, copy failed; `message` says why), 2 refused (Git clone).

## Launcher (Start-Report.ps1)

Main dialog (`Read-Link`): a "⚙ Settings" button at the bottom left, on the row of Create report / Cancel (y = 190). Flat style (`FlatStyle = Flat`, `FlatAppearance.BorderSize = 0`), gray text (`SystemColors.GrayText`), size about 100 × 28, same font as the dialog. Hover shows a hand cursor. It opens the Settings window modal over the main dialog; closing Settings returns to the main dialog unchanged. It is not the Accept or Cancel button.

Settings window (`Show-Settings`), `FixedDialog`, no maximize, centered on the parent, client size about 480 × 230, title "Settings":

```
+-- Settings -------------------------------------------+
| [Updates] --------------------------------------------|
|  Status:  Not checked yet.                            |
|  Latest:  -                                           |
|                                                       |
|  [Check for updates]   [Update now]                   |
|                                                       |
|  Manual update: github.com/Aikonn/warmane-character-exporter |
|                                                       |
|                                            [Close]    |
+-------------------------------------------------------+
```

- GroupBox "Updates" containing everything except Close.
- Status line texts:
  - before any check: "Not checked yet. Checking contacts github.com."
  - while checking: "Checking..." (both buttons disabled)
  - `up_to_date`: "Up to date."
  - `update_available`: "Update available: N files differ from the latest version." A ToolTip on the status label lists the paths (changed, missing, stale; at most 20, then "and N more").
  - `git_clone`: "This folder is a Git clone. Use git pull." plus " (behind GitHub)" when `behind` is true.
  - `error`: the message, in dark red.
- Latest line: `<date as yyyy-MM-dd HH:mm local> "<commit message first line>"`, or "-".
- Check for updates: runs `updater check` with the same Python and environment as the reports (`PYTHONPATH`, `PYTHONIOENCODING=utf-8`) as a hidden process; the window stays responsive (poll `HasExited` with `DoEvents`, as `Invoke-ProgressProcess` does). Parse stdout with `ConvertFrom-Json`. If stdout is not valid JSON, show "Check failed." and the last stderr line.
- Update now: enabled only after a check with status `update_available`. Confirm with YesNo: "Download the latest version (about 4 MB) from GitHub and replace the program files? Reports, cache and Python stay." On Yes: status "Updating...", buttons disabled, run `updater apply`. On exit 0 with `updated`: message "Updated. The launcher will now restart.", then `Start-Process wscript.exe` with `//nologo "<root>\Start-Report.vbs"` and `exit 0`. On other results: show the message and keep the window open.
- Manual update: a LinkLabel; clicking opens https://github.com/Aikonn/warmane-character-exporter in the default browser.
- Close: closes Settings (also Esc).

## Tests (no network)

Inject the HTTP getter (`http_get(url) -> bytes`) and use temp folders:

- `git_blob_sha` equals a known Git value (`git hash-object` of `b"hello\n"` is `ce013625030ba8dba906f756967f9e9ca394464a`).
- `compare_files`: changed / missing / stale detection; `__pycache__` and `.pyc` ignored; files outside `src/` and `tests/` that are not in the tree are not stale.
- `check`: up to date; update available; Git clone with HEAD in `refs/heads/main` and in `packed-refs`; rate limit (`HTTPError` 403 with `X-RateLimit-Remaining: 0`) gives status `error` with the limit message; truncated tree gives `error`.
- `extract_update`: rejects `..` member, absolute member, two top folders, missing `src/warmane_exporter/__init__.py`.
- `apply_update`: replaces changed files, adds missing, deletes stale, leaves `.warmane-cache/x`, `.tools/python312/x`, `warmane-character-exporter.config` and a git-ignored `library/acore/extra.db` untouched; refuses a Git clone with exit 2.
- `main`: prints exactly one JSON object; exit codes 0 / 1 / 2.
