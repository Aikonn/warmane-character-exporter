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
import hashlib
import http.client
import json
import os
import shutil
import stat
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath, PureWindowsPath
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
        latest = None
        if self.latest is not None:
            latest = {
                "sha": self.latest.sha,
                "date": self.latest.date,
                "message": self.latest.message,
            }
        return json.dumps({
            "status": self.status,
            "message": self.message,
            "latest": latest,
            "changed": self.files.changed,
            "missing": self.files.missing,
            "stale": self.files.stale,
            "local_sha": self.local_sha,
            "behind": self.behind,
        }, ensure_ascii=False, separators=(",", ":"))


def default_http_get(url: str) -> bytes:
    """GET ``url`` with ``USER_AGENT`` and ``TIMEOUT_SECONDS``; follow redirects; no retries.

    Raises ``UpdateError`` with a user-facing message: ``RATE_LIMIT_MESSAGE`` for HTTP 403/429
    with header ``X-RateLimit-Remaining: 0``; "Could not reach GitHub: <reason>" for network
    errors; "GitHub answered HTTP <code>." for other HTTP errors.
    """
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            return response.read()
    except urllib.error.HTTPError as exc:
        remaining = exc.headers.get("X-RateLimit-Remaining", "") if exc.headers else ""
        if exc.code in (403, 429) and remaining == "0":
            raise UpdateError(RATE_LIMIT_MESSAGE) from exc
        raise UpdateError(f"GitHub answered HTTP {exc.code}.") from exc
    except (urllib.error.URLError, TimeoutError, OSError, http.client.HTTPException) as exc:
        reason = getattr(exc, "reason", exc)
        raise UpdateError(f"Could not reach GitHub: {reason}") from exc


def git_blob_sha(data: bytes) -> str:
    """Git blob hash: sha1 of ``b"blob <len>\\0" + data``, lowercase hex."""
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()


def is_git_clone(root: Path) -> bool:
    """True when ``root/.git`` exists (folder or file)."""
    git_dir = root / ".git"
    return git_dir.exists() or git_dir.is_symlink()


def local_git_head(root: Path) -> str | None:
    """Commit sha of HEAD in a Git clone, read from files only (Git may not be installed).

    ``.git/HEAD`` either holds a sha (detached) or ``ref: refs/heads/<name>``; resolve the ref
    from ``.git/<ref>`` or, if that file is missing, from ``.git/packed-refs``. None when it
    cannot be resolved.
    """
    git_path = root / ".git"
    if git_path.is_dir():
        git_dir = git_path
    elif git_path.is_file():
        try:
            pointer = git_path.read_text(encoding="utf-8").strip()
        except OSError:
            return None
        if not pointer.startswith("gitdir: "):
            return None
        git_dir = Path(pointer[8:])
        if not git_dir.is_absolute():
            git_dir = (root / git_dir).resolve()
    else:
        return None

    try:
        head = (git_dir / "HEAD").read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not head.startswith("ref: "):
        return head or None

    ref = head[5:]
    if (not ref or "\\" in ref or PurePosixPath(ref).is_absolute()
            or PureWindowsPath(ref).is_absolute() or PureWindowsPath(ref).drive
            or ".." in PurePosixPath(ref).parts):
        return None
    try:
        return (git_dir / Path(*PurePosixPath(ref).parts)).read_text(encoding="utf-8").strip() or None
    except OSError:
        pass

    try:
        packed_refs = (git_dir / "packed-refs").read_text(encoding="utf-8")
    except OSError:
        return None
    for line in packed_refs.splitlines():
        if not line or line.startswith(("#", "^")):
            continue
        parts = line.split(" ", 1)
        if len(parts) == 2 and parts[1] == ref:
            return parts[0]
    return None


def _decode_json(body: bytes, description: str):
    try:
        return json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise UpdateError(f"GitHub returned an invalid {description} response.") from exc


def fetch_latest(http_get: HttpGet) -> LatestCommit:
    """Latest commit on ``BRANCH`` from ``API_COMMIT_URL`` (sha, commit.committer.date, first line
    of commit.message). ``UpdateError`` on unexpected JSON."""
    payload = _decode_json(http_get(API_COMMIT_URL), "commit")
    try:
        commit = payload["commit"]
        message = commit["message"].splitlines()[0]
        return LatestCommit(
            sha=payload["sha"],
            date=commit["committer"]["date"],
            message=message,
        )
    except (KeyError, IndexError, TypeError, AttributeError) as exc:
        raise UpdateError("GitHub returned an unexpected commit response.") from exc


