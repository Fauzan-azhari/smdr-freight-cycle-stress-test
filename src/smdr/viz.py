"""Gaya dan grafik untuk notebook. Satu palet tervalidasi (biru, oranye), satu sumbu per grafik,
label langsung, dan catatan sumber di setiap grafik."""
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter, MultipleLocator

BIRU, ORANYE, INK, INK2, GRID, SURFACE = "#2a78d6", "#eb6834", "#0b0b0b", "#52514e", "#e6e5e1", "#fcfcfb"
SUMBER = "Sumber: laporan keuangan konsolidasian SMDR; perhitungan penulis. Data 2026 belum diaudit."


def idn(x, d=1):
    """Format angka gaya Indonesia: 1.234,5."""
    return f"{x:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def apply_style():
    plt.rcParams.update({
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "axes.edgecolor": GRID, "axes.labelcolor": INK2,
        "xtick.color": INK2, "ytick.color": INK2, "text.color": INK, "axes.spines.top": False, "axes.spines.right": False,
        "axes.grid": True, "axes.axisbelow": True, "grid.color": GRID, "grid.linewidth": 0.6, "font.size": 10,
        "axes.titleweight": "bold", "axes.titlelocation": "left", "axes.titlesize": 11, "figure.dpi": 110})


def _frame(fig, catatan):
    fig.text(0.01, 0.01, catatan, fontsize=7.8, color=INK2, ha="left", va="bottom")
    fig.tight_layout(rect=(0, 0.045, 1, 1))
    return fig


def _juta_axis(ax, d=0):
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: idn(v, d)))
    ax.grid(axis="x", visible=False)


def quarterly(q):
    """Pendapatan dan EBIT per kuartal, dua panel karena skalanya berbeda."""
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.7))
    for ax, kolom, judul in ((axes[0], "revenue", "Pendapatan (USD juta)"), (axes[1], "ebit", "EBIT (USD juta)")):
        v = q[kolom] / 1e6
        ax.bar(v.index, v.values, color=BIRU, width=0.62)
        for i, x in enumerate(v.values):
            ax.text(i, x + v.max() * 0.015, idn(x), ha="center", va="bottom", fontsize=8.5, color=INK2)
        ax.set_title(judul); ax.set_ylim(0, v.max() * 1.14); ax.tick_params(axis="x", labelsize=8.5); _juta_axis(ax)
    return _frame(fig, SUMBER)


def composition(c):
    """EBITDA operasi per tahun dan TTM, dibagi EBIT dan penyusutan."""
    x, e, d = list(c.index), c["ebit"].values / 1e6, c["depreciation"].values / 1e6
    fig, ax = plt.subplots(figsize=(8.4, 4.2))
    ax.bar(x, e, color=BIRU, width=0.58, label="EBIT", edgecolor=SURFACE, linewidth=1.5)
    ax.bar(x, d, bottom=e, color=ORANYE, width=0.58, label="Penyusutan", edgecolor=SURFACE, linewidth=1.5)
    for i, (a, b) in enumerate(zip(e, d)):
        ax.text(i, a + b + (e + d).max() * 0.02, f"{idn(a + b)}\npenyusutan {idn(b / (a + b) * 100, 0)}%", ha="center", fontsize=8.5, color=INK2)
    ax.set_ylim(0, (e + d).max() * 1.2); _juta_axis(ax); ax.legend(frameon=False, loc="upper right", fontsize=9)
    last = c["depreciation_share"].iloc[-1]
    ax.set_title(f"Penyusutan menopang {idn(last, 0)}% EBITDA operasi pada TTM Sep-2026 (USD juta)")
    return _frame(fig, SUMBER)


def cover(band, threshold):
    """Cover covenant pada tanggal uji tahunan terhadap batas klausul."""
    fig, ax = plt.subplots(figsize=(8.4, 3.9))
    ax.plot(band.index, band["cover"], color=BIRU, lw=2, marker="o", ms=8, mec=SURFACE, mew=2)
    for i, v in enumerate(band["cover"]):
        ax.text(i, v + band["cover"].max() * 0.055, idn(v, 2) + "x", ha="center", fontsize=9.5, color=INK)
    ax.axhline(threshold, color=INK2, lw=1.2, ls=(0, (4, 3)))
    ax.text(-0.2, threshold + 0.1, f"batas klausul {idn(threshold, 2)}x", color=INK2, fontsize=8.5)
    ax.set_xlim(-0.25, len(band) - 0.75); ax.set_ylim(0, band["cover"].max() * 1.2)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: idn(v, 1) + "x")); ax.grid(axis="x", visible=False)
    ax.set_title(f"Ruang terhadap batas covenant menyusut: cover {idn(band['cover'].iloc[-1], 2)}x pada {band.index[-1]}")
    return _frame(fig, "Proforma atas laporan keuangan tahunan; bagian lancar liabilitas sewa diperhitungkan pada penyebut. Perhitungan penulis.")


def tabel(df, desimal=1, na_rep="n/a"):
    """Tabel dengan format angka Indonesia; kolom non-numerik dibiarkan."""
    df = df.rename_axis([None] * df.index.nlevels if df.index.nlevels > 1 else None)
    return df.style.format(lambda v: idn(v, desimal) if isinstance(v, (int, float)) else v, na_rep=na_rep)


BULAN = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]


def tanggal(d):
    """Tanggal gaya Indonesia: 2 Agu 2028."""
    return f"{d.day} {BULAN[d.month - 1]} {d.year}"


def debt_calendar(annual):
    """Kewajiban kas sukuk per tahun kalender: imbalan dan pokok (USD juta, kurs ilustrasi)."""
    x = [("2026\n(Okt-Des)" if y == 2026 else str(y)) for y in annual.index]
    imb, pok = annual["imbalan"].values, annual["pokok"].values
    fig, ax = plt.subplots(figsize=(8.4, 4.1))
    ax.bar(x, imb, color=BIRU, width=0.58, label="Imbalan", edgecolor=SURFACE, linewidth=1.5)
    ax.bar(x, pok, bottom=imb, color=ORANYE, width=0.58, label="Pokok (bullet)", edgecolor=SURFACE, linewidth=1.5)
    for i, (a, b) in enumerate(zip(imb, pok)):
        ax.text(i, a + b + (imb + pok).max() * 0.02, idn(a + b), ha="center", fontsize=9, color=INK2)
    ax.set_ylim(0, (imb + pok).max() * 1.16); _juta_axis(ax); ax.legend(frameon=False, loc="upper left", fontsize=9)
    peak = annual["total"].idxmax()
    ax.set_title(f"Kewajiban kas sukuk memuncak pada {peak}: USD {idn(annual['total'].max())} juta (imbalan dan pokok)")
    return _frame(fig, "Jadwal kontraktual; tanggal bayar disesuaikan untuk akhir pekan. Konversi USD memakai kurs ilustrasi. Perhitungan penulis.")


