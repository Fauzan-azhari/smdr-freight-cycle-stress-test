"""Registri data: sumber, lineage, kamus kolom, dan kontrak skema. Dibangun dari isi data/ dan peta di berkas ini.

Keluar (data/00_registry/): sources.csv, lineage.csv, dictionary.csv, schemas.csv
Pemeriksa: tests/test_data_architecture.py (isi folder = LAYOUT = lineage; hash mentah = sources; data memenuhi kontrak).

Jalankan dari root repo:  PYTHONPATH=src .venv/bin/python -m smdr.registry
"""
import hashlib
import os
import re

import pandas as pd

from . import datapaths as dp

LAYER_NAMES = {"00_registry": "registry", "01_raw": "raw", "02_curated": "curated", "03_canonical": "canonical", "04_marts": "marts"}

# ---------------------------------------------------------------- sumber (induk; rincian per berkas ada pada manifes masing-masing)
SOURCES = [
    # id, nama, penerbit, jenis, url, diakses, berkas mentah, redistribusi, manifes rincian, dipakai deck, catatan
    ("SRC-IDX", "Laporan keuangan konsolidasian SMDR FY2022-9M26 (tujuh berkas Excel IDX)", "PT Samudera Indonesia Tbk via Bursa Efek Indonesia", "pengungkapan emiten",
     "https://www.idx.co.id", "2026-10/11 (hash per berkas: fs_source_manifest.csv)", "idx_line_items.csv", "pengungkapan publik; yang dipublikasikan hanya ekstraksi nilai per butir, bukan berkas IDX",
     "fs_source_manifest.csv", "ya", "Ekstraksi teks per butir dari sheet 'Data Sumber'; alamat sel asli IDX tersimpan tiap baris"),
    ("SRC-FRED-BRENT", "Europe Brent Spot Price FOB (DCOILBRENTEU)", "U.S. Energy Information Administration via FRED, Federal Reserve Bank of St. Louis", "data terbuka",
     "https://fred.stlouisfed.org/series/DCOILBRENTEU", "2026-11 (lihat macro_source_manifest.csv)", "DCOILBRENTEU.csv;brent_daily_fred.csv", "terbuka dengan atribusi",
     "macro_source_manifest.csv", "ya", "Dua berkas: potongan 2021-2026 untuk basis skenario, dan riwayat 1987-2026 untuk uji keparahan"),
    ("SRC-FRED-FX", "Kurs USD/IDR bulanan (CCUSMA02IDM618N)", "OECD via FRED, Federal Reserve Bank of St. Louis", "data terbuka",
     "https://fred.stlouisfed.org/series/CCUSMA02IDM618N", "2026-11", "usdidr_monthly_fred.csv", "terbuka dengan atribusi", "", "ya", "Dipakai untuk uji keparahan kurs"),
    ("SRC-FX-PROV", "Kurs USD/IDR bulanan penutupan", "penyedia tidak tercatat pada berkas", "data pasar",
     "", "2026-11-03", "usdidr_monthly_provider.csv", "perlu verifikasi (penyedia tidak tercatat)", "macro_source_manifest.csv", "ya", "Dipakai untuk level kurs dasar skenario; angka format Indonesia pada sumber"),
    ("SRC-DREWRY", "Drewry World Container Index, komposit mingguan (USD per FEU)", "Drewry Shipping Consultants", "indeks pasar",
     "https://www.drewry.co.uk", "2026-11-05 (grafik publik; riwayat via paket akshare)", "wci_composite_weekly.csv", "perlu verifikasi; atribusi wajib: 'Source: Drewry World Container Index'",
     "", "ya", "Embed grafik berhenti 10 Sep 2026; pembacaan 5 Nov 2026 (4.389) dari halaman publik Drewry"),
    ("SRC-DOCS", "Dokumen perusahaan dan riset (Informasi Tambahan Sukuk, Annual Report, OCE Bank Mandiri, berita)", "SMDR, Bank Mandiri OCE, media", "dokumen publik",
     "", "2026-11-05/06", "", "dokumen asli tidak dipublikasikan; hanya manifes dan nilai yang diekstraksi", "source_manifest.csv", "ya",
     "Hash SHA-256 dan halaman rujukan tiap dokumen: source_manifest.csv; angka: operating_long.csv dan evidence.csv"),
]

