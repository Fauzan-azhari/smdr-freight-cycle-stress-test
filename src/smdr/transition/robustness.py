"""Uji ketahanan atas tiga klaim deck (6 Nov 2026): (1) statistik posisi siklus WCI, (2) ruang utang baru, (3) definisi cover.

(1) Posisi WCI >= +50% di atas rata-rata 52 pekan hanya terjadi pada dua episode sejak 2016 (2020-21 dan 2024), sehingga
    persentase pekan (61%) menyesatkan: 70 pekan tumpang tindih berasal dari dua episode, satu naik lanjut dan satu turun.
    Regresi perubahan 52 pekan ke depan terhadap posisi (galat HAC 52 pekan) tidak signifikan pada sampel penuh.
(2) Ruang utang baru = 3,0 x EBITDA - utang berbunga pada tanggal uji (bank + sukuk + sewa), per skenario parameter tengah.
(3) Cover dibaca tiga cara: proksi deck (sewa lancar ikut penyebut), bacaan harfiah klausul (bank lancar + sukuk lancar + bunga),
    dan penyebut tersirat DSCR perusahaan (sekitar USD 91 juta).
"""
import numpy as np
import pandas as pd
import statsmodels.api as sm

from .. import datapaths
from . import covenants as cvn

DSCR_IMPLIED_DEN = 91.0   # USD juta; tersirat dari DSCR yang dilaporkan FY2024-FY2025 (covenants.py)


def wci_episodes(wci, thr=0.5, gap_weeks=26):
    """Episode = pekan berturut-turut (jeda < gap_weeks) dengan rata-rata 4 pekan >= (1+thr) x rata-rata 52 pekan."""
    a4, a52 = wci.rolling(4).mean(), wci.rolling(52).mean()
    d = pd.DataFrame({"dev": a4 / a52 - 1, "fwd": wci.shift(-52) / wci - 1}).dropna()
    hi = d[d.dev >= thr]
    eps, cur = [], [hi.index[0]]
    for t in hi.index[1:]:
        if (t - cur[-1]).days > gap_weeks * 7:
            eps.append(cur); cur = [t]
        else:
            cur.append(t)
    eps.append(cur)
    return pd.DataFrame([{"mulai": e[0].date(), "selesai": e[-1].date(), "pekan": len(e), "perubahan_52p_dari_awal": float(d.loc[e[0], "fwd"]),
                          "median_52p": float(d.loc[e, "fwd"].median())} for e in eps])


def mean_reversion_fit(wci, exclude=None):
    """Regresi ln(WCI t+52 / WCI t) pada posisi (ln rata-rata 4 pekan - ln rata-rata 52 pekan); galat HAC 52 pekan."""
    w = wci.asfreq("W-THU").interpolate(limit=6)
    lw = np.log(w)
    d = pd.DataFrame({"dev": lw.rolling(4).mean() - lw.rolling(52).mean(), "fwd": lw.shift(-52) - lw}).dropna()
    if exclude:
        d = d[(d.index < exclude[0]) | (d.index > exclude[1])]
    m = sm.OLS(d.fwd, sm.add_constant(d.dev)).fit(cov_type="HAC", cov_kwds={"maxlags": 52})
    lo, hi = m.conf_int().loc["dev"]
    return {"n": int(len(d)), "slope": float(m.params["dev"]), "ci_lo": float(lo), "ci_hi": float(hi)}


def new_debt_capacity(suite, th=cvn.TH_ND):
    """Utang baru (USD juta) yang masih muat sebelum Net Debt/EBITDA mencapai batas; negatif = batas sudah tertembus."""
    s = suite[suite.case == "central"].copy()
    s["utang"] = s.nd_ebitda * s.ebitda
    s["ruang_utang_baru"] = th * s.ebitda - s.utang
    return s[["skenario", "kelompok", "fy", "ebitda", "utang", "ruang_utang_baru"]]


