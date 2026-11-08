"""Ingest laporan keuangan SMDR dari workbook hasil kurasi ke tabel panjang (tidy).

Sumber : Financial-Statements/SMDR_Financial_Statements_2021_9M26.xlsx
Keluar : data/03_canonical/fs_long.csv; data/00_registry/fs_line_dictionary.csv, fs_source_manifest.csv

Angka dibaca dari nilai tersimpan pada sheet laporan. Alamat sel aslinya (file, sheet,
sel pada file IDX) diambil dari formula sheet laporan yang menunjuk ke 'Data Sumber',
dan nilai tersimpan dicocokkan lagi dengan Data Sumber.

Jalankan dari root repo:  PYTHONPATH=src python3 -m smdr.fs_ingest
"""
import csv
import hashlib
import math
import os
import re
import warnings

from . import datapaths

import openpyxl

from .fs_lines import STATEMENTS, label_index

warnings.filterwarnings("ignore")

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SOURCE_XLSX = os.path.join(ROOT, "Financial-Statements", "SMDR_Financial_Statements_2021_9M26.xlsx")
IDX_DIR = os.path.join(ROOT, "Financial-Statements", "Excel-FS")

# sheet laporan, kolom data -> periode, baris awal/akhir pencarian
MAIN_COLUMNS = {
    "D": "FY2021", "E": "FY2022", "F": "FY2023", "G": "FY2024", "H": "FY2025",
    "J": "3M26", "K": "6M26", "L": "9M26",
}
MAIN_SHEETS = {"IS": "Laba Rugi", "BS": "Posisi Keuangan", "CF": "Arus Kas"}
COGS_ROWS = (17, 26)  # Catatan: rincian beban pokok pendapatan

# Pembanding Interim memuat 2025 dan 2026 berdampingan
INTERIM_COLUMNS = {"D": "3M25", "E": "3M26", "G": "6M25", "H": "6M26", "J": "9M25", "K": "9M26"}
INTERIM_SECTIONS = {"Laba rugi dan penghasilan komprehensif": "IS", "Arus kas": "CF"}

PERIODS = {
    "FY2021": ("flow", "2021-01-01", "2021-12-31"), "FY2022": ("flow", "2022-01-01", "2022-12-31"),
    "FY2023": ("flow", "2023-01-01", "2023-12-31"), "FY2024": ("flow", "2024-01-01", "2024-12-31"),
    "FY2025": ("flow", "2025-01-01", "2025-12-31"),
    "3M25": ("flow", "2025-01-01", "2025-03-31"), "6M25": ("flow", "2025-01-01", "2025-06-30"),
    "9M25": ("flow", "2025-01-01", "2025-09-30"),
    "3M26": ("flow", "2026-01-01", "2026-03-31"), "6M26": ("flow", "2026-01-01", "2026-06-30"),
    "9M26": ("flow", "2026-01-01", "2026-09-30"),
}

REF = re.compile(r"'Data Sumber'!G(\d+)")


class IngestError(Exception):
    pass


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_manifest(wb_values):
    """Daftar file sumber IDX dari sheet Panduan, dengan verifikasi hash terhadap file asli."""
    ws = wb_values["Panduan"]
    header = None
    out = []
    for row in ws.iter_rows(values_only=True):
        cells = [c for c in row if c is not None]
        if cells[:1] == ["ID"] and "SHA-256" in cells:
            header = cells
            continue
        if header and cells and re.fullmatch(r"F\d\d", str(cells[0])):
            rec = dict(zip(header, cells))
            if "File asli" not in rec:
                break
            out.append(rec)
        elif header and out and not cells:
            break
    for rec in out:
        path = os.path.join(IDX_DIR, rec["File asli"])
        rec["hash_check"] = (
            "OK" if os.path.exists(path) and sha256(path) == rec["SHA-256"]
            else "FILE_TIDAK_ADA" if not os.path.exists(path) else "BEDA"
        )
    return out


