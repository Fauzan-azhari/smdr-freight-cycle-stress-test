"""Rasio covenant sukuk pada tanggal uji tahunan (versi ringan, keputusan D05; sewa dihitung, D08).

Klausul (S1 PDF38, S2 PDF33, S3 PDF30), diuji pada laporan tahunan konsolidasian yang diaudit:
  - utang berbunga/bagi hasil / total ekuitas  <= 2,5x
  - EBITDA / (bagian lancar liabilitas jangka panjang berbunga + beban bunga)  >= 1,10x
    EBITDA = laba operasi + depresiasi + amortisasi

Klausul tidak menyebut sewa. Ukuran utama (keputusan D08) menghitung bagian lancar sewa pada penyebut dan
seluruh sewa pada utang berbunga. Kolom *_ex_lease dipertahankan hanya untuk jejak audit dan analisis
sensitivitas. Hasil berlabel proforma_conditional: bukan sertifikat kepatuhan dan bukan pernyataan pelanggaran.
"""
import numpy as np
import pandas as pd

from . import datapaths
from . import baseline

THRESHOLD_COVER = 1.10
THRESHOLD_DER = 2.5
LABEL = "proforma_conditional"


def ebitda_proxy(w, period):
    """EBITDA legacy: laba bruto - G&A + depresiasi pada beban pokok (tanpa depresiasi G&A)."""
    g = lambda s, k: w.loc[(s, k), period]
    return g("IS", "gross_profit") - g("IS", "ga_expense") + g("COGS_NOTE", "depreciation")


def ebitda_operating(w, period):
    """EBITDA operasi definisi final: EBIT + penyusutan biaya jasa + penyusutan G&A, keduanya dari bukti PDF
    berstatus usable (keputusan D01). Gagal bila bukti untuk periode itu tidak ada atau ganda."""
    ev = baseline.load_evidence()
    ev = ev[(ev["period"] == period) & (ev["acceptance_status"] == "usable")]
    pick = lambda metric: ev.loc[ev["metric"] == metric, "value"]
    cogs_dep, ga_dep = pick("cogs_depreciation"), pick("ga_depreciation")
    if len(cogs_dep) != 1 or len(ga_dep) != 1:
        raise ValueError("bukti penyusutan %s tidak tunggal atau tidak ada: cogs=%d ga=%d" % (period, len(cogs_dep), len(ga_dep)))
    ebit = w.loc[("IS", "gross_profit"), period] - w.loc[("IS", "ga_expense"), period]
    return ebit + float(cogs_dep.iloc[0]) + float(ga_dep.iloc[0])


def ebitda_pdf_fy2025(w):
    """EBITDA operasi FY2025 basis PDF audit (keputusan D01): EBIT + penyusutan biaya jasa + penyusutan G&A."""
    ev = baseline.load_evidence()
    ebit = w.loc[("IS", "gross_profit"), "FY2025"] - w.loc[("IS", "ga_expense"), "FY2025"]
    return ebit + baseline.ev_value(ev, "EV-LK25-COGS-DEP-PDF") + baseline.ev_value(ev, "EV-LK25-GA-DEP")


def clause_band(w, ebitda, include_proposed=False):
    """ebitda: dict periode -> EBITDA (USD penuh). Baris n.d. hanya diisi nol lewat aturan bernama."""
    statuses = ("approved", "proposed") if include_proposed else ("approved",)
    rules = baseline.load_zero_fill(statuses)
    rows = []
    for p, e in ebitda.items():
        used = []

        def g(k):
            v = w.loc[("BS", k), p]
            if pd.isna(v) and ("BS", k, p) in rules:
                rid, fill = rules[("BS", k, p)]
                used.append(rid)
                return fill
            return v

        interest = w.loc[("IS", "finance_expense"), p]
        cur = g("bank_long_term_current") + g("sukuk_current")
        lease_cur, lease_lt = g("lease_current"), g("lease_long_term")
        debt = g("bank_short_term") + g("bank_long_term_current") + g("bank_long_term") + g("sukuk_current") + g("sukuk_long_term")
        equity = w.loc[("BS", "total_equity"), p]
        rows.append({
            "period": p, "ebitda": e, "current_portion": cur, "lease_current": lease_cur, "interest": interest,
            "cover": e / (cur + lease_cur + interest), "headroom": e / (cur + lease_cur + interest) - THRESHOLD_COVER,
            "der": (debt + lease_cur + lease_lt) / equity,
            "cover_ex_lease": e / (cur + interest), "der_ex_lease": debt / equity,  # hanya audit/sensitivitas
            "zero_fill_rules": ",".join(sorted(set(used))),
            "uses_unapproved_rule": any(rules_status(r) != "approved" for r in used),
            "status": LABEL,
        })
    return pd.DataFrame(rows)


def rules_status(rule_id):
    df = pd.read_csv(datapaths.table("zero_fill_rules.csv")).set_index("rule_id")
    return df.loc[rule_id, "status"]
