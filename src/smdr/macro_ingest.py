"""Ingest data makro: USD/IDR (bulanan) dan Brent (harian).

Sumber : data/01_raw/fx/usdidr_monthly_provider.csv dan data/01_raw/fred/DCOILBRENTEU.csv (disalin apa adanya)
Keluar : data/03_canonical/macro_daily.csv, macro_monthly.csv, macro_monthly_wide.csv; data/00_registry/macro_source_manifest.csv

Seri bulanan Brent diturunkan dari data harian. Kurs hanya tersedia bulanan pada sumber.
Bulan terakhir tiap seri ditandai parsial bila belum lengkap.

Jalankan dari root repo:  PYTHONPATH=src .venv/bin/python -m smdr.macro_ingest
"""
import datetime as dt
import hashlib
import os

from . import datapaths

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FX_FILE = datapaths.table("usdidr_monthly_provider.csv")      # 01_raw/fx
BRENT_FILE = datapaths.table("DCOILBRENTEU.csv")               # 01_raw/fred

SOURCES = [
    # file, seri, frekuensi, satuan, catatan
    (FX_FILE, "usdidr_close", "bulanan", "IDR per USD",
     "Kolom Terakhir = penutupan bulan. Angka format Indonesia (titik ribuan, koma desimal). Penyedia tidak tercatat pada file."),
    (BRENT_FILE, "brent_usd_bbl", "harian", "USD per barel",
     "Seri FRED DCOILBRENTEU (Europe Brent Spot Price FOB). Hari libur ditandai '.' pada sumber."),
]


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def num_id(s):
    """Angka format Indonesia: '18.148,3' -> 18148.3 ; '0,13%' -> 0.13"""
    return pd.to_numeric(s.str.replace("%", "", regex=False).str.replace(".", "", regex=False)
                          .str.replace(",", ".", regex=False), errors="coerce")


def num_en(s):
    """Angka format Inggris: '2,652.00' -> 2652.0 ; '1.88%' -> 1.88"""
    return pd.to_numeric(s.str.replace("%", "", regex=False).str.replace(",", "", regex=False), errors="coerce")


def read_fx():
    raw = pd.read_csv(FX_FILE, encoding="utf-8-sig", dtype=str, keep_default_na=False)
    out = pd.DataFrame({
        "date": pd.to_datetime(raw["Tanggal"], format="%d/%m/%Y"),
        "close": num_id(raw["Terakhir"]), "open": num_id(raw["Pembukaan"]),
        "high": num_id(raw["Tertinggi"]), "low": num_id(raw["Terendah"]),
        "change_pct": num_id(raw["Perubahan%"]),
    })
    out["source_line"] = out.index + 2
    return out.sort_values("date").reset_index(drop=True)


def read_brent():
    raw = pd.read_csv(BRENT_FILE, dtype=str, keep_default_na=False)
    out = pd.DataFrame({
        "date": pd.to_datetime(raw["observation_date"], format="%Y-%m-%d"),
        "value": pd.to_numeric(raw["DCOILBRENTEU"], errors="coerce"),  # '.' atau kosong -> NaN
    })
    out["source_line"] = out.index + 2
    return out.sort_values("date").reset_index(drop=True)


def last_weekday(period):
    d = period.end_time.normalize()
    while d.weekday() >= 5:
        d -= pd.Timedelta(days=1)
    return d


def daily_table(brent):
    rows = []
    for series, df, col, fname in (("brent_usd_bbl", brent, "value", os.path.basename(BRENT_FILE)),):
        t = pd.DataFrame({
            "series": series, "date": df["date"].dt.strftime("%Y-%m-%d"), "value": df[col],
            "status": df[col].map(lambda v: "nd" if pd.isna(v) else "reported"),
            "source_file": fname, "source_line": df["source_line"],
        })
        rows.append(t)
    return pd.concat(rows, ignore_index=True)


def monthly_from_daily(df, col, prefix):
    d = df.dropna(subset=[col]).copy()
    d["month"] = d["date"].dt.to_period("M")
    g = d.groupby("month")
    out = pd.DataFrame({
        "avg": g[col].mean(), "eom": g[col].last(), "n_obs": g[col].count(), "last_obs_date": g["date"].max(),
    })
    last = out.index.max()
    out["partial"] = False
    out.loc[last, "partial"] = out.loc[last, "last_obs_date"] < last_weekday(last)
    return out


def monthly_table(fx, brent):
    """Tabel panjang: series, month, value, n_obs, last_obs_date, partial, source_file."""
    rows = []

    # kurs: bulan terakhir pada file adalah bulan saat file diekspor -> parsial
    export_month = pd.Period(dt.datetime.fromtimestamp(os.path.getmtime(FX_FILE)), "M")
    for _, r in fx.iterrows():
        m = r["date"].to_period("M")
        rows.append(("usdidr_close", m, r["close"], 1, "", m == export_month, os.path.basename(FX_FILE)))

    b = monthly_from_daily(brent, "value", "brent")
    for m, r in b.iterrows():
        for s, v in (("brent_avg", r["avg"]), ("brent_eom", r["eom"])):
            rows.append((s, m, v, int(r["n_obs"]), r["last_obs_date"].strftime("%Y-%m-%d"), bool(r["partial"]),
                         os.path.basename(BRENT_FILE)))

    t = pd.DataFrame(rows, columns=["series", "month", "value", "n_obs", "last_obs_date", "partial", "source_file"])
    t["month"] = t["month"].astype(str)
    return t.sort_values(["series", "month"]).reset_index(drop=True)


def manifest_table():
    out = []
    for path, series, freq, unit, note in SOURCES:
        if series == "usdidr_close":
            df = read_fx()
        else:
            df = read_brent()
        out.append({
            "file": os.path.relpath(path, ROOT), "series": series, "frequency": freq, "unit": unit,
            "rows": len(df), "first_date": df["date"].min().strftime("%Y-%m-%d"),
            "last_date": df["date"].max().strftime("%Y-%m-%d"),
            "sha256": sha256(path), "note": note,
        })
    return pd.DataFrame(out)


def wide_table(monthly):
    w = monthly.pivot(index="month", columns="series", values="value")
    keep = ["usdidr_close", "brent_avg", "brent_eom"]
    w = w[keep]
    partial = monthly.pivot(index="month", columns="series", values="partial")[keep]
    w["partial_any"] = partial.fillna(False).astype(bool).any(axis=1)
    return w.reset_index()


def main():
    fx, brent = read_fx(), read_brent()
    daily = daily_table(brent)
    monthly = monthly_table(fx, brent)
    daily.to_csv(datapaths.table("macro_daily.csv"), index=False)
    monthly.to_csv(datapaths.table("macro_monthly.csv"), index=False)
    wide_table(monthly).to_csv(datapaths.table("macro_monthly_wide.csv"), index=False)
    manifest_table().to_csv(datapaths.table("macro_source_manifest.csv"), index=False)

    print("harian: %d baris (n.d.: %d) | bulanan: %d baris" % (len(daily), (daily["status"] == "nd").sum(), len(monthly)))
    for s, g in monthly.groupby("series"):
        p = g[g["partial"]]["month"].tolist()
        print("  %-16s %s .. %s  (%d bulan)%s" % (s, g["month"].min(), g["month"].max(), len(g),
                                                  "  parsial: " + ",".join(p) if p else ""))


if __name__ == "__main__":
    main()
