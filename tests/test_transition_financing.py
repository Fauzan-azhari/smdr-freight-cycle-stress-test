import datetime as dt
import unittest

import pandas as pd

from smdr import datapaths
from smdr.transition import calendar as cal, financing, maturity


class CalendarTest(unittest.TestCase):
    def test_weekend_rolls_to_monday(self):
        self.assertEqual(cal.next_business_day(dt.date(2026, 11, 21)), dt.date(2026, 11, 23))  # Sabtu
        self.assertEqual(cal.next_business_day(dt.date(2026, 10, 4)), dt.date(2026, 10, 5))    # Minggu
        self.assertEqual(cal.next_business_day(dt.date(2028, 8, 2)), dt.date(2028, 8, 2))      # Rabu

    def test_quarterly_dates_keep_day_of_month(self):
        d = cal.quarterly_dates(dt.date(2026, 8, 21), dt.date(2029, 5, 21))
        self.assertEqual(len(d), 12)
        self.assertTrue(all(x.day == 21 for x in d))
        self.assertEqual(d[-1], dt.date(2029, 5, 21))


class DebtServiceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fac = financing.load_facilities()
        cls.ev = financing.debt_service(cls.fac)

    def test_event_counts_and_principal(self):
        self.assertEqual((self.ev.event_type == "coupon").sum(), 35)
        p = self.ev[self.ev.event_type == "principal"].set_index("facility_id")["amount"]
        self.assertEqual(p.to_dict(), {"S1B": 339175000000.0, "S2": 500000000000.0, "S3": 700000000000.0})

    def test_annual_coupon_equals_four_quarters(self):
        for fid, annual in (("S1B", 32052037500), ("S2", 44250000000), ("S3", 57750000000)):
            amt = self.ev[(self.ev.facility_id == fid) & (self.ev.event_type == "coupon")]["amount"].iloc[0]
            self.assertAlmostEqual(amt * 4, annual, delta=1)

    def test_coupon_rate_matches_stated_rate(self):
        for r in self.fac.itertuples():
            self.assertAlmostEqual(r.annual_coupon_amount / r.nominal_limit, r.fixed_rate, places=6)

    def test_november_2026_payment_matches_external_schedule(self):
        s3 = self.ev[(self.ev.facility_id == "S3") & (self.ev.event_type == "coupon")].iloc[0]
        self.assertEqual(str(s3["payment_date"]), "2026-11-23")  # jadwal KSEI: 23 November 2026

    def test_current_portion_precedes_cash_by_a_year(self):
        full = maturity.ev_all(self.fac)
        cp = {y: financing.current_portion(full, dt.date(y, 12, 31)) for y in (2026, 2027, 2028, 2029, 2030)}
        self.assertEqual(cp, {2026: 0.0, 2027: 339175000000.0, 2028: 700000000000.0, 2029: 500000000000.0, 2030: 0.0})

    def test_no_event_before_projection_start(self):
        self.assertTrue((pd.to_datetime(self.ev["payment_date"]) >= pd.Timestamp("2026-10-01")).all())

    def test_generated_file_matches_code(self):
        stored = pd.read_csv(datapaths.table("financing_events.csv"))
        self.assertEqual(len(stored), len(self.ev))
        self.assertAlmostEqual(stored["amount"].sum(), self.ev["amount"].sum(), delta=1)


class MaturityTest(unittest.TestCase):
    def test_nominal_reconciles_to_balance_sheet(self):
        m = maturity.build()
        self.assertAlmostEqual(m.balance_check["nominal_idr"], 1539175000000.0, delta=1)
        self.assertLess(abs(m.balance_check["gap_pct"]), 2.0)  # nominal vs saldo neraca, selisih kecil
        self.assertAlmostEqual(m.annual["pokok"].sum() * m.fx * 1e6, 1539175000000.0, delta=1)

    def test_unmatched_claims_are_not_projects(self):
        m = maturity.build()
        unmatched = m.claims[m.claims.match_status == "unmatched"]
        self.assertGreaterEqual(len(unmatched), 2)
        self.assertTrue(unmatched["project_id"].isna().all())


if __name__ == "__main__":
    unittest.main()
