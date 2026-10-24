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


if __name__ == "__main__":
    unittest.main()