def data_sumber_index(wb_values):
    ws = wb_values["Data Sumber"]
    idx = {}
    for i, r in enumerate(ws.iter_rows(min_row=1, values_only=True), start=1):
        if r[0] and re.fullmatch(r"F\d\d", str(r[0])):
            idx[i] = {"file_id": r[0], "sheet": str(r[2]), "cell": r[3], "label": r[4], "value": r[6], "basis": r[8]}
    return idx


def cell_record(statement, line_key, label, period, wb_cell, formula, cached, ds_idx):
    m = REF.search(formula) if isinstance(formula, str) else None
    src = ds_idx.get(int(m.group(1))) if m else None
    status, value = "reported", None
    if isinstance(cached, (int, float)) and not isinstance(cached, bool):
        value = float(cached)
    elif cached == "n.d.":
        status = "nd"
    else:
        raise IngestError("nilai tak dikenal %r di %s" % (cached, wb_cell))
    if src is not None:
        # nilai tersimpan harus sama dengan angka pada Data Sumber
        ds_val = src["value"]
        if status == "reported" and not (isinstance(ds_val, (int, float)) and math.isclose(ds_val, value, abs_tol=0.5)):
            raise IngestError("nilai %s (%r) tidak cocok dengan Data Sumber (%r)" % (wb_cell, value, ds_val))
        if status == "nd" and isinstance(ds_val, (int, float)):
            raise IngestError("%s n.d. tetapi Data Sumber berisi angka %r" % (wb_cell, ds_val))
    kind, start, end = PERIODS[period] if period in PERIODS else (None, None, None)
    return {
        "statement": statement, "line_key": line_key, "line_label_id": label, "period": period,
        "value_usd": "" if value is None else repr(value) if value != int(value) else str(int(value)),
        "status": status,
        "source_file_id": src["file_id"] if src else "",
        "source_sheet": src["sheet"] if src else "",
        "source_cell": src["cell"] if src else "",
        "workbook_cell": wb_cell,
    }


def balance_sheet_dates():
    return {"FY2021": "2021-12-31", "FY2022": "2022-12-31", "FY2023": "2023-12-31", "FY2024": "2024-12-31",
            "FY2025": "2025-12-31", "3M26": "2026-03-31", "6M26": "2026-06-30", "9M26": "2026-09-30"}


def extract_main(wb_f, wb_v, ds_idx):
    rows = []
    for stmt, sheet in MAIN_SHEETS.items():
        idx = label_index(stmt)
        wsf, wsv = wb_f[sheet], wb_v[sheet]
        for r in range(9, wsv.max_row + 1):
            label = wsv["B%d" % r].value
            if not isinstance(label, str):
                continue
            has_values = any(wsv["%s%d" % (c, r)].value is not None for c in MAIN_COLUMNS)
            if not has_values:
                continue  # judul seksi
            if label not in idx:
                raise IngestError("label belum terdaftar di fs_lines [%s baris %d]: %r" % (stmt, r, label))
            key = idx[label][0]
            for col, period in MAIN_COLUMNS.items():
                v = wsv["%s%d" % (col, r)].value
                if v is None:
                    continue
                rows.append(cell_record(stmt, key, label, period, "'%s'!%s%d" % (sheet, col, r),
                                        wsf["%s%d" % (col, r)].value, v, ds_idx))
    # rincian beban pokok
    idx = label_index("COGS_NOTE")
    wsf, wsv = wb_f["Catatan"], wb_v["Catatan"]
    for r in range(COGS_ROWS[0], COGS_ROWS[1] + 1):
        label = wsv["B%d" % r].value
        if label not in idx:
            raise IngestError("label COGS_NOTE belum terdaftar [baris %d]: %r" % (r, label))
        for col, period in MAIN_COLUMNS.items():
            v = wsv["%s%d" % (col, r)].value
            if v is None:
                continue
            rows.append(cell_record("COGS_NOTE", idx[label][0], label, period, "'Catatan'!%s%d" % (col, r),
                                    wsf["%s%d" % (col, r)].value, v, ds_idx))
    return rows


