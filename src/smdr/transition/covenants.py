"""Rangkaian uji covenant: dua himpunan yang berbeda sumbernya.

1. Covenant sukuk (Perjanjian Perwaliamanatan Pasal 6.3.8; S1 hlm. 38, S2 hlm. 33, S3 hlm. 30; diuji pada laporan tahunan audit):
   - Debt to Equity <= 2,5x (utang berbunga / total ekuitas)
   - EBITDA / (Beban Pokok Pinjaman + Beban Bunga Pinjaman) >= 1,10x; Beban Pokok Pinjaman = bagian lancar liabilitas jangka panjang
     berbunga pada laporan audit. Ukuran 'cover' di deck memakai definisi konservatif (sewa lancar dan pokok sukuk jatuh tempo 12 bulan
     ikut penyebut; keputusan D08), sehingga lebih ketat daripada DSCR yang dilaporkan perusahaan (2,11x pada FY2025).
2. Perjanjian kredit (tabel 'rasio yang dipersyaratkan', S2 hlm. 22, S3 hlm. 46): Current Ratio >= 1,10x; Debt to Equity <= 2,50x;
   DSCR >= 1,10x; Net Debt to EBITDA <= 3,00x; EBITDA / Interest >= 2,50x.

Definisi yang dapat direproduksi dari laporan keuangan (lihat tests/test_covenants.py):
   Net Debt to EBITDA = (utang bank + sukuk + liabilitas sewa) / EBITDA, tanpa mengurangi kas. FY2022 = 0,66x dan FY2025 = 2,52x, persis
   angka yang dilaporkan perusahaan. EBITDA / Interest = EBITDA / beban keuangan, persis angka yang dilaporkan (6,76x pada FY2025).
   DSCR yang dilaporkan tidak dapat direproduksi dari komponen neraca (penyebut tersirat sekitar USD 91 juta pada FY2024 dan FY2025).

Asumsi proyeksi (pro forma, bukan ramalan): utang bank dan liabilitas sewa ditahan pada posisi 30 Sep 2026, tanpa utang baru
(pembangunan kapal dibiayai kas, seperti pada model kas); pokok sukuk berkurang pada jatuh tempo bullet. Setiap USD 100 juta utang baru
menambah Net Debt/EBITDA sekitar 0,5x pada EBITDA USD 200 juta.
"""
import datetime as dt

import pandas as pd

from .. import baseline

TH_ND, TH_ICR, TH_CR, TH_COVER = 3.0, 2.5, 1.10, 1.10
SUKUK_DUE_12M = {"FY2027": 19.1, "FY2028": 39.5, "FY2029": 28.2, "FY2030": 0.0}   # pokok jatuh tempo dalam 12 bulan setelah tanggal uji (USD juta)
FYS = ("FY2027", "FY2028", "FY2029", "FY2030")


def reported_nd_ebitda(w, period, ebitda):
    """Net Debt to EBITDA menurut definisi yang mereproduksi angka perusahaan: (bank + sukuk + sewa) / EBITDA (USD juta)."""
    g = lambda k: 0.0 if pd.isna(w.loc[("BS", k), period]) else float(w.loc[("BS", k), period]) / 1e6
    debt = sum(g(k) for k in ("bank_short_term", "bank_long_term_current", "bank_long_term", "sukuk_current", "sukuk_long_term", "lease_current", "lease_long_term"))
    return debt / ebitda


def base_position(w, period="9M26"):
    g = lambda k: 0.0 if pd.isna(w.loc[("BS", k), period]) else float(w.loc[("BS", k), period]) / 1e6
    return {"bank": g("bank_short_term") + g("bank_long_term_current") + g("bank_long_term"), "sukuk": g("sukuk_current") + g("sukuk_long_term"),
            "lease": g("lease_current") + g("lease_long_term"), "equity": g("total_equity"), "ca": g("total_current_assets"), "cl": g("total_current_liabilities")}


def suite(paths, den, inp, start_liquidity, w=None, groups=None):
    """paths: {(skenario, case): DataFrame bulanan dengan kolom ebitda dan liquidity}; den: penyebut cover per FY (DataFrame, indeks FY)."""
    w = baseline.load_wide() if w is None else w
    b = base_position(w)
    rows = []
    for (sc, case), df in paths.items():
        e = df["ebitda"].groupby(df.index.str[:4]).sum()
        for fy in FYS:
            y = fy[2:]
            ebitda = float(e[y])
            sukuk = b["sukuk"] - sum(v for k, v in SUKUK_DUE_12M.items() if k < fy)   # pokok yang sudah jatuh tempo sebelum tanggal uji
            debt = b["bank"] + b["lease"] + max(sukuk, 0.0)
            liq = float(df["liquidity"][f"{y}-12"])
            ca = b["ca"] - (start_liquidity - liq)
            cl = b["cl"] + SUKUK_DUE_12M[fy]
            rows.append({"skenario": sc, "case": case, "fy": fy, "ebitda": ebitda,
                         "cover": ebitda / float(den.loc[fy, "penyebut"]), "nd_ebitda": debt / ebitda,
                         "icr": ebitda / inp["interest_ttm"], "current_ratio": ca / cl, "liquidity": liq,
                         "penyebut": float(den.loc[fy, "penyebut"])})
    t = pd.DataFrame(rows)
    if groups:
        t["kelompok"] = t["skenario"].map(groups)
    return t


def cure_requirement(row, th=TH_COVER):
    """Pengurangan penyebut (USD juta) yang dibutuhkan agar cover kembali ke batas; 0 bila sudah di atas batas."""
    return max(0.0, row["penyebut"] - row["ebitda"] / th)


def lever_capacity(inp):
    """Kapasitas tuas penyebut (USD juta, maksimum teoretis): memperpanjang tenor bank memindahkan bagian lancar bank ke jangka panjang;
    refinancing sukuk yang jatuh tempo dalam 12 bulan; sewa lancar tidak dihitung sebagai tuas (kontrak dan pengaturan pihak lain)."""
    return {"bank": float(inp["bank_current"]), "sukuk_FY2027": SUKUK_DUE_12M["FY2027"], "sukuk_FY2028": SUKUK_DUE_12M["FY2028"]}