def covenant_timing(timing):
    """Pokok yang masuk bagian lancar pada tutup buku vs pokok yang dibayar tunai pada tahun itu."""
    import numpy as np
    x = np.arange(len(timing)); wd = 0.36
    fig, ax = plt.subplots(figsize=(8.4, 4.1))
    ax.bar(x - wd / 2, timing["bagian_lancar"], wd, color=BIRU, label="Masuk bagian lancar pada tutup buku (uji covenant)", edgecolor=SURFACE, linewidth=1.5)
    ax.bar(x + wd / 2, timing["dibayar_tunai"], wd, color=ORANYE, label="Dibayar tunai pada tahun itu", edgecolor=SURFACE, linewidth=1.5)
    for i, (a, b) in enumerate(zip(timing["bagian_lancar"], timing["dibayar_tunai"])):
        for xx, v in ((i - wd / 2, a), (i + wd / 2, b)):
            # nilai nol tetap diberi label agar terbaca sebagai nol, bukan data kosong
            ax.text(xx, v + timing.max().max() * 0.015, idn(v) if v > 0 else "0", ha="center", fontsize=8.5, color=INK2)
    ax.set_xticks(x); ax.set_xticklabels([str(t) for t in timing.index]); ax.set_ylim(0, timing.max().max() * 1.35)
    _juta_axis(ax); ax.legend(frameon=False, loc="upper left", fontsize=8.8)
    ax.set_title("Pokok sukuk membebani uji covenant satu tahun lebih awal dari kas (USD juta)")
    return _frame(fig, "Bagian lancar = pokok yang jatuh tempo dalam 12 bulan setelah tutup buku. Kurs ilustrasi. Perhitungan penulis.")


def _hist_and_paths(ax, hist, paths, driver, styles, ylabel_fmt):
    """Riwayat bulanan (abu tua) dan jalur skenario (berwarna), dengan label langsung di ujung jalur."""
    import pandas as pd
    hx = [pd.Period(m, "M").to_timestamp() for m in hist.index]
    ax.plot(hx, hist.values, color=INK2, lw=1.6, label="Realisasi bulanan")
    for sid, (nama, warna, gaya) in styles.items():
        p = paths[(paths.scenario_id == sid) & (paths.driver == driver)].sort_values("month")
        p = p[p.month <= "2028-12"]
        px = [pd.Period(m, "M").to_timestamp() for m in p.month]
        ax.plot(px, p.value.values, color=warna, lw=2, ls=gaya, label=nama)
        ax.text(px[-1] + pd.Timedelta(days=25), p.value.values[-1], ylabel_fmt(p.value.values[-1]), color=INK, fontsize=8.5, va="center")
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: idn(v, 0))); ax.grid(axis="x", visible=False)


def brent_scenarios(hist, paths, plateau):
    """Brent: riwayat dan tiga jalur normalisasi; pita abu = rentang interkuartil plateau pasca-2022."""
    import pandas as pd
    fig, ax = plt.subplots(figsize=(9.4, 4.4))
    ax.axhspan(plateau[0], plateau[1], color=GRID, alpha=0.7, lw=0)
    ax.text(pd.Timestamp("2021-02-01"), plateau[1] + 1.5, "plateau pasca-2022 (rentang interkuartil)", fontsize=8, color=INK2)
    styles = {"MS-BASE": ("Dasar", BIRU, "-"), "MS-ENERGY": ("Energi bertahan", ORANYE, "-"), "MS-NORMAL": ("Normalisasi cepat", INK, (0, (4, 3)))}
    _hist_and_paths(ax, hist, paths, "brent", styles, lambda v: idn(v, 0))
    ax.set_xlim(pd.Timestamp("2021-01-01"), pd.Timestamp("2029-03-01")); ax.set_ylim(40, 140)
    ax.legend(frameon=False, loc="upper left", fontsize=8.8, ncol=2)
    ax.set_title(f"Brent Oktober 2026 (USD {idn(hist.iloc[-1], 0)}) di atas seluruh bulan penuh sejak 2021 (USD/barel)")
    return _frame(fig, "Rata-rata bulanan harga spot Brent; bulan Oktober 2026 parsial (hingga 27 Okt). Jalur skenario = asumsi penulis. Perhitungan penulis.")


def fx_scenarios(hist, paths, oce_range):
    """USD/IDR: riwayat dan tiga jalur; batang vertikal = rentang proyeksi enam bulan OCE (26 Okt 2026)."""
    import pandas as pd
    fig, ax = plt.subplots(figsize=(9.4, 4.4))
    styles = {"MS-BASE": ("Dasar", BIRU, "-"), "MS-FX": ("Tekanan kurs", ORANYE, "-"), "MS-COMBINED": ("Gabungan", INK, (0, (4, 3)))}
    _hist_and_paths(ax, hist, paths, "usdidr", styles, lambda v: idn(v, 0))
    t = pd.Timestamp("2027-04-01")
    ax.vlines(t, oce_range[0], oce_range[1], color=INK2, lw=5, alpha=0.55)
    ax.text(t + pd.Timedelta(days=12), oce_range[0] - 190, "rentang proyeksi OCE\n(6 bulan)", fontsize=8, color=INK2, va="top")
    ax.set_xlim(pd.Timestamp("2020-01-01"), pd.Timestamp("2029-03-01")); ax.set_ylim(13000, 20200)
    ax.legend(frameon=False, loc="upper left", fontsize=8.8, ncol=2)
    ax.set_title("Skenario tekanan kurs melampaui rentang proyeksi resmi OCE (IDR per USD)")
    return _frame(fig, "Penutupan bulanan; November 2026 parsial. Guncangan diukur terhadap jalur dasar. Jalur skenario = asumsi penulis. Perhitungan penulis.")


def bulan(periode):
    """'2022-06' -> 'Jun 2022'."""
    y, m = periode.split("-")
    return f"{BULAN[int(m) - 1]} {y}"


def _grouped(ax, labels, central, adverse, fmt):
    import numpy as np
    x = np.arange(len(labels)); wd = 0.36
    ax.bar(x - wd / 2, central, wd, color=BIRU, label="Parameter tengah", edgecolor=SURFACE, linewidth=1.5)
    ax.bar(x + wd / 2, adverse, wd, color=ORANYE, label="Parameter merugikan", edgecolor=SURFACE, linewidth=1.5)
    span = max(abs(min(list(central) + list(adverse))), abs(max(list(central) + list(adverse)))) or 1
    for xx, vals in ((x - wd / 2, central), (x + wd / 2, adverse)):
        for a_, v in zip(xx, vals):
            ax.text(a_, v + (span * 0.025 if v >= 0 else -span * 0.025), fmt(v), ha="center", va="bottom" if v >= 0 else "top", fontsize=8.5, color=INK2)
    ax.set_xticks(x); ax.set_xticklabels(labels, fontsize=8.8); ax.grid(axis="x", visible=False)
    ax.legend(frameon=False, loc="best", fontsize=8.8)


def scenario_ebitda(res, order):
    """Perubahan EBITDA 12 bulan menurut skenario (USD juta): parameter tengah dan merugikan."""
    c = res[res.case == "central"].set_index("scenario").loc[order]["d_ebitda"]
    a = res[res.case == "adverse"].set_index("scenario").loc[order]["d_ebitda"]
    fig, ax = plt.subplots(figsize=(9.4, 4.2))
    _grouped(ax, order, c.values, a.values, lambda v: idn(v, 1))
    ax.axhline(0, color=INK2, lw=0.8); ax.set_ylim(min(a.min(), c.min()) * 1.25, max(c.max(), a.max(), 0) + 3)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: idn(v, 0)))
    worst = order[int(a.values.argmin())]
    ax.set_title(f"Skenario {worst.lower()} memangkas EBITDA hingga USD {idn(abs(a.min()), 0)} juta pada 12 bulan pertama")
    return _frame(fig, "Selisih terhadap EBITDA operasi TTM Sep-2026 (USD 240 juta); bunker dan translasi kurs. Pro forma, bukan proyeksi. Perhitungan penulis.")