# ---------------------------------------------------------------- produsen dan masukan tiap tabel
PRODUCERS = {
    "idx_line_items.csv": ("smdr.raw_export", "Financial-Statements/SMDR_Financial_Statements_2021_9M26.xlsx (sheet Data Sumber)"),
    "fs_long.csv": ("smdr.fs_ingest", "idx_line_items.csv"),
    "fs_line_dictionary.csv": ("smdr.fs_ingest", "fs_lines.py"),
    "fs_source_manifest.csv": ("smdr.fs_ingest", "Financial-Statements/Excel-FS/*.xlsx (SHA-256)"),
    "macro_daily.csv": ("smdr.macro_ingest", "DCOILBRENTEU.csv"),
    "macro_monthly.csv": ("smdr.macro_ingest", "DCOILBRENTEU.csv; usdidr_monthly_provider.csv"),
    "macro_monthly_wide.csv": ("smdr.macro_ingest", "macro_monthly.csv"),
    "macro_source_manifest.csv": ("smdr.macro_ingest", "DCOILBRENTEU.csv; usdidr_monthly_provider.csv (SHA-256)"),
    "financing_events.csv": ("smdr.transition.financing", "financing_facilities.csv"),
    "network_exposure.csv": ("smdr.transition.exposure", "source_manifest.csv (halaman Annual Report)"),
    "emerging_risk_evidence.csv": ("smdr.transition.emerging", "emerging_risk_evidence_src.csv; emerging_risks.csv"),
    "fs_checks.csv": ("smdr.fs_checks", "fs_long.csv; fs_line_dictionary.csv; fs_known_exceptions.csv"),
    "macro_checks.csv": ("smdr.macro_checks", "DCOILBRENTEU.csv; usdidr_monthly_provider.csv; macro_monthly.csv; macro_known_exceptions.csv"),
    "operating_checks.csv": ("smdr.operating", "operating_long.csv; fs_long.csv; evidence.csv; financing_facilities.csv"),
    "baseline_quarters.csv": ("smdr.baseline", "fs_long.csv; zero_fill_rules.csv; evidence.csv; decisions.csv; legacy_benchmark.csv"),
    "baseline_ttm.csv": ("smdr.baseline", "fs_long.csv; zero_fill_rules.csv; evidence.csv; decisions.csv; legacy_benchmark.csv"),
    "baseline_bridge.csv": ("smdr.baseline", "fs_long.csv; zero_fill_rules.csv; evidence.csv; decisions.csv; legacy_benchmark.csv"),
    "opening_balance_2026-09-30.csv": ("smdr.baseline", "fs_long.csv"),
}
_MODEL_INPUTS = ("cash_assumptions.csv; operating_assumptions.csv; macro_scenario_definitions.csv; macro_anchors.csv; financing_facilities.csv; capex_milestones.csv; "
                 "baseline_ttm.csv; fs_long.csv; macro_monthly_wide.csv; brent_daily_fred.csv; usdidr_monthly_fred.csv; wci_composite_weekly.csv")
for _n in ("scenario_results.csv", "cash_paths_monthly.csv", "covenant_quarterly.csv", "mitigation_tests.csv", "backtest.csv", "historical_test.csv", "cash_tornado.csv", "severity.csv"):
    PRODUCERS[_n] = ("smdr.marts", _MODEL_INPUTS)

RESULT_MARTS = {n for n, (m, _) in PRODUCERS.items() if m == "smdr.marts"}   # dihitung fungsi yang sama dengan deck (tidak dibaca deck)

