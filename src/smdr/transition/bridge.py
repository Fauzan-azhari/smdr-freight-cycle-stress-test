"""Jembatan industri: dari kisah pasar pelayaran ke tarif dan volume, lalu ke covenant dan kas SMDR.

Hubungan antara variabel makro dan tarif tidak dapat dikuantifikasi dengan andal (Stopford, hlm. 723), sehingga setiap kisah adalah narasi berlabel
dengan besaran tarif, volume, dan lama yang dikalibrasi pada hasil yang pernah tercatat: perubahan tarif dan volume yang dilaporkan, serta
pendapatan angkutan terealisasi SMDR. Besaran diberlakukan pada pendapatan angkutan melalui mesin transmisi yang sama dengan notebook sebelumnya.
Hasil pro forma atas kewajiban 30 September 2026, bukan proyeksi dan bukan probabilitas.
"""
import os
from dataclasses import dataclass

import pandas as pd

from .. import baseline, operating
from . import cashflow as cf
from . import cycle as cy
from . import macro
from .. import datapaths
from . import transmission as tr

NARR = datapaths.table("industry_narratives.csv")
PSI_DOWN = "cost_flex_down"


def narratives():
    return pd.read_csv(NARR)


def reported():
    """Perubahan tarif dan volume yang dilaporkan (bukti dapat dipakai saja)."""
    o = operating.load()
    x = o[(o.domain == "price_volume_reported") & (o.acceptance_status == "usable")].copy()
    x["jenis"] = x["metric_key"].map({"freight_rate_change": "tarif", "freight_volume_growth": "volume"})
    return x[["period", "scope", "jenis", "value", "note"]].rename(columns={"period": "periode", "scope": "cakupan", "value": "perubahan", "note": "catatan"}).reset_index(drop=True)


def realized():
    """Pendapatan angkutan SMDR terealisasi, volume kontainer total, dan tarif efektif = (1 + perubahan pendapatan) / (1 + volume) - 1."""
    o = operating.load()
    f = o[(o.domain == "revenue_by_service") & (o.metric_key == "freight_income")].pivot_table(index="period", values="value")["value"] / 1e6
    vol = o[(o.metric_key == "container_volume_total")].pivot_table(index="period", values="value")["value"]
    rows = []
    for p, q in (("FY2023", "FY2022"), ("FY2024", "FY2023")):
        d, v = f[p] / f[q] - 1, vol[p] / vol[q] - 1
        rows.append({"periode": p, "pendapatan_angkutan": f[p], "perubahan_pendapatan": d, "volume": v, "tarif_efektif": (1 + d) / (1 + v) - 1, "sumber_volume": "kontainer total"})
    d, v = f["FY2025"] / f["FY2024"] - 1, 0.08       # volume total 2025 tidak diungkap; dipakai volume kargo perusahaan yang dilaporkan (+8%)
    rows.append({"periode": "FY2025", "pendapatan_angkutan": f["FY2025"], "perubahan_pendapatan": d, "volume": v, "tarif_efektif": (1 + d) / (1 + v) - 1, "sumber_volume": "kargo perusahaan (dilaporkan)"})
    return pd.DataFrame(rows).set_index("periode")


def delta_ebitda(F, ah, cogs_ex_dep, exposed, g, v, psi_down):
    """Selisih EBITDA (USD juta) atas perubahan tarif angkutan `g` dan volume `v`; struktur sama dengan transmission.rate_volume_grid."""
    d_rev = F * ((1 + v) * (1 + g) - 1) + ah * v
    psi = psi_down if v < 0 else 1.0
    return d_rev - psi * cogs_ex_dep * exposed * v


def backtest():
    """Uji balik: selisih EBITDA menurut model (basis tahun sebelumnya, tarif efektif dan volume tercatat) terhadap selisih EBITDA terealisasi."""
    a = tr.assumptions()
    psi = float(a.loc[PSI_DOWN, "central"])
    o = operating.load()
    rs = o[o.domain == "revenue_by_service"].pivot_table(index="metric_key", columns="period", values="value") / 1e6
    w = baseline.load_wide() / 1e6
    r = realized()
    from .. import covenant_band as cb
    rows = []
    for p, q in (("FY2023", "FY2022"), ("FY2024", "FY2023"), ("FY2025", "FY2024")):
        F, ah = rs.loc["freight_income", q], rs.loc["agency_forwarding_ports", q] + rs.loc["container_equipment_handling", q]
        rev = w.loc[("IS", "revenue"), q]
        cogs_ex = w.loc[("IS", "cogs"), q] - w.loc[("COGS_NOTE", "depreciation"), q]
        exposed = (F + ah + 0.0) / rev
        pred = delta_ebitda(F, ah, cogs_ex, exposed, r.loc[p, "tarif_efektif"], r.loc[p, "volume"], psi)
        act = (cb.ebitda_proxy(baseline.load_wide(), p) - cb.ebitda_proxy(baseline.load_wide(), q)) / 1e6
        rows.append({"periode": p, "tarif_efektif": r.loc[p, "tarif_efektif"], "volume": r.loc[p, "volume"], "model": pred, "terealisasi": act, "selisih_pct": (pred / act - 1) * 100})
    t = pd.DataFrame(rows).set_index("periode")
    return t


