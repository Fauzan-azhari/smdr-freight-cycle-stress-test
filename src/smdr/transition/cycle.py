"""Replay siklus: menghadapkan kewajiban saat ini pada tingkat EBITDA yang pernah dialami SMDR.

Dasar pikir (Stopford, Maritime Economics, edisi ketiga, hlm. 101-102, 131-133, 739): siklus pelayaran bersifat episodik dan tidak
beraturan, sehingga lama dan kedalaman penurunan tidak dapat diasumsikan dari satu angka. Risiko pelayaran adalah waktu penerimaan kas
terhadap titik impas. Karena itu uji dilakukan dengan (i) membandingkan EBITDA sejarah dengan titik impas kewajiban saat ini,
(ii) memberlakukan tingkat EBITDA sejarah selama 12, 24, atau 36 bulan, dan (iii) menambah sisi buruk 20% di bawah palung yang pernah
terjadi. Tidak ada probabilitas yang dilekatkan. Hasil adalah pro forma atas kewajiban pada 30 September 2026, bukan proyeksi.
"""
import datetime as dt
from dataclasses import dataclass

import pandas as pd

from .. import baseline, covenant_band as cb
from . import cashflow as cf
from . import macro
from . import transmission as tr

HIST = ["FY2021", "FY2022", "FY2023", "FY2024", "FY2025"]
TEST_YEARS = [2027, 2028, 2029, 2030]
DURATIONS = [12, 24, 36]
BEYOND = 0.20            # sisi buruk tambahan di bawah palung (Stopford, hlm. 739: tambahkan 20-25% pada kasus ekstrem)


def history():
    """EBITDA dan pendapatan tahunan (USD juta, basis laba operasi + penyusutan biaya jasa) serta TTM September 2026."""
    w = baseline.load_wide()
    m = baseline.metrics(w)
    rows = [(p, w.loc[("IS", "revenue"), p] / 1e6, cb.ebitda_proxy(w, p) / 1e6) for p in HIST]
    rows.append(("TTM Sep-2026", m["revenue_ttm"][0] / 1e6, m["ebitda_ttm_legacy"][0] / 1e6))
    h = pd.DataFrame(rows, columns=["periode", "pendapatan", "ebitda"]).set_index("periode")
    h["margin"] = h["ebitda"] / h["pendapatan"] * 100
    return h


def test_denominators(inp, paths=None):
    """Penyebut uji covenant pro forma per tahun buku: bagian lancar bank, sewa, bunga TTM, dan pokok sukuk yang jatuh tempo dalam 12 bulan
    setelah tanggal uji (kurs akhir tahun skenario dasar). Titik impas EBITDA = 1,10 x penyebut."""
    paths = macro.build_paths() if paths is None else paths
    fx = paths[(paths.scenario_id == "MS-BASE") & (paths.driver == "usdidr")].set_index("month")["value"]
    ev = cf.financing.debt_service(cf.financing.load_facilities(), start=dt.date(2000, 1, 1))
    rows = []
    for y in TEST_YEARS:
        cur = cf.financing.current_portion(ev, dt.date(y, 12, 31)) / fx[f"{y}-12"] / 1e6
        den = inp["bank_current"] + inp["lease_current"] + inp["interest_ttm"] + cur
        rows.append({"tahun": f"FY{y}", "bank": inp["bank_current"], "sewa": inp["lease_current"], "bunga": inp["interest_ttm"], "sukuk": cur,
                     "penyebut": den, "titik_impas": tr.THRESHOLD * den})
    return pd.DataFrame(rows).set_index("tahun")


def levels(hist, ttm_legacy=None):
    """Tingkat EBITDA replay (basis legacy, USD juta): kembali ke FY2023, FY2025, palung FY2024, dan 20% di bawah palung."""
    h = hist["ebitda"]
    return {"FY2023": float(h["FY2023"]), "FY2025": float(h["FY2025"]), "Palung FY2024": float(h["FY2024"]),
            "20% di bawah palung": float(h["FY2024"] * (1 - BEYOND))}


def _calendar_cover(df, den):
    e = df["ebitda"].groupby(df.index.str[:4]).sum()
    return {f"FY{y}": float(e[str(y)] / den.loc[f"FY{y}", "penyebut"]) for y in TEST_YEARS}


def replay(inp, paths, a_op, a, shift, months, case="central"):
    """Replay satu tingkat EBITDA (pergeseran `shift` USD juta per tahun selama `months` bulan), parameter lain tengah, tanpa efek makro."""
    return cf.run("MS-BASE", case, inp, paths, a_op, a, stress=cf.Stress(shift=shift, months=months), macro=False)


def critical_level(inp, paths, a_op, a, months, threshold, metric, ttm_legacy):
    """Tingkat EBITDA (basis legacy) yang membuat saldo minimum `metric` ('cash' atau 'liquidity') tepat sama dengan batas kas."""
    col = "closing" if metric == "cash" else "liquidity"
    gap = lambda s: float((replay(inp, paths, a_op, a, s, months)[col] - threshold).min())
    s = cf.solve(gap, -260.0, 60.0)
    return None if s is None else ttm_legacy + s


