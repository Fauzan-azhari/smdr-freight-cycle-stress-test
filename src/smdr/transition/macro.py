"""Asumsi makro dan jalur skenario.

Parameter skenario tersimpan di data/tidy/transition (macro_scenario_definitions.csv); kode hanya membangun jalur
bulanan dari parameter itu dan dari riwayat data. Setiap jalur membawa status: anchored (mengikuti proyeksi resmi
berversi), precedent (mengikuti episode historis), shock (besaran dari persentil historis), atau hold (diteruskan
tanpa proyeksi sumber).
"""
import os

import numpy as np
import pandas as pd

from .. import datapaths
from .. import baseline

START = pd.Period("2026-10", "M")
END = pd.Period("2031-12", "M")
DRIVERS = ["brent", "usdidr", "bi_rate", "fed_funds"]
PRECEDENT_MONTHS = 12  # penurunan mengikuti preseden 2022 selama 12 bulan, lalu ditahan
UNITS = {"brent": "USD/barel", "usdidr": "IDR/USD", "bi_rate": "% p.a.", "fed_funds": "% p.a."}


def read(name):
    return pd.read_csv(datapaths.table(name))


def history():
    """Riwayat bulanan penuh (tanpa bulan parsial untuk statistik) dari data tidy."""
    w = pd.read_csv(datapaths.table("macro_monthly_wide.csv")).set_index("month")
    full = w[~w["partial_any"]]
    return w, full


def precedent_ratios(brent, peak_window=("2022-01", "2023-12"), horizon=24):
    """Rasio Brent terhadap puncak pada +k bulan setelah puncak episode 2022 (k = 0..horizon), sebagai minimum kumulatif."""
    s = brent[peak_window[0]:peak_window[1]]
    pk = s.idxmax()
    i0 = list(brent.index).index(pk)
    r = pd.Series([brent.iloc[i0 + k] / brent.iloc[i0] for k in range(horizon + 1)])
    return r.cummin(), pk  # minimum kumulatif: jalur normalisasi tidak naik kembali


def six_month_fx_changes(fx_full):
    return (fx_full / fx_full.shift(6) - 1).dropna() * 100


def _months():
    return pd.period_range(START, END, freq="M")


def _decay(start, ratios, hold, n):
    out = []
    for i in range(n):
        k = max(0, i - hold)
        out.append(start * ratios.iloc[min(k, len(ratios) - 1)])
    return np.array(out)


def _shock_profile(ramp, hold, retrace_fraction, retrace_months, n):
    """Profil 0..1: naik bertahap, ditahan, lalu kembali sebagian (retrace_fraction) dalam retrace_months."""
    f = np.zeros(n)
    for i in range(n):
        if i <= ramp:
            f[i] = i / ramp if ramp else 1.0
        elif i <= ramp + hold:
            f[i] = 1.0
        else:
            j = min(i - ramp - hold, retrace_months)
            f[i] = 1.0 - retrace_fraction * (j / retrace_months if retrace_months else 1.0)
    return f


def _anchor_targets(start, targets, n):
    """Interpolasi linier antar titik target (bulan:nilai) lalu ditahan setelah titik terakhir."""
    pts = [(START, start)] + [(pd.Period(k, "M"), float(v)) for k, v in (t.split(":") for t in targets.split(";"))]
    idx = np.array([(p - START).n for p, _ in pts]); val = np.array([v for _, v in pts])
    return np.interp(np.arange(n), idx, val)


def build_paths():
    """Jalur bulanan per skenario dan driver. Guncangan kurs dan bunga diukur terhadap jalur dasar (overlay)."""
    defs, anchors = read("macro_scenario_definitions.csv"), read("macro_anchors.csv").set_index("driver")
    _, full = history()
    ratios, _ = precedent_ratios(full["brent_avg"].dropna(), horizon=PRECEDENT_MONTHS)
    months = _months(); n = len(months)
    start = lambda dr: float(anchors.loc[dr, "value"])
    base = {}
    for r in defs[(defs.scenario_id == "MS-BASE")].itertuples():
        base[r.driver] = _anchor_targets(start(r.driver), r.target, n) if r.path_type == "anchor_targets" else _decay(start(r.driver), ratios, int(r.hold_months), n)
    rows = []
    for r in defs.itertuples():
        if r.path_type == "follow":
            v, status = base[r.driver], "follows_base"
        elif r.path_type == "anchor_targets":
            v, status = _anchor_targets(start(r.driver), r.target, n), "anchored"
        elif r.path_type == "hold_then_decay":
            v, status = _decay(start(r.driver), ratios, int(r.hold_months), n), "precedent"
        elif r.path_type == "shock_retrace":
            f = _shock_profile(int(r.ramp_months), int(r.hold_months), float(r.retrace_fraction), int(r.retrace_months), n)
            delta = base[r.driver] * float(r.magnitude) / 100.0 * f if r.magnitude_unit == "pct" else float(r.magnitude) * f
            v, status = base[r.driver] + delta, "shock"
        else:
            raise ValueError("path_type tidak dikenal: %s" % r.path_type)
        for m_, x in zip(months, v):
            rows.append((r.scenario_id, "CENTRAL_PROVISIONAL", r.driver, str(m_), x, UNITS[r.driver], status, r.assumption_id))
    p = pd.DataFrame(rows, columns=["scenario_id", "assumption_set_id", "driver", "month", "value", "unit", "path_status", "assumption_id"])
    return p.sort_values(["scenario_id", "driver", "month"]).reset_index(drop=True)


