import unittest

import numpy as np

from smdr.transition import bridge as br
from smdr.transition import cashflow as cf
from smdr.transition import cycle as cy
from smdr.transition import macro
from smdr.transition import transmission as tr


class BridgeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cv, cls.sv = cf.build_view(), cy.build_view()
        cls.v = br.build_view(cls.cv, cls.sv)
        cls.inp, cls.a, cls.a_op, cls.paths = cf._init(), cf.assumptions(), tr.assumptions(), macro.build_paths()

    def test_narratives_are_labelled_and_sized_from_recorded_outcomes(self):
        n = self.v.narr
        self.assertEqual(len(n), 4)
        self.assertTrue(n.status.isin(["anchored", "assumed"]).all())
        self.assertTrue((n.tarif < 0).all() and (n.bulan > 0).all())
        self.assertEqual(n.set_index("narrative_id").loc["IN03", "status"], "assumed")        # kisah rute: tanpa data rute

    def test_reported_uses_usable_evidence_only(self):
        r = self.v.reported
        j = r[(r.periode == "FY2024") & (r.cakupan == "jakarta_hub") & (r.jenis == "tarif")]
        self.assertEqual(len(j), 1)
        self.assertEqual(float(j["perubahan"].iloc[0]), -21.0)                               # -29% bukti bersyarat, tidak dipakai

    def test_realized_effective_tariff_identity(self):
        r = self.v.realized
        self.assertAlmostEqual(r.loc["FY2023", "perubahan_pendapatan"], 548.819 / 968.0 - 1, delta=0.01)
        for p in r.index:
            self.assertAlmostEqual((1 + r.loc[p, "tarif_efektif"]) * (1 + r.loc[p, "volume"]), 1 + r.loc[p, "perubahan_pendapatan"], places=9)

    def test_delta_ebitda_matches_transmission_grid(self):
        rs = self.inp["rev_by_service"]
        F, ah = rs["freight_income"], rs["agency_forwarding_ports"] + rs["container_equipment_handling"]
        exposed = (F + rs["agency_forwarding_ports"] + rs["container_equipment_handling"]) / self.inp["revenue"]
        cogs_ex = self.inp["cogs"] - self.inp["cogs_dep"]
        for g, v in ((-0.12, 0.0), (-0.06, -0.05), (-0.12, 0.08)):
            grid = tr.rate_volume_grid(self.inp, self.a_op, [g], [v])[0].iloc[0]["d_ebitda"]
            self.assertAlmostEqual(br.delta_ebitda(F, ah, cogs_ex, exposed, g, v, float(self.a_op.loc["cost_flex_down", "central"])), grid, places=9)

    def test_backtest_is_conservative_in_correction_years_and_exact_in_recovery(self):
        b = self.v.backtest
        self.assertTrue((b.loc[["FY2023", "FY2024"], "model"] < b.loc[["FY2023", "FY2024"], "terealisasi"]).all())   # model lebih negatif = lebih konservatif
        self.assertLess(abs(b.loc["FY2025", "selisih_pct"]), 5.0)
        self.assertTrue(0 < self.v.cost_relief < 1)

    def test_fy2024_calibrated_narrative_reproduces_the_historical_trough(self):
        r = self.v.results.set_index(["id", "case"])
        self.assertAlmostEqual(r.loc[("IN02", "central"), "ebitda_tahunan"], self.sv.hist.loc["FY2024", "ebitda"], delta=3.0)   # selisih basis EBITDA sekitar 2,4

    def test_results_are_ordered_and_adverse_never_better(self):
        r = self.v.results
        for k in r.kisah.unique():
            c, d = r[(r.kisah == k) & (r.case == "central")].iloc[0], r[(r.kisah == k) & (r.case == "adverse")].iloc[0]
            self.assertLessEqual(d["min_liquidity"], c["min_liquidity"] + 1e-9, k)
        c = r[r.case == "central"].set_index("id")
        self.assertEqual(c["cover_min"].idxmin(), "IN04")                                         # gabungan = paling dalam
        self.assertEqual(c["min_liquidity"].idxmin(), "IN04")

    def test_hold_months_is_the_first_breaching_duration(self):
        n = self.v.narr.set_index("narrative_id").loc["IN04"]
        row = n.copy(); row["bulan"] = n["bulan"]
        h = br.hold_months(row, "central", self.inp, self.paths, self.a_op, self.a, self.v.threshold)
        self.assertIsNotNone(h)
        below = lambda m: float((br._run(row, "central", self.inp, self.paths, self.a_op, self.a, m)["liquidity"] - self.v.threshold).min()) < 0
        self.assertTrue(below(h) and not below(h - 1))

    def test_macro_rows_share_the_calendar_year_basis(self):
        mc = cy.macro_cover_table(self.cv, self.sv)
        m = self.v.macro_rows.set_index(["kisah", "case"])
        self.assertAlmostEqual(m.loc[("Dasar", "central"), "cover_min"], mc.loc[("Dasar", "tengah")].min(), places=9)

    def test_charts_render(self):
        import matplotlib
        matplotlib.use("Agg")
        from smdr import viz
        for f in (viz.transmission_chain, ):
            self.assertIsNotNone(f())
        self.assertIsNotNone(viz.observed_vs_headroom(self.v))
        self.assertIsNotNone(viz.industry_heatmap(self.v, "central"))
        self.assertIsNotNone(viz.industry_heatmap(self.v, "adverse"))


if __name__ == "__main__":
    unittest.main()
