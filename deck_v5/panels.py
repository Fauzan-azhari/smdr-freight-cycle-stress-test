"""Panel kelima slide (versi 2): satu pertanyaan per slide, label teknis Inggris konsisten, legend selalu di bawah."""
import datetime as dt
import math
import textwrap

import numpy as np
import pandas as pd
from matplotlib.patches import Rectangle

from theme import *  # noqa: F401,F403

BAND_R, BAND_Y = "#FBD9DA", "#FEEFC4"
MACRO_EN = {"Dasar": "Base Case", "Normalisasi cepat": "Rapid Normalization", "Energi bertahan": "Prolonged Energy", "Tekanan kurs": "FX Pressure", "Gabungan": "Combined"}
MACRO_USED = ("Dasar", "Energi bertahan", "Gabungan")   # skenario biaya yang dipakai di seluruh deck (slide 3 dan 5)
MARKET_EN = {"Permintaan melemah": "Demand Slowdown", "Kelebihan kapasitas": "Overcapacity", "Rute kembali normal": "Route Normalization",
             "Permintaan lemah dan kelebihan kapasitas": "Weak Demand + Overcapacity"}
RISK_EN = {"ER1": "Middle East Maritime Security", "ER2": "Suez Route Normalization", "ER3": "Fleet Overcapacity", "ER4": "Trade Fragmentation",
           "ER5": "IMO Emission Regulation", "ER6": "Domestic Fuel Supply", "ER7": "Extreme Weather", "ER8": "Cyber Disruption"}
MON = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]


def nhead(bg, x, w, y, s, num, size=10.5):
    """Judul panel bernomor (jalur baca 1-2-3): lencana kuning berangka, judul serif tebal, garis bawah selebar panel."""
    bg.add_patch(Rectangle((x, y - 0.12), 0.24, 0.24, fc=KUNING, ec="none"))
    txt(bg, x + 0.12, y, str(num), 9, INK, "bold", ha="center")
    txt(bg, x + 0.34, y, s, size + 1, INK, "bold", fontfamily=SERIF)
    hline(bg, x, x + w, y + 0.24)


def head(bg, x, w, y, s, lines=1, size=11):
    return panel_title(bg, x, w, y, s, lines=lines, size=size)


def leg(fig, bg, x, y, items, size=8, gap=0.25):
    return legend(bg, x, y, items, size=size, gap=gap, fig=fig)


def cap(bg, x, y, s, ha="left"):
    txt(bg, x, y, s, 8, ABU_D, ha=ha)


# ================ Pembantu data: jalur kuartalan, label bulan, hasil model ===
MK_WEAK, MK_OVER, MK_DEM = "Permintaan lemah dan kelebihan kapasitas", "Kelebihan kapasitas", "Permintaan melemah"


EW = 2.45   # early warning: di antara skenario yang tidak (<= 2,42x) dan yang akan (>= 2,50x) melewati 3,00x pada data Mar 2027, dibulatkan ke bawah
RUANG = 1.10   # ruang 10% di bawah batas covenant
ND_SASARAN = round(math.floor(3.0 / RUANG / 0.05) * 0.05, 2)   # sasaran pelunasan Net Debt to EBITDA: 3,00 / 1,10 dibulatkan ke bawah (2,70x)
DSCR_ALERT = round(1.10 * RUANG, 2)                            # Alert DSCR: 10% di atas batas 1,10x (1,21x)
assert ND_SASARAN == 2.7, "pelunasan_ke_2_7x di robustness.py dihitung terhadap 2,70x"


def qpeak(D, case="central", col="nd"):
    """Rasio terburuk per skenario atas pengukuran kuartalan Des 2026 - Des 2028 (EBITDA 12 bulan terakhir)."""
    q = D["v7"]["q"]; q = q[q.case == case]
    return q.groupby("skenario")[col].max() if col == "nd" else q.groupby("skenario")[col].min()


def qfirst(D, th=3.0, case="central"):
    """Akhir kuartal pertama rasio melewati `th` pada skenario mana pun (YYYY-MM)."""
    q = D["v7"]["q"]; q = q[(q.case == case) & (q.nd > th)]
    return q["quarter"].min()


def ym_label(ym):
    return f"{MON[int(ym[5:]) - 1]} {ym[:4]}"


def v7(D, case="central"):
    """Hasil konsisten (robustness.consistent_results) per skenario untuk satu kasus parameter."""
    r = D["v7"]["res"]
    return r[r.case == case].set_index("skenario")


def ebitda_pcts(D):
    """Dampak EBITDA (% TTM): pasar = tiga skenario terkalibrasi, biaya = lima skenario makro; tengah dan merugikan."""
    eb = D["inp_ebitda"]
    rs = D["results"][D["results"].kisah.isin(MARKET_EN) & (D["results"].kisah != "Rute kembali normal")]
    mkt = (rs["d_ebitda"].abs() / eb * 100)
    ms = D["macro_scen"].set_index(["scenario", "case"])["d_ebitda"]
    mac = [abs(ms[(n, c)]) / eb * 100 for n in MACRO_USED for c in ("central", "adverse")]
    return float(mkt.min()), float(mkt.max()), float(min(mac)), float(max(mac))


# ================ Risk: dampak EBITDA per skenario ===
# urutan baris Market Channel di kiri mengikuti urutan dampak skenario di kanan
ORDER = {"ER1": 1, "ER3": 2, "ER4": 3, "ER2": 4}
DRIVER = {"Prolonged Energy": "Middle East Maritime Security", "Overcapacity": "Fleet Overcapacity", "Demand Slowdown": "Trade Fragmentation",
          "Route Normalization": "Suez Route Normalization", "Weak Demand + Overcapacity": "Fleet Overcapacity +\nTrade Fragmentation"}


BASIS = {"Combined": "Energy + kurs p75 + BI Rate +50 bps", "Prolonged Energy": "Brent USD 125 (Okt) ditahan 9 bln", "FX Pressure": "Rupiah \u22126,9% (persentil 90, 6 bln)",
         "Base Case": "Proyeksi OCE Bank Mandiri", "Rapid Normalization": "Brent turun mengikuti pola 2022",
         "Weak Demand + Overcapacity": "Tarif \u221212%, volume \u22125%, 24 bln", "Overcapacity": "Tarif \u221212%, 24 bln (efektif FY2024)",
         "Demand Slowdown": "Tarif \u22126%, volume \u22125%, 12 bln (hub FY2023)"}