def cover_scenarios(res, order, threshold):
    """Cover uji FY2027 pro forma menurut skenario terhadap batas klausul."""
    c = res[res.case == "central"].set_index("scenario").loc[order]["cover"]
    a = res[res.case == "adverse"].set_index("scenario").loc[order]["cover"]
    fig, ax = plt.subplots(figsize=(9.4, 4.2))
    _grouped(ax, order, c.values, a.values, lambda v: idn(v, 2) + "x")
    ax.axhline(threshold, color=INK, lw=1.2, ls=(0, (4, 3))); ax.set_xlim(-0.6, len(order) + 0.45); ax.text(len(order) - 0.4, threshold, f"batas klausul\n{idn(threshold, 2)}x", ha="left", va="center", fontsize=8.5, color=INK2)
    ax.set_ylim(0, max(c.max(), a.max()) * 1.25); ax.yaxis.set_major_locator(MultipleLocator(0.2)); ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: idn(v, 1) + "x"))
    ax.set_title(f"Cover uji FY2027 pro forma tersisa {idn(a.min(), 2)}x pada skenario {a.idxmin().lower()} dengan parameter merugikan")
    return _frame(fig, "Pro forma berbasis posisi 30 Sep 2026 dan pokok Seri B pada penyebut; bukan proyeksi atau sertifikat kepatuhan. Perhitungan penulis.")


def rate_volume(grid, breakeven, threshold):
    """Cover uji FY2027 terhadap perubahan tarif angkut untuk tiga kasus volume; penanda = titik impas pada volume tetap."""
    fig, ax = plt.subplots(figsize=(9.4, 4.4))
    styles = {-0.10: ("Volume -10%", ORANYE, "-"), 0.0: ("Volume tetap", BIRU, "-"), 0.10: ("Volume +10%", INK, (0, (4, 3)))}
    for v, (nm, col, ls) in styles.items():
        g = grid[grid.volume == v].sort_values("rate")
        ax.plot(g.rate * 100, g.cover, color=col, lw=2, ls=ls, label=nm)
    ax.axhline(threshold, color=INK2, lw=1.2, ls=(0, (2, 2))); ax.text(10, threshold + 0.03, f"batas klausul {idn(threshold, 2)}x", ha="right", fontsize=8.5, color=INK2)
    cols = {k: v[1] for k, v in styles.items()}
    offs = {-0.10: (1.5, -0.32), 0.0: (-5.5, 0.34), 0.10: (-8.5, 0.34)}
    for v, b in breakeven.items():
        ax.scatter([b * 100], [threshold], color=cols[v], s=55, zorder=3, edgecolor=SURFACE, linewidth=1.5)
        dx, dy = offs[v]
        ax.annotate(f"impas {idn(b * 100, 1)}%", (b * 100, threshold), xytext=(b * 100 + dx, threshold + dy), fontsize=8.8, color=INK, ha="center",
                    arrowprops=dict(arrowstyle="-", color=INK2, lw=0.8))
    base = grid[(grid.volume == 0.0) & (grid.rate.abs() < 1e-9)].cover.iloc[0]
    ax.scatter([0], [base], marker="D", color=INK, s=42, zorder=4, edgecolor=SURFACE, linewidth=1.2)
    ax.annotate(f"posisi awal {idn(base, 2)}x", (0, base), xytext=(-9, base + 0.22), fontsize=8.8, color=INK, ha="center", arrowprops=dict(arrowstyle="-", color=INK2, lw=0.8))
    be = breakeven[0.0] * 100
    ax.set_xlabel("Perubahan tarif angkut (%)"); ax.set_ylim(0, 2.0); ax.set_xlim(-40, 10); ax.yaxis.set_major_locator(MultipleLocator(0.2))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: idn(v, 1) + "x")); ax.legend(frameon=False, loc="upper left", fontsize=8.8)
    ax.set_title(f"Ruang cover habis pada tarif {idn(be, 0)}% bila volume tetap, dan sudah habis bila volume turun 10%")
    return _frame(fig, "Perubahan relatif terhadap TTM Sep-2026; biaya lengket pada penurunan volume (parameter tengah). Pro forma. Perhitungan penulis.")


# --- jalur kas ---------------------------------------------------------------------------------------------------

def _ym(m):
    return ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"][int(m[5:]) - 1] + " " + m[:4]


def cash_paths(v):
    """Saldo kas bulanan skenario Dasar (parameter tengah dan merugikan), dengan dan tanpa deposito berjangka lancar."""
    import numpy as np
    from matplotlib.ticker import MultipleLocator as ML
    c, a = v.paths[("Dasar", "central")], v.paths[("Dasar", "adverse")]
    x = np.arange(len(c))
    fig, ax = plt.subplots(figsize=(9.6, 4.6))
    ax.plot(x, c["closing"], color=BIRU, lw=2.2, label="Kas, parameter tengah")
    ax.plot(x, a["closing"], color=ORANYE, lw=2.2, label="Kas, parameter merugikan")
    ax.plot(x, c["liquidity"], color=BIRU, lw=1.4, ls=(0, (4, 3)), label="Kas + deposito lancar, tengah")
    ax.plot(x, a["liquidity"], color=ORANYE, lw=1.4, ls=(0, (4, 3)), label="Kas + deposito lancar, merugikan")
    ax.axhline(v.threshold, color=INK, lw=1.0, ls=(0, (1, 2)))
    ax.axhline(0, color=INK2, lw=0.8)
    ax.text(0, v.threshold + 8, f"batas kas usulan USD {idn(v.threshold, 0)} juta", ha="left", fontsize=8.3, color=INK2)
    for m, nm in (("2028-08", "Seri B"), ("2029-05", "Seri III"), ("2030-07", "Seri II")):
        i = list(c.index).index(m)
        ax.axvline(i, color=GRID, lw=1.0, zorder=0)
        ax.text(i, ax.get_ylim()[1] * 0.97, "pelunasan\n" + nm, ha="center", va="top", fontsize=7.8, color=INK2)
    ticks = [i for i, m in enumerate(c.index) if m[5:] == "01"]
    ax.set_xticks(ticks); ax.set_xticklabels([c.index[i][:4] for i in ticks]); ax.grid(axis="x", visible=False)
    ax.set_xlim(-1, len(c) + 0.5)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda t, _: idn(t, 0)))
    first = v.scen[(v.scen.scenario == "Dasar") & (v.scen.case == "adverse")].iloc[0]["first_below"]
    endc = c["closing"].iloc[-1]
    ax.set_title(f"Tanpa refinancing, kas susut dari USD {idn(c['opening'].iloc[0], 0)} juta menjadi USD {idn(endc, 0)} juta pada 2031;\n"
                 f"batas kas tertembus {_ym(first)} hanya pada parameter merugikan")
    ax.legend(frameon=False, loc="lower left", fontsize=8.3, ncol=2)
    return _frame(fig, "USD juta, akhir bulan; simulasi dari posisi 30 Sep 2026 tanpa refinancing dan tanpa manfaat armada baru, EBITDA dasar pada TTM. Bukan proyeksi.")


