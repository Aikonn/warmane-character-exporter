import unittest

from warmane_exporter.snapshot_report import check_snapshot


def snap(json_ids, html_ids, json_points, html_totals, layout="anchors_consistent"):
    return {
        "character": {"name": "X", "realm": "Onyxia"},
        "complete": True,
        "sections": {
            "json_summary": {"status": "ok", "origin": "network", "data": {
                "equipment": [{"item_id": i} for i in json_ids],
                "talent_trees": [{"points": p} for p in json_points]}},
            "html_summary": {"status": "ok", "origin": "network", "data": {
                "equipment": {"layout_validation": {"status": layout},
                              "slots": [{"item_reference": {"href_item_id": str(i)},
                                         "client": {"slot_check": "ok"}} for i in html_ids]},
                "client_warnings": []}},
            "talents": {"status": "ok", "origin": "network", "data": {
                "specs": [{"trees": [{"reported_total": n} for n in t]} for t in html_totals],
                "warnings": [], "client_warnings": []}},
        },
    }


class ReportTests(unittest.TestCase):
    def test_consistent_snapshot_passes(self) -> None:
        lines, ok = check_snapshot(snap([1, 2], [2, 1], [[57, 14, 0], [18, 53, 0]], [(18, 53, 0), (57, 14, 0)]))
        self.assertTrue(ok, lines)

    def test_item_mismatch_fails(self) -> None:
        lines, ok = check_snapshot(snap([1, 2], [1, 3], [[1, 0, 0]], [(1, 0, 0)]))
        self.assertFalse(ok)
        self.assertTrue(any("MISMATCH" in line for line in lines))

    def test_talent_mismatch_and_bad_layout_fail(self) -> None:
        self.assertFalse(check_snapshot(snap([1], [1], [[5, 0, 0]], [(6, 0, 0)]))[1])
        self.assertFalse(check_snapshot(snap([1], [1], [[5, 0, 0]], [(5, 0, 0)], layout="unverified"))[1])


if __name__ == "__main__":
    unittest.main()
