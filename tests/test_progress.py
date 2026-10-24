import io
import os
import unittest
from contextlib import redirect_stdout
from unittest import mock

from warmane_exporter import progress, run


def capture(fn):
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        fn()
    return buffer.getvalue().splitlines()


class ProgressTests(unittest.TestCase):
    def test_silent_by_default(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("WARMANE_PROGRESS", None)
            self.assertEqual(capture(lambda: progress.start(4, "x")), [])

    def test_percent_lines(self):
        with mock.patch.dict(os.environ, {"WARMANE_PROGRESS": "1"}):
            def work():
                progress.start(4, "Starting")
                progress.advance("one")
                progress.note("working")
                progress.advance("two", 2)
                progress.advance("over", 5)
            self.assertEqual(capture(work), ["PROGRESS|0|Starting", "PROGRESS|25|one", "PROGRESS|25|working", "PROGRESS|75|two", "PROGRESS|100|over"])

    def test_run_character_reports_all_steps(self):
        plan = [("snapshot", lambda a: 0, []), ("achievements", lambda a: 0, []), ("export", lambda a: 0, [])]
        with mock.patch.dict(os.environ, {"WARMANE_PROGRESS": "1"}), mock.patch.object(run, "steps", return_value=plan):
            lines = capture(lambda: run.run_character("A", "Onyxia", "c", False, False))
        progress_lines = [l for l in lines if l.startswith("PROGRESS|")]
        self.assertEqual(progress_lines[0], "PROGRESS|0|Starting A (Onyxia)")
        self.assertTrue(progress_lines[-1].startswith("PROGRESS|"))
        self.assertIn("Reading character summary and talents", progress_lines[1])


if __name__ == "__main__":
    unittest.main()


class PveSubsetTests(unittest.TestCase):
    def test_default_categories_are_a_subset_and_full_is_everything(self):
        from warmane_exporter import collect
        for section, everything in (("achievements", collect.ACHIEVEMENT_CATEGORIES), ("statistics", collect.STATISTIC_CATEGORIES)):
            subset = collect.categories_for(section, False)
            self.assertEqual(collect.categories_for(section, True), everything)
            self.assertTrue(0 < len(subset) < len(everything))
        self.assertEqual(len(collect.categories_for("achievements", False)), 13)
        self.assertEqual(len(collect.categories_for("statistics", False)), 9)
