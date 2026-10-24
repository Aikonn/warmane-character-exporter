import unittest

from warmane_exporter.spell_text import SpellNumbers, format_duration, render_description


class Src:
    def __init__(self, spells, durations=None, radii=None):
        self.spells, self.durations, self.radii = spells, durations or {}, radii or {}

    def spell_numbers(self, sid):
        return self.spells.get(sid)

    def duration_ms(self, idx):
        return self.durations.get(idx)

    def radius_yards(self, idx):
        return self.radii.get(idx)


class RenderTests(unittest.TestCase):
    def test_simple_and_signed(self):
        src = Src({1: SpellNumbers(1, base_points=(-81, 24, 0))})
        self.assertEqual(render_description("Cost by $s1 and $m2%.", 1, src).text, "Cost by 80 and 25%.")

    def test_expression_with_other_spell(self):
        src = Src({58647: SpellNumbers(58647, base_points=(-81, 0, 0))})
        r = render_description("by ${$58647m1/-10} Runic Power", 1, src)
        self.assertEqual(r.text, "by 8 Runic Power")
        self.assertFalse(r.unresolved)

    def test_divide_prefix_and_duration(self):
        src = Src({5: SpellNumbers(5, base_points=(59999, 0, 0), duration_index=3)}, durations={3: 60000})
        self.assertEqual(render_description("$/1000;s1 s for $d", 5, src).text, "60 s for 1 min")

    def test_radius_and_range(self):
        src = Src({7: SpellNumbers(7, base_points=(9, 0, 0), die_sides=(3, 0, 0), radius_index=(4, 0, 0))}, radii={4: 8.0})
        self.assertEqual(render_description("$s1 dmg in $a1 yards", 7, src).text, "10 to 12 dmg in 8 yards")

    def test_unresolved_is_flagged_not_guessed(self):
        src = Src({1: SpellNumbers(1)})
        r = render_description("Does $?s123[a][b] things", 1, src)
        self.assertTrue(r.unresolved)
        r2 = render_description("Hits $s1", 99, src)
        self.assertTrue(r2.unresolved)
        self.assertIn("$s1", r2.text)

    def test_duration_format(self):
        self.assertEqual(format_duration(15000), "15 sec")
        self.assertEqual(format_duration(3600000), "1 hour")


if __name__ == "__main__":
    unittest.main()
