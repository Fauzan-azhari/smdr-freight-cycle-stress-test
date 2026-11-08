"""Generator naskah: membangun notebooks/paper.ipynb (artikel gaya jurnal ekonomi) dari marts dan data kanonik.

Angka pada teks TIDAK diketik: setiap token @kunci:d@ diganti nilai dari data saat membangun (d = jumlah desimal, format Indonesia).
Sel kode (tabel, gambar, verifikasi persamaan) dieksekusi dan disimpan dengan keluarannya.

Jalankan dari root repo:  PYTHONPATH=src .venv/bin/python notebooks/build_paper.py
"""
import os
import re
import sys

import nbformat as nbf
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
from smdr import baseline, covenant_band as cb, datapaths as dp, freight  # noqa: E402
from smdr.transition import covenants as cvn, robustness as rb, transmission as tr  # noqa: E402

OUT = os.path.join(ROOT, "notebooks", "paper.ipynb")


def idn(x, d=1):
    s = f"{abs(x):,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return ("−" if x < 0 else "") + s


# ================================================================ angka (N)
def load_numbers():
    N = {}
    sr = pd.read_csv(dp.table("scenario_results.csv"))
    cq = pd.read_csv(dp.table("covenant_quarterly.csv"))
    mt = pd.read_csv(dp.table("mitigation_tests.csv"))
    bt = pd.read_csv(dp.table("backtest.csv")).set_index("periode")
    ht = pd.read_csv(dp.table("historical_test.csv")).set_index("index")
    sev = pd.read_csv(dp.table("severity.csv")).set_index("metric")["value"]
    tor = pd.read_csv(dp.table("cash_tornado.csv"))
    bridge = pd.read_csv(dp.table("baseline_bridge.csv")).set_index("metric")["reconciled_value"]
    w = baseline.load_wide()
    b = cvn.base_position(w)
    from smdr.transition import cashflow as cf
    inp = cf._init()
    R = lambda sk, case, col: float(sr[(sr.skenario == sk) & (sr.case == case)].iloc[0][col])
    DEM, OVR, WRS = "Permintaan melemah", "Kelebihan kapasitas", "Permintaan lemah dan kelebihan kapasitas"
    N.update(rev=inp["revenue"], ebitda=inp["ebitda"], ebit=inp["ebit"], bank=b["bank"], sukuk=b["sukuk"], lease=b["lease"], debt=b["bank"] + b["sukuk"] + b["lease"],
             cash=inp["opening_cash"], deposits=inp["deposits"], liq0=inp["opening_cash"] + inp["deposits"], opex=inp["opex_month"], th_cash=float(inp["opex_month"]),
             nd_now=(b["bank"] + b["sukuk"] + b["lease"]) / inp["ebitda"], ca=b["ca"], cl=b["cl"], ocf_ttm=inp["ocf_ttm"], interest_ttm=inp["interest_ttm"])
    nh = {p: cvn.reported_nd_ebitda(w, p, cb.ebitda_operating(w, p) / 1e6) for p in ("FY2022", "FY2023", "FY2024", "FY2025")}
    N.update(nd22=nh["FY2022"], nd23=nh["FY2023"], nd24=nh["FY2024"], nd25=nh["FY2025"])
    N.update(den0=rb.dscr_denominator(w)["den"], hist24=ht.loc["FY2024", "nd"], hist24_e=ht.loc["FY2024", "ebitda"], hist25=ht.loc["FY2025", "nd"], hist23=ht.loc["FY2023", "nd"])
    for key, sk in (("dem", DEM), ("ovr", OVR), ("wrs", WRS), ("base", "Dasar"), ("energy", "Energi bertahan"), ("comb", "Gabungan")):
        for case in ("central", "adverse"):
            c = case[0]
            N[f"nd27_{key}_{c}"] = R(sk, case, "nd_FY2027"); N[f"nd28_{key}_{c}"] = R(sk, case, "nd_FY2028"); N[f"cov27_{key}_{c}"] = R(sk, case, "cover_FY2027")
            N[f"cr_{key}_{c}"] = R(sk, case, "current_ratio_min"); N[f"liq_{key}_{c}"] = R(sk, case, "min_liquidity"); N[f"e27_{key}_{c}"] = R(sk, case, "ebitda_FY2027")
            N[f"pay_{key}_{c}"] = R(sk, case, "pelunasan_ke_2_7x")
    for key, sk in (("ovr", OVR), ("wrs", WRS)):
        N[f"qpk_{key}_c"] = float(cq[(cq.skenario == sk) & (cq.case == "central")].nd.max()); N[f"qpk_{key}_a"] = float(cq[(cq.skenario == sk) & (cq.case == "adverse")].nd.max())
    mar = cq[(cq.quarter == "2027-03") & (cq.case == "central")].set_index("skenario")["nd"]
    N.update(m3_wrs=mar[WRS], m3_ovr=mar[OVR], m3_rest=mar.drop([WRS, OVR]).max(), ew=2.45)
    N["first_q"] = "Sep 2027"
    belowa = sr[(sr.skenario == WRS) & (sr.case == "adverse")].iloc[0]
    N["cr_breach_fy_wrs"] = belowa["current_ratio_breach_fy"]; N["liq_first_wrs"] = belowa["first_below"]
    bl = sr[(sr.skenario == OVR) & (sr.case == "adverse")].iloc[0]; N["liq_first_ovr"] = bl["first_below"]
    mm = lambda sk, case, pay, stop: mt[(mt.skenario == sk) & (mt.case == case) & (mt.paydown == pay) & (mt.dividend_stop == stop)].iloc[0]
    N.update(mit54_ovr_nd=mm(OVR, "central", 54.0, False).nd_FY2027, mit54_ovr_cr=mm(OVR, "central", 54.0, False).current_ratio_min, mit54_ovr_liq=mm(OVR, "central", 54.0, False).min_liquidity,
             mit107_wrs_nd=mm(WRS, "central", 107.0, False).nd_FY2027, mit107_wrs_cr=mm(WRS, "central", 107.0, False).current_ratio_min,
             mit107d_wrs_nd=mm(WRS, "central", 107.0, True).nd_FY2027, mit107d_wrs_cr=mm(WRS, "central", 107.0, True).current_ratio_min, mit107d_wrs_liq=mm(WRS, "central", 107.0, True).min_liquidity)
    for p in ("FY2023", "FY2024", "FY2025"):
        N[f"bt_pred_{p}"] = bt.loc[p, "model"]; N[f"bt_act_{p}"] = bt.loc[p, "terealisasi"]; N[f"bt_x_{p}"] = bt.loc[p, "model"] / bt.loc[p, "terealisasi"]
        N[f"bt_rate_{p}"] = bt.loc[p, "tarif_efektif"] * 100
    a = tr.assumptions()
    hr = (N["debt"] / cvn.TH_ND - N["ebitda"]) / inp["rev_by_service"]["freight_income"]
    N["headroom"] = abs(hr) * 100; N["headroom_24"] = abs(hr) * 100 / (N["bt_act_FY2024"] / N["bt_pred_FY2024"]); N["headroom_23"] = abs(hr) * 100 / (N["bt_act_FY2023"] / N["bt_pred_FY2023"])
    N["freight"] = inp["rev_by_service"]["freight_income"]; N["min_ebitda"] = N["debt"] / cvn.TH_ND
    f = lambda k: float(sev[k])
    N.update(brent_p90=f("brent_p90") * 100, brent_p90a=f("brent_p90_annual") * 100, n_brent=int(f("n_brent")), brent_start=str(int(f("brent_start"))), n_brent_a=int(f("n_brent_annual")), fx_p90=f("fx_p90") * 100, n_fx=int(f("n_fx")),
             d_brent=-f("d_brent"), d_brent_a=-f("d_brent_adverse"), d_fx=-f("d_fx"), d_fx_a=-f("d_fx_adverse"), d_rate=-f("d_rate"), corr=f("corr_wci_brent"), n_corr=int(f("n_corr")),
             sev_brent_pct=-f("d_brent") / N["ebitda"] * 100, sev_brent_pct_a=-f("d_brent_adverse") / N["ebitda"] * 100, sev_fx_pct=-f("d_fx") / N["ebitda"] * 100, sev_fx_pct_a=-f("d_fx_adverse") / N["ebitda"] * 100,
             sev_rate_pct=-f("d_rate") / N["ebitda"] * 100, brent_oct=f("brent_oct"), brent_ttm=f("brent_ttm"))
    for k, row in zip(("t1", "t2", "t3", "t4"), tor.head(4).itertuples()):
        N[k] = -row.d_min_liq
    N["tor_label"] = ", ".join(l[0].lower() + l[1:] for l in tor.head(4).label)
    wci = pd.read_csv(dp.table("wci_composite_weekly.csv"), parse_dates=["date"]).set_index("date")["wci"]
    pos = freight.position(wci)
    N.update(wci_now=pos["terkini"], wci_vs=pos["vs_rata_panjang"] * 100, wci_pct=pos["persentil"] * 100, wci_date=str(wci.index[-1].date()), wci_n=len(wci))
    # parameter transmisi
    for p in a.index:
        N[f"op_{p}_lo"], N[f"op_{p}_c"], N[f"op_{p}_hi"] = float(a.loc[p, "low"]), float(a.loc[p, "central"]), float(a.loc[p, "high"])
    ca_ = cf.assumptions()
    for p in ca_.index:
        N[f"ca_{p}_lo"], N[f"ca_{p}_c"], N[f"ca_{p}_hi"] = float(ca_.loc[p, "low"]), float(ca_.loc[p, "central"]), float(ca_.loc[p, "high"])
    N["fs_nd_rows"] = len(pd.read_csv(dp.table("fs_long.csv"))); N["fs_nd"] = int((pd.read_csv(dp.table("fs_long.csv")).status == "nd").sum())
    N["raw_rows"] = len(pd.read_csv(dp.table("idx_line_items.csv"))); N["parity"] = int((pd.read_csv(dp.table("fs_long.csv")).status == "reported").sum())
    N["safe_nd"] = 2.70; N["den_sukuk27"] = cvn.SUKUK_DUE_12M["FY2027"]
    return N


TOKEN = re.compile(r"@([A-Za-z0-9_]+)(?::(\d)(e)?)?@")


def fill(text, N):
    def rep(m):
        k, d, en = m.group(1), m.group(2), m.group(3)
        v = N[k]
        if isinstance(v, str):
            return v
        if en:   # format Inggris: titik desimal, koma ribuan
            return ("\u2212" if v < 0 else "") + f"{abs(float(v)):,.{int(d) if d is not None else 1}f}"
        return idn(float(v), int(d) if d is not None else 1)
    return TOKEN.sub(rep, text)


# ================================================================ isi naskah
CELLS = []
md = lambda t: CELLS.append(("md", t))
code = lambda t: CELLS.append(("code", t))

md(r"""# Sensitivitas Pemenuhan *Covenant* dan Likuiditas terhadap Siklus *Freight Rate*
## Stress Test Berbasis Skenario dan *Backtesting* pada PT Samudera Indonesia Tbk, 2026–2031

**Fauzan Azhari Najib** · 10 November 2026

---

**Abstract.** This study examines how a decline in container freight rates affects financial covenant compliance and liquidity at PT Samudera Indonesia Tbk (SMDR), an Indonesian shipping and logistics group, using only public data as of 30 September 2026. A hybrid design is adopted: statistics calibrate the size of shocks, and a structural accounting model transmits freight-rate, volume, fuel-cost, exchange-rate and interest-rate shocks to EBITDA, monthly cash flows and covenant ratios through December 2031. Model predictions are backtested against realised EBITDA changes in FY2023–FY2025. The results show that stress concentrates on one covenant. A 12% decline in the effective freight rate, equal to the 2024 decline, lifts Net Debt to EBITDA from @nd_now:2e@x to @nd27_ovr_c:2e@x in FY2027, and @nd27_wrs_c:2e@x when combined with a 5% volume decline, against a 3.00x limit. The first quarterly test above the limit falls in @first_q@ in both cases. Under central assumptions the DSCR and the Current Ratio stay above their 1.10x minimums in every scenario, and cash plus deposits stay above the proposed minimum. Under a downside cash-flow case, in which every cash item sits at its most adverse historical value, liquidity falls below the minimum from @liq_first_wrs@ in the worst scenario, @lag_liq:0e@ months after the leverage covenant is first breached. The model overstated realised impacts by @bt_x_FY2023:1e@ times in FY2023 and @bt_x_FY2024:1e@ times in FY2024, so the tariff headroom of @headroom:1e@% is conservative. An early-warning threshold of @ew:2e@x on March 2027 data separates the scenarios that later breach from those that do not, @lead:0e@ months before the first test. Results are pro forma estimates under explicit assumptions, not forecasts or statements of probability.

**Kata kunci:** *freight rate*; *covenant* keuangan; *stress test*; risiko likuiditas; pelayaran kontainer; Indonesia  

---""")

