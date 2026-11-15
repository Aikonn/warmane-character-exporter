import json
import unittest
from datetime import datetime
from pathlib import Path

from warmane_exporter.pve_report import build_pve_report
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
    sort_rows,
    summary_file_name,
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
        self.assertEqual(row.first_issue, pve["checks"]["issues"][0]["text"])
        self.assertEqual(row.data_time, self.report["snapshot_time"])
        self.assertTrue(row.from_cache)
        html = render_summary([row], "Onyxia", datetime(2026, 11, 15, 10, 30))
        cached_at = datetime.fromtimestamp(row.data_time).strftime("%Y-%m-%d %H:%M")
        self.assertIn(f"cached at {cached_at}", html)

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

    def test_render_summary_escapes_name_and_issue_text(self):
        row = RosterRow(
            name="A<b>",
            realm="Onyxia",
            status=OK,
            class_name="Priest",
            main_trees=["Holy"],
            gearscore=123,
            average_item_level=200,
            issues=1,
            warnings=0,
            first_issue="Missing <enchant>",
            report_file="A-b-Onyxia-quick-pve.html",
            armory_url="https://armory.warmane.com/character/A%3Cb%3E/Onyxia/summary",
            from_cache=False,
        )
        not_found = placeholder_row("Absent", "Onyxia", NOT_FOUND)
        html = render_summary([row, not_found], "Onyxia", datetime(2026, 11, 15, 10, 30))
        not_found_html = next(line for line in html.splitlines() if "<td>Absent</td>" in line)

        self.assertIn("A&lt;b&gt;", html)
        self.assertIn("Missing &lt;enchant&gt;", html)
        self.assertNotIn("A<b>", html)
        self.assertNotIn("Missing <enchant>", html)
        self.assertIn("fresh", html)
        self.assertIn("characters: 2; from cache: 0; not OK: 1", html)
        self.assertIn('href="A-b-Onyxia-quick-pve.html"', html)
        self.assertIn("https://armory.warmane.com/character/A%3Cb%3E/Onyxia/summary", html)
        self.assertNotIn("<script", html)
        self.assertEqual(not_found_html.count("<td>"), 11)
        self.assertEqual(not_found_html.count("<td></td>"), 9)
        self.assertIn('<a href="https://armory.warmane.com/character/Absent/Onyxia/summary">Armory</a>', not_found_html)


if __name__ == "__main__":
    unittest.main()