def s2_how_much(fig, bg, D, x, y, w, h):
    """Kanan: SEBERAPA BESAR. Delapan skenario terkalibrasi menurut jalur, dengan dasar besaran tiap skenario."""
    EXT = "#D5D6D8"
    eb = D["inp_ebitda"]
    ms = D["macro_scen"].set_index(["scenario", "case"])["d_ebitda"]
    res = D["results"].set_index(["kisah", "case"])["d_ebitda"]
    macro = sorted([(MACRO_EN[n], abs(ms[(n, "central")]), abs(ms[(n, "adverse")])) for n in MACRO_USED], key=lambda r: -r[2])
    market = sorted([(MARKET_EN[n], abs(res[(n, "central")]), abs(res[(n, "adverse")])) for n in MARKET_EN if n != "Rute kembali normal"], key=lambda r: -r[2])
    m0, m1, c0, c1 = ebitda_pcts(D)
    head(bg, x, w, y, f"Skenario pasar menggerus EBITDA {idn(m0, 0)}\u2013{idn(m1, 0)}%, skenario biaya {idn(c0, 0)}\u2013{idn(c1, 0)}%", size=11)
    bx0, bw, vmax, xd = x + 1.95, 1.4, 44.0, x + 3.95
    px = lambda v: bx0 + v / vmax * bw
    yh = y + 0.42
    txt(bg, x, yh, "Skenario", 7.8, ABU_D, "bold"); txt(bg, bx0, yh, f"% EBITDA TTM (USD {idn(eb, 0)} juta)", 7.8, ABU_D, "bold"); txt(bg, xd, yh, "Definisi dan dasar besaran", 7.8, ABU_D, "bold")
    yy = yh + 0.2
    ytop = yy
    mw = max(r[2] for r in macro) / eb * 100
    sv = D["v7"]["sev"]
    sev = [("Brent persentil 90 (+%s%%)" % idn(sv["brent_p90"] * 100, 0), abs(sv["d_brent"]), abs(sv["d_brent_adverse"])),
           ("Kurs persentil 90 (+%s%%)" % idn(sv["fx_p90"] * 100, 0), abs(sv["d_fx"]), abs(sv["d_fx_adverse"])),
           ("Tarif FY2024 (\u221212%, terjadi)", abs(sv["d_rate"]), abs(sv["d_rate"]))]
    BASIS.update({sev[0][0]: "FRED 1988\u20132026, perubahan 12 bulan", sev[1][0]: "FRED/OECD 2000\u20132026", sev[2][0]: "Tarif efektif SMDR aktual"})
    for gname, rows, col in (("Macro Shock (Cost)", macro, ABU_D), ("Market Shock (Freight Rate & Volume)", market, KUNING), ("Pembanding guncangan historis", sev, ABU)):
        hline(bg, x, x + w, yy + 0.02, ABU, 0.8)
        txt(bg, x, yy + 0.15, gname, 8.6, INK, "bold")
        if col == KUNING:
            ymk = yy + 0.02
            txt(bg, px(mw) + 0.08, yy + 0.15, f"Macro Shock terburuk: {idn(mw, 0)}%", 7.6, ABU_D)
        yy += 0.25
        for nm, c, a in rows:
            txt(bg, x + 0.15, yy + 0.125, nm, 8.4, INK)
            pc_, pa = c / eb * 100, a / eb * 100
            bg.add_patch(Rectangle((bx0, yy + 0.045), px(pc_) - bx0, 0.16, fc=col, ec="none", zorder=3))
            if pa - pc_ >= 0.3:
                bg.add_patch(Rectangle((px(pc_), yy + 0.045), px(pa) - px(pc_), 0.16, fc=EXT, ec="none", zorder=3))
            txt(bg, px(pa) + 0.08, yy + 0.125, f"{idn(pc_, 0)}\u2013{idn(pa, 0)}%" if pa - pc_ >= 0.5 else f"{idn(pc_, 0)}%", 8.6, INK, "bold")
            txt(bg, xd, yy + 0.125, BASIS[nm], 7.8, ABU_D)
            yy += 0.225
        if col == KUNING:
            ymk_end = yy
    for t_ in (10, 20, 30, 40):
        bg.plot([px(t_), px(t_)], [ytop + 0.22, yy], color=GRID, lw=0.8, zorder=1)
    bg.plot([px(mw)] * 2, [ymk, ymk_end], color=ABU_D, lw=0.9, ls=(0, (4, 2.5)), zorder=2)
    bg.plot([bx0, px(40)], [yy + 0.02, yy + 0.02], color=ABU_D, lw=0.8, zorder=2)
    for t_ in (0, 10, 20, 30, 40):
        bg.plot([px(t_)] * 2, [yy + 0.02, yy + 0.06], color=ABU_D, lw=0.8, zorder=2)
        txt(bg, px(t_), yy + 0.17, f"{t_}%", 7.6, ABU_D, ha="center")
    txt(bg, px(40) + 0.3, yy + 0.17, "penurunan EBITDA TTM", 7.6, ABU_D)
    leg(fig, bg, x, yy + 0.4, [("box", ABU_D, "batang: asumsi tengah"), ("box", EXT, "sambungan: sampai asumsi adverse")], size=8, gap=0.2)



# ================ Scenario: tarif yang pernah dialami SMDR ===
def s3_reported(fig, bg, D, x, y, w, h):
    head(bg, x, w, y, "Penurunan tarif 6\u201312% yang diuji pernah dialami SMDR", lines=1, size=10.5)
    lab = {("FY2023", "international"): "Rute internasional FY2023", ("FY2023", "jakarta_hub"): "Hub Jakarta FY2023", ("FY2023", "surabaya_hub"): "Hub Surabaya FY2023",
           ("FY2024", "jakarta_hub"): "Hub Jakarta FY2024", ("FY2024", "surabaya_hub"): "Hub Surabaya FY2024"}
    rep = D["reported"][D["reported"]["jenis"] == "tarif"]
    rp = [(lab[(r.periode, r.cakupan)], r.perubahan, ABU_D) for r in rep.itertuples() if (r.periode, r.cakupan) == ("FY2023", "surabaya_hub")]
    assert len(rp) == 1
    ef = sorted([(f"Tarif efektif {p}", r["tarif_efektif"] * 100, KUNING) for p, r in D["realized"].iterrows()], key=lambda t: t[1])
    items = ef + rp
    ys = list(range(len(ef))) + [len(ef) + 0.8 + i for i in range(len(rp))]
    den = D["den"]; lo, hi = den.loc["FY2027", "titik_impas_tarif"] * 100, den.loc["FY2028", "titik_impas_tarif"] * 100
    cx, cy, cw, ch = x, y + 0.6, w, h - 1.3
    AW = cw - 1.9 - 1.75
    ax = ax_in(fig, cx + 1.85, cy, AW, ch)
    ax.axvspan(-12, -6, color=BAND_Y, zorder=0)
    for i, (nm, v, c) in zip(ys, items):
        ax.plot([0, v], [i, i], color=c, lw=2.6, solid_capstyle="round", zorder=2); ax.plot([v], [i], "o", ms=8.5, color=c, mec=INK, mew=0.6, zorder=3)
        ax.text(v + (2 if v >= 0 else -2.2), i, idn(v, 0) + "%", ha="left" if v >= 0 else "right", va="center", fontsize=8.8, color=INK, fontweight="bold", zorder=6, bbox=dict(fc="white", ec="none", pad=0.6))
    ax.axvline(0, color=ABU_D, lw=0.9)
    ax.axhline(len(ef) - 0.1, color=GRID, lw=0.8, zorder=0)
    ax.text(-69, len(ef) + 0.25, "Tarif hub SMDR (laporan tahunan)", fontsize=7.6, color=ABU_D, ha="left", va="center", bbox=dict(fc="white", ec="none", pad=0.5), zorder=6)
    ax.set_yticks(ys); ax.set_yticklabels([i[0] for i in items])
    ax.set_xlim(-70, 22); ax.set_ylim(ys[-1] + 0.6, -1.35); ax.set_xticks([-40, -20, 0, 20]); ax.set_xticklabels(["−40%", "−20%", "0%", "+20%"])
    style_axes(ax); ax.tick_params(axis="y", labelsize=8.6, colors=INK, pad=4)
    for t in (-40, -20, 20):
        ax.axvline(t, color=GRID, lw=0.8, zorder=0)
    ndr = abs(D["nd"]["rate"]) * 100
    ax.axvline(-ndr, color=INK, lw=0.9, ls=(0, (4, 2.5)), zorder=1.5)
    ax.text(-ndr - 0.8, len(ef) - 0.45, f"Batas Net Debt\nto EBITDA \u2212{idn(ndr, 1)}%", fontsize=7.8, color=INK, ha="right", va="center", linespacing=1.05, fontweight="bold", zorder=6, bbox=dict(fc="white", ec="none", pad=0.8))
    ax.text(-13, -0.75, "Skenario uji\n−6% s.d. −12%", fontsize=7.8, color=INK, ha="right", va="center", linespacing=1.1)
    anchors = {"Tarif efektif FY2024": "\u2190 dasar skenario Overcapacity\n   dan Weak Demand + Overcapacity", "Hub Surabaya FY2023": "\u2190 dasar skenario Demand Slowdown"}
    ypx = lambda v: cy + (v - (-1.35)) / ((ys[-1] + 0.6) - (-1.35)) * ch
    for (nm, v, c), yv in zip(items, ys):
        if nm in anchors:
            txt(bg, cx + 1.85 + AW + 0.1, ypx(yv) - (0.08 if "\n" in anchors[nm] else 0), anchors[nm], 7.8, INK, "bold", linespacing=1.1)
    cap(bg, cx + 1.85, y + h - 0.4, "Perubahan tarif per tahun; kuning = tarif efektif SMDR")


# ================ Result: jalur kas ===
def _spread(vals, gap):
    vals = np.asarray(vals, dtype=float); order = np.argsort(vals); out = vals.copy()
    for k in range(1, len(order)):
        a, b = order[k - 1], order[k]
        if out[b] - out[a] < gap:
            out[b] = out[a] + gap
    return out


