"""Data seluruh grafik deck, dibangun dari modul src/smdr dan di-cache agar iterasi desain cepat.

Jalankan `python deck_v5/data.py` untuk membangun ulang cache (sekitar dua menit).
"""
import datetime as dt
import os
import pickle
import sys


import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "src"))
CACHE = os.path.join(HERE, "cache.pkl")

from smdr import datapaths  # noqa: E402  (sys.path disiapkan di atas)


def build():
    """Hanya menghitung yang dipakai slide (19 kunci). Rantai sumber: lihat data/00_registry/lineage.csv."""
    from smdr import baseline
    from smdr import covenant_band as cb, freight
    from smdr.transition import bridge as br, cashflow as cf, covenants as cvn, cycle as cy, robustness as rb, transmission as tr
    tv, cv = tr.build_view(), cf.build_view()
    sv = cy.build_view()
    bv = br.build_view(cv, sv)
    a_ = tr.assumptions()
    D = {"inp_ebitda": float(cv.inp["ebitda"]), "opening_cash": float(cv.inp["opening_cash"]), "deposits": float(cv.inp["deposits"]),
         "den": sv.den, "hist": sv.hist}
    D["narr"], D["results"] = bv.narr, bv.results
    D["macro_scen"] = tv.scenarios
    D["reported"], D["realized"], D["backtest"] = bv.reported, bv.realized, bv.backtest
    D["paths"] = {k: v[["closing", "liquidity", "reserve"]] for k, v in cv.paths.items()}
    D["tornado"] = cv.tornado
    D["inp_other"] = {"opex_month": float(cv.inp["opex_month"])}
    # posisi sekarang dan riwayat Net Debt to EBITDA (definisi covenant: bank + sukuk + sewa, tanpa dikurangi kas)
    b = cvn.base_position(baseline.load_wide())
    debt = b["bank"] + b["sukuk"] + b["lease"]
    D["nd"] = {"debt": debt, "ebitda": float(cv.inp["ebitda"]), "now": debt / float(cv.inp["ebitda"]), "min_ebitda": debt / cvn.TH_ND, "headroom": float(cv.inp["ebitda"]) - debt / cvn.TH_ND,
               "rate": tr.breakeven_rate(cv.inp, debt / cvn.TH_ND / 1.10, 0.0, a_), **{k: b[k] for k in ("bank", "sukuk", "lease", "equity")}}
    w_ = baseline.load_wide()
    D["nd_hist"] = {p: cvn.reported_nd_ebitda(w_, p, cb.ebitda_operating(w_, p) / 1e6) for p in ("FY2022", "FY2023", "FY2024", "FY2025")}
    D["nd_hist"]["TTM"] = D["nd"]["now"]
    # posisi siklus pasar: Drewry WCI komposit mingguan
    wci = pd.read_csv(datapaths.table("wci_composite_weekly.csv"), parse_dates=["date"]).set_index("date")["wci"]
    wci = wci[~wci.index.duplicated()]
    pos = freight.position(wci)
    a4, a52 = wci.rolling(4).mean(), wci.rolling(52).mean()
    d = pd.DataFrame({"dev": a4 / a52 - 1, "fwd": wci.shift(-52) / wci - 1}).dropna()
    hi = d[d.dev >= 0.5]
    pos.update({"tanggal": str(wci.index[-1].date()), "n_hi": int(len(hi)), "share_fall12_hi": float((hi.fwd <= -0.12).mean()), "share_fall12_all": float((d.fwd <= -0.12).mean()),
                "median_fwd_hi": float(hi.fwd.median())})
    D["wci"] = pos
    D["wci_eps"] = rb.wci_episodes(wci)
    # hasil konsisten (cover basis DSCR, pembiayaan bank yang sama untuk rasio dan kas), uji keparahan, uji balik, uji historis, kuartalan, mitigasi
    res, P, th = rb.consistent_results()
    D["v7"] = {"res": res, "paths": {k: v[["closing", "liquidity", "ebitda"]] for k, v in P.items()}, "th": th,
               "dscr": rb.dscr_denominator(baseline.load_wide()), "sev": rb.severity_check(), "bt": rb.backtest_errors(),
               "cover_be": {fy: float(tr.breakeven_rate(cv.inp, rb.dscr_denominator(baseline.load_wide())["den"] + cvn.SUKUK_DUE_12M[fy], 0.0, a_)) for fy in ("FY2027", "FY2028")},
               "hist": rb.historical_test(debt), "q": rb.quarterly_tests(P), "recover_fy2025": rb.weak_recovery(P, res, float(rb.historical_test(debt).loc["FY2025", "ebitda"])), "tornado": rb.cash_tornado(), "geo": _geo(),
               "mit": pd.concat([rb.mitigation_test(res, P, pd_, ds_) for pd_, ds_ in ((54.0, False), (107.0, False), (107.0, True))], ignore_index=True),
               "rev_growth_9m": float(baseline.load_wide().loc[("IS", "revenue"), "9M26"] / baseline.load_wide().loc[("IS", "revenue"), "9M25"] - 1)}
    return D


def _geo():
    """Pendapatan 9M26 menurut pasar geografis (catatan segmen LK 9M26), USD juta."""
    from smdr import operating
    o = operating.load()
    g = o[(o.metric_key == "fs_revenue_geography") & (o.period == "9M26")].set_index("scope")["value"] / 1e6
    return g


def load(refresh=False):
    if refresh or not os.path.exists(CACHE):
        D = build()
        with open(CACHE, "wb") as f:
            pickle.dump(D, f)
    with open(CACHE, "rb") as f:
        return pickle.load(f)


def _record_dependencies():
    """Catat tabel data yang benar-benar dibuka saat deck dibangun -> data/00_registry/deck_dependencies.csv (sumber used_by_deck di lineage)."""
    seen = set()

    def hook(ev, args):
        if ev == "open" and isinstance(args[0], str) and args[0].startswith(datapaths.DATA):
            seen.add(os.path.basename(args[0]))
    sys.addaudithook(hook)
    return seen


if __name__ == "__main__":
    deps = _record_dependencies()
    D = load(refresh=True)
    names = sorted(n for n in deps if n in datapaths.LAYOUT)
    with open(datapaths.table("deck_dependencies.csv"), "w", encoding="utf-8", newline="") as f:
        f.write("dataset\n" + "\n".join(names) + "\n")

    print({k: type(v).__name__ for k, v in D.items()})
