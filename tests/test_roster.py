import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock
from contextlib import redirect_stderr, redirect_stdout
import io

from warmane_exporter.pve_report import build_pve_report, render_html as render_pve_html
from warmane_exporter import progress
from warmane_exporter.roster import (
    FAILED,
    NOT_FOUND,
    NOT_RUN,
    OK,
    RosterRow,
    build_row,
    parse_names,
    placeholder_row,
    render_summary,
    run_roster,
    sort_rows,
    summary_file_name,
    STOP_NOTE,
    main,
)


FIXTURES = Path(__file__).parent / "fixtures"


class ParseNamesTests(unittest.TestCase):
    def test_trims_blank_lines_and_deduplicates_case_insensitively(self):
        result = parse_names(" \n alice \nALICE\n  BoB  \n", "Onyxia")
        self.assertEqual(result.names, ["Alice", "Bob"])
        self.assertEqual(result.errors, [])

    def test_accepts_matching_realm_suffix_and_rejects_other_realm(self):
        result = parse_names("Alice-ONYXIA\nBob-Icecrown\nCara", "Onyxia")
        self.assertEqual(result.names, ["Alice", "Cara"])
        self.assertEqual(len(result.errors), 1)
        self.assertIn("Line 2", result.errors[0])
        self.assertIn("Bob-Icecrown", result.errors[0])

    def test_rejects_nonletter_names_but_accepts_accented_letters(self):
        result = parse_names("Qzx1\nTwo Words\nÉLODIE\ne\u0301lodie", "Onyxia")
        self.assertEqual(result.names, ["Élodie"])
        self.assertEqual(len(result.errors), 2)

    def test_rejects_more_than_40_distinct_names(self):
        alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

        def name_for(index):
            letters = ""
            while index:
                index, remainder = divmod(index - 1, len(alphabet))
                letters = alphabet[remainder] + letters
            return "Name" + letters

        result = parse_names("\n".join(name_for(i) for i in range(1, 42)), "Onyxia")
        self.assertEqual(result.names, [])
        self.assertEqual(len(result.errors), 1)
        self.assertIn("40", result.errors[0])
        self.assertIn("Line 41", result.errors[0])
        self.assertIn("NameAO", result.errors[0])