# ---------------------------------------------------------------- deskripsi kolom tabel inti (kolom lain: statistik otomatis)
DESC = {
    "idx_line_items.csv": {"file_id": "ID berkas IDX (F01-F07, lihat fs_source_manifest.csv)", "file_period": "periode laporan pada berkas", "source_sheet": "nama sheet pada berkas IDX",
                           "source_cell": "alamat sel pada berkas IDX", "source_label": "uraian butir pada sumber", "source_context": "konteks atau komponen (label Inggris sumber)",
                           "source_value": "nilai persis seperti pada sumber, disimpan sebagai teks", "unit": "satuan nilai", "basis": "Berjalan atau Pembanding atau Metadata",
                           "period_start": "awal periode butir", "period_end": "akhir periode butir"},
    "fs_long.csv": {"statement": "laporan: IS laba rugi, BS posisi keuangan, CF arus kas, COGS_NOTE, EQ ekuitas, PPE aset tetap, DEBT_NOTE utang bank", "line_key": "kunci baris kanonik (fs_line_dictionary.csv)",
                    "line_label_id": "label baris berbahasa Indonesia", "period": "periode: FY2021-FY2025, 3M/6M/9M 2025 dan 2026", "basis": "fy tahunan, ytd kumulatif sejak 1 Januari, instant saldo pada tanggal",
                    "period_start": "awal periode (kosong untuk basis instant)", "period_end": "akhir periode", "value_usd": "nilai USD penuh; kosong bila status nd (n.d. bukan nol)",
                    "status": "reported dilaporkan, nd tidak diungkapkan pada sumber", "source_file_id": "berkas IDX asal", "source_sheet": "sheet asal", "source_cell": "sel asal", "workbook_cell": "sel pada workbook kurasi"},
    "macro_daily.csv": {"series": "seri harian (brent_usd_bbl)", "date": "tanggal", "value": "USD per barel; kosong bila libur (status nd)", "status": "reported atau nd",
                        "source_file": "berkas mentah asal", "source_line": "nomor baris pada berkas mentah"},
    "macro_monthly.csv": {"series": "usdidr_close, brent_avg (rata-rata bulanan), brent_eom (akhir bulan)", "month": "YYYY-MM", "value": "nilai seri", "n_obs": "jumlah observasi dalam bulan",
                          "last_obs_date": "observasi terakhir pada bulan itu", "partial": "True bila bulan belum lengkap", "source_file": "berkas mentah asal"},
    "macro_monthly_wide.csv": {"month": "YYYY-MM", "usdidr_close": "IDR per USD, penutupan bulan", "brent_avg": "USD per barel, rata-rata bulan", "brent_eom": "USD per barel, akhir bulan",
                               "partial_any": "True bila ada seri parsial pada bulan itu"},
    "financing_events.csv": {"event_id": "ID peristiwa", "facility_id": "fasilitas (S1B, S2, S3 = seri sukuk)", "event_type": "coupon atau principal", "contractual_date": "tanggal kontrak",
                             "payment_date": "tanggal bayar (hari kerja berikutnya)", "amount": "nilai dalam mata uang peristiwa", "currency": "IDR", "status": "scheduled",
                             "payment_date_basis": "dasar penyesuaian tanggal bayar"},
    "scenario_results.csv": {"skenario": "nama skenario", "kelompok": "Market atau Macro", "case": "central (asumsi tengah) atau adverse (downside case arus kas)",
                             "ebitda_FY2026": "EBITDA USD juta", "ebitda_FY2027": "EBITDA USD juta", "nd_FY2027": "Net Debt to EBITDA FY2027 (pembiayaan ulang bank bergulir)",
                             "nd_FY2027_amortisasi": "sama tanpa pembiayaan ulang", "cover_FY2027": "DSCR FY2027", "ebitda_FY2028": "EBITDA USD juta", "nd_FY2028": "Net Debt to EBITDA FY2028",
                             "cover_FY2028": "DSCR FY2028", "nd_FY2026": "Net Debt to EBITDA FY2026", "current_ratio_min": "Current Ratio terendah FY2027-FY2030",
                             "current_ratio_breach_fy": "tahun pertama Current Ratio di bawah 1,10x (kosong bila tidak ada)", "min_liquidity": "kas + deposito terendah, USD juta",
                             "nd_FY2028_amortisasi": "Net Debt to EBITDA FY2028 tanpa pembiayaan ulang bank", "min_liquidity_noref": "kas + deposito terendah tanpa pembiayaan ulang bank, USD juta",
                             "first_below": "bulan pertama kas + deposito di bawah batas minimum", "pelunasan_ke_2_7x": "pelunasan utang bank (USD juta) agar ND <= 2,70x"},
    "covenant_quarterly.csv": {"skenario": "nama skenario", "case": "central atau adverse", "quarter": "akhir kuartal YYYY-MM", "ebitda_ttm": "EBITDA 12 bulan, USD juta",
                               "nd": "Net Debt to EBITDA (bank + sukuk + sewa, tanpa dikurangi kas)", "dscr_bank": "DSCR basis dilaporkan", "dscr_with_sukuk": "DSCR dengan pokok sukuk per kuartal", "debt": "utang total, USD juta"},
    "cash_paths_monthly.csv": {"skenario": "nama skenario", "case": "central atau adverse", "month": "YYYY-MM", "closing": "kas akhir bulan, USD juta", "liquidity": "kas + deposito, USD juta",
                               "ebitda": "EBITDA bulanan, USD juta",
                               "ocf": "arus kas operasi", "interest_income": "pendapatan bunga", "sukuk_coupon": "imbal hasil sukuk", "other_interest": "bunga pinjaman lain", "lease": "pembayaran sewa",
                               "maintenance_capex": "belanja pemeliharaan", "program_capex": "belanja program kapal baru", "bank_repay": "angsuran utang bank", "short_bank_repay": "pelunasan pinjaman jangka pendek",
                               "dividend": "dividen", "sukuk_principal": "pokok sukuk jatuh tempo", "refi_draw": "pencairan pembiayaan ulang", "refi_service": "pelayanan pembiayaan ulang",
                               "bank_redraw": "penarikan ulang utang bank", "bank_balance": "saldo utang bank", "fx_translation": "selisih translasi kurs", "opening": "kas awal bulan",
                               "floor_intramonth": "kas terendah dalam bulan", "net_flow": "arus kas bersih", "reserve": "deposito entitas anak yang dapat ditarik", "fx": "kurs USD/IDR (IDR per USD)"},
    "backtest.csv": {"periode": "FY2023-FY2025", "tarif_efektif": "perubahan tarif efektif", "volume": "perubahan volume", "model": "perubahan EBITDA yang diprediksi model, USD juta",
                     "terealisasi": "perubahan EBITDA aktual, USD juta", "selisih_pct": "prediksi terhadap aktual, persen", "galat_pct": "galat prediksi, persen", "biaya_jasa_delta": "perubahan biaya jasa, USD juta"},
}

