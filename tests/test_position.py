import unittest

import matplotlib
matplotlib.use("Agg")

from smdr import covenant_band as cb, position, viz


class PositionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pos = position.build()

    def test_key_figures(self):
        self.assertAlmostEqual(self.pos.composition.loc["TTM", "ebitda"], 240044492, delta=1)
        self.assertAlmostEqual(self.pos.band.loc["FY2025", "cover"], 1.318, places=3)
        self.assertAlmostEqual(self.pos.quarterly["ebit_margin"].min(), 9.5, delta=0.1)
        self.assertAlmostEqual(self.pos.cash, 342283444, delta=1)

    def test_composition_adds_up(self):
        c = self.pos.composition
        self.assertTrue(((c["ebit"] + c["depreciation"] - c["ebitda"]).abs() < 1).all())

    def test_no_unexplained_integrity_issue(self):
        self.assertEqual(self.pos.integrity["unexplained"], 0)

    def test_charts_render(self):
        viz.apply_style()
        for fig in (viz.quarterly(self.pos.quarterly), viz.composition(self.pos.composition), viz.cover(self.pos.band, cb.THRESHOLD_COVER)):
            self.assertTrue(fig.axes)


if __name__ == "__main__":
    unittest.main()