md(r"""## 1. Pendahuluan

### 1.1 Latar belakang

Pelayaran kontainer adalah industri siklis yang pendapatannya bergerak mengikuti tarif angkut (*freight rate*), sedangkan struktur pembiayaannya relatif tetap. Siklus tarif dipengaruhi pertumbuhan perdagangan, pasokan kapal, dan gangguan rute (Stopford, 2009). Pada indeks komposit Drewry (*World Container Index*, WCI), rata-rata tahunan melonjak dari sekitar @wci_2020:0@ pada 2020 menjadi @wci_2021:0@ pada 2021, turun ke @wci_2023:0@ pada 2023, lalu naik lagi ke @wci_2024:0@ pada 2024. Pada 5 November 2026 indeks berada di @wci_now:0@, atau @wci_vs:0@% di atas rata-rata 52 pekan terakhir.

Bagi perusahaan yang memiliki utang bank, sukuk, dan sewa kapal, ayunan tarif semacam ini diteruskan ke pembiayaan melalui *covenant*, yaitu syarat keuangan dalam perjanjian kredit. *Covenant breach* memindahkan hak kendali tertentu kepada kreditur; pada perusahaan Amerika Serikat, *covenant violation* semacam itu dilaporkan oleh 10% sampai 20% perusahaan nonkeuangan dalam setahun, dan setelahnya perusahaan memangkas belanja modal, akuisisi, utang, dan pembayaran kepada pemegang saham (Nini, Smith, dan Sufi, 2012; Chava dan Roberts, 2008). Karena itu, jarak antara posisi keuangan saat ini dan batas *covenant* menentukan ruang gerak manajemen, bukan sekadar angka akuntansi.

PT Samudera Indonesia Tbk (SMDR) adalah grup pelayaran dan logistik yang terdaftar di Bursa Efek Indonesia. Pada 30 September 2026, pendapatan 12 bulan terakhir (*trailing twelve months*, TTM) mencapai USD @rev:0@ juta, EBITDA operasi USD @ebitda:0@ juta, dan rasio *Net Debt to EBITDA* @nd_now:2@x terhadap batas 3,00x. EBITDA operasi turun dari USD @e22:0@ juta pada FY2022 menjadi USD @e23:0@ juta pada FY2023 dan USD @e24:0@ juta pada FY2024, sejalan dengan penurunan tarif efektif sebesar @bt_rate_FY2023_a:0@% (FY2023) dan @bt_rate_FY2024_a:0@% (FY2024).

### 1.2 Rumusan masalah dan tujuan

Penelitian ini menjawab satu pertanyaan utama: **seberapa besar penurunan tarif angkut dan volume yang dapat ditanggung SMDR sebelum *covenant* dan likuiditasnya tertekan, dan *covenant* mana yang tertekan lebih dahulu?** Pertanyaan itu dirinci menjadi empat:

1. Seberapa besar penurunan tarif yang membawa *Net Debt to EBITDA* ke batas 3,00x?
2. Apakah *Debt Service Coverage Ratio* (DSCR), *Current Ratio*, dan likuiditas tetap memenuhi batas pada skenario yang sama?
3. Apakah model yang dipakai cukup andal, diuji terhadap dampak yang benar-benar terjadi pada FY2023–FY2025?
4. Indikator apa yang dapat berfungsi sebagai *Early Warning* sebelum pengujian *covenant* pertama yang mengalami *breach*?

Tujuan penelitian adalah mengukur ketahanan *covenant* dan likuiditas, mengidentifikasi urutan tekanan, dan menurunkan *Key Risk Indicator* (KRI) beserta *threshold* Alert dan Breach.

### 1.3 Kontribusi

Penelitian ini memberi tiga kontribusi. **Pertama**, ia menghubungkan siklus tarif dengan kepatuhan *covenant* dan likuiditas dalam satu kerangka yang dapat direplikasi dari data publik. **Kedua**, ia menyajikan *backtesting* terhadap tiga tahun realisasi, sehingga klaim "model konservatif" diperiksa, bukan diasumsikan. **Ketiga**, seluruh angka, data, kode, dan model Excel tersedia terbuka, dan setiap angka pada naskah ini dihitung ulang dari data saat naskah dibangun.

### 1.4 Proposisi yang diuji

Karena rancangannya berbasis skenario, bukan inferensi statistik, penelitian ini menguji *proposisi*, bukan hipotesis:

- **P1.** Tekanan penurunan tarif terkonsentrasi pada *covenant leverage* (*Net Debt to EBITDA*); DSCR, *Current Ratio*, dan kas lebih tahan.
- **P2.** Prediksi model tidak meremehkan dampak aktual pada FY2023–FY2025.
- **P3.** *Threshold Early Warning* (EW) dapat dikalibrasi pada data kuartal pertama sebelum pengujian *covenant* untuk memisahkan skenario yang kelak mengalami *breach* dari yang tidak.

Penelitian ini tidak menyatakan probabilitas terjadinya skenario mana pun. Seluruh hasil bersifat pro forma atas posisi 30 September 2026.""")

md(r"""## 2. Tinjauan Pustaka dan Kerangka Konseptual

### 2.1 Siklus pelayaran dan tarif

Stopford (2009) menggambarkan pasar pelayaran sebagai sistem yang digerakkan oleh permintaan angkutan, pasokan armada, dan keterlambatan penyesuaian pasokan: kapal baru dipesan saat tarif tinggi dan tiba saat permintaan sudah melemah, sehingga tarif berayun lebih lebar daripada permintaan. Implikasinya bagi penelitian ini bersifat praktis. Posisi tarif saat ini (@wci_vs:0@% di atas rata-rata 52 pekan; Gambar 1) adalah informasi tentang *posisi dalam siklus*, bukan ramalan arah tarif. Indeks global juga tidak otomatis mencerminkan tarif yang diterima pelayaran domestik: pada 2024, WCI naik @wci_g24:0@% sedangkan tarif efektif SMDR turun @bt_rate_FY2024_a:0@%. Karena itu tarif efektif SMDR, bukan WCI, dipakai sebagai besaran yang diguncang pada model.""")

code(r"""wci = pd.read_csv(dp.table("wci_composite_weekly.csv"), parse_dates=["date"]).set_index("date")["wci"]
a4, a52 = wci.rolling(4).mean(), wci.rolling(52).mean(); dev = a4 / a52 - 1
fig, ax = plt.subplots(figsize=(9.4, 4.4)); fstyle(ax); ftitle(ax, "Drewry World Container Index, komposit mingguan (USD per FEU)")
YM = wci.max() * 1.12
ax.fill_between(wci.index, 0, YM, where=(dev >= 0.5).reindex(wci.index).fillna(False).values, color="#ECEDEE", lw=0, zorder=0)
ax.plot(wci.index, wci.values, color=INK, lw=1.4, zorder=3); ax.plot(a52.index, a52.values, color=ABU_D, lw=1.2, ls=(0, (4, 2)), zorder=2)
pk = wci.idxmax(); ax.annotate("Puncak %s: %s" % (pk.strftime("%b %Y"), idn(wci.max(), 0)), xy=(pk, wci.max()), xytext=(pk + pd.Timedelta(days=330), wci.max() * 0.97), fontsize=8.6, color=INK, fontweight="bold", va="top", arrowprops=dict(arrowstyle="-", color=ABU_D, lw=0.8))
ax.plot([wci.index[-1]], [wci.iloc[-1]], "o", color=MERAH, mec=INK, ms=6.5, zorder=5)
ax.annotate("%s: %s\n(+%s%% vs rata-rata 52 pekan)" % (wci.index[-1].strftime("%d %b %Y").lstrip("0"), idn(wci.iloc[-1], 0), idn((wci.iloc[-4:].mean() / wci.iloc[-52:].mean() - 1) * 100, 0)), xy=(wci.index[-1], wci.iloc[-1]), xytext=(wci.index[-1] - pd.Timedelta(days=1150), 6900), fontsize=8.6, color=MERAH, fontweight="bold", va="top", arrowprops=dict(arrowstyle="-", color=MERAH, lw=0.8))
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
ax.legend(handles=[Line2D([0], [0], color=INK, lw=1.4, label="WCI mingguan"), Line2D([0], [0], color=ABU_D, lw=1.2, ls=(0, (4, 2)), label="Rata-rata 52 pekan"),
                   Patch(color="#ECEDEE", label="Rata-rata 4 pekan \u2265 +50% di atas rata-rata 52 pekan")], loc="upper left", bbox_to_anchor=(0.0, 0.99), frameon=False, fontsize=8.6, labelcolor=ABU_D)
ax.set_ylim(0, YM); ax.set_xlim(wci.index[0], wci.index[-1] + pd.Timedelta(days=60)); plt.tight_layout(); plt.show()
caption_below("Gambar 1. Drewry World Container Index, komposit mingguan", "Sumber: Drewry World Container Index (atribusi: Source: Drewry World Container Index); perhitungan penulis. Posisi dalam siklus, bukan ramalan arah tarif.")""")

md(r"""### 2.2 *Sticky cost*

Anderson, Banker, dan Janakiraman (2003) menunjukkan bahwa biaya penjualan, umum, dan administrasi naik rata-rata 0,55% untuk setiap kenaikan penjualan 1%, tetapi turun hanya 0,35% untuk setiap penurunan penjualan 1% (*sticky costs*). Pada pelayaran, asimetri serupa terlihat pada SMDR: pada FY2023 pendapatan turun jauh lebih dalam daripada biaya jasa. Model ini menangkapnya dengan parameter *cost flexibility* ke bawah (@op_cost_flex_down_c:2@ pada asumsi tengah, rentang @op_cost_flex_down_lo:2@–@op_cost_flex_down_hi:2@), sedangkan pada kenaikan volume biaya diasumsikan mengikuti penuh.

### 2.3 *Covenant* dan kendali kreditur

Dichev dan Skinner (2002) menemukan bahwa pemberi pinjaman swasta menetapkan *covenant* dengan ketat, *technical violation* sering terjadi, dan *violation* tidak selalu menandakan kesulitan keuangan. Chava dan Roberts (2008) menunjukkan bahwa belanja modal turun tajam setelah *covenant violation*, dan Nini, Smith, dan Sufi (2012) menemukan bahwa perusahaan yang mengalami *violation* mengurangi akuisisi, belanja modal, utang, dan pembayaran kepada pemegang saham. Rangkuman ini memberi dasar bagi dua pilihan rancangan: (i) *covenant* diperlakukan sebagai titik keputusan, bukan sekadar rasio; dan (ii) opsi pengelolaan *leverage* yang diuji (pelunasan sebagian utang bank dan penahanan dividen) meniru tindakan yang secara empiris diambil perusahaan setelah *violation*, tetapi dilakukan sebelum *breach*.

### 2.4 *Stress test*

Sorge (2004) dan Borio, Drehmann, dan Tsatsaronis (2014) mengulas kekuatan dan kelemahan *stress test* makro. Borio dkk. menyimpulkan bahwa *stress test* makro dengan teknologi saat ini kurang cocok sebagai alat *Early Warning* dan lebih efektif untuk manajemen krisis. Dua implikasi diterapkan di sini. **Pertama**, hasil *stress test* dibaca sebagai ukuran sensitivitas dan urutan tekanan, bukan prediksi. **Kedua**, *threshold* EW pada Bab 5 diperlakukan sebagai usulan awal yang harus dikalibrasi ulang dengan data kuartalan internal, bukan sebagai penanda yang sudah teruji.

### 2.5 Kerangka konseptual

Rantai transmisi yang diuji adalah:

> penurunan tarif dan volume → EBITDA → rasio *covenant* (*Net Debt to EBITDA*, DSCR, *Current Ratio*) dan kas → opsi pengelolaan *leverage*.

Rantai ini bersifat akuntansi dan terstruktur (bukan hubungan statistik), sehingga setiap mata rantai dapat diperiksa terhadap laporan keuangan.""")