def s4_fan(fig, bg, D, x, y, w, h):
    nhead(bg, x, w, y, "Kas + deposito tetap di atas batas minimum hingga 2031 pada asumsi tengah", 3)
    start = D["opening_cash"] + D["deposits"]
    Pp = D["v7"]["paths"]; th = D["v7"]["th"]
    base = Pp[("Dasar", "central")]["liquidity"].values; ka = Pp[(MK_OVER, "central")]["liquidity"].values
    gb = Pp[(MK_WEAK, "central")]["liquidity"].values; ga = Pp[(MK_WEAK, "adverse")]["liquidity"]
    X = np.arange(-1, 63); full = lambda a: np.concatenate([[start], a])
    cap(bg, x, y + 0.34, "Kas + deposito, USD juta; garis tegak = jatuh tempo sukuk; putus-putus = skenario terburuk, downside case arus kas")
    cap(bg, x, y + 0.52, f"Batas minimum USD {idn(th, 0)} juta = 1 bulan biaya operasi tunai (usulan; SMDR belum menetapkan batas internal)")
    cx, cy, cw, ch = x, y + 0.8, w, h - 1.1
    axw = cw - 2.2
    ax = ax_in(fig, cx + 0.38, cy, axw - 0.38, ch)
    ax.plot(X, full(base), color=ABU_D, lw=1.8, zorder=3); ax.plot(X, full(ka), color=KUNING, lw=3.2, zorder=4); ax.plot(X, full(gb), color=INK, lw=1.9, zorder=5)
    ax.plot(X, full(ga.values), color=INK, lw=1.5, ls=(0, (3, 2)), zorder=5)
    ax.axhline(th, color=MERAH, lw=1.2, ls=(0, (4, 2.5)), zorder=2); ax.axhline(0, color=ABU, lw=0.8)
    fb = ga.index[ga < th]
    if len(fb):
        i0 = list(ga.index).index(fb[0])
        ax.plot([i0], [ga.iloc[i0]], "o", ms=7, color=MERAH, mec=INK, mew=0.6, zorder=7)
        ax.text(0, -30, f"Downside case: di bawah batas\nmulai {ym_label(fb[0])}", fontsize=7.8, color=MERAH, ha="left", va="top", fontweight="bold", zorder=7)
    YL = (-200, 780)
    for mm, a, b, ytxt in [(22, "Seri B", "Agu 2028", 780), (31, "Seri III", "Mei 2029", 680), (45, "Seri II", "Jul 2030", 780)]:
        ax.plot([mm, mm], [0, ytxt], color=ABU, lw=0.7, zorder=0); ax.text(mm + 0.6, ytxt, f"{a} {b}", fontsize=7.8, color=ABU_D, ha="left", va="top")
    ax.plot([-1], [start], marker="o", ms=6, color=INK, zorder=6)
    ax.set_xticks([-1, 14, 26, 38, 50, 62]); ax.set_xticklabels(["Sep-26", "Des-27", "Des-28", "Des-29", "Des-30", "Des-31"])
    ax.set_yticks([0, 200, 400, 600])
    for t in (200, 400, 600):
        ax.axhline(t, color=GRID, lw=0.8, zorder=0)
    style_axes(ax); ax.set_ylim(*YL); ax.set_xlim(-1.5, 63)
    ypix = lambda v: cy + (YL[1] - v) / (YL[1] - YL[0]) * ch
    ends = [(base[-1], "Base Case", ABU_D), (ka[-1], "Overcapacity", KUNING), (gb[-1], "Terburuk", INK), (th, "Batas minimum", MERAH), (float(ga.iloc[-1]), "Terburuk, downside case", INK)]
    adj = _spread([ypix(e[0]) for e in ends], 0.24)
    over = adj[-1] - (cy + ch - 0.05)
    if over > 0:
        adj = [v - over for v in adj]
    xe = cx + axw + 0.05
    txt(bg, xe + 0.22, min(adj) - 0.22, "Des 2031, USD juta", 7.4, ABU_D, nofloor=True)
    for (v, a, c_), yy in zip(ends, adj):
        bg.plot([xe, xe + 0.16], [ypix(v), yy], color=c_, lw=1.4)
        txt(bg, xe + 0.22, yy, f"{a} {idn(v, 0)}", 8.2, MERAH if c_ == MERAH else INK, "bold")
    tq = D["v7"]["tornado"]; tq = tq[tq.d_min_liq.abs() >= 30].head(4)
    nm = {"maintenance_capex": "pemeliharaan", "lease_principal": "pokok sewa", "deposit_availability": "deposito anak", "ocf_conversion": "konversi kas"}
    a_ = v7(D, "adverse"); crfy = a_.loc[MK_WEAK, "current_ratio_breach_fy"]


STYLE = {"Safe": (ABU, INK), "Alert": (KUNING, INK), "Breach": (MERAH, "white")}


# ================ Next Step: KRI dan tahapan ===
def s5_kri(fig, bg, D, x, y, w, h):
    """Dasbor KRI: bullet gauge per indikator; posisi saat ini ditandai segitiga dengan nilainya. Zona: (dari, sampai, warna, label threshold)."""
    head(bg, x, w, y, f"Posisi terkini: tarif global di zona Alert,\nNet Debt to EBITDA {idn(D['nd']['now'], 2)}x di zona aman", lines=2)
    y += 0.2; h -= 0.2
    opex = D["inp_other"]["opex_month"]; wp = D["wci"]
    cover = D["inp_ebitda"] / D["v7"]["dscr"]["den"]
    liq = D["opening_cash"] + D["deposits"]
    pct = lambda v: idn(v, 0, signed=True) + "%"
    g = [("Tarif dan volume (pendahulu: WCI)", "% WCI di atas rata-rata 52 pekan", wp["vs_rata_panjang"] * 100, (-40.0, 80.0), [(50.0, "Zona puncak")], pct(wp["vs_rata_panjang"] * 100), pct),
         ("Net Debt to EBITDA (12 bln)", "x, batas covenant 3,00x", D["nd"]["now"], (1.50, 3.30), [(EW, "Alert"), (3.00, "Breach")], f"{idn(D['nd']['now'], 2)}x", lambda v: idn(v, 2) + "x"),
         ("DSCR (12 bln)", "x, batas min. 1,10x", cover, (3.00, 1.00), [(DSCR_ALERT, "Alert"), (1.10, "Breach")], f"{idn(cover, 2)}x", lambda v: idn(v, 2) + "x"),
         ("Kas + deposito", f"USD juta, batas minimum usulan {idn(opex, 0)}", liq, (600.0, 0.0), [(2 * opex, "Alert"), (opex, "Breach")], f"USD {idn(liq, 0)} juta", lambda v: idn(v, 0))]
    x0, x1 = x + 2.3, x + w - 0.1
    txt(bg, x0, y + 0.4, "\u25c4 Jauh dari batas", 7.4, ABU_D); txt(bg, x1, y + 0.4, "Dekat batas \u25ba", 7.4, ABU_D, ha="right")
    y0 = y + 0.46; rh = (h - 0.78) / 4
    for i, (nm, sub, val, dom, ths, vlab, tfmt) in enumerate(g):
        yy = y0 + i * rh + rh * 0.64
        txt(bg, x, yy - 0.05, nm, 9, INK, "bold"); txt(bg, x, yy + 0.14, sub, 7.8, ABU_D)
        if i == 0:   # indikator internal menautkan threshold slide 4
            txt(bg, x, yy + 0.44, f"Indikator internal: tarif efektif SMDR; headroom {idn(abs(D['nd']['rate']) * 100, 1)}% sebelum 3,00x (slide 4)", 7.8, ABU_D)
        pos = lambda v: x0 + (v - dom[0]) / (dom[1] - dom[0]) * (x1 - x0)
        edges = [dom[0]] + [t for t, _ in ths] + [dom[1]]
        cols = [ABU, KUNING, MERAH][:len(edges) - 1]
        for a_, b_, c_ in zip(edges[:-1], edges[1:], cols):
            bg.add_patch(Rectangle((min(pos(a_), pos(b_)), yy - 0.08), abs(pos(b_) - pos(a_)), 0.16, fc=c_, ec="none"))
        close = len(ths) == 2 and abs(pos(ths[0][0]) - pos(ths[1][0])) < 0.6
        for q, (t, nm_) in enumerate(ths):
            ha_ = ("right" if q == 0 else "left") if close else "center"
            dx = (-0.03 if q == 0 else 0.03) if close else 0
            txt(bg, pos(t) + dx, yy + 0.165, nm_, 6.8, INK, "bold", ha=ha_); txt(bg, pos(t) + dx, yy + 0.275, tfmt(t), 6.8, ABU_D, ha=ha_)
        txt(bg, x0, yy + 0.165, tfmt(dom[0]), 6.8, ABU_D, ha="left")
        if all(abs(x1 - pos(t)) > 0.75 for t, _ in ths):
            txt(bg, x1, yy + 0.165, tfmt(dom[1]), 6.8, ABU_D, ha="right")
        px_ = pos(val)
        bg.plot([px_], [yy - 0.17], marker="v", ms=9, color=INK, mec=INK, zorder=5)
        txt(bg, px_ + 0.13, yy - 0.17, vlab, 8.8, INK, "bold")
    leg(fig, bg, x, y + h - 0.1, [("box", ABU, "Safe"), ("box", KUNING, "Alert"), ("box", MERAH, "Breach"), ("tri", INK, "Posisi terkini")], gap=0.2)