def fx_brent_beta():
    """Hubungan perubahan log bulanan Brent terhadap kurs (bulan penuh), galat baku HAC. Dipakai untuk menilai koherensi skenario gabungan."""
    import statsmodels.api as sm
    _, full = history()
    d = pd.DataFrame({"fx": np.log(full["usdidr_close"]).diff() * 100, "brent": np.log(full["brent_avg"]).diff() * 100}).dropna()
    out = {}
    for lag in (0, 1):
        x = d["brent"].shift(lag).dropna()
        m = sm.OLS(d["fx"].loc[x.index], sm.add_constant(x)).fit(cov_type="HAC", cov_kwds={"maxlags": 2})
        out[lag] = {"beta": float(m.params.iloc[1]), "t": float(m.tvalues.iloc[1]), "r2": float(m.rsquared), "n": int(len(x))}
    return out


def realisation_vs_ifrs9():
    """Realisasi 3Q26 (penutupan September) terhadap skenario IFRS 9 vintage Mei 2026."""
    v = read("macro_ifrs9_vintage.csv")
    w, _ = history()
    q = v[v.quarter == "3Q26"].pivot(index="variable", columns="scenario", values="value")
    q["realisasi"] = np.nan
    q.loc["idr_usd", "realisasi"] = float(w.loc["2026-09", "usdidr_close"])
    q.loc["bi_rate", "realisasi"] = 5.75
    return q.loc[["idr_usd", "bi_rate"]]


def vintages():
    return read("macro_forecast_vintages.csv")


def summary():
    """Angka jangkar dari data riwayat, dipakai narasi notebook."""
    w, full = history()
    b_all, b_full = w["brent_avg"].dropna(), full["brent_avg"].dropna()
    r, pk = precedent_ratios(b_full, horizon=12)
    plateau = b_full["2022-07":"2025-12"]
    fx_full = full["usdidr_close"].dropna()
    ch12 = (fx_full / fx_full.shift(12) - 1).dropna() * 100
    last12 = (w["usdidr_close"]["2026-10"] / w["usdidr_close"]["2025-10"] - 1) * 100
    fx6 = six_month_fx_changes(fx_full)
    return {
        "brent_oct": float(b_all["2026-10"]), "brent_max_full": float(b_full.max()), "brent_max_month": b_full.idxmax(), "n_full": int(len(b_full)),
        "months_ge_100": int((b_all >= 100).sum()), "peak_month": pk, "drop3": float((1 - r[3]) * 100), "drop6": float((1 - r[6]) * 100), "drop12": float((1 - r[12]) * 100),
        "plateau": (float(plateau.quantile(.25)), float(plateau.median()), float(plateau.quantile(.75))),
        "fx_oct": float(w["usdidr_close"]["2026-10"]), "fx_nov": float(w["usdidr_close"].dropna().iloc[-1]), "fx_max_before": float(fx_full.max()),
        "fx_12m": float(last12), "fx_12m_pctile": float((ch12 < last12).mean() * 100), "fx6_p75": float(fx6.quantile(.75)), "fx6_p90": float(fx6.quantile(.90)), "fx6_n": int(len(fx6)),
    }


# --- tampilan untuk notebook ----------------------------------------------------------------------------

from dataclasses import dataclass


@dataclass
class MacroView:
    summary: dict
    anchors: pd.DataFrame
    official: pd.DataFrame
    notes: dict
    ifrs9: pd.DataFrame
    beta: pd.DataFrame
    beta_raw: dict
    scenarios: pd.DataFrame
    paths: pd.DataFrame
    brent_hist: pd.Series
    fx_hist: pd.Series
    plateau: tuple
    oce_fx_6m: tuple