# ---------------------------------------------------------------- kontrak skema: kunci unik, kolom wajib, domain nilai
CONTRACTS = {
    "idx_line_items.csv": {"key": [], "required": ["file_id", "source_sheet", "source_cell", "source_value"], "enum": {"file_id": "F01|F02|F03|F04|F05|F06|F07"}},
    "fs_long.csv": {"key": ["statement", "line_key", "period", "basis"], "required": ["statement", "line_key", "period", "basis", "period_end", "status"],
                    "enum": {"statement": "BS|CF|COGS_NOTE|DEBT_NOTE|EQ|IS|PPE", "basis": "fy|instant|ytd", "status": "nd|reported"}, "null_iff": ("value_usd", "status", "nd")},
    "macro_daily.csv": {"key": ["series", "date"], "required": ["series", "date", "status"], "enum": {"status": "nd|reported"}, "null_iff": ("value", "status", "nd"), "positive": ["value"]},
    "macro_monthly.csv": {"key": ["series", "month"], "required": ["series", "month", "value", "n_obs"], "enum": {"series": "brent_avg|brent_eom|usdidr_close"}, "positive": ["value"]},
    "macro_monthly_wide.csv": {"key": ["month"], "required": ["month", "usdidr_close"], "positive": ["usdidr_close", "brent_avg", "brent_eom"]},
    "financing_events.csv": {"key": ["event_id"], "required": ["event_id", "facility_id", "event_type", "contractual_date", "payment_date", "amount"], "enum": {"event_type": "coupon|principal"}, "positive": ["amount"]},
    "scenario_results.csv": {"key": ["skenario", "case"], "required": ["skenario", "case", "nd_FY2027", "cover_FY2027", "current_ratio_min", "min_liquidity"], "enum": {"case": "adverse|central", "kelompok": "Macro|Market"}, "positive": ["nd_FY2027", "cover_FY2027"]},
    "covenant_quarterly.csv": {"key": ["skenario", "case", "quarter"], "required": ["skenario", "case", "quarter", "nd", "ebitda_ttm"], "enum": {"case": "adverse|central"}, "positive": ["nd", "ebitda_ttm", "debt"]},
    "cash_paths_monthly.csv": {"key": ["skenario", "case", "month"], "required": ["skenario", "case", "month", "closing", "liquidity"], "enum": {"case": "adverse|central"}},
    "mitigation_tests.csv": {"key": ["skenario", "case", "paydown", "dividend_stop"], "required": ["skenario", "case", "paydown", "dividend_stop"], "enum": {"case": "adverse|central"}},
    "backtest.csv": {"key": ["periode"], "required": ["periode", "model", "terealisasi"]},
    "historical_test.csv": {"key": ["index"], "required": ["index", "ebitda", "nd"], "positive": ["ebitda", "nd"]},
}


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