def cover_readings(suite, den, th=cvn.TH_COVER):
    """Cover per skenario menurut tiga bacaan penyebut (FY2027-FY2030)."""
    s = suite[suite.case == "central"].copy()
    lease = float(den["sewa"].iloc[0])
    s["cover_proksi"] = s.ebitda / s.penyebut
    s["cover_harfiah"] = s.ebitda / (s.penyebut - lease)
    s["cover_dscr_tersirat"] = s.ebitda / DSCR_IMPLIED_DEN
    return s[["skenario", "kelompok", "fy", "ebitda", "cover_proksi", "cover_harfiah", "cover_dscr_tersirat"]]


# --- Revisi 7 Nov 2026: hasil yang konsisten antar-ukuran -----------------------------------------------------------
# (a) Cover sukuk dibaca pada basis DSCR yang dilaporkan perusahaan: penyebut tersirat FY2024 dan FY2025 sama (sekitar USD 91 juta),
#     ditambah pokok sukuk yang jatuh tempo dalam 12 bulan setelah tanggal uji. Bacaan dengan sewa lancar menghasilkan 1,32x untuk
#     FY2025, jauh dari 2,11x yang dilaporkan, sehingga dipakai hanya sebagai uji sensitivitas.
# (b) Net Debt/EBITDA dan kas memakai asumsi pembiayaan yang sama: angsuran bank dibiayai ulang (saldo bank 9M26 tetap), sesuai
#     saldo utang bank yang stabil USD 185-224 juta pada FY2023-9M26. Varian tanpa pembiayaan ulang dilaporkan sebagai sensitivitas.

DSCR_REPORTED = {"FY2024": 1.89, "FY2025": 2.11}   # Informasi Tambahan Sukuk Ijarah II/III, tabel rasio yang dipersyaratkan
MARKET = ("Permintaan melemah", "Kelebihan kapasitas", "Permintaan lemah dan kelebihan kapasitas")   # Rute kembali normal: belum dikalibrasi
MACRO = {"MS-BASE": "Dasar", "MS-ENERGY": "Energi bertahan", "MS-COMBINED": "Gabungan"}
TH_SAFE_ND = 2.70   # zona aman: jarak 10% dari threshold 3,0x


def dscr_denominator(w):
    """Penyebut DSCR tersirat (USD juta) = EBITDA operasi / DSCR dilaporkan, dan cover FY2025 menurut dua bacaan neraca sebagai validasi."""
    from .. import covenant_band as cb
    g = lambda k, p: 0.0 if pd.isna(w.loc[("BS", k), p]) else float(w.loc[("BS", k), p]) / 1e6
    out = {p: cb.ebitda_operating(w, p) / 1e6 / r for p, r in DSCR_REPORTED.items()}
    e25, i25 = cb.ebitda_operating(w, "FY2025") / 1e6, float(w.loc[("IS", "finance_expense"), "FY2025"]) / 1e6
    base = g("bank_long_term_current", "FY2025") + g("sukuk_current", "FY2025") + i25
    return {"implied": out, "den": float(np.mean(list(out.values()))),
            "fy2025_reported": DSCR_REPORTED["FY2025"], "fy2025_with_lease": e25 / (base + g("lease_current", "FY2025")), "fy2025_literal": e25 / base}


def _ebitda_fy2026(w, path):
    """EBITDA FY2026 = 9M26 terealisasi + Okt-Des 2026 menurut jalur skenario (basis EBITDA operasi TTM)."""
    from .. import covenant_band as cb
    from . import cashflow as cf
    ttm = cf._init()["ebitda"]
    q4_25 = (cb.ebitda_proxy(w, "FY2025") - cb.ebitda_proxy(w, "9M25")) / 1e6
    return ttm - q4_25 + float(path.loc["2026-10":"2026-12", "ebitda"].sum())