class RosterRowTests(unittest.TestCase):
    def setUp(self):
        self.report = json.loads((FIXTURES / "synthetic" / "roster-report-synthetic.json").read_text(encoding="utf-8"))

    def test_uses_pve_report_gearscore_checks_and_specialization_labels(self):
        row = build_row(self.report, "Mélora-Onyxia-quick-pve.html", from_cache=True)
        pve = build_pve_report(self.report)

        self.assertEqual(row.status, OK)
        self.assertEqual(row.name, self.report["identity"]["name"])
        self.assertEqual(row.class_name, self.report["identity"]["class"])
        self.assertEqual(row.main_trees, ["Discipline", "-"])
        self.assertEqual(row.gearscore, pve["gearscore"]["gearscore"])
        self.assertEqual(row.average_item_level, pve["gearscore"]["average_item_level"])
        self.assertEqual(row.issues, len(pve["checks"]["issues"]))
        self.assertEqual(row.warnings, len(pve["checks"]["warnings"]))
        self.assertEqual(
            row.issue_texts,
            [
                f"{issue['slot']}: {issue['text']}" if issue.get("slot") is not None else issue["text"]
                for issue in pve["checks"]["issues"]
            ],
        )
        self.assertEqual(row.data_time, self.report["snapshot_time"])
        self.assertTrue(row.from_cache)

    def test_derives_main_tree_and_pads_a_missing_second_spec(self):
        report = json.loads(json.dumps(self.report))
        report["specializations"] = [{
            "label": None,
            "split": [14, 0, 57],
            "trees": ["Discipline", "Holy", "Shadow"],
        }]

        row = build_row(report, "Mélora-Onyxia-quick-pve.html", from_cache=False)
        html = render_summary([row], "Onyxia", datetime(2026, 11, 15, 10, 30))

        self.assertEqual(row.main_trees, ["Shadow", "-"])
        self.assertIn('<td data-sort="shadow / -">Shadow / -</td>', html)

    def test_build_row_keeps_all_issue_texts_in_check_order(self):
        issues = [{"text": "first"}, {"text": "second"}, {"text": "third"}]
        with mock.patch("warmane_exporter.roster.run_checks", return_value={
            "issues": issues,
            "warnings": [],
        }):
            row = build_row(self.report, "Mélora-Onyxia-quick-pve.html", from_cache=False)

        self.assertEqual(row.issue_texts, ["first", "second", "third"])

    def test_build_row_prefixes_gear_issue_but_not_spec_issue(self):
        report = json.loads(json.dumps(self.report))
        report["specializations"][0]["split"] = [57, 12, 0]

        row = build_row(report, "Mélora-Onyxia-quick-pve.html", from_cache=False)

        self.assertEqual(row.issue_texts, [
            "Head: No enchant.",
            "2 unspent talent point(s) (69 of 71 spent).",
        ])

    def test_placeholder_rows_keep_identity_and_armory_link_only(self):
        for status in (NOT_FOUND, NOT_RUN, FAILED):
            with self.subTest(status=status):
                row = placeholder_row("Alice", "Onyxia", status, "details")
                self.assertEqual((row.name, row.realm, row.status), ("Alice", "Onyxia", status))
                self.assertEqual(row.armory_url, "https://armory.warmane.com/character/Alice/Onyxia/summary")
                self.assertIsNone(row.class_name)
                self.assertIsNone(row.gearscore)
                self.assertIsNone(row.issues)

    def test_sort_rows_case_insensitively(self):
        rows = [placeholder_row("zara", "Onyxia", NOT_RUN), placeholder_row("Alice", "Onyxia", NOT_RUN),
                placeholder_row("bOb", "Onyxia", NOT_RUN)]
        self.assertEqual([row.name for row in sort_rows(rows)], ["Alice", "bOb", "zara"])


