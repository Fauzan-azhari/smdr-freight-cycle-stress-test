import unittest

import numpy as np

from smdr.transition import cashflow as cf
from smdr.transition import macro, mitigation as mt
from smdr.transition import transmission as tr


class MitigationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inp, cls.a, cls.a_op, cls.paths = cf._init(), cf.assumptions(), tr.assumptions(), macro.build_paths()
        cls.trig = 2 * cls.inp["opex_month"]
        cls.th = cf.min_cash(cls.inp, cls.a, "central")
        cls.go = staticmethod(lambda sid="MS-BASE", case="adverse", **kw: cf.run(sid, case, cls.inp, cls.paths, cls.a_op, cls.a, **kw))
        cls.none = cls.go()

    def test_no_trigger_or_no_breach_changes_nothing(self):
        same = self.go(mit=cf.Mitigation(None, 0.3, 1.0, 1.0))
        self.assertTrue(np.allclose(same["closing"], self.none["closing"]))
        central = cf.run("MS-BASE", "central", self.inp, self.paths, self.a_op, self.a, mit=cf.Mitigation(30.0, 0.3, 1.0, 1.0))   # kas tidak pernah di bawah 30
        base = cf.run("MS-BASE", "central", self.inp, self.paths, self.a_op, self.a)
        self.assertTrue(np.allclose(central["closing"], base["closing"]))

    def test_levers_start_after_trigger_plus_lead_time(self):
        df = self.go(mit=cf.Mitigation(self.trig, 0.3, 1.0, 1.0))
        tm = df.attrs["trigger_month"]
        self.assertTrue(self.none["closing"][self.none.index < tm].min() >= self.trig)    # sebelum pemicu saldo di atas threshold
        self.assertLess(self.none.loc[tm, "closing"], self.trig)
        months = list(df.index)
        i = months.index(tm)
        self.assertEqual(df.attrs["start"], {"capex": months[i + 2], "dividend": months[i + 3], "bank": months[i + 6]})
        self.assertTrue(np.allclose(df["closing"].iloc[:i + 2], self.none["closing"].iloc[:i + 2]))   # belum ada pengaruh sebelum waktu tunggu

    def test_each_lever_improves_minimum_liquidity(self):
        base = self.none["liquidity"].min()
        for kw in (dict(capex_cut=0.3), dict(dividend_cut=1.0), dict(bank_redraw=1.0)):
            self.assertGreater(self.go(mit=cf.Mitigation(self.trig, **kw))["liquidity"].min(), base, kw)

    def test_capex_deferral_is_repaid_after_window(self):
        df = self.go(mit=cf.Mitigation(self.trig, capex_cut=0.3))
        s0 = list(df.index).index(df.attrs["start"]["capex"])
        win = slice(s0, s0 + 24)
        self.assertGreater(df["maintenance_capex"].iloc[win].sum(), self.none["maintenance_capex"].iloc[win].sum())   # hemat di jendela (kurang negatif)
        after = slice(s0 + 24, None)
        self.assertLess(df["maintenance_capex"].iloc[after].sum(), self.none["maintenance_capex"].iloc[after].sum())   # dibayar kembali sesudahnya

    def test_dividend_cut_removes_later_payments_only(self):
        df = self.go(mit=cf.Mitigation(self.trig, dividend_cut=1.0))
        start = df.attrs["start"]["dividend"]
        for m in df.index:
            if m[5:] == "06":
                self.assertEqual(df.loc[m, "dividend"] == 0.0, m >= start, m)

    def test_tariff_lamps_follow_the_tightest_covenant_test(self):
        v = mt.build_view(cf.build_view(), tr.build_view())
        yellow = v.lamps.loc["Tarif angkut terhadap TTM", "Kuning (siaga)"]
        self.assertIn("1,5%", yellow)                                   # separuh dari 3,0% (uji FY2028), bukan 3,4% dari FY2027
        self.assertIn("2,4%", v.lamps.loc["Tarif angkut terhadap TTM", "Merah (bertindak)"])

    def test_register_and_lamps(self):
        r = mt.register()
        self.assertEqual(len(r), 4)
        self.assertEqual(r.set_index("tuas").loc["Sesuaikan sewa kapal", "availability_status"], "data_needed")   # tidak dikuantifikasi tanpa data
        self.assertTrue((r[r.mitigation_id != "MT04"].availability_status == "assumed").all())

    def test_view_and_charts(self):
        import matplotlib
        matplotlib.use("Agg")
        from smdr import viz
        v = mt.build_view()
        self.assertEqual(len(v.impact), 10)
        self.assertIsNotNone(viz.mitigation_levers(v))
        self.assertIsNotNone(viz.mitigation_paths(v))
        t = v.impact.set_index(["scenario", "tuas"])["min_liquidity"]
        self.assertGreater(t[("Dasar", "Ketiga tuas bersama")], t[("Dasar", "Bank bergulir")])


if __name__ == "__main__":
    unittest.main()