def fetch_tree(http_get: HttpGet, sha: str) -> dict[str, str]:
    """``{path: blob sha}`` for every entry of type "blob" in the recursive tree of ``sha``.

    ``UpdateError`` when the response says ``"truncated": true`` (the list would be incomplete).
    """
    payload = _decode_json(http_get(API_TREE_URL.format(sha=sha)), "tree")
    if not isinstance(payload, dict) or payload.get("truncated") is True:
        raise UpdateError("GitHub returned a truncated or invalid file tree.")
    entries = payload.get("tree")
    if not isinstance(entries, list):
        raise UpdateError("GitHub returned an unexpected file tree response.")
    result = {}
    for entry in entries:
        if not isinstance(entry, dict) or entry.get("type") != "blob":
            continue
        path = entry.get("path")
        blob_sha = entry.get("sha")
        if not isinstance(path, str) or not path or not isinstance(blob_sha, str):
            raise UpdateError("GitHub returned an invalid file entry.")
        posix_path = PurePosixPath(path)
        if (posix_path.is_absolute() or PureWindowsPath(path).is_absolute()
                or PureWindowsPath(path).drive or "\\" in path
                or any(":" in part for part in posix_path.parts)
                or any(part in ("", ".", "..") for part in path.split("/"))):
            raise UpdateError("GitHub returned an unsafe file path.")
        result[path] = blob_sha
    return result


def compare_files(root: Path, tree: dict[str, str]) -> FileComparison:
    """Compare local files with ``tree`` as described in the spec (How "differs" is decided).

    Paths are POSIX-style and relative to ``root``. Stale files are looked for only under
    ``OWNED_DIRS``, skipping ``__pycache__`` folders and ``*.pyc`` files. Lists are sorted.
    """
    comparison = FileComparison()
    for path, expected_sha in tree.items():
        local_path = root.joinpath(*PurePosixPath(path).parts)
        if not local_path.is_file():
            comparison.missing.append(path)
        elif git_blob_sha(local_path.read_bytes()) != expected_sha:
            comparison.changed.append(path)

    tracked = set(tree)
    for owned_dir in OWNED_DIRS:
        directory = root / owned_dir
        if not directory.exists():
            continue
        for local_path in directory.rglob("*"):
            if not local_path.is_file() or "__pycache__" in local_path.parts or local_path.suffix == ".pyc":
                continue
            relative = local_path.relative_to(root).as_posix()
            if relative not in tracked:
                comparison.stale.append(relative)

    comparison.changed.sort()
    comparison.missing.sort()
    comparison.stale.sort()
    return comparison


def check(root: Path, http_get: HttpGet = default_http_get) -> CheckResult:
    """Run the update check for the program folder ``root``.

    Git clone: status ``GIT_CLONE`` with ``local_sha`` and ``behind`` (1 API request; no file
    comparison). Otherwise ``UP_TO_DATE`` or ``UPDATE_AVAILABLE`` with the file lists and the
    message "Up to date." / "N files differ from the latest version.". Any ``UpdateError``
    becomes status ``ERROR`` with its message; nothing raises.
    """
    try:
        latest = fetch_latest(http_get)
        if is_git_clone(root):
            local_sha = local_git_head(root)
            return CheckResult(
                status=GIT_CLONE,
                message="This folder is a Git clone. Use git pull.",
                latest=latest,
                local_sha=local_sha,
                behind=local_sha != latest.sha,
            )
        files = compare_files(root, fetch_tree(http_get, latest.sha))
        if files.count == 0:
            return CheckResult(status=UP_TO_DATE, message="Up to date.", latest=latest, files=files)
        return CheckResult(
            status=UPDATE_AVAILABLE,
            message=f"{files.count} files differ from the latest version.",
            latest=latest,
            files=files,
        )
    except UpdateError as exc:
        return CheckResult(status=ERROR, message=str(exc))
    except OSError as exc:
        return CheckResult(status=ERROR, message=f"Could not read local files: {exc}")


