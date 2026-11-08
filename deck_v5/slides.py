import datetime as dt
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from theme import *  # noqa: F401,F403
from data import load
import panels as P


def _wave(bg, c, a, lam, ph, col, shadow=True, z=3):
    """Satu lapis ombak berisi penuh sampai tepi bawah, dengan bayangan tipis di atasnya."""
    import numpy as np
    x = np.linspace(0, W, 600)
    y = c + a * np.sin(2 * np.pi * x / lam + ph) + 0.4 * a * np.sin(2 * np.pi * x / (lam * 0.47) + 2 * ph)
    if shadow:
        for k in range(5):
            bg.fill_between(x, y - 0.012 * (k + 1), H, color=INK, alpha=0.035, lw=0, zorder=z - 0.1)
    bg.fill_between(x, y, H, color=col, lw=0, zorder=z)


def _ship(bg, x0=8.55, yd=5.68):
    """Kapal peti kemas: lambung hitam, bangunan akomodasi abu dengan cerobong kuning, tumpukan kontainer berwarna palet Samudera."""
    from matplotlib.patches import Polygon
    bg.add_patch(Polygon([(x0, yd), (x0 + 4.35, yd), (x0 + 3.95, yd + 0.55), (x0 + 0.25, yd + 0.55)], closed=True, fc=INK, ec="none", zorder=2))
    bg.add_patch(Rectangle((x0 + 0.05, yd - 0.04), 4.3, 0.07, fc=MERAH, ec="none", zorder=2))
    bg.add_patch(Rectangle((x0 + 0.2, yd - 0.95), 0.62, 0.91, fc="white", ec=ABU_D, lw=0.8, zorder=2))
    bg.add_patch(Rectangle((x0 + 0.14, yd - 1.12), 0.74, 0.17, fc=ABU_D, ec="none", zorder=2))
    for k in range(3):
        bg.add_patch(Rectangle((x0 + 0.28 + k * 0.19, yd - 0.86), 0.12, 0.09, fc=ABU, ec="none", zorder=2.5))
    bg.add_patch(Rectangle((x0 + 0.42, yd - 1.36), 0.2, 0.24, fc=MERAH, ec="none", zorder=2))
    bg.add_patch(Rectangle((x0 + 0.42, yd - 1.36), 0.2, 0.05, fc=ABU_D, ec="none", zorder=2.5))
    pal = [MERAH, ABU, "white", ABU_L, ABU_D]
    stacks = [3, 4, 5, 5, 4, 5, 3, 2]
    cw, ch = 0.42, 0.26
    for c, n in enumerate(stacks):
        for r in range(n):
            bg.add_patch(Rectangle((x0 + 1.0 + c * (cw + 0.02), yd - 0.01 - (r + 1) * (ch + 0.015)), cw, ch, fc=pal[(c * 2 + r * 3) % 5], ec=ABU_D if pal[(c * 2 + r * 3) % 5] == "white" else "white", lw=0.8, zorder=2))


def slide0(D=None):
    """Sampul: kapal peti kemas berlayar di atas empat lapis ombak abu-abu dan merah."""
    fig, bg = new_slide()
    _wave(bg, 6.0, 0.08, 4.6, 0.3, ABU_L, shadow=False, z=1)
    _ship(bg)
    _wave(bg, 6.2, 0.1, 3.9, 1.6, ABU, z=3)
    _wave(bg, 6.58, 0.12, 5.2, 0.4, MERAH, z=4)
    _wave(bg, 7.05, 0.1, 4.1, 2.4, ABU_D, z=5)
    bg.set_xlim(0, W); bg.set_ylim(H, 0)
    bg.add_patch(Rectangle((MARGIN + 0.5, 1.55), 0.55, 0.05, fc=KUNING, ec="none"))
    txt(bg, MARGIN + 0.5, 2.05, "Sensitivitas Pemenuhan Covenant dan Likuiditas", 36, INK, "normal", fontfamily=SERIF)
    txt(bg, MARGIN + 0.5, 2.62, "terhadap Siklus Freight Rate", 36, INK, "normal", fontfamily=SERIF)
    txt(bg, MARGIN + 0.5, 3.3, "Stress Test Berbasis Skenario dan Backtesting", 16, INK, fontfamily=SERIF)
    txt(bg, MARGIN + 0.5, 3.64, "pada PT Samudera Indonesia Tbk, 2026\u20132031", 16, INK, fontfamily=SERIF)
    txt(bg, MARGIN + 0.5, 4.75, "Fauzan Azhari Najib", 13, INK, "bold", fontfamily=SERIF)
    txt(bg, MARGIN + 0.5, 5.05, "10 November 2026", 11, ABU_D, fontfamily=SERIF)
    return fig


