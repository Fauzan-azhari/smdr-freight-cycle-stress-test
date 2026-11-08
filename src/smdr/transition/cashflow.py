"""Jalur kas bulanan eksploratif Oktober 2026 - Desember 2031 (63 bulan), dalam USD juta.

Pendekatan kas operasi: EBITDA operasi dikalikan rasio konversi kas, dikurangi bunga, sewa, belanja modal, angsuran dan
pelunasan utang, serta dividen. Setiap peristiwa kas masuk tepat satu kategori. Saldo awal adalah posisi 30 September 2026;
hasil adalah simulasi dari tanggal tersebut, bukan kas aktual sesudahnya, dan bukan proyeksi laba: EBITDA dasar ditahan pada
TTM dan hanya digeser oleh skenario makro serta tekanan tarif/volume yang dinyatakan.
"""
import datetime as dt
import os
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .. import baseline
from . import financing, macro
from .. import datapaths
from . import transmission as tr

MONTHS = [str(p) for p in pd.period_range("2026-10", "2031-12", freq="M")]
PROGRAM_START, PROGRAM_MONTHS, FRONT_MONTHS = "2026-11", 13, 6
DIVIDEND_MONTH = 6
BASE_RATE = 5.75
LINES = ["ocf", "interest_income", "sukuk_coupon", "other_interest", "lease", "maintenance_capex", "program_capex",
         "bank_repay", "short_bank_repay", "dividend", "sukuk_principal", "refi_draw", "refi_service", "bank_redraw"]


def assumptions():
    return pd.read_csv(datapaths.table("cash_assumptions.csv")).set_index("parameter")


def pick(a, name, case):
    r = a.loc[name]
    if case == "central":
        return float(r["central"])
    return float(r["high"] if r["adverse_rule"] == "high" else r["low"])


def inputs():
    inp = tr.inputs()
    w = baseline.load_wide() / 1e6
    t = lambda s, k: float(w.loc[(s, k), "FY2025"] - w.loc[(s, k), "9M25"] + w.loc[(s, k), "9M26"])
    ev = financing.debt_service()
    ocf_ttm = t("CF", "cfo") + t("CF", "interest_paid") - t("CF", "interest_received")
    inp.update({
        "opening_cash": float(w.loc[("BS", "cash"), "9M26"]), "ocf_ttm": ocf_ttm, "interest_paid_ttm": t("CF", "interest_paid"),
        "interest_received_ttm": t("CF", "interest_received"), "short_bank": float(w.loc[("BS", "bank_short_term"), "9M26"]),
        "bank_current": float(w.loc[("BS", "bank_long_term_current"), "9M26"]),
        "idr_cash_usd": float(operating_fx()["idr_cash"]) / 1e6, "deposits": float(w.loc[("BS", "other_fin_assets_current"), "9M26"]),
        "opex_month": (inp["revenue"] - inp["ebitda"]) / 12, "events": ev,
        "program_idr": float(pd.read_csv(datapaths.table("capex_milestones.csv"))["amount"].sum()),
    })
    inp["sukuk_coupon_ttm"] = sukuk_coupons_ttm()
    return inp


def operating_fx():
    from .. import operating
    ops = operating.load()
    return ops[(ops.domain == "fx_position") & (ops.period == "9M26")].set_index("metric_key")["value"]


def sukuk_coupons_ttm():
    """Kupon sukuk yang jatuh pada Okt 2025 - Sep 2026 menurut tabel fasilitas, dikonversi ke USD pada kurs rata-rata TTM."""
    fac = financing.load_facilities()
    fx = tr.inputs()["fx_ttm"]
    start, end = dt.date(2025, 10, 1), dt.date(2026, 9, 30)
    total = 0.0
    for r in fac.itertuples():
        q = r.annual_coupon_amount / 4.0
        for d in financing.cal.quarterly_dates(r.first_coupon_date, r.maturity_date):
            if start <= financing.cal.next_business_day(d) <= end:
                total += q
    return total / fx / 1e6


def _fx_series(paths, sid):
    p = paths[(paths.scenario_id == sid) & (paths.driver == "usdidr")].set_index("month")["value"]
    return p.reindex(MONTHS)