def build_view():
    w, full = history()
    S, paths, beta = summary(), build_paths(), fx_brent_beta()
    vint, defs = vintages(), read("macro_scenario_definitions.csv")
    v = vint.set_index(["vintage_id", "variable", "horizon"])["value"]
    a = read("macro_anchors.csv")
    anchors = pd.DataFrame({"Variabel": ["Brent (rata-rata Okt 2026, parsial)", "USD/IDR (penutupan Okt 2026)", "BI Rate", "Fed Funds (batas atas)"],
                            "Nilai": a["value"].values, "Satuan": a["unit"].values,
                            "Catatan": ["OCE membaca sekitar USD118 pada akhir Oktober; berbeda ukuran dan tanggal", "November (parsial): Rp18.148", "Ditahan pada RDG 21 Okt 2026", "Per 2 Nov 2026"]}).set_index("Variabel")
    rows = ["gdp_growth", "inflation", "idr_usd_eop", "bi_rate", "fed_funds", "idr_10y_yield"]
    t = vint[(vint.evidence_status == "forecast") & vint.variable.isin(rows) & vint.vintage_id.isin(["OCE-2026-10", "OCE-2026-11"])].copy()
    t["kolom"] = t.vintage_id.map({"OCE-2026-10": "OCE Okt 2026", "OCE-2026-11": "OCE Nov 2026"}) + " " + t.horizon
    official = t.pivot(index="variable", columns="kolom", values="value").reindex(rows)
    official.index = ["PDB riil (% yoy)", "Inflasi (% yoy)", "USD/IDR akhir periode", "BI Rate (%)", "Fed Funds (%)", "Imbal hasil SBN 10 tahun (%)"]
    official = official[["OCE Okt 2026 2026F", "OCE Nov 2026 2026F", "OCE Okt 2026 2027F"]]
    wb = vint[vint.vintage_id == "WB-2026-10"].set_index("horizon")["value"]
    fx = vint[vint.vintage_id == "OCE-2026-10-FX"].set_index("variable")["value"]
    notes = {"wb_2026": wb["2026F"], "wb_2028": wb["2028F"], "fx3": (fx["idr_usd_3m_low"], fx["idr_usd_3m_high"]), "fx6": (fx["idr_usd_6m_low"], fx["idr_usd_6m_high"]),
             "fx_okt": v[("OCE-2026-10", "idr_usd_eop", "2026F")], "fx_nov": v[("OCE-2026-11", "idr_usd_eop", "2026F")]}
    ifr = realisation_vs_ifrs9().rename(columns={"baseline": "Baseline", "downside": "Downside", "upside": "Upside", "realisasi": "Realisasi"})[["Baseline", "Downside", "Upside", "Realisasi"]]
    ifr.index = ["USD/IDR 3Q26 (Rp)", "BI Rate 3Q26 (%)"]
    bt = pd.DataFrame(beta).T.rename(columns={"beta": "Koefisien (% kurs per 1% Brent)", "t": "Statistik t (HAC)", "r2": "R²", "n": "Observasi"})
    bt.index = ["Bulan yang sama", "Brent tertinggal satu bulan"]
    d = defs.set_index(["scenario_id", "driver"]); mag = lambda sid, dr: float(d.loc[(sid, dr), "magnitude"]); idn = lambda x, k=1: f"{x:,.{k}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    narasi = pd.DataFrame([
        ("Dasar (sementara)", "Titik acuan: kurs dan bunga mengikuti proyeksi resmi; Brent bertahan tiga bulan lalu normal mengikuti preseden 2022", "MS-BASE"),
        ("Energi bertahan", "Brent tetap pada level Oktober selama sembilan bulan sebelum normalisasi; kurs dan bunga mengikuti jalur dasar", "MS-ENERGY"),
        ("Normalisasi cepat", "Rute dan energi normal sejak Oktober; relevan sebagai tekanan tarif ketika kapasitas efektif pulih", "MS-NORMAL"),
        ("Tekanan kurs", f"Rupiah melemah {idn(mag('MS-FX', 'usdidr'))}% terhadap jalur dasar dalam enam bulan (persentil 90 historis), ditahan, lalu kembali separuhnya", "MS-FX"),
        ("Tekanan bunga", f"BI Rate naik {idn(mag('MS-RATE', 'bi_rate') * 100, 0)} bps dan Fed Funds {idn(mag('MS-RATE', 'fed_funds') * 100, 0)} bps terhadap jalur dasar, ditahan 12 bulan", "MS-RATE"),
        ("Gabungan", f"Energi bertahan, kurs {idn(mag('MS-COMBINED', 'usdidr'))}%, BI Rate +{idn(mag('MS-COMBINED', 'bi_rate') * 100, 0)} bps, Fed Funds +{idn(mag('MS-COMBINED', 'fed_funds') * 100, 0)} bps", "MS-COMBINED")],
        columns=["Skenario", "Rancangan", "id"])
    pv = paths.pivot_table(index="scenario_id", columns=["driver", "month"], values="value")
    narasi["Brent Apr-2027"] = narasi.id.map(pv[("brent", "2027-04")]); narasi["Brent Okt-2027"] = narasi.id.map(pv[("brent", "2027-10")])
    narasi["Kurs puncak"] = narasi.id.map(paths[paths.driver == "usdidr"].groupby("scenario_id").value.max())
    narasi["BI Rate puncak"] = narasi.id.map(paths[paths.driver == "bi_rate"].groupby("scenario_id").value.max())
    return MacroView(S, anchors, official, notes, ifr, bt, beta, narasi.drop(columns="id").set_index("Skenario"), paths,
                     w["brent_avg"].dropna(), w["usdidr_close"].dropna(), (S["plateau"][0], S["plateau"][2]), (float(fx["idr_usd_6m_low"]), float(fx["idr_usd_6m_high"])))
