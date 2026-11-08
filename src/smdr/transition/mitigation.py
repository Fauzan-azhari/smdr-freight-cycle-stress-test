"""Tuas mitigasi kas, pemicu, dan lampu pemantauan.

Tuas aktif setelah pemicu (kas akhir bulan tanpa tindakan di bawah dua bulan biaya operasi tunai) ditambah waktu tunggu
masing-masing. Jabatan pemilik, persetujuan, waktu tunggu, dan kapasitas adalah usulan yang belum dikonfirmasi perusahaan.
Penyesuaian sewa tidak dihitung karena manfaat bersihnya bergantung pada margin kapal sewa yang belum tersedia.
"""
import os
from dataclasses import dataclass

import pandas as pd

from . import cashflow as cf
from . import cycle as cy
from . import macro
from .. import datapaths
from . import transmission as tr

REGISTER = datapaths.table("mitigations.csv")
LEVERS = {"Tunda belanja modal 30%": dict(capex_cut=0.30), "Hapus dividen": dict(dividend_cut=1.0), "Bank bergulir": dict(bank_redraw=1.0),
          "Ketiga tuas bersama": dict(capex_cut=0.30, dividend_cut=1.0, bank_redraw=1.0)}


def register():
    return pd.read_csv(REGISTER)


@dataclass
class MitigationView:
    register: pd.DataFrame
    impact: pd.DataFrame      # skenario merugikan x tuas
    timing: pd.DataFrame      # pemicu lebih awal atau lebih lambat, ketiga tuas
    paths: dict               # (skenario, 'tanpa'|'dengan') -> DataFrame
    lamps: pd.DataFrame
    trigger: float
    threshold: float


def build_view(cv=None, tv=None):
    cv = cv or cf.build_view()
    tv = tv or tr.build_view()
    inp, a, a_op, paths = cv.inp, cf.assumptions(), tr.assumptions(), macro.build_paths()
    th, month = cv.threshold, cv.inp["opex_month"]
    trig = 2 * month
    rows, pth = [], {}
    for sid in ("MS-BASE", "MS-COMBINED"):
        nm = cf.NAMES[sid]
        none = cf.run(sid, "adverse", inp, paths, a_op, a)
        pth[(nm, "tanpa")] = none
        for label, kw in [("Tanpa tindakan", {})] + list(LEVERS.items()):
            df = none if not kw else cf.run(sid, "adverse", inp, paths, a_op, a, mit=cf.Mitigation(trig, **kw))
            if kw and label == "Ketiga tuas bersama":
                pth[(nm, "dengan")] = df
            s = cf.summarize(df, th)
            rows.append({"scenario": nm, "tuas": label, "min_cash": s["min_cash"], "min_liquidity": s["min_liquidity"], "end_cash": s["end_cash"],
                         "first_below_liq": s["first_below_liq"], "trigger_month": df.attrs.get("trigger_month")})
    impact = pd.DataFrame(rows)
    trows = []
    for k in (1.0, 1.5, 2.0, 3.0):
        df = cf.run("MS-BASE", "adverse", inp, paths, a_op, a, mit=cf.Mitigation(k * month, **LEVERS["Ketiga tuas bersama"]))
        s = cf.summarize(df, th)
        trows.append({"months": k, "trigger": k * month, "trigger_month": df.attrs.get("trigger_month"), "min_cash": s["min_cash"],
                      "min_liquidity": s["min_liquidity"], "first_below_liq": s["first_below_liq"]})
    den = cy.test_denominators(inp, paths)             # threshold tarif mengikuti uji covenant terketat (FY2028), bukan FY2027
    be = min(abs(tr.breakeven_rate(inp, d, 0.0, a_op)) for d in den["penyebut"]) * 100
    lamps = pd.DataFrame([
        ("Tarif angkut terhadap TTM", f"turun {be * 0.5:.1f}% (separuh headroom uji terketat)".replace(".", ","), f"turun {be * 0.8:.1f}% (80% headroom uji terketat)".replace(".", ",")),
        ("Cover pro forma uji berikutnya", "di bawah 1,21x (ruang di bawah 10%)", "di bawah 1,16x (ruang di bawah 5%)"),
        ("Kas akhir bulan", f"di bawah USD {2 * month:.0f} juta (2 bulan biaya operasi)", f"di bawah USD {month:.0f} juta (1 bulan)"),
        ("Jarak ke pelunasan sukuk", "12 bulan sebelum, bila kas + deposito kurang dari pokok + 2 bulan biaya operasi", "6 bulan sebelum, dengan syarat yang sama"),
    ], columns=["Ukuran", "Kuning (siaga)", "Merah (bertindak)"]).set_index("Ukuran")
    return MitigationView(register(), impact, pd.DataFrame(trows), pth, lamps, trig, th)


# --- tabel untuk notebook ----------------------------------------------------------------------------------------

def register_table(v):
    r = v.register.copy()
    r["status"] = r["availability_status"].map({"assumed": "usulan", "data_needed": "perlu data"})
    r = r.rename(columns={"tuas": "Tuas", "trigger_metric": "Pemicu", "owner": "Pemilik (usulan)", "approval_role": "Persetujuan", "lead_time_months": "Waktu tunggu (bulan)",
                          "cash_cost": "Biaya dan risiko", "benefit_rule": "Manfaat", "capacity_limit": "Kapasitas", "status": "Status"})
    return r.set_index("Tuas")[["Pemicu", "Pemilik (usulan)", "Persetujuan", "Waktu tunggu (bulan)", "Manfaat", "Biaya dan risiko", "Kapasitas", "Status"]]


def impact_table(v):
    t = v.impact.copy()
    t["Likuiditas di bawah batas sejak"] = t["first_below_liq"].map(cf.ym)
    t = t.rename(columns={"min_cash": "Kas minimum", "min_liquidity": "Kas + deposito minimum", "end_cash": "Kas akhir 2031", "scenario": "Skenario", "tuas": "Tuas"})
    return t.set_index(["Skenario", "Tuas"])[["Kas minimum", "Kas + deposito minimum", "Kas akhir 2031", "Likuiditas di bawah batas sejak"]]


def timing_table(v):
    t = v.timing.copy()
    t["Pemicu"] = t.apply(lambda r: f"{r['months']:.1f} bulan biaya operasi (USD {r['trigger']:.0f} juta)".replace(".", ","), axis=1)
    t["Pemicu tercapai"] = t["trigger_month"].map(lambda m: cf.ym(m, none="tidak tercapai"))
    t = t.rename(columns={"min_cash": "Kas minimum", "min_liquidity": "Kas + deposito minimum"})
    return t.set_index("Pemicu")[["Pemicu tercapai", "Kas minimum", "Kas + deposito minimum"]]