def s5_timeline(fig, bg, D, x, y, w, h):
    """Peta jalan satu sumbu waktu: 90 hari persiapan (Nov 2026 - Feb 2027), keputusan dengan data Mar 2027, pelunasan sebelum
    pengukuran pertama yang dapat melewati batas, lalu langkah kas yang hanya diperlukan pada parameter kas merugikan."""
    import matplotlib.dates as md
    q1 = qfirst(D)
    head(bg, x, w, y, f"Usulan tahapan: persiapan sebelum data Mar 2027,\nevaluasi opsi sebelum pengukuran {ym_label(q1)}", lines=2)
    y += 0.2; h -= 0.2
    start = dt.date(2026, 11, 10)
    d0, d1 = dt.date(2026, 11, 1), dt.date(2028, 12, 31)
    dq = lambda ym: pd.Period(ym, "M").to_timestamp("M").date()
    tmar, tjun, tq1, tdec = dq("2027-03"), dq("2027-06"), dq(q1), dq("2027-12")
    c = v7(D)
    po, pw = c.loc[MK_OVER, "pelunasan_ke_2_7x"], c.loc[MK_WEAK, "pelunasan_ke_2_7x"]
    mt = D["v7"]["mit"]; ok = mt[(mt.case == "central") & (((mt.skenario == MK_OVER) & (mt.paydown == 54) & ~mt.dividend_stop) | ((mt.skenario == MK_WEAK) & (mt.paydown == 107) & mt.dividend_stop))]
    LW = 2.55
    cy, ch = y + 0.45, h - 1.1
    YT, YB = -1.5, 7.5
    ypix = lambda v: cy + (v - YT) / (YB - YT) * ch
    bands = ((0.9, 3.3, "Persi-\napan"), (3.4, 5.3, "Cove-\nnant"), (5.4, 7.3, "Likui-\nditas"))
    for (a_, b_, nm) in bands:
        bg.add_patch(Rectangle((x, ypix(a_)), w, ypix(b_) - ypix(a_), fc="#F4F4F5", ec="none", zorder=0))
        bg.add_patch(Rectangle((x, ypix(a_)), 0.5, ypix(b_) - ypix(a_), fc=KUNING, ec="none", zorder=1))
        bg.text(x + 0.25, (ypix(a_) + ypix(b_)) / 2, nm, fontsize=7.8, fontweight="bold", color=INK, ha="center", va="center", linespacing=1.05, zorder=2)
    ax = ax_in(fig, x + LW, cy, w - LW, ch)
    ax.patch.set_alpha(0)
    X = md.date2num
    ax.set_xlim(X(d0), X(d1)); ax.set_ylim(YB, YT)
    tk = [dt.date(2027, 1, 1), dt.date(2027, 7, 1), dt.date(2028, 1, 1), dt.date(2028, 7, 1)]
    ax.set_xticks([X(d) for d in tk]); ax.set_xticklabels(["Jan 2027", "Jul 2027", "Jan 2028", "Jul 2028"])
    style_axes(ax); ax.set_yticks([])
    ax.spines["left"].set_visible(False)
    for d in tk:
        ax.axvline(X(d), color="white", lw=1.2, zorder=0)
    bg.text(x + 0.58, ypix(0), "Katalis", fontsize=8, fontweight="bold", color=INK, ha="left", va="center")
    ax.axhline(0, color=ABU, lw=0.8, zorder=1)
    cat = [(tjun, "Jun 2027: data konfirmasi", -1.15, "right"), (tq1, f"Pengukuran {ym_label(q1)}", -0.5, "left"),
           (dt.date(2028, 8, 2), "Jatuh tempo Seri B (Agu 2028)", -1.15, "right")]   # bila diukur tahunan (Des 2027): di Catatan
    for d, a_, dy, ha in cat:
        ax.plot([X(d)], [0], "D", ms=7.5, color=KUNING, mec=INK, mew=0.7, zorder=4)
        if dy < -0.6:   # label tingkat atas: garis penunjuk ke penanda
            ax.plot([X(d)] * 2, [dy + 0.22, -0.15], color=ABU, lw=0.6, zorder=1, clip_on=False)
        ax.text(X(d) + {"left": -6, "right": 6}.get(ha, 0), dy, a_, fontsize=7.8, color=INK, ha=ha, va="center", fontweight="bold")
    ax.plot([X(tmar)], [0], "v", ms=8, color=INK, zorder=5)
    ax.text(X(tmar) + 12, -0.5, "Mar 2027: titik evaluasi", fontsize=7.8, color=INK, ha="right", va="center", fontweight="bold")
    dash = dict(fc="white", ec=ABU_D, lw=1.0, ls=(0, (2, 1.5)), zorder=3)
    def lever(yy, nm, txt_, s0, s1, solid=True, left=False, at=None):
        bg.text(x + 0.58, ypix(yy), nm, fontsize=7.8, color=INK, ha="left", va="center")
        kw = dict(fc=KUNING, ec="none", zorder=3) if solid else dash
        ax.add_patch(Rectangle((X(s0), yy - 0.3), X(s1) - X(s0), 0.6, **kw))
        if left:
            ax.text(X(s0) - 6, yy, txt_, ha="right", va="center", fontsize=7.8, color=INK)
        else:
            ax.text(X(at or s1) + 8, yy, txt_, ha="left", va="center", fontsize=7.8, color=INK)
    d30, d60, d90 = [start + dt.timedelta(days=k) for k in (30, 60, 90)]
    lever(1.4, "1. Penetapan threshold dan pemilik KRI", "kalibrasi dengan data kuartalan internal", start, d30, at=d90)
    lever(2.1, "2. Konfirmasi definisi covenant", "frekuensi pengukuran dan DSCR, bersama bank dan Wali Amanat", d30, d60, at=d90)
    lever(2.8, "3. Kuantifikasi empat risiko operasional", "data internal, uji BCP (slide 3)", d60, d90)
    crfy = v7(D, "adverse").loc[MK_WEAK, "current_ratio_breach_fy"]; tcr = dq(f"{crfy[2:]}-12"); tprep = dq(f"{crfy[2:]}-06")
    lever(3.95, "Penahanan dividen 2027", "skenario terburuk, USD 23 juta/tahun", tmar, tjun, at=tq1)
    lever(4.75, "Pelunasan sebagian utang bank\natau permohonan waiver", f"USD {idn(po, 0)}\u2013{idn(pw, 0)} juta", tjun, tq1)
    lever(5.95, "Refinancing utang bank", f"bila downside case: Current Ratio < 1,10x Des {crfy[2:]}", tprep, tcr, solid=False, left=True)
    lever(6.75, "Penundaan belanja modal", "belanja pemeliharaan USD 70 juta/tahun", tprep, tcr, solid=False, left=True)
    ax.plot([X(tq1)] * 2, [3.4, 5.3], color=MERAH, lw=1.2, ls=(0, (4, 2.5)), zorder=2)
    cap(bg, x, y + h - 0.36, f"Hasil uji (asumsi tengah): Net Debt to EBITDA \u2264 {idn(ND_SASARAN, 2)}x per {ym_label(q1)}, Current Ratio \u2265 {idn(ok.current_ratio_min.min(), 2)}x, kas + deposito \u2265 USD {idn(ok.min_liquidity.min(), 0)} juta")
    leg(fig, bg, x, y + h - 0.1, [("diamond", KUNING, "Katalis"), ("box", KUNING, "Jendela persiapan"), ("hbox", ABU_D, "Bersyarat (downside case)"), ("tri", INK, "Titik evaluasi"), ("dash", MERAH, "Pengukuran covenant")], size=7.2, gap=0.1)