META = ("sources.csv", "lineage.csv", "dictionary.csv", "schemas.csv")   # registri hasil bangunan, tidak masuk lineage dirinya


def _all_tables():
    return sorted(n for n in dp.LAYOUT if n not in META)


def _read(name):
    return pd.read_csv(dp.table(name), low_memory=False)


def sources_table():
    rows = []
    for sid, nama, pub, jenis, url, acc, raws, redis, manifest, deck, note in SOURCES:
        files = [r for r in raws.split(";") if r]
        rows.append({"source_id": sid, "name": nama, "publisher": pub, "kind": jenis, "url": url, "accessed": acc,
                     "raw_files": ";".join(files), "raw_sha256": ";".join(sha256(dp.table(r)) for r in files), "redistribution": redis,
                     "detail_manifest": manifest, "used_in_deck": deck, "note": note})
    return pd.DataFrame(rows)


def _consumers():
    """Modul, deck, dan test yang menyebut nama tabel (rujukan tekstual)."""
    texts = {}
    for base in ("src/smdr", "deck_v5", "tests"):
        for dpth, _, fs in os.walk(os.path.join(dp.ROOT, base)):
            for f in fs:
                if f.endswith(".py") and f not in ("datapaths.py", "registry.py") and "__pycache__" not in dpth:
                    texts[os.path.relpath(os.path.join(dpth, f), dp.ROOT)] = open(os.path.join(dpth, f), encoding="utf-8").read()
    out = {}
    for n in _all_tables():
        out[n] = sorted(k for k, t in texts.items() if '"%s"' % n in t and k.startswith(("src/", "deck_v5/")))
    return out


def lineage_table():
    deck_direct = set(pd.read_csv(dp.table("deck_dependencies.csv"))["dataset"])
    cons = _consumers()
    # hulu: masukan transitif dari tabel yang dipakai langsung
    upstream, frontier = set(), set(deck_direct)
    while frontier:
        nxt = set()
        for t in frontier:
            for part in re.split(r"[;]\s*", PRODUCERS.get(t, ("", ""))[1]):
                part = part.strip()
                if part in dp.LAYOUT and part not in upstream:
                    upstream.add(part); nxt.add(part)
        frontier = nxt
    rows = []
    for n in _all_tables():
        d = _read(n)
        layer = dp.layer_of(n)
        prod, inputs = PRODUCERS.get(n, ("kurasi tangan" if layer == "02_curated" else ("penyedia" if layer == "01_raw" else "kurasi tangan"), ""))
        use = ("setara" if n in RESULT_MARTS else "langsung" if n in deck_direct else "hulu" if n in upstream else "pendukung" if cons[n] else "dokumentasi")
        rows.append({"dataset": n, "layer": LAYER_NAMES[layer], "path": os.path.join("data", dp.LAYOUT[n], n), "rows": len(d), "columns": len(d.columns),
                     "produced_by": prod, "inputs": inputs, "read_by": ";".join(cons[n]), "deck_use": use})
    return pd.DataFrame(rows)


