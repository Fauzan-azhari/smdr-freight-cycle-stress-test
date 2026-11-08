"""Uji lapisan data makro. Jalankan ingest dan cek dulu:

    PYTHONPATH=src .venv/bin/python -m smdr.macro_ingest && PYTHONPATH=src .venv/bin/python -m smdr.macro_checks
    PYTHONPATH=src .venv/bin/python -m unittest discover -s tests
"""
import os
import unittest

import pandas as pd

from smdr import datapaths, macro_checks, macro_ingest



class MacroDataTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.monthly = pd.read_csv(datapaths.table("macro_monthly.csv"))
        cls.daily = pd.read_csv(datapaths.table("macro_daily.csv"))
        cls.wide = pd.read_csv(datapaths.table("macro_monthly_wide.csv")).set_index("month")

    def test_number_parsing(self):
        self.assertEqual(macro_ingest.num_id(pd.Series(["18.148,3", "0,13%", "-1,66%"])).tolist(), [18148.3, 0.13, -1.66])
        self.assertEqual(macro_ingest.num_en(pd.Series(["2,652.00", "-13.92%"])).tolist(), [2652.0, -13.92])

    def test_known_values(self):
        self.assertEqual(self.wide.loc["2026-10", "usdidr_close"], 18125.0)
        self.assertAlmostEqual(self.wide.loc["2021-01", "brent_avg"], 54.0, delta=5)

    def test_partial_months_flagged(self):
        part = self.monthly[self.monthly["partial"]].groupby("series")["month"].max()
        self.assertEqual(part["usdidr_close"], "2026-11")
        for s in ("brent_avg", "brent_eom"):
            self.assertEqual(part[s], "2026-10", s)
        # 1 kurs + 2 Brent, masing-masing satu bulan terakhir
        self.assertEqual(int(self.monthly["partial"].sum()), 3)

    def test_missing_brent_days_kept_as_nd(self):
        nd = self.daily[(self.daily["series"] == "brent_usd_bbl") & (self.daily["status"] == "nd")]
        self.assertGreater(len(nd), 0)
        self.assertTrue(nd["value"].isna().all())

    def test_no_unexplained_failures(self):
        rows = macro_checks.run()
        exceptions = macro_checks.load_exceptions()
        failed = [r["check_id"] for r in rows if r["status"] == "FAIL" and r["check_id"] not in exceptions]
        self.assertEqual(failed, [])


if __name__ == "__main__":
    unittest.main()
