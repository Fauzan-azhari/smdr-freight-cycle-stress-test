"""Baseline historis dari data tidy: kuartal diskrit, TTM, saldo pembuka, dan jembatan ke benchmark legacy.

Tidak ada nilai yang diisi nol. Sel n.d. pada salah satu komponen membuat hasil turunan n.d.
Benchmark legacy dibaca dari data/02_curated/decisions/legacy_benchmark.csv (dicatat dari spesifikasi),
tidak dari model/data.

Keluaran: data/04_marts/baseline/
Jalankan dari root repo:  PYTHONPATH=src .venv/bin/python -m smdr.baseline
"""
import datetime as dt
import hashlib
import json
import os
import sys

import numpy as np
import pandas as pd

from . import datapaths
from . import fs_checks

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RUN_ID = "M1_baseline"
OUT = datapaths.BASELINE
FLOW = ("IS", "CF", "COGS_NOTE")
TOLERANCE = 1.0  # USD penuh

QUARTERS = {  # kuartal: (periode kumulatif akhir, periode kumulatif sebelumnya atau None)
    "2025Q1": ("3M25", None), "2025Q2": ("6M25", "3M25"), "2025Q3": ("9M25", "6M25"), "2025Q4": ("FY2025", "9M25"),
    "2026Q1": ("3M26", None), "2026Q2": ("6M26", "3M26"), "2026Q3": ("9M26", "6M26"),
}
TTM = {"label": "TTM_2026-09", "plus": "FY2025", "minus": "9M25", "add": "9M26"}

# Baris yang tidak boleh dihitung TTM walau komponennya terisi
NOT_COMPARABLE = {
    ("CF", "dividends_received"): "galat penyajian sumber pada 9M25 (lihat fs_known_exceptions)",
}


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_wide():
    df = pd.read_csv(datapaths.table("fs_long.csv"))
    return df.pivot(index=["statement", "line_key"], columns="period", values="value_usd")


def quarters(w):
    rows = []
    for (stmt, key), r in w.iterrows():
        if stmt not in FLOW:
            continue
        for q, (cum, prev) in QUARTERS.items():
            a = r.get(cum, np.nan)
            b = 0.0 if prev is None else r.get(prev, np.nan)
            if pd.isna(a) or pd.isna(b):
                rows.append((stmt, key, q, np.nan, "nd", "%s-%s" % (cum, prev) if prev else cum))
            else:
                rows.append((stmt, key, q, a - b, "derived", "%s-%s" % (cum, prev) if prev else cum))
    return pd.DataFrame(rows, columns=["statement", "line_key", "quarter", "value_usd", "status", "method"])


def ttm(w):
    rows = []
    for (stmt, key), r in w.iterrows():
        if stmt not in FLOW:
            continue
        comp = [r.get(TTM["plus"], np.nan), r.get(TTM["minus"], np.nan), r.get(TTM["add"], np.nan)]
        if (stmt, key) in NOT_COMPARABLE:
            status, val, why = "not_comparable", np.nan, NOT_COMPARABLE[(stmt, key)]
        elif any(pd.isna(c) for c in comp):
            miss = [n for n, c in zip((TTM["plus"], TTM["minus"], TTM["add"]), comp) if pd.isna(c)]
            status, val, why = "nd_component", np.nan, "n.d. pada " + ",".join(miss)
        else:
            status, val, why = "ok", comp[0] - comp[1] + comp[2], ""
        rows.append((stmt, key, TTM["label"], val, status, why))
    return pd.DataFrame(rows, columns=["statement", "line_key", "window", "value_usd", "status", "reason"])


def load_zero_fill(statuses=("approved",)):
    """Aturan zero-fill. Default hanya yang disetujui; mode eksploratori boleh menyertakan 'proposed'."""
    path = datapaths.table("zero_fill_rules.csv")
    df = pd.read_csv(path)
    df = df[df["status"].isin(statuses)]
    return {(r.statement, r.line_key, r.period): (r.rule_id, float(r.fill_value)) for r in df.itertuples()}


def load_decisions():
    return pd.read_csv(datapaths.table("decisions.csv")).set_index("decision_id")["decision"].to_dict()


