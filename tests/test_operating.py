import os
import unittest

import pandas as pd

try:
    import needs_sources as ns
except ImportError:   # dijalankan sebagai tests.test_x
    from tests import needs_sources as ns
from smdr import baseline, datapaths, operating

ALLOWED_ACCEPTANCE = {"usable", "conditional", "quarantined"}


class OperatingDataTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.df = operating.load()

    @ns.needs("Annual-Report")
    def test_every_value_is_found_on_its_cited_page(self):
        ok = operating.verify_tokens(self.df)
        self.assertTrue(ok.all(), self.df[~ok][["metric_key", "period", "source_id", "pdf_page"]].to_dict("records"))

    def test_reconciliation_checks_pass(self):
        res = operating.run_checks(self.df, verify=False)
        self.assertEqual(res[res.status == "FAIL"].check_id.tolist(), [])
        self.assertGreaterEqual((res.status == "PASS").sum(), 5)

    def test_schema_and_references(self):
        m = pd.read_csv(datapaths.table("source_manifest.csv"))
        self.assertTrue(set(self.df.source_id) <= set(m.source_id))
        self.assertTrue(set(self.df.acceptance_status) <= ALLOWED_ACCEPTANCE)
        self.assertTrue(self.df[["source_token", "pdf_page", "unit"]].notna().all().all())

    def test_one_preferred_value_per_series_and_conflicts_kept(self):
        seg = self.df[self.df.series_role == "preferred"].groupby(["metric_key", "scope", "period"]).size()
        self.assertEqual(seg[seg > 1].to_dict(), {})
        for g, rows in self.df[self.df.conflict_group_id.notna()].groupby("conflict_group_id"):
            self.assertEqual((rows.series_role == "preferred").sum(), 1, g)
            self.assertGreaterEqual(len(rows), 2, g)  # vintage yang bertentangan dipertahankan, tidak ditimpa

    def test_quarantined_values_never_preferred(self):
        q = self.df[self.df.acceptance_status == "quarantined"]
        self.assertTrue((q.series_role == "excluded").all())

    def test_known_values(self):
        v = lambda mk, sc, p: float(self.df[(self.df.metric_key == mk) & (self.df.scope == sc) & (self.df.period == p) & (self.df.series_role != "vintage")].value.iloc[0])
        self.assertEqual(v("segment_revenue", "shipping", "FY2025"), 640.3)
        self.assertEqual(v("fleet_operational_control", "group_operational_control", "FY2025"), 42)
        self.assertEqual(v("energy_total", "group", "FY2025"), 6570542)

    def test_segment_note_ties_and_confirms_depreciation_basis(self):
        res = operating.run_checks(self.df, verify=False).set_index("check_id")
        for cid in ("FS_SEG_SUM", "FS_PROFIT", "FS_DA", "FS_GEO", "FS_TIES_AR", "THROUGHPUT_GROWTH"):
            self.assertEqual(res.loc[cid, "status"], "PASS", cid)
        v = lambda mk, sc, p: float(self.df[(self.df.metric_key == mk) & (self.df.scope == sc) & (self.df.period == p)].value.iloc[0])
        self.assertEqual(v("fs_segment_revenue", "shipping_agency", "FY2025"), 640275879)
        self.assertEqual(v("fs_segment_da", "consolidated", "FY2025"), 98916822)  # = 96.603.808 (basis PDF) + 2.313.014
        self.assertEqual(v("fs_segment_da", "consolidated", "9M26"), 111845806)

    def test_resolved_vintage_conflicts_are_confirmed_by_financial_statements(self):
        c = self.df[(self.df.metric_key == "segment_revenue") & (self.df.series_role == "preferred") & (self.df.period == "FY2022")]
        self.assertTrue((c.acceptance_status == "usable").all())  # dikonfirmasi laporan keuangan diaudit

    def test_ttm_revenue_by_service_ties_to_baseline(self):
        r = self.df[self.df.domain == "revenue_by_service"].pivot_table(index="metric_key", columns="period", values="value")
        ttm = (r["FY2025"] - r["9M25"] + r["9M26"]).sum()
        self.assertAlmostEqual(ttm, 877511474, delta=1)  # sama dengan pendapatan TTM pada baseline


if __name__ == "__main__":
    unittest.main()
