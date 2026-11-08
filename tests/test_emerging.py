import unittest

import pandas as pd

try:
    import needs_sources as ns
except ImportError:   # dijalankan sebagai tests.test_x
    from tests import needs_sources as ns
from smdr.transition import emerging as em
from smdr.transition import bridge as br
from smdr.transition import transmission as tr


class EmergingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tv, cls.bv = tr.build_view(), br.build_view()
        cls.r, cls.ev = em.build_view(cls.tv, cls.bv)

    @ns.needs("Research")
    def test_local_evidence_quotes_are_found_on_recorded_pages(self):
        self.assertEqual(em.verify(), [])

    def test_every_risk_has_evidence_and_web_rows_have_links(self):
        self.assertEqual(set(self.ev.risk_id), set(self.r.risk_id))
        web = self.ev[self.ev.verifikasi.isin(["web_resmi", "web_media"])]
        self.assertTrue(len(web) >= 6 and web["url"].str.startswith("https://").all() and (web["diakses"] == "2026-11-06").all())
        for rid in ("ER3", "ER5"):                                                    # dua butir yang diverifikasi silang
            self.assertTrue((self.ev[(self.ev.risk_id == rid) & (self.ev.verifikasi == "web_resmi")].shape[0]) >= 1, rid)
        self.assertTrue(self.ev["tanggal"].astype(str).str.len().ge(4).all())

    def test_horizon_and_status_are_valid(self):
        self.assertTrue((self.r.horizon_min <= self.r.horizon_max).all())
        self.assertTrue(self.r.status_uji.isin(["diuji", "sebagian", "belum"]).all())
        self.assertTrue(self.r.kecepatan.isin(["cepat", "sedang", "lambat"]).all())

    def test_measured_impacts_tie_to_the_scenario_and_narrative_tables(self):
        r = self.r.set_index("risk_id")
        e = self.tv.scenarios.set_index(["scenario", "case"])["d_ebitda"]
        self.assertAlmostEqual(r.loc["ER1", "d_central"], e[("Energi bertahan", "central")], places=9)
        n = self.bv.results.set_index(["kisah", "case"])["d_ebitda"]
        self.assertAlmostEqual(r.loc["ER3", "d_central"], n[("Kelebihan kapasitas", "central")], places=9)
        self.assertAlmostEqual(r.loc["ER2", "d_central"], n[("Rute kembali normal", "central")], places=9)

    def test_unmeasured_risks_carry_no_number_and_measured_risks_do(self):
        for x in self.r.itertuples():
            if x.status_uji == "belum":
                self.assertTrue(pd.isna(x.d_central), x.risk_id)
            else:
                self.assertTrue(x.tautan and x.d_central < 0, x.risk_id)

    def test_no_probability_columns(self):
        self.assertFalse(any("prob" in c.lower() for c in self.r.columns))

    def test_tables_and_chart_render(self):
        import matplotlib
        matplotlib.use("Agg")
        from smdr import viz
        self.assertEqual(len(em.radar_table(self.r)), 8)
        self.assertEqual(len(em.sinyal_table(self.ev, self.r)), len(self.ev))
        self.assertIsNotNone(viz.emerging_radar(self.r))


if __name__ == "__main__":
    unittest.main()
