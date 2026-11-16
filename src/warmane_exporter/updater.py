"""Update a Download ZIP copy of the program from branch main on GitHub.

python -m warmane_exporter.updater check
python -m warmane_exporter.updater apply

Specification: docs/tasks/update-feature.md. Git is not needed: the check compares the Git
blob hash of every local file with the file tree of the latest commit on main (2 GitHub API
requests), and the update downloads that commit as a zip (1 request) and copies it over the
program folder. Requests happen only when the user runs a command (no automatic check).

Both commands print exactly one JSON object on stdout (see ``CheckResult.to_json``).
Exit codes: 0 success, 1 error (network, rate limit, bad zip, copy failed), 2 refused (the
folder is a Git clone; use git pull there).
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

OWNER = "Aikonn"
REPO = "warmane-character-exporter"
BRANCH = "main"
API_COMMIT_URL = f"https://api.github.com/repos/{OWNER}/{REPO}/commits/{BRANCH}"
API_TREE_URL = f"https://api.github.com/repos/{OWNER}/{REPO}/git/trees/{{sha}}?recursive=1"
ZIP_URL = f"https://codeload.github.com/{OWNER}/{REPO}/zip/{{sha}}"
REPO_PAGE_URL = f"https://github.com/{OWNER}/{REPO}"
USER_AGENT = "warmane-character-exporter-updater"
TIMEOUT_SECONDS = 20

# Folders fully owned by the repo: local files here that are not on main are deleted on update.
OWNED_DIRS = ("src", "tests")
# Never written or deleted by the updater, even if a zip contained them.
PROTECTED = (".git", ".tools", ".warmane-cache", "warmane-character-exporter.config")
# Files that must exist in the zip's top folder before anything is copied.
REQUIRED_IN_ZIP = ("src/warmane_exporter/__init__.py", "Start-Report.ps1")
RATE_LIMIT_MESSAGE = "GitHub request limit reached, try again in an hour."

# Status values.
UP_TO_DATE = "up_to_date"
UPDATE_AVAILABLE = "update_available"
GIT_CLONE = "git_clone"
UPDATED = "updated"
ERROR = "error"

HttpGet = Callable[[str], bytes]


class UpdateError(Exception):
    """A failure with a message meant for the user (shown as-is in the Settings window)."""


@dataclass
class LatestCommit:
    sha: str
    date: str      # ISO 8601 committer date as GitHub gives it, e.g. "2026-11-16T10:12:00Z"
    message: str   # first line of the commit message


@dataclass
class FileComparison:
    changed: list[str] = field(default_factory=list)  # on disk and in the tree, hash differs
    missing: list[str] = field(default_factory=list)  # in the tree, not on disk
    stale: list[str] = field(default_factory=list)    # on disk under OWNED_DIRS, not in the tree

    @property
    def count(self) -> int:
        return len(self.changed) + len(self.missing) + len(self.stale)


@dataclass
class CheckResult:
    status: str
    message: str
    latest: LatestCommit | None = None
    files: FileComparison = field(default_factory=FileComparison)
    local_sha: str | None = None   # Git clone only
    behind: bool | None = None     # Git clone only: local HEAD differs from latest

    def to_json(self) -> str:
        """One-line JSON object as in the spec (CLI section).

        Keys: status, message, latest ({sha, date, message} or null), changed, missing,
        stale (lists of POSIX-style relative paths, sorted), local_sha, behind.
        ``ensure_ascii=False``.
        """
        raise NotImplementedError


def default_http_get(url: str) -> bytes:
    """GET ``url`` with ``USER_AGENT`` and ``TIMEOUT_SECONDS``; follow redirects; no retries.

    Raises ``UpdateError`` with a user-facing message: ``RATE_LIMIT_MESSAGE`` for HTTP 403/429
    with header ``X-RateLimit-Remaining: 0``; "Could not reach GitHub: <reason>" for network
    errors; "GitHub answered HTTP <code>." for other HTTP errors.
    """
    raise NotImplementedError


def git_blob_sha(data: bytes) -> str:
    """Git blob hash: sha1 of ``b"blob <len>\\0" + data``, lowercase hex."""
    raise NotImplementedError


def is_git_clone(root: Path) -> bool:
    """True when ``root/.git`` exists (folder or file)."""
    raise NotImplementedError


def local_git_head(root: Path) -> str | None:
    """Commit sha of HEAD in a Git clone, read from files only (Git may not be installed).

    ``.git/HEAD`` either holds a sha (detached) or ``ref: refs/heads/<name>``; resolve the ref
    from ``.git/<ref>`` or, if that file is missing, from ``.git/packed-refs``. None when it
    cannot be resolved.
    """
    raise NotImplementedError


def fetch_latest(http_get: HttpGet) -> LatestCommit:
    """Latest commit on ``BRANCH`` from ``API_COMMIT_URL`` (sha, commit.committer.date, first line
    of commit.message). ``UpdateError`` on unexpected JSON."""
    raise NotImplementedError


def fetch_tree(http_get: HttpGet, sha: str) -> dict[str, str]:
    """``{path: blob sha}`` for every entry of type "blob" in the recursive tree of ``sha``.

    ``UpdateError`` when the response says ``"truncated": true`` (the list would be incomplete).
    """
    raise NotImplementedError


def compare_files(root: Path, tree: dict[str, str]) -> FileComparison:
    """Compare local files with ``tree`` as described in the spec (How "differs" is decided).

    Paths are POSIX-style and relative to ``root``. Stale files are looked for only under
    ``OWNED_DIRS``, skipping ``__pycache__`` folders and ``*.pyc`` files. Lists are sorted.
    """
    raise NotImplementedError


def check(root: Path, http_get: HttpGet = default_http_get) -> CheckResult:
    """Run the update check for the program folder ``root``.

    Git clone: status ``GIT_CLONE`` with ``local_sha`` and ``behind`` (1 API request; no file
    comparison). Otherwise ``UP_TO_DATE`` or ``UPDATE_AVAILABLE`` with the file lists and the
    message "Up to date." / "N files differ from the latest version.". Any ``UpdateError``
    becomes status ``ERROR`` with its message; nothing raises.
    """
    raise NotImplementedError


def extract_update(zip_path: Path, target: Path) -> Path:
    """Extract ``zip_path`` into ``target`` (emptied first) and return the single top folder.

    Raise ``UpdateError`` before extracting anything when a member name is absolute or has a
    ``..`` part, when there is not exactly one top folder, or after extracting when any of
    ``REQUIRED_IN_ZIP`` is missing under the top folder.
    """
    raise NotImplementedError


def apply_update(root: Path, http_get: HttpGet = default_http_get) -> tuple[CheckResult, int]:
    """Update ``root`` to the latest commit on main; return the result and the exit code.

    Steps as in the spec (Applying an update): refuse a Git clone (``GIT_CLONE``, 2); check;
    nothing to do when up to date (``UP_TO_DATE``, 0); download ``ZIP_URL`` for the checked sha
    into ``root/.tools/update``; ``extract_update``; copy every file through a temp file and
    ``os.replace``, skipping anything under ``PROTECTED``; delete the stale files; remove
    ``.tools/update``. Success: status ``UPDATED``, message "Updated to <date> \\"<message>\\".",
    exit 0. Any failure: status ``ERROR``, exit 1; a failed copy names the file and adds
    "Use the manual update: <REPO_PAGE_URL>".
    """
    raise NotImplementedError


def program_root() -> Path:
    """The program folder: two levels above this package (``<root>/src/warmane_exporter``)."""
    return Path(__file__).resolve().parents[2]


def main(argv: list[str] | None = None, http_get: HttpGet = default_http_get,
         root: Path | None = None) -> int:
    """CLI: ``check`` or ``apply`` on ``root`` (default ``program_root()``; tests pass a temp folder).

    Writes exactly one JSON line (``CheckResult.to_json``) to stdout as UTF-8 and returns the
    exit code: ``check`` gives 0 unless the status is ``ERROR`` (1); ``apply`` gives the code
    from ``apply_update``. Argument errors exit 2 through argparse.
    """
    raise NotImplementedError


if __name__ == "__main__":
    sys.exit(main())