def monthly_effects(inp, paths, a_op, sid, case):
    """Selisih EBITDA bulanan terhadap TTM (bunker + translasi) dan selisih bunga mengambang per USD saldo pinjaman bank.
    Rata-rata 12 bulan pertama sama dengan scenario_effects pada modul transmisi."""
    p = paths[paths.scenario_id == sid]
    g = lambda d: p[p.driver == d].set_index("month")["value"].reindex(MONTHS)
    brent, fx, bi = g("brent"), g("usdidr"), g("bi_rate")
    d_brent_w = brent.iloc[:tr.WINDOW].mean() / inp["brent_ttm"] - 1
    eps, phi = tr.pick(a_op, "bunker_brent_elasticity", case, d_brent_w), tr.pick(a_op, "bunker_pass_through", case, d_brent_w)
    fc = tr.fuel_cost(inp, a_op, case, d_brent_w)
    d_bunker = -fc / 12 * eps * (brent / inp["brent_ttm"] - 1) * (1 - phi)
    theta = tr.pick(a_op, "idr_ebit_share", case, np.sign(fx.iloc[:tr.WINDOW].mean() - inp["fx_ttm"]))
    d_trans = theta * inp["ebit"] / 12 * (inp["fx_ttm"] / fx - 1)
    d_rate_w = float(bi.iloc[:tr.WINDOW].mean()) - BASE_RATE
    fs = tr.pick(a_op, "floating_debt_share", case, d_rate_w)
    d_rate = (bi - BASE_RATE) / 100 * fs / 12   # per USD pinjaman bank per bulan
    return (d_bunker + d_trans).rename("d_ebitda"), d_rate.rename("rate_per_usd"), fx


def program_profile(front_share):
    """Bobot pembayaran program kapal baru per bulan (13 bulan dari Nov 2026): porsi `front_share` pada enam bulan pertama."""
    w = np.zeros(len(MONTHS))
    i0 = MONTHS.index(PROGRAM_START)
    w[i0:i0 + FRONT_MONTHS] = front_share / FRONT_MONTHS
    w[i0 + FRONT_MONTHS:i0 + PROGRAM_MONTHS] = (1 - front_share) / (PROGRAM_MONTHS - FRONT_MONTHS)
    return w


@dataclass
class Stress:
    """Tekanan operasi tambahan: perubahan tarif angkut dan volume yang berlaku `months` bulan sejak Oktober 2026."""
    rate: float = 0.0
    volume: float = 0.0
    months: int = 24
    uplift: float = 0.0          # tambahan EBITDA per tahun (USD juta) sejak Januari 2028, mis. manfaat armada baru
    shift: float = 0.0           # pergeseran EBITDA per tahun (USD juta) selama `months` bulan sejak Oktober 2026, mis. replay siklus


@dataclass
class Financing:
    """Alternatif pendanaan (kasus utama tanpa refinancing): porsi pokok sukuk jatuh tempo yang diganti dengan sukuk tenor
    36 bulan dan porsi angsuran bank yang ditarik kembali."""
    sukuk_refi: float = 0.0
    bank_redraw: float = 0.0


@dataclass
class Mitigation:
    """Tindakan pengelolaan kas yang aktif setelah pemicu: kas akhir bulan (tanpa tindakan) turun di bawah `trigger` (USD juta),
    ditambah waktu tunggu masing-masing tuas. Penundaan belanja modal bersifat sementara: jumlah yang tertunda dibayar kembali
    setelah jendela penundaan, secara merata selama `catchup` bulan."""
    trigger: float = None
    capex_cut: float = 0.0
    dividend_cut: float = 0.0
    bank_redraw: float = 0.0
    lead_capex: int = 2
    lead_dividend: int = 3
    lead_bank: int = 6
    defer_months: int = 24
    catchup: int = 24


