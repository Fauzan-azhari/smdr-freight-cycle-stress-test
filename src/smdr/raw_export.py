"""Ekspor lapisan mentah IDX: setiap butir yang dilaporkan, sebagai teks apa adanya.

Sumber : Financial-Statements/SMDR_Financial_Statements_2021_9M26.xlsx, sheet "Data Sumber" (kurasi tujuh file IDX)
Keluar : data/01_raw/idx/idx_line_items.csv (UTF-8, LF, satu baris per butir, nilai disimpan sebagai teks seperti pada sumber)

Tidak ada konversi tipe, satuan, atau pembersihan di sini. Pembersihan dan standardisasi terjadi pada lapisan berikutnya
(smdr.fs_ingest -> data/03_canonical/fs_long.csv). parity() membuktikan tiap angka kanonik dapat ditelusuri ke satu baris mentah.

Jalankan dari root repo:  PYTHONPATH=src .venv/bin/python -m smdr.raw_export
"""
import csv
import os

import openpyxl

from . import datapaths

SOURCE_XLSX = os.path.join(datapaths.ROOT, "Financial-Statements", "SMDR_Financial_Statements_2021_9M26.xlsx")
HEADER = ["file_id", "file_period", "source_sheet", "source_cell", "source_label", "source_context", "source_value", "unit", "basis", "period_start", "period_end"]
FIRST_ROW = 6   # baris 5 = judul kolom pada sheet sumber


def _text(v):
    return "" if v is None else str(v)


def export(path=None):
    path = path or datapaths.table("idx_line_items.csv")
    wb = openpyxl.load_workbook(SOURCE_XLSX, data_only=True, read_only=True)
    ws = wb["Data Sumber"]
    rows = [[_text(c) for c in r[:len(HEADER)]] for r in ws.iter_rows(min_row=FIRST_ROW, values_only=True) if any(c is not None for c in r)]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(HEADER)
        w.writerows(rows)
    return len(rows)


def parity():
    """Setiap baris fs_long berstatus reported harus punya satu baris mentah dengan nilai sama. Mengembalikan (diuji, tak cocok, tak ditemukan)."""
    import pandas as pd
    raw = pd.read_csv(datapaths.table("idx_line_items.csv"), dtype=str, keep_default_na=False)
    key = raw.set_index(["file_id", "source_sheet", "source_cell"])
    fs = pd.read_csv(datapaths.table("fs_long.csv"))
    fs = fs[fs["status"] == "reported"]
    mismatch, missing = [], []
    for r in fs.itertuples():
        k = (r.source_file_id, str(r.source_sheet), r.source_cell)
        if k not in key.index:
            missing.append(k)
            continue
        hit = key.loc[[k]]
        vals = pd.to_numeric(hit["source_value"], errors="coerce").dropna()
        if not any(abs(abs(v) - abs(r.value_usd)) <= 1.0 for v in vals):
            mismatch.append((k, r.value_usd, hit["source_value"].tolist()))
    return len(fs), mismatch, missing


if __name__ == "__main__":
    n = export()
    print("%d baris -> %s" % (n, os.path.relpath(datapaths.table("idx_line_items.csv"), datapaths.ROOT)))
    tested, mism, miss = parity()
    print("paritas fs_long vs mentah: diuji %d, tak cocok %d, tak ditemukan %d" % (tested, len(mism), len(miss)))
