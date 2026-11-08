"""Tema deck: palet Samudera, huruf, ukuran slide, dan komponen bersama (judul panel, legend, sumber/catatan).

Satu warna selalu bermakna sama di seluruh slide:
  merah  = batas covenant / pelanggaran      kuning = sorotan pesan utama (skenario fokus, parameter operasi)
  abu    = konteks, dasar, belum terukur     hitam  = teks dan satu seri terberat (skenario paling dalam)
"""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle

INK, KUNING, MERAH, ABU = "#0D0403", "#FDB913", "#ED1C24", "#BCBEC0"
ABU_D, ABU_L, GRID, MERAH_T = "#6D6E71", "#ECEDEE", "#EFEFF0", "#F6A5A7"
W, H = 13.333, 7.5
MARGIN = 0.5

plt.rcParams["font.family"] = ["Arial", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = True
SERIF = ["Times New Roman", "DejaVu Serif"]


def idn(x, d=1, signed=False):
    s = f"{abs(x):,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    if x < 0:
        return "−" + s
    return ("+" + s) if signed and x > 0 else s


def new_slide():
    fig = plt.figure(figsize=(W, H), dpi=110)
    fig.patch.set_facecolor("white")
    bg = fig.add_axes([0, 0, 1, 1])
    bg.set_xlim(0, W); bg.set_ylim(H, 0); bg.axis("off")
    return fig, bg


def ax_in(fig, x, y, w, h, **kw):
    """Axes pada koordinat inci slide (x, y dari kiri-atas)."""
    return fig.add_axes([x / W, 1 - (y + h) / H, w / W, h / H], **kw)


def txt(bg, x, y, s, size=9, color=INK, weight="normal", ha="left", va="center", style="normal", **kw):
    if not kw.pop("nofloor", False):
        size = max(size, 8.2)
    return bg.text(x, y, s, fontsize=size, color=color, fontweight=weight, ha=ha, va=va, fontstyle=style, **kw)


def hline(bg, x0, x1, y, color=ABU, lw=0.8):
    bg.plot([x0, x1], [y, y], color=color, lw=lw, solid_capstyle="butt")


def section(bg, name):
    txt(bg, MARGIN, 0.36, " ".join(name.upper()), 8.5, INK, "bold")
    bg.add_patch(Rectangle((MARGIN, 0.52), 0.55, 0.045, fc=KUNING, ec="none"))


def _wrap_measured(bg, s, maxw, size=22):
    """Pecah kalimat menjadi baris yang mengisi lebar maksimum (inci) berdasarkan lebar teks terukur, bukan jumlah karakter."""
    fig = bg.figure
    r = fig.canvas.get_renderer()
    width = lambda t: bg.text(0, 0, t, fontsize=size, fontfamily=SERIF).get_window_extent(r).width / fig.dpi
    lines, cur = [], ""
    for wd in s.split(" "):   # spasi tak-terputus (\u00a0) mengunci frasa agar tidak dipenggal
        cand = (cur + " " + wd).strip()
        wv = width(cand); bg.texts[-1].remove()
        if wv <= maxw or not cur:
            cur = cand
        else:
            lines.append(cur); cur = wd
    lines.append(cur)
    return lines


def title(bg, lines):
    """Judul aksi: list baris (manual) atau satu kalimat yang diisi penuh per baris (lebar 12,33 inci)."""
    if isinstance(lines, str):
        lines = _wrap_measured(bg, lines, W - 2 * MARGIN - 0.05)
    for i, s in enumerate(lines):
        txt(bg, MARGIN, 0.98 + i * 0.39, s, 22, INK, "normal", fontfamily=SERIF)


def panel_title(bg, x, w, y, s, lines=1, size=11):
    """Judul panel; lines=2 membungkus teks dan menurunkan garis agar sejajar antarpanel."""
    import textwrap
    chars = max(8, int(w / (0.0078 * size)))
    parts = s.split("\n") if "\n" in s else (textwrap.wrap(s, chars) if lines > 1 else [s])   # \n = pemisah baris eksplisit
    for i, p in enumerate(parts[:lines]):
        txt(bg, x, y + i * 0.2, p, size + 1, INK, "bold", fontfamily=SERIF)
    hline(bg, x, x + w, y + 0.24 + 0.2 * (lines - 1))
    return len(parts[:lines])


def legend(bg, x, y, items, size=8, gap=0.3, fig=None):
    """Strip legend dengan lebar teks terukur: items = [(kind, color, label)], kind in {'line','dash','box','dot','ribbon'}; mengembalikan lebar total (inci)."""
    fig = fig or bg.figure
    size = max(size, 8)
    r = fig.canvas.get_renderer()
    cx = x
    for kind, color, label in items:
        if kind in ("line", "dash"):
            bg.plot([cx, cx + 0.3], [y, y], color=color, lw=2.6 if color != ABU_D else 2.0, ls="-" if kind == "line" else (0, (3, 2)), solid_capstyle="butt"); cx += 0.38
        elif kind == "box":
            bg.add_patch(Rectangle((cx, y - 0.065), 0.16, 0.13, fc=color, ec="none")); cx += 0.23
        elif kind == "ribbon":
            bg.add_patch(Rectangle((cx, y - 0.07), 0.3, 0.14, fc=color, ec="none")); cx += 0.38
        elif kind == "hbox":
            bg.add_patch(Rectangle((cx, y - 0.065), 0.16, 0.13, fc="white", ec=color, lw=1.0, ls=(0, (2, 1.5)))); cx += 0.23
        elif kind in ("diamond", "tri"):
            bg.plot([cx + 0.08], [y], marker="D" if kind == "diamond" else "v", ms=6.5, color=color, mec=INK, mew=0.6); cx += 0.22
        else:
            bg.plot([cx + 0.07], [y], marker="o", ms=6, color=color, mec=INK, mew=0.5); cx += 0.2
        t = txt(bg, cx, y, label, size, ABU_D)
        bb = t.get_window_extent(r)
        cx += bb.width / fig.dpi + gap
    return cx - x


def footer(bg, sumber, catatan, page):
    lines = catatan.split("\n")
    ys = {1: [6.98, 7.14], 2: [6.99, 7.12, 7.25], 3: [6.9, 7.03, 7.15, 7.27]}[len(lines)]
    txt(bg, MARGIN, ys[0], "Sumber: " + sumber, 7.2, ABU_D, nofloor=True)
    for k, ln in enumerate(lines):
        txt(bg, MARGIN, ys[1 + k], ("Catatan: " if k == 0 else "") + ln, 7.2, ABU_D, nofloor=True)
    from matplotlib.patches import FancyBboxPatch
    bg.add_patch(FancyBboxPatch((12.23, 6.98), 0.52, 0.22, boxstyle="round,pad=0,rounding_size=0.11", fc="none", ec=ABU_D, lw=0.8))
    txt(bg, 12.49, 7.09, str(page), 8, ABU_D, ha="center")


def implikasi(bg, s, y=6.3):
    """Kalimat kesimpulan slide: serif 16 pt, satu baris (maksimum sekitar 125 karakter)."""
    bg.add_patch(Rectangle((MARGIN, y), 0.07, 0.5, fc=KUNING, ec="none"))
    txt(bg, MARGIN + 0.22, y + 0.1, "IMPLIKASI", 9, ABU_D, "bold")
    txt(bg, MARGIN + 0.22, y + 0.34, s, 16, INK, fontfamily=SERIF)


def style_axes(ax, left=False, bottom=True):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.spines["left"].set_visible(left); ax.spines["bottom"].set_visible(bottom)
    ax.spines["left"].set_color(ABU); ax.spines["bottom"].set_color(ABU)
    ax.tick_params(length=0, labelsize=8.5, colors=ABU_D)
    ax.set_facecolor("none")
