import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from test_report import SNAP
from warmane_exporter.cache import ResponseCache
from warmane_exporter.export import build_full_report, main, render_full_markdown
from warmane_exporter.fingerprint import fingerprint_for_bodies, response_cache_keys
from warmane_exporter.timing import TimingLog, activate

FIX = Path(__file__).parent / "fixtures" / "real"


class ExportTests(unittest.TestCase):
    def test_missing_parts_are_listed_not_invented(self):
        r = build_full_report(SNAP, None, None, None, None)
        self.assertEqual(r["missing_sections"], ["achievements", "statistics", "reputation", "mounts", "companions"])
        self.assertIn("## Missing sections", render_full_markdown(r))

    def test_full_merge(self):
        ach = {"complete": True, "categories": [
            {"id": 92, "name": "General", "parent": None, "status": "ok", "entries": [
                {"id": 6, "title": "Level 10", "points": 10, "earned": True, "earned_date": "2025-02-22"}]},
            {"id": 14861, "name": "Classic", "parent": 96, "status": "ok", "entries": []}]}
        stats = {"complete": True, "categories": [{"id": 130, "name": "Character", "parent": None, "status": "ok",
                                                   "entries": [{"name": "Respecs", "value": "8"}]}]}
        rep = (FIX / "reputation-sample-aikka-onyxia.html").read_text(encoding="utf-8")
        mounts = (FIX / "mounts-sample-aikka-onyxia.html").read_text(encoding="utf-8")
        r = build_full_report(SNAP, ach, stats, rep, mounts)
        self.assertEqual(r["missing_sections"], [])
        self.assertEqual(r["achievements"]["summary"]["earned_points"], 10)
        md = render_full_markdown(r)
        for needle in ("## Achievements", "- Respecs: 8", "## Reputation", "Blue Wind Rider", "Mojo"):
            self.assertIn(needle, md)

    def test_export_cli_records_each_format_timing(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp) / "cache"
            snapshots = cache / "snapshots"
            snapshots.mkdir(parents=True)
            (snapshots / "x-onyxia-123.json").write_text(json.dumps(SNAP), encoding="utf-8")
            timing_log = TimingLog(Path(tmp) / "timing")
            with activate(timing_log), redirect_stderr(io.StringIO()), redirect_stdout(io.StringIO()):
                code = main(["X", "Onyxia", "--cache-dir", str(cache)])
        self.assertEqual(code, 0)
        for label in ("export JSON", "export Markdown", "export PvE HTML"):
            self.assertIn(f"X@Onyxia | {label}", timing_log.totals)

    def test_quick_export_stores_fingerprint_in_json_and_html(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache_dir = Path(tmp) / "cache"
            snapshots = cache_dir / "snapshots"
            snapshots.mkdir(parents=True)
            (snapshots / "x-onyxia-123.json").write_text(json.dumps(SNAP), encoding="utf-8")
            bodies = ("json response", "summary response", "talents response")
            response_cache = ResponseCache(cache_dir / "responses.sqlite")
            try:
                for key, body in zip(response_cache_keys("X", "Onyxia"), bodies, strict=True):
                    response_cache.put(key, key.split("|", 1)[0], body, 1.0)
            finally:
                response_cache.close()

            with redirect_stderr(io.StringIO()), redirect_stdout(io.StringIO()):
                code = main(
                    ["X", "Onyxia", "--cache-dir", str(cache_dir), "--quick"],
                    tool_version="tool-v1",
                )

            fingerprint = fingerprint_for_bodies("tool-v1", *bodies)
            report_path = cache_dir / "exports" / "x-onyxia-quick.json"
            html_path = cache_dir / "exports" / "x-onyxia-quick-pve.html"
            report = json.loads(report_path.read_text(encoding="utf-8"))
            html = html_path.read_text(encoding="utf-8")

        self.assertEqual(code, 0)
        self.assertEqual(report["fingerprint"], fingerprint)
        self.assertIn(
            f'<meta name="warmane-fingerprint" content="{fingerprint}">',
            html,
        )


if __name__ == "__main__":
    unittest.main()