def run(sid, case, inp=None, paths=None, a_op=None, a=None, stress=None, fin=None, program=True, mit=None, macro=True):
    inp = inp or _init()
    paths = paths if paths is not None else macro.build_paths()
    a_op = a_op if a_op is not None else tr.assumptions()
    a = a if a is not None else assumptions()
    stress, fin = stress or Stress(), fin or Financing()
    d_ebitda, rate_pu, fx = monthly_effects(inp, paths, a_op, sid, case)
    if not macro:                # uji siklus murni: kurs hanya dipakai untuk konversi sukuk; tanpa efek bunker, translasi, dan bunga
        d_ebitda, rate_pu = d_ebitda * 0.0, rate_pu * 0.0
    idx = pd.Index(MONTHS, name="month")
    start = {"capex": None, "dividend": None, "bank": None}
    trig_month = None
    if mit is not None and mit.trigger is not None:
        base = run(sid, case, inp, paths, a_op, a, stress, fin, program, macro=macro)
        hit = [i for i, m in enumerate(MONTHS) if base["closing"].iloc[i] < mit.trigger]
        if hit:
            trig_month = MONTHS[hit[0]]
            start = {"capex": hit[0] + mit.lead_capex, "dividend": hit[0] + mit.lead_dividend, "bank": hit[0] + mit.lead_bank}
    df = pd.DataFrame(0.0, index=idx, columns=LINES)
    ebitda = inp["ebitda"] / 12 + d_ebitda
    if stress.rate or stress.volume:
        d = tr.rate_volume_grid(inp, a_op, [stress.rate], [stress.volume], case)[0].iloc[0]["d_ebitda"] / 12
        ebitda = ebitda + np.where(np.arange(len(MONTHS)) < stress.months, d, 0.0)
    if stress.uplift:
        ebitda = ebitda + np.where(np.array(MONTHS) >= "2028-01", stress.uplift / 12, 0.0)
    if stress.shift:
        ebitda = ebitda + np.where(np.arange(len(MONTHS)) < stress.months, stress.shift / 12, 0.0)
    df["ebitda"] = ebitda
    df["ocf"] = ebitda * pick(a, "ocf_conversion", case)
    # utang sukuk: jadwal kontraktual dalam IDR, dikonversi pada kurs bulan pembayaran menurut skenario
    ev = inp["events"].copy()
    ev["month"] = [d.strftime("%Y-%m") for d in ev["payment_date"]]
    for r in ev.itertuples():
        if r.month not in MONTHS:
            continue
        usd = r.amount / fx[r.month] / 1e6
        if r.event_type == "coupon":
            df.loc[r.month, "sukuk_coupon"] -= usd
        else:
            df.loc[r.month, "sukuk_principal"] -= usd
            if fin.sukuk_refi:
                df.loc[r.month, "refi_draw"] += usd * fin.sukuk_refi
                rate = pick(a, "refi_coupon", case)
                m0 = pd.Period(r.month, "M")
                for k in range(1, 37):
                    m = str(m0 + k)
                    if m not in MONTHS:
                        break
                    if k % 3 == 0:
                        df.loc[m, "refi_service"] -= r.amount * fin.sukuk_refi * rate / 4 / fx[m] / 1e6
                    if k == 36:
                        df.loc[m, "refi_service"] -= r.amount * fin.sukuk_refi / fx[m] / 1e6
    # bunga lain (bank dan sewa) = bunga dibayar TTM dikurangi kupon sukuk; kenaikan bunga mengikuti pinjaman bank berjalan
    other_interest = inp["interest_paid_ttm"] - inp["sukuk_coupon_ttm"]
    bank = inp["bank_debt"]
    amort = inp["bank_current"] / 12
    rows_bank = []
    for m in MONTHS:
        df.loc[m, "other_interest"] = -(other_interest / 12 + bank * rate_pu[m])
        rows_bank.append(bank)
        repay = min(amort, bank)
        df.loc[m, "bank_repay"] = -repay
        share = max(fin.bank_redraw, mit.bank_redraw if (mit is not None and start["bank"] is not None and len(rows_bank) - 1 >= start["bank"]) else 0.0)
        df.loc[m, "bank_redraw"] = repay * share
        bank = bank - repay + repay * share
    df["bank_balance"] = rows_bank
    df["lease"] = -pick(a, "lease_principal", case) / 12
    df["maintenance_capex"] = -pick(a, "maintenance_capex", case) / 12
    if mit is not None and mit.capex_cut and start["capex"] is not None:
        s0, s1 = start["capex"], start["capex"] + mit.defer_months
        w = np.arange(len(MONTHS))
        deferred = df["maintenance_capex"].where((w >= s0) & (w < s1), 0.0) * mit.capex_cut
        df["maintenance_capex"] = df["maintenance_capex"] - deferred
        back = np.where((w >= s1) & (w < s1 + mit.catchup), deferred.sum() / mit.catchup, 0.0)
        df["maintenance_capex"] = df["maintenance_capex"] + back
    if program:
        total = inp["program_idr"] / inp["fx_sep"] / 1e6 * (1 + pick(a, "program_cost_overrun", case))
        df["program_capex"] = -total * program_profile(pick(a, "program_front_share", case))
    roll = pick(a, "short_bank_rollover", case)
    df.loc["2027-09", "short_bank_repay"] = -inp["short_bank"] * (1 - roll)  # jatuh tempo dalam 12 bulan sejak 30 Sep 2026
    df["dividend"] = [-pick(a, "dividend_annual", case) if int(m[5:]) == DIVIDEND_MONTH else 0.0 for m in MONTHS]
    if mit is not None and mit.dividend_cut and start["dividend"] is not None:
        df["dividend"] = [d * (1 - mit.dividend_cut) if i >= start["dividend"] else d for i, d in enumerate(df["dividend"])]
    # kas, bunga atas kas, dan efek translasi (bukan arus kas)
    cash, rows = inp["opening_cash"], []
    idr_cash_idr = inp["idr_cash_usd"] * inp["fx_sep"]
    y = pick(a, "cash_yield", case) / 12
    prev_fx = inp["fx_sep"]
    for m in MONTHS:
        inc = cash * y
        df.loc[m, "interest_income"] = inc
        flows = df.loc[m, LINES].sum()
        trans = idr_cash_idr * (1 / fx[m] - 1 / prev_fx)
        df.loc[m, "fx_translation"] = trans
        out_only = df.loc[m, ["sukuk_coupon", "other_interest", "lease", "maintenance_capex", "program_capex", "bank_repay",
                              "short_bank_repay", "dividend", "sukuk_principal", "refi_service"]].sum()
        df.loc[m, "opening"] = cash
        df.loc[m, "floor_intramonth"] = cash + out_only   # uji urutan konservatif: pengeluaran bulan itu sebelum penerimaan
        cash = cash + flows + trans
        df.loc[m, "closing"] = cash
        prev_fx = fx[m]
    df["net_flow"] = df["closing"] - df["opening"] - df["fx_translation"]
    df["reserve"] = inp["deposits"] * pick(a, "deposit_availability", case)
    df["liquidity"] = df["closing"] + df["reserve"]
    df["fx"] = fx
    df.attrs["trigger_month"] = trig_month
    df.attrs["start"] = {k: (MONTHS[v] if v is not None and v < len(MONTHS) else None) for k, v in start.items()}
    return df


