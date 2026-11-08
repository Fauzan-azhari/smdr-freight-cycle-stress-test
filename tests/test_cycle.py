import unittest

import numpy as np

from smdr.transition import cashflow as cf
from smdr.transition import cycle as cy
from smdr.transition import macro
from smdr.transition import transmission as tr


class CycleTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.v = cy.build_view()
        cls.inp, cls.a, cls.a_op, cls.paths = cf._init(), cf.assumptions(), tr.assumptions(), macro.build_paths()

    def test_history_ties_to_financial_statements(self):
        h = self.v.hist
        self.assertAlmostEqual(h.loc["FY2024", "ebitda"], 170.2567, places=3)
        self.assertAlmostEqual(h.loc["FY2022", "pendapatan"], 1150.960, places=2)
        self.assertAlmostEqual(h.loc["TTM Sep-2026", "ebitda"], 237.643282, places=5)       # basis sama dengan sejarah (legacy)
        self.assertEqual(self.v.hist.index[0], "FY2021")

    def test_fy2027_denominator_and_tariff_breakeven_tie_to_transmission_module(self):
        fx = self.paths[(self.paths.scenario_id == "MS-BASE") & (self.paths.driver == "usdidr") & (self.paths.month == "2027-12")]["value"].iloc[0]
        self.assertAlmostEqual(self.v.den.loc["FY2027", "penyebut"], tr.denominator(self.inp, fx), places=6)
        self.assertAlmostEqual(self.v.den.loc["FY2027", "titik_impas_tarif"], tr.build_view().breakeven[0.0], places=6)
        self.assertTrue(np.allclose(self.v.den["titik_impas"], 1.10 * self.v.den["penyebut"]))

    def test_sukuk_current_portion_follows_maturity_schedule(self):
        s = self.v.den["sukuk"]
        self.assertAlmostEqual(s["FY2027"], 339.175e9 / 17722 / 1e6, places=4)               # Seri B (Agu 2028)
        self.assertAlmostEqual(s["FY2028"], 700e9 / 17722 / 1e6, places=4)                    # Seri III (Mei 2029)
        self.assertAlmostEqual(s["FY2029"], 500e9 / 17722 / 1e6, places=4)                    # Seri II (Jul 2030)
        self.assertEqual(s["FY2030"], 0.0)

    def test_fy2028_is_the_tightest_test(self):
        self.assertEqual(self.v.den["ruang_ebitda"].idxmin(), "FY2028")
        self.assertEqual(self.v.den["titik_impas_tarif"].idxmax(), "FY2028")                  # paling dekat dengan nol = paling ketat

    def test_counts_below_breakeven_are_consistent_with_history(self):
        for f in self.v.den.index:
            self.assertEqual(self.v.below[f], int((self.v.hist.loc[cy.HIST, "ebitda"] < self.v.den.loc[f, "titik_impas"]).sum()))

    def test_zero_shift_replay_equals_reference_path(self):
        df = cy.replay(self.inp, self.paths, self.a_op, self.a, 0.0, 24)
        self.assertTrue(np.allclose(df["closing"], self.v.ref["closing"]))
        cov = cy._calendar_cover(self.v.ref, self.v.den)
        self.assertAlmostEqual(cov["FY2028"], self.inp["ebitda"] / self.v.den.loc["FY2028", "penyebut"], places=6)

    def test_shift_applies_for_exact_duration(self):
        df = cy.replay(self.inp, self.paths, self.a_op, self.a, -60.0, 12)
        d = df["ebitda"] - self.v.ref["ebitda"]
        self.assertAlmostEqual(d.sum(), -60.0, places=6)
        self.assertTrue((d.iloc[:12] < 0).all() and (d.iloc[12:].abs() < 1e-9).all())

    def test_deeper_or_longer_replay_is_never_better(self):
        g = self.v.grid[self.v.grid.case == "central"]
        for lb in self.v.levels:
            x = g[g.level == lb].sort_values("months")["min_liquidity"].values
            self.assertTrue(np.all(np.diff(x) <= 1e-9), lb)
        for m in cy.DURATIONS:
            x = g[g.months == m].set_index("level").loc[list(self.v.levels)]["min_liquidity"].values
            self.assertTrue(np.all(np.diff(x) <= 1e-9) , m)

    def test_levels_are_ordered_from_mild_to_severe(self):
        x = list(self.v.levels.values())
        self.assertTrue(all(a > b for a, b in zip(x, x[1:])))
        self.assertAlmostEqual(x[-1], 0.8 * x[-2], places=6)                                    # 20% di bawah palung

    def test_critical_levels_hit_threshold_and_covenant_binds_first(self):
        ttm = self.v.basis["ttm_hist"]
        for m in cy.DURATIONS:
            L = self.v.critical.loc[m, "liquidity"]
            df = cy.replay(self.inp, self.paths, self.a_op, self.a, L - ttm, m)
            self.assertAlmostEqual(df["liquidity"].min(), self.v.threshold, delta=0.01)
            self.assertLess(self.v.critical.loc[m, "liquidity"], self.v.den.loc[["FY2027", "FY2028", "FY2029"], "titik_impas"].min())   # uji yang terkena penurunan (sampai Sep 2029): covenant lebih dulu
            self.assertGreater(self.v.critical.loc[m, "cash"], self.v.critical.loc[m, "liquidity"])

    def test_basis_difference_does_not_change_counts(self):
        diff = self.v.basis["fy2025_penuh"] - self.v.basis["fy2025_hist"]
        self.assertLess(abs(diff), 3.0)
        for f in self.v.den.index:
            moved = int(((self.v.hist.loc[cy.HIST, "ebitda"] + diff) < self.v.den.loc[f, "titik_impas"]).sum())
            self.assertEqual(moved, self.v.below[f], f)

    def test_macro_cover_table_matches_calendar_ebitda_and_stays_above_threshold(self):
        cv = cf.build_view()
        mc = cy.macro_cover_table(cv, self.v)
        df = cv.paths[("Dasar", "central")]
        e28 = df["ebitda"].groupby(df.index.str[:4]).sum()["2028"]
        self.assertAlmostEqual(mc.loc[("Dasar", "tengah"), "FY2028"], e28 / self.v.den.loc["FY2028", "penyebut"], places=9)
        self.assertGreater(mc.values.min(), 1.10)
        self.assertEqual(mc.shape, (6, 3))

    def test_charts_and_tables_render(self):
        import matplotlib
        matplotlib.use("Agg")
        from smdr import viz
        self.assertIsNotNone(viz.cycle_history(self.v))
        self.assertIsNotNone(viz.replay_grid(self.v))
        for f in (cy.history_table, cy.breakeven_table, cy.critical_table, cy.grid_table):
            self.assertGreater(len(f(self.v)), 0)


if __name__ == "__main__":
    unittest.main()
