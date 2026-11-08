"""Lapisan marts: hasil model final sebagai teks (CSV UTF-8), konsumsi bersama deck, workbook Excel, dan naskah.

Semua angka final yang tampil di deck berasal dari fungsi yang sama dengan berkas ini (smdr.transition.robustness). Berkas di sini adalah
kontrak antara model dan penyajian: workbook Excel dan naskah membaca atau dicocokkan terhadap marts ini, bukan menghitung ulang diam-diam.

Keluar : data/04_marts/results/*.csv (deterministik, tanpa cap waktu)
Jalankan dari root repo:  PYTHONPATH=src .venv/bin/python -m smdr.marts
"""
import pandas as pd

from . import baseline, datapaths
from .transition import covenants as cvn, robustness as rb


def build():
    res, P, th = rb.consistent_results()
    w = baseline.load_wide()
    b = cvn.base_position(w)
    debt = b["bank"] + b["sukuk"] + b["lease"]
    out = {}
    out["scenario_results.csv"] = res.round(6)
    paths = pd.concat([df.assign(skenario=k[0], case=k[1]).reset_index() for k, df in P.items()], ignore_index=True)
    out["cash_paths_monthly.csv"] = paths[["skenario", "case", "month"] + [c for c in paths.columns if c not in ("skenario", "case", "month")]].round(6)
    out["covenant_quarterly.csv"] = rb.quarterly_tests(P).round(6)
    mit = pd.concat([rb.mitigation_test(res, P, pd_, ds_) for pd_, ds_ in ((54.0, False), (107.0, False), (107.0, True))], ignore_index=True)
    out["mitigation_tests.csv"] = mit.round(6)
    out["backtest.csv"] = rb.backtest_errors().reset_index().round(6)
    out["historical_test.csv"] = rb.historical_test(debt).reset_index().round(6)
    out["cash_tornado.csv"] = rb.cash_tornado().round(6)
    sev = rb.severity_check()
    out["severity.csv"] = pd.DataFrame([(k, str(v)) for k, v in sev.items()], columns=["metric", "value"])
    out["_cash_threshold"] = th
    return out


def write():
    import os
    out = build()
    os.makedirs(datapaths.RESULTS, exist_ok=True)
    for name, df in out.items():
        if name.startswith("_"):
            continue
        df.to_csv(datapaths.table(name), index=False, lineterminator="\n")
    return {k: (len(v) if hasattr(v, "__len__") else 0) for k, v in out.items() if not k.startswith("_")}


if __name__ == "__main__":
    for k, n in write().items():
        print("%-26s %6d baris" % (k, n))