md(r"""## 3. Metodologi

### 3.1 Rancangan hibrida dan alasan tidak memakai ekonometrika sebagai inti

Penelitian ini memakai rancangan hibrida: **statistik** untuk mengkalibrasi besaran guncangan, dan **model akuntansi terstruktur** untuk meneruskannya ke EBITDA, kas, dan rasio. Model ekonometrika tidak dijadikan inti karena dua alasan. Pertama, hanya tersedia @n_obs:0@ observasi tahunan yang sebanding (FY2023–FY2025) untuk mengestimasi hubungan antara tarif dan EBITDA SMDR. Kedua, rentang itu memuat patahan struktural (lonjakan 2021–2022 dan koreksi 2023), sehingga koefisien yang diestimasi tidak stabil. Statistik dipakai di tempat ia kuat: persentil historis untuk *severity* guncangan Brent dan kurs (Bab 6), dan *backtesting* terhadap realisasi.

### 3.2 Definisi rasio *covenant*

Pada tanggal uji t, dengan B<sub>t</sub> utang bank, S<sub>t</sub> sukuk yang belum jatuh tempo, L<sub>t</sub> liabilitas sewa, dan E<sub>t</sub> EBITDA 12 bulan terakhir:

$$ND_t=\frac{B_t+S_t+L_t}{E_t}\qquad\text{(batas }\le 3{,}00\text{x)}\tag{1}$$

Definisi ini tidak mengurangkan kas, sesuai definisi pada perjanjian yang direproduksi (rasio yang dilaporkan perusahaan untuk FY2022 dan FY2025 dapat direproduksi dengan definisi yang sama). DSCR memakai penyebut tersirat dari DSCR yang dilaporkan, D̄, ditambah pokok sukuk yang jatuh tempo dalam 12 bulan setelah tanggal uji, P<sub>t</sub>:

$$DSCR_t=\frac{E_t}{\bar D+P_t},\qquad \bar D=\frac{1}{2}\sum_{y\in\{2024,2025\}}\frac{E_y}{DSCR_y^{\text{lap}}}\tag{2}$$

dengan D̄ = USD @den0:1@ juta dan batas ≥ 1,10x. *Current Ratio* memakai aset lancar CA<sub>0</sub> dan liabilitas jangka pendek CL<sub>0</sub> pada 30 September 2026, disesuaikan dengan perubahan kas C<sub>t</sub> − C<sub>0</sub>:

$$CR_t=\frac{CA_0-(C_0-C_t)}{CL_0+P_t}\qquad\text{(batas }\ge 1{,}10\text{x)}\tag{3}$$

Frekuensi pengukuran *covenant* bank belum terkonfirmasi. Karena tabel rasio juga dilaporkan per 31 Maret, rasio diukur per akhir kuartal atas EBITDA 12 bulan terakhir; ini pendekatan konservatif, sebab pengujian tahunan pertama baru jatuh pada Desember 2027.

### 3.3 Transmisi tarif dan volume ke EBITDA

Dengan F pendapatan angkutan, A pendapatan agensi dan kepelabuhanan, H pendapatan penanganan kontainer dan peralatan (semuanya TTM), g perubahan tarif efektif, dan v perubahan volume:

$$\Delta Rev=F\big[(1+v)(1+g)-1\big]+(A+H)\,v\tag{4}$$

$$\Delta Cost=\psi(v)\,(COGS-Dep)\,\varepsilon\,v,\quad \varepsilon=\frac{F+A+H}{Rev},\quad \psi(v)=\begin{cases}\psi_{\downarrow} & v<0\\ 1 & v\ge 0\end{cases}\tag{5}$$

$$\Delta EBITDA=\Delta Rev-\Delta Cost\tag{6}$$

ψ<sub>↓</sub> adalah porsi biaya yang menurun mengikuti penurunan volume (*sticky cost*, Bagian 2.2). Dari (1), (4)–(6) diperoleh bentuk tertutup untuk ***headroom* penurunan tarif**, yaitu perubahan tarif g<sup>∗</sup> (pada v = 0) yang membawa ND tepat ke batas τ = 3,00 dengan D utang total:

$$g^{*}=\frac{D/\tau-E_0}{F}\tag{7}$$

### 3.4 Transmisi makro: bunker, kurs, dan bunga

Untuk skenario makro (skenario biaya), perubahan EBITDA bulanan berasal dari tiga saluran. Dengan Q konsumsi energi, s pangsa bunker, λ nilai kalor, P<sub>v</sub> harga VLSFO, η elastisitas bunker terhadap Brent, φ pass-through, dan θ porsi EBIT berfungsi rupiah:

$$\Delta E^{\text{bunker}}_t=-\frac{1}{12}\cdot\frac{Q\,s}{\lambda}P_v\cdot\eta\cdot\Big(\frac{Brent_t}{Brent_0}-1\Big)(1-\phi)\tag{8}$$

$$\Delta E^{\text{kurs}}_t=\frac{\theta\,EBIT}{12}\Big(\frac{X_0}{X_t}-1\Big)\tag{9}$$

dan beban bunga bank mengambang berubah sebesar

$$\Delta I_t=B_t\,\frac{i_t-i_0}{100}\,\frac{f}{12}\tag{10}$$

dengan f porsi utang mengambang. Jalur Brent<sub>t</sub>, X<sub>t</sub> (kurs USD/IDR), dan i<sub>t</sub> (BI Rate) dibangun dari definisi skenario: interpolasi jangkar proyeksi resmi, penurunan mengikuti preseden 2022, atau guncangan dengan pemulihan sebagian. Skenario pasar tidak memakai saluran ini; ia hanya menggeser EBITDA sebesar (6) selama m bulan pertama.

### 3.5 Kas bulanan

Kas akhir bulan C<sub>t</sub> mengikuti identitas sumber dan penggunaan kas, dengan κ konversi EBITDA ke kas operasi dan y imbal hasil kas:

$$C_t=C_{t-1}+\kappa E^{m}_t+\frac{y}{12}C_{t-1}-O_t+R_t+M\Big(\frac{1}{X_t}-\frac{1}{X_{t-1}}\Big)\tag{11}$$

E<sup>m</sup><sub>t</sub> EBITDA bulanan, O<sub>t</sub> seluruh pengeluaran (kupon dan pokok sukuk, bunga, sewa, belanja pemeliharaan dan program kapal baru, angsuran bank, dividen), R<sub>t</sub> penarikan ulang pinjaman bank, dan suku terakhir translasi kas berdenominasi rupiah M. Likuiditas adalah kas ditambah deposito yang dapat ditarik:

$$Liq_t=C_t+\delta\cdot Dep\tag{12}$$

Utang bank diasumsikan di-*refinance* (*rollover*, saldo tetap), sesuai saldo utang bank yang stabil pada USD @bank_min:0@–@bank_max:0@ juta pada akhir FY2023–FY2025 dan 30 September 2026.

### 3.6 *Covenant* kuartalan dan EBITDA 12 bulan

EBITDA 12 bulan pada akhir kuartal q adalah jumlah EBITDA bulanan 12 bulan terakhir; bulan sebelum Oktober 2026 diwakili rata-rata TTM:

$$E_q=\sum_{j=0}^{11}E^{m}_{q-j},\qquad E^{m}_{s}=\frac{E_0}{12}\ \text{untuk } s<\text{Okt 2026}\tag{13}$$

### 3.7 Skenario dan dua kasus parameter

Enam skenario diuji (Tabel 4): tiga skenario makro (*Base Case*, *Prolonged Energy*, *Combined*) dan tiga skenario pasar (*Demand Slowdown*, *Overcapacity*, *Weak Demand + Overcapacity*). Besaran skenario pasar dijangkarkan pada tarif dan volume yang pernah dialami SMDR. Tiap skenario dijalankan pada dua kasus: **asumsi tengah** dan **downside case arus kas**, yaitu setiap pos pengeluaran berada pada nilai paling merugikan dalam rentang historisnya.

### 3.8 *Backtesting* dan penskalaan ruang

Untuk setiap tahun uji y, prediksi model dihitung dari tarif efektif dan volume realisasi tahun itu melalui (4)–(6), lalu dibandingkan dengan perubahan EBITDA aktual:

$$\rho_y=\frac{\Delta EBITDA^{\text{model}}_y}{\Delta EBITDA^{\text{aktual}}_y}\tag{14}$$

Jika dampak nyata adalah fraksi 1/ρ<sub>y</sub> dari prediksi, *headroom* penurunan tarif meluas menjadi g<sup>∗</sup><sub>y</sub> = g<sup>∗</sup>·ρ<sub>y</sub> (15).

### 3.9 Mitigasi dan *Early Warning*

Pelunasan sebagian utang bank sebesar P<sup>lunas</sup> pada September 2027 dan penahanan dividen sejak Juni 2027 diuji pada jalur kas yang sama:

$$ND'_t=\frac{ND_t\,E_t-P^{\text{lunas}}}{E_t}\tag{16}$$

Penghematan bunga atas pelunasan tidak dihitung (sisi konservatif). *Threshold* EW (τ<sub>EW</sub>) dipilih pada data Maret 2027: di bawah nilai terendah skenario yang kelak mengalami *breach*, dan di atas nilai tertinggi skenario yang tidak.

### 3.10 Uji *severity*

Besaran guncangan pembanding diambil dari persentil ke-90 perubahan 12 bulan historis (Brent sejak @brent_start@, kurs sejak 2000):

$$d^{90}=Q_{0{,}9}\!\left(\frac{x_t}{x_{t-12}}-1\right)\tag{17}$$

lalu diterjemahkan ke selisih EBITDA melalui (8) dan (9) pada parameter tengah dan merugikan.""")

md(r"""## 4. Data

### 4.1 Sumber

Seluruh analisis memakai data publik; tidak ada data internal perusahaan. Tabel 1 merangkum sumber utama. Setiap sumber terdaftar beserta tanggal akses, status redistribusi, dan hash SHA-256 pada registri sumber repositori.""")

code(r"""sources = pd.read_csv(dp.table("sources.csv"), keep_default_na=False)
show = sources[["source_id", "name", "publisher", "kind", "redistribution"]].rename(columns={"source_id": "ID", "name": "Sumber", "publisher": "Penerbit", "kind": "Jenis", "redistribution": "Status redistribusi"})
caption("Tabel 1. Sumber data", "Registri sumber repositori (data/00_registry/sources.csv).")
md_table(show)""")

md(r"""### 4.1b Profil usaha

SMDR memperoleh pendapatan terutama dari angkutan (*freight*) dan jasa yang melekat padanya. Tabel 1b menunjukkan komposisi TTM menurut jenis jasa dan komposisi 9M26 menurut pasar geografis. Pendapatan angkutan, yang menjadi besaran yang diguncang pada model, mencapai @svc_freight_pct:0@% dari total.""")

code(r"""from smdr import operating
svc = pd.Series(inp["rev_by_service"]); nm = {"freight_income": "Angkutan (freight)", "time_charter": "Sewa berjangka (time charter)", "agency_forwarding_ports": "Agensi, forwarding, kepelabuhanan",
                                              "container_equipment_handling": "Penanganan kontainer dan peralatan", "other_revenue": "Lainnya"}
t1b = pd.DataFrame({"Jenis jasa": [nm[k] for k in svc.index], "USD juta": svc.values, "Pangsa (%)": svc.values / svc.sum() * 100})
caption("Tabel 1b. Komposisi pendapatan TTM menurut jenis jasa", "Annual Report dan laporan keuangan 9M26; TTM = FY2025 + 9M26 - 9M25.")
md_table(t1b, fmt={"USD juta": 1, "Pangsa (%)": 1})
o = operating.load(); geo = o[(o.metric_key == "fs_revenue_geography") & (o.period == "9M26")].set_index("scope")["value"] / 1e6
t1c = pd.DataFrame({"Pasar": geo.index, "USD juta": geo.values, "Pangsa (%)": geo.values / geo.sum() * 100})
caption("Tabel 1c. Pendapatan 9M26 menurut pasar geografis", "Catatan segmen laporan keuangan 9M26 (belum diaudit).")
md_table(t1c, fmt={"USD juta": 1, "Pangsa (%)": 1})""")

