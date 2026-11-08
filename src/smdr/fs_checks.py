"""Validasi identitas akuntansi pada data/03_canonical/fs_long.csv.

Aturan penjumlahan dibaca dari kamus baris (parent dan sign), jadi tidak ada angka yang
ditulis ulang di sini. Toleransi USD 1, sama dengan sheet Rekonsiliasi pada workbook sumber.
Sel n.d. dihitung nol dalam penjumlahan dan dicatat jumlahnya di kolom nd_terms.

Selisih yang sudah dipahami penyebabnya ditandai KNOWN lewat data/02_curated/quality/fs_known_exceptions.csv.
Selisih lain berstatus FAIL dan menghentikan pipeline.

Jalankan dari root repo:  PYTHONPATH=src python3 -m smdr.fs_checks
"""
import csv
import os
import sys

from . import datapaths
from collections import defaultdict

from .fs_lines import EQUALITIES

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TOLERANCE = 1.0

PRIOR_YEAR_END = {  # periode -> periode neraca awal tahun berjalan
    "FY2022": "FY2021", "FY2023": "FY2022", "FY2024": "FY2023", "FY2025": "FY2024",
    "3M25": "FY2024", "6M25": "FY2024", "9M25": "FY2024",
    "3M26": "FY2025", "6M26": "FY2025", "9M26": "FY2025",
}


def load():
    values, status = {}, {}
    with open(datapaths.table("fs_long.csv"), encoding="utf-8") as f:
        for r in csv.DictReader(f):
            k = (r["statement"], r["line_key"], r["period"])
            values[k] = float(r["value_usd"]) if r["status"] == "reported" else None
    dictionary = []
    with open(datapaths.table("fs_line_dictionary.csv"), encoding="utf-8") as f:
        dictionary = list(csv.DictReader(f))
    return values, dictionary


def load_exceptions():
    path = datapaths.table("fs_known_exceptions.csv")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return {(r["check_id"], r["period"]): r["explanation"] for r in csv.DictReader(f)}