def min_cash(inp, a, case):
    return pick(a, "min_cash_months", case) * inp["opex_month"]


def summarize(df, threshold):
    c = df["closing"]
    below = df.index[c < threshold]
    lq = df["liquidity"]
    lb = df.index[lq < threshold]
    return {"min_cash": float(c.min()), "min_month": c.idxmin(), "end_cash": float(c.iloc[-1]),
            "first_below": below[0] if len(below) else None, "months_below": int(len(below)),
            "min_liquidity": float(lq.min()), "liq_month": lq.idxmin(), "first_below_liq": lb[0] if len(lb) else None,
            "min_floor_intramonth": float(df["floor_intramonth"].min()), "floor_month": df["floor_intramonth"].idxmin(),
            "cum_net_flow": float(df["net_flow"].sum())}


_INP = None


def _init():
    global _INP
    if _INP is None:
        _INP = inputs()
    return _INP


# --- uji balik dan tampilan --------------------------------------------------------------------------------------
NAMES, ORDER = tr.NAMES, tr.ORDER
GROUPS = {"Kas operasi sebelum bunga": ["ocf"], "Bunga dan imbal hasil, neto": ["interest_income", "sukuk_coupon", "other_interest", "refi_service"],
          "Pokok sewa": ["lease"], "Belanja modal pemeliharaan": ["maintenance_capex"], "Program kapal baru": ["program_capex"],
          "Angsuran bank, neto": ["bank_repay", "short_bank_repay", "bank_redraw"], "Pelunasan sukuk, neto": ["sukuk_principal", "refi_draw"],
          "Dividen": ["dividend"]}


