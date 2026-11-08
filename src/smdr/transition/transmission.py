"""Transmisi skenario makro dan guncangan tarif/volume ke EBITDA, laba sebelum pajak, dan ruang cover covenant.

Pendekatan: perubahan relatif terhadap baseline TTM September 2026, bukan level yield. Setiap parameter berupa rentang
(rendah, tengah, merugikan) pada operating_assumptions.csv. Hasil adalah pro forma berbasis posisi 30 September 2026
dan bukan proyeksi.
"""
import os

import numpy as np
import pandas as pd

from .. import baseline, datapaths, operating
from . import macro

WINDOW = 12  # bulan, Okt 2026 s.d. Sep 2027
THRESHOLD = 1.10


def assumptions():
    a = pd.read_csv(datapaths.table("operating_assumptions.csv")).set_index("parameter")
    return a


def pick(a, name, case, direction=0):
    """Nilai parameter. 'central' = tengah. 'adverse' dipilih menurut aturan merugikan dan arah guncangan (direction > 0 berarti
    biaya/tarif bergerak naik, yang merugikan jika parameter besar)."""
    r = a.loc[name]
    if case == "central":
        return float(r["central"])
    rule = r["adverse_rule"]
    if rule == "high": return float(r["high"])
    if rule == "low": return float(r["low"])
    if rule == "sign": return float(r["high"] if direction >= 0 else r["low"])
    if rule == "sign_inverse": return float(r["low"] if direction >= 0 else r["high"])
    raise ValueError(rule)


def inputs():
    ops = operating.load()
    r = ops[ops.domain == "revenue_by_service"].pivot_table(index="metric_key", columns="period", values="value")
    ttm = (r["FY2025"] - r["9M25"] + r["9M26"]) / 1e6
    w = baseline.load_wide()
    t = pd.read_csv(datapaths.table("baseline_ttm.csv")).set_index(["statement", "line_key"])["value_usd"]
    b = pd.read_csv(datapaths.table("baseline_bridge.csv")).set_index("metric")
    mw, full = macro.history()
    bs = lambda k: float(w.loc[("BS", k), "9M26"])
    en = ops[(ops.metric_key == "energy_conventional") & (ops.period == "FY2025")]["value"].iloc[0]
    price = ops[(ops.metric_key == "vlsfo_singapore_avg")]["value"].iloc[0]
    fx = ops[ops.domain == "fx_position"].pivot_table(index="period", columns="metric_key", values="value")
    n9 = fx.loc["9M26"]
    short_idr = (n9[["idr_bank_loans", "idr_trade_payables", "idr_long_term_loans", "idr_sukuk"]].sum() - n9[["idr_cash", "idr_receivables"]].sum()) / 1e6
    fac = pd.read_csv(datapaths.table("financing_facilities.csv")).set_index("facility_id")
    ttm_months = [str(p) for p in pd.period_range("2025-10", "2026-09", freq="M")]
    return {
        "rev_by_service": ttm, "revenue": float(ttm.sum()), "cogs": t[("IS", "cogs")] / 1e6, "cogs_dep": t[("COGS_NOTE", "depreciation")] / 1e6,
        "ebit": b.loc["ebit_ttm", "reconciled_value"] / 1e6, "ebitda": b.loc["ebitda_ttm_operating_pdf_basis", "reconciled_value"] / 1e6,
        "interest_ttm": t[("IS", "finance_expense")] / 1e6, "bank_debt": (bs("bank_short_term") + bs("bank_long_term_current") + bs("bank_long_term")) / 1e6,
        "bank_current": bs("bank_long_term_current") / 1e6, "lease_current": bs("lease_current") / 1e6,
        "energy_gj": float(en), "vlsfo": float(price), "short_idr": float(short_idr), "idr_sukuk_usd": float(n9["idr_sukuk"]) / 1e6,
        "brent_ttm": float(mw.loc[ttm_months, "brent_avg"].mean()), "fx_ttm": float(mw.loc[ttm_months, "usdidr_close"].mean()),
        "fx_sep": float(mw.loc["2026-09", "usdidr_close"]), "seri_b_idr": float(fac.loc["S1B", "nominal_limit"]),
    }