def run_checks(values, dictionary):
    periods = sorted({k[2] for k in values})
    results = []

    def record(check_id, stmt, period, desc, expected, actual, nd_terms):
        diff = actual - expected
        results.append({
            "check_id": check_id, "statement": stmt, "period": period, "description": desc,
            "expected": expected, "actual": actual, "diff": diff, "nd_terms": nd_terms,
            "status": "PASS" if abs(diff) <= TOLERANCE else "FAIL",
        })

    # 1) subtotal = jumlah komponen menurut kamus
    groups = defaultdict(list)
    for d in dictionary:
        if d["parent"]:
            groups[(d["statement"], d["parent"])].append((d["line_key"], int(d["sign"])))
    for (stmt, parent), children in groups.items():
        target = parent.split("#")[0]
        for p in periods:
            reported = values.get((stmt, target, p))
            terms = [(values.get((stmt, c, p)), s) for c, s in children if (stmt, c, p) in values]
            if reported is None or not terms or all(v is None for v, _ in terms):
                continue
            total = sum(s * v for v, s in terms if v is not None)
            nd = sum(1 for v, _ in terms if v is None)
            record("SUM:%s:%s" % (stmt, parent), stmt, p,
                   "%s = jumlah komponen" % target, reported, total, nd)

    # 2) kesamaan pasangan baris
    for stmt, a, b in EQUALITIES:
        for p in periods:
            va, vb = values.get((stmt, a, p)), values.get((stmt, b, p))
            if va is None or vb is None:
                continue
            record("EQ:%s:%s=%s" % (stmt, a, b), stmt, p, "%s = %s" % (a, b), va, vb, 0)

    # 3) antar laporan
    for p in periods:
        cash_end, cash_bs = values.get(("CF", "cash_end", p)), values.get(("BS", "cash", p))
        if cash_end is not None and cash_bs is not None:
            record("X:cash_end=BS_cash", "CF/BS", p, "kas akhir arus kas = kas neraca", cash_bs, cash_end, 0)
        cogs_is, cogs_n = values.get(("IS", "cogs", p)), values.get(("COGS_NOTE", "cogs_note", p))
        if cogs_is is not None and cogs_n is not None:
            record("X:cogs_note=IS", "IS/COGS_NOTE", p, "beban pokok catatan = laba rugi", cogs_is, cogs_n, 0)
        cash_begin, prev = values.get(("CF", "cash_begin", p)), PRIOR_YEAR_END.get(p)
        if cash_begin is not None and prev and values.get(("BS", "cash", prev)) is not None:
            record("X:cash_begin=BS_prior", "CF/BS", p, "kas awal = kas neraca akhir tahun lalu",
                   values[("BS", "cash", prev)], cash_begin, 0)
    # 4) ekuitas, aset tetap, dan utang bank terhadap laporan utama
    def pair(check_id, stmt, desc, left, right, p):
        a, b = values.get(left + (p,)), values.get(right + (p,))
        if a is not None and b is not None:
            record(check_id, stmt, p, desc, a, b, 0)

    for p in periods:
        for blk, bs_key in (("total", "total_equity"), ("parent", "equity_parent"), ("nci", "equity_nci")):
            pair("X:eq_closing=BS_%s" % blk, "EQ/BS", "ekuitas akhir (%s) = neraca" % blk, ("BS", bs_key), ("EQ", blk + ".closing"), p)
        pair("X:eq_profit=IS_total", "EQ/IS", "laba pada perubahan ekuitas = laba rugi", ("IS", "profit_period"), ("EQ", "total.profit"), p)
        pair("X:eq_profit=IS_parent", "EQ/IS", "laba induk pada perubahan ekuitas = laba rugi", ("IS", "profit_parent"), ("EQ", "parent.profit"), p)
        pair("X:eq_oci=IS_total", "EQ/IS", "OCI pada perubahan ekuitas = laba rugi", ("IS", "oci_total"), ("EQ", "total.oci"), p)
        for mv in ("opening", "profit", "oci", "dividends", "closing"):
            a, b, c = (values.get(("EQ", "%s.%s" % (x, mv), p)) for x in ("total", "parent", "nci"))
            if None not in (a, b, c):
                record("X:eq_total=parent+nci:" + mv, "EQ", p, "ekuitas total = induk + non-pengendali (%s)" % mv, a, b + c, 0)
        prev = PRIOR_YEAR_END.get(p)
        if prev:
            a, b = values.get(("BS", "total_equity", prev)), values.get(("EQ", "total.opening", p))
            if a is not None and b is not None:
                record("X:eq_opening=BS_prior", "EQ/BS", p, "ekuitas awal = ekuitas neraca akhir tahun lalu", a, b, 0)
        nbv, cost, acc = (values.get(("PPE", k, p)) for k in ("nbv.ppe.closing", "cost.ppe.closing", "acc.ppe.closing"))
        pair("X:ppe_nbv=BS", "PPE/BS", "nilai buku aset tetap = neraca", ("BS", "fixed_assets"), ("PPE", "nbv.ppe.closing"), p)
        if None not in (nbv, cost, acc):
            record("X:ppe_nbv=cost-acc", "PPE", p, "nilai buku = bruto - akumulasi", nbv, cost - acc, 0)
        a, b = values.get(("PPE", "nbv.ppe.opening", p)), None
        if prev:
            b = values.get(("BS", "fixed_assets", prev))
        if a is not None and b is not None:
            record("X:ppe_nbv_opening=BS_prior", "PPE/BS", p, "nilai buku awal = neraca akhir tahun lalu", b, a, 0)
        for note_key, bs_key in (("bank_st_total", "bank_short_term"), ("bank_lt_current", "bank_long_term_current"),
                                 ("bank_lt_noncurrent", "bank_long_term")):
            pair("X:bank_note=BS:" + note_key, "DEBT_NOTE/BS", "rincian utang bank = neraca (%s)" % note_key,
                 ("BS", bs_key), ("DEBT_NOTE", note_key), p)
    return results


def main():
    values, dictionary = load()
    exceptions = load_exceptions()
    results = run_checks(values, dictionary)
    for r in results:
        if r["status"] == "FAIL" and (r["check_id"], r["period"]) in exceptions:
            r["status"] = "KNOWN"
            r["note"] = exceptions[(r["check_id"], r["period"])]
        else:
            r["note"] = ""
    cols = ["check_id", "statement", "period", "description", "expected", "actual", "diff", "nd_terms", "status", "note"]
    with open(datapaths.table("fs_checks.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in results:
            w.writerow({c: (("%.0f" % r[c]) if c in ("expected", "actual", "diff") else r[c]) for c in cols})
    n = {s: sum(1 for r in results if r["status"] == s) for s in ("PASS", "KNOWN", "FAIL")}
    print("%d cek: PASS %d, KNOWN %d, FAIL %d" % (len(results), n["PASS"], n["KNOWN"], n["FAIL"]))
    for r in results:
        if r["status"] in ("FAIL", "KNOWN"):
            print("  %-5s %-34s %-7s selisih %12.0f  nd=%d" % (r["status"], r["check_id"], r["period"], r["diff"], r["nd_terms"]))
    return 1 if n["FAIL"] else 0


if __name__ == "__main__":
    sys.exit(main())
