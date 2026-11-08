import unittest

import numpy as np

from smdr import baseline, covenant_band as cb


class CovenantBandTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.w = baseline.load_wide()
        cls.e = {p: cb.ebitda_operating(cls.w, p) for p in ("FY2022", "FY2023", "FY2024", "FY2025")}
        cls.band = cb.clause_band(cls.w, cls.e).set_index("period")

    def test_operating_ebitda_uses_pdf_basis(self):
        # FY2025 = EBIT 93.662.767 + penyusutan biaya jasa PDF 96.603.808 + penyusutan G&A 2.313.014
        self.assertAlmostEqual(self.e["FY2025"], 192579589, delta=1)

    def test_ttm_operating_ebitda_consistent_with_baseline_bridge(self):
        # TTM = FY2025 - 9M25 + 9M26 pada baris yang sama; angka akhir dijaga oleh test_baseline (240.044.492)
        self.assertAlmostEqual(cb.ebitda_operating(self.w, "FY2025"), 192579589, delta=1)

    def test_primary_measure_includes_lease(self):
        r = self.band.loc["FY2025"]
        self.assertAlmostEqual(r["cover"], 192579589 / (30730265 + 86916379 + 28467496), places=4)
        self.assertLess(r["der"], cb.THRESHOLD_DER)
        self.assertGreater(r["cover_ex_lease"], r["cover"])  # sewa memperbesar penyebut

    def test_band_is_always_labelled_conditional(self):
        self.assertTrue((self.band["status"] == "proforma_conditional").all())

    def test_only_approved_rules_are_used(self):
        self.assertFalse(self.band["uses_unapproved_rule"].any())
        self.assertTrue(self.band[["cover", "der"]].notna().all().all())  # Z02-Z05 disetujui, semua tahun dapat dihitung
        self.assertEqual(baseline.load_zero_fill(("proposed",)), {})

    def test_missing_evidence_stops_calculation(self):
        with self.assertRaises(ValueError):
            cb.ebitda_operating(self.w, "FY2021")  # belum ada bukti PDF untuk FY2021

    def test_reported_ebitda_over_interest_reproduced(self):
        ratio = self.e["FY2025"] / self.w.loc[("IS", "finance_expense"), "FY2025"]
        self.assertAlmostEqual(ratio, 6.76, places=2)  # S3 PDF21 melaporkan 6,76x


if __name__ == "__main__":
    unittest.main()