def cash_uses(v):
    """Sumber dan penggunaan kas kumulatif Okt 2026 - Des 2031, skenario Dasar parameter tengah (air terjun)."""
    short = {"Kas operasi sebelum bunga": "Kas operasi\nsebelum bunga", "Bunga dan imbal hasil, neto": "Bunga\nneto", "Pokok sewa": "Pokok\nsewa",
             "Belanja modal pemeliharaan": "Capex\npemeliharaan", "Program kapal baru": "Program\nkapal baru", "Angsuran bank, neto": "Angsuran\nbank",
             "Pelunasan sukuk, neto": "Pelunasan\nsukuk", "Dividen": "Dividen"}
    steps = [(short[k], x) for k, x in v.uses.items() if k in short]
    trans = float(v.uses.get("Selisih translasi kurs (non-kas)", 0.0))
    start = v.inp["opening_cash"]
    end = start + sum(x for _, x in steps) + trans
    labels = ["Kas awal"] + [k for k, _ in steps] + ["Kas akhir"]
    fig, ax = plt.subplots(figsize=(9.6, 4.6))
    run, tops = start, [start]
    ax.bar(0, start, color=INK2, width=0.62, edgecolor=SURFACE, linewidth=1.5); ax.text(0, start + 16, idn(start, 0), ha="center", fontsize=8.8, color=INK)
    for i, (_, val) in enumerate(steps, start=1):
        bottom = run if val >= 0 else run + val
        ax.bar(i, abs(val), bottom=bottom, color=BIRU if val >= 0 else ORANYE, width=0.62, edgecolor=SURFACE, linewidth=1.5)
        ax.text(i, bottom + abs(val) + 16, ("+" if val >= 0 else "-") + idn(abs(val), 0), ha="center", fontsize=8.8, color=INK)
        run += val; tops.append(max(run, run - val))
    n = len(labels) - 1
    ax.bar(n, end, color=INK2, width=0.62, edgecolor=SURFACE, linewidth=1.5); ax.text(n, end + 16, idn(end, 0), ha="center", fontsize=8.8, color=INK)
    ax.set_xticks(range(len(labels))); ax.set_xticklabels(labels, fontsize=8.2)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda t, _: idn(t, 0))); ax.grid(axis="x", visible=False)
    ax.set_ylim(0, max(tops) * 1.1)
    ax.set_title(f"Kas operasi USD {idn(steps[0][1], 0)} juta tidak cukup menutup sewa, belanja modal, bunga, dividen, dan utang;\nkas akhir 2031 USD {idn(end, 0)} juta")
    return _frame(fig, f"USD juta, kumulatif Okt 2026 - Des 2031; skenario Dasar, parameter tengah, tanpa refinancing. Selisih translasi kurs non-kas (USD {idn(trans, 1)} juta) termasuk dalam kas akhir.")


def cash_tornado(v):
    """Pengaruh tiap parameter pada sisi merugikan terhadap likuiditas minimum, dibandingkan dengan guncangan makro gabungan."""
    t = v.tornado.copy()
    t = t[t["d_min_liq"].abs() >= 0.5][["label", "d_min_liq"]]
    sc = v.scen.set_index(["scenario", "case"])
    t.loc[len(t)] = ["Skenario makro gabungan (tengah)", sc.loc[("Gabungan", "central"), "min_liquidity"] - sc.loc[("Dasar", "central"), "min_liquidity"]]
    t = t.sort_values("d_min_liq", ascending=True)
    fig, ax = plt.subplots(figsize=(9.6, 4.2))
    y = range(len(t))
    cols = [INK2 if "makro" in l else ORANYE for l in t["label"]]
    ax.barh(list(y), t["d_min_liq"], color=cols, height=0.58, edgecolor=SURFACE, linewidth=1.5)
    for i, val in zip(y, t["d_min_liq"]):
        ax.text(val - 2, i, idn(val, 0), va="center", ha="right", fontsize=8.8, color=INK)
    ax.set_yticks(list(y)); ax.set_yticklabels(t["label"], fontsize=8.8); ax.invert_yaxis()
    ax.grid(axis="y", visible=False); ax.set_xlim(min(t["d_min_liq"]) * 1.18, 0)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda s, _: idn(s, 0)))
    top = t.iloc[0]
    fig.suptitle(f"Asumsi operasi menggeser likuiditas minimum lebih besar daripada guncangan makro;\nterbesar {top['label'].lower()} (USD {idn(abs(top['d_min_liq']), 0)} juta)", x=0.01, ha="left", fontsize=11, fontweight="bold")
    return _frame(fig, "Selisih saldo minimum kas + deposito 2026-2031 terhadap skenario Dasar tengah (USD juta); satu parameter di sisi merugikan, lainnya tetap.")


def cash_reverse(v, fy2028=None):
    """Batas ketahanan pada skenario Dasar: penurunan tarif angkut yang menembus tiap batas. `fy2028` = titik impas tarif uji FY2028 (opsional)."""
    rev = v.reverse[0]
    g = lambda months, metric: rev[(rev.scenario == "Dasar") & (rev.case == "central") & (rev.months == months) & (rev.metric == metric)]["rate"].iloc[0] * 100
    rows = [("Kas saja di bawah batas kas\n(tarif turun 24 bulan)", g(24, "cash"), BIRU)]
    if fy2028 is not None:
        rows.append(("Covenant FY2028 di bawah 1,10x\n(volume tetap)", fy2028 * 100, ORANYE))
    rows += [("Covenant FY2027 di bawah 1,10x\n(volume tetap)", v.cov_breakeven * 100, ORANYE),
             ("Kas + deposito di bawah batas kas\n(tarif turun 24 bulan)", g(24, "liquidity"), BIRU),
             ("Kas + deposito di bawah batas kas\n(tarif turun 12 bulan)", g(12, "liquidity"), BIRU)]
    rows.sort(key=lambda r: -r[1])
    cov = [r[1] for r in rows if r[2] == ORANYE]
    liq = g(24, "liquidity")
    fig, ax = plt.subplots(figsize=(9.6, 3.9 + 0.35 * (len(rows) - 4)))
    for i, (lb, val, col) in enumerate(rows):
        ax.barh(i, val, color=col, height=0.55, edgecolor=SURFACE, linewidth=1.5)
        ax.text(val - 0.6, i, idn(val, 1) + "%", va="center", ha="right", fontsize=9, color=INK)
    ax.set_yticks(range(len(rows))); ax.set_yticklabels([r[0] for r in rows], fontsize=8.6); ax.invert_yaxis()
    ax.grid(axis="y", visible=False); ax.set_xlim(min(r[1] for r in rows) * 1.18, 0)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda s, _: idn(s, 0) + "%"))
    tight = " atau ".join(idn(abs(c), 1) + "%" for c in sorted(cov, reverse=True)) if len(cov) > 1 else idn(abs(cov[0]), 1) + "%"
    fig.suptitle(f"Covenant tertembus lebih dulu: pada penurunan tarif {tight} (uji FY2028 atau FY2027), sedangkan kas + deposito baru pada {idn(abs(liq), 0)}%\n"
                 "(bertahan 24 bulan); kas saja nyaris tanpa ruang" if len(cov) > 1 else
                 f"Covenant tertembus lebih dulu: pada penurunan tarif {tight}, sedangkan kas + deposito baru pada {idn(abs(liq), 0)}%\n(bertahan 24 bulan); kas saja nyaris tanpa ruang",
                 x=0.01, ha="left", fontsize=10.5, fontweight="bold")
    return _frame(fig, "Perubahan tarif angkut terhadap TTM Sep-2026; skenario Dasar, parameter tengah. Biru = kas; oranye = covenant. Perhitungan penulis.")