md(r"""### 4.2 Konstruksi variabel dan perlakuan data

Alur dari perolehan sampai hasil dijelaskan terpisah (`docs/data-treatment.md`). Aturan yang paling menentukan angka adalah:

1. **`n.d.` bukan nol.** Dari @fs_nd_rows:0@ baris laporan keuangan kanonik, @fs_nd:0@ berstatus tidak diungkapkan (*n.d.*) dan bernilai kosong; nilai nol hanya diisi melalui aturan tertulis yang dapat ditelusuri.
2. **Laba rugi dan arus kas interim bersifat kumulatif.** 6M26 adalah Januari–Juni. Besaran 12 bulan terakhir dihitung sebagai FY2025 + 9M26 − 9M25.
3. **EBITDA operasi** = EBIT (laba bruto dikurangi beban umum dan administrasi) ditambah penyusutan biaya jasa dan penyusutan beban umum dan administrasi dari bukti pada dokumen berhalaman; penyusutan FY2025 memakai laporan audit.
4. **Jejak.** Setiap angka kanonik membawa berkas, sheet, dan sel asal. Dari @parity:0@ angka berstatus dilaporkan, seluruhnya dapat ditelusuri ke satu baris dari @raw_rows:0@ baris mentah, dengan nilai yang sama.
5. **Kontrol mutu.** Identitas akuntansi diuji pada @chk_n:0@ pemeriksaan (@chk_pass:0@ *pass*, @chk_known:0@ pengecualian yang diketahui penyebabnya, 0 *fail*).

### 4.3 Posisi dasar

Tabel 2 memuat posisi dasar pada 30 September 2026.""")

code(r"""inp = cf._init(); w = baseline.load_wide(); b = cvn.base_position(w)
ebitda0 = inp["ebitda"]; debt0 = b["bank"] + b["sukuk"] + b["lease"]
pos = pd.DataFrame([
    ["Pendapatan usaha TTM", inp["revenue"]], ["EBITDA operasi TTM", ebitda0], ["EBIT TTM", inp["ebit"]],
    ["Utang bank", b["bank"]], ["Sukuk", b["sukuk"]], ["Liabilitas sewa", b["lease"]], ["Utang total (bank + sukuk + sewa)", debt0],
    ["Kas dan setara kas", inp["opening_cash"]], ["Deposito dan aset keuangan lancar lain", inp["deposits"]], ["Kas + deposito", inp["opening_cash"] + inp["deposits"]],
    ["Biaya operasi tunai per bulan", inp["opex_month"]]], columns=["Butir", "USD juta"])
caption("Tabel 2. Posisi dasar SMDR, 30 September 2026", "Laporan keuangan SMDR (9M26, belum diaudit); perhitungan penulis. Net Debt to EBITDA = %s x." % idn(debt0 / ebitda0, 2))
md_table(pos, fmt={"USD juta": 1})""")

md(r"""### 4.3b Statistik deskriptif historis

Tabel 2b menempatkan posisi saat ini dalam riwayat empat tahun terakhir. *Net Debt to EBITDA* naik dari @nd22:2@x menjadi @nd25:2@x dalam tiga tahun, sementara EBITDA operasi turun dari USD @e22:0@ juta menjadi USD @e25:0@ juta; TTM September 2026 (USD @ebitda:0@ juta) menunjukkan pemulihan sebagian, tetapi rasio tetap lebih tinggi daripada pada awal periode.""")

code(r"""btx = pd.read_csv(dp.table("backtest.csv")).set_index("periode")
rows = []
for p in ("FY2022", "FY2023", "FY2024", "FY2025"):
    e = cb.ebitda_operating(w, p) / 1e6
    rows.append([p, w.loc[("IS", "revenue"), p] / 1e6, e, cvn.reported_nd_ebitda(w, p, e), (btx.loc[p, "tarif_efektif"] * 100) if p in btx.index else float("nan")])
rows.append(["TTM Sep 2026", inp["revenue"], ebitda0, debt0 / ebitda0, float("nan")])
t2b = pd.DataFrame(rows, columns=["Periode", "Pendapatan", "EBITDA operasi", "ND/EBITDA (x)", "Perubahan tarif efektif (%)"]).fillna("-")
caption("Tabel 2b. Statistik deskriptif historis", "USD juta. ND/EBITDA memakai definisi covenant (bank + sukuk + sewa, tanpa dikurangi kas) pada neraca tiap periode. Sumber: laporan keuangan SMDR; perhitungan penulis.")
md_table(t2b, fmt={"Pendapatan": 1, "EBITDA operasi": 1, "ND/EBITDA (x)": 2, "Perubahan tarif efektif (%)": 1})""")

md(r"""### 4.4 Parameter

Parameter transmisi dan kas disajikan sebagai rentang rendah, tengah, dan tinggi, masing-masing dengan sumber dan status pada tabel kurasi (`data/02_curated/assumptions`). Tabel 3 meringkasnya; basis tiap parameter ada pada lampiran dan pada sheet `Asumsi` model Excel.""")

code(r"""op = pd.read_csv(dp.table("operating_assumptions.csv")); ca = pd.read_csv(dp.table("cash_assumptions.csv"))
par = pd.concat([op.assign(Kelompok="Transmisi"), ca.assign(Kelompok="Kas")])[["Kelompok", "parameter", "low", "central", "high", "adverse_rule"]]
par.columns = ["Kelompok", "Parameter", "Rendah", "Tengah", "Tinggi", "Aturan merugikan"]
caption("Tabel 3. Parameter model", "data/02_curated/assumptions; status dan dasar tiap parameter pada tabel sumber.")
md_table(par, fmt={"Rendah": 3, "Tengah": 3, "Tinggi": 3})""")

md(r"""### 4.5 Skenario

Tabel 4 merangkum enam skenario. Besaran skenario pasar dijangkarkan pada pengalaman SMDR sendiri: tarif efektif @bt_rate_FY2024_a:0@% pada FY2024 dan perubahan tarif dan volume hub pada FY2023.""")

code(r"""from smdr.transition import bridge as br
nar = br.narratives().set_index("kisah")
rows = [["Base Case", "makro", "Proyeksi resmi; Brent bertahan tiga bulan lalu normal", "-", "-", "-"],
        ["Prolonged Energy", "makro", "Brent bertahan 9 bulan sebelum normalisasi", "-", "-", "-"],
        ["Combined", "makro", "Energi bertahan, kurs, BI Rate naik", "-", "-", "-"]]
for k, lab in (("Permintaan melemah", "Demand Slowdown"), ("Kelebihan kapasitas", "Overcapacity"),
               ("Permintaan lemah dan kelebihan kapasitas", "Weak Demand + Overcapacity (terburuk)")):
    n = nar.loc[k]; rows.append([lab, "pasar", n["jangkar_tarif"], "%s%%" % idn(n["tarif"] * 100, 0), "%s%%" % idn(n["volume"] * 100, 0), "%d" % n["bulan"]])
caption("Tabel 4. Skenario", "Definisi skenario: data/02_curated/scenarios dan sheet Asumsi pada model Excel.")
md_table(pd.DataFrame(rows, columns=["Skenario", "Jenis", "Dasar", "Tarif", "Volume", "Bulan"]))""")

md(r"""## 5. Hasil

### 5.1 Posisi awal

Pada 30 September 2026 *Net Debt to EBITDA* berada di @nd_now:2@x, naik dari @nd22:2@x pada FY2022 (@nd23:2@x pada FY2023, @nd24:2@x pada FY2024, dan @nd25:2@x pada FY2025) seiring turunnya EBITDA dan bertambahnya liabilitas sewa. Ruang terhadap batas 3,00x karenanya sudah menyempit sebelum skenario apa pun diterapkan.

### 5.2 Tekanan terkonsentrasi pada *covenant leverage*

Tabel 5 memuat hasil enam skenario pada dua kasus. Dua skenario pasar mengalami *breach* atas batas 3,00x: *Overcapacity* mencapai @nd27_ovr_c:2@x pada FY2027 (puncak kuartalan @qpk_ovr_c:2@x), dan *Weak Demand + Overcapacity* @nd27_wrs_c:2@x (puncak kuartalan @qpk_wrs_c:2@x; @qpk_wrs_a:2@x pada *downside case*). Keduanya pertama kali mengalami *breach* pada pengujian @first_q@. *Demand Slowdown* mencapai @nd27_dem_c:2@x, dan ketiga skenario makro (skenario biaya) tidak melampaui @nd27_energy_a:2@x bahkan pada *downside case*. Hasil *Overcapacity* hanya berjarak @ovr_margin:2@x di atas batas, sehingga hasilnya sensitif terhadap parameter; ia lebih tepat dibaca sebagai berada pada batas daripada sebagai *breach* yang tegas.""")

code(r"""sr = pd.read_csv(dp.table("scenario_results.csv"))
order = ["Dasar", "Energi bertahan", "Gabungan", "Permintaan melemah", "Kelebihan kapasitas", "Permintaan lemah dan kelebihan kapasitas"]
t5 = sr.assign(o=sr.skenario.map({k: i for i, k in enumerate(order)})).sort_values(["o", "case"])
t5 = t5[["skenario", "case", "ebitda_FY2027", "nd_FY2027", "nd_FY2028", "cover_FY2027", "current_ratio_min", "min_liquidity", "first_below"]].fillna("-")
t5.columns = ["Skenario", "Kasus", "EBITDA FY2027", "ND FY2027", "ND FY2028", "DSCR FY2027", "Current Ratio min.", "Kas+deposito min.", "Kas di bawah batas sejak"]
t5["Kasus"] = t5["Kasus"].map({"central": "tengah", "adverse": "downside"}); t5["Skenario"] = t5["Skenario"].map(EN)
caption("Tabel 5. Hasil per skenario dan kasus", "EBITDA dan kas dalam USD juta; rasio dalam x. Batas: ND 3,00x; DSCR dan Current Ratio 1,10x; kas minimum usulan USD %s juta. Sumber: data/04_marts/results/scenario_results.csv." % idn(inp["opex_month"], 0))
md_table(t5, fmt={"EBITDA FY2027": 1, "ND FY2027": 2, "ND FY2028": 2, "DSCR FY2027": 2, "Current Ratio min.": 2, "Kas+deposito min.": 1})""")

code(r"""cq = pd.read_csv(dp.table("covenant_quarterly.csv"))
Q = sorted(cq.quarter.unique()); xq = np.arange(len(Q))
g_ = lambda k, case: cq[(cq.skenario == k) & (cq.case == case)].sort_values("quarter").nd.values
fig, ax = plt.subplots(figsize=(9.4, 4.8)); fstyle(ax); ftitle(ax, "Net Debt to EBITDA per akhir kuartal (x)")
for k in ("Dasar", "Energi bertahan", "Gabungan"): ax.plot(xq, g_(k, "central"), color=ABU, lw=1.3, zorder=2)
ax.plot(xq, g_(DEM, "central"), color=ABU_D, lw=1.8, zorder=3)
ax.plot(xq, g_(OVR, "central"), color=KUNING, lw=3.2, zorder=4)
ax.plot(xq, g_(WRS, "central"), color=INK, lw=2.4, zorder=5)
ax.plot(xq, g_(WRS, "adverse"), color=INK, lw=1.3, ls=(0, (3, 2)), zorder=5)
ax.axhline(3.0, color=MERAH, ls=(0, (4, 2.5)), lw=1.3, zorder=1); ax.text(-0.25, 3.03, "Batas 3,00x", color=MERAH, fontsize=9, fontweight="bold")
ax.axhline(2.45, color=ABU_D, ls=":", lw=1.0, zorder=1); ax.text(5.7, 2.475, "Threshold Early Warning 2,45x", color=ABU_D, fontsize=8.3)
for xv, t in ((1, "Mar 2027:\ndata Early Warning"), (3, "Sep 2027:\nbreach pertama")):
    ax.axvline(xv, color=ABU, lw=0.8, zorder=0); ax.text(xv + 0.08, 3.86, t, fontsize=8.3, color=INK, va="top")
ends = [(g_(WRS, "adverse"), "Weak Demand + Overcapacity,\ndownside case: puncak %s" % idn(g_(WRS, "adverse").max(), 2) + "x", INK, "bold"),
        (g_(WRS, "central"), "Weak Demand + Overcapacity: puncak %s" % idn(g_(WRS, "central").max(), 2) + "x", INK, "bold"),
        (g_(OVR, "central"), "Overcapacity: puncak %s" % idn(g_(OVR, "central").max(), 2) + "x", "#B7860B", "bold"),
        (g_(DEM, "central"), "Demand Slowdown: puncak %s" % idn(g_(DEM, "central").max(), 2) + "x", ABU_D, "normal"),
        (g_("Gabungan", "central"), "Base Case, Prolonged Energy, Combined:\npuncak maks. %s" % idn(max(g_(k, "central").max() for k in ("Dasar", "Energi bertahan", "Gabungan")), 2) + "x", ABU_D, "normal")]
ly = spread([e[0][-1] for e in ends], 0.2)
for (v, t, c, wt), yy in zip(ends, ly):
    ax.plot([xq[-1] + 0.05, xq[-1] + 0.4], [v[-1], yy], color=c if c != ABU_D else ABU, lw=0.8, clip_on=False)
    ax.text(xq[-1] + 0.5, yy, t, fontsize=8.4, color=c, fontweight=wt, va="center")
ax.set_xticks(xq); ax.set_xticklabels([mlabel(q) for q in Q]); ax.set_xlim(-0.3, 8.1); ax.set_ylim(1.95, 3.9)
fig.subplots_adjust(right=0.64); plt.show()
caption_below("Gambar 2. Net Debt to EBITDA per akhir kuartal", "Asumsi tengah, kecuali garis putus-putus (downside case arus kas). EBITDA 12 bulan terakhir. Sumber: data/04_marts/results/covenant_quarterly.csv.")""")

