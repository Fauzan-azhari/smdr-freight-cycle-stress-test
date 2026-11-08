"""Posisi awal SMDR per 30 September 2026: profitabilitas, baseline TTM, struktur EBITDA, dan rasio covenant.

Modul ini merakit tabel yang ditampilkan notebook 01 dari data tidy dan hasil baseline. Tidak ada
angka yang dihitung di notebook; notebook hanya memanggil `build()` lalu menyajikan hasilnya.
"""
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from . import baseline, covenant_band as cb, fs_checks

ANNUAL = ["FY2022", "FY2023", "FY2024", "FY2025"]
OUT = Path(baseline.OUT)


@dataclass
class Position:
    quarterly: pd.DataFrame    # indeks kuartal; USD: revenue, gross_profit, ga_expense, ebit; ebit_margin dalam persen
    ttm: pd.DataFrame          # indeks pos; kolom value_usd
    composition: pd.DataFrame  # indeks periode (tahunan dan TTM): ebit, depreciation, ebitda, depreciation_share (persen)
    band: pd.DataFrame         # indeks tahun buku: rasio covenant proforma
    cash: float                # kas dan setara kas konsolidasi, 30 Sep 2026
    integrity: dict            # total uji dan jumlah ketidaksesuaian yang belum dijelaskan


def _quarterly():
    q = pd.read_csv(OUT / "baseline_quarters.csv")
    pick = lambda s, k: q[(q.statement == s) & (q.line_key == k)].set_index("quarter")["value_usd"]
    t = pd.DataFrame({"revenue": pick("IS", "revenue"), "gross_profit": pick("IS", "gross_profit"), "ga_expense": pick("IS", "ga_expense")})
    t["ebit"] = t["gross_profit"] - t["ga_expense"]
    t["ebit_margin"] = t["ebit"] / t["revenue"] * 100
    return t


def _ttm(bridge):
    t = pd.read_csv(OUT / "baseline_ttm.csv").set_index(["statement", "line_key"])["value_usd"]
    ebit = bridge.loc["ebit_ttm", "reconciled_value"]
    ebitda = bridge.loc["ebitda_ttm_operating_pdf_basis", "reconciled_value"]
    rows = [("Pendapatan", t[("IS", "revenue")]), ("Laba bruto", t[("IS", "gross_profit")]),
            ("Beban umum dan administrasi", t[("IS", "ga_expense")]), ("EBIT", ebit), ("Penyusutan", ebitda - ebit),
            ("EBITDA operasi", ebitda), ("Beban bunga dan keuangan", t[("IS", "finance_expense")]),
            ("Laba periode berjalan", t[("IS", "profit_period")]), ("Arus kas operasi", t[("CF", "cfo")]),
            ("Arus kas investasi", t[("CF", "cfi")]), ("Arus kas pendanaan", t[("CF", "cff")])]
    return pd.DataFrame(rows, columns=["pos", "value_usd"]).set_index("pos")


def _composition(w, bridge):
    rows = {}
    for p in ANNUAL:
        ebit = w.loc[("IS", "gross_profit"), p] - w.loc[("IS", "ga_expense"), p]
        rows[p] = (ebit, cb.ebitda_operating(w, p) - ebit)
    ebit = bridge.loc["ebit_ttm", "reconciled_value"]
    rows["TTM"] = (ebit, bridge.loc["ebitda_ttm_operating_pdf_basis", "reconciled_value"] - ebit)
    c = pd.DataFrame(rows, index=["ebit", "depreciation"]).T
    c["ebitda"] = c["ebit"] + c["depreciation"]
    c["depreciation_share"] = c["depreciation"] / c["ebitda"] * 100
    return c


def build():
    if not (OUT / "baseline_bridge.csv").exists():
        raise FileNotFoundError("Hasil baseline belum ada; jalankan `python -m smdr.baseline` lebih dulu.")
    w = baseline.load_wide()
    bridge = pd.read_csv(OUT / "baseline_bridge.csv").set_index("metric")
    comp = _composition(w, bridge)
    band = cb.clause_band(w, {p: comp.loc[p, "ebitda"] for p in ANNUAL})
    values, dictionary = fs_checks.load()
    results, known = fs_checks.run_checks(values, dictionary), fs_checks.load_exceptions()
    unexplained = [r for r in results if r["status"] == "FAIL" and (r["check_id"], r["period"]) not in known]
    return Position(quarterly=_quarterly(), ttm=_ttm(bridge), composition=comp, band=band.set_index("period"),
                    cash=float(w.loc[("BS", "cash"), "9M26"]), integrity={"total": len(results), "unexplained": len(unexplained)})