def extract_update(zip_path: Path, target: Path) -> Path:
    """Extract ``zip_path`` into ``target`` (emptied first) and return the single top folder.

    Raise ``UpdateError`` before extracting anything when a member name is absolute or has a
    ``..`` part, when there is not exactly one top folder, or after extracting when any of
    ``REQUIRED_IN_ZIP`` is missing under the top folder.
    """
    if target.is_symlink() or target.is_file():
        target.unlink()
    elif target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)

    try:
        with zipfile.ZipFile(zip_path) as archive:
            members = archive.infolist()
            top_folders = set()
            for member in members:
                name = member.filename
                windows_name = PureWindowsPath(name)
                parts = name.split("/")
                if name.endswith("/"):
                    parts = parts[:-1]
                if (not name or name.startswith("/") or windows_name.is_absolute()
                        or windows_name.drive or "\\" in name
                        or any(":" in part for part in parts)
                        or any(part in ("", ".", "..") for part in parts)):
                    raise UpdateError("The update ZIP contains an unsafe path.")
                if len(parts) < 2 and not (len(parts) == 1 and member.is_dir()):
                    raise UpdateError("The update ZIP must contain exactly one top folder.")
                top_folders.add(parts[0])
                if stat.S_ISLNK(member.external_attr >> 16):
                    raise UpdateError("The update ZIP contains a symbolic link.")
            if len(top_folders) != 1:
                raise UpdateError("The update ZIP must contain exactly one top folder.")
            top_folder = target / next(iter(top_folders))
            archive.extractall(target)
    except zipfile.BadZipFile as exc:
        raise UpdateError("GitHub returned an invalid update ZIP.") from exc
    except (NotImplementedError, RuntimeError) as exc:
        raise UpdateError(f"Could not extract the update ZIP: {exc}") from exc
    except OSError as exc:
        raise UpdateError(f"Could not extract the update ZIP: {exc}") from exc

    for required in REQUIRED_IN_ZIP:
        if not top_folder.joinpath(*PurePosixPath(required).parts).is_file():
            raise UpdateError(f"The update ZIP is missing required file {required}.")
    return top_folder


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
    result = check(root, http_get)
    if result.status == GIT_CLONE:
        return result, 2
    if result.status == ERROR:
        return result, 1
    if result.status == UP_TO_DATE:
        return result, 0

    update_dir = root / ".tools" / "update"
    failure = None
    try:
        if update_dir.exists():
            shutil.rmtree(update_dir)
        update_dir.mkdir(parents=True)
        zip_path = update_dir / "update.zip"
        if result.latest is None:
            raise UpdateError("GitHub did not provide the checked commit.")
        zip_path.write_bytes(http_get(ZIP_URL.format(sha=result.latest.sha)))
        extracted = extract_update(zip_path, update_dir / "extract")

        for source in extracted.rglob("*"):
            if not source.is_file():
                continue
            relative = source.relative_to(extracted).as_posix()
            protected_path = relative.casefold()
            if any(
                protected_path == item.casefold()
                or protected_path.startswith(item.casefold() + "/")
                for item in PROTECTED
            ):
                continue
            destination = root.joinpath(*PurePosixPath(relative).parts)
            temporary = None
            try:
                destination.parent.mkdir(parents=True, exist_ok=True)
                descriptor, temporary_name = tempfile.mkstemp(prefix=".update-", dir=destination.parent)
                temporary = Path(temporary_name)
                with os.fdopen(descriptor, "wb") as stream:
                    stream.write(source.read_bytes())
                os.replace(temporary, destination)
            except OSError as exc:
                if temporary is not None:
                    try:
                        temporary.unlink(missing_ok=True)
                    except OSError as cleanup_error:
                        cleanup_message = f" Temporary file remains at {temporary}: {cleanup_error}"
                    else:
                        cleanup_message = ""
                else:
                    cleanup_message = ""
                raise UpdateError(
                    f"Could not update {relative}: {exc}.{cleanup_message} "
                    f"Use the manual update: {REPO_PAGE_URL}"
                ) from exc

        for relative in result.files.stale:
            stale_path = root.joinpath(*PurePosixPath(relative).parts)
            if stale_path.is_file():
                stale_path.unlink()
    except UpdateError as exc:
        failure = str(exc)
    except OSError as exc:
        failure = f"Could not apply the update: {exc} Use the manual update: {REPO_PAGE_URL}"

    cleanup_failure = None
    if update_dir.exists():
        try:
            shutil.rmtree(update_dir)
        except OSError as exc:
            cleanup_failure = f"Could not remove updater temporary files: {exc}"
    if failure:
        return CheckResult(status=ERROR, message=failure, latest=result.latest, files=result.files), 1
    if cleanup_failure:
        return CheckResult(
            status=ERROR, message=cleanup_failure, latest=result.latest, files=result.files
        ), 1
    assert result.latest is not None
    return CheckResult(
        status=UPDATED,
        message=f'Updated to {result.latest.date} "{result.latest.message}".',
        latest=result.latest,
        files=result.files,
    ), 0


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
    parser = argparse.ArgumentParser(description="Check for or apply program updates from GitHub.")
    parser.add_argument("command", choices=("check", "apply"))
    args = parser.parse_args(argv)
    program = root if root is not None else program_root()
    if args.command == "check":
        result = check(program, http_get)
        exit_code = 1 if result.status == ERROR else 0
    else:
        result, exit_code = apply_update(program, http_get)
    output = result.to_json() + "\n"
    stdout_buffer = getattr(sys.stdout, "buffer", None)
    if stdout_buffer is None:
        sys.stdout.write(output)
    else:
        stdout_buffer.write(output.encode("utf-8"))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
