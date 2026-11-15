# Notes for Claude

- Claude is the overseer: goals, design, review, docs, instruction files and code skeletons (signatures + docstrings, bodies raise `NotImplementedError`). GitHub Copilot in VS Code on the owner's PC implements function bodies and tests.
- Everyone works directly on `main` (owner decision 2026-11-15). Claude pushes docs, instruction files and skeletons without asking.
- At the start of each chat, read `docs/COPILOT_NOTES.md`. Answer open entries there (`**Claude:**` replies), move them to Resolved, and update README, `docs/handoff.md` and `.github/copilot-instructions.md` with accepted decisions.
- Review Copilot's work against the actual diff and run the tests in the cloud clone (`PYTHONPATH=src python -m unittest discover -s tests`); say which checks ran.
- Every Task/Design note for Copilot has a `Done when:` line. Larger specs live in `docs/tasks/`.
- The owner's clone is on his Windows PC; changes pushed here need a `git pull` there. Don't edit code while Copilot has unsynced changes.
- Current state, access rules and backlog: `docs/handoff.md`; dated history: `docs/development-status.md`.
- Commit under the session's default git identity (`Claude <noreply@anthropic.com>`). Don't set `user.name`/`user.email` or `--author` to Aikonn: the session signing key only verifies for the Claude identity, so Aikonn-authored commits show as Unverified on GitHub.