CONTACT_PUBLIC = [("GitHub", "github.com/Fauzan-azhari"), ("LinkedIn", "linkedin.com/in/fauzan-najib")]


def _contact_private():
    """Kontak tambahan (mis. email) dibaca dari deck_v5/contact.local.json yang TIDAK dilacak git; bila ada, slide penutup versi pribadi ikut dirender."""
    import json
    p = os.path.join(HERE, "contact.local.json")
    return [tuple(x) for x in json.load(open(p, encoding="utf-8"))] if os.path.exists(p) else []


CONTACT = CONTACT_PUBLIC


def _port(bg, x0=6.1, yd=5.68, xq=10.75, yq=5.52):
    """Kapal sandar di dermaga: lambung dan anjungan tanpa muatan di geladak, dua quay crane, gudang, dan tali tambat."""
    from matplotlib.patches import Polygon
    for gx, gw, gh, col in ((11.5, 0.9, 0.8, ABU_L), (12.5, 0.9, 1.1, ABU)):                       # gudang di belakang dermaga
        bg.add_patch(Rectangle((gx, yq - gh), gw, gh, fc=col, ec="none", zorder=0.8))
    # quay crane: kaki portal, balok, boom terangkat dengan rangka diagonal, rumah mesin kuning
    def crane(lx, tip_x, top, z, col):
        for dx in (0.0, 0.75):
            bg.plot([lx + dx, lx + dx], [yq, top + 0.12], color=col, lw=3.2, solid_capstyle="butt", zorder=z)
        bg.add_patch(Rectangle((lx - 0.1, top), 0.95, 0.14, fc=col, ec="none", zorder=z))
        bg.plot([lx + 0.0, lx + 0.75], [yq, top + 0.12], color=col, lw=1.0, zorder=z)
        bg.plot([lx + 0.75, lx + 0.0], [yq, top + 0.12], color=col, lw=1.0, zorder=z)
        yb = top - 0.35
        bg.plot([tip_x, lx + 0.9], [yb - 0.18, yb + 0.1], color=col, lw=2.2, zorder=z)                 # boom atas
        bg.plot([tip_x, lx + 0.9], [yb - 0.0, yb + 0.28], color=col, lw=2.2, zorder=z)                 # boom bawah
        n = 9
        for k in range(n + 1):
            u = k / n; xx = tip_x + u * (lx + 0.9 - tip_x)
            bg.plot([xx, xx], [yb - 0.18 + u * 0.28, yb + u * 0.28], color=col, lw=0.8, zorder=z)
            if k < n:
                u2 = (k + 1) / n; x2 = tip_x + u2 * (lx + 0.9 - tip_x)
                bg.plot([xx, x2], [yb + u * 0.28, yb - 0.18 + u2 * 0.28], color=col, lw=0.8, zorder=z)
        bg.plot([lx + 0.4, lx + 0.4], [top + 0.12, yb + 0.1], color=col, lw=2.2, zorder=z)               # tiang penyangga
        bg.add_patch(Rectangle((lx + 0.5, yb - 0.02), 0.4, 0.26, fc=KUNING if col == ABU_D else ABU_L, ec="none", zorder=z + 0.1))
        bg.plot([tip_x + 0.55] * 2, [yb + 0.02, yb + 0.55], color=col, lw=0.8, zorder=z)              # kabel spreader
        bg.add_patch(Rectangle((tip_x + 0.4, yb + 0.55), 0.3, 0.07, fc=MERAH if col == ABU_D else ABU, ec="none", zorder=z))
    crane(12.1, 9.5, 2.95, 1.0, ABU)
    crane(10.95, 8.1, 3.35, 1.4, ABU_D)
    # kapal
    L = 4.35
    bg.add_patch(Polygon([(x0, yd), (x0 + L, yd), (x0 + L - 0.4, yd + 0.55), (x0 + 0.25, yd + 0.55)], closed=True, fc=INK, ec="none", zorder=2))
    bg.add_patch(Rectangle((x0 + 0.05, yd - 0.04), L - 0.05, 0.07, fc=MERAH, ec="none", zorder=2))
    bg.add_patch(Rectangle((x0 + 0.2, yd - 0.95), 0.62, 0.91, fc="white", ec=ABU_D, lw=0.8, zorder=2))     # akomodasi
    bg.add_patch(Rectangle((x0 + 0.14, yd - 1.12), 0.74, 0.17, fc=ABU_D, ec="none", zorder=2))
    for k in range(3):
        bg.add_patch(Rectangle((x0 + 0.28 + k * 0.19, yd - 0.86), 0.12, 0.09, fc=ABU, ec="none", zorder=2.5))
    bg.add_patch(Rectangle((x0 + 0.42, yd - 1.36), 0.2, 0.24, fc=MERAH, ec="none", zorder=2))
    bg.add_patch(Rectangle((x0 + 0.42, yd - 1.36), 0.2, 0.05, fc=ABU_D, ec="none", zorder=2.5))
    for k in range(4):                                                                                  # penutup palka (kosong)
        bg.add_patch(Rectangle((x0 + 1.1 + k * 0.75, yd - 0.11), 0.68, 0.11, fc=ABU, ec=ABU_D, lw=0.7, zorder=2))
    bg.plot([x0 + L - 0.35] * 2, [yd, yd - 0.7], color=INK, lw=1.6, zorder=2)                           # tiang haluan
    # dermaga: dinding beton, pelat atas, bolder, tali tambat
    bg.add_patch(Rectangle((xq, yq), W - xq, H - yq, fc=ABU_D, ec="none", zorder=6))
    bg.add_patch(Rectangle((xq, yq), W - xq, 0.1, fc=ABU, ec="none", zorder=6.1))
    bg.add_patch(Rectangle((xq + 0.25, yq - 0.1), 0.14, 0.1, fc=INK, ec="none", zorder=6.2))
    pal = [MERAH, ABU_D, ABU, KUNING, MERAH, ABU_D]                                                     # peti kemas hasil bongkar di lapangan penumpukan
    cw, ch = 0.5, 0.32
    for c, n in enumerate((2, 4, 3, 2)):
        for r in range(n):
            bg.add_patch(Rectangle((xq + 0.45 + c * (cw + 0.02), yq - (r + 1) * (ch + 0.015)), cw, ch, fc=pal[(c * 2 + r * 3 + 1) % 6], ec="white", lw=0.9, zorder=6.15))
    bg.plot([x0 + L - 0.15, xq + 0.32], [yd, yq - 0.05], color=INK, lw=0.9, zorder=2.2)