# ================ Risk dan Scenario: siklus tarif, eksposur, backtesting ===
def r3_cycle_chart(fig, bg, D, x, y, w, h):
    """Hero slide Risk (Stopford): WCI mingguan vs tarif efektif SMDR (indeks FY2022 = 100), dengan dua episode posisi tinggi WCI."""
    import datetime as _dt
    import pandas as pd
    import matplotlib.dates as md
    from smdr import datapaths
    cap(bg, x, y + 0.34, "Indeks 2022 = 100; titik abu = rata-rata tahunan WCI, setara frekuensi dengan tarif SMDR")
    s = pd.read_csv(datapaths.table("wci_composite_weekly.csv"), parse_dates=["date"]).set_index("date")["wci"]
    s = s[~s.index.duplicated()]
    idx = s[s.index >= "2020-01-01"] / s[s.index.year == 2022].mean() * 100
    rz = D["realized"]["tarif_efektif"]
    lvl = [100.0]
    for p in ("FY2023", "FY2024", "FY2025"):
        lvl.append(lvl[-1] * (1 + float(rz[p])))
    dts = [_dt.date(2022 + k, 7, 1) for k in range(4)]
    ax = ax_in(fig, x + 0.45, y + 0.62, w - 0.55, h - 1.35)
    X = md.date2num
    for _, r in D["wci_eps"].iterrows():
        ax.axvspan(X(r["mulai"]), X(r["selesai"]), color=ABU_L, lw=0, zorder=0)
        ax.text((X(r["mulai"]) + X(r["selesai"])) / 2, 187, "Zona puncak", fontsize=7.8, ha="center", va="bottom", color=ABU_D)
    ax.plot([X(d) for d in idx.index.date], idx.values, color=ABU, lw=1.0, zorder=2)
    ann = s[(s.index.year >= 2022) & (s.index.year <= 2025)].groupby(s[(s.index.year >= 2022) & (s.index.year <= 2025)].index.year).mean()
    ann = ann / ann.loc[2022] * 100
    ax.plot([X(_dt.date(int(yv), 7, 1)) for yv in ann.index], ann.values, color=ABU_D, lw=1.6, ls=(0, (3, 2)), marker="o", ms=6, mfc="white", mec=ABU_D, mew=1.2, zorder=3)
    for yv, v in ann.items():
        if yv in (2023, 2025):
            ax.text(X(_dt.date(int(yv), 7, 1)) + 50, v, f"{idn(v, 0)}", fontsize=8.4, ha="left", va="center", color=ABU_D, fontweight="bold", zorder=5)
    head(bg, x, w, y, f"WCI kini di zona puncak; koreksi 2023 menurunkan tarif SMDR {idn(100 - lvl[1], 0)}%", size=11)
    ax.plot([X(d) for d in dts], lvl, color=KUNING, lw=3.2, marker="o", ms=7, mec=INK, mew=0.7, zorder=4)
    for k, (d, v) in enumerate(zip(dts, lvl)):
        if k != 2:   # 2024: titik WCI dan SMDR berdekatan; nilainya tidak diperlukan untuk pesan panel
            ax.text(X(d), v + 9, f"{idn(v, 0)}", fontsize=9, ha="center", va="bottom", color=INK, fontweight="bold", zorder=5)
    ax.plot([X(idx.index[-1].date())], [idx.iloc[-1]], "o", ms=6.5, color=INK, zorder=5)
    wp = D["wci"]
    ax.annotate(f"WCI USD {idn(wp['terkini'], 0)} (5 Nov 2026), {idn(wp['vs_rata_panjang'] * 100, 0, signed=True)}% vs rata-rata 52 pekan\nOrderbook 46,5% armada, tertinggi sejak 2009:\npasokan baru akan menekan tarif (Stopford)", xy=(X(idx.index[-1].date()), idx.iloc[-1] + 4), xytext=(X(idx.index[-1].date()) + 5, 142), fontsize=8.2, ha="right", va="bottom", color=INK, linespacing=1.15, arrowprops=dict(arrowstyle="-", color=ABU_D, lw=0.8))
    ax.text(X(_dt.date(2021, 10, 1)), 166, "Drewry WCI", fontsize=8.8, color=ABU_D, ha="left", va="bottom", fontweight="bold")
    ax.text(X(_dt.date(2022, 9, 15)), 118, "Tarif efektif SMDR", fontsize=8.8, color=INK, ha="left", va="bottom", fontweight="bold")
    ax.set_xlim(X(_dt.date(2020, 1, 1)), X(_dt.date(2026, 12, 31))); ax.set_ylim(0, 205)
    ax.set_xticks([X(_dt.date(yv, 1, 1)) for yv in range(2020, 2027)]); ax.set_xticklabels([str(yv) for yv in range(2020, 2027)])
    ax.set_yticks([50, 100, 150]); ax.axhline(100, color=ABU, lw=0.8, ls=(0, (3, 3)), zorder=1)
    style_axes(ax, left=True); ax.tick_params(labelsize=8.6)
    cap(bg, x + 0.45, y + h - 0.15, "Zona puncak: WCI > +50% di atas rata-rata 52 pekan (dua episode sejak 2016; posisi, bukan ramalan)")


def r3_strip(fig, bg, D, x, y, w):
    """Dua baris konteks: eksposur geografis 9M26 sebagai satu batang 100% berlabel langsung, dan risiko yang belum terukur."""
    g = D["v7"]["geo"]; tot = g.sum()
    seg = [("indonesia", "Indonesia", ABU_D, "white"), ("southeast_asia_ex_indonesia", "Asia Tenggara lain", ABU, INK),
           ("middle_east_india", "TT & India", KUNING, INK), ("others", "", ABU_L, INK)]
    txt(bg, x, y + 0.08, "Eksposur pendapatan:", 8.8, INK, "bold")
    bx, bw, bh = x + 1.75, 6.2, 0.2
    cx = bx
    for k, lab, fc, tc in seg:
        sw = g[k] / tot * bw
        bg.add_patch(Rectangle((cx, y + 0.08 - bh / 2), sw - 0.02, bh, fc=fc, ec="none"))
        t = f"{lab} {idn(g[k] / tot * 100, 0)}%".strip()
        txt(bg, cx + 0.05, y + 0.08, t, 7.6, tc, "bold", nofloor=True)
        cx += sw
    txt(bg, cx + 0.12, y + 0.08, f"TT (Timur Tengah) & India: USD {idn(g['middle_east_india'], 0)} juta; insiden Hormuz 13 Okt 2026", 8.2, INK)
    txt(bg, x, y + 0.34, "Belum dikuantifikasi:", 8.8, INK, "bold")
    txt(bg, x + 1.75, y + 0.34, "pasokan BBM domestik (butuh konsumsi BBM per rute), cuaca ekstrem (hari off-hire), gangguan siber (downtime sistem), "
        "regulasi emisi IMO (biaya kepatuhan per kapal)", 8.8, "#3A3A3A")