LABELS = {"ocf_conversion": "Konversi EBITDA ke kas operasi", "maintenance_capex": "Belanja modal pemeliharaan", "lease_principal": "Pokok sewa kapal",
          "program_cost_overrun": "Kelebihan biaya program kapal baru", "program_front_share": "Termin program condong awal", "cash_yield": "Imbal hasil atas kas",
          "short_bank_rollover": "Pinjaman jangka pendek tidak diperpanjang", "deposit_availability": "Deposito entitas anak tidak dapat ditarik",
          "refi_coupon": "Imbalan sukuk pengganti"}


def _gap(df, threshold, metric):
    return float((df["closing" if metric == "cash" else "liquidity"] - threshold).min())


def solve(fn, lo, hi, tol=1e-4):
    """Akar monoton `fn(x) = 0` pada [lo, hi] dengan bagi dua; None bila tidak ada tanda yang berbeda."""
    flo, fhi = fn(lo), fn(hi)
    if flo * fhi > 0:
        return None
    for _ in range(60):
        mid = (lo + hi) / 2
        fm = fn(mid)
        if abs(fm) < tol or (hi - lo) < 1e-7:
            return mid
        if flo * fm <= 0:
            hi, fhi = mid, fm
        else:
            lo, flo = mid, fm
    return (lo + hi) / 2


def breakeven_rate_cash(sid, case, threshold, months=24, metric="liquidity", **kw):
    """Perubahan tarif angkut (volume tetap) yang membuat saldo minimum `metric` sama dengan batas kas."""
    return solve(lambda g: _gap(run(sid, case, stress=Stress(rate=g, months=months), **kw), threshold, metric), -0.9, 0.2)


def required_uplift(sid, case, threshold, metric="liquidity", **kw):
    """Tambahan EBITDA tahunan sejak 2028 agar saldo minimum `metric` tidak di bawah batas kas (0 bila sudah terpenuhi)."""
    if _gap(run(sid, case, **kw), threshold, metric) >= 0:
        return 0.0
    return solve(lambda u: _gap(run(sid, case, stress=Stress(uplift=u), **kw), threshold, metric), 0.0, 400.0)


@dataclass
class CashView:
    inp: dict
    threshold: float
    paths: dict          # kunci (nama skenario, kasus) -> DataFrame bulanan
    scen: pd.DataFrame
    uses: pd.DataFrame   # sumber dan penggunaan kas kumulatif menurut kelompok, kasus dasar tengah
    tornado: pd.DataFrame
    fin: pd.DataFrame
    intramonth: pd.DataFrame
    reverse: pd.DataFrame
    sens_min: pd.DataFrame
    assumptions: pd.DataFrame
    cov_breakeven: float         # perubahan tarif impas uji covenant FY2027 (volume tetap), dari modul transmisi


