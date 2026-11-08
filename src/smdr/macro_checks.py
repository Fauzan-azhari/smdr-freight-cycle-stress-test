"""Validasi data makro (kurs, Brent) dan pencocokan dengan ekstraksi v4.

Status: PASS (lolos), FAIL (gagal, menghentikan pipeline), INFO (temuan yang dicatat tanpa
menghakimi, mis. lonjakan harga yang memang terjadi), KNOWN (gagal tetapi sudah dijelaskan
di data/02_curated/quality/macro_known_exceptions.csv).

Jalankan dari root repo:  PYTHONPATH=src .venv/bin/python -m smdr.macro_checks
"""
import os
import sys

import numpy as np
import pandas as pd

from . import datapaths
from . import macro_ingest as mi

RET_FLAG = 0.08  # |perubahan harian Brent| di atas 8% dicatat sebagai INFO


def check(rows, check_id, description, n_tested, bad, detail=""):
    n_bad = len(bad) if hasattr(bad, "__len__") else int(bad)
    rows.append({"check_id": check_id, "description": description, "n_tested": int(n_tested),
                 "n_fail": n_bad, "status": "PASS" if n_bad == 0 else "FAIL",
                 "detail": detail if n_bad else ""})


def info(rows, check_id, description, n_tested, n_flag, detail):
    rows.append({"check_id": check_id, "description": description, "n_tested": int(n_tested),
                 "n_fail": int(n_flag), "status": "INFO", "detail": detail})


def run():
    rows = []
    fx, brent = mi.read_fx(), mi.read_brent()

    # ---- kurs
    months = pd.period_range(fx["date"].min(), fx["date"].max(), freq="M")
    missing = sorted(set(months) - set(fx["date"].dt.to_period("M")))
    check(rows, "FX:no_gap", "deret bulan kurs tanpa celah", len(months), missing, ",".join(map(str, missing)))
    check(rows, "FX:unique_month", "satu baris per bulan", len(fx), fx["date"].dt.to_period("M").duplicated().loc[lambda s: s])
    ohlc_bad = fx[(fx["high"] < fx[["open", "close"]].max(axis=1)) | (fx["low"] > fx[["open", "close"]].min(axis=1))]
    check(rows, "FX:ohlc", "tertinggi >= max(buka,tutup) dan terendah <= min", len(fx), ohlc_bad,
          ",".join(ohlc_bad["date"].dt.strftime("%Y-%m")))
    calc = fx["close"].pct_change() * 100
    chg_bad = fx[(calc - fx["change_pct"]).abs() > 0.02].iloc[0:]
    chg_bad = chg_bad[calc.loc[chg_bad.index].notna()]
    check(rows, "FX:change_pct", "perubahan% sumber = hitungan dari penutupan berurutan (toleransi 0,02 pp)",
          int(calc.notna().sum()), chg_bad, ",".join(chg_bad["date"].dt.strftime("%Y-%m")))

    # ---- Brent
    check(rows, "BRENT:sorted_unique", "tanggal berurutan tanpa duplikat", len(brent),
          brent[brent["date"].duplicated() | (brent["date"].diff() < pd.Timedelta(0))])
    check(rows, "BRENT:positive", "harga > 0", int(brent["value"].notna().sum()), brent[brent["value"] <= 0])
    n_nd = int(brent["value"].isna().sum())
    info(rows, "BRENT:nd_days", "hari tanpa nilai ('.' pada sumber, umumnya libur)", len(brent), n_nd, "%d hari" % n_nd)
    ret = np.log(brent.dropna(subset=["value"]).set_index("date")["value"]).diff().dropna()
    big = ret[ret.abs() > RET_FLAG]
    info(rows, "BRENT:large_moves", "perubahan harian > 8%% (dicatat, bukan galat)", len(ret), len(big),
         "; ".join("%s %+.1f%%" % (d.strftime("%Y-%m-%d"), 100 * (np.exp(v) - 1)) for d, v in big.items()))

    # ---- keluaran tidy
    monthly = pd.read_csv(datapaths.table("macro_monthly.csv"))
    n_obs = monthly[monthly["series"] == "brent_avg"].set_index("month")["n_obs"]
    thin = n_obs[(n_obs < 15) & ~monthly[monthly["series"] == "brent_avg"].set_index("month")["partial"]]
    check(rows, "BRENT:coverage", "bulan lengkap punya >= 15 observasi harian", len(n_obs), thin,
          ",".join(thin.index))

    return rows


def load_exceptions():
    path = datapaths.table("macro_known_exceptions.csv")
    if not os.path.exists(path):
        return {}
    return {r.check_id: r.explanation for r in pd.read_csv(path).itertuples()}


def main():
    rows = run()
    exceptions = load_exceptions()
    for r in rows:
        if r["status"] == "FAIL" and r["check_id"] in exceptions:
            r["status"] = "KNOWN"
            r["detail"] = (r["detail"] + " | " if r["detail"] else "") + exceptions[r["check_id"]]
    out = pd.DataFrame(rows)
    out.to_csv(datapaths.table("macro_checks.csv"), index=False)
    n = out["status"].value_counts().to_dict()
    print("%d cek: PASS %d, INFO %d, KNOWN %d, FAIL %d" % (len(out), n.get("PASS", 0), n.get("INFO", 0),
                                                         n.get("KNOWN", 0), n.get("FAIL", 0)))
    for r in rows:
        if r["status"] != "PASS":
            print("  %-5s %-22s n=%-5d bermasalah=%-4d %s" % (r["status"], r["check_id"], r["n_tested"], r["n_fail"], r["detail"][:230]))
    return 1 if n.get("FAIL", 0) else 0


if __name__ == "__main__":
    sys.exit(main())