md(r"""**Rincian per skenario.** Skenario makro menghasilkan tekanan paling ringan: pada asumsi tengah, *Net Debt to EBITDA* FY2027 adalah @nd27_base_c:2@x (*Base Case*), @nd27_energy_c:2@x (*Prolonged Energy*), dan @nd27_comb_c:2@x (*Combined*); pada *downside case* naik paling tinggi ke @nd27_comb_a:2@x. Guncangan biaya (bunker, kurs, bunga) mengurangi EBITDA FY2027 sebesar @mc_lo:1@–@mc_hi:1@% terhadap TTM (kedua kasus), jauh lebih kecil daripada guncangan pasar yang mengurangi @mk_lo:1@–@mk_hi:1@% pada asumsi tengah. *Demand Slowdown* (tarif −6%, volume −5%, 12 bulan) menghasilkan @nd27_dem_c:2@x pada FY2027 dengan puncak kuartalan di bawah 3,00x, karena jendelanya hanya 12 bulan. *Overcapacity* dan *Weak Demand + Overcapacity* berlangsung 24 bulan sehingga efek penuh jatuh pada FY2027 dan *breach* pertama terjadi pada @first_q@. Perbedaan antara *Overcapacity* (@nd27_ovr_c:2@x) dan *Weak Demand + Overcapacity* (@nd27_wrs_c:2@x) sepenuhnya berasal dari komponen volume (−5%), yang menambah @vol_effect:0@ juta dolar pengurangan EBITDA setelah memperhitungkan *sticky cost*.""")

md(r"""### 5.3 DSCR, *Current Ratio*, dan likuiditas

Pada asumsi tengah, DSCR terendah (FY2027–FY2028) adalah @dscr_min_c:2@x dan *Current Ratio* terendah @cr_min_c:2@x, keduanya di atas batas 1,10x pada seluruh skenario, dan kas ditambah deposito terendah adalah USD @liq_min_c:0@ juta, jauh di atas batas minimum usulan USD @th_cash:0@ juta (satu bulan biaya operasi tunai).

Pada *downside case arus kas*, hasilnya berbeda. Pada skenario terburuk *Current Ratio* turun di bawah 1,10x pada @cr_breach_fy_wrs@ dan kas ditambah deposito di bawah batas minimum mulai @liq_first_wrs@; pada *Overcapacity* kas di bawah batas mulai @liq_first_ovr@. Urutan tekanan dapat ditelusuri: sejak *breach* pertama *Net Debt to EBITDA* (@first_q@), *Current Ratio* menyusul @lag_cr:0@ bulan kemudian dan kas @lag_liq:0@ bulan kemudian pada skenario terburuk. Empat pos kas terbesar yang menggerakkan hasil *downside* adalah @tor_label@ (Lampiran B).

### 5.4 *Early Warning*

Pada data Maret 2027, dua skenario yang kelak melewati 3,00x sudah berada di @m3_wrs:2@x dan @m3_ovr:2@x, sedangkan skenario lain tidak lebih dari @m3_rest:2@x. *Threshold* EW @ew:2@x memisahkan keduanya, @lead:0@ bulan sebelum pengujian pertama yang mengalami *breach*. *Threshold* ini dipilih pada *output* model yang sama; karena itu ia tidak boleh dibaca sebagai bukti prediktif di luar sampel (lihat Bagian 2.4 dan 8).

### 5.5 Opsi pengelolaan *leverage*

Tabel 6 menguji dua opsi pada jalur kas yang sama: pelunasan sebagian utang bank dari kas pada September 2027, dan penahanan dividen sejak Juni 2027. Pada *Overcapacity*, pelunasan USD 54 juta (dibulatkan dari USD @pay_ovr_c:1@ juta yang dibutuhkan untuk mencapai sasaran @safe_nd:2@x, yaitu ruang 10% di bawah batas) menurunkan *Net Debt to EBITDA* menjadi @mit54_ovr_nd:2@x, dengan *Current Ratio* @mit54_ovr_cr:2@x dan kas ditambah deposito terendah USD @mit54_ovr_liq:0@ juta. Pada skenario terburuk, pelunasan USD 107 juta (dari kebutuhan USD @pay_wrs_c:1@ juta) menurunkan rasio ke @mit107_wrs_nd:2@x, tetapi *Current Ratio* turun ke @mit107_wrs_cr:2@x tanpa penahanan dividen; dengan penahanan dividen *Current Ratio* menjadi @mit107d_wrs_cr:2@x dan kas minimum USD @mit107d_wrs_liq:0@ juta. Penghematan bunga atas pelunasan tidak dihitung.""")

code(r"""mt = pd.read_csv(dp.table("mitigation_tests.csv"))
sel = mt[(mt.case == "central") & (mt.skenario.isin(["Kelebihan kapasitas", "Permintaan lemah dan kelebihan kapasitas"]))].copy()
sel["Paket"] = sel.apply(lambda r: "Pelunasan USD %d juta%s" % (r.paydown, " + henti dividen" if r.dividend_stop else ""), axis=1)
t6 = sel[["skenario", "Paket", "nd_FY2027", "nd_FY2028", "current_ratio_min", "current_ratio_min_fy", "min_liquidity"]]
t6 = t6.assign(skenario=t6["skenario"].map(EN)); t6.columns = ["Skenario", "Paket", "ND FY2027", "ND FY2028", "Current Ratio min.", "Tahun CR min.", "Kas+deposito min."]
caption("Tabel 6. Uji opsi pengelolaan leverage (asumsi tengah)", "Pelunasan pada Sep 2027; penahanan dividen sejak Jun 2027. Sumber: data/04_marts/results/mitigation_tests.csv.")
md_table(t6, fmt={"ND FY2027": 2, "ND FY2028": 2, "Current Ratio min.": 2, "Kas+deposito min.": 1})""")

code(r"""cp = pd.read_csv(dp.table("cash_paths_monthly.csv"))
gm = lambda k, case: cp[(cp.skenario == k) & (cp.case == case)].sort_values("month").reset_index(drop=True)
fig, ax = plt.subplots(figsize=(9.4, 4.8)); fstyle(ax); ftitle(ax, "Kas + deposito, Okt 2026 sampai Des 2031 (USD juta)")
th = inp["opex_month"]; x = np.arange(63)
ser = [("Dasar", "central", ABU_D, 1.8, "-", "Base Case", ABU_D), (OVR, "central", KUNING, 3.0, "-", "Overcapacity", "#B7860B"),
       (WRS, "central", INK, 2.2, "-", "Weak Demand + Overcapacity", INK), (WRS, "adverse", INK, 1.4, (0, (3, 2)), "Weak Demand + Overcapacity,\ndownside case", INK)]
for k, case, c, lw, ls, lab, tc in ser:
    ax.plot(x, gm(k, case).liquidity, color=c, lw=lw, ls=ls)
ends = [gm(k, case).liquidity.iloc[-1] for k, case, *_ in ser]; ly = spread(ends, 55)
for (k, case, c, lw, ls, lab, tc), v, yy in zip(ser, ends, ly):
    ax.plot([62.1, 63.6], [v, yy], color=ABU, lw=0.8, clip_on=False)
    ax.text(63.9, yy, "%s: %s" % (lab, idn(v, 0)), fontsize=8.4, color=tc, fontweight="bold" if tc == INK else "normal", va="center")
ax.axhline(th, color=MERAH, ls=(0, (4, 2.5)), lw=1.3); ax.text(0.5, th + 14, "Batas minimum usulan USD %s juta" % idn(th, 0), color=MERAH, fontsize=9, fontweight="bold")
ax.axhline(0, color=ABU, lw=0.8)
ga = gm(WRS, "adverse"); fb = int(np.argmax(ga.liquidity.values < th))
ax.plot([fb], [ga.liquidity.iloc[fb]], "o", color=MERAH, mec=INK, ms=7, zorder=6)
ax.annotate("%s: di bawah batas\n(downside case)" % ("Jun 2029" if ga.month.iloc[fb] == "2029-06" else ga.month.iloc[fb]), xy=(fb, ga.liquidity.iloc[fb]), xytext=(fb - 14, -140), fontsize=8.4, color=MERAH, fontweight="bold",
            arrowprops=dict(arrowstyle="-", color=MERAH, lw=0.8))
for m_, t, ty in (("2028-08", "Seri B Agu 2028", 628), ("2029-05", "Seri III Mei 2029", 590), ("2030-07", "Seri II Jul 2030", 628)):
    i = int(np.where(gm("Dasar", "central").month.values == m_)[0][0]); ax.axvline(i, color=ABU, lw=0.7, zorder=0); ax.text(i + 0.4, ty, t, fontsize=7.8, color=ABU_D, va="top")
tk = [2, 14, 26, 38, 50, 62]; ax.set_xticks(tk); ax.set_xticklabels([mlabel(ga.month.iloc[i]) for i in tk])
ax.set_xlim(-1, 63); ax.set_ylim(-220, 640); fig.subplots_adjust(right=0.7); plt.show()
caption_below("Gambar 3. Kas + deposito, Okt 2026 sampai Des 2031", "Garis tegak = jatuh tempo sukuk. Refinancing utang bank (rollover). Sumber: data/04_marts/results/cash_paths_monthly.csv.")""")

md(r"""## 6. Uji Ketahanan

### 6.1 *Backtesting* FY2023–FY2025

Tabel 7 membandingkan prediksi model dengan perubahan EBITDA aktual. Pada FY2023 model memprediksi penurunan USD @bt_pred_FY2023_a:0@ juta, sedangkan yang terjadi USD @bt_act_FY2023_a:0@ juta, atau prediksi @bt_x_FY2023:1@ kali aktual. Pada FY2024 rasionya @bt_x_FY2024:1@, dan pada FY2025 @bt_x_FY2025:1@ (hampir sama). Dalam tiga tahun itu prediksi tidak pernah lebih kecil dari dampak aktual, yang mendukung P2. Satu perbedaan penting adalah bahwa pada FY2023 biaya jasa dan penanganan angkutan turun USD @cost23:0@ juta, yang tidak dimodelkan; model mengasumsikan biaya tidak menurun penuh mengikuti volume. Karena hanya tiga pengamatan dan rasio FY2025 mendekati satu, hasil ini menunjukkan model tidak meremehkan dampak, bukan bahwa ia selalu konservatif.""")

