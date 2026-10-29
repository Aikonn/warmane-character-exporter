import unittest
from unittest import mock

from warmane_exporter import run


class RunTests(unittest.TestCase):
    def test_plan_order_and_offline(self):
        online = [s[0] for s in run.steps("A", "Onyxia", "c", False, False)]
        self.assertEqual(online, ["snapshot", "reputation", "mounts-and-companions", "achievements", "statistics", "export"])
        self.assertEqual([s[0] for s in run.steps("A", "Onyxia", "c", False, True)], ["export"])

    def test_stops_at_first_failure(self):
        calls = []

        def fake(label, code):
            def f(argv):
                calls.append(label)
                return code
            return f

        plan = [("one", fake("one", 0), []), ("two", fake("two", 3), []), ("three", fake("three", 0), [])]
        with mock.patch.object(run, "steps", return_value=plan):
            self.assertFalse(run.run_character("A", "Onyxia", "c", False, False))
        self.assertEqual(calls, ["one", "two"])

    def test_link_runs_one_character_and_copies_html(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp) / "cache"
            (cache / "exports").mkdir(parents=True)
            (cache / "exports" / "aikka-onyxia-pve.html").write_text("<html>ok</html>", encoding="utf-8")
            target = Path(tmp) / "out" / "report.html"
            with mock.patch.object(run, "run_character", return_value=True) as runner:
                code = run.main(["https://armory.warmane.com/character/Aikka/Onyxia/summary", "--cache-dir", str(cache),
                                 "--html-output", str(target), "--offline"])
            self.assertEqual(code, 0)
            runner.assert_called_once_with("Aikka", "Onyxia", str(cache), False, True, False, False)
            self.assertEqual(target.read_text(encoding="utf-8"), "<html>ok</html>")

    def test_bad_link_is_reported(self):
        with mock.patch.object(run, "run_character") as runner:
            self.assertEqual(run.main(["https://example.com/character/A/Onyxia/summary"]), 2)
            self.assertEqual(run.main(["Aikka"]), 2)
        runner.assert_not_called()


if __name__ == "__main__":
    unittest.main()
