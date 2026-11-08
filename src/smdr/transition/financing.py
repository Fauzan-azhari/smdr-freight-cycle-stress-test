"""Jadwal imbalan dan pokok sukuk dari tabel fasilitas, serta bagian lancar pada tanggal neraca.

Imbalan triwulanan = imbalan tahunan yang tercantum pada dokumen / 4 (basis 30/360, setiap triwulan 90 hari).
Pokok dibayar sekaligus (bullet) pada jatuh tempo. Nilai nominal dalam IDR; konversi ke USD dilakukan pada
lapisan penyajian dengan kurs yang dinyatakan secara eksplisit.
"""
import datetime as dt
import os

import pandas as pd
from dateutil.relativedelta import relativedelta

from .. import baseline, datapaths
from . import calendar as cal

PROJECTION_START = dt.date(2026, 10, 1)  # setelah cutoff keuangan 30 September 2026


def load_facilities():
    f = pd.read_csv(datapaths.table("financing_facilities.csv"))
    for col in ("first_coupon_date", "maturity_date", "issue_date"):
        f[col] = pd.to_datetime(f[col]).dt.date
    return f


def debt_service(facilities=None, start=PROJECTION_START):
    """Peristiwa pembayaran per fasilitas sejak `start`: imbalan triwulanan dan pokok pada jatuh tempo."""
    facilities = load_facilities() if facilities is None else facilities
    rows = []
    for r in facilities.itertuples():
        quarterly = r.annual_coupon_amount / 4.0
        for d in cal.quarterly_dates(r.first_coupon_date, r.maturity_date):
            if d >= start:
                rows.append(dict(facility_id=r.facility_id, event_type="coupon", contractual_date=d,
                                 payment_date=cal.next_business_day(d), amount=quarterly, currency=r.currency))
        if r.maturity_date >= start:
            rows.append(dict(facility_id=r.facility_id, event_type="principal", contractual_date=r.maturity_date,
                             payment_date=cal.next_business_day(r.maturity_date), amount=float(r.nominal_limit), currency=r.currency))
    ev = pd.DataFrame(rows).sort_values(["payment_date", "facility_id", "event_type"]).reset_index(drop=True)
    ev.insert(0, "event_id", ["FE%03d" % (i + 1) for i in range(len(ev))])
    ev["status"] = "scheduled"
    ev["payment_date_basis"] = cal.PAYMENT_DATE_BASIS
    return ev


def current_portion(events, as_of):
    """Pokok yang jatuh tempo dalam 12 bulan setelah `as_of` (klasifikasi bagian lancar pada tanggal neraca)."""
    limit = as_of + relativedelta(months=12)
    p = events[(events.event_type == "principal") & (events.contractual_date > as_of) & (events.contractual_date <= limit)]
    return float(p["amount"].sum())


def outstanding_principal(facilities, as_of):
    """Pokok nominal yang belum jatuh tempo pada `as_of` (seri yang sudah diterbitkan)."""
    f = facilities[(facilities.issue_date <= as_of) & (facilities.maturity_date > as_of)]
    return float(f["nominal_limit"].sum())


def write_events(path=None):
    ev = debt_service()
    ev.to_csv(path or datapaths.table("financing_events.csv"), index=False)
    return ev


if __name__ == "__main__":
    e = write_events()
    print("%d peristiwa: %d imbalan, %d pokok" % (len(e), (e.event_type == "coupon").sum(), (e.event_type == "principal").sum()))