def build_view():
    inp, a, a_op, paths = _init(), assumptions(), tr.assumptions(), macro.build_paths()
    th = min_cash(inp, a, "central")
    runs, rows = {}, []
    for sid, nm in NAMES.items():
        for case in ("central", "adverse"):
            df = run(sid, case, inp, paths, a_op, a)
            runs[(nm, case)] = df
            r = summarize(df, th)
            r.update(scenario=nm, case=case)
            rows.append(r)
    scen = pd.DataFrame(rows)
    base = runs[("Dasar", "central")]
    uses = pd.Series({k: base[v].sum().sum() for k, v in GROUPS.items()})
    uses["Selisih translasi kurs (non-kas)"] = base["fx_translation"].sum()
    # tornado: satu parameter pada sisi merugikan, lainnya tengah, skenario Dasar
    ref = summarize(base, th)
    trows = []
    for prm in ["ocf_conversion", "maintenance_capex", "lease_principal", "program_cost_overrun", "program_front_share", "cash_yield",
                "short_bank_rollover", "deposit_availability", "refi_coupon"]:
        am = a.copy()
        am.loc[prm, "central"] = pick(a, prm, "adverse")
        s = summarize(run("MS-BASE", "central", inp, paths, a_op, am), th)
        trows.append({"parameter": prm, "central": float(a.loc[prm, "central"]), "adverse": pick(a, prm, "adverse"),
                      "d_end_cash": s["end_cash"] - ref["end_cash"], "d_min_liq": s["min_liquidity"] - ref["min_liquidity"]})
    tor = pd.DataFrame(trows)
    tor["label"] = tor["parameter"].map(LABELS)
    # alternatif pendanaan pada skenario Dasar dan Gabungan, kasus merugikan
    frows = []
    for sid in ("MS-BASE", "MS-COMBINED"):
        for case in ("central", "adverse"):
            for label, fin in (("Tanpa refinancing", Financing()), ("Pinjaman bank bergulir", Financing(bank_redraw=1.0)),
                               ("Seri jatuh tempo diganti 50%", Financing(sukuk_refi=0.5)), ("Seri jatuh tempo diganti 100%", Financing(sukuk_refi=1.0)),
                               ("Bank bergulir dan sukuk diganti 100%", Financing(sukuk_refi=1.0, bank_redraw=1.0))):
                s = summarize(run(sid, case, inp, paths, a_op, a, fin=fin), th)
                frows.append({"scenario": NAMES[sid], "case": case, "alternatif": label, "min_cash": s["min_cash"], "min_liquidity": s["min_liquidity"],
                              "end_cash": s["end_cash"], "first_below_liq": s["first_below_liq"]})
    finv = pd.DataFrame(frows)
    # uji urutan intrabulan pada bulan pelunasan sukuk
    bullets = ["2028-08", "2029-05", "2030-07"]
    irows = []
    for case in ("central", "adverse"):
        df = runs[("Dasar", case)]
        for m in bullets:
            r = df.loc[m]
            irows.append({"case": case, "month": m, "opening": r["opening"], "outflow": r["floor_intramonth"] - r["opening"], "floor": r["floor_intramonth"],
                          "floor_liq": r["floor_intramonth"] + r["reserve"], "closing": r["closing"]})
    # uji balik: tarif yang menghabiskan batas kas, dan manfaat EBITDA yang diperlukan
    rrows = []
    for sid in ("MS-BASE", "MS-COMBINED"):
        for case in ("central", "adverse"):
            for months in (12, 24):
                for metric in ("cash", "liquidity"):
                    be = breakeven_rate_cash(sid, case, th, months, metric, inp=inp, paths=paths, a_op=a_op, a=a)
                    rrows.append({"scenario": NAMES[sid], "case": case, "months": months, "metric": metric, "rate": be})
    rev = pd.DataFrame(rrows)
    up = []
    for sid in ("MS-BASE", "MS-COMBINED"):
        for case in ("central", "adverse"):
            for metric in ("cash", "liquidity"):
                up.append({"scenario": NAMES[sid], "case": case, "metric": metric, "uplift": required_uplift(sid, case, th, metric, inp=inp, paths=paths, a_op=a_op, a=a)})
    rev2 = pd.DataFrame(up)
    sm = []
    for mm in (0.5, 1.0, 2.0):
        t = mm * inp["opex_month"]
        for (nm, case), df in runs.items():
            if nm in ("Dasar", "Gabungan"):
                s = summarize(df, t)
                sm.append({"months": mm, "threshold": t, "scenario": nm, "case": case, "first_below": s["first_below"], "first_below_liq": s["first_below_liq"]})
    disp = a[["description", "low", "central", "high", "status"]].copy()
    grid, den = tr.rate_volume_grid(inp, a_op, [0.0], [0.0])
    cov = tr.breakeven_rate(inp, den, 0.0, a_op)
    return CashView(inp, th, runs, scen, uses, tor, finv, pd.DataFrame(irows), (rev, rev2), pd.DataFrame(sm), disp, cov)


# --- tabel untuk notebook ----------------------------------------------------------------------------------------
_BLN = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]


def ym(m, none="tidak tertembus"):
    return none if m is None or (isinstance(m, float) and np.isnan(m)) else f"{_BLN[int(m[5:]) - 1]} {m[:4]}"


def first_negative(df, col="closing"):
    n = df.index[df[col] < 0]
    return n[0] if len(n) else None


def annual_table(df):
    """Arus kas tahunan menurut kelompok dan saldo akhir tahun (USD juta)."""
    y = df.index.str[:4]
    t = pd.DataFrame({k: df[v].sum(axis=1).groupby(y).sum() for k, v in GROUPS.items()})
    t["Selisih translasi (non-kas)"] = df["fx_translation"].groupby(y).sum()
    t["Kas akhir tahun"] = df["closing"].groupby(y).last()
    t["Kas + deposito akhir tahun"] = df["liquidity"].groupby(y).last()
    t.index.name = None
    return t.rename(columns=lambda c: c.replace(", neto", ""))