def consistent_results(th_cash=None):
    """Satu tabel per skenario x kasus: Net Debt/EBITDA (FY2026-FY2028), cover basis DSCR, Current Ratio, kas + deposito minimum dan
    bulan pertama di bawah batas kas, semuanya dari jalur kas yang sama (angsuran bank dibiayai ulang)."""
    from .. import baseline
    from . import bridge as br, cashflow as cf, macro, transmission as tr
    w = baseline.load_wide()
    inp, a, a_op, paths = cf._init(), cf.assumptions(), tr.assumptions(), macro.build_paths()
    th = th_cash if th_cash is not None else cf.min_cash(inp, a, "central")
    b = cvn.base_position(w)
    den0 = dscr_denominator(w)["den"]
    roll, noref = cf.Financing(bank_redraw=1.0), cf.Financing()
    runs = []
    N = br.narratives().set_index("kisah")
    for k in MARKET:
        n = N.loc[k]
        st = cf.Stress(rate=float(n.tarif), volume=float(n.volume), months=int(n.bulan))
        runs.append((k, "Market", lambda case, fin, st=st: cf.run("MS-BASE", case, inp, paths, a_op, a, stress=st, fin=fin, macro=False)))
    for sid, k in MACRO.items():
        runs.append((k, "Macro", lambda case, fin, sid=sid: cf.run(sid, case, inp, paths, a_op, a, fin=fin)))
    rows, P = [], {}
    for k, grp, fn in runs:
        for case in ("central", "adverse"):
            df, df_n = fn(case, roll), fn(case, noref)
            P[(k, case)] = df
            e = df["ebitda"].groupby(df.index.str[:4]).sum()
            r = {"skenario": k, "kelompok": grp, "case": case, "ebitda_FY2026": _ebitda_fy2026(w, df)}
            for fy in cvn.FYS[:2]:
                y = fy[2:]
                r[f"ebitda_{fy}"] = float(e[y])
                sukuk = max(b["sukuk"] - sum(v for kk, v in cvn.SUKUK_DUE_12M.items() if kk < fy), 0.0)
                debt = b["bank"] + b["lease"] + sukuk
                r[f"nd_{fy}"] = debt / float(e[y])
                bank_n = float(df_n.loc[f"{y}-12", "bank_balance"]) + inp["short_bank"] * cf.pick(a, "short_bank_rollover", case)
                r[f"nd_{fy}_amortisasi"] = (bank_n + b["lease"] + sukuk) / float(e[y])
                r[f"cover_{fy}"] = float(e[y]) / (den0 + cvn.SUKUK_DUE_12M[fy])
            r["nd_FY2026"] = (b["bank"] + b["lease"] + b["sukuk"]) / r["ebitda_FY2026"]
            cr = []
            for fy in cvn.FYS:
                y = fy[2:]
                cash = float(df["closing"][f"{y}-12"])     # deposito tetap tercatat di aset lancar walau sebagian tidak dapat ditarik
                cr.append((b["ca"] - (inp["opening_cash"] - cash)) / (b["cl"] + cvn.SUKUK_DUE_12M[fy]))
            r["current_ratio_min"] = min(cr)
            r["current_ratio_breach_fy"] = next((fy for fy, v in zip(cvn.FYS, cr) if v < cvn.TH_CR), None)
            below = df.index[df["liquidity"] < th]
            r["min_liquidity"] = float(df["liquidity"].min())
            r["first_below"] = below[0] if len(below) else None
            r["min_liquidity_noref"] = float(df_n["liquidity"].min())
            rows.append(r)
    t = pd.DataFrame(rows)
    t["pelunasan_ke_2_7x"] = [max(0.0, (b["bank"] + b["lease"] + b["sukuk"]) - TH_SAFE_ND * e) for e in t["ebitda_FY2027"]]
    return t, P, th


def _long_series():
    """Brent harian FRED DCOILBRENTEU (1987-2026, rata-rata bulanan) dan USD/IDR bulanan FRED CCUSMA02IDM618N (OECD)."""
    import os
    from .. import baseline
    from .. import datapaths
    rd = lambda f: pd.to_numeric(pd.read_csv(datapaths.table(f), parse_dates=["observation_date"]).set_index("observation_date").iloc[:, 0], errors="coerce").dropna()
    return rd("brent_daily_fred.csv").resample("MS").mean(), rd("usdidr_monthly_fred.csv")