def extract_blocks(wb_f, wb_v, ds_idx, sheet, first_row, last_row, statement):
    """Baris bersusun blok: judul blok (tanpa angka) diikuti baris data. Label kamus = 'judul | baris'."""
    idx = label_index(statement)
    wsf, wsv = wb_f[sheet], wb_v[sheet]
    rows, header = [], None
    for r in range(first_row, last_row + 1):
        label = wsv["B%d" % r].value
        if not isinstance(label, str):
            continue
        cells = {c: wsv["%s%d" % (c, r)].value for c in MAIN_COLUMNS}
        if all(v is None for v in cells.values()):
            header = label
            continue
        full = "%s | %s" % (header, label)
        if full not in idx:
            raise IngestError("label belum terdaftar di fs_lines [%s baris %d]: %r" % (statement, r, full))
        for col, period in MAIN_COLUMNS.items():
            if cells[col] is None:
                continue
            rows.append(cell_record(statement, idx[full][0], full, period, "'%s'!%s%d" % (sheet, col, r),
                                    wsf["%s%d" % (col, r)].value, cells[col], ds_idx))
    return rows


# Judul pada Data Sumber berbeda tipis dari sheet laporan
COGS_ALIAS = {"Beban pokok penjualan dan pendapatan": "Beban pokok pendapatan"}
INTERIM_2025 = {"F05": "3M25", "F06": "6M25", "F07": "9M25"}


def extract_cogs_2025(ds_idx):
    """Rincian beban pokok 2025 interim tidak ada di sheet Catatan; angkanya ada di Data Sumber
    sebagai kolom pembanding pada file 2026 (sheet IDX 3670000)."""
    idx = label_index("COGS_NOTE")
    rows = []
    for ds_row, d in sorted(ds_idx.items()):
        if d["file_id"] not in INTERIM_2025 or d["sheet"] != "3670000" or d["basis"] != "Pembanding":
            continue
        label = COGS_ALIAS.get(d["label"], d["label"])
        if label not in idx:
            raise IngestError("label COGS 2025 belum terdaftar: %r (Data Sumber baris %d)" % (d["label"], ds_row))
        if not isinstance(d["value"], (int, float)):
            continue
        rows.append({
            "statement": "COGS_NOTE", "line_key": idx[label][0], "line_label_id": label,
            "period": INTERIM_2025[d["file_id"]], "value_usd": str(int(d["value"])) if d["value"] == int(d["value"]) else repr(d["value"]),
            "status": "reported", "source_file_id": d["file_id"], "source_sheet": d["sheet"], "source_cell": d["cell"],
            "workbook_cell": "'Data Sumber'!G%d" % ds_row,
        })
    return rows


def extract_interim(wb_f, wb_v, ds_idx):
    """Kolom 2025 dari Pembanding Interim. Kolom 2026 hanya dipakai sebagai pembanding silang."""
    sheet = "Pembanding Interim"
    wsf, wsv = wb_f[sheet], wb_v[sheet]
    rows, section = [], None
    for r in range(9, wsv.max_row + 1):
        label = wsv["B%d" % r].value
        if not isinstance(label, str):
            continue
        if label in INTERIM_SECTIONS:
            section = INTERIM_SECTIONS[label]
            continue
        if section is None or not any(wsv["%s%d" % (c, r)].value is not None for c in INTERIM_COLUMNS):
            continue
        idx = label_index(section)
        if label not in idx:
            raise IngestError("label interim belum terdaftar [%s baris %d]: %r" % (section, r, label))
        for col, period in INTERIM_COLUMNS.items():
            v = wsv["%s%d" % (col, r)].value
            if v is None:
                continue
            rec = cell_record(section, idx[label][0], label, period, "'%s'!%s%d" % (sheet, col, r),
                              wsf["%s%d" % (col, r)].value, v, ds_idx)
            rows.append(rec)
    return rows