def scenario_table(v):
    s = v.scen.copy()
    out = pd.DataFrame({
        "Parameter": s["case"].map({"central": "tengah", "adverse": "merugikan"}),
        "Kas minimum": s["min_cash"], "Kas di bawah batas sejak": s["first_below"].map(ym),
        "Kas + deposito minimum": s["min_liquidity"], "Kas + deposito di bawah batas sejak": s["first_below_liq"].map(ym),
        "Kas akhir 2031": s["end_cash"]})
    out.index = pd.MultiIndex.from_arrays([s["scenario"], out.pop("Parameter")])
    return out.loc[[(n, c) for n in ORDER for c in ("tengah", "merugikan")]]


def fin_table(v, scenario="Dasar"):
    f = v.fin[v.fin.scenario == scenario]
    t = f.pivot_table(index="alternatif", columns="case", values=["min_cash", "min_liquidity"], sort=False)
    t.columns = [f"{'Kas minimum' if a == 'min_cash' else 'Kas + deposito minimum'}, {'tengah' if b == 'central' else 'merugikan'}" for a, b in t.columns]
    return t[[c for c in ("Kas minimum, tengah", "Kas minimum, merugikan", "Kas + deposito minimum, tengah", "Kas + deposito minimum, merugikan") if c in t]]


def intramonth_table(v):
    t = v.intramonth.copy()
    t["Parameter"] = t["case"].map({"central": "tengah", "adverse": "merugikan"})
    t["Bulan"] = t["month"].map(ym)
    t = t.rename(columns={"opening": "Kas awal bulan", "outflow": "Seluruh pengeluaran bulan itu", "floor": "Kas terendah (tanpa penerimaan)",
                          "floor_liq": "Kas + deposito terendah", "closing": "Kas akhir bulan"})
    return t.set_index(["Parameter", "Bulan"])[["Kas awal bulan", "Seluruh pengeluaran bulan itu", "Kas terendah (tanpa penerimaan)", "Kas + deposito terendah", "Kas akhir bulan"]]


def reverse_table(v):
    r = v.reverse[0]
    r = r[r.case == "central"].copy()
    r["Ukuran"] = r["metric"].map({"cash": "Kas", "liquidity": "Kas + deposito"})
    t = r.pivot_table(index=["scenario", "Ukuran"], columns="months", values="rate", sort=False) * 100
    t.columns = [f"Tarif turun {m} bulan (%)" for m in t.columns]
    t.index.names = [None, None]
    return t


def uplift_table(v):
    u = v.reverse[1].copy()
    u["Ukuran"] = u["metric"].map({"cash": "Kas", "liquidity": "Kas + deposito"})
    u["Parameter"] = u["case"].map({"central": "tengah", "adverse": "merugikan"})
    t = u.pivot_table(index=["scenario", "Parameter"], columns="Ukuran", values="uplift", sort=False)
    t.index.names = [None, None]
    return t.rename(columns=lambda c: f"{c}: tambahan EBITDA per tahun")


def sens_table(v):
    s = v.sens_min.copy()
    s["Batas"] = s.apply(lambda r: f"{r['months']:.1f} bulan (USD {r['threshold']:.0f} juta)".replace(".", ","), axis=1)
    s["Skenario"] = s["scenario"] + ", " + s["case"].map({"central": "tengah", "adverse": "merugikan"})
    s["Kas"] = s["first_below"].map(ym)
    s["Kas + deposito"] = s["first_below_liq"].map(ym)
    return s.set_index(["Batas", "Skenario"])[["Kas", "Kas + deposito"]]


def assumption_table(v):
    t = v.assumptions.copy()
    pct = ["ocf_conversion", "program_cost_overrun", "program_front_share", "cash_yield", "short_bank_rollover", "refi_coupon", "deposit_availability"]
    t.loc[pct, ["low", "central", "high"]] = t.loc[pct, ["low", "central", "high"]] * 100
    t.loc[pct, "description"] = t.loc[pct, "description"] + " (%)"
    t.columns = ["Parameter", "Rendah", "Tengah", "Merugikan (batas)", "Status"]
    t["Status"] = t["Status"].map({"assumed": "asumsi", "proposed": "usulan"})
    return t.set_index("Parameter")