def build_view():
    inp, a, a_op, paths = cf._init(), cf.assumptions(), tr.assumptions(), macro.build_paths()
    th = cf.min_cash(inp, a, "central")
    hist = history()
    ttm_legacy = float(hist.loc["TTM Sep-2026", "ebitda"])
    den = test_denominators(inp, paths)
    lv = levels(hist)
    ref = cf.run("MS-BASE", "central", inp, paths, a_op, a, macro=False)
    rows = []
    for label, L in lv.items():
        for m in DURATIONS:
            for case in ("central", "adverse"):
                df = replay(inp, paths, a_op, a, L - ttm_legacy, m, case)
                s = cf.summarize(df, th)
                cov = _calendar_cover(df, den)
                worst = min(cov, key=cov.get)
                rows.append({"level": label, "ebitda": L, "months": m, "case": case, "min_cash": s["min_cash"], "min_liquidity": s["min_liquidity"],
                             "end_cash": s["end_cash"], "first_below": s["first_below"], "first_below_liq": s["first_below_liq"],
                             **{f"cover_{k}": v for k, v in cov.items()}, "cover_min": cov[worst], "cover_min_year": worst})
    grid = pd.DataFrame(rows)
    crit = pd.DataFrame([{"months": m, "cash": critical_level(inp, paths, a_op, a, m, th, "cash", ttm_legacy),
                          "liquidity": critical_level(inp, paths, a_op, a, m, th, "liquidity", ttm_legacy)} for m in DURATIONS]).set_index("months")
    den["ruang_ebitda"] = inp["ebitda"] - den["titik_impas"]
    den["titik_impas_tarif"] = [tr.breakeven_rate(inp, d, 0.0, a_op) for d in den["penyebut"]]
    basis = {"fy2025_hist": float(hist.loc["FY2025", "ebitda"]), "fy2025_penuh": float(cb.ebitda_pdf_fy2025(baseline.load_wide()) / 1e6),
             "ttm_hist": ttm_legacy, "ttm_penuh": inp["ebitda"]}
    below = {f: int((hist.loc[HIST, "ebitda"] < den.loc[f, "titik_impas"]).sum()) for f in den.index}
    return CycleView(inp, th, hist, den, lv, grid, crit, ref, basis, below)


@dataclass
class CycleView:
    inp: dict
    threshold: float
    hist: pd.DataFrame
    den: pd.DataFrame
    levels: dict
    grid: pd.DataFrame
    critical: pd.DataFrame     # tingkat EBITDA kritis untuk kas dan likuiditas menurut lama penurunan
    ref: pd.DataFrame          # jalur acuan: EBITDA TTM ditahan, tanpa guncangan
    basis: dict
    below: dict                # jumlah tahun buku sejarah (dari lima) dengan EBITDA di bawah titik impas tiap uji


# --- tabel untuk notebook ----------------------------------------------------------------------------------------

def history_table(v):
    h = v.hist.copy()
    h.columns = ["Pendapatan", "EBITDA", "Margin EBITDA (%)"]
    return h


def breakeven_table(v):
    d = v.den.copy()
    for f in d.index:
        d.loc[f, "Tahun buku sejarah di bawah titik impas (dari 5)"] = v.below[f]
    d = d.rename(columns={"bank": "Bagian lancar bank", "sewa": "Bagian lancar sewa", "bunga": "Bunga TTM", "sukuk": "Pokok sukuk dalam 12 bulan",
                          "penyebut": "Penyebut", "titik_impas": "EBITDA titik impas (1,10x)", "ruang_ebitda": "Ruang EBITDA TTM",
                          "titik_impas_tarif": "Titik impas tarif (%)"})
    d["Titik impas tarif (%)"] = d["Titik impas tarif (%)"] * 100
    return d


def critical_table(v):
    c = v.critical.copy()
    c.index = [f"Penurunan {m} bulan" for m in c.index]
    c.columns = ["EBITDA kritis untuk kas", "EBITDA kritis untuk kas + deposito"]
    return c


def grid_table(v, case="central"):
    g = v.grid[v.grid.case == case].copy()
    g["Lama"] = g["months"].map(lambda m: f"{m} bulan")
    g["Cover minimum"] = g["cover_min"]
    g["Tahun"] = g["cover_min_year"]
    t = g.set_index(["level", "Lama"])[["ebitda", "Cover minimum", "Tahun", "min_cash", "min_liquidity", "end_cash"]]
    t.index.names = [None, None]
    return t.rename(columns={"ebitda": "EBITDA", "min_cash": "Kas minimum", "min_liquidity": "Kas + deposito minimum", "end_cash": "Kas akhir 2031"})


def macro_cover_table(cv, v, scenarios=("Dasar", "Energi bertahan", "Gabungan")):
    """Cover covenant per tahun uji (FY2027-FY2029) pada skenario makro, memakai EBITDA tahun kalender dari jalur bulanan dan penyebut pro forma."""
    rows = {}
    for sc in scenarios:
        for case, lb in (("central", "tengah"), ("adverse", "merugikan")):
            df = cv.paths[(sc, case)]
            e = df["ebitda"].groupby(df.index.str[:4]).sum()
            rows[(sc, lb)] = {f"FY{y}": float(e[str(y)] / v.den.loc[f"FY{y}", "penyebut"]) for y in (2027, 2028, 2029)}
    return pd.DataFrame(rows).T