def dictionary_table():
    rows = []
    for n in _all_tables():
        if n == "deck_dependencies.csv":
            continue
        d = _read(n)
        for c in d.columns:
            col = d[c]
            ex = col.dropna().iloc[0] if col.notna().any() else ""
            desc = DESC.get(n, {}).get(c, "")
            rows.append({"dataset": n, "column": c, "dtype": str(col.dtype), "n_missing": int(col.isna().sum()), "n_unique": int(col.nunique()),
                         "example": str(ex)[:60], "description": desc, "description_status": "kurasi" if desc else "otomatis"})
    return pd.DataFrame(rows)


def schemas_table():
    rows = []
    for n, c in CONTRACTS.items():
        d = _read(n)
        for col in d.columns:
            rows.append({"dataset": n, "column": col, "dtype": str(d[col].dtype),
                         "key_part": (c["key"].index(col) + 1) if col in c["key"] else "",
                         "required": "Y" if col in c.get("required", []) else "",
                         "allowed": c.get("enum", {}).get(col, ""), "positive": "Y" if col in c.get("positive", []) else "",
                         "null_iff": ("%s=%s" % (c["null_iff"][1], c["null_iff"][2])) if c.get("null_iff") and c["null_iff"][0] == col else ""})
    return pd.DataFrame(rows)


def validate_contracts():
    """Kembalikan daftar pelanggaran kontrak (kosong = semua tabel memenuhi)."""
    bad = []
    for n, c in CONTRACTS.items():
        d = _read(n)
        if c["key"] and d.duplicated(c["key"]).any():
            bad.append((n, "kunci tidak unik: %s" % c["key"]))
        for col in c.get("required", []):
            if col not in d.columns:
                bad.append((n, "kolom wajib hilang: " + col))
            elif d[col].isna().any():
                bad.append((n, "kolom wajib berisi kosong: " + col))
        for col, vals in c.get("enum", {}).items():
            extra = set(d[col].dropna().astype(str)) - set(vals.split("|"))
            if extra:
                bad.append((n, "nilai di luar domain %s: %s" % (col, sorted(extra)[:5])))
        for col in c.get("positive", []):
            if (d[col].dropna() <= 0).any():
                bad.append((n, "nilai tak positif: " + col))
        if c.get("null_iff"):
            col, scol, sval = c["null_iff"]
            if not ((d[col].isna()) == (d[scol] == sval)).all():
                bad.append((n, "%s kosong tidak sejalan dengan %s=%s" % (col, scol, sval)))
    return bad


def write():
    """Urutan penting: sources, lineage, dictionary, schemas (registri sendiri tidak masuk lineage dirinya)."""
    out = {"sources.csv": sources_table(), "schemas.csv": schemas_table()}
    for name, df in out.items():
        df.to_csv(dp.table(name), index=False, lineterminator="\n")
    for name, df in (("lineage.csv", lineage_table()), ("dictionary.csv", dictionary_table())):
        df.to_csv(dp.table(name), index=False, lineterminator="\n"); out[name] = df
    return {k: len(v) for k, v in out.items()}


if __name__ == "__main__":
    for k, n in write().items():
        print("%-16s %5d baris" % (k, n))
    bad = validate_contracts()
    print("kontrak: %d pelanggaran" % len(bad))
    for b in bad:
        print("  ", b)