def s4_back_sens(fig, bg, D, x, y, w, h):
    """Backtesting dalam bahasa sehari-hari: pasangan batang prediksi vs aktual dengan label langsung dan kelipatan di atasnya;
    pada FY2023 bagian yang tidak terjadi karena biaya ikut turun diarsir. Di kanan: headroom penurunan tarif sebelum 3,00x."""
    from matplotlib.patches import Rectangle as _R
    head(bg, x, w, y, "Backtesting FY2023\u2013FY2025: dampak aktual tidak melampaui prediksi model", lines=1, size=10.5)
    b = D["backtest"]; be = D["v7"]["bt"]
    ratio = (b["terealisasi"] / b["model"]).clip(upper=1.0)
    assert (b["model"] <= b["terealisasi"] + 1.0).all(), "judul panel: penurunan aktual tidak melebihi prediksi (toleransi USD 1 juta)"
    cw_ = w * 0.56
    cap(bg, x, y + 0.36, "Perubahan EBITDA, USD juta")
    ax = ax_in(fig, x + 0.1, y + 0.7, cw_ - 0.1, h - 1.3)
    cost = abs(float(be.loc["FY2023", "biaya_jasa_delta"]))
    for i, p in enumerate(b.index):
        mv, av = float(b.loc[p, "model"]), float(b.loc[p, "terealisasi"])
        if p == "FY2023":
            ax.bar(i - 0.2, mv + cost, width=0.36, color=KUNING, lw=0, zorder=3)
            ax.add_patch(_R((i - 0.38, mv), 0.36, cost, fc="white", ec="#B7860B", hatch="////", lw=0.8, zorder=3))
            ax.annotate(f"biaya ikut turun\nUSD {idn(cost, 0)} juta", xy=(i - 0.02, mv + cost / 2), xytext=(i + 0.45, mv + cost / 2 - 40), fontsize=7.6, color=INK,
                        ha="left", va="center", arrowprops=dict(arrowstyle="-", color=ABU_D, lw=0.7))
        else:
            ax.bar(i - 0.2, mv, width=0.36, color=KUNING, lw=0, zorder=3)
        ax.bar(i + 0.2, av, width=0.36, color=ABU_D, lw=0, zorder=3)
        for off, v in ((-0.2, mv), (0.2, av)):
            ax.text(i + off, v + (-14 if v < 0 else 14), idn(v, 0), ha="center", va="top" if v < 0 else "bottom", fontsize=8.4, color=INK, fontweight="bold")
        k = mv / av if av else 1.0
        lab_ = "prediksi\n= aktual" if abs(k - 1) < 0.05 else f"prediksi\n{idn(k, 1)}\u00d7 aktual"
        ax.text(i, 95, lab_, ha="center", va="bottom", fontsize=8.2, color=INK, fontweight="bold", linespacing=1.1)
    ax.axhline(0, color=ABU_D, lw=0.9, zorder=4)
    ax.set_xticks(range(len(b))); ax.set_xticklabels(list(b.index)); ax.set_xlim(-0.6, len(b) - 0.4); ax.set_ylim(-560, 185)
    ax.set_yticks([]); style_axes(ax, bottom=False); ax.tick_params(axis="x", labelsize=8.4, pad=14)
    for i in range(len(b)):
        ax.text(i - 0.2, -540, "prediksi", ha="center", va="bottom", fontsize=6.8, color="#B7860B")
        ax.text(i + 0.2, -540, "aktual", ha="center", va="bottom", fontsize=6.8, color=ABU_D)
    tx = x + cw_ + 0.3; tw = w - cw_ - 0.3
    yy = y + 0.7
    txt(bg, tx, yy, "Headroom penurunan tarif", 9.5, INK, "bold"); txt(bg, tx, yy + 0.2, "sebelum 3,00x", 9.5, INK, "bold")
    txt(bg, tx, yy + 0.47, "Jika dampak nyata:", 8.4, ABU_D)
    hline(bg, tx, tx + tw, yy + 0.6, ABU, 0.8)
    rate = abs(D["nd"]["rate"]) * 100
    rows = [("sama dengan prediksi", rate, True)] + [(f"seperti {p}", rate / float(ratio[p]), False) for p in ("FY2024", "FY2023")]
    for k, (lab, v, bold) in enumerate(rows):
        ry = yy + 0.8 + k * 0.3
        if k:
            hline(bg, tx, tx + tw, ry - 0.16, GRID, 0.8)
        txt(bg, tx, ry, lab, 9, INK, "bold" if bold else "normal"); txt(bg, tx + tw, ry, f"{idn(v, 1)}%", 9.5, INK, "bold", ha="right")


# ================ Result: Net Debt to EBITDA per kuartal ===
def r5_quarterly(fig, bg, D, x, y, w, h):
    """Hero slide Result: Net Debt to EBITDA per akhir kuartal (EBITDA 12 bulan terakhir), Sep 2026 - Des 2028. Membuktikan dua klaim:
    kapan rasio pertama melewati 3,00x, dan bahwa data Mar 2027 sudah memisahkan skenario (early warning 2,45x)."""
    q = D["v7"]["q"]; qc, qa = q[q.case == "central"], q[q.case == "adverse"]
    qs = list(qc.quarter.drop_duplicates()); X = list(range(1, len(qs) + 1))
    now = D["nd"]["now"]; q1 = qfirst(D)
    nhead(bg, x, w, y, f"Net Debt to EBITDA melewati 3,00x per {ym_label(q1)} pada dua skenario pasar", 1)
    cap(bg, x, y + 0.34, "Per akhir kuartal (EBITDA 12 bulan); label = puncak tiap skenario (\u2022); putus-putus = downside case arus kas")
    cap(bg, x, y + 0.52, "Terburuk = Weak Demand + Overcapacity; Base Case = proyeksi makro dasar (OCE Bank Mandiri)")
    ax = ax_in(fig, x + 0.38, y + 0.8, w - 2.05, h - 1.18)
    path = lambda d, k: [now] + list(d[d.skenario == k].sort_values("quarter")["nd"])
    for k in ("Dasar", "Energi bertahan", "Gabungan", MK_DEM):
        ax.plot([0] + X, path(qc, k), color=ABU if k != MK_DEM else ABU_D, lw=1.2, zorder=2)
    ax.plot([0] + X, path(qa, MK_WEAK), color=INK, lw=1.2, ls=(0, (3, 2)), zorder=3)
    ax.plot([0] + X, path(qc, MK_OVER), color=KUNING, lw=3.0, zorder=4)
    ax.plot([0] + X, path(qc, MK_WEAK), color=INK, lw=2.2, zorder=5)
    ax.axhline(3.0, color=MERAH, lw=1.3, ls=(0, (4, 2.5)), zorder=1)
    ax.axhline(EW, color=ABU_D, lw=0.9, ls=(0, (1.5, 2)), zorder=1)
    ax.text(0.05, 3.03, "Batas maks. 3,00x", fontsize=8.2, color=MERAH, fontweight="bold", va="bottom")
    ax.text(len(qs) - 0.5, EW + 0.03, f"Early Warning {idn(EW, 2)}x", fontsize=7.8, color=ABU_D, va="bottom", ha="right")
    im, iq = qs.index("2027-03") + 1, qs.index(q1) + 1
    for xi, lab in ((im, "Mar 2027:\nEarly Warning"), (iq, f"{ym_label(q1)}:\npertama > 3,00x")):
        ax.axvline(xi, color=ABU, lw=0.8, zorder=0)
        ax.text(xi + 0.08, 3.93, lab, fontsize=7.6, color=INK, va="top", linespacing=1.1)
    m3 = qc[qc.quarter == "2027-03"].set_index("skenario")["nd"]
    for k in (MK_WEAK, MK_OVER):
        ax.plot([im], [m3[k]], "o", ms=5.5, color=INK if k == MK_WEAK else KUNING, mec=INK, mew=0.6, zorder=6)
    rest = m3.drop([MK_OVER, MK_WEAK]).max()

    ax.set_xticks([0] + X); ax.set_xticklabels(["Sep 26"] + [f"{MON[int(t[5:]) - 1]} {t[2:4]}" if t[5:] in ("03", "09") or t == qs[0] else "" for t in qs])
    ax.set_ylim(1.9, 3.95); ax.set_xlim(-0.2, len(qs) + 0.2); ax.set_yticks([2.0, 2.5, 3.0, 3.5])
    ax.set_yticklabels(["2,0x", "2,5x", "3,0x", "3,5x"])
    style_axes(ax, left=True); ax.tick_params(labelsize=8)
    cy, ch = y + 0.8, h - 1.18
    ypix = lambda v: cy + (3.95 - v) / (3.95 - 1.9) * ch
    pk, pka = qpeak(D), qpeak(D, "adverse")
    assert abs(pk["Energi bertahan"] - pk["Gabungan"]) <= 0.02, "label gabungan: dua garis biaya harus berimpit"
    kc = max(["Energi bertahan", "Gabungan"], key=lambda k: pk[k])
    ends = [(qa, MK_WEAK, "Terburuk, downside case", f"puncak {idn(pka[MK_WEAK], 2)}x", INK),
            (qc, MK_WEAK, "Terburuk", f"puncak {idn(pk[MK_WEAK], 2)}x", INK),
            (qc, MK_OVER, "Overcapacity", f"puncak {idn(pk[MK_OVER], 2)}x", "#B7860B"),
            (qc, MK_DEM, "Demand Slowdown", f"puncak {idn(pk[MK_DEM], 2)}x", ABU_D),
            (qc, kc, "Prolonged Energy & Combined", f"puncak {idn(pk[kc], 2)}x", ABU_D),
            (qc, "Dasar", "Base Case", f"puncak {idn(pk['Dasar'], 2)}x", ABU_D)]
    def peak_xy(d, k):
        sr = list(d[d.skenario == k].sort_values("quarter")["nd"]); m = max(sr)
        return len(sr) - list(reversed(sr)).index(m), m   # kuartal terakhir yang mencapai puncak (indeks X)
    x0a, wa = x + 0.38, w - 2.05
    xpix = lambda xi: x0a + (xi + 0.2) / (len(qs) + 0.4) * wa
    last = lambda d, k: float(d[d.skenario == k].sort_values("quarter")["nd"].iloc[-1])
    adj = _spread([ypix(last(d, k)) for d, k, *_ in ends], 0.34)
    over = adj[-1] - (cy + ch - 0.1)
    if over > 0:
        adj = [v - over for v in adj]
    xe = x0a + wa + 0.12
    for (d, k, a1, a2, c_), yy in zip(ends, adj):
        px_, pv = peak_xy(d, k)
        bg.plot([xpix(px_)], [ypix(pv)], "o", ms=3.6, color=c_ if c_ != "#B7860B" else KUNING, mec=INK, mew=0.4, zorder=8)
        bg.plot([xpix(len(qs)) + 0.04, xe - 0.04], [ypix(last(d, k)), yy], color=c_ if c_ != "#B7860B" else KUNING, lw=0.9, zorder=0)
        bold = "bold" if c_ != ABU_D else "normal"
        txt(bg, xe, yy - 0.075, a1, 7.8, c_, bold)
        txt(bg, xe, yy + 0.085, a2, 7.8, c_, bold)
    assert min(m3[MK_WEAK], m3[MK_OVER]) >= EW > rest, "early warning harus memisahkan skenario pada data Mar 2027"
    txt(bg, x, y + h - 0.05, f"Early Warning (\u25cf): pada data Mar 2027, dua skenario yang nanti melewati 3,00x sudah {idn(m3[MK_WEAK], 2)}x dan {idn(m3[MK_OVER], 2)}x; skenario lain \u2264 {idn(rest, 2)}x.", 7.8, INK)


