import hashlib
import io
import json
import re
import tempfile
import time
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock
from contextlib import redirect_stderr, redirect_stdout

from warmane_exporter.pve_report import build_pve_report, render_html as render_pve_html
from warmane_exporter.cache import ResponseCache
from warmane_exporter.checkpoint import ProbeCheckpointStore
from warmane_exporter.http_client import HttpResponse
from warmane_exporter import progress
from warmane_exporter.fingerprint import (
    fingerprint_for_bodies,
    response_cache_keys,
    tool_version_hash,
)
from warmane_exporter.roster import (
    FAILED,
    NOT_FOUND,
    NOT_RUN,
    OK,
    RosterRow,
    build_row,
    group_issues,
    parse_names,
    placeholder_row,
    quick_sum,
    render_summary,
    run_roster,
    sort_rows,
    summary_file_name,
    STOP_NOTE,
    main,
)
from warmane_exporter.transport import RequestOrchestrator, TransportConfig


FIXTURES = Path(__file__).parent / "fixtures"


class ParseNamesTests(unittest.TestCase):
    def test_trims_blank_lines_and_deduplicates_case_insensitively(self):
        result = parse_names(" \n alice \nALICE\n  BoB  \n", "Onyxia")
        self.assertEqual(result.names, ["Alice", "Bob"])
        self.assertEqual(result.errors, [])

    def test_accepts_names_separated_by_whitespace_and_commas(self):
        result = parse_names("Alice, Bob\tCara-Onyxia alice", "Onyxia")
        self.assertEqual(result.names, ["Alice", "Bob", "Cara"])
        self.assertEqual(result.errors, [])

    def test_accepts_ten_names_on_one_line_with_trailing_spaces(self):
        names = "Hyacinthus Uzbudu Nitkov Renoster Dutchflower Madoxx Denerriss Ypestis Sofla Aikka"
        result = parse_names(names + " " * 30, "Onyxia")
        self.assertEqual(
            result.names,
            ["Hyacinthus", "Uzbudu", "Nitkov", "Renoster", "Dutchflower",
             "Madoxx", "Denerriss", "Ypestis", "Sofla", "Aikka"],
        )
        self.assertEqual(result.errors, [])

    def test_accepts_matching_realm_suffix_and_rejects_other_realm(self):
        result = parse_names("Alice-ONYXIA\nBob-Icecrown\nCara", "Onyxia")
        self.assertEqual(result.names, ["Alice", "Cara"])
        self.assertEqual(len(result.errors), 1)
        self.assertIn("Line 2", result.errors[0])
        self.assertIn("Bob-Icecrown", result.errors[0])

    def test_rejects_nonletter_names_but_accepts_accented_letters(self):
        result = parse_names("Qzx1\nTwo_Words\nÉLODIE\ne\u0301lodie", "Onyxia")
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
            row.issue_findings,
            pve["checks"]["issues"],
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
        self.assertIn('<td class="spec" data-sort="shadow / -">Shadow / -</td>', html)

    def test_build_row_keeps_structured_issue_findings_in_check_order(self):
        issues = [
            {"kind": "unknown", "slot": "Head", "text": "first"},
            {"kind": "unknown", "text": "second"},
            {"kind": "unknown", "text": "third"},
        ]
        with mock.patch("warmane_exporter.roster.run_checks", return_value={
            "issues": issues,
            "warnings": [],
        }):
            row = build_row(self.report, "Mélora-Onyxia-quick-pve.html", from_cache=False)

        self.assertEqual(row.issue_findings, issues)
        self.assertEqual(group_issues(row.issue_findings), [
            ("Head:", "first"), ("", "second"), ("", "third"),
        ])

    def test_build_row_groups_common_gems_but_excludes_glyph_warnings(self):
        issues = [
            {"kind": "gem_common", "slot": "Head", "count": 2, "text": "2 common-quality gem(s): gem; gem."},
            {"kind": "gem_common", "slot": "Chest", "count": 1, "text": "1 common-quality gem(s): gem."},
        ]
        warning = {"kind": "glyphs", "count": 1, "spec_index": 1, "text": "glyph warning"}
        with mock.patch("warmane_exporter.roster.run_checks", return_value={
            "issues": issues,
            "warnings": [warning],
        }):
            row = build_row(self.report, "Mélora-Onyxia-quick-pve.html", from_cache=False)

        self.assertEqual(row.warnings, 1)
        self.assertEqual(
            group_issues(row.issue_findings),
            [("Common gems (3):", "Head 2, Chest 1")],
        )
        self.assertIn("3 common gems", quick_sum(row))
        self.assertNotIn("glyph", str(group_issues(row.issue_findings)))
        self.assertNotIn("glyph", quick_sum(row))

    def test_build_row_prefixes_gear_issue_but_not_spec_issue(self):
        report = json.loads(json.dumps(self.report))
        report["specializations"][0]["split"] = [57, 12, 0]

        row = build_row(report, "Mélora-Onyxia-quick-pve.html", from_cache=False)

        self.assertEqual(row.issue_findings[0]["slot"], "Head")
        self.assertEqual(row.issue_findings[0]["kind"], "enchant")
        self.assertEqual(row.issue_findings[1]["kind"], "talents")
        self.assertEqual(row.issue_findings[1]["spec_index"], 0)

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


