import unittest
from pathlib import Path

from warmane_exporter.summary_parser import _parse_professions

BLOCK = '<div class="profskills"><div class="stub"><div class="text"> Tailoring <span class="value">427 / 450</span> </div></div><div class="stub"><div class="text"> First Aid <span class="value">1 / 75</span> </div></div></div><div class="clear"></div><h3>PvP Teams</h3><div class="text">X <span class="value">9 / 9</span></div>'


class ProfessionTests(unittest.TestCase):
    def test_block_is_bounded_and_numeric(self):
        self.assertEqual(_parse_professions(BLOCK), [
            {"name": "Tailoring", "skill": 427, "maximum": 450},
            {"name": "First Aid", "skill": 1, "maximum": 75}])

    def test_no_block_means_no_professions(self):
        self.assertEqual(_parse_professions("<html></html>"), [])


if __name__ == "__main__":
    unittest.main()