def merge(main_rows, interim_rows):
    """Gabungkan; kolom 2026 pada Pembanding Interim harus sama dengan sheet laporan."""
    key = lambda x: (x["statement"], x["line_key"], x["period"])
    have = {key(x): x for x in main_rows}
    out = list(main_rows)
    conflicts = []
    for x in interim_rows:
        k = key(x)
        if k in have:
            a, b = have[k], x
            if a["status"] != b["status"] or a["value_usd"] != b["value_usd"]:
                conflicts.append((k, a["value_usd"] or a["status"], b["value_usd"] or b["status"]))
        else:
            out.append(x)
    if conflicts:
        raise IngestError("Pembanding Interim 2026 berbeda dari sheet laporan: %r" % conflicts[:5])
    return out


def write_csv(path, fieldnames, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def main():
    wb_f = openpyxl.load_workbook(SOURCE_XLSX)
    wb_v = openpyxl.load_workbook(SOURCE_XLSX, data_only=True)
    ds_idx = data_sumber_index(wb_v)
    manifest = read_manifest(wb_v)
    rows = merge(extract_main(wb_f, wb_v, ds_idx), extract_interim(wb_f, wb_v, ds_idx))
    rows += extract_cogs_2025(ds_idx)
    rows += extract_blocks(wb_f, wb_v, ds_idx, "Perubahan Ekuitas", 9, 33, "EQ")
    rows += extract_blocks(wb_f, wb_v, ds_idx, "Catatan", 28, 228, "PPE")
    rows += extract_blocks(wb_f, wb_v, ds_idx, "Catatan", 230, 237, "DEBT_NOTE")

    order = {"IS": 0, "BS": 1, "CF": 2, "COGS_NOTE": 3, "EQ": 4, "PPE": 5, "DEBT_NOTE": 6}
    pord = {p: i for i, p in enumerate(["FY2021", "FY2022", "FY2023", "FY2024", "FY2025",
                                         "3M25", "6M25", "9M25", "3M26", "6M26", "9M26"])}
    line_pos = {(s, k[1]): i for s, lines in STATEMENTS.items() for i, k in enumerate(lines)}
    rows.sort(key=lambda x: (order[x["statement"]], line_pos[(x["statement"], x["line_key"])], pord[x["period"]]))

    for x in rows:
        kind, start, end = PERIODS[x["period"]]
        if x["statement"] == "BS":
            x["basis"], x["period_start"], x["period_end"] = "instant", "", balance_sheet_dates()[x["period"]]
        else:
            x["basis"], x["period_start"], x["period_end"] = "ytd" if x["period"][1] == "M" else "fy", start, end
    cols = ["statement", "line_key", "line_label_id", "period", "basis", "period_start", "period_end",
            "value_usd", "status", "source_file_id", "source_sheet", "source_cell", "workbook_cell"]
    write_csv(datapaths.table("fs_long.csv"), cols, rows)

    dictionary = []
    for stmt, lines in STATEMENTS.items():
        for label, key, parent, sign in lines:
            dictionary.append({"statement": stmt, "line_key": key, "line_label_id": label,
                               "parent": parent or "", "sign": sign})
    write_csv(datapaths.table("fs_line_dictionary.csv"),
              ["statement", "line_key", "line_label_id", "parent", "sign"], dictionary)

    man_rows = [{"file_id": m["ID"], "period": m["Periode"], "file": m["File asli"], "start": str(m["Awal"])[:10],
                 "end": str(m["Akhir"])[:10], "audit": m["Audit"], "sha256": m["SHA-256"], "hash_check": m["hash_check"]}
                for m in manifest]
    write_csv(datapaths.table("fs_source_manifest.csv"),
              ["file_id", "period", "file", "start", "end", "audit", "sha256", "hash_check"], man_rows)

    n_nd = sum(1 for x in rows if x["status"] == "nd")
    print("%d baris -> %s  (n.d.: %d)" % (len(rows), os.path.relpath(datapaths.table("fs_long.csv"), ROOT), n_nd))
    print("hash file sumber IDX:", ", ".join("%s=%s" % (m["file_id"], m["hash_check"]) for m in man_rows))


if __name__ == "__main__":
    main()