class IssueGroupingTests(unittest.TestCase):
    def test_groups_findings_by_kind_in_required_order(self):
        issues = [
            {"kind": "unknown", "slot": "Waist", "text": "Other issue."},
            {"kind": "glyphs", "count": 3, "spec_index": 0, "text": "glyphs"},
            {"kind": "sockets", "slot": "Chest", "count": 2, "text": "sockets"},
            {"kind": "gem_common", "slot": "Head", "count": 2, "text": "gems"},
            {"kind": "enchant", "slot": "Chest", "text": "enchant"},
            {"kind": "meta", "slot": "Head", "text": "meta"},
            {"kind": "buckle", "slot": "Waist", "text": "buckle"},
            {"kind": "talents", "count": 5, "spec_index": 0, "text": "talents"},
            {"kind": "ring_enchant", "slot": "Finger 1", "text": "ring"},
            {"kind": "sockets", "slot": "Head", "count": 1, "text": "sockets"},
            {"kind": "gem_common", "slot": "Chest", "count": 1, "text": "gems"},
            {"kind": "enchant", "slot": "Head", "text": "enchant"},
            {"kind": "meta", "slot": "Head", "text": "meta"},
            {"kind": "sockets", "slot": "Chest", "count": 1, "text": "sockets"},
            {"kind": "glyphs", "count": 2, "spec_index": 1, "text": "glyphs"},
            {"kind": "talents", "count": 3, "spec_index": 1, "text": "talents"},
            {"kind": "ring_enchant", "slot": "Finger 2", "text": "ring"},
            {"kind": "meta", "slot": "Feet", "text": "meta"},
        ]

        self.assertEqual(group_issues(issues), [
            ("No enchant (2):", "Chest, Head"),
            ("No ring enchant (Enchanter) (2):", "Finger 1, Finger 2"),
            ("Empty sockets (4):", "Chest 3, Head 1"),
            ("Common gems (3):", "Head 2, Chest 1"),
            ("Meta gem not active:", "Head, Feet"),
            ("Belt buckle missing", ""),
            ("Unspent talent points:", "Spec1 5, Spec2 3"),
            ("Major glyphs empty:", "Spec1 3, Spec2 2"),
            ("Waist:", "Other issue."),
        ])