def slide7(D=None, contact=None):
    """Penutup: kapal telah sandar, peti kemas sudah dibongkar ke dermaga, ucapan terima kasih, dan kontak penulis."""
    fig, bg = new_slide()
    _wave(bg, 6.0, 0.06, 4.6, 0.3, ABU_L, shadow=False, z=1)
    _port(bg)
    _wave(bg, 6.2, 0.07, 3.9, 1.6, ABU, z=3)
    _wave(bg, 6.58, 0.09, 5.2, 0.4, MERAH, z=4)
    _wave(bg, 7.05, 0.08, 4.1, 2.4, ABU_D, z=5)
    bg.set_xlim(0, W); bg.set_ylim(H, 0)
    x0 = MARGIN + 0.5
    bg.add_patch(Rectangle((x0, 1.55), 0.55, 0.05, fc=KUNING, ec="none"))
    txt(bg, x0, 2.2, "Thank You", 44, INK, "normal", fontfamily=SERIF)
    yy = 3.2
    for lab, val in (contact or CONTACT):
        if not val:
            continue
        txt(bg, x0, yy, lab, 10, ABU_D, "bold")
        txt(bg, x0 + 1.1, yy, val, 13, INK, fontfamily=SERIF)
        yy += 0.38
    return fig


def _t27():
    return int(round((dt.date(2027, 12, 31) - dt.date(2026, 11, 7)).days / 30.44))