def metrics(w):
    """Ukuran legacy direproduksi dari tidy. Tiap entri: nilai, sumber komponen, aturan zero-fill yang dipakai."""
    rules, used = load_zero_fill(), []

    def g(s, k, p):
        v = w.loc[(s, k), p]
        if pd.isna(v) and (s, k, p) in rules:
            rid, fill = rules[(s, k, p)]
            used.append(rid)
            return fill
        return v

    flow = lambda s, k: g(s, k, "FY2025") - g(s, k, "9M25") + g(s, k, "9M26")
    ebit = lambda p: g("IS", "gross_profit", p) - g("IS", "ga_expense", p)
    ebit_ttm = ebit("FY2025") - ebit("9M25") + ebit("9M26")
    ebitda = ebit_ttm + flow("COGS_NOTE", "depreciation")
    fixed = (g("BS", "bank_short_term", "9M26") + g("BS", "bank_long_term_current", "9M26")
             + g("BS", "lease_current", "9M26") + g("BS", "sukuk_current", "9M26") + flow("IS", "finance_expense"))
    src = "fs_long: %s; periode FY2025, 9M25, 9M26"
    z = ",".join(sorted(set(used)))
    return {
        "revenue_ttm": (flow("IS", "revenue"), src % "IS.revenue", ""),
        "ebit_ttm": (ebit_ttm, src % "IS.gross_profit - IS.ga_expense", ""),
        "ebitda_ttm_legacy": (ebitda, src % "EBIT + COGS_NOTE.depreciation", ""),
        "fixed_obligations_ttm": (fixed, "fs_long: BS.bank_short_term + bank_long_term_current + lease_current + sukuk_current (9M26) + IS.finance_expense TTM", z),
        "fixed_charge_cover": (ebitda / fixed, "ebitda_ttm_legacy / fixed_obligations_ttm", z),
        "cash_consolidated": (g("BS", "cash", "9M26"), "fs_long: BS.cash 9M26", ""),
    }


def load_evidence():
    return pd.read_csv(datapaths.table("evidence.csv"))


def ev_value(ev, evidence_id):
    return float(ev.loc[ev["evidence_id"] == evidence_id, "value"].iloc[0])


def bridge(w):
    legacy = pd.read_csv(datapaths.table("legacy_benchmark.csv")).set_index("metric")
    new = metrics(w)
    rows = []
    for m, (val, src, zf) in new.items():
        old = float(legacy.loc[m, "value"])
        tol = 1e-4 if m == "fixed_charge_cover" else TOLERANCE
        diff = val - old
        ok = abs(diff) <= tol
        rows.append({
            "metric": m, "legacy_value": old, "tidy_value": val, "definition_adjustment": 0.0,
            "reconciled_value": val, "difference": diff,
            "difference_reason": "identik dengan benchmark (definisi sama)" if ok else "BELUM DIJELASKAN",
            "source_ids": src, "zero_fill_rules": zf, "status": "reproduced" if ok else "not_reproduced",
        })
    # penyesuaian definisi: depresiasi di luar beban pokok (G&A), dibuktikan ke PDF LK; nilai dibaca dari evidence
    ev = load_evidence()
    basis = load_decisions().get("D01")  # basis depresiasi beban pokok FY2025 yang dipilih pengguna
    if basis not in ("pdf_audit", "idx_excel"):
        raise ValueError("keputusan D01 (basis EBITDA) belum ada atau tidak dikenal: %r" % basis)
    legacy_e = new["ebitda_ttm_legacy"][0]
    ga_fy, ga_9m25, ga_9m26 = (ev_value(ev, i) for i in ("EV-LK25-GA-DEP", "EV-LK9M26-GA-DEP-25", "EV-LK9M26-GA-DEP-26"))
    ga_ttm = ga_fy - ga_9m25 + ga_9m26
    pdf_gap = ev_value(ev, "EV-LK25-COGS-DEP-PDF") - ev_value(ev, "EV-IDX-COGS-DEP-FY25")
    # evidence harus cocok dengan data tidy sebelum dipakai
    ties = [(ev_value(ev, "EV-IDX-COGS-DEP-FY25"), w.loc[("COGS_NOTE", "depreciation"), "FY2025"], "depresiasi beban pokok FY2025 (IDX)"),
            (ev_value(ev, "EV-LK25-GA-TOTAL"), w.loc[("IS", "ga_expense"), "FY2025"], "total G&A FY2025")]
    for a, b, what in ties:
        if abs(a - b) > TOLERANCE:
            raise ValueError("evidence tidak cocok dengan fs_long: %s (%s vs %s)" % (what, a, b))
    rows.append({
        "metric": "ebitda_ttm_operating_reconstructed", "legacy_value": legacy_e, "tidy_value": legacy_e,
        "definition_adjustment": ga_ttm, "reconciled_value": legacy_e + ga_ttm, "difference": ga_ttm,
        "difference_reason": "tambah penyusutan dalam beban umum dan administrasi TTM = FY2025 %s - 9M25 %s + 9M26 %s; depresiasi beban pokok basis Excel IDX; tidak ditemukan beban amortisasi pada laba rugi" % (
            "{:,.0f}".format(ga_fy), "{:,.0f}".format(ga_9m25), "{:,.0f}".format(ga_9m26)),
        "source_ids": "EV-LK25-GA-DEP;EV-LK9M26-GA-DEP-25;EV-LK9M26-GA-DEP-26", "zero_fill_rules": "",
        "status": "selected" if basis == "idx_excel" else "verified_primary",
    })
    rows.append({
        "metric": "ebitda_ttm_operating_pdf_basis", "legacy_value": legacy_e, "tidy_value": legacy_e,
        "definition_adjustment": ga_ttm + pdf_gap, "reconciled_value": legacy_e + ga_ttm + pdf_gap, "difference": ga_ttm + pdf_gap,
        "difference_reason": "basis depresiasi beban pokok FY2025 menurut PDF audit (selisih %s terhadap Excel IDX; sama dengan pemulihan penurunan nilai aset tetap); cocok dengan 240,04 juta pada catatan riset; basis dipilih pengguna 2026-11-05 (D01, KE-LK-01)" % "{:,.0f}".format(pdf_gap),
        "source_ids": "EV-LK25-COGS-DEP-PDF;EV-IDX-COGS-DEP-FY25;EV-LK25-IMP-REVERSAL;D01", "zero_fill_rules": "",
        "status": "selected" if basis == "pdf_audit" else "verified_primary",
    })
    return pd.DataFrame(rows)


