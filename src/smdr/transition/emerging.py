"""Radar risiko yang sedang muncul: sinyal bersumber, saluran ke SMDR, horizon, kecepatan, indikator dini, dan status uji.

Radar tidak memuat probabilitas. Sumbu yang dipakai adalah kapan risiko terasa (horizon) dan apakah dampaknya sudah terukur pada riset ini
(selisih EBITDA dari skenario makro atau kisah pasar). Sinyal berasal dari berkas lokal (kutipan diverifikasi terhadap halaman PDF), data operasional,
atau sumber web berlabel dengan tanggal dan tautan.
"""
import os
import re

import pandas as pd

from .. import baseline, datapaths
from . import bridge as br
from . import transmission as tr

ROOT = datapaths.ROOT
RISKS = datapaths.table("emerging_risks.csv")
SRC = datapaths.table("emerging_risk_evidence_src.csv")
EVIDENCE = datapaths.table("emerging_risk_evidence.csv")


def _page_text(path):
    import pypdf
    r = pypdf.PdfReader(path)
    return {i + 1: re.sub(r"\s+", " ", p.extract_text() or "") for i, p in enumerate(r.pages)}


def build_evidence():
    """Temukan halaman PDF setiap kutipan pada berkas lokal; gagal bila kutipan tidak ditemukan."""
    s = pd.read_csv(SRC).fillna("")
    cache, rows = {}, []
    for r in s.itertuples():
        page = ""
        if r.verifikasi == "berkas":
            path = os.path.join(ROOT, r.berkas)
            if path not in cache:
                cache[path] = _page_text(path)
            hit = [p for p, t in cache[path].items() if r.token in t and (r.halaman == "" or p == int(r.halaman))]
            if not hit:
                raise ValueError(f"kutipan tidak ditemukan: {r.risk_id} {r.berkas}")
            page = hit[0]
        rows.append({**r._asdict(), "pdf_page": page})
    df = pd.DataFrame(rows).drop(columns="Index")
    df.to_csv(EVIDENCE, index=False)
    return df


def evidence():
    return pd.read_csv(EVIDENCE).fillna("")


def verify(ev=None):
    """Butir bukti berkas yang kutipannya tidak ada pada halaman tercatat."""
    ev = evidence() if ev is None else ev
    cache, bad = {}, []
    for r in ev[ev.verifikasi == "berkas"].itertuples():
        path = os.path.join(ROOT, r.berkas)
        if path not in cache:
            cache[path] = _page_text(path)
        if r.token not in cache[path].get(int(r.pdf_page), ""):
            bad.append((r.risk_id, r.berkas))
    return bad


def risks():
    return pd.read_csv(RISKS).fillna("")


def measured(tv, bv):
    """Selisih EBITDA per tahun (USD juta; tengah dan merugikan) menurut tautan: skenario makro atau kisah pasar."""
    out = {}
    sc = tv.scenarios.set_index(["scenario", "case"])["d_ebitda"]
    nr = bv.results.set_index(["kisah", "case"])["d_ebitda"]
    for r in risks().itertuples():
        if not r.tautan:
            out[r.risk_id] = (None, None)
            continue
        kind, name = r.tautan.split(":", 1)
        src = sc if kind == "macro" else nr
        out[r.risk_id] = (float(src[(name, "central")]), float(src[(name, "adverse")]))
    return out


def build_view(tv=None, bv=None):
    tv = tv or tr.build_view()
    bv = bv or br.build_view()
    m = measured(tv, bv)
    r = risks().copy()
    r["d_central"] = r["risk_id"].map(lambda k: m[k][0])
    r["d_adverse"] = r["risk_id"].map(lambda k: m[k][1])
    return r, evidence()


def radar_table(r):
    t = r.copy()
    t["Horizon (bulan)"] = t.apply(lambda x: f"{x['horizon_min']}-{x['horizon_max']}", axis=1)
    t["Dampak terukur (selisih EBITDA, USD juta per tahun)"] = t.apply(
        lambda x: "belum terukur" if pd.isna(x["d_central"]) else (f"{x['d_central']:.0f}" if abs(x["d_central"] - x["d_adverse"]) < 0.5 else f"{x['d_central']:.0f} sampai {x['d_adverse']:.0f}"), axis=1)
    t = t.rename(columns={"risiko": "Risiko", "kelompok": "Kelompok", "saluran": "Saluran ke SMDR", "kecepatan": "Kecepatan", "indikator_dini": "Indikator dini", "status_uji": "Status uji"})
    return t.set_index("Risiko")[["Kelompok", "Saluran ke SMDR", "Horizon (bulan)", "Kecepatan", "Dampak terukur (selisih EBITDA, USD juta per tahun)", "Indikator dini", "Status uji"]]


def sinyal_table(ev, r):
    names = r.set_index("risk_id")["risiko"]
    t = ev.copy()
    t["Risiko"] = t["risk_id"].map(names)
    t["Verifikasi"] = t["verifikasi"].map({"berkas": "kutipan diverifikasi pada dokumen", "web_resmi": "situs resmi, diakses 6 Nov 2026", "web_media": "media dengan atribusi, diakses 6 Nov 2026", "data": "data operasional riset"})
    t = t.rename(columns={"sinyal": "Sinyal", "sumber": "Sumber", "tanggal": "Tanggal"})
    t["Tautan"] = t["url"]
    return t.set_index("Risiko")[["Sinyal", "Sumber", "Tanggal", "Verifikasi", "Tautan"]]
