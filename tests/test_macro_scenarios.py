import unittest

import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("Agg")

from smdr import viz
from smdr.transition import macro


class ScenarioPathTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p = macro.build_paths()
        cls.pv = cls.p.pivot_table(index=["scenario_id", "driver"], columns="month", values="value")
        cls.anchors = macro.read("macro_anchors.csv").set_index("driver")["value"]
        cls.defs = macro.read("macro_scenario_definitions.csv")

    def test_grid_is_complete(self):
        self.assertEqual(self.p.groupby(["scenario_id", "driver"]).size().unique().tolist(), [63])
        self.assertEqual(self.p.scenario_id.nunique(), 6)
        self.assertEqual(self.p.month.min(), "2026-10"); self.assertEqual(self.p.month.max(), "2031-12")
        self.assertTrue((self.p.value > 0).all())

    def test_paths_start_at_anchor(self):
        for (sid, dr), r in self.pv.iterrows():
            self.assertAlmostEqual(r["2026-10"], self.anchors[dr], delta=1e-6, msg=(sid, dr))

    def test_base_hits_official_forecast_targets(self):
        self.assertAlmostEqual(self.pv.loc[("MS-BASE", "usdidr"), "2026-12"], 18118, delta=0.5)
        self.assertAlmostEqual(self.pv.loc[("MS-BASE", "usdidr"), "2027-12"], 17722, delta=0.5)
        self.assertAlmostEqual(self.pv.loc[("MS-BASE", "bi_rate"), "2027-12"], 6.00, delta=1e-9)

    def test_energy_scenarios_follow_precedent_and_ordering(self):
        b = self.pv.loc[("MS-BASE", "brent")]; e = self.pv.loc[("MS-ENERGY", "brent")]; n = self.pv.loc[("MS-NORMAL", "brent")]
        self.assertTrue((e >= b - 1e-9).all() and (b >= n - 1e-9).all())          # energi bertahan >= dasar >= normalisasi cepat
        self.assertAlmostEqual(e["2027-06"], e["2026-10"], delta=1e-6)             # ditahan sembilan bulan
        self.assertTrue((np.diff(n.values) <= 1e-9).all())                         # normalisasi tidak naik kembali
        ratios, _ = macro.precedent_ratios(macro.history()[1]["brent_avg"].dropna(), horizon=12)
        self.assertAlmostEqual(n["2027-10"] / n["2026-10"], ratios.iloc[12], places=6)

    def test_shocks_are_relative_to_base(self):
        base_fx = self.pv.loc[("MS-BASE", "usdidr")]; fx = self.pv.loc[("MS-FX", "usdidr")]
        _, full = macro.history()
        p90 = round(macro.six_month_fx_changes(full["usdidr_close"].dropna()).quantile(.9), 1)
        self.assertAlmostEqual(fx["2027-04"] / base_fx["2027-04"] - 1, p90 / 100, places=4)
        self.assertAlmostEqual(self.pv.loc[("MS-RATE", "bi_rate"), "2027-04"] - self.pv.loc[("MS-BASE", "bi_rate"), "2027-04"], 1.0, places=6)

    def test_combined_is_milder_than_single_driver_extremes(self):
        self.assertLess(self.pv.loc[("MS-COMBINED", "usdidr")].max(), self.pv.loc[("MS-FX", "usdidr")].max())
        self.assertLess(self.pv.loc[("MS-COMBINED", "bi_rate")].max(), self.pv.loc[("MS-RATE", "bi_rate")].max())
        self.assertAlmostEqual(self.pv.loc[("MS-COMBINED", "brent")].max(), self.pv.loc[("MS-ENERGY", "brent")].max(), delta=1e-6)

    def test_followers_equal_base(self):
        for sid, dr in (("MS-ENERGY", "usdidr"), ("MS-NORMAL", "bi_rate"), ("MS-FX", "brent")):
            self.assertTrue(np.allclose(self.pv.loc[(sid, dr)].values, self.pv.loc[("MS-BASE", dr)].values))

    def test_every_assumption_is_documented(self):
        self.assertTrue(self.defs["assumption_id"].notna().all() and self.defs["basis"].str.len().gt(20).all())
        self.assertTrue(set(self.p.assumption_id) <= set(self.defs.assumption_id))


class VintageTest(unittest.TestCase):
    def test_vintages_are_labelled_and_not_blended(self):
        v = macro.vintages()
        self.assertEqual(v.duplicated(["vintage_id", "variable", "horizon"]).sum(), 0)
        self.assertTrue(v[["provider", "as_of_date", "source_id", "locator"]].notna().all().all())
        self.assertTrue((v[v.evidence_status == "derived_from_note"].acceptance_status == "conditional").all())
        fx = v[(v.variable == "idr_usd_eop") & (v.horizon == "2026F")].set_index("vintage_id")["value"]
        self.assertEqual((fx["OCE-2026-10"], fx["OCE-2026-11"]), (17805, 18118))  # dua vintage berbeda dipertahankan

    def test_ifrs9_vintage_is_stale_versus_realisation(self):
        q = macro.realisation_vs_ifrs9()
        self.assertGreater(q.loc["idr_usd", "realisasi"], q.loc["idr_usd", "baseline"])  # kurs nyata di atas baseline vintage Mei
        self.assertLess(q.loc["idr_usd", "realisasi"], q.loc["idr_usd", "downside"])

    def test_brent_fx_link_is_statistically_weak(self):
        r = macro.fx_brent_beta()
        self.assertLess(r[0]["r2"], 0.1); self.assertLess(r[1]["r2"], 0.1)

    def test_charts_render(self):
        w, full = macro.history(); viz.apply_style(); p = macro.build_paths()
        self.assertTrue(viz.brent_scenarios(full["brent_avg"].dropna(), p, (73.9, 85.0)).axes)
        self.assertTrue(viz.fx_scenarios(full["usdidr_close"].dropna(), p, (17250, 18340)).axes)


if __name__ == "__main__":
    unittest.main()


class ViewAndRenderTest(unittest.TestCase):
    def test_charts_render_fully_and_only_plot_their_own_driver(self):
        import io
        view = macro.build_view(); viz.apply_style()
        figs = (viz.brent_scenarios(view.brent_hist, view.paths, view.plateau), viz.fx_scenarios(view.fx_hist, view.paths, view.oce_fx_6m))
        for fig, (lo, hi) in zip(figs, ((40, 140), (13000, 20200))):
            buf = io.BytesIO(); fig.savefig(buf, format="png", bbox_inches="tight")  # render penuh, bukan sekadar membuat gambar
            self.assertLess(fig.get_size_inches()[1] * fig.dpi, 2000)
            ax = fig.axes[0]
            ys = [y for line in ax.lines for y in line.get_ydata() if y == y]
            self.assertTrue(lo <= min(ys) and max(ys) <= hi * 1.05, (lo, hi, min(ys), max(ys)))

    def test_view_tables(self):
        view = macro.build_view()
        self.assertEqual(view.scenarios.shape[0], 6)
        self.assertAlmostEqual(view.official.loc["USD/IDR akhir periode", "OCE Nov 2026 2026F"], 18118)