def severity_check():
    """Perbandingan pada keparahan historis setara: perubahan 12 bulan persentil 90 dari sejarah panjang (Brent 1988-2026; kurs
    2000-2026, rezim kurs mengambang) dan penurunan tarif efektif SMDR FY2024, diterjemahkan ke selisih EBITDA (USD juta).
    Rentang Brent dan kurs memakai parameter transmisi tengah dan merugikan (elastisitas bunker, pass-through, porsi EBIT rupiah)."""
    import os
    from .. import baseline
    from . import cashflow as cf, transmission as tr
    inp, a = cf._init(), tr.assumptions()
    b, fx = _long_series()
    fx = fx["2000":]
    rb, rf = (b / b.shift(12) - 1).dropna(), (fx / fx.shift(12) - 1).dropna()
    ann = b.groupby(b.index.year).mean().pct_change().dropna()
    db, dfx = float(rb.quantile(0.9)), float(rf.quantile(0.9))
    fc = lambda case: tr.fuel_cost(inp, a, case, db)
    d_brent = {case: -fc(case) * tr.pick(a, "bunker_brent_elasticity", case, db) * db * (1 - tr.pick(a, "bunker_pass_through", case, db)) for case in ("central", "adverse")}
    d_fx = {case: tr.pick(a, "idr_ebit_share", case, 1) * inp["ebit"] * (1 / (1 + dfx) - 1) for case in ("central", "adverse")}
    d_rate = float(tr.rate_volume_grid(inp, a, [-0.116], [0.0], "central")[0].iloc[0]["d_ebitda"])
    m = pd.read_csv(datapaths.table("macro_monthly.csv")).pivot(index="month", columns="series", values="value")
    wc = pd.read_csv(datapaths.table("wci_composite_weekly.csv"), parse_dates=["date"]).drop_duplicates("date").set_index("date")["wci"]
    wa, ba = wc.groupby(wc.index.year).mean(), b.groupby(b.index.year).mean()
    j = pd.concat([np.log(wa).diff(), np.log(ba).diff()], axis=1, keys=["wci", "brent"]).dropna()
    j = j[j.index <= 2025]
    return {"brent_p90": db, "n_brent": int(len(rb)), "brent_start": int(b.index.min().year), "brent_p90_annual": float(ann[ann.index < 2026].quantile(0.9)),
            "n_brent_annual": int((ann.index < 2026).sum()), "d_brent": d_brent["central"], "d_brent_adverse": d_brent["adverse"],
            "fx_p90": dfx, "n_fx": int(len(rf)), "d_fx": d_fx["central"], "d_fx_adverse": d_fx["adverse"],
            "rate_fy2024": -0.116, "d_rate": d_rate, "ebitda": inp["ebitda"],
            "corr_wci_brent": float(j.corr().iloc[0, 1]), "n_corr": int(len(j)), "corr_years": (int(j.index.min()), int(j.index.max())),
            "brent_oct": float(m["brent_avg"].dropna().iloc[-1]), "brent_ttm": inp["brent_ttm"]}


def historical_test(debt, periods=("FY2022", "FY2023", "FY2024", "FY2025")):
    """Net Debt to EBITDA bila EBITDA tahun historis terjadi pada utang hari ini (bank + sukuk + sewa 30 Sep 2026). EBITDA basis operasi,
    basis yang sama yang mereproduksi rasio yang dilaporkan perusahaan (FY2022 0,66x; FY2025 2,52x) dan EBITDA TTM USD 240 juta."""
    from .. import baseline, covenant_band as cb
    w = baseline.load_wide()
    e = pd.Series({p: cb.ebitda_operating(w, p) / 1e6 for p in periods})
    return pd.DataFrame({"ebitda": e, "nd": debt / e})