code(r"""bt = pd.read_csv(dp.table("backtest.csv"))
t7 = bt[["periode", "tarif_efektif", "volume", "model", "terealisasi"]].copy()
t7["Prediksi / aktual"] = bt.model / bt.terealisasi
t7["Tarif efektif"] = bt.tarif_efektif * 100; t7["Volume"] = bt.volume * 100
t7 = t7[["periode", "Tarif efektif", "Volume", "model", "terealisasi", "Prediksi / aktual"]]
t7.columns = ["Periode", "Tarif efektif (%)", "Volume (%)", "Prediksi model", "Aktual", "Prediksi / aktual (x)"]
caption("Tabel 7. Backtesting: perubahan EBITDA (USD juta)", "Sumber: data/04_marts/results/backtest.csv.")
md_table(t7, fmt={"Tarif efektif (%)": 1, "Volume (%)": 1, "Prediksi model": 1, "Aktual": 1, "Prediksi / aktual (x)": 2})
fig, ax = plt.subplots(figsize=(8.2, 4.2)); fstyle(ax, grid=False); ftitle(ax, "Backtesting: prediksi model dan dampak aktual pada EBITDA (USD juta)")
xs = np.arange(len(bt)); wd = 0.34
ax.bar(xs - wd / 2, bt.model, wd, color=KUNING, zorder=3); ax.bar(xs + wd / 2, bt.terealisasi, wd, color=ABU_D, zorder=3)
for xi, (m_, a_) in enumerate(zip(bt.model, bt.terealisasi)):
    for dx, v in ((-wd / 2, m_), (wd / 2, a_)):
        ax.text(xi + dx, v + (-18 if v < 0 else 14), idn(v, 0), ha="center", va="top" if v < 0 else "bottom", fontsize=9, fontweight="bold", color=INK)
    ax.text(xi, 75, ("prediksi = aktual" if abs(m_ / a_ - 1) < 0.01 else "prediksi %s× aktual" % idn(m_ / a_, 1)), ha="center", fontsize=9, color=INK, fontweight="bold")
ax.axhline(0, color=INK, lw=0.8, zorder=4); ax.set_xticks(xs); ax.set_xticklabels(bt.periode, fontsize=10); ax.set_ylim(-540, 130)
ax.set_yticks([])
ax.spines["left"].set_visible(False)
ax.text(2.45, -500, "kuning = prediksi model; abu = aktual", fontsize=8.5, color=ABU_D, ha="right")
plt.tight_layout(); plt.show()
caption_below("Gambar 4. Prediksi model dan dampak aktual", "Sumber: data/04_marts/results/backtest.csv. Pada FY2023 sebagian biaya jasa turun USD %s juta dan tidak dimodelkan." % idn(abs(float(pd.read_csv(dp.table("backtest.csv")).set_index("periode").loc["FY2023", "biaya_jasa_delta"])), 0))""")

md(r"""### 6.2 *Headroom* penurunan tarif

Dari persamaan (7), tarif angkut dapat turun @headroom:1@% (volume tetap) sebelum *Net Debt to EBITDA* mencapai 3,00x: EBITDA minimum agar rasio tepat di batas adalah USD @min_ebitda:0@ juta, dibandingkan USD @ebitda:0@ juta sekarang, dengan pendapatan angkutan USD @freight:0@ juta. Jika dampak nyata sama seperti FY2024 (aktual @act_ratio24:0@% dari prediksi), ruang meluas menjadi @headroom_24:1@%, dan seperti FY2023 menjadi @headroom_23:1@% (persamaan 15). Gambar 5 memetakan *Net Debt to EBITDA* menurut kombinasi tarif dan volume setahun penuh; penurunan tarif 12% dengan volume tetap menghasilkan 3,02x, konsisten dengan skenario *Overcapacity* ketika efek penuh jatuh pada FY2027.""")

code(r"""F = inp["rev_by_service"]["freight_income"]; A_ = inp["rev_by_service"]["agency_forwarding_ports"]; H_ = inp["rev_by_service"]["container_equipment_handling"]
a_op = tr.assumptions(); psi_dn = tr.pick(a_op, "cost_flex_down", "central")
def dE(g, v):
    return F * ((1 + v) * (1 + g) - 1) + (A_ + H_) * v - (psi_dn if v < 0 else 1.0) * (inp["cogs"] - inp["cogs_dep"]) * ((F + A_ + H_) / inp["revenue"]) * v
rg = [-0.02 * i for i in range(12)]; vg = [-0.02 * i for i in range(6)]
Z = np.array([[debt0 / (ebitda0 + dE(g, v)) for v in vg] for g in rg])
from matplotlib.colors import ListedColormap, BoundaryNorm
fig, ax = plt.subplots(figsize=(7.8, 5.2)); ftitle(ax, "Net Debt to EBITDA menurut perubahan tarif dan volume (x)")
ax.imshow(Z, cmap=ListedColormap(["#ECEDEE", "#FDE9A8", "#F6A5A7"]), norm=BoundaryNorm([0, 2.7, 3.0, 10], 3), aspect="auto")
for i in range(len(rg)):
    for j in range(len(vg)):
        ax.text(j, i, idn(Z[i, j], 2), ha="center", va="center", fontsize=9, color=INK, fontweight="bold" if Z[i, j] > 3.0 else "normal")
ax.set_xticks(range(len(vg))); ax.set_xticklabels(["%d%%" % round(v * 100) for v in vg]); ax.set_yticks(range(len(rg))); ax.set_yticklabels(["%d%%" % round(g * 100) for g in rg])
ax.xaxis.set_ticks_position("top"); ax.xaxis.set_label_position("top"); ax.set_xlabel("Perubahan volume", fontsize=9, color=ABU_D); ax.set_ylabel("Perubahan tarif efektif", fontsize=9, color=ABU_D)
ax.tick_params(length=0, labelsize=8.5, colors=ABU_D)
for sp in ax.spines.values(): sp.set_visible(False)
for (r_, c_, lab) in ((6, 0, "Overcapacity"), (6, 2.5, "Weak Demand + Overcapacity")):
    ax.add_patch(plt.Rectangle((c_ - 0.5 if c_ == 0 else c_ - 0.35, r_ - 0.5), 1.0 if c_ == 0 else 0.7, 1.0, fill=False, ec=INK, lw=1.8)) if c_ == 0 else ax.scatter([c_], [r_], marker="*", s=170, color=INK, zorder=5)
from matplotlib.patches import Patch
ax.legend(handles=[Patch(color="#ECEDEE", label="< 2,70x"), Patch(color="#FDE9A8", label="2,70x sampai 3,00x"), Patch(color="#F6A5A7", label="> 3,00x (breach)")], loc="upper center", bbox_to_anchor=(0.5, -0.04), ncol=3, frameon=False, fontsize=8.5)
plt.tight_layout(); plt.show()
caption_below("Gambar 5. Net Debt to EBITDA menurut perubahan tarif dan volume (setahun penuh)", "Asumsi tengah; bentuk tertutup persamaan (4)-(6). Kotak = Overcapacity (tarif -12%, volume 0%); bintang = Weak Demand + Overcapacity (tarif -12%, volume -5%). Sumber: perhitungan penulis; peta yang sama ada pada sheet Sensitivitas model Excel.")""")

md(r"""### 6.3 Perbandingan dengan *severity* historis

Untuk menilai apakah guncangan pada skenario wajar, Tabel 8 membandingkannya dengan *severity* historis setara: perubahan 12 bulan persentil ke-90 Brent (+@brent_p90:0@%, @n_brent:0@ bulan tumpang tindih sejak @brent_start@) dan kurs (+@fx_p90:0@%, @n_fx:0@ bulan sejak 2000), serta penurunan tarif efektif FY2024. Guncangan Brent persentil ke-90 mengurangi EBITDA sekitar @sev_brent_pct:0@–@sev_brent_pct_a:0@% dan guncangan kurs @sev_fx_pct:0@–@sev_fx_pct_a:0@%, sedangkan penurunan tarif seperti FY2024 mengurangi EBITDA @sev_rate_pct:0@%. Tarif dan volume karenanya merupakan risiko EBITDA terbesar: dampak penurunan tarif seperti FY2024 adalah @r_lo:1@–@r_hi:1@ kali dampak guncangan Brent persentil ke-90.""")

code(r"""sv = pd.read_csv(dp.table("severity.csv")).set_index("metric")["value"].astype(str)
e0 = float(sv["ebitda"])
t8 = pd.DataFrame([
    ["Brent, persentil 90 perubahan 12 bulan (+%s%%)" % idn(float(sv["brent_p90"]) * 100, 0), -float(sv["d_brent"]), -float(sv["d_brent_adverse"])],
    ["Kurs USD/IDR, persentil 90 (+%s%%)" % idn(float(sv["fx_p90"]) * 100, 0), -float(sv["d_fx"]), -float(sv["d_fx_adverse"])],
    ["Penurunan tarif efektif FY2024 (%s%%)" % idn(float(sv["rate_fy2024"]) * 100, 0), -float(sv["d_rate"]), -float(sv["d_rate"])]], columns=["Guncangan", "Dampak EBITDA tengah", "Dampak EBITDA merugikan"])
t8["% EBITDA tengah"] = t8["Dampak EBITDA tengah"] / e0 * 100; t8["% EBITDA merugikan"] = t8["Dampak EBITDA merugikan"] / e0 * 100
caption("Tabel 8. Severity historis setara dan dampak pada EBITDA", "USD juta dan persen EBITDA TTM. Sumber: data/04_marts/results/severity.csv (data FRED).")
md_table(t8, fmt={"Dampak EBITDA tengah": 1, "Dampak EBITDA merugikan": 1, "% EBITDA tengah": 1, "% EBITDA merugikan": 1})""")

md(r"""### 6.4 Replay historis dan keterkaitan indeks global

Replay historis menerapkan EBITDA tahun lalu pada utang hari ini. Dengan EBITDA FY2024 (USD @hist24_e:0@ juta), *Net Debt to EBITDA* akan menjadi @hist24:2@x, dan dengan EBITDA FY2023 @hist23:2@x. Artinya tingkat EBITDA yang pernah dialami SMDR sendiri sudah berada dekat batas, sehingga skenario yang diuji bukan tekanan yang belum pernah terjadi. Keterkaitan WCI dengan Brent pada data tahunan lemah dan tidak signifikan (ρ = @corr:2@, n = @n_corr:0@), konsisten dengan pemilihan tarif efektif SMDR sebagai besaran utama.""")

md(r"""### 6.5 Sensitivitas terhadap *sticky cost* dan definisi EBITDA

Dua pilihan pemodelan paling menentukan angka tekanan: porsi biaya yang menurun mengikuti volume (ψ<sub>↓</sub>) dan definisi EBITDA. Tabel 9 memperlihatkan bahwa skenario tanpa penurunan volume (*Overcapacity*) tidak peka terhadap ψ<sub>↓</sub> karena persamaan (5) hanya berlaku saat volume turun, sedangkan skenario dengan penurunan volume (*Weak Demand + Overcapacity*) bergerak dari @psi_lo_nd:2@x pada ψ<sub>↓</sub> = @op_cost_flex_down_lo:2@ sampai @psi_hi_nd:2@x pada ψ<sub>↓</sub> = @op_cost_flex_down_hi:2@. Pada seluruh rentang itu skenario tersebut tetap di atas batas 3,00x. Definisi EBITDA mengubah *headroom* penurunan tarif: dengan EBITDA operasi (USD @ebitda:0@ juta) ruangnya @headroom:1@%, sedangkan dengan EBITDA basis lama (USD @ebitda_legacy:0@ juta) @headroom_legacy:1@%.""")

code(r"""rows = []
for lab, psi in (("Rendah", a_op.loc["cost_flex_down", "low"]), ("Tengah", a_op.loc["cost_flex_down", "central"]), ("Tinggi", a_op.loc["cost_flex_down", "high"])):
    cells = []
    for g_, v_ in ((-0.12, 0.0), (-0.12, -0.05)):
        d_ = F * ((1 + v_) * (1 + g_) - 1) + (A_ + H_) * v_ - (psi if v_ < 0 else 1.0) * (inp["cogs"] - inp["cogs_dep"]) * ((F + A_ + H_) / inp["revenue"]) * v_
        cells.append(debt0 / (ebitda0 + d_))
    rows.append(["%s (%s)" % (lab, idn(psi, 2)), cells[0], cells[1]])
t9 = pd.DataFrame(rows, columns=["Cost flexibility (psi)", "Overcapacity (tarif -12%, volume 0%)", "Weak Demand + Overcapacity (tarif -12%, volume -5%)"])
caption("Tabel 9. Net Debt to EBITDA FY2027 menurut cost flexibility", "Efek tahun penuh; asumsi tengah lainnya. Sumber: persamaan (4)-(6).")
md_table(t9, fmt={"Overcapacity (tarif -12%, volume 0%)": 2, "Weak Demand + Overcapacity (tarif -12%, volume -5%)": 2})""")