# ================ Executive Summary: rantai cerita ===
def s1_spine(fig, bg, D, x, y, w):
    """Executive Summary sebagai satu rantai sebab-akibat: Situasi -> Pemicu -> Transmisi -> Dampak -> Respons, dengan lini waktu di
    bawahnya. Tiga mikro-visual berbeda jenis (sparkline WCI, bridge EBITDA, skala rasio); kotak pertama dan terakhir berupa angka."""
    import os
    import matplotlib.dates as md
    from matplotlib.patches import Polygon
    from smdr import datapaths
    c, a = v7(D), v7(D, "adverse")
    q1 = qfirst(D); pk, pka = qpeak(D), qpeak(D, "adverse"); hs = D["v7"]["hist"]; sv = D["v7"]["sev"]
    m0, m1, c0_, c1_ = ebitda_pcts(D)
    e0, e1 = D["inp_ebitda"], float(c.loc[MK_OVER, "ebitda_FY2027"])
    tr12 = abs(float(D["narr"].set_index("kisah").loc[MK_OVER, "tarif"])) * 100
    po, pw = c.loc[MK_OVER, "pelunasan_ke_2_7x"], c.loc[MK_WEAK, "pelunasan_ke_2_7x"]
    crfy = a.loc[MK_WEAK, "current_ratio_breach_fy"]; fb = a["first_below"].dropna().min()
    nb, ga = 5, 0.34
    bw = (w - (nb - 1) * ga) / nb
    by, bh = y, 3.95
    bx = [x + i * (bw + ga) for i in range(nb)]
    stages = ["SITUASI", "PEMICU", "TRANSMISI", "DAMPAK", "RESPONS"]
    for i, xx in enumerate(bx):
        bg.add_patch(Rectangle((xx, by), bw, bh, fc="#F6F6F7", ec="none", zorder=0))
        bg.add_patch(Rectangle((xx, by), bw, 0.05, fc=MERAH if i == 3 else (KUNING if i == 4 else ABU_D), ec="none", zorder=1))
        txt(bg, xx + 0.14, by + 0.25, stages[i], 7.8, ABU_D, "bold", nofloor=True)
        if i < nb - 1:
            ax0, ay = xx + bw + 0.07, by + 1.5
            bg.add_patch(Polygon([(ax0, ay - 0.16), (ax0 + 0.2, ay), (ax0, ay + 0.16)], closed=True, fc=ABU, ec="none"))
    big = lambda i, s, col=INK: txt(bg, bx[i] + 0.14, by + 0.72, s, 24, col, "bold")
    lab = lambda i, lines: [txt(bg, bx[i] + 0.14, by + 1.1 + 0.17 * k, ln, 8.4, ABU_D) for k, ln in enumerate(lines)]
    note = lambda i, lines: [txt(bg, bx[i] + 0.14, by + 3.02 + 0.19 * k, ln, 8.4, INK) for k, ln in enumerate(lines)]
    vx, vw, vy, vh = lambda i: bx[i] + 0.14, bw - 0.28, by + 1.6, 1.15

    # 1 SITUASI: tren rasio menuju batas
    big(0, f"{idn(D['nd']['now'], 2)}x")
    lab(0, ["Net Debt to EBITDA, TTM Sep 2026", "batas maksimal bank 3,00x"])
    nd = D["nd_hist"]; keys = (("FY22", "FY2022"), ("FY23", "FY2023"), ("FY24", "FY2024"), ("FY25", "FY2025"), ("TTM", "TTM"))
    cw_ = (vw - 0.08 * 4) / 5; base = vy + vh - 0.14
    for k, (lb, key) in enumerate(keys):
        hh = nd[key] / 3.3 * (vh - 0.2); xx = vx(0) + k * (cw_ + 0.08)
        bg.add_patch(Rectangle((xx, base - hh), cw_, hh, fc=KUNING if key == "TTM" else ABU, ec="none", zorder=2))
        txt(bg, xx + cw_ / 2, base + 0.09, lb, 6.8, ABU_D, ha="center", nofloor=True)
        if key in ("FY2022", "TTM"):
            txt(bg, xx + cw_ / 2, base - hh - 0.08, idn(nd[key], 2), 6.8, INK, "bold", ha="center", nofloor=True)
    yl = base - 3.0 / 3.3 * (vh - 0.2)
    bg.plot([vx(0), vx(0) + vw], [yl, yl], color=MERAH, lw=1.0, ls=(0, (3, 2)), zorder=3)
    txt(bg, vx(0), yl - 0.08, "batas 3,00x", 6.8, MERAH, "bold", nofloor=True)
    ebitda_ttm = D["inp_ebitda"]
    note(0, [f"Kas + deposito USD {idn(D['opening_cash'] + D['deposits'], 0)} juta", "Tiap USD 100 juta utang atau sewa", f"kapal baru menambah +{idn(100 / ebitda_ttm, 2)}x"])

    # 2 PEMICU: posisi siklus (sparkline WCI dengan zona puncak)
    big(1, f"+{idn(D['wci']['vs_rata_panjang'] * 100, 0)}%")
    lab(1, ["Indeks tarif kontainer global (WCI)", "vs rata-rata 52 pekan: zona puncak"])
    s = pd.read_csv(datapaths.table("wci_composite_weekly.csv"), parse_dates=["date"]).set_index("date")["wci"]
    s = s[~s.index.duplicated()]
    dev = s.rolling(4).mean() / s.rolling(52).mean() - 1
    s3, d3 = s[s.index >= "2023-07-01"], dev[dev.index >= "2023-07-01"]
    ax = ax_in(fig, vx(1), vy, vw, vh - 0.12); ax.patch.set_alpha(0)
    X = md.date2num(s3.index.to_pydatetime())
    ax.fill_between(X, 0, s3.max() * 1.1, where=(d3 >= 0.5).values, color=ABU_L, lw=0, zorder=0)
    ax.plot(X, s3.values, color=ABU_D, lw=1.1, zorder=2); ax.plot([X[-1]], [s3.iloc[-1]], "o", ms=5, color=MERAH, zorder=3)
    ax.set_xlim(X[0], X[-1] + 20); ax.set_ylim(0, s3.max() * 1.1); ax.axis("off")
    txt(bg, vx(1), vy + vh + 0.02, "2023", 6.8, ABU_D, nofloor=True); txt(bg, vx(1) + vw, vy + vh + 0.02, "Nov 2026", 6.8, ABU_D, ha="right", nofloor=True)
    txt(bg, vx(1) + vw / 2, vy + vh + 0.02, "abu = zona puncak", 6.8, ABU_D, ha="center", nofloor=True)
    note(1, ["Orderbook 46,5% armada,", "tertinggi sejak 2009: pasokan", "baru akan menekan tarif"])

    # 3 TRANSMISI: bridge EBITDA
    big(2, f"\u2212{idn((e0 - e1) / e0 * 100, 0)}%")
    lab(2, [f"EBITDA jika tarif \u2212{idn(tr12, 0)}%", "(setara FY2024)"])
    vals = [(e0, 0, ABU_D, idn(e0, 0)), (e0 - e1, e1, KUNING, f"\u2212{idn(e0 - e1, 0)}"), (e1, 0, ABU, idn(e1, 0))]
    sc = (vh - 0.25) / e0; base = vy + vh - 0.14; cw3 = vw / 3 - 0.12
    for k, (v, bot, col, lb) in enumerate(vals):
        xx = vx(2) + k * (vw / 3)
        bg.add_patch(Rectangle((xx, base - (bot + v) * sc), cw3, v * sc, fc=col, ec="none", zorder=2))
        txt(bg, xx + cw3 / 2, base - (bot + v) * sc - 0.08, lb, 7.4, INK, "bold", ha="center", nofloor=True)
        txt(bg, xx + cw3 / 2, base + 0.09, ("TTM", "tarif", "sesudah")[k], 6.8, ABU_D, ha="center", nofloor=True)
    note(2, [f"Tarif + volume: hingga {idn(m1, 0)}% EBITDA,", "sekitar 2\u00d7 dampak harga minyak", "Backtesting: model konservatif"])

    # 4 DAMPAK: skala rasio terhadap batas
    big(3, f"{idn(pk[MK_OVER], 2)}x", MERAH)
    lab(3, [f"Net Debt to EBITDA per {ym_label(q1)}", f"(tarif \u2212{idn(tr12, 0)}% selama 24 bulan)"])
    lo, hi = 2.0, 3.6
    px = lambda v: vx(3) + (v - lo) / (hi - lo) * vw
    yy = vy + vh * 0.55
    bg.plot([vx(3), vx(3) + vw], [yy, yy], color=ABU, lw=2.2, solid_capstyle="round", zorder=1)
    bg.plot([px(3.0)] * 2, [yy - 0.3, yy + 0.22], color=MERAH, lw=1.2, ls=(0, (3, 2)), zorder=2)
    txt(bg, px(3.0), yy - 0.38, "batas 3,00x", 6.8, MERAH, "bold", ha="center", nofloor=True)
    marks = [(D["nd"]["now"], "kini", ABU_D, "o", 1), (pk[MK_OVER], "", KUNING, "D", 1), (pk[MK_WEAK], "terburuk", INK, "o", 1)]
    for v, lb, col, mk, side in marks:
        bg.plot([px(v)], [yy], marker=mk, ms=7, color=col, mec=INK, mew=0.7, zorder=4)
        if lb:
            txt(bg, px(v), yy + 0.2 * side, f"{lb} {idn(v, 2)}", 6.8, INK, ha="center", nofloor=True)
    note(3, [f"Terburuk {idn(pk[MK_WEAK], 2)}x; FY2024 aktual {idn(hs.loc['FY2024', 'nd'], 2)}x", "Rasio lain memenuhi (asumsi tengah)",
             f"Current Ratio Des {crfy[2:]}, kas {ym_label(fb)}:", "hanya pada downside case arus kas"])

    # 5 RESPONS: aturan tindakan
    big(4, f"\u2265 {idn(EW, 2)}x")
    lab(4, ["pada data Mar 2027", "\u2192 titik evaluasi opsi mitigasi"])
    items = [(True, f"Pelunasan USD {idn(po, 0)}\u2013{idn(pw, 0)} juta"), (False, "atau waiver; skenario terburuk"), (False, "+ penahanan dividen"),
             (True, "Empat KRI:"), (False, "tarif & volume, Net Debt to EBITDA,"), (False, "DSCR, kas (threshold Alert/Breach)"),
             (True, "Downside case arus kas:"), (False, "refinancing, tunda belanja modal")]
    yk = vy + 0.05
    for bullet, it in items:
        if bullet:
            yk += 0.1
            bg.add_patch(Rectangle((vx(4), yk - 0.05), 0.1, 0.1, fc=KUNING, ec="none"))
        txt(bg, vx(4) + 0.18, yk, it, 8.4 if bullet else 8.2, INK if bullet else ABU_D, "bold" if bullet else "normal")
        yk += 0.19