class SummaryRenderingTests(unittest.TestCase):
    def test_summary_file_name_uses_local_timestamp(self):
        self.assertEqual(summary_file_name(datetime(2026, 11, 15, 9, 7)), "raid-2026-11-15-0907.html")

    def test_render_summary_escapes_each_issue_in_the_list(self):
        row = RosterRow(
            name="A<b>",
            realm="Onyxia",
            status=OK,
            class_name="Priest",
            main_trees=["Holy"],
            gearscore=123,
            average_item_level=200,
            issues=2,
            warnings=0,
            issue_texts=["<Head &>: Missing <enchant>", "Second & final"],
            report_file="A-b-Onyxia-quick-pve.html",
            armory_url="https://armory.warmane.com/character/A%3Cb%3E/Onyxia/summary",
            from_cache=False,
        )
        not_found = placeholder_row("Absent", "Onyxia", NOT_FOUND)
        html = render_summary([row, not_found], "Onyxia", datetime(2026, 11, 15, 10, 30))
        not_found_html = next(line for line in html.splitlines() if 'data-sort="absent">Absent</td>' in line)

        self.assertIn("A&lt;b&gt;", html)
        self.assertIn("&lt;Head &amp;&gt;: Missing &lt;enchant&gt;", html)
        self.assertIn("Missing &lt;enchant&gt;", html)
        self.assertIn(
            '<div class="issues"><div>&lt;Head &amp;&gt;: Missing &lt;enchant&gt;</div>'
            '<div>Second &amp; final</div></div>',
            html,
        )
        self.assertNotIn("A<b>", html)
        self.assertNotIn("Missing <enchant>", html)
        self.assertNotIn("<ul", html)
        self.assertNotIn("<li", html)
        self.assertIn("characters: 2; from cache: 0; not OK: 1", html)
        self.assertIn('href="A-b-Onyxia-quick-pve.html"', html)
        self.assertIn("https://armory.warmane.com/character/A%3Cb%3E/Onyxia/summary", html)
        self.assertIn("<th>Issues list</th>", html)
        self.assertEqual(html.count("<script>"), 1)
        self.assertEqual(html.count("</script>"), 1)
        pve_html = render_pve_html(build_pve_report({"identity": {"name": "X", "realm": "Onyxia"}}))
        self.assertEqual(pve_html.count("<script"), 0)
        self.assertEqual(not_found_html.count("<td"), 11)
        self.assertEqual(not_found_html.count("<td></td>"), 1)
        self.assertIn('<tr class="not-ok"><td data-sort="absent">Absent</td>', not_found_html)
        self.assertIn('<span class="status">not found: not found</span>', not_found_html)
        self.assertIn(".status{color:#666;font-style:italic}", html)
        self.assertIn('<a href="https://armory.warmane.com/character/Absent/Onyxia/summary">Armory</a>', not_found_html)

    def test_data_age_format_is_zero_padded_for_cached_and_fresh_rows(self):
        rows = [
            RosterRow(name="Cached", realm="Onyxia", status=OK, data_time=1234567890, from_cache=True),
            RosterRow(name="Fresh", realm="Onyxia", status=OK, data_time=1234567890, from_cache=False),
        ]
        with mock.patch("warmane_exporter.roster.datetime") as local_datetime:
            local_datetime.fromtimestamp.return_value = datetime(2026, 1, 6, 9, 4)
            html = render_summary(rows, "Onyxia", datetime(2026, 11, 15, 10, 30))

        self.assertIn('data-sort="1234567890">2026-01-06 09:04 (from cache)</td>', html)
        self.assertIn('data-sort="1234567890">2026-01-06 09:04 (fresh)</td>', html)
        self.assertEqual(local_datetime.fromtimestamp.call_count, 2)

    def test_sortable_cells_have_text_numeric_and_epoch_sort_keys(self):
        row = RosterRow(
            name="Alpha",
            realm="Onyxia",
            status=OK,
            class_name="Priest",
            main_trees=["Holy", "Discipline"],
            gearscore=4800,
            average_item_level=245.5,
            issues=2,
            warnings=3,
            issue_texts=["An issue"],
            report_file="Alpha-Onyxia-quick-pve.html",
            armory_url="https://armory.warmane.com/character/Alpha/Onyxia/summary",
            data_time=1234567890,
            from_cache=True,
        )
        html = render_summary([row], "Onyxia", datetime(2026, 11, 15, 10, 30))

        self.assertIn(
            '<td data-sort="alpha">Alpha</td><td class="cls-priest" data-sort="priest">Priest</td>'
            '<td data-sort="holy / discipline">Holy / Discipline</td>'
            '<td data-sort="4800">4800</td><td data-sort="245.5">245.5</td>'
            '<td data-sort="2"><span class="count-issue">2</span></td>'
            '<td data-sort="3"><span class="count-warn">3</span></td>',
            html,
        )
        self.assertIn('<td data-sort="1234567890">', html)
        for heading in ("Issues list", "Report", "Armory"):
            self.assertIn(f"<th>{heading}</th>", html)
            self.assertNotIn(f'<th class="sortable" data-type="text">{heading}</th>', html)
            self.assertNotIn(f'<th class="sortable" data-type="num">{heading}</th>', html)
        self.assertIn(".sortable{cursor:pointer}", html)

    def test_class_colors_use_the_wotlk_335_palette(self):
        palette = {
            "Death Knight": ("cls-death-knight", "#C41F3B", "#fff"),
            "Druid": ("cls-druid", "#FF7D0A", "#111"),
            "Hunter": ("cls-hunter", "#ABD473", "#111"),
            "Mage": ("cls-mage", "#69CCF0", "#111"),
            "Paladin": ("cls-paladin", "#F58CBA", "#111"),
            "Priest": ("cls-priest", "#FFFFFF", "#111"),
            "Rogue": ("cls-rogue", "#FFF569", "#111"),
            "Shaman": ("cls-shaman", "#0070DE", "#fff"),
            "Warlock": ("cls-warlock", "#9482C9", "#111"),
            "Warrior": ("cls-warrior", "#C79C6E", "#111"),
        }
        rows = [
            RosterRow(name=name, realm="Onyxia", status=OK, class_name=name)
            for name in palette
        ]
        html = render_summary(rows, "Onyxia", datetime(2026, 11, 15, 10, 30))

        for class_name, (css_class, background, foreground) in palette.items():
            with self.subTest(class_name=class_name):
                self.assertIn(
                    f'<td class="{css_class}" data-sort="{class_name.casefold()}">{class_name}</td>',
                    html,
                )
                self.assertIn(
                    f".{css_class}{{background:{background};color:{foreground}}}",
                    html,
                )
                self.assertEqual(html.count(f".{css_class}{{"), 1)

        pve_html = render_pve_html(build_pve_report({"identity": {"name": "X", "realm": "Onyxia"}}))
        self.assertNotIn("cls-", pve_html)

    def test_unknown_or_missing_class_has_no_color_class(self):
        rows = [
            RosterRow(name="Unknown", realm="Onyxia", status=OK, class_name="Evoker"),
            RosterRow(name="Missing", realm="Onyxia", status=OK),
        ]
        html = render_summary(rows, "Onyxia", datetime(2026, 11, 15, 10, 30))
        unknown_row = next(line for line in html.splitlines() if 'data-sort="unknown">Unknown' in line)
        missing_row = next(line for line in html.splitlines() if 'data-sort="missing">Missing' in line)

        self.assertIn('<td data-sort="evoker">Evoker</td>', unknown_row)
        self.assertIn('<td data-sort=""></td>', missing_row)
        self.assertNotIn('class="cls-', unknown_row)
        self.assertNotIn('class="cls-', missing_row)

    def test_count_classes_for_zero_low_and_high_counts(self):
        rows = [
            RosterRow(name="Zero", realm="Onyxia", status=OK, issues=0, warnings=0),
            RosterRow(name="Low", realm="Onyxia", status=OK, issues=1, warnings=3),
            RosterRow(name="High", realm="Onyxia", status=OK, issues=4, warnings=4),
        ]
        html = render_summary(rows, "Onyxia", datetime(2026, 11, 15, 10, 30))

        self.assertIn(
            '<td data-sort="0">0</td><td data-sort="0">0</td><td></td>',
            html,
        )
        self.assertIn(
            '<td data-sort="1"><span class="count-issue">1</span></td>'
            '<td data-sort="3"><span class="count-warn">3</span></td><td></td>',
            html,
        )
        self.assertIn(
            '<td data-sort="4"><span class="count-issue count-high">4</span></td>'
            '<td data-sort="4"><span class="count-warn count-high">4</span></td><td></td>',
            html,
        )
        self.assertIn(".count-issue{color:#b00020}", html)
        self.assertIn(".count-warn{color:#a65a00}", html)
        self.assertIn(".count-high{font-weight:700}", html)
        self.assertIn(".issues{font-size:.8em;margin:.1em 0}", html)


class RosterRunTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.cache = self.root / "cache"
        self.output = self.root / "output"
        self.fixture = json.loads(
            (FIXTURES / "synthetic" / "roster-report-synthetic.json").read_text(encoding="utf-8")
        )

    def tearDown(self):
        self.temp.cleanup()

    def seed_success(self, name):
        exports = self.cache / "exports"
        snapshots = self.cache / "snapshots"
        exports.mkdir(parents=True, exist_ok=True)
        snapshots.mkdir(parents=True, exist_ok=True)
        report = json.loads(json.dumps(self.fixture))
        report["identity"]["name"] = name
        report["identity"]["realm"] = "Onyxia"
        stem = f"{name.lower()}-onyxia-quick"
        (exports / f"{stem}.json").write_text(json.dumps(report), encoding="utf-8")
        (exports / f"{stem}-pve.html").write_text(f"<html>{name}</html>", encoding="utf-8")
        snapshot = {
            "sections": {
                key: {"origin": "cache"}
                for key in ("json_summary", "html_summary", "talents")
            }
        }
        (snapshots / f"{name.lower()}-onyxia-123.json").write_text(
            json.dumps(snapshot), encoding="utf-8"
        )

    def test_continues_after_not_found_and_failed_character(self):
        self.seed_success("Alice")
        self.seed_success("Bob")

        def fake_run(name, realm, cache_dir, refresh, offline, full=False, quick=False,
                     max_age_minutes=15, start_progress=True):
            self.assertEqual(max_age_minutes, 120)
            self.assertFalse(start_progress)
            return {"Alice": 0, "Missing": 3, "Broken": 1, "Bob": 0}[name]

        with mock.patch("warmane_exporter.run.run_character", side_effect=fake_run) as runner:
            rows, summary = run_roster(
                ["Alice", "Missing", "Broken", "Bob"], "Onyxia", self.output,
                str(self.cache), False, 120,
            )

        self.assertEqual([row.status for row in rows], [OK, NOT_FOUND, FAILED, OK])
        self.assertEqual(runner.call_count, 4)
        self.assertTrue((self.output / "alice-onyxia-quick-pve.html").exists())
        self.assertTrue((self.output / "bob-onyxia-quick-pve.html").exists())
        summary_text = summary.read_text(encoding="utf-8")
        self.assertIn("not found: Character does not exist.", summary_text)
        self.assertIn("failed: Character run failed (exit code 1).", summary_text)
        self.assertEqual(list(self.output.glob(".*.tmp")), [])

    def test_progress_percent_never_decreases_across_two_characters(self):
        self.seed_success("Alice")
        self.seed_success("Bob")

        def fake_run(name, realm, cache_dir, refresh, offline, full=False, quick=False,
                     max_age_minutes=15, start_progress=True):
            self.assertFalse(start_progress)
            progress.advance(f"{name} snapshot", 3)
            progress.advance(f"{name} export")
            return 0

        with (
            mock.patch.dict("os.environ", {"WARMANE_PROGRESS": "1"}),
            mock.patch("warmane_exporter.run.run_character", side_effect=fake_run) as runner,
            redirect_stdout(io.StringIO()) as output,
        ):
            rows, summary = run_roster(
                ["Alice", "Bob"], "Onyxia", self.output, str(self.cache), False, 120,
            )

        percentages = [
            int(line.split("|", 2)[1])
            for line in output.getvalue().splitlines()
            if line.startswith("PROGRESS|")
        ]
        progress_lines = output.getvalue().splitlines()
        self.assertEqual(percentages, sorted(percentages))
        self.assertEqual(percentages[-1], 100)
        first_note = "PROGRESS|0|Character 1 of 2: Alice"
        first_snapshot = "PROGRESS|37|Alice snapshot"
        self.assertLess(progress_lines.index(first_note), progress_lines.index(first_snapshot))
        self.assertIn("PROGRESS|50|Character 2 of 2: Bob", output.getvalue())
        self.assertEqual([row.status for row in rows], [OK, OK])
        self.assertTrue(summary.exists())
        self.assertEqual(runner.call_count, 2)

    def test_stops_after_exit_four_and_writes_remaining_not_run_rows(self):
        self.seed_success("Alice")

        with mock.patch(
            "warmane_exporter.run.run_character",
            side_effect=[0, 4],
        ) as runner:
            rows, summary = run_roster(
                ["Alice", "Blocked", "Later"], "Onyxia", self.output,
                str(self.cache), False, 120,
            )

        self.assertEqual([row.status for row in rows], [OK, FAILED, NOT_RUN])
        self.assertEqual(rows[1].note, STOP_NOTE)
        self.assertEqual(runner.call_count, 2)
        self.assertTrue(summary.exists())
        html = summary.read_text(encoding="utf-8")
        self.assertIn("not run: An earlier character stopped the roster.", html)
        self.assertTrue((self.output / "alice-onyxia-quick-pve.html").exists())

    def test_cli_exit_codes_and_max_age_argument(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "summary.html"
            args = ["--realm", "Onyxia", "--names", "Alice", "--output-dir", tmp,
                    "--max-age-minutes", "90"]
            with mock.patch("warmane_exporter.roster.run_roster", return_value=([], output)) as runner:
                with redirect_stdout(io.StringIO()):
                    self.assertEqual(main(args), 0)
                self.assertEqual(runner.call_args.args[-1], 90)
            with mock.patch("warmane_exporter.roster.run_roster", return_value=([], output)) as runner:
                with redirect_stdout(io.StringIO()):
                    self.assertEqual(main(args + ["--timing"]), 0)
                self.assertTrue(runner.call_args.kwargs["timing"])
            with mock.patch(
                "warmane_exporter.roster.run_roster",
                return_value=([placeholder_row("Alice", "Onyxia", FAILED, STOP_NOTE)], output),
            ):
                with redirect_stdout(io.StringIO()):
                    self.assertEqual(main(args), 1)
            with mock.patch("warmane_exporter.roster.run_roster") as runner:
                with redirect_stdout(io.StringIO()):
                    self.assertEqual(main([
                        "--realm", "Onyxia", "--names", "A1", "--output-dir", tmp,
                    ]), 2)
                runner.assert_not_called()

    def test_timing_off_emits_no_timing_output(self):
        self.seed_success("Alice")
        stderr = io.StringIO()
        with mock.patch.dict("os.environ", {"WARMANE_TIMING": ""}), \
             mock.patch("warmane_exporter.run.run_character", return_value=0), \
             redirect_stderr(stderr):
            run_roster(["Alice"], "Onyxia", self.output, str(self.cache), False, 120)
        self.assertEqual(stderr.getvalue(), "")
        self.assertEqual(list(self.cache.glob("timing-*.log")), [])

    def test_timing_logs_steps_to_stderr_and_file_when_enabled(self):
        self.seed_success("Alice")
        stderr = io.StringIO()
        with mock.patch.dict("os.environ", {"WARMANE_TIMING": "1"}), \
             mock.patch("warmane_exporter.run.run_character", return_value=0), \
             redirect_stderr(stderr):
            run_roster(["Alice"], "Onyxia", self.output, str(self.cache), False, 120)

        lines = stderr.getvalue().splitlines()
        self.assertTrue(any("Alice@Onyxia | total per character" in line for line in lines))
        self.assertTrue(any("Alice@Onyxia | copy to output folder" in line for line in lines))
        self.assertTrue(any("summary rendering" in line for line in lines))
        self.assertTrue(any("total run" in line for line in lines))
        log_files = list(self.cache.glob("timing-*.log"))
        self.assertEqual(len(log_files), 1)
        self.assertRegex(log_files[0].name, r"^timing-\d{8}-\d{4}\.log$")
        self.assertEqual(log_files[0].read_text(encoding="utf-8").splitlines(), lines)

    def test_cli_reads_names_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            names_file = Path(tmp) / "names.txt"
            names_file.write_text("Alice\nBob\n", encoding="utf-8")
            output = Path(tmp) / "summary.html"
            with mock.patch("warmane_exporter.roster.run_roster", return_value=([], output)) as runner:
                with redirect_stdout(io.StringIO()):
                    self.assertEqual(main([
                        "--realm", "Onyxia", "--names-file", str(names_file), "--output-dir", tmp,
                    ]), 0)
            self.assertEqual(runner.call_args.args[0], ["Alice", "Bob"])

    def test_summary_is_promoted_from_a_same_directory_temp_file(self):
        replace = Path.replace
        replacements = []

        def tracked_replace(source, target):
            replacements.append((source, target))
            return replace(source, target)

        with mock.patch.object(Path, "replace", tracked_replace):
            rows, summary = run_roster([], "Onyxia", self.output, str(self.cache), False, 120)
        self.assertEqual(rows, [])
        self.assertEqual(len(replacements), 1)
        self.assertEqual(replacements[0][0].parent, summary.parent)
        self.assertEqual(replacements[0][1], summary)
        self.assertTrue(summary.exists())

    def test_output_may_be_the_existing_exports_folder(self):
        self.seed_success("Alice")
        output = self.cache / "exports"
        with mock.patch("warmane_exporter.run.run_character", return_value=0):
            rows, summary = run_roster(["Alice"], "Onyxia", output, str(self.cache), False, 120)
        self.assertEqual(rows[0].status, OK)
        self.assertTrue((output / "alice-onyxia-quick-pve.html").exists())
        self.assertTrue(summary.exists())


if __name__ == "__main__":
    unittest.main()