def slide1(D):
    fig, bg = new_slide()
    section(bg, "Executive Summary")
    q1 = P.qfirst(D); pk = P.qpeak(D)
    tr12 = abs(float(D["narr"].set_index("kisah").loc[P.MK_OVER, "tarif"])) * 100
    assert abs(tr12 - 12) < 0.5 and pk[P.MK_OVER] > 3.0
    title(bg, f"Penurunan tarif {idn(tr12, 0)}%, setara FY2024, sudah cukup membawa Net Debt to EBITDA SMDR ke\u00a03,00x paling\u00a0cepat\u00a0{P.ym_label(q1)}")
    P.s1_spine(fig, bg, D, 0.5, 1.85, 12.33)
    implikasi(bg, "Tekanan terkonsentrasi pada covenant leverage; keputusan dapat diambil dengan data Mar 2027.")
    footer(bg, "Laporan keuangan SMDR FY2021\u20139M26; Informasi Tambahan Sukuk Ijarah II\u2013III (rasio yang dipersyaratkan); Drewry WCI; Linerlytica (20 Okt 2026); Kontan (30 Okt 2026); SSL (3 Nov 2026).",
           "Pro forma 30 Sep 2026, bukan proyeksi. Net Debt to EBITDA = (bank + sukuk + sewa) \u00f7 EBITDA, tanpa dikurangi kas; mereproduksi rasio dilaporkan FY2022 (0,66x) dan FY2025 (2,52x).\n"
           "Rasio diukur tiap akhir kuartal atas EBITDA 12 bulan terakhir (tabel rasio juga dilaporkan per 31 Mar); bila tahunan, pengukuran pertama Des 2027. \u221229% = EBITDA 12 bulan skenario Overcapacity (tarif \u221212%) vs TTM.\n"
           "Utang bank di-refinance (rollover; saldo akhir FY2023\u2013FY2025 dan 9M26 stabil). Downside case arus kas = setiap pos pengeluaran di batas terberat historisnya (slide 5).", 2)
    return fig


