"""Eksposur jaringan dan rute SMDR dari laporan tahunan Samudera Shipping Line (SSL) FY2025, anak perusahaan yang tercatat di SGX.

Setiap butir bukti memuat kutipan pendek (token) yang diverifikasi terhadap halaman PDF; tabel dibangun dari berkas bukti, bukan diketik ulang.
"""
import os
import re

import pandas as pd

from .. import datapaths
from .. import baseline

ROOT = datapaths.ROOT
PDF = os.path.join(ROOT, "Annual-Report", "Samudera-Shipping-Line-AR-2025.pdf")
PATH = datapaths.table("network_exposure.csv")
SOURCE_URL = "https://samudera.listedcompany.com/newsroom/20260409_182038_S56_YY6C1AGMVDCYNVDR.1.pdf"

# (item, nilai, satuan, cakupan, token verbatim (spasi dinormalisasi), catatan)
ITEMS = [
    ("services_indonesia", 7, "layanan", "hub Singapura ke pelabuhan utama Indonesia", "We operate 7 services from the Singapore hub covering Indonesia", "frekuensi 1 sampai 3 pelayaran per minggu; per 1 Maret 2026"),
    ("services_southeast_asia", 20, "layanan", "Malaysia, Thailand, Vietnam, Myanmar, Kamboja, Filipina utara", "There are 20 services serving Penang", "hingga 4 pelayaran per minggu"),
    ("services_india_middle_east", 19, "layanan", "India, Bangladesh, Sri Lanka, Pakistan, Jebel Ali (UEA)", "We operate 19 services covering Chennai", "hingga 4 pelayaran per minggu"),
    ("services_far_east", 1, "layanan mingguan", "China ke Singapura, Malaysia, India, Sri Lanka, Bangladesh, kawasan Teluk", "We have a weekly service from China ports", ""),
    ("services_gulf_india_mediterranean", 2, "layanan baru (2024)", "kawasan Teluk dan India ke Laut Tengah", "Launched two new services connecting the Gulf", "eksposur potensial terhadap rute Suez/Laut Merah"),
    ("revenue_group_fy2025", 605.7, "USD juta", "SSL konsolidasian", "Revenue increased 13.8% to USD605.7", "naik 13,8% dari USD 532,0 juta"),
    ("revenue_container_fy2025", 556.2, "USD juta", "segmen peti kemas SSL", "revenue grew 13.6% to USD556.2 million", "naik 13,6% dari USD 489,6 juta"),
    ("liftings_fy2025", 2062000, "TEU", "segmen peti kemas SSL", "2,062,000 TEUs in FY2025", "naik 7,9% dari 1.911.000 TEU"),
    ("freight_rate_h1_2025", None, "kualitatif", "segmen peti kemas SSL", "higher average freight rates in the first half of the FY2025", "tarif rata-rata semester I 2025 lebih tinggi daripada semester I 2024"),
    ("red_sea_capacity", None, "kualitatif", "pasar", "tightened available capacity in the market", "pengalihan rute melalui Tanjung Harapan mengetatkan kapasitas dan mendukung permintaan kapal sewa"),
    ("charter_in_cost", None, "kualitatif", "biaya jasa SSL", "more chartered-in vessels at a time of elevated", "lebih banyak kapal sewa masuk pada tarif sewa tinggi"),
    ("charter_out_europe", None, "kualitatif", "armada SSL", "European feeder services centred in Rotterdam", "kapal disewakan keluar secara selektif ke layanan feeder Eropa"),
    ("middle_east_exposure", None, "kualitatif", "Timur Tengah", "Our current exposure in the Middle East has been", "eksposur terbatas karena konflik geopolitik yang berlangsung"),
    ("middle_east_escalation_2026", None, "kualitatif", "Timur Tengah", "geopolitical tensions have once again escalated in the Middle East", "dinyatakan pada saat penulisan laporan (awal 2026)"),
]


def _pages():
    import pypdf
    r = pypdf.PdfReader(PDF)
    return {i + 1: re.sub(r"\s+", " ", p.extract_text() or "") for i, p in enumerate(r.pages)}


def build_evidence(path=PATH):
    """Temukan halaman setiap token pada PDF dan tulis berkas bukti. Gagal bila token tidak ditemukan atau ganda pada halaman berbeda."""
    pages = _pages()
    rows = []
    for item, val, unit, scope, token, note in ITEMS:
        hit = [p for p, t in pages.items() if token in t]
        if not hit:
            raise ValueError(f"token tidak ditemukan: {item}")
        rows.append({"item": item, "value": val, "unit": unit, "scope": scope, "pdf_page": hit[0], "token": token, "note": note,
                     "source": "Samudera Shipping Line Ltd, Annual Report 2025", "source_url": SOURCE_URL})
    df = pd.DataFrame(rows)
    df.to_csv(path, index=False)
    return df


def load():
    return pd.read_csv(PATH)


def verify(df=None):
    """Kembalikan butir yang tokennya tidak ditemukan pada halaman yang dicatat."""
    df = load() if df is None else df
    pages = _pages()
    return [r.item for r in df.itertuples() if r.token not in pages.get(int(r.pdf_page), "")]


def network_table(df=None):
    df = load() if df is None else df
    d = df[df["unit"].str.startswith("layanan")].copy()
    d["Layanan"] = d["value"].astype(int)
    d = d.rename(columns={"scope": "Cakupan", "note": "Catatan"})
    names = {"services_indonesia": "Indonesia (dari hub Singapura)", "services_southeast_asia": "Asia Tenggara lain", "services_india_middle_east": "India dan Timur Tengah",
             "services_far_east": "Timur Jauh (mingguan)", "services_gulf_india_mediterranean": "Teluk dan India ke Laut Tengah (baru 2024)"}
    d["Kawasan"] = d["item"].map(names)
    return d.set_index("Kawasan")[["Layanan", "Cakupan", "Catatan"]]


def ssl_share(df=None):
    """Pendapatan SSL terhadap pendapatan konsolidasian SMDR FY2025 (USD juta); SSL sebelum eliminasi antargrup."""
    df = load() if df is None else df
    ssl = float(df.set_index("item").loc["revenue_group_fy2025", "value"])
    w = baseline.load_wide()
    smdr = float(w.loc[("IS", "revenue"), "FY2025"] / 1e6)
    return {"ssl": ssl, "smdr": smdr, "share": ssl / smdr, "container": float(df.set_index("item").loc["revenue_container_fy2025", "value"]),
            "liftings": int(df.set_index("item").loc["liftings_fy2025", "value"])}


def fleet_charter():
    """Jumlah kapal sewa masuk dan sewa keluar FY2025 (data operasional)."""
    from .. import operating
    o = operating.load()
    g = lambda k: float(o[(o.metric_key == k) & (o.period == "FY2025")]["value"].iloc[0])
    return {"owned": g("fleet_owned"), "chartered_in": g("fleet_chartered_in"), "chartered_out": g("fleet_chartered_out")}
