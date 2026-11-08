import os, unittest
import pandas as pd
from smdr import baseline, datapaths
from smdr.transition import robustness as rb



class RobustnessTest(unittest.TestCase):
    def test_wci_high_position_is_two_episodes(self):
        w = pd.read_csv(datapaths.table("wci_composite_weekly.csv"), parse_dates=["date"]).set_index("date")["wci"]
        ep = rb.wci_episodes(w[~w.index.duplicated()])
        self.assertEqual(len(ep), 2)
        self.assertGreater(ep.perubahan_52p_dari_awal.iloc[0], 0)    # 2020-21: naik lanjut
        self.assertLess(ep.perubahan_52p_dari_awal.iloc[1], 0)       # 2024: turun

    def test_capacity_and_cover_readings(self):
        s = pd.read_csv(datapaths.table("covenant_suite.csv"))
        cap = rb.new_debt_capacity(s)
        row = cap[(cap.skenario == "Kelebihan kapasitas") & (cap.fy == "FY2027")].iloc[0]
        self.assertLess(row.ruang_utang_baru, 0)          # Overcapacity sudah menembus 3,0x
        base = cap[(cap.skenario == "Dasar") & (cap.fy == "FY2027")].iloc[0]
        self.assertAlmostEqual(base.ruang_utang_baru, 3.0 * base.ebitda - base.utang)


if __name__ == "__main__":
    unittest.main()


# --- revisi 7 Nov 2026 -------------------------------------------------------------------------------------------------
class ConsistentResultsTest(unittest.TestCase):
    def test_dscr_denominator_stable_and_lease_reading_rejected(self):
        d = rb.dscr_denominator(baseline.load_wide())
        self.assertLess(abs(d["implied"]["FY2024"] - d["implied"]["FY2025"]), 0.5)   # penyebut tersirat stabil sekitar USD 91 juta
        self.assertTrue(90 < d["den"] < 92.5)
        self.assertTrue(d["fy2025_with_lease"] < 1.4 < d["fy2025_reported"])        # bacaan dengan sewa lancar tidak mereproduksi 2,11x

    def test_consistent_results_central(self):
        t, P, th = rb.consistent_results()
        c = t[t.case == "central"].set_index("skenario")
        self.assertAlmostEqual(c.loc["Kelebihan kapasitas", "nd_FY2027"], 3.016, delta=0.005)
        self.assertAlmostEqual(c.loc["Permintaan lemah dan kelebihan kapasitas", "nd_FY2027"], 3.412, delta=0.005)
        self.assertTrue((c[["cover_FY2027", "cover_FY2028"]] > 1.10).all().all())
        self.assertTrue((c["current_ratio_min"] > 1.10).all())
        self.assertTrue(c["first_below"].isna().all())
        self.assertTrue((c["nd_FY2026"] < 2.7).all())                                 # pengujian 31 Des 2026 aman di semua skenario
        self.assertTrue((c["nd_FY2027_amortisasi"] <= c["nd_FY2027"]).all())

    def test_severity_ranking_holds(self):
        s = rb.severity_check()
        self.assertLess(abs(s["d_brent"]), abs(s["d_rate"]))
        self.assertLess(abs(s["d_fx"]), abs(s["d_rate"]))

    def test_mitigation_package_is_jointly_safe(self):
        t, P, th = rb.consistent_results()
        c = lambda pd_, ds, k: rb.mitigation_test(t, P, pd_, ds).set_index(["skenario", "case"]).loc[(k, "central")]
        o = c(54.0, False, "Kelebihan kapasitas")
        self.assertLessEqual(o.nd_FY2027, 2.705); self.assertGreater(o.current_ratio_min, 1.21); self.assertGreater(o.min_liquidity, th)
        w = c(107.0, False, "Permintaan lemah dan kelebihan kapasitas")
        self.assertLess(w.current_ratio_min, 1.10)                                   # pelunasan saja menembus Current Ratio
        wd = c(107.0, True, "Permintaan lemah dan kelebihan kapasitas")
        self.assertGreater(wd.current_ratio_min, 1.10); self.assertGreater(wd.min_liquidity, th)

    def test_historical_ebitda_reaches_threshold(self):
        from smdr.transition import covenants as cvn
        b = cvn.base_position(baseline.load_wide())
        h = rb.historical_test(b["bank"] + b["sukuk"] + b["lease"])
        self.assertAlmostEqual(h.loc["FY2024", "nd"], 2.97, delta=0.01)          # basis operasi: nyaris, tidak melewati 3,00x

    def test_quarterly_first_breach(self):
        t, P, th = rb.consistent_results()
        q = rb.quarterly_tests(P, "central")
        f = rb.first_quarter(q)
        self.assertEqual(f[("Kelebihan kapasitas", "central")], "2027-09")
        self.assertEqual(f[("Permintaan lemah dan kelebihan kapasitas", "central")], "2027-09")
        m = q[q.quarter == "2027-03"].set_index("skenario")["nd"]
        self.assertTrue(m["Kelebihan kapasitas"] >= 2.495 and m["Permintaan lemah dan kelebihan kapasitas"] >= 2.495)
        self.assertTrue((m.drop(["Kelebihan kapasitas", "Permintaan lemah dan kelebihan kapasitas"]) < 2.5).all())   # early warning memisahkan
        self.assertTrue((q.dscr_bank > 1.10).all())

    def test_cash_tornado_ranking(self):
        t = rb.cash_tornado()
        self.assertEqual(t.parameter.iloc[0], "maintenance_capex")
        self.assertLess(t.attrs["all_adverse"], t.attrs["ref"] + t.d_min_liq.sum() + 50)