def slide2(D):
    fig, bg = new_slide()
    section(bg, "Risk")
    m0, m1, c0, c1 = P.ebitda_pcts(D)
    sv = D["v7"]["sev"]
    ratio_oil = m1 / (abs(sv['d_brent_adverse']) / sv['ebitda'] * 100)
    assert 1.8 <= ratio_oil <= 2.3, "judul slide 3: 'dua kali' harus didukung angka"
    title(bg, "Tarif angkut dan volume adalah risiko EBITDA terbesar, sekitar dua\u00a0kali dampak harga\u00a0minyak, dan siklus tarif kini di\u00a0puncak")
    y, h = 1.85, 4.3
    y, h = 1.8, 3.85
    P.r3_cycle_chart(fig, bg, D, 0.5, y, 5.7, h); P.s2_how_much(fig, bg, D, 6.55, y, 6.28, h)
    P.r3_strip(fig, bg, D, 0.5, 5.78, 12.33)
    implikasi(bg, "Pemantauan dimulai dari tarif dan volume; empat risiko operasional perlu data internal agar dapat diukur.")
    footer(bg, "Informasi Tambahan Sukuk III (risiko usaha; pemeringkat); laporan keuangan SMDR; OCE Bank Mandiri (proyeksi makro); SIRI; Linerlytica; FRED; Drewry WCI; perhitungan penulis.",
           f"Pro forma atas TTM Sep 2026. Batang = parameter transmisi tengah; abu muda = hingga batas rentangnya; tanpa probabilitas. Persentil 90 dari 463 bulan tumpang tindih (sekitar 38 tahun independen; persentil 90 tahunan +{idn(sv['brent_p90_annual'] * 100, 0)}%).\n"
           f"Rentang transmisi = elastisitas bunker, pass-through, porsi EBIT rupiah, fleksibilitas biaya. \u201cDua kali\u201d = {idn(m1, 0)}% vs {idn(abs(sv['d_brent_adverse']) / sv['ebitda'] * 100, 0)}% (batas atas Brent persentil 90). WCI\u2013Brent: \u03c1 = {idn(sv['corr_wci_brent'], 2)} (tahunan, n = {sv['n_corr']}; tidak signifikan).", 3)
    return fig


def slide3(D):
    fig, bg = new_slide()
    section(bg, "Scenario")
    bb = D["backtest"]; rr = (bb["terealisasi"] / bb["model"]).clip(upper=1.0)
    title(bg, "Skenario dan model dapat diandalkan: skenario memakai penurunan tarif yang pernah dialami SMDR, dan backtesting menunjukkan model cenderung\u00a0konservatif")
    y, h = 1.85, 4.3
    pc3 = P
    P.s3_reported(fig, bg, D, 0.5, y, 6.0, h); P.s4_back_sens(fig, bg, D, 6.85, y, 5.98, h)
    rz = D["realized"]["tarif_efektif"] * 100
    r24 = float(rr["FY2024"])
    implikasi(bg, f"Angka {idn(abs(D['nd']['rate']) * 100, 1)}% adalah batas konservatif, sebab dampak nyata lebih ringan dari prediksi; layak menjadi threshold pemantauan tarif.")
    footer(bg, "Annual Report SMDR 2023\u20132025 (tarif hub dan rute); laporan keuangan SMDR FY2022\u2013FY2025 (pendapatan, biaya, EBITDA); perhitungan penulis.",
           "Tarif efektif = (1 + \u0394 pendapatan angkutan) \u00f7 (1 + \u0394 volume) \u2212 1; FY2023 = koreksi dari puncak FY2022. Tarif hub dan rute lain FY2023\u2013FY2024: \u221239% s.d. +14%.\n"
           "Tarif efektif = proksi harga (bauran rute dan charter). Skenario mulai Okt 2026. Model linier, deterministik; biaya tidak ikut turun. Headroom penurunan tarif = 11,8% \u00f7 (aktual sebagai % prediksi).", 4)
    return fig