# --- peta hasil stress test --------------------------------------------------------------------------------------
STATUS = {"Aman": ("#0ca30c", "#ffffff", "✓"), "Tipis": ("#fab219", INK, "!"), "Tertembus": ("#d03b3b", "#ffffff", "✕")}


def _status(room, safe):
    """Ruang relatif terhadap batas: di bawah 0 = tertembus; 0 sampai `safe` = tipis; sisanya aman."""
    return "Tertembus" if room < 0 else ("Tipis" if room < safe else "Aman")


def stress_heatmap(cover_res, cash_scen, cov_threshold, cash_threshold, scenarios=("Dasar", "Energi bertahan", "Gabungan")):
    """Peta hasil stress test: skenario x tiga ukuran. Warna menurut ruang terhadap batas, selalu disertai kata dan simbol."""
    cov = cover_res.set_index(["scenario", "case"])["cover"]
    cs = cash_scen.set_index(["scenario", "case"])
    cols = ["Cover covenant\nFY2027 (batas 1,10x)", f"Kas minimum 2026-2031\n(batas USD {idn(cash_threshold, 0)} juta)", f"Kas + deposito minimum\n(batas USD {idn(cash_threshold, 0)} juta)"]
    rows = [(s, c) for s in scenarios for c in ("central", "adverse")]
    fig, ax = plt.subplots(figsize=(9.6, 4.9))
    n = {"Aman": 0, "Tipis": 0, "Tertembus": 0}
    for i, (s, c) in enumerate(rows):
        cells = [(cov[(s, c)], idn(cov[(s, c)], 2) + "x", _status(cov[(s, c)] / cov_threshold - 1, 0.10)),
                 (cs.loc[(s, c), "min_cash"], idn(cs.loc[(s, c), "min_cash"], 0), _status(cs.loc[(s, c), "min_cash"] / cash_threshold - 1, 0.5)),
                 (cs.loc[(s, c), "min_liquidity"], idn(cs.loc[(s, c), "min_liquidity"], 0), _status(cs.loc[(s, c), "min_liquidity"] / cash_threshold - 1, 0.5))]
        for j, (_, txt, st) in enumerate(cells):
            face, ink, sym = STATUS[st]
            n[st] += 1
            ax.add_patch(plt.Rectangle((j, len(rows) - 1 - i), 0.96, 0.92, facecolor=face, edgecolor=SURFACE, linewidth=2))
            ax.text(j + 0.48, len(rows) - 1 - i + 0.5, f"{txt}\n{sym} {st}", ha="center", va="center", fontsize=9.2, color=ink, fontweight="bold")
    ax.set_xlim(0, 3); ax.set_ylim(0, len(rows)); ax.axis("off")
    for j, lb in enumerate(cols):
        ax.text(j + 0.48, len(rows) + 0.12, lb, ha="center", va="bottom", fontsize=8.8, color=INK2)
    for i, (s, c) in enumerate(rows):
        ax.text(-0.04, len(rows) - 1 - i + 0.5, f"{s}\n{'parameter tengah' if c == 'central' else 'parameter merugikan'}", ha="right", va="center", fontsize=8.8, color=INK)
    cov_hit = any(_status(cov[(s, c)] / cov_threshold - 1, 0.10) == "Tertembus" for s, c in rows)
    liq_hit = [c for s, c in rows if _status(cs.loc[(s, c), "min_liquidity"] / cash_threshold - 1, 0.5) == "Tertembus"]
    head = "Covenant tidak tertembus pada skenario makro mana pun" if not cov_hit else "Covenant tertembus pada sebagian skenario"
    tail = ("kas + deposito hanya tertembus pada parameter merugikan" if liq_hit and set(liq_hit) == {"adverse"}
            else ("kas + deposito tidak tertembus" if not liq_hit else "kas + deposito tertembus pada sebagian skenario"))
    fig.suptitle(f"{head};\n{tail}, dan kas saja lebih rentan", x=0.01, ha="left", fontsize=11, fontweight="bold")
    fig.text(0.01, 0.01, "Aman: ruang di atas 10% (cover) atau 50% (kas) dari batas; Tipis: di atas batas tetapi di bawah ruang itu. Pita adalah usulan. Pro forma dari posisi 30 Sep 2026; bukan proyeksi.", fontsize=7.6, color=INK2)
    fig.tight_layout(rect=(0.12, 0.04, 1, 0.9))
    return fig


# --- mitigasi ----------------------------------------------------------------------------------------------------

def mitigation_levers(v):
    """Perbaikan likuiditas minimum (kas + deposito) menurut tuas, pada kasus merugikan, dua skenario."""
    import numpy as np
    t = v.impact.pivot(index="tuas", columns="scenario", values="min_liquidity")
    gain = t.sub(t.loc["Tanpa tindakan"], axis=1).drop("Tanpa tindakan")
    order = ["Tunda belanja modal 30%", "Hapus dividen", "Bank bergulir", "Ketiga tuas bersama"]
    gain = gain.loc[order]
    fig, ax = plt.subplots(figsize=(9.6, 3.9))
    y = np.arange(len(order)); h = 0.34
    for k, (sc, col) in enumerate((("Dasar", BIRU), ("Gabungan", ORANYE))):
        ax.barh(y + (k - 0.5) * h, gain[sc], height=h, color=col, label=sc, edgecolor=SURFACE, linewidth=1.5)
        for yy, val in zip(y + (k - 0.5) * h, gain[sc]):
            ax.text(val + 2, yy, idn(val, 0), va="center", fontsize=8.8, color=INK)
    ax.set_yticks(y); ax.set_yticklabels(order, fontsize=9); ax.invert_yaxis(); ax.grid(axis="y", visible=False)
    ax.set_xlim(0, gain.values.max() * 1.12); ax.legend(frameon=False, loc="upper right", fontsize=8.8, title="Skenario", title_fontsize=8.5)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda s, _: idn(s, 0)))
    best1 = gain.drop("Ketiga tuas bersama")["Dasar"].idxmax()
    fig.suptitle(f"Tiga tuas bersama menaikkan likuiditas minimum USD {idn(gain.loc['Ketiga tuas bersama', 'Dasar'], 0)} juta;\n{best1.lower()} paling besar bila berdiri sendiri", x=0.01, ha="left", fontsize=11, fontweight="bold")
    fig.text(0.01, 0.01, "Kenaikan saldo minimum kas + deposito 2026-2031 (USD juta), parameter merugikan; tuas aktif setelah pemicu ditambah waktu tunggu. Perhitungan penulis.", fontsize=7.8, color=INK2)
    fig.tight_layout(rect=(0, 0.045, 1, 0.9))
    return fig