class QuickSumTests(unittest.TestCase):
    def row(self, findings, name="Name", score=5766, status=OK):
        return RosterRow(
            name=name, realm="Onyxia", status=status, gearscore=score,
            issues=len(findings), issue_findings=findings,
        )

    def test_examples_and_rounding_down(self):
        ravenik = self.row([
            {"kind": "enchant"} for _ in range(10)
        ] + [{"kind": "sockets", "count": 11}, {"kind": "buckle"}], "Ravenik", 4872)
        aldrenna = self.row([
            {"kind": "buckle"}, {"kind": "glyphs", "count": 3},
        ], "Aldrenna", 5766)

        self.assertEqual(quick_sum(ravenik), "Ravenik 4.8k - missing 10 enchants, 11 gems, buckle")
        self.assertEqual(quick_sum(aldrenna), "Aldrenna 5.7k - missing buckle, 3 glyphs")
        self.assertEqual(quick_sum(self.row([{"kind": "enchant"}], score=6090)), "Name 6.0k - missing 1 enchant")

    def test_singular_other_only_and_no_issue_cases(self):
        one_each = self.row([
            {"kind": "enchant"}, {"kind": "sockets", "count": 1},
            {"kind": "glyphs", "count": 1}, {"kind": "talents", "count": 1},
        ], score=5000)
        meta_only = self.row([{"kind": "meta"}], score=5500)
        self.assertEqual(
            quick_sum(one_each),
            "Name 5.0k - missing 1 enchant, 1 gem, 1 glyph; 1 unspent talent",
        )
        self.assertEqual(quick_sum(meta_only), "Name 5.5k - inactive meta gem")
        self.assertEqual(
            quick_sum(self.row([{"kind": "custom"}], score=5500)),
            "Name 5.5k - 1 other",
        )
        self.assertIsNone(quick_sum(self.row([])))
        self.assertIsNone(quick_sum(self.row([{"kind": "buckle"}], status=NOT_FOUND)))

    def test_common_gem_count_is_singular_or_plural_before_meta(self):
        self.assertEqual(
            quick_sum(self.row([
                {"kind": "enchant"},
                {"kind": "gem_common", "count": 1},
                {"kind": "meta"},
            ])),
            "Name 5.7k - missing 1 enchant; 1 common gem, inactive meta gem",
        )
        self.assertEqual(
            quick_sum(self.row([
                {"kind": "enchant"},
                {"kind": "gem_common", "count": 1},
                {"kind": "gem_common", "count": 2},
                {"kind": "meta"},
            ])),
            "Name 5.7k - missing 1 enchant; 3 common gems, inactive meta gem",
        )

    def test_message_stays_under_wow_chat_limit(self):
        findings = (
            [{"kind": "enchant"} for _ in range(8)]
            + [{"kind": "sockets", "count": 3} for _ in range(19)]
            + [{"kind": "buckle"}]
            + [{"kind": "glyphs", "count": 3} for _ in range(2)]
            + [{"kind": "talents", "count": 71} for _ in range(2)]
            + [{"kind": "custom"} for _ in range(20)]
        )
        self.assertLessEqual(len(quick_sum(self.row(findings, "Abcdefghijkl", 6000))), 255)