def slide4(D):
    fig, bg = new_slide()
    section(bg, "Result")
    c, a_ = P.v7(D), P.v7(D, "adverse")
    pk = P.qpeak(D); q1 = P.qfirst(D)
    mk = pk[[P.MK_DEM, P.MK_OVER, P.MK_WEAK]]
    assert int((mk > 3.0).sum()) == 2, "judul: dua skenario pasar melewati 3,00x"
    assert (c[["cover_FY2027", "cover_FY2028"]] > 1.10).all().all() and (c.current_ratio_min > 1.10).all() and c.first_below.isna().all(), "judul: rasio lain memenuhi pada parameter tengah"
    fb = a_["first_below"].dropna().min()
    lag = (pd_period(fb) - pd_period(q1))
    crfy = a_.loc[P.MK_WEAK, "current_ratio_breach_fy"]; lag_cr = pd_period(f"{crfy[2:]}-12") - pd_period(q1)
    title(bg, f"Tekanan penurunan tarif terkonsentrasi pada covenant leverage: Net Debt to EBITDA melewati 3,00x per\u00a0{P.ym_label(q1)}, sementara DSCR, Current Ratio, dan kas tetap\u00a0memenuhi")
    P.r5_quarterly(fig, bg, D, 0.5, 1.8, 6.0, 4.1)
    P.s5_ratios(fig, bg, D, 6.8, 1.8, 6.03, 1.4)
    P.s4_fan(fig, bg, D, 6.8, 3.62, 6.03, 2.33)
    lead = pd_period(q1) - pd_period("2027-03"); assert lead == 6
    implikasi(bg, f"Pemantauan covenant dapat diprioritaskan pada Net Debt to EBITDA; data Mar 2027 memberi sinyal enam bulan lebih awal.", y=6.3)
    tq = D["v7"]["tornado"].head(4); nm = {"maintenance_capex": "pemeliharaan", "lease_principal": "sewa", "deposit_availability": "deposito anak", "ocf_conversion": "konversi"}
    assert set(tq.parameter) == set(nm), "empat pendorong kas terbesar berubah: perbarui label"
    drv = ", ".join(f"{nm[r.parameter]} {idn(r.d_min_liq, 0)}" for r in tq.itertuples())
    dd = D["v7"]["dscr"]; qq = D["v7"]["q"]; dws = qq[qq.case == "central"]["dscr_with_sukuk"].min(); rec = min(D["v7"]["recover_fy2025"].values())
    footer(bg, "Laporan keuangan SMDR FY2021\u20139M26; Informasi Tambahan Sukuk Ijarah II\u2013III (rasio yang dipersyaratkan dalam perjanjian kredit); perhitungan penulis.",
           f"Pro forma 30 Sep 2026; rasio per akhir kuartal atas EBITDA 12 bulan terakhir. Utang bank di-refinance (rollover; saldo akhir FY2023\u2013FY2025 dan 9M26 USD 185\u2013224 juta); tanpa itu {idn(c.loc[P.MK_OVER, 'nd_FY2027_amortisasi'], 2)}x dan {idn(c.loc[P.MK_WEAK, 'nd_FY2027_amortisasi'], 2)}x. Pembanding: EBITDA FY2024 aktual pada utang hari ini = {idn(D['v7']['hist'].loc['FY2024', 'nd'], 2)}x.\n"
           f"DSCR = EBITDA \u00f7 (penyebut tersirat DSCR dilaporkan, USD {idn(dd['den'], 0)} juta, + pokok sukuk 12 bln, laporan audit tahunan). Bila pokok sukuk dihitung per kuartal: terburuk {idn(dws, 2)}x; definisi perlu konfirmasi.\n"
           f"Downside case arus kas = tiap pos pengeluaran di batas terberat historis (pendorong: {drv} USD juta). Bila EBITDA hanya pulih ke FY2025: kas terendah USD {idn(rec, 0)} juta.", 5)
    return fig


def pd_period(ym):
    return int(ym[:4]) * 12 + int(ym[5:])