def _run(row, case, inp, paths, a_op, a, months=None, macro_on=False):
    st = cf.Stress(rate=float(row["tarif"]), volume=float(row["volume"]), months=int(months or row["bulan"]))
    return cf.run("MS-BASE", case, inp, paths, a_op, a, stress=st, macro=macro_on)


def hold_months(row, case, inp, paths, a_op, a, th, metric="liquidity"):
    """Lama (bulan) kisah harus bertahan sebelum saldo minimum `metric` menembus batas kas; None bila tidak tertembus dalam horizon."""
    col = "closing" if metric == "cash" else "liquidity"
    lo, hi = 1, len(cf.MONTHS)
    if float((_run(row, case, inp, paths, a_op, a, hi)[col] - th).min()) >= 0:
        return None
    while lo < hi:
        mid = (lo + hi) // 2
        if float((_run(row, case, inp, paths, a_op, a, mid)[col] - th).min()) < 0:
            hi = mid
        else:
            lo = mid + 1
    return lo


@dataclass
class BridgeView:
    narr: pd.DataFrame
    reported: pd.DataFrame
    realized: pd.DataFrame
    backtest: pd.DataFrame
    results: pd.DataFrame       # kisah x kasus
    paths: dict
    den: pd.DataFrame
    threshold: float
    macro_rows: pd.DataFrame    # skenario makro, basis yang sama
    cost_relief: float          # porsi penurunan tarif yang diimbangi penurunan biaya menurut uji balik FY2024
    relief_breakeven: pd.DataFrame


def build_view(cv=None, sv=None):
    cv = cv or cf.build_view()
    sv = sv or cy.build_view()
    inp, a, a_op, paths = cf._init(), cf.assumptions(), tr.assumptions(), macro.build_paths()
    th = cv.threshold
    N = narratives()
    rows, pth = [], {}
    base_e = None
    for _, n in N.iterrows():
        for case in ("central", "adverse"):
            df = _run(n, case, inp, paths, a_op, a)
            pth[(n["kisah"], case)] = df
            s = cf.summarize(df, th)
            cov = cy._calendar_cover(df, sv.den)
            worst = min(cov, key=cov.get)
            first_cov = next((k for k in ("FY2027", "FY2028", "FY2029", "FY2030") if cov[k] < tr.THRESHOLD), None)
            d_e = float(tr.rate_volume_grid(inp, a_op, [n["tarif"]], [n["volume"]], case)[0].iloc[0]["d_ebitda"])
            rows.append({"id": n["narrative_id"], "kisah": n["kisah"], "case": case, "d_ebitda": d_e, "ebitda_tahunan": inp["ebitda"] + d_e, "min_cash": s["min_cash"],
                         "min_liquidity": s["min_liquidity"], "end_cash": s["end_cash"], "first_below": s["first_below"], "first_below_liq": s["first_below_liq"],
                         "cover_min": cov[worst], "cover_min_year": worst, "first_cover_breach": first_cov,
                         **{f"cover_{k}": v for k, v in cov.items()},
                         "hold_liq": hold_months(n, case, inp, paths, a_op, a, th, "liquidity"), "hold_cash": hold_months(n, case, inp, paths, a_op, a, th, "cash")})
    res = pd.DataFrame(rows)
    mrows = []
    for sc in ("Dasar", "Energi bertahan", "Gabungan"):
        for case in ("central", "adverse"):
            df = cv.paths[(sc, case)]
            cov = cy._calendar_cover(df, sv.den)
            worst = min(cov, key=cov.get)
            s = cf.summarize(df, th)
            mrows.append({"kisah": sc, "case": case, "cover_min": cov[worst], "cover_min_year": worst, "min_cash": s["min_cash"], "min_liquidity": s["min_liquidity"],
                          "first_below": s["first_below"], "first_below_liq": s["first_below_liq"]})
    bt = backtest()
    relief = float(1 - bt.loc["FY2024", "terealisasi"] / bt.loc["FY2024", "model"])
    F = inp["rev_by_service"]["freight_income"]
    be = pd.DataFrame({"tanpa": sv.den["ruang_ebitda"] / F, "dengan": sv.den["ruang_ebitda"] / (F * (1 - relief))}) * -100
    return BridgeView(N, reported(), realized(), bt, res, pth, sv.den, th, pd.DataFrame(mrows), relief, be)


