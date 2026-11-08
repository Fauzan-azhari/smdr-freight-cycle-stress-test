"""Data operasional SMDR (Annual Report FY2021-FY2025 dan catatan laporan keuangan): verifikasi dan rekonsiliasi.

Setiap angka pada data/tidy/operating_long.csv membawa halaman dan token teks sebagaimana tercetak. Modul ini
memastikan (1) token benar-benar ada pada halaman yang dikutip, (2) angka sesuai satu sama lain dan dengan laporan
keuangan, dan (3) konflik antar-vintage tercatat, bukan ditimpa.

Jalankan dari root repo:  PYTHONPATH=src .venv/bin/python -m smdr.operating
"""
import os
import re
import sys

import pandas as pd
import pypdf

from . import datapaths
from . import baseline

ROOT = baseline.ROOT


def load():
    return pd.read_csv(datapaths.table("operating_long.csv"))


def _paths():
    m = pd.read_csv(datapaths.table("source_manifest.csv"))
    return {r.source_id: os.path.join(ROOT, r.path_or_url) for r in m.itertuples()}


def _norm(s):
    return re.sub(r"\s+", "", str(s))


def verify_tokens(df):
    """True bila source_token tercetak pada halaman PDF yang dikutip (spasi diabaikan)."""
    paths, cache, ok = _paths(), {}, []
    for r in df.itertuples():
        key = (r.source_id, int(r.pdf_page))
        if key not in cache:
            reader = pypdf.PdfReader(paths[r.source_id])
            cache[key] = _norm(reader.pages[int(r.pdf_page) - 1].extract_text() or "")
        ok.append(_norm(r.source_token) in cache[key])
    return pd.Series(ok, index=df.index)


def _consolidated_revenue():
    fs = pd.read_csv(datapaths.table("fs_long.csv"))
    r = fs[(fs.statement == "IS") & (fs.line_key == "revenue")].set_index("period")["value_usd"]
    return r


