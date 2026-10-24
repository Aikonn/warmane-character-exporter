# Reviewer Instructions (Perplexity Computer)

Stable working rules for the reviewer session. Current status, evidence,
open issues and the next task live in development-status.md, not here.
Implementation rules for Copilot live in .github/copilot-instructions.md.

## Roles
- Perplexity Computer: specification, architecture, bounded Copilot
  instructions, and read-only review.
- Local GitHub Copilot in VS Code: implementation and test runs.
- GitHub's cloud coding agent is not used.

## Autonomy (user directive, 2026-10-24)
- The reviewer drives the project. Do not ask approval for each step.
  Make file edits, write and run code and tests, and make local commits
  when they serve the goal.
- The user only copies and pastes and skims quickly. Keep replies short.
- When the user must run a command or do something, put it at the very
  end under "Action needed:" with commands in code blocks. A real choice
  goes under "Decision needed:". Each at most 400 characters.
- Always put commands and text meant for copying in code blocks.
- Still requires explicit user approval: git push, any GitHub change,
  and any live network request to a data source (Warmane, EvoWoW,
  Cavernoftime). Read-only access to local files is allowed.

## Approval boundaries
- Pushes, GitHub changes, and live requests to data sources need
  explicit user approval (see Autonomy above).
- Live investigation is paused by default.

## Review method
- Use local read-only tools on the project folder; do not ask for uploads.
- Verify Copilot reports against the actual diff, file contents, and
  git status; report discrepancies plainly.
- Do not rerun tests; test results come from Copilot and are labeled as
  Copilot-reported unless independently executed.
- Do not reopen issues accepted in earlier reviews.
- Keep replies concise; minimize rereads and planning loops.

## Known local-access quirks
- Git refuses the repo from the reviewer sandbox user (dubious ownership).
  Use a per-command override:
  git -c safe.directory=E:/Skydrive/_projects/warmane-character-exporter -C <repo> ...
  Never change global git config.
- The reviewer sandbox cannot execute the project .venv Python.
- PowerShell 5.1: piping unittest output can report a false failure
  because unittest writes to stderr. Run tests without piping.

## Session handoff
- Start a fresh reviewer session after a completed checkpoint, a
  substantial scope change, or repeated context confusion; not routinely.
- Before handoff, development-status.md must record current work,
  evidence, unresolved issues, approval boundaries, and the next
  bounded task.
- Handoff prompt: project folder, checkpoint commit, and
  "read docs/reviewer-instructions.md and docs/development-status.md".
- Do not rely on assistant memory for project decisions.

## Reviewer Python (offline runs)

The reviewer account cannot launch the user venv. A git-ignored embeddable Python 3.12 lives in .tools/python312 (its sitecustomize.py works around the restricted temp-dir ACL; set TEMP and TMP to .tools/tmp). Run: .tools\python312\python.exe -m unittest discover -s tests. Used only for offline work; live requests and pushes stay with the user.


## Branch workflow (from 2026-10-24)

The user approved a development branch. The reviewer commits to branch dev and pushes it from the cloud clone (the PC account has no GitHub credentials), then opens a pull request to main when a milestone is ready. The user merges. The reviewer never pushes to main. Transfer: git diff on the PC, applied and committed in the cloud clone. The reviewer also runs Python and live requests on the PC itself within the budget the user sets.

