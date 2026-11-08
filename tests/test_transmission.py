import io
import unittest

import matplotlib
matplotlib.use("Agg")
import numpy as np

from smdr import viz
from smdr.transition import transmission as tr


class TransmissionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.v = tr.build_view()
        cls.s = cls.v.scenarios.set_index(["scenario", "case"])

    def test_inputs_tie_to_data_layers(self):
        i = self.v.inp
        self.assertAlmostEqual(i["revenue"], 877.511474, places=3)           # TTM pendapatan menurut jenis jasa = baseline
        self.assertAlmostEqual(i["ebitda"], 240.044492, places=3)
        self.assertAlmostEqual(i["short_idr"], 96.639 - 50.730, delta=0.01)   # posisi rupiah neto dari catatan moneter

    def test_assumption_ranges_are_ordered_and_labelled(self):
        a = tr.assumptions()
        self.assertTrue(((a.low <= a.central) & (a.central <= a.high)).all())
        self.assertTrue((a.status == "assumed").all())

    def test_adverse_never_better_than_central(self):
        for sc in tr.ORDER:
            self.assertLessEqual(self.s.loc[(sc, "adverse"), "d_ebitda"], self.s.loc[(sc, "central"), "d_ebitda"] + 1e-9, sc)
            self.assertLessEqual(self.s.loc[(sc, "adverse"), "cover"], self.s.loc[(sc, "central"), "cover"] + 1e-9, sc)

    def test_scenario_ordering(self):
        e = lambda n: self.s.loc[(n, "central"), "d_ebitda"]
        self.assertLess(e("Energi bertahan"), e("Dasar"))
        self.assertLess(e("Dasar"), e("Normalisasi cepat"))                 # energi lebih murah = beban lebih ringan
        self.assertLessEqual(self.s.loc[("Gabungan", "adverse"), "cover"], self.s.loc[("Energi bertahan", "adverse"), "cover"])

    def test_fx_stress_creates_noncash_revaluation_gain(self):
        self.assertGreater(self.s.loc[("Tekanan kurs", "central"), "reval"], 0)

    def test_ebitda_impact_excludes_noncash_and_below_ebit_items(self):
        r = self.s.loc[("Tekanan kurs", "central")]
        self.assertAlmostEqual(r["d_pbt"], r["d_ebitda"] + r["reval"] - r["d_interest"], places=9)

    def test_grid_monotonic_and_breakeven_closed_form(self):
        g = self.v.grid
        for vol, sub in g.groupby("volume"):
            self.assertTrue((np.diff(sub.sort_values("rate").cover.values) > 0).all())
        be = self.v.breakeven[0.0]
        row = tr.rate_volume_grid(self.v.inp, tr.assumptions(), [be], [0.0])[0].iloc[0]
        self.assertAlmostEqual(row["cover"], tr.THRESHOLD, places=6)         # pada titik impas cover tepat 1,10x

    def test_charts_render(self):
        viz.apply_style()
        figs = (viz.scenario_ebitda(self.v.scenarios, tr.ORDER), viz.cover_scenarios(self.v.scenarios, tr.ORDER, tr.THRESHOLD),
                viz.rate_volume(self.v.grid, self.v.breakeven, tr.THRESHOLD))
        for f in figs:
            buf = io.BytesIO(); f.savefig(buf, format="png", bbox_inches="tight")
            self.assertLess(f.get_size_inches()[1] * f.dpi, 2000)


if __name__ == "__main__":
    unittest.main()