# --- tabel untuk notebook ----------------------------------------------------------------------------------------

def narrative_table(v):
    n = v.narr.copy()
    n["status"] = n["status"].map({"anchored": "dikalibrasi", "assumed": "asumsi"})
    n["tarif"], n["volume"] = n["tarif"] * 100, n["volume"] * 100
    n = n.rename(columns={"kisah": "Kisah", "rantai": "Rantai sebab-akibat", "tarif": "Tarif (%)", "volume": "Volume (%)", "bulan": "Lama (bulan)",
                          "jangkar_tarif": "Jangkar tarif", "jangkar_volume": "Jangkar volume", "status": "Status"})
    return n.set_index("Kisah")[["Rantai sebab-akibat", "Tarif (%)", "Volume (%)", "Lama (bulan)", "Jangkar tarif", "Jangkar volume", "Status"]]


def result_table(v, case="central"):
    r = v.results[v.results.case == case].copy()
    r["Cover pertama di bawah 1,10x"] = r["first_cover_breach"].fillna("tidak ada")
    r["Kas + deposito di bawah batas sejak"] = r["first_below_liq"].map(cf.ym)
    r["Bertahan sebelum kas + deposito tertembus (bulan)"] = r["hold_liq"].map(lambda x: "tidak tertembus" if pd.isna(x) else f"{int(x)}")
    r = r.rename(columns={"kisah": "Kisah", "d_ebitda": "Selisih EBITDA per tahun", "ebitda_tahunan": "EBITDA selama kisah", "cover_min": "Cover terendah",
                          "cover_min_year": "Tahun", "min_cash": "Kas minimum", "min_liquidity": "Kas + deposito minimum"})
    cols = ["Selisih EBITDA per tahun", "EBITDA selama kisah", "Cover terendah", "Tahun", "Cover pertama di bawah 1,10x", "Kas minimum", "Kas + deposito minimum", "Kas + deposito di bawah batas sejak"]
    if case == "central":
        cols.append("Bertahan sebelum kas + deposito tertembus (bulan)")
    return r.set_index("Kisah")[cols]


def reported_table(v):
    t = v.reported.copy()
    t["cakupan"] = t["cakupan"].map({"company": "perusahaan", "domestic": "domestik", "international": "internasional", "jakarta_hub": "hub Jakarta", "surabaya_hub": "hub Surabaya",
                                     "jakarta_makassar": "Jakarta-Makassar", "surabaya_makassar": "Surabaya-Makassar", "global_container": "kontainer global"}).fillna(t["cakupan"])
    p = t.pivot_table(index=["periode", "cakupan"], columns="jenis", values="perubahan", aggfunc="first")
    p.index.names = [None, None]
    return p[[c for c in ("tarif", "volume") if c in p]].rename(columns={"tarif": "Tarif (%)", "volume": "Volume (%)"})


def realized_table(v):
    r = v.realized.copy()
    r["perubahan_pendapatan"], r["volume"], r["tarif_efektif"] = r["perubahan_pendapatan"] * 100, r["volume"] * 100, r["tarif_efektif"] * 100
    return r.rename(columns={"pendapatan_angkutan": "Pendapatan angkutan", "perubahan_pendapatan": "Perubahan (%)", "volume": "Volume (%)", "tarif_efektif": "Tarif efektif (%)",
                             "sumber_volume": "Sumber volume"})


def backtest_table(v):
    b = v.backtest.copy()
    b["tarif_efektif"], b["volume"] = b["tarif_efektif"] * 100, b["volume"] * 100
    return b.rename(columns={"tarif_efektif": "Tarif efektif (%)", "volume": "Volume (%)", "model": "Selisih EBITDA model", "terealisasi": "Selisih EBITDA terealisasi",
                             "selisih_pct": "Model melebihkan (%)"})


def relief_table(v):
    t = v.relief_breakeven.copy()
    t.columns = ["Tanpa penyesuaian (%)", f"Biaya turun {v.cost_relief * 100:.0f}% dari penurunan (%)".replace(".", ",")]
    return t