# ================ Result: DSCR dan Current Ratio ===
def s5_ratios(fig, bg, D, x, y, w, h):
    """(2) DSCR dan Current Ratio terendah per skenario pada asumsi tengah: angka saja (semua memenuhi), tanpa kotak status."""
    c = v7(D)
    nhead(bg, x, w, y, "DSCR dan Current Ratio tetap di atas 1,10x pada asumsi tengah", 2)
    crfy = v7(D, "adverse").loc[MK_WEAK, "current_ratio_breach_fy"]; assert isinstance(crfy, str) and crfy.startswith("FY")
    cap(bg, x, y + 0.34, "Nilai terendah FY2027\u2013FY2030 per skenario, asumsi tengah; terburuk = Weak Demand + Overcapacity")
    cap(bg, x, y + 0.52, f"Downside case arus kas: Current Ratio skenario terburuk di bawah 1,10x mulai Des {crfy[2:]}")
    keys = [("Dasar", ["Base", "Case"]), ("Energi bertahan", ["Prolonged", "Energy"]), ("Gabungan", ["Combined"]),
            (MK_DEM, ["Demand", "Slowdown"]), (MK_OVER, ["Over-", "capacity"]), (MK_WEAK, ["Terburuk"])]
    lw_ = 1.85; cw = (w - lw_) / len(keys)
    yh = y + 0.74
    for j, (k, hd) in enumerate(keys):
        for q, ln in enumerate(hd):
            txt(bg, x + lw_ + j * cw + cw / 2, yh + 0.13 * q, ln, 7.4, ABU_D, ha="center", nofloor=True)
    cov = lambda k: min(c.loc[k, "cover_FY2027"], c.loc[k, "cover_FY2028"])
    rows = [("DSCR (min. 1,10x)", cov), ("Current Ratio (min. 1,10x)", lambda k: c.loc[k, "current_ratio_min"])]
    for i, (lab, f) in enumerate(rows):
        yy = yh + 0.42 + i * 0.28
        hline(bg, x, x + w, yy - 0.15, GRID if i else ABU, 0.8)
        txt(bg, x, yy, lab, 8.4, INK, "bold")
        for j, (k, _) in enumerate(keys):
            v = float(f(k)); assert v > 1.10
            txt(bg, x + lw_ + j * cw + cw / 2, yy, f"{idn(v, 2)}x", 9, INK, "bold" if k == MK_WEAK else "normal", ha="center")