def slide5(D):
    fig, bg = new_slide()
    section(bg, "Next Step")
    qq = D["v7"]["q"]; m3 = qq[(qq.case == "central") & (qq.quarter == "2027-03")].set_index("skenario")["nd"]
    hit = m3[[P.MK_OVER, P.MK_WEAK]]; rest = m3.drop([P.MK_OVER, P.MK_WEAK])
    assert rest.max() < P.EW < hit.min(), "early warning memisahkan skenario dengan margin di kedua sisi"
    title(bg, f"Hasil penelitian dapat diturunkan menjadi empat KRI beserta threshold Alert dan Breach; data\u00a0Mar\u00a02027 menjadi titik evaluasi opsi pengelolaan leverage sebelum pengukuran\u00a0{P.ym_label(P.qfirst(D))}")
    y, h = 1.8, 4.35
    P.s5_kri(fig, bg, D, 0.5, y, 5.5, h); P.s5_timeline(fig, bg, D, 6.3, y, 6.53, h)
    mt = D["v7"]["mit"]; cm = mt[mt.case == "central"].set_index(["skenario", "paydown", "dividend_stop"])
    o54, w107, w107d = cm.loc[(P.MK_OVER, 54.0, False)], cm.loc[(P.MK_WEAK, 107.0, False)], cm.loc[(P.MK_WEAK, 107.0, True)]
    assert o54.current_ratio_min > 1.21 and w107.current_ratio_min < 1.10 and w107d.current_ratio_min > 1.10, "implikasi: 54 cukup; 107 butuh henti dividen"
    implikasi(bg, "Opsi pengelolaan leverage teruji: USD 54 juta untuk Overcapacity, USD 107 juta dan penahanan dividen untuk skenario terburuk.", y=6.3)
    footer(bg, "Laporan keuangan SMDR; Informasi Tambahan Sukuk Ijarah II\u2013III; Drewry WCI; perhitungan penulis.",
           f"Threshold Early Warning {idn(P.EW, 2)}x memisahkan skenario pada data Mar 2027 ({idn(hit.min(), 2)}\u2013{idn(hit.max(), 2)}x vs \u2264 {idn(rest.max(), 2)}x, dibulatkan ke bawah). Tanpa penahanan dividen, pelunasan 107 menurunkan Current Ratio ke {idn(w107.current_ratio_min, 2)}x.\n"
           f"Sasaran pelunasan {idn(P.ND_SASARAN, 2)}x dan Alert DSCR {idn(P.DSCR_ALERT, 2)}x = headroom 10% di bawah batas; Alert kas = 2 bulan biaya operasi. WCI = posisi siklus global (> +50%), tak selalu sejalan tarif SMDR (2024: +127% vs \u221212%).\n"
           "Indikator internal = yield dan volume per TEU. Bila covenant diukur tahunan, pengukuran pertama Des 2027. Tahapan, pemilik, dan opsi adalah usulan untuk didiskusikan dengan manajemen.", 6)
    return fig


