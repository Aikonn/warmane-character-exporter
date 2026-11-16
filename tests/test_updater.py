import io
import json
import tempfile
import unittest
import urllib.error
import zipfile
from pathlib import Path
from unittest.mock import patch

from warmane_exporter import updater


def archive_bytes(files, folder="warmane-character-exporter-main"):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr(f"{folder}/", b"")
        for path, content in files.items():
            archive.writestr(f"{folder}/{path}", content)
    return output.getvalue()


def commit_response(sha="abc123"):
    return json.dumps({
        "sha": sha,
        "commit": {
            "committer": {"date": "2026-11-16T10:12:00Z"},
            "message": "Update files\n\nMore details",
        },
    }).encode()


class UpdaterTests(unittest.TestCase):
    def test_git_blob_sha_matches_known_git_hash(self):
        self.assertEqual(
            updater.git_blob_sha(b"hello\n"),
            "ce013625030ba8dba906f756967f9e9ca394464a",
        )

    def test_compare_files_detects_changed_missing_and_stale_only_in_owned_dirs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "src").mkdir()
            (root / "src" / "__pycache__").mkdir()
            (root / "tests" / "__pycache__").mkdir(parents=True)
            (root / "library").mkdir()
            (root / "src" / "changed.py").write_bytes(b"old")
            (root / "src" / "stale.py").write_bytes(b"stale")
            (root / "src" / "__pycache__" / "ignored.py").write_bytes(b"ignored")
            (root / "tests" / "__pycache__" / "ignored.pyc").write_bytes(b"ignored")
            (root / "tests" / "ignored.pyc").write_bytes(b"ignored")
            (root / "library" / "extra.db").write_bytes(b"ignored")
            tree = {
                "src/changed.py": updater.git_blob_sha(b"new"),
                "src/missing.py": updater.git_blob_sha(b"missing"),
            }

            comparison = updater.compare_files(root, tree)

            self.assertEqual(comparison.changed, ["src/changed.py"])
            self.assertEqual(comparison.missing, ["src/missing.py"])
            self.assertEqual(comparison.stale, ["src/stale.py"])

    def test_check_up_to_date_and_update_available(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "README.md"
            path.write_bytes(b"same")
            payload = {
                updater.API_COMMIT_URL: commit_response(),
                updater.API_TREE_URL.format(sha="abc123"): json.dumps({
                    "truncated": False,
                    "tree": [{"type": "blob", "path": "README.md", "sha": updater.git_blob_sha(b"same")}],
                }).encode(),
            }
            calls = []

            def http_get(url):
                calls.append(url)
                return payload[url]

            result = updater.check(root, http_get)
            self.assertEqual(result.status, updater.UP_TO_DATE)
            self.assertEqual(calls, [updater.API_COMMIT_URL, updater.API_TREE_URL.format(sha="abc123")])

            payload[updater.API_TREE_URL.format(sha="abc123")] = json.dumps({
                "truncated": False,
                "tree": [{"type": "blob", "path": "README.md", "sha": updater.git_blob_sha(b"different")}],
            }).encode()
            self.assertEqual(updater.check(root, http_get).status, updater.UPDATE_AVAILABLE)

    def test_check_git_clone_resolves_loose_and_packed_refs_without_tree_request(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            git = root / ".git"
            (git / "refs" / "heads").mkdir(parents=True)
            (git / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
            (git / "refs" / "heads" / "main").write_text("local-sha\n", encoding="utf-8")
            urls = []
            result = updater.check(root, lambda url: (urls.append(url), commit_response())[1])
            self.assertEqual(result.status, updater.GIT_CLONE)
            self.assertTrue(result.behind)
            self.assertEqual(result.local_sha, "local-sha")
            self.assertEqual(urls, [updater.API_COMMIT_URL])

            (git / "refs" / "heads" / "main").unlink()
            (git / "packed-refs").write_text("# pack-refs\npacked-sha refs/heads/main\n", encoding="utf-8")
            self.assertEqual(updater.local_git_head(root), "packed-sha")

    def test_default_http_get_reports_github_rate_limit(self):
        error = urllib.error.HTTPError(
            "https://api.github.com/", 403, "rate limited",
            {"X-RateLimit-Remaining": "0"}, io.BytesIO(),
        )
        with patch("urllib.request.urlopen", side_effect=error):
            with self.assertRaisesRegex(updater.UpdateError, updater.RATE_LIMIT_MESSAGE):
                updater.default_http_get("https://api.github.com/")

    def test_check_rejects_truncated_tree(self):
        with tempfile.TemporaryDirectory() as directory:
            responses = [
                commit_response(),
                b'{"truncated":true,"tree":[]}',
            ]
            result = updater.check(Path(directory), lambda _url: responses.pop(0))
            self.assertEqual(result.status, updater.ERROR)
            self.assertIn("truncated", result.message)

    def test_extract_update_rejects_unsafe_paths_multiple_roots_and_missing_files(self):
        cases = [
            ({"../outside": b"x"}, "unsafe"),
            ({"C:/outside": b"x"}, "unsafe"),
            ({"one/a": b"x", "two/b": b"y"}, "exactly one top folder"),
            ({"repo/Start-Report.ps1": b"x"}, "missing required file"),
        ]
        for files, message in cases:
            with self.subTest(message=message), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                zip_path = root / "update.zip"
                with zipfile.ZipFile(zip_path, "w") as archive:
                    for path, content in files.items():
                        archive.writestr(path, content)
                with self.assertRaisesRegex(updater.UpdateError, message):
                    updater.extract_update(zip_path, root / "extract")

    def test_apply_update_replaces_adds_deletes_and_preserves_local_data(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            files = {
                "Start-Report.ps1": b"new launcher",
                "src/warmane_exporter/__init__.py": b"",
                "src/value.py": b"new value",
                "src/added.py": b"added",
                ".tools/python312/x": b"archive python",
                ".warmane-cache/x": b"archive cache",
                "warmane-character-exporter.config": b"archive config",
            }
            (root / "src").mkdir()
            (root / "tests").mkdir()
            (root / ".tools" / "python312").mkdir(parents=True)
            (root / ".warmane-cache").mkdir()
            (root / "library" / "acore").mkdir(parents=True)
            (root / "src" / "value.py").write_bytes(b"old value")
            (root / "tests" / "obsolete.py").write_bytes(b"stale")
            (root / ".tools" / "python312" / "x").write_bytes(b"local python")
            (root / ".warmane-cache" / "x").write_bytes(b"local cache")
            (root / "warmane-character-exporter.config").write_bytes(b"local config")
            (root / "library" / "acore" / "extra.db").write_bytes(b"local database")
            tree = [
                {"type": "blob", "path": path, "sha": updater.git_blob_sha(content)}
                for path, content in files.items()
            ]
            responses = {
                updater.API_COMMIT_URL: commit_response(),
                updater.API_TREE_URL.format(sha="abc123"): json.dumps({
                    "truncated": False,
                    "tree": tree,
                }).encode(),
                updater.ZIP_URL.format(sha="abc123"): archive_bytes(files),
            }

            result, code = updater.apply_update(root, lambda url: responses[url])

            self.assertEqual(code, 0)
            self.assertEqual(result.status, updater.UPDATED)
            self.assertEqual((root / "src" / "value.py").read_bytes(), b"new value")
            self.assertEqual((root / "src" / "added.py").read_bytes(), b"added")
            self.assertFalse((root / "tests" / "obsolete.py").exists())
            self.assertEqual((root / ".tools" / "python312" / "x").read_bytes(), b"local python")
            self.assertEqual((root / ".warmane-cache" / "x").read_bytes(), b"local cache")
            self.assertEqual((root / "warmane-character-exporter.config").read_bytes(), b"local config")
            self.assertEqual((root / "library" / "acore" / "extra.db").read_bytes(), b"local database")
            self.assertFalse((root / ".tools" / "update").exists())

    def test_apply_update_refuses_git_clone(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".git").mkdir()
            result, code = updater.apply_update(root, lambda _url: commit_response())
            self.assertEqual(code, 2)
            self.assertEqual(result.status, updater.GIT_CLONE)

    def test_apply_copy_failure_names_file_and_manual_update(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            files = {
                "Start-Report.ps1": b"launcher",
                "src/warmane_exporter/__init__.py": b"",
                "src/value.py": b"new",
            }
            tree = [
                {"type": "blob", "path": path, "sha": updater.git_blob_sha(content)}
                for path, content in files.items()
            ]
            responses = {
                updater.API_COMMIT_URL: commit_response(),
                updater.API_TREE_URL.format(sha="abc123"): json.dumps({
                    "truncated": False,
                    "tree": tree,
                }).encode(),
                updater.ZIP_URL.format(sha="abc123"): archive_bytes(files),
            }
            with patch("warmane_exporter.updater.os.replace", side_effect=OSError("disk full")):
                result, code = updater.apply_update(root, lambda url: responses[url])
            self.assertEqual(code, 1)
            self.assertEqual(result.status, updater.ERROR)
            self.assertIn("Start-Report.ps1", result.message)
            self.assertIn(updater.REPO_PAGE_URL, result.message)

    def test_main_prints_one_json_object_and_returns_success(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            responses = [
                commit_response(),
                b'{"truncated":false,"tree":[]}',
            ]
            output = io.StringIO()
            with patch("sys.stdout", output):
                code = updater.main(["check"], lambda _url: responses.pop(0), root)
            lines = output.getvalue().splitlines()
            self.assertEqual(code, 0)
            self.assertEqual(len(lines), 1)
            self.assertEqual(json.loads(lines[0])["status"], updater.UP_TO_DATE)

    def test_main_returns_error_and_git_clone_exit_codes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            def unavailable(_url):
                raise updater.UpdateError("offline")

            output = io.StringIO()
            with patch("sys.stdout", output):
                code = updater.main(["check"], unavailable, root)
            self.assertEqual(code, 1)
            self.assertEqual(json.loads(output.getvalue())["status"], updater.ERROR)

            (root / ".git").mkdir()
            output = io.StringIO()
            with patch("sys.stdout", output):
                code = updater.main(["apply"], lambda _url: commit_response(), root)
            self.assertEqual(code, 2)
            self.assertEqual(json.loads(output.getvalue())["status"], updater.GIT_CLONE)


if __name__ == "__main__":
    unittest.main()
