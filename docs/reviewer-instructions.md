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
- When a user decision is needed, put it at the very end under a label
  "Decision needed:", at most 400 characters.
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