def mitigation_test(res, P, paydown, dividend_stop=False, paydown_month="2027-09", stop_from="2027-06"):
    """Uji gabungan satu paket langkah pada jalur kas yang sama: pelunasan utang bank dari kas (USD juta, bulan `paydown_month`) dan
    penghentian dividen sejak `stop_from`. Mengembalikan Net Debt/EBITDA FY2027-FY2028, Current Ratio terendah FY2027-FY2030 dan
    kas + deposito terendah. Penghematan bunga atas pelunasan tidak dihitung (sisi konservatif)."""
    from .. import baseline
    from . import cashflow as cf
    b = cvn.base_position(baseline.load_wide())
    inp, a = cf._init(), cf.assumptions()
    out = []
    for (k, case), df in P.items():
        idx = df.index
        adj = pd.Series(np.where(idx >= paydown_month, -paydown, 0.0), index=idx)
        if dividend_stop:
            div = pd.Series([-cf.pick(a, "dividend_annual", case) if int(m[5:]) == cf.DIVIDEND_MONTH else 0.0 for m in idx], index=idx)
            adj = adj - (div * (idx >= stop_from)).cumsum()
        cash, liq = df["closing"] + adj, df["liquidity"] + adj
        r = res[(res.skenario == k) & (res.case == case)].iloc[0]
        row = {"skenario": k, "case": case, "paydown": paydown, "dividend_stop": dividend_stop}
        for fy in cvn.FYS[:2]:
            row[f"nd_{fy}"] = (r[f"nd_{fy}"] * r[f"ebitda_{fy}"] - paydown) / r[f"ebitda_{fy}"]
        cr = [(b["ca"] - (inp["opening_cash"] - float(cash[f"{fy[2:]}-12"]))) / (b["cl"] + cvn.SUKUK_DUE_12M[fy]) for fy in cvn.FYS]
        row["current_ratio_min"] = min(cr)
        row["current_ratio_min_fy"] = cvn.FYS[int(np.argmin(cr))]
        row["min_liquidity"] = float(liq.min())
        out.append(row)
    return pd.DataFrame(out)


def backtest_errors():
    """Galat uji balik (model / aktual) dan perubahan biaya kas yang tidak dimodelkan (jasa + penanganan angkutan, USD juta)."""
    from .. import baseline
    from . import bridge as br
    bt = br.backtest()
    w = baseline.load_wide() / 1e6
    c = lambda p: float(w.loc[("COGS_NOTE", "services_cost"), p] + w.loc[("COGS_NOTE", "freight_handling"), p])
    bt["galat_pct"] = (bt["model"] / bt["terealisasi"] - 1) * 100
    bt["biaya_jasa_delta"] = [c(p) - c(q) for p, q in (("FY2023", "FY2022"), ("FY2024", "FY2023"), ("FY2025", "FY2024"))]
    return bt


def cash_tornado(skenario="Permintaan lemah dan kelebihan kapasitas"):
    """Sensitivitas satu-per-satu: kas + deposito terendah (USD juta) bila satu parameter kas digeser ke sisi merugikan dan
    parameter lain tetap tengah, pada skenario pasar `skenario` dengan pembiayaan yang sama (angsuran bank dibiayai ulang)."""
    from . import bridge as br, cashflow as cf, macro, transmission as tr
    inp, a, a_op, paths = cf._init(), cf.assumptions(), tr.assumptions(), macro.build_paths()
    n = br.narratives().set_index("kisah").loc[skenario]
    st = cf.Stress(rate=float(n.tarif), volume=float(n.volume), months=int(n.bulan))
    fin = cf.Financing(bank_redraw=1.0)
    run = lambda am, case="central": cf.run("MS-BASE", case, inp, paths, a_op, am, stress=st, fin=fin, macro=False)["liquidity"].min()
    ref = float(run(a))
    rows = []
    for prm in ["ocf_conversion", "maintenance_capex", "lease_principal", "deposit_availability", "short_bank_rollover",
                "program_cost_overrun", "program_front_share", "cash_yield"]:
        am = a.copy()
        am.loc[prm, "central"] = cf.pick(a, prm, "adverse")
        rows.append({"parameter": prm, "label": cf.LABELS.get(prm, prm), "central": float(a.loc[prm, "central"]), "adverse": cf.pick(a, prm, "adverse"),
                     "d_min_liq": float(run(am)) - ref})
    t = pd.DataFrame(rows).sort_values("d_min_liq").reset_index(drop=True)
    t.attrs.update({"ref": ref, "all_adverse": float(run(a, "adverse"))})
    return t