md(r"""## 7. Pembahasan

**Proposisi P1** didukung dengan catatan. Tekanan memang terkonsentrasi pada *covenant leverage*: pada asumsi tengah, hanya *Net Debt to EBITDA* yang mengalami *breach*, dan DSCR (@dscr_min_c:2@x), *Current Ratio* (@cr_min_c:2@x), serta kas tetap memenuhi. Catatannya dua. Hasil *Overcapacity* hanya @ovr_margin:2@x di atas batas, dan pada *downside case* *Current Ratio* serta kas juga tertekan, yang menunjukkan bahwa "terkonsentrasi" berlaku untuk asumsi tengah, bukan untuk setiap kasus parameter.

**Proposisi P2** didukung pada sampel yang ada. Prediksi model berada pada atau di atas dampak aktual pada ketiga tahun pengujian, sehingga *headroom* penurunan tarif @headroom:1@% tidak terlalu optimistis. Dengan tiga pengamatan dan satu di antaranya hampir sama dengan prediksi, hasil ini tidak boleh dibaca sebagai jaminan konservatisme.

**Proposisi P3** didukung secara *in-sample*. Pemisahan skenario pada data Maret 2027 (@m3_ovr:2@x dan @m3_wrs:2@x melawan paling tinggi @m3_rest:2@x) memberi jeda @lead:0@ bulan. Sesuai Borio dkk. (2014), ini diperlakukan sebagai usulan yang perlu dikalibrasi ulang dengan data kuartalan internal, bukan sebagai alat peringatan yang sudah teruji.

**Implikasi bagi pemantauan risiko.** Empat KRI turun dari rantai transmisi: tarif dan volume (WCI sebagai indikator pendahulu, dan tarif efektif internal dengan *headroom* @headroom:1@%), *Net Debt to EBITDA* (Alert @ew:2@x, batas 3,00x), DSCR, dan kas. Opsi pengelolaan *leverage* (pelunasan sebagian dan penahanan dividen) meniru tindakan yang menurut Nini dkk. (2012) diambil perusahaan setelah *violation*, tetapi di sini dikaji sebelum *breach*; Dichev dan Skinner (2002) mengingatkan bahwa *technical violation* sering terjadi tanpa kesulitan keuangan, sehingga jeda antara *breach* dan tindakan perlu dinegosiasikan, bukan diasumsikan.""")

md(r"""## 8. Keterbatasan dan Penelitian Lanjutan

1. **Tanpa data internal.** Tarif efektif, yield per TEU, dan volume per rute dibaca dari laporan publik. Empat risiko operasional (pasokan BBM domestik, cuaca ekstrem, gangguan siber, regulasi emisi) belum dikuantifikasi karena memerlukan data internal.
2. **Frekuensi pengukuran *covenant* belum terkonfirmasi.** Diasumsikan kuartalan sebagai pendekatan konservatif; bila tahunan, pengukuran pertama jatuh pada Desember 2027.
3. ***Refinancing* utang bank dan belanja modal kapal baru** di luar tiga proyek kapal baru yang dialokasikan dari dana sukuk belum dikonfirmasi. Batas kas minimum, *threshold* KRI, dan tahapan tindak lanjut adalah usulan.
4. **Model linier dan deterministik.** Tidak ada interaksi tarif dengan biaya selain melalui (5), dan backtesting terbatas pada tiga tahun.
5. ***Threshold* EW dikalibrasi pada *output* model yang sama**, sehingga belum teruji *out-of-sample*.
6. **Skenario normalisasi rute tidak ditampilkan** karena belum dapat dikalibrasi.
7. **Posisi 30 September 2026 belum diaudit**, dan hasil bukan proyeksi atau pernyataan probabilitas.

Penelitian lanjutan mencakup kalibrasi ulang *threshold* dengan data internal kuartalan, kuantifikasi risiko operasional, dan konfirmasi definisi *covenant* dengan bank dan Wali Amanat.""")

md(r"""## 9. Kesimpulan

Penelitian ini menunjukkan bahwa, pada asumsi tengah, penurunan tarif efektif sebesar 12% (setara FY2024) cukup membawa *Net Debt to EBITDA* SMDR ke batas 3,00x pada pengujian @first_q@, sedangkan DSCR, *Current Ratio*, dan kas tetap memenuhi batasnya. Tekanan karenanya terkonsentrasi pada *covenant leverage*; likuiditas baru tertekan pada *downside case arus kas*, @lag_liq:0@ bulan setelah *breach* pertama pada skenario terburuk. *Backtesting* menunjukkan model tidak meremehkan dampak pada FY2023–FY2025, sehingga *headroom* penurunan tarif @headroom:1@% layak dipakai sebagai *threshold* pemantauan. *Threshold* EW @ew:2@x pada data Maret 2027 memberi jeda @lead:0@ bulan, tetapi perlu dikalibrasi ulang dengan data internal. Opsi pelunasan sebagian utang bank (USD @pay_ovr_c:0@–@pay_wrs_c:0@ juta) dan penahanan dividen memulihkan rasio pada skenario yang diuji. Seluruh hasil bersifat pro forma dan tidak menyatakan probabilitas.""")

md(r"""## Referensi

- Anderson, M. C., Banker, R. D., dan Janakiraman, S. N. (2003). Are selling, general, and administrative costs "sticky"? *Journal of Accounting Research*, 41(1), 47–63. https://doi.org/10.1111/1475-679X.00095
- Borio, C., Drehmann, M., dan Tsatsaronis, K. (2014). Stress-testing macro stress testing: Does it live up to expectations? *Journal of Financial Stability*, 12, 3–15. https://doi.org/10.1016/j.jfs.2013.06.001
- Chava, S., dan Roberts, M. R. (2008). How does financing impact investment? The role of debt covenants. *The Journal of Finance*, 63(5), 2085–2121. https://doi.org/10.1111/j.1540-6261.2008.01391.x
- Dichev, I. D., dan Skinner, D. J. (2002). Large-sample evidence on the debt covenant hypothesis. *Journal of Accounting Research*, 40(4), 1091–1123. https://doi.org/10.1111/1475-679X.00083
- Nini, G., Smith, D. C., dan Sufi, A. (2012). Creditor control rights, corporate governance, and firm value. *The Review of Financial Studies*, 25(6), 1713–1761. https://doi.org/10.1093/rfs/hhs007
- Sorge, M. (2004). *Stress-testing financial systems: An overview of current methodologies* (BIS Working Paper No. 165). Bank for International Settlements.
- Stopford, M. (2009). *Maritime Economics* (edisi ke-3). Routledge.

Data: laporan keuangan dan *Annual Report* PT Samudera Indonesia Tbk; Informasi Tambahan Sukuk Ijarah II–III; Drewry *World Container Index*; FRED (EIA dan OECD); proyeksi makro dan *Industry Rating & Outlook 2026 Angkutan Laut Kontainer*, Mandiri OCE; Linerlytica; Samudera Indonesia Research Initiative (SIRI). Rinciannya ada pada `data/00_registry/sources.csv`.""")

md(r"""## Lampiran A. Verifikasi persamaan terhadap implementasi

Setiap persamaan penting dihitung ulang dari input dan dibandingkan dengan output model (selisih harus nol). Persamaan (8)–(12) diverifikasi oleh kecocokan 3.754 sel antara model Python dan model Excel berumus hidup (`model/SMDR_Financial_Model.xlsx`).""")

code(r"""checks = []
def chk(label, got, ref, tol=1e-6):
    checks.append([label, got, ref, got - ref, "PASS" if abs(got - ref) <= tol * max(1, abs(ref)) else "FAIL"])
# (1) ND sekarang
chk("(1) ND TTM Sep 2026", debt0 / ebitda0, float(sr[(sr.skenario == "Dasar") & (sr.case == "central")].iloc[0].nd_FY2026) * float(sr[(sr.skenario == "Dasar") & (sr.case == "central")].iloc[0].ebitda_FY2026) / ebitda0)
# (2) penyebut DSCR
den0 = np.mean([float(pd.read_csv(dp.table("historical_test.csv")).set_index("index").loc[y, "ebitda"]) / r for y, r in (("FY2024", 1.89), ("FY2025", 2.11))])
chk("(2) penyebut tersirat DSCR", den0, rb.dscr_denominator(w)["den"])
# (3) Current Ratio terendah, seluruh 12 hasil
due = cvn.SUKUK_DUE_12M; worst = 0.0
for (k, case), g in cp.groupby(["skenario", "case"]):
    g = g.set_index("month"); crs = [(b["ca"] - (inp["opening_cash"] - g.loc[f"{fy[2:]}-12", "closing"])) / (b["cl"] + due[fy]) for fy in cvn.FYS]
    ref = float(sr[(sr.skenario == k) & (sr.case == case)].iloc[0].current_ratio_min); worst = max(worst, abs(min(crs) - ref))
chk("(3) Current Ratio terendah, 12 hasil (selisih maks.)", worst, 0.0, tol=1e-6)
# (4)-(6) EBITDA FY2027 pada tiga skenario pasar
nar2 = br.narratives().set_index("kisah"); worst = 0.0
for k in ("Permintaan melemah", "Kelebihan kapasitas", "Permintaan lemah dan kelebihan kapasitas"):
    n = nar2.loc[k]; shift = dE(float(n.tarif), float(n.volume)) / 12; months = [f"2027-{m:02d}" for m in range(1, 13)]
    idx = {m: i for i, m in enumerate(pd.period_range("2026-10", "2031-12", freq="M").astype(str))}
    e27 = sum(ebitda0 / 12 + (shift if idx[m] < int(n.bulan) else 0.0) for m in months)
    worst = max(worst, abs(e27 - float(sr[(sr.skenario == k) & (sr.case == "central")].iloc[0].ebitda_FY2027)))
chk("(4)-(6) EBITDA FY2027, 3 skenario pasar (selisih maks.)", worst, 0.0, tol=1e-6)
# (7) headroom penurunan tarif
chk("(7) headroom penurunan tarif g*", (debt0 / cvn.TH_ND - ebitda0) / F, tr.breakeven_rate(inp, debt0 / cvn.TH_ND / 1.10, 0.0, a_op))
# (13) EBITDA 12 bulan kuartalan
cq_ = cq[(cq.skenario == "Kelebihan kapasitas") & (cq.case == "central") & (cq.quarter == "2027-09")].iloc[0]
e = cp[(cp.skenario == "Kelebihan kapasitas") & (cp.case == "central")].set_index("month")["ebitda"]
chk("(13) EBITDA 12 bulan, Sep 2027", float(e["2026-10":"2027-09"].sum()), float(cq_.ebitda_ttm))
# (14)-(15) backtest dan ruang
ratio = bt.set_index("periode"); chk("(14) rasio prediksi / aktual FY2023", ratio.loc["FY2023", "model"] / ratio.loc["FY2023", "terealisasi"], 1 + float(ratio.loc["FY2023", "galat_pct"]) / 100)
g_star = (debt0 / cvn.TH_ND - ebitda0) / F
chk("(15) ruang FY2024 = g* x prediksi/aktual", g_star * ratio.loc["FY2024", "model"] / ratio.loc["FY2024", "terealisasi"], g_star * (1 + float(ratio.loc["FY2024", "galat_pct"]) / 100))
# (16) mitigasi
m_ = mt[(mt.skenario == "Kelebihan kapasitas") & (mt.case == "central") & (mt.paydown == 54.0) & (~mt.dividend_stop)].iloc[0]
r_ = sr[(sr.skenario == "Kelebihan kapasitas") & (sr.case == "central")].iloc[0]
chk("(16) ND setelah pelunasan 54", (r_.nd_FY2027 * r_.ebitda_FY2027 - 54.0) / r_.ebitda_FY2027, float(m_.nd_FY2027))
# (17) persentil ke-90 Brent
from smdr.transition.robustness import _long_series
bm, fxs = _long_series(); rb12 = (bm / bm.shift(12) - 1).dropna()
chk("(17) persentil 90 perubahan 12 bulan Brent", float(rb12.quantile(0.9)), float(sv["brent_p90"]))
res = pd.DataFrame(checks, columns=["Persamaan", "Dihitung ulang", "Output model", "Selisih", "Status"])
caption("Tabel A1. Verifikasi persamaan terhadap implementasi", "Tolerance relatif 1e-6.")
md_table(res, fmt={"Dihitung ulang": 6, "Output model": 6, "Selisih": 9})
assert (res.Status == "PASS").all(), res""")

md(r"""## Lampiran B. Sensitivitas kas satu-per-satu (*downside case*)

Tabel B1 menggeser satu parameter kas ke sisi merugikan dengan parameter lain pada asumsi tengah, pada skenario terburuk, dan melaporkan penurunan kas ditambah deposito terendah. Tabel ini dihitung di Python dengan menjalankan ulang model per parameter; ia tidak ditiru dalam rumus Excel.""")

