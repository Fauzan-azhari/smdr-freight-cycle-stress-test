"""Uji baseline: kuartal diskrit, TTM, dan jembatan ke benchmark legacy.

    PYTHONPATH=src .venv/bin/python -m smdr.fs_ingest && PYTHONPATH=src .venv/bin/python -m smdr.baseline
    PYTHONPATH=src .venv/bin/python -m unittest discover -s tests
"""
import os
import unittest

import pandas as pd

from smdr import baseline

OUT = baseline.OUT


class BaselineTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.w = baseline.load_wide()
        cls.q = pd.read_csv(os.path.join(OUT, "baseline_quarters.csv"))
        cls.t = pd.read_csv(os.path.join(OUT, "baseline_ttm.csv"))
        cls.b = pd.read_csv(os.path.join(OUT, "baseline_bridge.csv")).set_index("metric")

    def test_legacy_benchmark_reproduced(self):
        for m in ("revenue_ttm", "ebit_ttm", "ebitda_ttm_legacy", "fixed_obligations_ttm",
                  "fixed_charge_cover", "cash_consolidated"):
            self.assertEqual(self.b.loc[m, "status"], "reproduced", m)

    def test_depreciation_9m25_available(self):
        self.assertEqual(self.w.loc[("COGS_NOTE", "depreciation"), "9M25"], 66138018)

    def test_quarters_sum_to_year(self):
        r = self.q[(self.q.statement == "IS") & (self.q.line_key == "revenue")].set_index("quarter")["value_usd"]
        self.assertAlmostEqual(r["2025Q1"] + r["2025Q2"] + r["2025Q3"] + r["2025Q4"], 801694731, delta=1)
        self.assertAlmostEqual(r["2025Q4"], 801694731 - 571556818, delta=1)

    def test_ttm_status_rules(self):
        s = self.t.set_index(["statement", "line_key"])["status"]
        self.assertEqual(s[("IS", "revenue")], "ok")
        self.assertEqual(s[("CF", "lease_payments")], "nd_component")     # tahunan tidak memisahkan sewa
        self.assertEqual(s[("CF", "dividends_received")], "not_comparable")  # galat sumber 9M25
        self.assertTrue(self.t[self.t.status != "ok"]["value_usd"].isna().all())

    def test_zero_fill_only_by_named_rule(self):
        rules = baseline.load_zero_fill()  # hanya aturan berstatus approved
        self.assertEqual(sorted(k[1:] for k in rules), [("sukuk_current", "9M26"), ("sukuk_current", "FY2022"), ("sukuk_current", "FY2024"),
                                                        ("sukuk_current", "FY2025"), ("sukuk_long_term", "FY2022")])
        self.assertTrue(pd.isna(self.w.loc[("BS", "sukuk_current"), "9M26"]))  # data tidy tetap n.d.

    def test_operating_ebitda_bridge(self):
        r = self.b.loc["ebitda_ttm_operating_reconstructed"]
        self.assertEqual(r["status"], "verified_primary")
        self.assertAlmostEqual(r["definition_adjustment"], 2313014 - 1757414 + 1747225, delta=1)  # penyusutan G&A TTM
        self.assertAlmostEqual(r["reconciled_value"], 239946107, delta=1)

    def test_pdf_basis_selected_by_user_decision(self):
        r = self.b.loc["ebitda_ttm_operating_pdf_basis"]
        self.assertEqual(baseline.load_decisions()["D01"], "pdf_audit")
        self.assertEqual(r["status"], "selected")
        self.assertEqual(self.b.loc["ebitda_ttm_operating_reconstructed", "status"], "verified_primary")  # alternatif, tidak dipilih
        self.assertAlmostEqual(r["reconciled_value"], 240044492, delta=1)
        self.assertAlmostEqual(r["reconciled_value"] / 1e6, 240.04, places=2)  # catatan riset: 240,04
        self.assertAlmostEqual(r["reconciled_value"] - self.b.loc["ebitda_ttm_operating_reconstructed", "reconciled_value"], 98385, delta=1)


class NewStatementsTest(unittest.TestCase):
    def test_equity_ppe_debt_tie_to_balance_sheet(self):
        w = baseline.load_wide()
        self.assertEqual(w.loc[("EQ", "total.closing"), "9M26"], w.loc[("BS", "total_equity"), "9M26"])
        self.assertEqual(w.loc[("PPE", "nbv.ppe.closing"), "9M26"], w.loc[("BS", "fixed_assets"), "9M26"])
        self.assertEqual(w.loc[("DEBT_NOTE", "bank_lt_noncurrent"), "FY2025"], w.loc[("BS", "bank_long_term"), "FY2025"])


if __name__ == "__main__":
    unittest.main()