def mitigation_paths(v, scenario="Dasar"):
    """Saldo kas + deposito dengan dan tanpa ketiga tuas, pada kasus merugikan, dengan pemicu dan awal berlaku tuas."""
    import numpy as np
    a, b = v.paths[(scenario, "tanpa")], v.paths[(scenario, "dengan")]
    x = np.arange(len(a))
    fig, ax = plt.subplots(figsize=(9.6, 4.5))
    ax.plot(x, a["liquidity"], color=ORANYE, lw=2.2, label="Kas + deposito, tanpa tindakan")
    ax.plot(x, b["liquidity"], color=BIRU, lw=2.2, label="Kas + deposito, dengan tiga tuas")
    ax.plot(x, a["closing"], color=ORANYE, lw=1.3, ls=(0, (4, 3)), label="Kas saja, tanpa tindakan")
    ax.plot(x, b["closing"], color=BIRU, lw=1.3, ls=(0, (4, 3)), label="Kas saja, dengan tiga tuas")
    ax.axhline(v.threshold, color=INK, lw=1.0, ls=(0, (1, 2))); ax.axhline(0, color=INK2, lw=0.8)
    ax.text(0, v.threshold + 8, f"batas kas usulan USD {idn(v.threshold, 0)} juta", ha="left", fontsize=8.3, color=INK2)
    st = b.attrs["start"]; tm = b.attrs["trigger_month"]
    months = list(a.index)
    for m, lb in ((tm, "pemicu"), (st["bank"], "bank bergulir\nberlaku")):
        if m:
            i = months.index(m); ax.axvline(i, color=GRID, lw=1.0, zorder=0)
            ax.text(i, ax.get_ylim()[1] * 0.97, lb, ha="center", va="top", fontsize=7.8, color=INK2)
    ticks = [i for i, m in enumerate(months) if m[5:] == "01"]
    ax.set_xticks(ticks); ax.set_xticklabels([months[i][:4] for i in ticks]); ax.grid(axis="x", visible=False); ax.set_xlim(-1, len(a) + 0.5)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda t, _: idn(t, 0)))
    ax.legend(frameon=False, loc="lower left", fontsize=8.3, ncol=2)
    fig.suptitle(f"Dengan tiga tuas, kas + deposito minimum USD {idn(b['liquidity'].min(), 0)} juta dan tetap di atas batas;\n"
                 f"tanpa tindakan, saldo itu turun hingga {'negatif ' if a['liquidity'].min() < 0 else ''}USD {idn(abs(a['liquidity'].min()), 0)} juta", x=0.01, ha="left", fontsize=10.5, fontweight="bold")
    fig.text(0.01, 0.01, f"USD juta, akhir bulan, skenario {scenario.lower()} dengan parameter merugikan. Pemicu: kas di bawah dua bulan biaya operasi tunai. Bukan proyeksi.", fontsize=7.8, color=INK2)
    fig.tight_layout(rect=(0, 0.045, 1, 0.9))
    return fig


# --- siklus dan replay -------------------------------------------------------------------------------------------

def cycle_history(v):
    """EBITDA tahunan SMDR terhadap titik impas covenant (EBITDA yang dibutuhkan uji tiap tahun buku, kewajiban saat ini)."""
    import numpy as np
    h = v.hist["ebitda"]
    x = np.arange(len(h))
    fig, ax = plt.subplots(figsize=(9.6, 4.7))
    cols = [BIRU] * (len(h) - 1) + [INK2]
    ax.bar(x, h.values, color=cols, width=0.58, edgecolor=SURFACE, linewidth=1.5)
    for xi, val in zip(x, h.values):
        ax.text(xi, val + 7, idn(val, 0), ha="center", fontsize=9, color=INK)
    styles = {"FY2027": ((0, (5, 3)), 1.3, "top"), "FY2028": ((0, (1, 1.6)), 2.0, "bottom")}
    for f, (ls, lw, va) in styles.items():
        be = v.den.loc[f, "titik_impas"]
        ax.axhline(be, color=ORANYE, lw=lw, ls=ls)
        ax.text(len(h) - 0.6, be + (-4 if va == "top" else 4), f"impas uji {f}: {idn(be, 0)}", ha="left", va=va, fontsize=8.4, color=INK2)
    ax.set_xticks(x); ax.set_xticklabels(list(h.index), fontsize=9); ax.grid(axis="x", visible=False)
    ax.set_xlim(-0.6, len(h) + 1.0); ax.set_ylim(0, h.max() * 1.12); ax.yaxis.set_major_formatter(FuncFormatter(lambda t, _: idn(t, 0)))
    fig.suptitle(f"Dihadapkan pada kewajiban saat ini, EBITDA {v.below['FY2027']} dari 5 tahun buku sejarah berada di bawah titik impas uji FY2027 "
                 f"dan {v.below['FY2028']} dari 5 di bawah uji FY2028", x=0.01, ha="left", fontsize=10.5, fontweight="bold", wrap=True)
    fig.text(0.01, 0.01, "USD juta; EBITDA = laba operasi + penyusutan biaya jasa. Garis = 1,10 x penyebut pro forma atas kewajiban saat ini, bukan kewajiban tahun itu.", fontsize=7.6, color=INK2)
    fig.tight_layout(rect=(0, 0.045, 1, 0.9))
    return fig


def replay_grid(v):
    """Replay tingkat EBITDA sejarah selama 12, 24, atau 36 bulan: cover covenant terendah (FY2027-FY2030) dan kas + deposito minimum."""
    g = v.grid[v.grid.case == "central"]
    lv = list(v.levels)
    durs = sorted(g["months"].unique())
    th = v.threshold
    fig, axes = plt.subplots(1, 2, figsize=(10.4, 4.3))
    count = {"Tertembus": 0}
    for ax, kind in zip(axes, ("cover", "liq")):
        for i, lb in enumerate(lv):
            for j, m in enumerate(durs):
                r = g[(g.level == lb) & (g.months == m)].iloc[0]
                if kind == "cover":
                    val, txt, st = r["cover_min"], idn(r["cover_min"], 2) + "x", _status(r["cover_min"] / 1.10 - 1, 0.10)
                else:
                    val, txt, st = r["min_liquidity"], idn(r["min_liquidity"], 0), _status(r["min_liquidity"] / th - 1, 0.5)
                face, ink, sym = STATUS[st]
                ax.add_patch(plt.Rectangle((j, len(lv) - 1 - i), 0.96, 0.92, facecolor=face, edgecolor=SURFACE, linewidth=2))
                ax.text(j + 0.48, len(lv) - 1 - i + 0.5, f"{txt}\n{sym} {st}", ha="center", va="center", fontsize=8.8, color=ink, fontweight="bold")
        ax.set_xlim(0, len(durs)); ax.set_ylim(0, len(lv)); ax.axis("off")
        for j, m in enumerate(durs):
            ax.text(j + 0.48, len(lv) + 0.08, f"{m} bulan", ha="center", va="bottom", fontsize=8.8, color=INK2)
        ax.set_title("Cover covenant terendah (FY2027-FY2030)" if kind == "cover" else f"Kas + deposito minimum (batas USD {idn(th, 0)} juta)", fontsize=9.6, pad=22)
    for i, lb in enumerate(lv):
        e = v.levels[lb]
        axes[0].text(-0.04, len(lv) - 1 - i + 0.5, f"{lb}\nEBITDA {idn(e, 0)}", ha="right", va="center", fontsize=8.6, color=INK)
    c = g[g.months == 24].set_index("level").loc[lv]
    first_cov = next((lb for lb in lv if _status(c.loc[lb, "cover_min"] / 1.10 - 1, 0.10) == "Tertembus"), None)
    first_liq = next((lb for lb in lv if _status(c.loc[lb, "min_liquidity"] / th - 1, 0.5) == "Tertembus"), None)
    fig.suptitle(f"Pada penurunan 24 bulan, covenant tertembus mulai tingkat {first_cov or 'tidak ada'};\n"
                 f"kas + deposito baru mulai tingkat {first_liq or 'tidak ada'}", x=0.01, ha="left", fontsize=10.5, fontweight="bold")
    fig.text(0.01, 0.01, "Replay tingkat EBITDA sejarah sejak Okt 2026, pulih ke TTM setelahnya; parameter tengah, tanpa guncangan makro, tanpa refinancing atau mitigasi. Pro forma, bukan proyeksi.", fontsize=7.6, color=INK2)
    fig.tight_layout(rect=(0.14, 0.04, 1, 0.88))
    return fig