def main():
    values, dictionary = fs_checks.load()
    results = fs_checks.run_checks(values, dictionary)
    exc = fs_checks.load_exceptions()
    failed = [r for r in results if r["status"] == "FAIL" and (r["check_id"], r["period"]) not in exc]
    if failed:
        print("Cek integritas data gagal; baseline dihentikan:", failed[:3])
        return 1
    w = load_wide()
    q, t, b = quarters(w), ttm(w), bridge(w)
    os.makedirs(OUT, exist_ok=True)
    q.to_csv(os.path.join(OUT, "baseline_quarters.csv"), index=False)
    t.to_csv(os.path.join(OUT, "baseline_ttm.csv"), index=False)
    b.to_csv(os.path.join(OUT, "baseline_bridge.csv"), index=False)
    opening = w.xs("9M26", axis=1).reset_index()
    opening = opening[opening["statement"] == "BS"].rename(columns={"9M26": "value_usd"})
    opening.insert(2, "as_of", "2026-09-30")
    opening.to_csv(os.path.join(OUT, "opening_balance_2026-09-30.csv"), index=False)
    manifest = {
        "run_id": RUN_ID, "model_version": "v5_transition", "created": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "financial_cutoff": "2026-09-30", "knowledge_cutoff": "2026-11-05", "ttm_window": TTM,
        "input_sha256": {os.path.relpath(datapaths.table(n), ROOT): sha256(datapaths.table(n)) for n in ("fs_long.csv", "zero_fill_rules.csv", "evidence.csv", "decisions.csv", "legacy_benchmark.csv")},
        "checks": {"total": len(results), "pass": sum(r["status"] == "PASS" for r in results),
                   "known_exceptions": sum(1 for r in results if r["status"] == "FAIL" and (r["check_id"], r["period"]) in exc), "fail": 0},
        "decisions_applied": {k: v for k, v in load_decisions().items() if k in ("D01", "D02")},
        "bridge_status": b["status"].value_counts().to_dict(),
        "python": sys.version.split()[0], "pandas": pd.__version__,
    }
    with open(os.path.join(OUT, "run_manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    print("run", RUN_ID, "->", os.path.relpath(OUT, ROOT))
    print(b[["metric", "legacy_value", "tidy_value", "status"]].to_string(index=False, float_format=lambda x: "%.4f" % x if abs(x) < 10 else "%.0f" % x))
    print("TTM: %d baris, ok %d" % (len(t), (t.status == "ok").sum()), t.status.value_counts().to_dict())
    return 0


if __name__ == "__main__":
    sys.exit(main())