def fuel_cost(inp, a, case, direction=0):
    share, lhv = pick(a, "vessel_energy_share", case, direction), pick(a, "lhv_gj_per_t", case, direction)
    return inp["energy_gj"] * share / lhv * inp["vlsfo"] / 1e6  # USD juta


def denominator(inp, seri_b_fx, d_interest=0.0):
    """Penyebut cover uji FY2027 pro forma: bagian lancar bank + sewa + bunga + pokok Seri B (kurs skenario akhir 2027)."""
    return inp["bank_current"] + inp["lease_current"] + inp["interest_ttm"] + d_interest + inp["seri_b_idr"] / seri_b_fx / 1e6


def scenario_effects(inp, paths, a, sid, case):
    p = paths[paths.scenario_id == sid]
    win = lambda drv: p[p.driver == drv].sort_values("month").iloc[:WINDOW]["value"]
    brent, fx, bi = win("brent"), win("usdidr"), win("bi_rate")
    d_brent = brent.mean() / inp["brent_ttm"] - 1
    eps, phi = pick(a, "bunker_brent_elasticity", case, d_brent), pick(a, "bunker_pass_through", case, d_brent)
    fc = fuel_cost(inp, a, case, d_brent)
    d_bunker = -fc * eps * d_brent * (1 - phi)                      # dampak ke EBITDA (negatif bila biaya naik)
    theta = pick(a, "idr_ebit_share", case, np.sign(fx.mean() - inp["fx_ttm"]))
    d_trans = theta * inp["ebit"] * (inp["fx_ttm"] / fx.mean() - 1)   # translasi laba rupiah ke dolar AS
    fx_end = float(fx.iloc[-1])
    reval = inp["short_idr"] * (1 - inp["fx_sep"] / fx_end)         # revaluasi posisi rupiah neto (non-kas, di bawah EBIT)
    d_rate = float(bi.mean()) - 5.75
    fs = pick(a, "floating_debt_share", case, d_rate)
    d_int = fs * inp["bank_debt"] * d_rate / 100
    d_ebitda = d_bunker + d_trans
    fx_dec27 = float(p[(p.driver == "usdidr") & (p.month == "2027-12")]["value"].iloc[0])
    den = denominator(inp, fx_dec27, d_int)
    return {"scenario": sid, "case": case, "d_brent_pct": d_brent * 100, "d_bunker": d_bunker, "d_translation": d_trans, "d_ebitda": d_ebitda,
            "reval": reval, "d_interest": d_int, "d_pbt": d_ebitda + reval - d_int, "ebitda": inp["ebitda"] + d_ebitda,
            "denominator": den, "cover": (inp["ebitda"] + d_ebitda) / den}


def all_scenarios(inp=None, paths=None, a=None):
    inp, paths, a = inp or inputs(), paths if paths is not None else macro.build_paths(), a if a is not None else assumptions()
    rows = [scenario_effects(inp, paths, a, sid, c) for sid in sorted(paths.scenario_id.unique()) for c in ("central", "adverse")]
    return pd.DataFrame(rows)


def rate_volume_grid(inp, a, rates, vols, case="central"):
    """Perubahan EBITDA (USD juta) dan cover uji FY2027 untuk kombinasi perubahan tarif angkut dan volume."""
    rs = inp["rev_by_service"]
    F, A, H = rs["freight_income"], rs["agency_forwarding_ports"], rs["container_equipment_handling"]
    exposed = (F + A + H) / inp["revenue"]
    cogs_exdep = inp["cogs"] - inp["cogs_dep"]
    psi_dn = pick(a, "cost_flex_down", case)
    fx_dec27 = float(macro.build_paths().query("scenario_id == 'MS-BASE' and driver == 'usdidr' and month == '2027-12'")["value"].iloc[0])
    den = denominator(inp, fx_dec27)
    out = []
    for g in rates:
        for v in vols:
            d_rev = F * ((1 + v) * (1 + g) - 1) + (A + H) * v
            psi = psi_dn if v < 0 else 1.0
            d_cost = psi * cogs_exdep * exposed * v
            d_e = d_rev - d_cost
            out.append({"rate": g, "volume": v, "d_ebitda": d_e, "ebitda": inp["ebitda"] + d_e, "cover": (inp["ebitda"] + d_e) / den})
    return pd.DataFrame(out), den


