import unittest

from warmane_exporter import run
from warmane_exporter.pve_report import build_pve_report, render_html


class QuickTests(unittest.TestCase):
    def test_quick_plan_is_snapshot_and_export_only(self):
        labels = [label for label, _, _ in run.steps("A", "Onyxia", "c", False, False, quick=True)]
        self.assertEqual(labels, ["snapshot", "export"])
        self.assertIn("--quick", run.steps("A", "Onyxia", "c", False, False, quick=True)[-1][2])
        self.assertEqual([l for l, _, _ in run.steps("A", "Onyxia", "c", False, True, quick=True)], ["export"])
        self.assertGreater(len(run.steps("A", "Onyxia", "c", False, False)), 4)

    def test_quick_report_has_only_the_quick_sections(self):
        report = {"quick": True, "identity": {"name": "A", "realm": "Onyxia", "class": "Priest", "level": 80},
                  "equipment": [], "professions": [], "specializations": [], "missing_sections": []}
        html = render_html(build_pve_report(report))
        self.assertIn("Quick PvE report", html)
        self.assertIn('id="checks"', html)
        for gone in ("WotLK raid achievements", "Reputation", "Mounts", "boss kills", "Missing sections"):
            self.assertNotIn(gone, html.split("Quick report:")[0] if gone == "Missing sections" else html.replace("were not collected", ""))