code(r"""tor = pd.read_csv(dp.table("cash_tornado.csv"))
t = tor[["label", "central", "adverse", "d_min_liq"]]; t.columns = ["Parameter", "Tengah", "Merugikan", "Perubahan kas minimum (USD juta)"]
caption("Tabel B1. Sensitivitas kas satu-per-satu", "Skenario terburuk, refinancing bank (rollover). Sumber: data/04_marts/results/cash_tornado.csv.")
md_table(t, fmt={"Tengah": 2, "Merugikan": 2, "Perubahan kas minimum (USD juta)": 1})""")

code(r"""fig, ax = plt.subplots(figsize=(8.2, 3.9)); fstyle(ax, grid=False); ftitle(ax, "Sensitivitas kas minimum satu-per-satu, skenario terburuk (USD juta)")
tt = tor.sort_values("d_min_liq", ascending=False).reset_index(drop=True)
cols = [KUNING if i >= len(tt) - 4 else ABU for i in range(len(tt))]
ax.barh(range(len(tt)), tt.d_min_liq, color=cols, height=0.62, zorder=3)
for i, v in enumerate(tt.d_min_liq): ax.text(v - 2, i, idn(v, 1), ha="right", va="center", fontsize=8.6, color=INK, fontweight="bold")
ax.set_yticks(range(len(tt))); ax.set_yticklabels(tt.label, fontsize=8.8, color=INK); ax.axvline(0, color=INK, lw=0.8)
ax.set_xlim(tt.d_min_liq.min() * 1.18, 6); ax.xaxis.set_visible(False); ax.spines["bottom"].set_visible(False); ax.spines["left"].set_visible(False); ax.tick_params(axis="y", length=0)
plt.tight_layout(); plt.show()
caption_below("Gambar 6. Sensitivitas kas minimum satu-per-satu", "Setiap batang = penurunan kas + deposito terendah bila satu parameter ke sisi merugikan. Kuning = empat pendorong terbesar. Sumber: data/04_marts/results/cash_tornado.csv.")""")


md(r"""## Lampiran C. Reproduksi

Seluruh naskah ini dibangun dari data oleh `notebooks/build_paper.py`: angka pada teks dihitung dari `data/04_marts` dan data kanonik, tabel dan gambar dieksekusi pada notebook, dan persamaan pada Lampiran A diverifikasi terhadap implementasi. Alur data dan perlakuannya: `data/README.md` dan `docs/data-treatment.md`. Model Excel berumus hidup, dengan kecocokan sel per sel terhadap model Python: `model/SMDR_Financial_Model.xlsx`.""")

SETUP = r"""import os, sys, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.abspath("../src"))
import numpy as np, pandas as pd, matplotlib.pyplot as plt
from IPython.display import Markdown, display
from smdr import baseline, datapaths as dp, covenant_band as cb
from smdr.transition import covenants as cvn, robustness as rb, transmission as tr, cashflow as cf
plt.rcParams.update({"font.family": ["Arial", "DejaVu Sans"], "axes.unicode_minus": True, "figure.dpi": 110})
INK, KUNING, MERAH, ABU, ABU_D = "#0D0403", "#FDB913", "#ED1C24", "#BCBEC0", "#6D6E71"
EN = {"Dasar": "Base Case", "Energi bertahan": "Prolonged Energy", "Gabungan": "Combined", "Permintaan melemah": "Demand Slowdown", "Kelebihan kapasitas": "Overcapacity", "Permintaan lemah dan kelebihan kapasitas": "Weak Demand + Overcapacity"}
inp = cf._init(); w = baseline.load_wide(); b = cvn.base_position(w); ebitda0 = inp["ebitda"]; debt0 = b["bank"] + b["sukuk"] + b["lease"]
SERIF = ["Times New Roman", "DejaVu Serif"]
MON = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]
def mlabel(m):
    return f"{MON[int(m[5:7]) - 1]} {m[2:4]}"
def fstyle(ax, grid=True):
    for sp in ("top", "right"): ax.spines[sp].set_visible(False)
    for sp in ("left", "bottom"): ax.spines[sp].set_color(ABU)
    ax.tick_params(length=0, labelsize=8.5, colors=ABU_D)
    if grid:
        ax.yaxis.grid(True, color="#EFEFF0", lw=0.8); ax.set_axisbelow(True)
def ftitle(ax, text):
    ax.set_title(text, loc="left", fontsize=11.5, fontweight="bold", fontfamily=SERIF, pad=12, color=INK)
def spread(vals, gap):
    order = sorted(range(len(vals)), key=lambda i: vals[i]); out = list(vals)
    for k in range(1, len(order)):
        i, j = order[k - 1], order[k]
        if out[j] - out[i] < gap: out[j] = out[i] + gap
    return out
OVR, WRS, DEM = "Kelebihan kapasitas", "Permintaan lemah dan kelebihan kapasitas", "Permintaan melemah"

def idn(x, d=1):
    s = f"{abs(x):,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return ("−" if x < 0 else "") + s

def caption(title, note=""):
    display(Markdown(f"**{title}**" + (f"  \n*{note}*" if note else "")))

def caption_below(title, note=""):
    display(Markdown(f"**{title}**" + (f"  \n*{note}*" if note else "")))

def md_table(df, fmt=None):
    fmt = fmt or {}
    head = "| " + " | ".join(str(c) for c in df.columns) + " |\n|" + "|".join("---" if i == 0 else "---:" for i, _ in enumerate(df.columns)) + "|\n"
    rows = []
    for _, r in df.iterrows():
        cells = []
        for c in df.columns:
            v = r[c]
            if isinstance(v, (int, float, np.integer, np.floating)) and not isinstance(v, bool):
                cells.append(idn(float(v), fmt.get(c, 2)))
            else:
                cells.append(str(v))
        rows.append("| " + " | ".join(cells) + " |")
    display(Markdown(head + "\n".join(rows)))
"""


# ================================================================ angka tambahan, rakitan, eksekusi
def extend_numbers(N):
    wci = pd.read_csv(dp.table("wci_composite_weekly.csv"), parse_dates=["date"]).set_index("date")["wci"]
    ann = wci.groupby(wci.index.year).mean()
    for y in (2020, 2021, 2023, 2024):
        N[f"wci_{y}"] = float(ann[y])
    ht = pd.read_csv(dp.table("historical_test.csv")).set_index("index")
    N.update(e22=ht.loc["FY2022", "ebitda"], e23=ht.loc["FY2023", "ebitda"], e24=ht.loc["FY2024", "ebitda"], n_obs=3)
    bt = pd.read_csv(dp.table("backtest.csv")).set_index("periode")
    for p in ("FY2023", "FY2024", "FY2025"):
        N[f"bt_rate_{p}_a"] = abs(N[f"bt_rate_{p}"]); N[f"bt_pred_{p}_a"] = abs(N[f"bt_pred_{p}"]); N[f"bt_act_{p}_a"] = abs(N[f"bt_act_{p}"])
    sr_all = pd.read_csv(dp.table("scenario_results.csv"))
    ck = pd.read_csv(dp.table("fs_checks.csv")); N.update(chk_n=len(ck), chk_pass=int((ck.status == "PASS").sum()), chk_known=int((ck.status == "KNOWN").sum()))
    w_ = baseline.load_wide(); bk = [cvn.base_position(w_, p)["bank"] for p in ("FY2023", "FY2024", "FY2025", "9M26")]; N.update(bank_min=min(bk), bank_max=max(bk))
    N["wci_g24"] = (ann[2024] / ann[2023] - 1) * 100
    inp_ = __import__("smdr.transition.cashflow", fromlist=["x"])._init(); rs = inp_["rev_by_service"]; N["svc_freight_pct"] = rs["freight_income"] / rs.sum() * 100
    a_ = tr.assumptions(); Fx, Ax, Hx = rs["freight_income"], rs["agency_forwarding_ports"], rs["container_equipment_handling"]
    for tag, key in (("lo", "low"), ("hi", "high")):
        psi = float(a_.loc["cost_flex_down", key]); v_, g_ = -0.05, -0.12
        d_ = Fx * ((1 + v_) * (1 + g_) - 1) + (Ax + Hx) * v_ - psi * (inp_["cogs"] - inp_["cogs_dep"]) * ((Fx + Ax + Hx) / inp_["revenue"]) * v_
        N[f"psi_{tag}_nd"] = N["debt"] / (inp_["ebitda"] + d_)
    br_ = pd.read_csv(dp.table("baseline_bridge.csv")).set_index("metric")["reconciled_value"]; N["ebitda_legacy"] = br_["ebitda_ttm_legacy"] / 1e6
    N["headroom_legacy"] = abs((N["debt"] / cvn.TH_ND - N["ebitda_legacy"]) / Fx) * 100
    N["e25"] = ht.loc["FY2025", "ebitda"]
    N["vol_effect"] = N["e27_ovr_c"] - N["e27_wrs_c"]
    N["r_lo"] = N["sev_rate_pct"] / N["sev_brent_pct_a"]; N["r_hi"] = N["sev_rate_pct"] / N["sev_brent_pct"]
    red = lambda col: (N["ebitda"] - col) / N["ebitda"] * 100
    mac = sr_all[sr_all.skenario.isin(["Dasar", "Energi bertahan", "Gabungan"])].ebitda_FY2027; mkt = sr_all[(~sr_all.skenario.isin(["Dasar", "Energi bertahan", "Gabungan"])) & (sr_all.case == "central")].ebitda_FY2027
    N.update(mc_lo=red(mac.max()), mc_hi=red(mac.min()), mk_lo=red(mkt.max()), mk_hi=red(mkt.min()))
    N["cost23"] = abs(float(bt.loc["FY2023", "biaya_jasa_delta"])); N["act_ratio24"] = N["bt_act_FY2024"] / N["bt_pred_FY2024"] * 100
    cen = [k for k in N if k.startswith("cov27_") and k.endswith("_c")]
    sr = pd.read_csv(dp.table("scenario_results.csv")); c = sr[sr.case == "central"]
    N["dscr_min_c"] = float(np.minimum(c.cover_FY2027, c.cover_FY2028).min()); N["cr_min_c"] = float(c.current_ratio_min.min()); N["liq_min_c"] = float(c.min_liquidity.min())
    N["ovr_margin"] = N["qpk_ovr_c"] - 3.0
    m = lambda a, b: (pd.Period(b, "M") - pd.Period(a, "M")).n
    N["lag_cr"] = m("2027-09", f"{N['cr_breach_fy_wrs'][2:]}-12"); N["lag_liq"] = m("2027-09", N["liq_first_wrs"]); N["lead"] = m("2027-03", "2027-09")
    for k in ("liq_first_wrs", "liq_first_ovr"):
        y, mo = N[k].split("-"); N[k] = ["", "Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"][int(mo)] + " " + y
    N["cr_breach_fy_wrs"] = "Desember " + str(N["cr_breach_fy_wrs"])[2:]
    return N


def build():
    N = extend_numbers(load_numbers())
    nb = nbf.v4.new_notebook()
    nb.metadata["kernelspec"] = {"display_name": "Python 3", "language": "python", "name": "python3"}
    cells = [nbf.v4.new_code_cell(SETUP)]
    cells[0].metadata["tags"] = ["hide-input"]
    for kind, text in CELLS:
        if kind == "md":
            cells.append(nbf.v4.new_markdown_cell(fill(text, N)))
        else:
            c = nbf.v4.new_code_cell(text); c.metadata["tags"] = ["hide-input"]; cells.append(c)
    nb.cells = cells
    return nb, N


def execute(nb):
    from nbclient import NotebookClient
    NotebookClient(nb, timeout=600, kernel_name="python3", resources={"metadata": {"path": os.path.join(ROOT, "notebooks")}}).execute()
    return nb


def main():
    nb, N = build()
    nb = execute(nb)
    nbf.write(nb, OUT)
    import subprocess
    subprocess.run([sys.executable, "-m", "jupyter", "nbconvert", "--to", "html", "--no-input", "--output", "paper.html", OUT], check=True, capture_output=True, cwd=os.path.join(ROOT, "notebooks"))
    words = sum(len(c.source.split()) for c in nb.cells if c.cell_type == "markdown")
    print("naskah: %d sel, sekitar %d kata (teks markdown)" % (len(nb.cells), words))


if __name__ == "__main__":
    main()