def breakeven_rate(inp, den, volume=0.0, a=None, case="central"):
    """Perubahan tarif angkut yang membuat cover = 1,10x pada volume tertentu (bentuk tertutup, linier)."""
    rs = inp["rev_by_service"]; F, A, H = rs["freight_income"], rs["agency_forwarding_ports"], rs["container_equipment_handling"]
    exposed = (F + A + H) / inp["revenue"]; cogs_exdep = inp["cogs"] - inp["cogs_dep"]
    psi = pick(a, "cost_flex_down", case) if volume < 0 else 1.0
    d_vol = F * volume + (A + H) * volume - psi * cogs_exdep * exposed * volume
    need = THRESHOLD * den - inp["ebitda"]               # kenaikan EBITDA yang dibutuhkan (negatif = ada ruang)
    return (need - d_vol) / (F * (1 + volume))


# --- tampilan untuk notebook ------------------------------------------------------------------------------------

from dataclasses import dataclass

NAMES = {"MS-BASE": "Dasar", "MS-ENERGY": "Energi bertahan", "MS-NORMAL": "Normalisasi cepat", "MS-FX": "Tekanan kurs",
         "MS-RATE": "Tekanan bunga", "MS-COMBINED": "Gabungan"}
ORDER = ["Dasar", "Normalisasi cepat", "Energi bertahan", "Tekanan kurs", "Tekanan bunga", "Gabungan"]
RATES = [x / 100 for x in range(-40, 11, 5)]


@dataclass
class TransmissionView:
    inp: dict
    scenarios: pd.DataFrame      # kolom: scenario (nama), case, dan komponen dampak
    structure: pd.DataFrame      # pendapatan TTM menurut jenis jasa dan kepekaan
    assumptions: pd.DataFrame    # tabel parameter untuk tampilan
    fuel: tuple                  # (rendah, tengah, tinggi) biaya bunker TTM, USD juta
    grid: pd.DataFrame
    denominator: float
    breakeven: dict              # volume -> perubahan tarif impas
    headroom: float              # ruang EBITDA terhadap batas pada baseline, USD juta


def build_view():
    inp, a, paths = inputs(), assumptions(), macro.build_paths()
    res = all_scenarios(inp, paths, a)
    res["scenario"] = res["scenario"].map(NAMES)
    rs = inp["rev_by_service"]
    tot = rs.sum()
    labels = {"freight_income": ("Pendapatan angkutan", "tarif dan volume"), "agency_forwarding_ports": ("Keagenan, forwarding, dan pelabuhan", "volume"),
              "container_equipment_handling": ("Penanganan peralatan dan muatan", "volume"), "time_charter": ("Sewa kapal berbasis waktu", "kontrak (tetap)"),
              "other_revenue": ("Lain-lain", "tetap")}
    st = pd.DataFrame([(labels[k][0], rs[k], rs[k] / tot * 100, labels[k][1]) for k in labels], columns=["Jenis jasa", "Pendapatan TTM (USD juta)", "Porsi (%)", "Kepekaan dalam model"]).set_index("Jenis jasa")
    disp = a[["description", "low", "central", "high", "status"]].copy()
    disp.columns = ["Parameter", "Rendah", "Tengah", "Merugikan (batas)", "Status"]
    disp["Status"] = disp["Status"].map({"assumed": "asumsi"})
    disp = disp.set_index("Parameter")
    k = lambda sh, lh: inp["energy_gj"] * sh / lh * inp["vlsfo"] / 1e6
    fuel = (k(a.loc["vessel_energy_share", "low"], a.loc["lhv_gj_per_t", "high"]), fuel_cost(inp, a, "central"),
            k(a.loc["vessel_energy_share", "high"], a.loc["lhv_gj_per_t", "low"]))
    grid, den = rate_volume_grid(inp, a, RATES, [-0.10, 0.0, 0.10])
    be = {v: breakeven_rate(inp, den, v, a) for v in (-0.10, 0.0, 0.10)}
    return TransmissionView(inp, res, st, disp, fuel, grid, den, be, inp["ebitda"] - THRESHOLD * den)
