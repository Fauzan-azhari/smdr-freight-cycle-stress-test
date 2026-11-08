import unittest

import numpy as np

from smdr.transition import cashflow as cf
from smdr.transition import macro
from smdr.transition import transmission as tr


class CashflowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inp = cf._init()
        cls.a, cls.a_op, cls.paths = cf.assumptions(), tr.assumptions(), macro.build_paths()
        cls.th = cf.min_cash(cls.inp, cls.a, "central")
        cls.go = staticmethod(lambda sid="MS-BASE", case="central", **kw: cf.run(sid, case, cls.inp, cls.paths, cls.a_op, cls.a, **kw))
        cls.base = cls.go("MS-BASE", "central")

    def test_calendar_and_opening_balance(self):
        self.assertEqual(len(cf.MONTHS), 63)
        self.assertEqual((cf.MONTHS[0], cf.MONTHS[-1]), ("2026-10", "2031-12"))
        self.assertAlmostEqual(self.base["opening"].iloc[0], 342.283444, places=5)     # kas 30 Sep 2026

    def test_balance_identity_each_month(self):
        for case in ("central", "adverse"):
            df = self.go("MS-COMBINED", case)
            self.assertTrue(np.allclose(df["closing"], df["opening"] + df[cf.LINES].sum(axis=1) + df["fx_translation"]))
            self.assertTrue(np.allclose(df["opening"].iloc[1:].values, df["closing"].iloc[:-1].values))

    def test_translation_is_not_a_cash_flow(self):
        self.assertTrue(np.allclose(self.base["net_flow"], self.base[cf.LINES].sum(axis=1)))

    def test_sukuk_schedule_ties_to_facility_table(self):
        df = self.base
        idr_principal = (-df["sukuk_principal"] * df["fx"]).sum() * 1e6
        self.assertAlmostEqual(idr_principal, 339.175e9 + 700e9 + 500e9, delta=1e3)     # tiga seri sukuk, seluruh pokok jatuh tempo dalam horizon
        ev = self.inp["events"]
        idr_coupon = (-df["sukuk_coupon"] * df["fx"]).sum() * 1e6
        self.assertAlmostEqual(idr_coupon, ev[ev.event_type == "coupon"]["amount"].sum(), delta=1e3)

    def test_program_capex_total_and_window(self):
        pc = -self.base["program_capex"]
        self.assertAlmostEqual(pc.sum(), 694.82e9 / 17875 / 1e6, places=6)
        paid = pc[pc > 0].index
        self.assertEqual((paid[0], paid[-1]), ("2026-11", "2027-11"))
        self.assertEqual(len(paid), 13)
        self.assertGreater(-self.go(case="adverse")["program_capex"].sum(), pc.sum())   # kelebihan biaya 10%

    def test_dividend_paid_only_in_june(self):
        d = -self.base["dividend"]
        self.assertTrue(all(m[5:] == "06" for m in d[d > 0].index))
        self.assertEqual((d > 0).sum(), 5)                                                # Juni 2027 s.d. 2031

    def test_first_year_ebitda_effect_matches_transmission_module(self):
        for sid in ("MS-BASE", "MS-ENERGY", "MS-COMBINED"):
            for case in ("central", "adverse"):
                d, _, _ = cf.monthly_effects(self.inp, self.paths, self.a_op, sid, case)
                self.assertAlmostEqual(d.iloc[:12].sum(), tr.scenario_effects(self.inp, self.paths, self.a_op, sid, case)["d_ebitda"], delta=0.01)   # selisih kecil: translasi bulanan vs kurs rata-rata 12 bulan

    def test_adverse_never_better_than_central(self):
        for sid in macro.build_paths().scenario_id.unique():
            c, d = self.go(sid, "central"), self.go(sid, "adverse")
            self.assertLessEqual(d["liquidity"].min(), c["liquidity"].min() + 1e-9, sid)

    def test_parameters_are_ordered_and_labelled(self):
        a = self.a
        self.assertTrue(((a.low <= a.central) & (a.central <= a.high)).all())
        self.assertTrue(a.status.isin(["assumed", "proposed"]).all())
        self.assertEqual(a.loc["min_cash_months", "status"], "proposed")                  # batas kas minimum adalah usulan

    def test_intramonth_floor_never_above_opening(self):
        self.assertTrue((self.base["floor_intramonth"] <= self.base["opening"] + 1e-9).all())

    def test_no_refinancing_is_the_primary_case_and_alternatives_help(self):
        none = self.base["liquidity"].min()
        self.assertGreater(self.go(fin=cf.Financing(bank_redraw=1.0))["liquidity"].min(), none)
        self.assertGreater(self.go(fin=cf.Financing(sukuk_refi=1.0))["liquidity"].min(), none)
        self.assertEqual(self.base["refi_draw"].abs().sum() + self.base["bank_redraw"].abs().sum(), 0.0)

    def test_reverse_stress_root_hits_the_threshold(self):
        be = cf.breakeven_rate_cash("MS-BASE", "central", self.th, 24, "liquidity", inp=self.inp, paths=self.paths, a_op=self.a_op, a=self.a)
        self.assertLess(be, 0)
        df = self.go(stress=cf.Stress(rate=be, months=24))
        self.assertAlmostEqual(df["liquidity"].min(), self.th, delta=0.01)

    def test_required_uplift_restores_threshold(self):
        up = cf.required_uplift("MS-BASE", "adverse", self.th, "liquidity", inp=self.inp, paths=self.paths, a_op=self.a_op, a=self.a)
        self.assertGreater(up, 0)
        self.assertAlmostEqual(self.go(case="adverse", stress=cf.Stress(uplift=up))["liquidity"].min(), self.th, delta=0.01)
        self.assertEqual(cf.required_uplift("MS-BASE", "central", self.th, "liquidity", inp=self.inp, paths=self.paths, a_op=self.a_op, a=self.a), 0.0)

    def test_view_builds_and_charts_render(self):
        import matplotlib
        matplotlib.use("Agg")
        from smdr import viz
        v = cf.build_view()
        self.assertEqual(len(v.scen), 12)
        self.assertAlmostEqual(v.uses.sum() + 342.283444, v.paths[("Dasar", "central")]["closing"].iloc[-1], places=4)   # sumber-penggunaan menutup saldo akhir
        for f in (viz.cash_paths(v), viz.cash_uses(v), viz.cash_tornado(v), viz.cash_reverse(v)):
            self.assertIsNotNone(f)
        res = tr.all_scenarios(); res["scenario"] = res["scenario"].map(tr.NAMES)
        self.assertIsNotNone(viz.stress_heatmap(res, v.scen, tr.THRESHOLD, v.threshold))


if __name__ == "__main__":
    unittest.main()
