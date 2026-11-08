"""Kalender jatuh tempo sukuk dan alokasi proyek, dirakit untuk notebook 02.

Seluruh jadwal dibentuk dari tabel fasilitas (financing.py). Konversi ke USD memakai satu kurs ilustrasi
yang dinyatakan eksplisit (penutupan terakhir tersedia), bukan proyeksi kurs.
"""
import datetime as dt
import os
from dataclasses import dataclass

import pandas as pd

from .. import datapaths
from .. import baseline
from . import financing

TEST_YEARS = [2026, 2027, 2028, 2029, 2030]


@dataclass
class Maturity:
    fx: float                 # IDR per USD, ilustrasi
    fx_month: str
    facilities: pd.DataFrame
    events: pd.DataFrame      # jadwal pembayaran (IDR)
    annual: pd.DataFrame      # per tahun kalender: imbalan, pokok, total (USD juta)
    timing: pd.DataFrame      # per tahun buku: pokok yang masuk bagian lancar vs pokok yang dibayar tunai (USD juta)
    balance_check: dict       # rekonsiliasi nominal sukuk terhadap saldo neraca
    projects: pd.DataFrame
    claims: pd.DataFrame
    allocation_total: float   # total alokasi dana kapal pada sukuk Tahap III (IDR)
    fleet: dict               # angka program armada dari dokumen dan pengumuman (IDR atau jumlah kapal)


def _last_fx():
    m = pd.read_csv(datapaths.table("macro_monthly_wide.csv")).dropna(subset=["usdidr_close"])
    return float(m["usdidr_close"].iloc[-1]), str(m["month"].iloc[-1])


def build():
    fx, fx_month = _last_fx()
    fac = financing.load_facilities()
    ev = financing.debt_service(fac)
    ev["year"] = pd.to_datetime(ev["payment_date"]).dt.year
    usd = lambda x: x / fx / 1e6
    annual = ev.pivot_table(index="year", columns="event_type", values="amount", aggfunc="sum", fill_value=0).rename(
        columns={"coupon": "imbalan", "principal": "pokok"})
    annual = usd(annual)
    annual["total"] = annual["imbalan"] + annual["pokok"]
    rows = []
    for y in TEST_YEARS:
        paid = ev[(ev.event_type == "principal") & (ev.year == y)]["amount"].sum()
        rows.append((y, usd(financing.current_portion(ev_all(fac), dt.date(y, 12, 31))), usd(paid)))
    timing = pd.DataFrame(rows, columns=["tahun", "bagian_lancar", "dibayar_tunai"]).set_index("tahun")
    # nominal seluruh seri terhadap saldo neraca konsolidasi (kurs penutupan bulan neraca)
    w = baseline.load_wide()
    sep_close = float(pd.read_csv(datapaths.table("macro_monthly_wide.csv")).set_index("month").loc["2026-09", "usdidr_close"])
    nominal_usd = financing.outstanding_principal(fac, dt.date(2026, 9, 30)) / sep_close
    carrying = float(w.loc[("BS", "sukuk_long_term"), "9M26"])
    check = {"nominal_idr": financing.outstanding_principal(fac, dt.date(2026, 9, 30)), "fx_sep": sep_close,
             "nominal_usd": nominal_usd, "carrying_usd": carrying, "gap_pct": (nominal_usd / carrying - 1) * 100}
    projects = pd.read_csv(datapaths.table("projects.csv"))
    claims = pd.read_csv(datapaths.table("project_aliases.csv"))
    e = pd.read_csv(datapaths.table("evidence.csv")).set_index("evidence_id")["value"]
    fleet = {"chem_total": float(e["EV-S3-CT-TOTAL"]), "container_net": float(e["EV-S3-CV-NET"]),
             "gsm_funding": float(fac.set_index("facility_id").loc["S2", "nominal_limit"]),
             "contracted": int(float(e["EV-N-KONTAN-5"])), "planned": int(float(e["EV-N-KONTAN-4"])), "ssl_units": int(float(e["EV-N-SSL-UNITS"]))}
    allocation = float(pd.read_csv(datapaths.table("capex_milestones.csv"))["amount"].sum())
    return Maturity(fx, fx_month, fac, ev, annual, timing, check, projects, claims, allocation, fleet)


def ev_all(fac):
    """Seluruh pokok sepanjang umur seri (tanpa batas awal proyeksi), untuk klasifikasi bagian lancar."""
    return financing.debt_service(fac, start=dt.date(2000, 1, 1))