def slide6(D=None):
    """Disclaimer bergaya template BCG: judul serif di kiri, garis vertikal tipis, paragraf kecil di kanan, kapsul nomor halaman."""
    import textwrap
    from matplotlib.patches import FancyBboxPatch
    fig, bg = new_slide()
    fig.patch.set_facecolor("#FBFBFA")
    bg.add_patch(Rectangle((0, 0), W, H, fc="#FBFBFA", ec="none", zorder=0))
    paras = [("Sifat dokumen", "Dokumen ini merupakan riset mandiri penulis yang disusun sebagai bahan diskusi. Dokumen ini bukan dokumen resmi dan tidak merepresentasikan pandangan PT Samudera Indonesia Tbk maupun entitas anaknya. Isinya tidak dimaksudkan sebagai nasihat hukum, akuntansi, perpajakan, investasi, maupun kredit, dan sebaiknya dibaca bersama penjelasan lisan penulis."),
             ("Data", "Seluruh analisis memakai data publik: laporan keuangan dan Annual Report SMDR; Informasi Tambahan Sukuk Ijarah II\u2013III, termasuk rasio yang dipersyaratkan dalam perjanjian kredit; Drewry World Container Index; FRED (harga Brent dan kurs USD/IDR); proyeksi makro dan Industry Rating & Outlook 2026 Angkutan Laut Kontainer dari OCE Bank Mandiri; serta Linerlytica, Samudera Indonesia Research Initiative (SIRI), dan pemberitaan media. Sumber telah diverifikasi sejauh memungkinkan, tetapi kelengkapan data pihak ketiga tidak dapat dijamin. Informasi berlaku per tanggal penyusunan."),
             ("Sifat hasil", "Hasil merupakan stress test pro forma atas posisi keuangan 30 September 2026 (belum diaudit) dengan asumsi yang dinyatakan eksplisit. Hasil ini bukan proyeksi, ramalan, atau pernyataan probabilitas, dan tidak menyimpulkan kepatuhan maupun pelanggaran covenant. Besaran skenario dikalibrasi pada pergerakan historis tarif SMDR, Brent, dan kurs; skenario normalisasi rute belum dapat dikalibrasi sehingga tidak ditampilkan. Model transmisi bersifat linier dan deterministik, dengan backtesting terbatas pada FY2023\u2013FY2025. Posisi siklus WCI adalah indikator posisi, bukan ramalan arah tarif."),
             ("Keterbatasan", "Penulis tidak memiliki akses ke data internal perusahaan. Net Debt to EBITDA mereproduksi rasio yang dilaporkan (FY2022 dan FY2025), dan DSCR dibaca pada basis yang dilaporkan perusahaan. Tiga asumsi belum terkonfirmasi: frekuensi pengukuran covenant (diasumsikan kuartalan sebagai pendekatan konservatif), refinancing angsuran bank, dan belanja modal kapal baru di luar tiga milestone dana sukuk. Empat risiko operasional belum dikuantifikasi karena memerlukan data internal. Batas kas minimum, threshold KRI, dan tahapan tindak lanjut merupakan usulan untuk didiskusikan. Data, kode, dan notebook pendukung tersedia untuk direplikasi.")]
    lh, gap, wrapn, hd = 0.175, 0.24, 118, 0.21
    blocks = [(lab, textwrap.wrap(p, wrapn)) for lab, p in paras]
    total = sum(hd + len(b) * lh for _, b in blocks) + gap * (len(blocks) - 1)
    y0 = 3.75 - total / 2
    txt(bg, 0.9, 3.75, "Disclaimer", 40, INK, fontfamily=SERIF)
    bg.plot([4.55, 4.55], [y0 - 0.1, y0 + total + 0.05], color=ABU_D, lw=1.0)
    yy = y0
    for lab, b in blocks:
        txt(bg, 4.95, yy + lh / 2, lab, 8.8, INK, "bold")   # label paragraf
        yy += hd
        for ln in b:
            txt(bg, 4.95, yy + lh / 2, ln, 8.4, "#3A3A3A")
            yy += lh
        yy += gap
    bg.add_patch(FancyBboxPatch((12.23, 6.98), 0.52, 0.22, boxstyle="round,pad=0,rounding_size=0.11", fc="none", ec=ABU_D, lw=0.8))
    txt(bg, 12.49, 7.09, "1", 7.5, ABU_D, ha="center")
    return fig


if __name__ == "__main__":
    D = load()
    os.makedirs(os.path.join(HERE, "out"), exist_ok=True)
    only = [int(a) for a in sys.argv[1:]] or [0, 1, 2, 3, 4, 5, 6, 7]
    # urutan berkas: 00 cover, 01 Disclaimer, 02 Executive Summary, 03 Risk, 04 Scenario, 05 Result, 06 Next Step, 07 Thank You
    for n, f in ((0, slide0), (1, slide6), (2, slide1), (3, slide2), (4, slide3), (5, slide4), (6, slide5), (7, slide7)):
        if n in only:
            fig = f(D)
            fig.savefig(os.path.join(HERE, "out", f"slide_{n:02d}.png"), dpi=150, facecolor="white")
            if n == 7 and _contact_private():   # versi dengan email: out_private/ tidak dilacak git
                os.makedirs(os.path.join(HERE, "out_private"), exist_ok=True)
                slide7(D, _contact_private() + CONTACT_PUBLIC).savefig(os.path.join(HERE, "out_private", "slide_07.png"), dpi=150, facecolor="white")
    print("ok")