# --- jembatan industri -------------------------------------------------------------------------------------------

def transmission_chain():
    """Rantai makro -> industri pelayaran -> SMDR: biru = dihitung dalam riset, abu = kualitatif (tidak dikuantifikasi)."""
    from matplotlib.patches import FancyBboxPatch
    fig, ax = plt.subplots(figsize=(10.2, 4.1))
    ax.set_xlim(0, 10.2); ax.set_ylim(0, 4.1); ax.axis("off")

    def box(x, y, w, h, text, calc):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.12", facecolor=BIRU if calc else "#e6e5e1",
                                    edgecolor=BIRU if calc else INK2, linewidth=1.2))
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=8.8, color="#ffffff" if calc else INK, fontweight="bold" if calc else "normal")

    def arrow(x0, y0, x1, y1):
        ax.annotate("", xy=(x1, y1), xytext=(x0, y0), arrowprops=dict(arrowstyle="-|>", color=INK2, lw=1.3))

    y = 1.75
    box(0.15, y, 1.75, 0.9, "Ekonomi dunia\ndan perdagangan", False)
    box(2.35, y, 1.75, 0.9, "Permintaan angkut\n(ton-mil)", False)
    box(4.55, y, 1.75, 0.9, "Tarif dan volume\nSMDR", True)
    box(6.75, y, 1.5, 0.9, "EBITDA", True)
    box(8.55, y, 1.5, 0.9, "Covenant\ndan kas", True)
    box(2.35, 0.35, 1.75, 0.9, "Kapasitas armada\ndan pesanan kapal", False)
    box(6.75, 3.0, 1.5, 0.9, "Energi, kurs,\nbunga", True)
    arrow(1.9, y + 0.45, 2.35, y + 0.45); arrow(4.1, y + 0.45, 4.55, y + 0.45); arrow(6.3, y + 0.45, 6.75, y + 0.45); arrow(8.25, y + 0.45, 8.55, y + 0.45)
    arrow(4.1, 0.8, 5.2, y); arrow(7.5, 3.0, 7.5, y + 0.9)
    ax.text(5.35, 0.75, "Empat kisah pasar menerjemahkan rantai ini\nmenjadi tarif, volume, dan lama, dikalibrasi\npada hasil yang pernah tercatat.", fontsize=8.2, color=INK2, va="center")
    ax.text(8.35, 3.45, "skenario makro:\nbiaya dan bunga", fontsize=8.2, color=INK2, va="center")
    ax.text(0.15, 3.85, "Biru = dihitung dalam riset. Abu = kualitatif; hubungan makro ke tarif tidak dapat dikuantifikasi dengan andal.", fontsize=8.2, color=INK2, va="top")
    fig.suptitle("Makro memengaruhi SMDR lewat dua jalur: biaya (energi, kurs, bunga)\ndan, jauh lebih besar, tarif dan volume pelayaran", x=0.01, ha="left", fontsize=10.5, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.9))
    return fig


def observed_vs_headroom(v):
    """Perubahan tarif tercatat terhadap ruang covenant (titik impas tarif uji FY2028 dan FY2027)."""
    rep = v.reported[v.reported["jenis"] == "tarif"]
    lab = {("FY2023", "international"): "Rute internasional FY2023", ("FY2023", "jakarta_hub"): "Hub Jakarta FY2023", ("FY2023", "surabaya_hub"): "Hub Surabaya FY2023",
           ("FY2024", "jakarta_hub"): "Hub Jakarta FY2024", ("FY2024", "surabaya_hub"): "Hub Surabaya FY2024", ("FY2025", "global_container"): "Kontainer global FY2025 (indeks pasar)"}
    items = [(lab[(r.periode, r.cakupan)], r.perubahan, INK2 if r.cakupan == "global_container" else BIRU) for r in rep.itertuples() if (r.periode, r.cakupan) in lab]
    for p, r in v.realized.iterrows():
        items.append((f"Tarif efektif pendapatan angkutan {p}", r["tarif_efektif"] * 100, ORANYE))
    items.sort(key=lambda t: t[1])
    fig, ax = plt.subplots(figsize=(9.8, 4.9))
    lo, hi = v.den.loc["FY2027", "titik_impas_tarif"] * 100, v.den.loc["FY2028", "titik_impas_tarif"] * 100
    ax.axvspan(lo, hi, color=GRID, zorder=0)
    ax.text((lo + hi) / 2, len(items) - 0.35, "ruang\ncovenant", ha="center", va="top", fontsize=8, color=INK2)
    for i, (lb, val, col) in enumerate(items):
        ax.barh(i, val, color=col, height=0.58, edgecolor=SURFACE, linewidth=1.3)
        ax.text(val + (1.0 if val >= 0 else -1.0), i, idn(val, 0) + "%", va="center", ha="left" if val >= 0 else "right", fontsize=8.8, color=INK)
    ax.axvline(0, color=INK2, lw=0.8)
    ax.set_yticks(range(len(items))); ax.set_yticklabels([t[0] for t in items], fontsize=8.5); ax.grid(axis="y", visible=False)
    ax.set_xlim(-58, 22); ax.xaxis.set_major_formatter(FuncFormatter(lambda s, _: idn(s, 0) + "%"))
    n_down = sum(1 for t in items if t[1] <= hi)
    fig.suptitle(f"Tarif yang tercatat turun hingga {idn(abs(items[0][1]), 0)}% per tahun pada tahun koreksi;\n{n_down} dari {len(items)} catatan melampaui ruang covenant ({idn(abs(hi), 0)}% sampai {idn(abs(lo), 0)}%)", x=0.01, ha="left", fontsize=10.5, fontweight="bold")
    fig.text(0.01, 0.01, "Biru = dilaporkan perusahaan; oranye = diturunkan dari pendapatan angkutan terealisasi dan volume; abu = indeks pasar global. Tarif efektif FY2023 turun dari puncak.", fontsize=7.6, color=INK2)
    fig.tight_layout(rect=(0, 0.04, 1, 0.9))
    return fig