class SummaryRenderingTests(unittest.TestCase):
    def test_summary_file_name_uses_local_timestamp(self):
        self.assertEqual(summary_file_name(datetime(2026, 11, 15, 9, 7)), "raid-2026-11-15-0907.html")

    def test_summary_escapes_text_and_uses_nine_cells(self):
        row = RosterRow(
            name="A<b>",
            realm="Onyxia",
            status=OK,
            class_name="Priest",
            main_trees=["Holy", "-"],
            gearscore=4800,
            average_item_level=245.5,
            issues=2,
            warnings=0,
            issue_findings=[
                {"kind": "custom", "slot": "<Head &>", "text": "Missing <enchant>"},
                {"kind": "custom", "text": "Second & final"},
            ],
            report_file="A-b-Onyxia-quick-pve.html",
            armory_url="https://armory.warmane.com/character/A%3Cb%3E/Onyxia/summary",
            from_cache=False,
        )
        not_found = placeholder_row("Absent", "Onyxia", NOT_FOUND)
        html = render_summary([row, not_found], "Onyxia", datetime(2026, 11, 15, 10, 30))
        not_found_html = next(line for line in html.splitlines() if 'data-sort="absent"' in line)

        self.assertIn("A&lt;b&gt;", html)
        self.assertIn('<span class="lbl">&lt;Head &amp;&gt;:</span> Missing &lt;enchant&gt;', html)
        self.assertIn('data-quick-sum="A&lt;b&gt; 4.8k - 2 other"', html)
        self.assertNotIn("A<b>", html)
        self.assertNotIn("Missing <enchant>", html)
        self.assertIn("characters: 2; from cache: 0; not OK: 1", html)
        self.assertIn('href="A-b-Onyxia-quick-pve.html"', html)
        self.assertIn(
            'href="https://armory.warmane.com/character/A%3Cb%3E/Onyxia/summary" title="Armory" '
            'aria-label="Armory for A&lt;b&gt;" target="_blank" rel="noopener"',
            html,
        )
        self.assertIn("<th>Issues list</th>", html)
        self.assertEqual(html.count("<script>"), 1)
        self.assertEqual(html.count("</script>"), 1)
        self.assertEqual(not_found_html.count("<td"), 9)
        self.assertIn('<tr class="not-ok"><td class="name-cell" data-sort="absent">Absent', not_found_html)
        self.assertIn('<span class="status">not found: not found</span>', not_found_html)
        self.assertIn(
            '<a class="armory" href="https://armory.warmane.com/character/Absent/Onyxia/summary"',
            not_found_html,
        )
        for heading in ("Report", "Armory", "Main trees"):
            self.assertNotIn(f"<th>{heading}</th>", html)
        self.assertNotIn("cls-", render_pve_html(build_pve_report({"identity": {"name": "X", "realm": "Onyxia"}})))

    def test_summary_header_includes_rate_limit_wait_count_and_final_spacing(self):
        html = render_summary(
            [], "Onyxia", datetime(2026, 11, 17, 10, 30),
            rate_limit_waits=4, final_spacing_seconds=5,
        )
        self.assertIn("rate-limit waits: 4, spacing 5 s", html)

    def test_pve_report_exposes_fingerprint_in_html_head(self):
        report = build_pve_report({"identity": {"name": "X", "realm": "Onyxia"}})
        fingerprint = "a" * 64
        report["report"]["fingerprint"] = fingerprint
        self.assertIn(
            f'<meta name="warmane-fingerprint" content="{fingerprint}">',
            render_pve_html(report),
        )

    def test_pve_html_for_synthetic_fixture_is_unchanged(self):
        report = json.loads((FIXTURES / "synthetic" / "roster-report-synthetic.json").read_text(encoding="utf-8"))
        html = render_pve_html(build_pve_report(report))
        html_without_style = re.sub(r"<style>.*?</style>", "<style></style>", html, count=1, flags=re.DOTALL)
        self.assertEqual(
            hashlib.sha256(html_without_style.encode("utf-8")).hexdigest(),
            "5b05c3cb067f48bc492272ae347291f54db947db99365ccb0a735e5283b087f7",
        )

    def test_relative_age_keeps_fallback_and_epoch_sort_value(self):
        rows = [
            RosterRow(name="Cached", realm="Onyxia", status=OK, data_time=1234567890, from_cache=True),
            RosterRow(name="Fresh", realm="Onyxia", status=OK, data_time=1234567890, from_cache=False),
        ]
        with mock.patch("warmane_exporter.roster.datetime") as local_datetime:
            local_datetime.fromtimestamp.return_value = datetime(2026, 1, 6, 9, 4)
            html = render_summary(rows, "Onyxia", datetime(2026, 11, 15, 10, 30))

        self.assertIn(
            'class="age" data-sort="1234567890" data-age="1234567890" data-state="cache" '
            'title="2026-01-06 09:04 (from cache)">2026-01-06 09:04 (from cache)</td>',
            html,
        )
        self.assertIn(
            'data-state="fresh" title="2026-01-06 09:04 (fresh)">2026-01-06 09:04 (fresh)</td>',
            html,
        )
        self.assertIn('if (age < 90) text = "just now"', html)
        self.assertIn("min ago", html)
        self.assertIn("h ago", html)
        self.assertIn("d ago", html)
        self.assertEqual(local_datetime.fromtimestamp.call_count, 2)

    def test_nine_columns_sort_keys_and_armory_report_links(self):
        row = RosterRow(
            name="Alpha",
            realm="Onyxia",
            status=OK,
            class_name="Priest",
            main_trees=["Holy", "Discipline"],
            gearscore=4800,
            average_item_level=245.5,
            issues=1,
            warnings=3,
            issue_findings=[{"kind": "buckle", "text": "Buckle missing"}],
            report_file="Alpha-Onyxia-quick-pve.html",
            armory_url="https://armory.warmane.com/character/Alpha/Onyxia/summary",
            data_time=1234567890,
            from_cache=True,
        )
        html = render_summary([row], "Onyxia", datetime(2026, 11, 15, 10, 30))

        self.assertIn('<td class="name-cell" data-sort="alpha"><a class="name" href="Alpha-Onyxia-quick-pve.html">Alpha</a>', html)
        self.assertIn('<td class="cls" data-sort="priest"><span class="cls-label">Priest</span></td>', html)
        self.assertIn('<td class="spec" data-sort="holy / discipline">Holy / Discipline</td>', html)
        self.assertIn('<td class="num" data-sort="4800">4800</td><td class="num" data-sort="245.5">245.5</td>', html)
        self.assertIn('<td class="num" data-sort="1"><button type="button" class="copy"', html)
        self.assertIn('<td class="num" data-sort="3"><span class="count-warn">3</span></td>', html)
        self.assertIn('<th class="sortable" data-type="text">Spec1 / Spec2</th>', html)
        self.assertEqual(html.count("<th ") + html.count("<th>"), 9)
        self.assertIn("sortRows(header.cellIndex, header.dataset.type, descending)", html)
        self.assertIn('await navigator.clipboard.writeText(text)', html)
        self.assertIn('document.execCommand("copy")', html)
        self.assertIn('button.title = copied ? "Copied" : "Copy failed"', html)

    def test_theme_and_class_tints_match_the_specification(self):
        palette = {
            "Death Knight": ("c-death-knight", "#C41F3B", "#F2CED4"),
            "Druid": ("c-druid", "#FF7D0A", "#FFE2C9"),
            "Hunter": ("c-hunter", "#ABD473", "#EDF6E0"),
            "Mage": ("c-mage", "#69CCF0", "#DEF4FC"),
            "Paladin": ("c-paladin", "#F58CBA", "#FDE6F0"),
            "Priest": ("c-priest", "#FFFFFF", "#EDEDED"),
            "Rogue": ("c-rogue", "#FFF569", "#FFFDDE"),
            "Shaman": ("c-shaman", "#0070DE", "#C7E0F8"),
            "Warlock": ("c-warlock", "#9482C9", "#E7E4F3"),
            "Warrior": ("c-warrior", "#C79C6E", "#F3E9DF"),
        }
        rows = [
            RosterRow(name=name, realm="Onyxia", status=OK, class_name=name)
            for name in palette
        ]
        html = render_summary(rows, "Onyxia", datetime(2026, 11, 15, 10, 30))

        self.assertIn("prefers-color-scheme:dark", html)
        self.assertIn("color-scheme:light", html)
        self.assertIn("color-scheme:dark", html)
        self.assertIn("--bg:#ffffff;--fg:#111111;--muted:#666666;--border:#c4c4c4;--head:#eeeeee", html)
        self.assertIn("--bg:#16181d;--fg:#e4e6ea;--muted:#9aa0a6;--border:#383d46;--head:#22262d", html)
        for class_name, (css_class, color, tint) in palette.items():
            with self.subTest(class_name=class_name):
                self.assertIn(f'<tr class="{css_class}">', html)
                self.assertIn(f".{css_class}{{--class-color:{color};--class-tint:{tint}}}", html)
        self.assertIn("tr.c-hunter td", html)
        self.assertIn("{background:var(--class-tint)}", html)
        self.assertIn("tr.c-hunter .name,tr.c-hunter .cls-label", html)

    def test_unknown_class_and_issue_free_rows_have_no_class_or_copy_button(self):
        rows = [
            RosterRow(name="Unknown", realm="Onyxia", status=OK, class_name="Evoker", issues=0),
            RosterRow(name="Missing", realm="Onyxia", status=OK, issues=0),
        ]
        html = render_summary(rows, "Onyxia", datetime(2026, 11, 15, 10, 30))
        unknown_row = next(line for line in html.splitlines() if 'data-sort="unknown"' in line)
        missing_row = next(line for line in html.splitlines() if 'data-sort="missing"' in line)
        self.assertIn('<td class="cls" data-sort="evoker"><span class="cls-label">Evoker</span></td>', unknown_row)
        self.assertIn('<td class="cls" data-sort=""></td>', missing_row)
        self.assertNotIn('<tr class="c-', unknown_row)
        self.assertNotIn('<tr class="c-', missing_row)
        self.assertNotIn('<button type="button" class="copy"', html)
        self.assertIn('<td class="num" data-sort="0">0</td><td class="num" data-sort="">', unknown_row)

    def test_count_classes_and_pve_report_remains_script_free(self):
        rows = [
            RosterRow(name="Zero", realm="Onyxia", status=OK, issues=0, warnings=0),
            RosterRow(name="Low", realm="Onyxia", status=OK, issues=1, warnings=3),
            RosterRow(name="High", realm="Onyxia", status=OK, issues=4, warnings=4),
        ]
        html = render_summary(rows, "Onyxia", datetime(2026, 11, 15, 10, 30))
        self.assertIn('<td class="num" data-sort="1"><span class="count-issue">1</span></td>', html)
        self.assertIn('<td class="num" data-sort="4"><span class="count-issue count-high">4</span></td>', html)
        self.assertIn(".count-issue{color:var(--issue)}", html)
        self.assertIn(".count-warn{color:var(--warn)}", html)
        self.assertIn(".count-high{font-weight:700}", html)
        report = json.loads((FIXTURES / "synthetic" / "roster-report-synthetic.json").read_text(encoding="utf-8"))
        self.assertNotIn("<script", render_pve_html(build_pve_report(report)))


class RosterRunTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.cache = self.root / "cache"
        self.output = self.root / "output"
        self.fixture = json.loads(
            (FIXTURES / "synthetic" / "roster-report-synthetic.json").read_text(encoding="utf-8")
        )
        self.definition_loader_patch = mock.patch(
            "warmane_exporter.snapshot.load_definition_sources", return_value=(None, None),
        )
        self.definition_loader = self.definition_loader_patch.start()

    def tearDown(self):
        self.definition_loader_patch.stop()
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

    def seed_fingerprinted_success(self, name):
        version = tool_version_hash()
        bodies = ("json body", "html body", "talents body")
        fingerprint = fingerprint_for_bodies(version, *bodies)
        cache = ResponseCache(self.cache / "responses.sqlite")
        try:
            now = time.time()
            for key, body in zip(response_cache_keys(name, "Onyxia"), bodies, strict=True):
                cache.put(key, key.split("|", 1)[0], body, now)
        finally:
            cache.close()

        self.seed_success(name)
        stem = f"{name.lower()}-onyxia-quick"
        report_path = self.cache / "exports" / f"{stem}.json"
        report = json.loads(report_path.read_text(encoding="utf-8"))
        report["fingerprint"] = fingerprint
        report_path.write_text(json.dumps(report), encoding="utf-8")
        html_path = self.cache / "exports" / f"{stem}-pve.html"
        html_path.write_text(
            f'<html><head><meta name="warmane-fingerprint" content="{fingerprint}"></head>{name}</html>',
            encoding="utf-8",
        )
        return fingerprint

    def test_continues_after_not_found_and_failed_character(self):
        self.seed_success("Alice")
        self.seed_success("Bob")

        def fake_run(name, realm, cache_dir, refresh, offline, full=False, quick=False,
                     max_age_minutes=15, start_progress=True, **kwargs):
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
                     max_age_minutes=15, start_progress=True, **kwargs):
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

    def test_stop_file_is_cleared_then_stops_before_next_character(self):
        for name in ("Alice", "Bob", "Cara"):
            self.seed_success(name)
        stop_file = self.cache / "stop-request"
        self.cache.mkdir(parents=True, exist_ok=True)
        stop_file.write_text("stale", encoding="utf-8")

        def finish_first_character(name, *args, **kwargs):
            self.assertEqual(name, "Alice")
            self.assertFalse(stop_file.exists())
            stop_file.write_text("stop", encoding="utf-8")
            return 0

        with mock.patch("warmane_exporter.run.run_character", side_effect=finish_first_character) as runner:
            rows, summary = run_roster(
                ["Alice", "Bob", "Cara"], "Onyxia", self.output, str(self.cache), False, 120,
            )

        self.assertEqual(runner.call_count, 1)
        self.assertEqual([row.status for row in rows], [OK, NOT_RUN, NOT_RUN])
        self.assertEqual([row.note for row in rows[1:]], ["stopped by user", "stopped by user"])
        self.assertTrue(summary.exists())
        self.assertIn("not run: stopped by user", summary.read_text(encoding="utf-8"))
        self.assertTrue((self.output / "alice-onyxia-quick-pve.html").exists())

    def test_stop_during_character_writes_summary_with_not_run_rows(self):
        now = [1_000.0]
        stop_file = self.cache / "stop-request"

        class RateLimitedClient:
            def get(self, url, connect_timeout, read_timeout):
                return HttpResponse(429, {}, "too many requests")

        def stop_during_wait(name, realm, cache_dir, *args, **kwargs):
            def fake_sleep(seconds):
                now[0] += seconds
                stop_file.write_text("stop", encoding="utf-8")

            orchestrator = RequestOrchestrator(
                checkpoint=ProbeCheckpointStore(path=self.cache / "transport.json"),
                config=TransportConfig(cooldown_schedule_seconds=(60,), jitter_ratio=0.0),
                now_fn=lambda: now[0],
                sleep_fn=fake_sleep,
                skip_completed=False,
            )
            orchestrator.execute_single_request(
                "https://armory.warmane.com/character/Alice/Onyxia/summary",
                RateLimitedClient(),
            )

        with mock.patch("warmane_exporter.run.run_character", side_effect=stop_during_wait) as runner:
            rows, summary = run_roster(
                ["Alice", "Bob"], "Onyxia", self.output, str(self.cache), True, 120,
            )
        self.assertEqual(runner.call_count, 1)
        self.assertEqual([row.status for row in rows], [NOT_RUN, NOT_RUN])
        self.assertTrue(all(row.note == "stopped by user" for row in rows))
        self.assertTrue(summary.exists())

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

    def test_unchanged_output_skips_run_and_preserves_report_file(self):
        fingerprint = self.seed_fingerprinted_success("Alice")
        self.output.mkdir()
        target = self.output / "alice-onyxia-quick-pve.html"
        target.write_text(
            f'<html><head><meta name="warmane-fingerprint" content="{fingerprint}"></head>keep</html>',
            encoding="utf-8",
        )
        before = (target.read_bytes(), target.stat().st_mtime_ns)
        report = json.loads((self.cache / "exports" / "alice-onyxia-quick.json").read_text(encoding="utf-8"))
        expected_row = build_row(report, target.name, from_cache=True)

        with (
            mock.patch.dict("os.environ", {"WARMANE_PROGRESS": "1"}),
            mock.patch("warmane_exporter.run.run_character") as runner,
            redirect_stdout(io.StringIO()) as progress_output,
        ):
            rows, summary = run_roster(
                ["Alice"], "Onyxia", self.output, str(self.cache), False, 120,
            )

        runner.assert_not_called()
        self.definition_loader.assert_not_called()
        self.assertEqual(rows, [expected_row])
        self.assertTrue(rows[0].from_cache)
        self.assertEqual((target.read_bytes(), target.stat().st_mtime_ns), before)
        self.assertIn("Character 1 of 1: Alice (unchanged, skipped)", progress_output.getvalue())
        self.assertIn("PROGRESS|100|Alice: unchanged, skipped", progress_output.getvalue())
        self.assertTrue(summary.exists())

    def test_missing_or_stale_output_is_copied_from_matching_export(self):
        self.seed_fingerprinted_success("Alice")
        self.output.mkdir()
        target = self.output / "alice-onyxia-quick-pve.html"
        source = self.cache / "exports" / target.name
        source_text = source.read_text(encoding="utf-8")

        for stale in (False, True):
            with self.subTest(stale=stale):
                if stale:
                    target.write_text(
                        '<meta name="warmane-fingerprint" content="' + "0" * 64 + '">',
                        encoding="utf-8",
                    )
                elif target.exists():
                    target.unlink()
                with mock.patch("warmane_exporter.run.run_character") as runner:
                    rows, _ = run_roster(
                        ["Alice"], "Onyxia", self.output, str(self.cache), False, 120,
                    )
                runner.assert_not_called()
                self.assertEqual(target.read_text(encoding="utf-8"), source_text)
                self.assertEqual(rows[0].status, OK)

    def test_refresh_never_skips_a_matching_fingerprint(self):
        self.seed_fingerprinted_success("Alice")
        with mock.patch("warmane_exporter.run.run_character", return_value=1) as runner:
            rows, _ = run_roster(
                ["Alice"], "Onyxia", self.output, str(self.cache), True, 120,
            )
        runner.assert_called_once()
        self.assertTrue(runner.call_args.args[3])
        self.assertEqual(rows[0].status, FAILED)

    def test_roster_loads_shared_definitions_once_for_normal_runs(self):
        self.seed_success("Alice")
        self.seed_success("Bob")
        definitions = object()
        client_context = object()
        self.definition_loader.return_value = (definitions, client_context)
        with (
            mock.patch("warmane_exporter.roster.tool_version_hash", return_value="tool-hash") as version_hash,
            mock.patch("warmane_exporter.snapshot.close_definition_sources") as close,
            mock.patch("warmane_exporter.run.run_character", return_value=1) as runner,
        ):
            run_roster(["Alice", "Bob"], "Onyxia", self.output, str(self.cache), False, 120)

        version_hash.assert_called_once_with()
        self.definition_loader.assert_called_once_with()
        close.assert_called_once_with(definitions, client_context)
        self.assertEqual(runner.call_count, 2)
        self.assertTrue(all(call.kwargs["definitions_preloaded"] for call in runner.call_args_list))
        self.assertTrue(all(call.kwargs["defs"] is definitions for call in runner.call_args_list))
        self.assertEqual(
            len({call.kwargs["tool_version"] for call in runner.call_args_list}),
            1,
        )
        self.assertEqual(runner.call_args.kwargs["tool_version"], "tool-hash")


if __name__ == "__main__":
    unittest.main()
