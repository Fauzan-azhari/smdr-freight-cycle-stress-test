"""Kalender pembayaran: tanggal kontraktual dan penyesuaian hari kerja.

Dokumen sukuk menetapkan bahwa pembayaran yang jatuh pada bukan hari kerja dilakukan pada hari kerja
berikutnya tanpa kompensasi. Kalender hari libur bank belum tersedia, sehingga penyesuaian di sini
hanya untuk akhir pekan dan berstatus asumsi.
"""
import datetime as dt

from dateutil.relativedelta import relativedelta

PAYMENT_DATE_BASIS = "assumed_weekend_only"


def next_business_day(d):
    """Geser ke Senin bila jatuh pada Sabtu atau Minggu."""
    while d.weekday() >= 5:
        d += dt.timedelta(days=1)
    return d


def quarterly_dates(first, last):
    """Tanggal kontraktual setiap tiga bulan dari `first` sampai `last` (termasuk), hari dalam bulan tetap."""
    out, i = [], 0
    while True:
        d = first + relativedelta(months=3 * i)
        if d > last:
            return out
        out.append(d)
        i += 1