def stress_map(rows, cov_threshold, cash_threshold, group_break=None):
    """Peta hasil: baris = skenario/kisah. `rows` = list dict(label, sub, cover, cover_year, cash, liq). Warna menurut ruang terhadap batas, selalu dengan kata dan simbol."""
    fig, ax = plt.subplots(figsize=(10.2, 0.62 * len(rows) + 1.6))
    cols = ["Cover covenant terendah\nFY2027-FY2029 (batas 1,10x)", f"Kas minimum 2026-2031\n(batas USD {idn(cash_threshold, 0)} juta)", f"Kas + deposito minimum\n(batas USD {idn(cash_threshold, 0)} juta)"]
    n = len(rows)
    out = []
    for i, r in enumerate(rows):
        y = n - 1 - i
        cells = [(idn(r["cover"], 2) + "x\n" + r["cover_year"], _status(r["cover"] / cov_threshold - 1, 0.10)),
                 (idn(r["cash"], 0), _status(r["cash"] / cash_threshold - 1, 0.5)), (idn(r["liq"], 0), _status(r["liq"] / cash_threshold - 1, 0.5))]
        out.append([c[1] for c in cells])
        for j, (txt, st) in enumerate(cells):
            face, ink, sym = STATUS[st]
            ax.add_patch(plt.Rectangle((j, y), 0.96, 0.9, facecolor=face, edgecolor=SURFACE, linewidth=2))
            ax.text(j + 0.48, y + 0.45, f"{txt}\n{sym} {st}" if j else f"{txt}\n{sym} {st}", ha="center", va="center", fontsize=8.2, color=ink, fontweight="bold")
        ax.text(-0.04, y + 0.45, f"{r['label']}\n{r['sub']}", ha="right", va="center", fontsize=8.4, color=INK)
    if group_break is not None:
        ax.plot([-1.7, 3], [n - group_break] * 2, color=INK2, lw=0.9)
    ax.set_xlim(0, 3); ax.set_ylim(0, n); ax.axis("off")
    for j, lb in enumerate(cols):
        ax.text(j + 0.48, n + 0.1, lb, ha="center", va="bottom", fontsize=8.4, color=INK2)
    fig.tight_layout(rect=(0.2, 0.03, 1, 0.9))
    return fig, out


def industry_heatmap(bv, case="central"):
    """Peta hasil: tiga skenario makro (biaya) dan empat kisah pasar, satu kasus parameter."""
    names = {"central": "parameter tengah", "adverse": "parameter merugikan"}
    rows = []
    for r in bv.macro_rows[bv.macro_rows.case == case].itertuples():
        rows.append({"label": r.kisah, "sub": "skenario makro", "cover": r.cover_min, "cover_year": r.cover_min_year, "cash": r.min_cash, "liq": r.min_liquidity})
    for r in bv.results[bv.results.case == case].itertuples():
        rows.append({"label": r.kisah, "sub": "kisah pasar", "cover": r.cover_min, "cover_year": r.cover_min_year, "cash": r.min_cash, "liq": r.min_liquidity})
    fig, st = stress_map(rows, tr_threshold(), bv.threshold, group_break=3)
    macro_hit = sum(s[0] == "Tertembus" for s in st[:3]); narr_hit = sum(s[0] == "Tertembus" for s in st[3:])
    liq_hit = [rows[i + 3]["label"] for i, s in enumerate(st[3:]) if s[2] == "Tertembus"]
    head = "Skenario makro tidak menembus covenant" if macro_hit == 0 else f"{macro_hit} skenario makro menembus covenant"
    mid = f"{narr_hit} dari {len(st) - 3} kisah pasar menembusnya"
    macro_liq = sum(x[2] == "Tertembus" for x in st[:3])
    if macro_liq == 3 and len(liq_hit) == len(st) - 3:
        tail = "kas + deposito sudah tertembus pada semua baris, termasuk skenario makro"
    else:
        tail = (f"kas + deposito tertembus pada {len(liq_hit)} kisah" if liq_hit else "kas + deposito tidak tertembus pada kisah mana pun")
    fig.suptitle(f"{head}; {mid};\n{tail} ({names[case]})", x=0.01, ha="left", fontsize=10.5, fontweight="bold")
    fig.text(0.01, 0.01, "Aman: ruang di atas 10% (cover) atau 50% (kas) dari batas; Tipis: di atas batas tetapi di bawah ruang itu. Pita adalah usulan. Pro forma dari posisi 30 Sep 2026; bukan proyeksi.", fontsize=7.4, color=INK2)
    return fig


def tr_threshold():
    return 1.10


# --- radar risiko yang sedang muncul -----------------------------------------------------------------------------

def emerging_radar(r):
    """Radar tanpa probabilitas: batang = jendela waktu risiko mulai terasa; biru = dampak sudah terukur, abu = belum terukur."""
    import textwrap
    d = r.sort_values(["horizon_min", "horizon_max"]).reset_index(drop=True)
    n = len(d)
    fig, ax = plt.subplots(figsize=(10.4, 0.55 * n + 1.7))
    for i, x in d.iterrows():
        y = n - 1 - i
        meas = x["d_central"] == x["d_central"] and x["d_central"] is not None
        ax.barh(y, x["horizon_max"] - x["horizon_min"], left=x["horizon_min"], height=0.52, color=BIRU if meas else "#d9d8d2", edgecolor=BIRU if meas else INK2, linewidth=1.0)
        if meas:
            lab = f"selisih EBITDA {idn(x['d_central'], 0)}" + (f" sampai {idn(x['d_adverse'], 0)}" if abs(x["d_central"] - x["d_adverse"]) >= 0.5 else "") + " juta/tahun"
        else:
            lab = "belum terukur: butuh data"
        ax.text(124, y, lab, va="center", ha="left", fontsize=8.2, color=INK if meas else INK2)
    ax.set_yticks(range(n)); ax.set_yticklabels(["\n".join(textwrap.wrap(t, 34)) for t in d["risiko"][::-1]], fontsize=8.3)
    ax.set_xlim(0, 215); ax.set_xticks([0, 12, 24, 36, 60, 120]); ax.set_xlabel("Bulan sejak Okt 2026 sampai risiko terasa"); ax.grid(axis="y", visible=False)
    ax.spines["bottom"].set_bounds(0, 120)
    m = int(sum(1 for v in d["d_central"] if v == v and v is not None))
    fig.suptitle(f"{m} dari {n} risiko yang sedang muncul sudah terukur pada riset ini;\n{n - m} lainnya belum terukur dan membutuhkan data", x=0.01, ha="left", fontsize=10.5, fontweight="bold")
    fig.text(0.01, 0.01, "Tanpa probabilitas. Selisih EBITDA terhadap TTM dari skenario makro atau kisah pasar (parameter tengah sampai merugikan). Sumber sinyal pada tabel bukti.", fontsize=7.6, color=INK2)
    fig.tight_layout(rect=(0, 0.04, 1, 0.9))
    return fig