# --- Revisi audit investigatif 7 Nov 2026 ---------------------------------------------------------------------------
# Tabel "rasio yang dipersyaratkan dalam perjanjian kredit" juga dilaporkan per 31 Maret 2025 (Informasi Tambahan Sukuk II hal. 22),
# sehingga frekuensi pengukuran covenant belum tentu tahunan. Sisi prudent: rasio diukur tiap akhir kuartal atas EBITDA 12 bulan terakhir.
QUARTERS = ["2026-12", "2027-03", "2027-06", "2027-09", "2027-12", "2028-03", "2028-06", "2028-09", "2028-12"]


def _sukuk_due_12m(inp, date):
    """Pokok sukuk (USD juta, kurs Sep 2026) yang jatuh tempo dalam 12 bulan setelah `date` (YYYY-MM)."""
    ev = inp["events"]
    d0 = pd.Period(date, "M").to_timestamp("M")
    d1 = d0 + pd.DateOffset(months=12)
    m = (ev.event_type != "coupon") & (pd.to_datetime(ev.payment_date) > d0) & (pd.to_datetime(ev.payment_date) <= d1)
    return float(ev.loc[m, "amount"].sum()) / inp["fx_sep"] / 1e6


def quarterly_tests(P, case_filter=None):
    """Net Debt to EBITDA dan DSCR per akhir kuartal Des 2026 - Des 2028 atas EBITDA 12 bulan terakhir. Bulan aktual sebelum Okt 2026
    diwakili rata-rata TTM Sep 2026 (EBITDA TTM / 12). Utang: bank tetap (dibiayai ulang), sewa tetap, sukuk berkurang saat jatuh tempo."""
    from .. import baseline
    from . import cashflow as cf
    inp = cf._init()
    b = cvn.base_position(baseline.load_wide())
    den0 = dscr_denominator(baseline.load_wide())["den"]
    ev = inp["events"]
    rows = []
    for (k, case), df in P.items():
        if case_filter and case != case_filter:
            continue
        e = df["ebitda"]
        for q in QUARTERS:
            end = pd.Period(q, "M")
            months = [str(end - i) for i in range(12)]
            ttm = sum(float(e[m]) if m in e.index else inp["ebitda"] / 12 for m in months)
            paid = ev[(ev.event_type != "coupon") & (pd.to_datetime(ev.payment_date) <= end.to_timestamp("M"))]
            sukuk = max(b["sukuk"] - float(paid["amount"].sum()) / inp["fx_sep"] / 1e6, 0.0)
            debt = b["bank"] + b["lease"] + sukuk
            rows.append({"skenario": k, "case": case, "quarter": q, "ebitda_ttm": ttm, "nd": debt / ttm, "dscr_bank": ttm / den0,
                         "dscr_with_sukuk": ttm / (den0 + _sukuk_due_12m(inp, q)), "debt": debt})
    return pd.DataFrame(rows)


def first_quarter(q, col="nd", th=3.0, above=True):
    """Kuartal pertama per skenario x kasus saat rasio melewati `th` (None bila tidak pernah)."""
    out = {}
    for (k, case), g in q.groupby(["skenario", "case"]):
        hit = g[g[col] > th] if above else g[g[col] < th]
        out[(k, case)] = hit["quarter"].iloc[0] if len(hit) else None
    return out


def weak_recovery(P, res, recover_to, case="central"):
    """Sensitivitas pemulihan: setelah guncangan berakhir EBITDA hanya pulih ke `recover_to` (USD juta/tahun), bukan ke TTM.
    Selisih EBITDA dikalikan konversi kas lalu diakumulasikan ke kas; bunga atas kas diabaikan. Mengembalikan kas + deposito terendah."""
    from . import bridge as br, cashflow as cf
    inp, a = cf._init(), cf.assumptions()
    N = br.narratives().set_index("kisah")
    out = {}
    for k in MARKET:
        df = P[(k, case)]
        n = int(N.loc[k, "bulan"])
        gap = np.where(np.arange(len(df)) >= n, (inp["ebitda"] - recover_to) / 12 * cf.pick(a, "ocf_conversion", case), 0.0)
        out[k] = float((df["liquidity"] - np.cumsum(gap)).min())
    return out