def run_checks(df=None, verify=True):
    df = load() if df is None else df
    out = []

    def rec(cid, desc, tested, bad, detail="", status=None):
        out.append({"check_id": cid, "description": desc, "n_tested": tested, "n_fail": len(bad) if hasattr(bad, "__len__") else int(bad),
                    "status": status or ("PASS" if (len(bad) if hasattr(bad, "__len__") else int(bad)) == 0 else "FAIL"), "detail": detail})

    if verify:
        ok = verify_tokens(df)
        bad = df[~ok]
        rec("TOKEN", "token teks tercetak pada halaman yang dikutip", len(df), bad,
            "; ".join("%s %s hal.%s" % (r.metric_key, r.period, r.pdf_page) for r in bad.head(8).itertuples()))

    cons = _consolidated_revenue()
    rs = df[df.domain == "revenue_by_service"].pivot_table(index="period", columns="metric_key", values="value", aggfunc="sum")
    diff = (rs.sum(axis=1) - cons.reindex(rs.index)).abs()
    rec("REVSVC_SUM", "jumlah lima jenis jasa = pendapatan konsolidasi (toleransi USD 1)", len(rs), diff[diff > 1],
        ", ".join("%s: %.0f" % (p, v) for p, v in diff[diff > 1].items()))

    pref = df[(df.domain == "segment_revenue") & (df.series_role == "preferred")].pivot_table(index="period", columns="scope", values="value")
    full = pref.dropna(subset=["shipping", "logistics", "ports", "services"])
    elim = (full.sum(axis=1) / (cons.reindex(full.index) / 1e6) - 1) * 100
    badel = elim[(elim < 0) | (elim > 8)]
    rec("SEG_GROSS", "jumlah empat lini melebihi pendapatan konsolidasi sebesar 0 sampai 8% (eliminasi antar-segmen)", len(elim), badel,
        ", ".join("%s: %.1f%%" % (p, v) for p, v in badel.items()))
    out[-1]["detail"] = out[-1]["detail"] or "; ".join("%s %.1f%%" % (p, v) for p, v in elim.items())

    sh = df[df.domain == "segment_share_reported"]
    bad = []
    for per, g in sh.groupby("period"):
        if per in full.index:
            gross = full.loc[per, ["shipping", "logistics", "ports", "services"]].sum()
            for r in g.itertuples():
                if abs(full.loc[per, r.scope] / gross * 100 - r.value) > 0.15:
                    bad.append((per, r.scope))
    rec("SHARE_GROSS", "pangsa segmen yang dilaporkan = nilai / jumlah gross empat lini (toleransi 0,15 pp)", len(sh), bad)

    gr = df[df.metric_key == "yoy_growth_reported"]
    prior = lambda p: "FY%d" % (int(p[2:]) - 1)
    bad = []
    for r in gr.itertuples():
        if r.scope == "consolidated_revenue":
            a, b = cons[r.period] / 1e6, cons[prior(r.period)] / 1e6
        elif r.scope == "intl_container_volume":
            v = df[(df.metric_key == "container_volume_intl")].set_index("period")["value"]
            a, b = v[r.period], v[prior(r.period)]
            if abs(b * (1 + r.value / 100) - a) > 0.05:  # nilai 2025 dibulatkan satu desimal
                bad.append((r.scope, r.period))
            continue
        else:
            s = pref[r.scope]
            a, b = s[r.period], s[prior(r.period)]
        tol = 0.5 if r.value == round(r.value) else 0.15
        if abs((a / b - 1) * 100 - r.value) > tol:
            bad.append((r.scope, r.period))
    rec("GROWTH", "pertumbuhan yang dilaporkan = pertumbuhan dari nilai yang disimpan", len(gr), bad, "; ".join("%s %s" % x for x in bad))

    fl = df[df.domain == "fleet"].pivot_table(index="period", columns="metric_key", values="value")
    fl = fl.dropna(subset=["fleet_owned", "fleet_chartered_in", "fleet_chartered_out", "fleet_operational_control"])
    bad = fl[(fl.fleet_owned + fl.fleet_chartered_in - fl.fleet_chartered_out) != fl.fleet_operational_control]
    rec("FLEET_ID", "kendali operasional = milik + sewa masuk - sewa keluar", len(fl), bad)

    en = df[(df.domain == "energy") & (df.series_role == "preferred")].pivot_table(index="period", columns="metric_key", values="value")
    bad = en[(en.energy_conventional + en.energy_renewable - en.energy_total).abs() > 0.5]
    rec("ENERGY_SUM", "energi konvensional + terbarukan = total", len(en), bad)

    # --- catatan informasi segmen pada laporan keuangan (diaudit; interim tidak diaudit)
    fs = df[df.domain == "segment_fs"]
    pv = lambda mk: fs[fs.metric_key == mk].pivot_table(index="period", columns="scope", values="value")
    rev, prof, da, geo = pv("fs_segment_revenue"), pv("fs_segment_profit"), pv("fs_segment_da"), pv("fs_revenue_geography")
    d1 = (rev[["shipping_agency", "logistics_ports", "others"]].sum(axis=1) - rev["total_gross"]).abs()
    d2 = (rev["total_gross"] + rev["elimination"] - cons.reindex(rev.index)).abs()
    rec("FS_SEG_SUM", "tiga segmen = total gross; gross + eliminasi = pendapatan konsolidasi (toleransi USD 1)", len(rev), pd.concat([d1[d1 > 1], d2[d2 > 1]]))
    fsd = pd.read_csv(datapaths.table("fs_long.csv"))
    gp = fsd[(fsd.statement == "IS") & (fsd.line_key == "gross_profit")].set_index("period")["value_usd"]
    d3 = (prof[["shipping_agency", "logistics_ports", "others"]].sum(axis=1) - gp.reindex(prof.index)).abs()
    rec("FS_PROFIT", "jumlah laba segmen = laba bruto konsolidasi (toleransi USD 1)", len(prof), d3[d3 > 1])
    ev = pd.read_csv(datapaths.table("evidence.csv"))
    ev = ev[(ev.acceptance_status == "usable") & ev.metric.isin(["cogs_depreciation", "ga_depreciation"])]
    ev = ev.assign(value=pd.to_numeric(ev["value"]))
    dep = ev.pivot_table(index="period", columns="metric", values="value", aggfunc="sum")
    cogs_dep = fsd[(fsd.statement == "COGS_NOTE") & (fsd.line_key == "depreciation")].set_index("period")["value_usd"]
    ga_dep = {"9M26": 1747225.0, "9M25": 1757414.0}
    tot = {}
    for per in da.index:
        c = dep.loc[per, "cogs_depreciation"] if per in dep.index else cogs_dep[per]
        g = dep.loc[per, "ga_depreciation"] if per in dep.index else ga_dep[per]
        tot[per] = c + g
    d4 = (da["consolidated"] - pd.Series(tot)).abs()
    rec("FS_DA", "penyusutan dan amortisasi segmen = penyusutan beban pokok + penyusutan G&A (tidak ada amortisasi terpisah)", len(da), d4[d4 > 1],
        ", ".join("%s: %.0f" % (k, v) for k, v in d4[d4 > 1].items()))
    d5 = (geo.sum(axis=1) - cons.reindex(geo.index)).abs()
    rec("FS_GEO", "pendapatan menurut pasar geografis = pendapatan konsolidasi (toleransi USD 1)", len(geo), d5[d5 > 1])
    ar = df[(df.domain == "segment_revenue") & (df.series_role == "preferred")].pivot_table(index="period", columns="scope", values="value")
    ties = []
    for per in ar.index.intersection(rev.index):
        f = rev.loc[per] / 1e6
        if abs(f["logistics_ports"] - ar.loc[per, "logistics"] - ar.loc[per, "ports"]) > 0.2: ties.append((per, "logistics_ports"))
        if abs(f["others"] - ar.loc[per, "services"]) > 0.1: ties.append((per, "others"))
        if abs(f["shipping_agency"] - ar.loc[per, "shipping"]) > 0.15: ties.append((per, "shipping_agency"))
    rec("FS_TIES_AR", "angka lini pada Annual Report (seri pilihan) = segmen pada laporan keuangan diaudit", len(ar.index.intersection(rev.index)), ties,
        "; ".join("%s %s" % t for t in ties))
    tp = df[(df.metric_key == "port_throughput_total") & (df.source_id == "S3")].set_index("period")["value"]
    g = (tp["FY2024"] / tp["FY2023"] - 1) * 100
    rep = df[(df.metric_key == "port_throughput_growth") & (df.period == "FY2024")]["value"].iloc[0]
    rec("THROUGHPUT_GROWTH", "pertumbuhan throughput 2024 dari angka absolut (dokumen sukuk) = pertumbuhan yang dilaporkan Annual Report 2024 (toleransi 0,1 pp)", 1,
        [] if abs(g - rep) <= 0.1 else [1], "dihitung %.2f%% vs dilaporkan %.1f%%" % (g, rep))
    t25 = df[(df.metric_key == "port_throughput_total") & (df.period == "FY2025")]["value"].iloc[0]
    rec("INFO_THROUGHPUT_2025", "throughput total 2025 menurun terhadap 2024 walau teks menyebut kemitraan baru", 1, 0,
        "%.1f%% (960.000 vs 1.002.723 TEU)" % ((t25 / tp["FY2024"] - 1) * 100), status="INFO")

    fx = df[df.domain == "fx_position"]
    fxp = fx.pivot_table(index="period", columns="metric_key", values="value")
    liab = ["idr_bank_loans", "idr_trade_payables", "idr_long_term_loans", "idr_sukuk"]
    chk = []
    for per in fxp.index:
        if abs(fxp.loc[per, "monetary_assets_total"] - fxp.loc[per, "monetary_liabilities_total"] - fxp.loc[per, "monetary_net"]) > 1:
            chk.append((per, "net"))
        if fxp.loc[per, liab].sum() > fxp.loc[per, "monetary_liabilities_total"] or fxp.loc[per, ["idr_cash", "idr_receivables"]].sum() > fxp.loc[per, "monetary_assets_total"]:
            chk.append((per, "idr_slice"))
    rec("FX_POSITION", "aset - liabilitas moneter = posisi neto; potongan rupiah tidak melebihi total", len(fxp), chk)
    fac = pd.read_csv(datapaths.table("financing_facilities.csv"))
    nominal = {"9M26": fac["nominal_limit"].sum(), "FY2025": fac[fac.facility_id != "S3"]["nominal_limit"].sum()}
    bad = [(k, "nominal") for k, v in nominal.items() if abs(fx[(fx.metric_key == "idr_sukuk_nominal") & (fx.period == k)]["value"].iloc[0] - v) > 1]
    rec("FX_SUKUK_TIE", "nominal sukuk rupiah pada catatan moneter = jumlah seri beredar pada jadwal pendanaan", len(nominal), bad)
    # temuan yang dicatat, bukan galat
    conflicts = df[df.conflict_group_id.notna()].groupby("conflict_group_id")["value"].agg(["min", "max", "count"])
    rec("INFO_VINTAGE", "konflik antar-vintage pada seri segmen (dipertahankan, vintage terbaru ditandai preferred)", len(conflicts), 0,
        "; ".join("%s: %.1f-%.1f" % (k, r["min"], r["max"]) for k, r in conflicts.iterrows()), status="INFO")
    e = en.loc[["FY2024", "FY2025"], "energy_total"]
    rec("INFO_ENERGY_TEXT", "teks laporan 2025 menyebut konsumsi energi menurun, sedangkan tabel naik", 1, 0,
        "tabel: %+.1f%% (FY2025 terhadap FY2024)" % ((e["FY2025"] / e["FY2024"] - 1) * 100), status="INFO")
    return pd.DataFrame(out)


def main():
    res = run_checks()
    res.to_csv(datapaths.table("operating_checks.csv"), index=False)
    n = res.status.value_counts().to_dict()
    print("%d cek: %s" % (len(res), ", ".join("%s %d" % (k, v) for k, v in n.items())))
    for r in res.itertuples():
        if r.status != "PASS":
            print("  %-5s %-18s n=%-3d gagal=%-3d %s" % (r.status, r.check_id, r.n_tested, r.n_fail, r.detail[:200]))
    return 1 if n.get("FAIL") else 0


if __name__ == "__main__":
    sys.exit(main())
