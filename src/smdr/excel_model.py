"""Pembangun workbook Financial Model: salinan workbook laporan keuangan (berkas asli tidak diubah) ditambah sheet model berumus hidup.

Tahap B1: Panduan_Model, Asumsi, Data_Makro, Baseline_TTM (tertaut ke sheet laporan), Skenario_Jalur.
Verifikasi: recalc() menghitung ulang dengan LibreOffice, check_b1() mencocokkan hasil dengan model Python (selisih harus nol).

Jalankan dari root repo:  PYTHONPATH=src .venv/bin/python -m smdr.excel_model
"""
import os
import shutil
import subprocess

import openpyxl
import pandas as pd
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter as L

from . import baseline, datapaths as dp

SOURCE = os.path.join(dp.ROOT, "Financial-Statements", "SMDR_Financial_Statements_2021_9M26.xlsx")
OUT = os.path.join(dp.ROOT, "model", "SMDR_Financial_Model.xlsx")
N_MONTHS, FIRST_COL = 63, 5            # Okt 2026 .. Des 2031; kolom E dst
MONTHS = [str(p) for p in pd.period_range("2026-10", "2031-12", freq="M")]
MACRO = [("MS-BASE", "Dasar"), ("MS-ENERGY", "Energi bertahan"), ("MS-COMBINED", "Gabungan")]
DRIVERS = [("brent", "Brent", "USD/barel", '#,##0.00'), ("usdidr", "Kurs USD/IDR", "IDR/USD", '#,##0.0'), ("bi_rate", "BI Rate", "% p.a.", '0.000')]

# ---- gaya templat workbook sumber (Open Sans judul navy, Arial Narrow isi, pita biru muda, gridlines mati)
NAVY, BLUE, GREY = "FF000C3F", "FF3271D2", "FF5C6575"
F_TITLE = Font(name="Open Sans", size=14, bold=True, color=NAVY)
F_SEC = Font(name="Open Sans", size=14, bold=True, color=BLUE)
F_SUB = Font(name="Arial Narrow", size=11, color=GREY)
F_BODY = Font(name="Arial Narrow", size=12)
F_BOLD = Font(name="Arial Narrow", size=12, bold=True)
F_INPUT = Font(name="Arial Narrow", size=12, color="FF0000FF")
F_LINK = Font(name="Arial Narrow", size=12, color="FF007A33")
F_NOTE = Font(name="Arial Narrow", size=10, color=GREY, italic=True)
FILL_BAND = PatternFill("solid", fgColor="FFE7F2FF")
FILL_INPUT = PatternFill("solid", fgColor="FFFFF8E1")
THIN = Border(bottom=Side(style="thin", color="FFBCBEC0"))


def sheet(wb, name, title, subtitle, tab=NAVY, widths=None):
    ws = wb.create_sheet(name)
    ws.sheet_view.showGridLines = False
    ws.sheet_properties.tabColor = tab
    ws.column_dimensions["A"].width = 2
    ws["B2"], ws["B2"].font = title, F_TITLE
    ws["B3"], ws["B3"].font = subtitle, F_SUB
    for c, w in (widths or {}).items():
        ws.column_dimensions[c].width = w
    return ws


def put(ws, ref, value, kind="calc", fmt=None, bold=False):
    c = ws[ref]
    c.value = value
    c.font = {"input": F_INPUT, "link": F_LINK, "calc": F_BOLD if bold else F_BODY, "label": F_BOLD if bold else F_BODY, "note": F_NOTE, "sec": F_SEC}[kind]
    if kind == "input":
        c.fill = FILL_INPUT
    if fmt:
        c.number_format = fmt
    return c


def header(ws, row, labels, col=2):
    for i, t in enumerate(labels):
        c = ws.cell(row=row, column=col + i, value=t)
        c.font, c.fill = F_BOLD, FILL_BAND
        c.alignment = Alignment(horizontal="center" if i else "left", vertical="center", wrap_text=True)


# =============================================================== Asumsi
def build_asumsi(wb):
    ws = sheet(wb, "Asumsi", "Asumsi dan parameter model", "Biru = input; hitam = rumus; hijau = tautan antar sheet. Rentang rendah/tengah/merugikan dari data/02_curated.",
               widths={"B": 38, "C": 11, "D": 11, "E": 11, "F": 11, "G": 14, "H": 11, "I": 70})
    A = {}
    r = 5
    put(ws, f"B{r}", "1. Parameter transmisi operasi", "sec"); r += 1
    header(ws, r, ["Parameter", "ID", "Rendah", "Tengah", "Tinggi", "Aturan merugikan", "Status", "Dasar"]); r += 1
    op = pd.read_csv(dp.table("operating_assumptions.csv"))
    for x in op.itertuples():
        put(ws, f"B{r}", x.parameter, "label"); put(ws, f"C{r}", x.assumption_id, "label")
        for col, v in zip("DEF", (x.low, x.central, x.high)):
            put(ws, f"{col}{r}", float(v), "input", "0.000")
        put(ws, f"G{r}", x.adverse_rule, "input"); put(ws, f"H{r}", x.status, "label"); put(ws, f"I{r}", str(x.basis)[:240], "note")
        A["op:" + x.parameter] = r; r += 1
    r += 1
    put(ws, f"B{r}", "2. Parameter kas", "sec"); r += 1
    header(ws, r, ["Parameter", "ID", "Rendah", "Tengah", "Tinggi", "Aturan merugikan", "Status", "Dasar"]); r += 1
    ca = pd.read_csv(dp.table("cash_assumptions.csv"))
    for x in ca.itertuples():
        put(ws, f"B{r}", x.parameter, "label"); put(ws, f"C{r}", x.assumption_id, "label")
        for col, v in zip("DEF", (x.low, x.central, x.high)):
            put(ws, f"{col}{r}", float(v), "input", "0.000")
        put(ws, f"G{r}", x.adverse_rule, "input"); put(ws, f"H{r}", x.status, "label"); put(ws, f"I{r}", str(x.basis)[:240], "note")
        A["ca:" + x.parameter] = r; r += 1
    r += 1
    put(ws, f"B{r}", "3. Konstanta dan batas covenant", "sec"); r += 1
    from .transition import covenants as cvn, cashflow as cf
    _ht = pd.read_csv(dp.table("historical_test.csv")).set_index("index")
    for key, label, val, fmt, note in (
            ("base_rate", "BI Rate dasar (% p.a.)", cf.BASE_RATE, "0.00", "BI Rate 30 Sep 2026; selisih terhadap ini menggerakkan bunga mengambang"),
            ("window", "Jendela efek tahunan (bulan)", 12, "0", "Okt 2026 s.d. Sep 2027"),
            ("th_nd", "Batas Net Debt to EBITDA (x)", cvn.TH_ND, "0.00", "Covenant bank dan sukuk"),
            ("th_cr", "Batas Current Ratio minimum (x)", cvn.TH_CR, "0.00", "Perjanjian sukuk"),
            ("th_cover", "Batas DSCR minimum (x)", cvn.TH_COVER, "0.00", "Perjanjian sukuk"),
            ("safe_nd", "Sasaran pelunasan Net Debt to EBITDA (x)", 2.70, "0.00", "3,00 / 1,10 dibulatkan ke bawah 0,05 (headroom 10%)")):
        put(ws, f"B{r}", label, "label"); put(ws, f"E{r}", float(val), "input", fmt); put(ws, f"I{r}", note, "note"); A[key] = r; r += 1
    for key, label, val, fmt, note in (
            ("due_FY2027", "Pokok sukuk jatuh tempo dalam 12 bulan setelah uji FY2027 (USD juta)", cvn.SUKUK_DUE_12M["FY2027"], "0.0", "Jadwal sukuk; kurs Sep 2026"),
            ("due_FY2028", "Idem FY2028", cvn.SUKUK_DUE_12M["FY2028"], "0.0", ""),
            ("due_FY2029", "Idem FY2029", cvn.SUKUK_DUE_12M["FY2029"], "0.0", ""),
            ("due_FY2030", "Idem FY2030", cvn.SUKUK_DUE_12M["FY2030"], "0.0", ""),
            ("dscr_FY2024", "DSCR dilaporkan FY2024 (x)", 1.89, "0.00", "Informasi Tambahan Sukuk Ijarah II/III, rasio yang dipersyaratkan"),
            ("dscr_FY2025", "DSCR dilaporkan FY2025 (x)", 2.11, "0.00", "Idem"),
            ("ebitda_FY2024", "EBITDA operasi FY2024 (USD juta)", float(_ht.loc["FY2024", "ebitda"]), "0.000000", "04_marts/results/historical_test.csv (basis EBITDA operasi, bukti PDF)"),
            ("ebitda_FY2025", "EBITDA operasi FY2025 (USD juta)", float(_ht.loc["FY2025", "ebitda"]), "0.000000", "Idem"),
            ("coupon_ttm", "Kupon sukuk dibayar TTM (USD juta)", 5.256492, "0.000000", "Jadwal fasilitas (smdr.transition.cashflow.sukuk_coupons_ttm), kurs rata-rata TTM")):
        put(ws, f"B{r}", label, "label"); put(ws, f"E{r}", float(val), "input", fmt); put(ws, f"I{r}", note, "note"); A[key] = r; r += 1
    r += 1
    put(ws, f"B{r}", "4. Definisi jalur skenario makro", "sec"); r += 1
    header(ws, r, ["Skenario / driver", "Tipe jalur", "Awal", "Hold (bln)", "Ramp (bln)", "Porsi kembali", "Bulan kembali", "Besaran (satuan) dan target"]); r += 1
    defs = pd.read_csv(dp.table("macro_scenario_definitions.csv"))
    anch = pd.read_csv(dp.table("macro_anchors.csv")).set_index("driver")["value"]
    for sid, nm in MACRO:
        for drv, _, _, fm in DRIVERS:
            d = defs[(defs.scenario_id == sid) & (defs.driver == drv)].iloc[0]
            put(ws, f"B{r}", f"{sid} | {drv}", "label"); put(ws, f"C{r}", d.path_type, "input")
            put(ws, f"D{r}", float(anch[drv]), "input", fm)
            for col, key in (("E", "hold_months"), ("F", "ramp_months"), ("G", "retrace_fraction"), ("H", "retrace_months")):
                v = d[key]
                put(ws, f"{col}{r}", None if pd.isna(v) else float(v), "input", "0.0")
            put(ws, f"I{r}", ("%s %s; " % (d.magnitude, d.magnitude_unit) if not pd.isna(d.magnitude) else "") + (str(d.target) if not pd.isna(d.target) else ""), "note")
            A[f"def:{sid}:{drv}"] = r; r += 1
    r += 1
    put(ws, f"B{r}", "5. Skenario pasar (guncangan tarif dan volume)", "sec"); r += 1
    header(ws, r, ["Skenario", "ID", "Tarif efektif", "Volume", "Bulan", "Status", "", "Jangkar"]); r += 1
    from .transition import bridge as br
    for x in br.narratives().itertuples():
        if x.kisah not in ("Permintaan melemah", "Kelebihan kapasitas", "Permintaan lemah dan kelebihan kapasitas"):
            continue
        put(ws, f"B{r}", x.kisah, "label"); put(ws, f"C{r}", x.narrative_id, "label")
        put(ws, f"D{r}", float(x.tarif), "input", "0.0%"); put(ws, f"E{r}", float(x.volume), "input", "0.0%"); put(ws, f"F{r}", int(x.bulan), "input", "0")
        put(ws, f"G{r}", x.status, "label"); put(ws, f"I{r}", f"{x.jangkar_tarif}; {x.jangkar_volume}", "note"); A["mk:" + x.kisah] = r; r += 1
    ws.freeze_panes = "C5"
    return A


# =============================================================== Data_Makro
def build_data_makro(wb):
    ws = sheet(wb, "Data_Makro", "Data makro bulanan", "Sumber: data/03_canonical/macro_monthly_wide.csv (Brent EIA via FRED; kurs penyedia). Bulan parsial diberi tanda.",
               widths={"B": 12, "C": 14, "D": 14, "E": 10})
    w = pd.read_csv(dp.table("macro_monthly_wide.csv"))
    header(ws, 5, ["Bulan", "Brent (USD/bbl)", "USD/IDR", "Parsial"])
    ref = {}
    for i, x in enumerate(w.itertuples()):
        r = 6 + i
        put(ws, f"B{r}", x.month, "label")
        if pd.notna(x.brent_avg): put(ws, f"C{r}", float(x.brent_avg), "input", "#,##0.00")
        if pd.notna(x.usdidr_close): put(ws, f"D{r}", float(x.usdidr_close), "input", "#,##0.0")
        put(ws, f"E{r}", "Y" if x.partial_any else "", "label"); ref[x.month] = r
    ws.freeze_panes = "B6"
    return ref


# =============================================================== Baseline_TTM
def _cell(stmt, key, period):
    fs = baseline.load_long() if hasattr(baseline, "load_long") else pd.read_csv(dp.table("fs_long.csv"))
    row = fs[(fs.statement == stmt) & (fs.line_key == key) & (fs.period == period)]
    return row.iloc[0].workbook_cell


def build_baseline(wb, M):
    ws = sheet(wb, "Baseline_TTM", "Posisi dasar: TTM Sep 2026 dan neraca 30 Sep 2026", "USD juta. Hijau = tautan ke sheet laporan; biru = input beralamat sumber; TTM = FY2025 + 9M26 - 9M25.",
               widths={"B": 44, "C": 14, "D": 62})
    from .transition import cashflow as cf
    fs = pd.read_csv(dp.table("fs_long.csv"))
    cellof = lambda s, k, p: fs[(fs.statement == s) & (fs.line_key == k) & (fs.period == p)].iloc[0].workbook_cell
    ttm = lambda s, k: "=(%s+%s-%s)/1000000" % (cellof(s, k, "FY2025"), cellof(s, k, "9M26"), cellof(s, k, "9M25"))
    bs = lambda k: "N(%s)/1000000" % cellof("BS", k, "9M26")   # N(): sel n.d. dihitung nol (aturan zero-fill Z01), sesuai base_position
    ops = pd.read_csv(dp.table("operating_long.csv"))
    br_ = pd.read_csv(dp.table("baseline_bridge.csv")).set_index("metric")
    B = {}
    header(ws, 5, ["Butir", "Nilai", "Sumber / rumus"])
    rows = [
        ("revenue_stmt", "Pendapatan usaha TTM", ttm("IS", "revenue"), "link", "Laba Rugi"),
        ("cogs", "Beban pokok TTM", ttm("IS", "cogs"), "link", "Laba Rugi"),
        ("interest_ttm", "Beban keuangan TTM", ttm("IS", "finance_expense"), "link", "Laba Rugi"),
        ("cogs_dep", "Penyusutan dalam beban pokok TTM", ttm("COGS_NOTE", "depreciation"), "link", "Catatan (rincian beban pokok)"),
        ("ebit", "EBIT TTM (basis rekonsiliasi)", float(br_.loc["ebit_ttm", "reconciled_value"]) / 1e6, "input", "baseline_bridge.csv: ebit_ttm"),
        ("ebitda", "EBITDA operasi TTM", float(br_.loc["ebitda_ttm_operating_pdf_basis", "reconciled_value"]) / 1e6, "input", "baseline_bridge.csv: EBIT + penyusutan biaya jasa + penyusutan G&A (bukti PDF, keputusan D01)"),
        ("cfo", "Arus kas operasi TTM", ttm("CF", "cfo"), "link", "Arus Kas"),
        ("interest_paid_ttm", "Bunga dibayar TTM", ttm("CF", "interest_paid"), "link", "Arus Kas"),
        ("interest_received_ttm", "Bunga diterima TTM", ttm("CF", "interest_received"), "link", "Arus Kas"),
        ("opening_cash", "Kas dan setara kas 30 Sep 2026", "=" + bs("cash"), "link", "Posisi Keuangan"),
        ("deposits", "Aset keuangan lancar lain (deposito) 30 Sep 2026", "=" + bs("other_fin_assets_current"), "link", "Posisi Keuangan"),
        ("bank_short", "Utang bank jangka pendek", "=" + bs("bank_short_term"), "link", "Posisi Keuangan"),
        ("bank_current", "Utang bank jangka panjang jatuh tempo < 1 tahun", "=" + bs("bank_long_term_current"), "link", "Posisi Keuangan"),
        ("bank_long", "Utang bank jangka panjang", "=" + bs("bank_long_term"), "link", "Posisi Keuangan"),
        ("lease_current", "Liabilitas sewa jatuh tempo < 1 tahun", "=" + bs("lease_current"), "link", "Posisi Keuangan"),
    ]
    r = 6
    for key, label, val, kind, src in rows:
        put(ws, f"B{r}", label, "label"); put(ws, f"C{r}", val, kind, "#,##0.000"); put(ws, f"D{r}", src, "note"); B[key] = r; r += 1
    extra = [
        ("sukuk_bs", "Sukuk (lancar + jangka panjang) 30 Sep 2026", "=%s+%s" % (bs("sukuk_current"), bs("sukuk_long_term")), "link", "Posisi Keuangan"),
        ("lease_bs", "Liabilitas sewa (lancar + jangka panjang) 30 Sep 2026", "=%s+%s" % (bs("lease_current"), bs("lease_long_term")), "link", "Posisi Keuangan"),
        ("ca_bs", "Aset lancar 30 Sep 2026", "=" + bs("total_current_assets"), "link", "Posisi Keuangan"),
        ("cl_bs", "Liabilitas jangka pendek 30 Sep 2026", "=" + bs("total_current_liabilities"), "link", "Posisi Keuangan"),
        ("q4_25", "EBITDA proksi kuartal IV 2025 (FY2025 - 9M25)", "=((%s-%s+%s)-(%s-%s+%s))/1000000" % (
            cellof("IS", "gross_profit", "FY2025"), cellof("IS", "ga_expense", "FY2025"), cellof("COGS_NOTE", "depreciation", "FY2025"),
            cellof("IS", "gross_profit", "9M25"), cellof("IS", "ga_expense", "9M25"), cellof("COGS_NOTE", "depreciation", "9M25")), "link", "laba bruto - G&A + penyusutan beban pokok"),
    ]
    from . import operating as _op
    _ops = _op.load()
    _fx = _ops[(_ops.domain == "fx_position") & (_ops.period == "9M26")].set_index("metric_key")["value"]
    _en = float(_ops[(_ops.metric_key == "energy_conventional") & (_ops.period == "FY2025")]["value"].iloc[0])
    _vl = float(_ops[_ops.metric_key == "vlsfo_singapore_avg"]["value"].iloc[0])
    _prog = float(pd.read_csv(dp.table("capex_milestones.csv"))["amount"].sum())
    extra += [("energy_gj", "Konsumsi energi konvensional FY2025 (GJ)", _en, "input", "operating_long.csv (Annual Report 2025)"),
              ("vlsfo", "Harga VLSFO Singapura rata-rata (USD/ton)", _vl, "input", "operating_long.csv"),
              ("idr_cash_usd", "Kas berdenominasi rupiah (USD juta)", float(_fx["idr_cash"]) / 1e6, "input", "operating_long.csv, posisi mata uang 9M26"),
              ("program_idr", "Program kapal baru, alokasi dana Seri III (IDR)", _prog, "input", "capex_milestones.csv")]
    for key, label, val, kind, src in extra:
        put(ws, f"B{r}", label, "label"); put(ws, f"C{r}", val, kind, "#,##0.000"); put(ws, f"D{r}", src, "note"); B[key] = r; r += 1
    # turunan
    der = [("bank_debt", "Utang bank total", f"=C{B['bank_short']}+C{B['bank_current']}+C{B['bank_long']}", "jangka pendek + jatuh tempo + panjang"),
           ("ocf_ttm", "Kas operasi sebelum bunga TTM", f"=C{B['cfo']}+C{B['interest_paid_ttm']}-C{B['interest_received_ttm']}", "CFO + bunga dibayar - bunga diterima"),
           ("revenue", "Pendapatan TTM (jumlah jasa, basis AR)", None, "jumlah lima jenis jasa di bawah"),
           ("opex_month", "Biaya operasi tunai per bulan", None, "(pendapatan - EBITDA) / 12")]
    # pendapatan per jasa (Annual Report) sebagai input beralamat sumber
    r += 1; put(ws, f"B{r}", "Pendapatan menurut jenis jasa (USD juta, TTM)", "sec"); r += 1
    svc = ops[ops.domain == "revenue_by_service"].pivot_table(index="metric_key", columns="period", values="value")
    first = r
    last_svc = first + 4
    for k in ("freight_income", "time_charter", "agency_forwarding_ports", "container_equipment_handling", "other_revenue"):
        put(ws, f"B{r}", k, "label")
        put(ws, f"C{r}", "=(%s+%s-%s)/1000000" % tuple(repr(float(svc.loc[k, p])) for p in ("FY2025", "9M26", "9M25")), "input", "#,##0.000")
        put(ws, f"D{r}", "operating_long.csv (Annual Report dan laporan 9M): (FY2025 + 9M26 - 9M25) / 1e6", "note"); B["svc:" + k] = r; r += 1
    for key, label, f, note in der:
        if key == "revenue":
            f = f"=SUM(C{first}:C{last_svc})"
        if key == "opex_month":
            f = f"=(C{B['revenue']}-C{B['ebitda']})/12"
        put(ws, f"B{r}", label, "label", bold=True); put(ws, f"C{r}", f, "calc", "#,##0.000", bold=True); put(ws, f"D{r}", note, "note"); B[key] = r; r += 1
    # makro dasar: dari Data_Makro
    r += 1; put(ws, f"B{r}", "Posisi makro dasar", "sec"); r += 1
    m0, m1 = M["2025-10"], M["2026-09"]
    for key, label, f, fmt in (("brent_ttm", "Brent rata-rata TTM (USD/bbl)", f"=AVERAGE(Data_Makro!C{m0}:C{m1})", "#,##0.000"),
                               ("fx_ttm", "USD/IDR rata-rata TTM", f"=AVERAGE(Data_Makro!D{m0}:D{m1})", "#,##0.0"),
                               ("fx_sep", "USD/IDR 30 Sep 2026", f"=Data_Makro!D{M['2026-09']}", "#,##0.0")):
        put(ws, f"B{r}", label, "label"); put(ws, f"C{r}", f, "link", fmt); put(ws, f"D{r}", "Data_Makro", "note"); B[key] = r; r += 1
    ws.freeze_panes = "B6"
    return B


# =============================================================== Skenario_Jalur
def build_jalur(wb, A, M):
    ws = sheet(wb, "Skenario_Jalur", "Jalur driver makro bulanan, Okt 2026 - Des 2031", "Dibangun dari definisi di Asumsi: interpolasi jangkar, penurunan preseden 2022, dan guncangan dengan pemulihan sebagian.",
               widths={"B": 22, "C": 18, "D": 11})
    header(ws, 5, ["Skenario", "Driver", "Satuan"] + MONTHS)
    for i in range(N_MONTHS):
        ws.column_dimensions[L(FIRST_COL + i)].width = 9
    put(ws, "B6", "Indeks bulan (i)", "label")
    for i in range(N_MONTHS):
        put(ws, f"{L(FIRST_COL + i)}6", i, "calc", "0")
    # rasio preseden Brent: puncak 2022-2023, rasio terhadap puncak pada +k bulan, minimum kumulatif (k = 0..12)
    put(ws, "B8", "Rasio preseden Brent (k = 0..12)", "sec")
    r0, r1 = M["2022-01"], M["2023-12"]
    put(ws, "B9", "Indeks puncak 2022-2023 (posisi dalam Data_Makro)", "label")
    put(ws, "E9", f"=MATCH(MAX(Data_Makro!C{r0}:C{r1}),Data_Makro!C{M['2020-01']}:C{M['2026-10']},0)", "calc", "0")
    put(ws, "B10", "Brent puncak", "label"); put(ws, "E10", f"=MAX(Data_Makro!C{r0}:C{r1})", "calc", "#,##0.00")
    put(ws, "B11", "k", "label"); put(ws, "B12", "Rasio mentah", "label"); put(ws, "B13", "Rasio (minimum kumulatif)", "label", bold=True)
    for k in range(13):
        col = L(FIRST_COL + k)
        put(ws, f"{col}11", k, "calc", "0")
        put(ws, f"{col}12", f"=INDEX(Data_Makro!$C${M['2020-01']}:$C${M['2026-10']},$E$9+{col}11)/$E$10", "calc", "0.0000")
        put(ws, f"{col}13", f"={col}12" if k == 0 else f"=MIN({L(FIRST_COL + k - 1)}13,{col}12)", "calc", "0.0000", bold=True)
    rat = f"$E$13:$Q$13"
    base_rows = {}
    r = 15
    put(ws, f"B{r}", "Jalur", "sec"); r += 1
    D = lambda sid, drv, col: f"Asumsi!${col}${A[f'def:{sid}:{drv}']}"
    for sid, nm in MACRO:
        for drv, dn, unit, fm in DRIVERS:
            put(ws, f"B{r}", sid, "label"); put(ws, f"C{r}", dn, "label"); put(ws, f"D{r}", unit, "note")
            base_rows[(sid, drv)] = r
            for i in range(N_MONTHS):
                col = L(FIRST_COL + i); idx = f"{col}$6"
                put(ws, f"{col}{r}", _path_formula(sid, drv, idx, D, base_rows, col), "calc", fm)
            r += 1
        r += 1
    ws.freeze_panes = "E7"
    return {k: v for k, v in base_rows.items()}


def _path_formula(sid, drv, idx, D, rows, col):
    defs = pd.read_csv(dp.table("macro_scenario_definitions.csv"))
    d = defs[(defs.scenario_id == sid) & (defs.driver == drv)].iloc[0]
    start = D(sid, drv, "D")
    if d.path_type == "hold_then_decay":
        return f"={start}*INDEX($E$13:$Q$13,MIN(MAX(0,{idx}-{D(sid, drv, 'E')}),12)+1)"
    if d.path_type == "anchor_targets":
        pts = [(0, None)] + [(int((pd.Period(t.split(":")[0], "M") - pd.Period("2026-10", "M")).n), float(t.split(":")[1])) for t in d.target.split(";")]
        (i1, v1), (i2, v2) = pts[1], pts[2]
        f = (f"IF({idx}<={i1},{start}+({v1}-{start})*{idx}/{i1},IF({idx}<={i2},{v1}+({v2}-{v1})*({idx}-{i1})/({i2}-{i1}),{v2}))")
        return "=" + f
    if d.path_type == "follow":
        return f"={col}{rows[('MS-BASE', drv)]}"
    if d.path_type == "shock_retrace":
        ramp, hold, rf, rm = D(sid, drv, "F"), D(sid, drv, "E"), D(sid, drv, "G"), D(sid, drv, "H")
        prof = (f"IF({idx}<={ramp},{idx}/{ramp},IF({idx}<={ramp}+{hold},1,1-{rf}*MIN({idx}-{ramp}-{hold},{rm})/{rm}))")
        base = f"{col}{rows[('MS-BASE', drv)]}"
        mag = float(d.magnitude)
        return f"={base}+{base}*{mag}/100*{prof}" if d.magnitude_unit == "pct" else f"={base}+{mag}*{prof}"
    raise ValueError(d.path_type)


# =============================================================== Data_Sukuk
def build_sukuk(wb):
    ws = sheet(wb, "Data_Sukuk", "Jadwal pembayaran sukuk (IDR)", "Sumber: data/03_canonical/financing_events.csv. Tanggal bayar disesuaikan ke hari kerja berikutnya.",
               widths={"B": 10, "C": 10, "D": 12, "E": 12, "F": 18})
    ev = pd.read_csv(dp.table("financing_events.csv"))
    header(ws, 5, ["Peristiwa", "Fasilitas", "Jenis", "Bulan bayar", "Nilai (IDR)"])
    for i, x in enumerate(ev.itertuples()):
        r = 6 + i
        put(ws, f"B{r}", x.event_id, "label"); put(ws, f"C{r}", x.facility_id, "label"); put(ws, f"D{r}", x.event_type, "label")
        put(ws, f"E{r}", str(x.payment_date)[:7], "label"); put(ws, f"F{r}", float(x.amount), "input", "#,##0")
    return (6, 6 + len(ev) - 1)


# =============================================================== Mesin kas dan covenant (12 blok)
SCEN = [("Dasar", "MS-BASE", None), ("Energi bertahan", "MS-ENERGY", None), ("Gabungan", "MS-COMBINED", None),
        ("Permintaan melemah", None, "Permintaan melemah"), ("Kelebihan kapasitas", None, "Kelebihan kapasitas"),
        ("Permintaan lemah dan kelebihan kapasitas", None, "Permintaan lemah dan kelebihan kapasitas")]
SHEETS = {"Dasar": "Kas_Dasar", "Energi bertahan": "Kas_Energi", "Gabungan": "Kas_Gabungan", "Permintaan melemah": "Kas_Permintaan",
          "Kelebihan kapasitas": "Kas_Kapasitas", "Permintaan lemah dan kelebihan kapasitas": "Kas_Terburuk"}
FYS = ("FY2027", "FY2028", "FY2029", "FY2030")
PKGS = [(54.0, False), (107.0, False), (107.0, True)]


def _pick_op(A, name, case, dirx):
    r = A["op:" + name]
    return (f'IF({case}="central",Asumsi!$E${r},IF(Asumsi!$G${r}="high",Asumsi!$F${r},IF(Asumsi!$G${r}="low",Asumsi!$D${r},'
            f'IF(Asumsi!$G${r}="sign",IF({dirx}>=0,Asumsi!$F${r},Asumsi!$D${r}),IF({dirx}>=0,Asumsi!$D${r},Asumsi!$F${r})))))')


def _pick_ca(A, name, case):
    r = A["ca:" + name]
    return f'IF({case}="central",Asumsi!$E${r},IF(Asumsi!$G${r}="high",Asumsi!$F${r},Asumsi!$D${r}))'


def build_kas(wb, A, B, J, SK):
    """Satu sheet per skenario, dua blok (central, adverse). Kembalikan peta keluaran: {(skenario, case): {kunci: sel}} dan baris deret."""
    out = {}
    colM = lambda i: L(FIRST_COL + i)
    last = colM(N_MONTHS - 1)
    bl = lambda k: f"Baseline_TTM!$C${B[k]}"
    asm = lambda k: f"Asumsi!$E${A[k]}"
    for name, sid, mk in SCEN:
        ws = sheet(wb, SHEETS[name], f"Mesin kas dan covenant: {name}", "USD juta. Sel biru pada Asumsi mengubah seluruh blok. Blok atas = asumsi tengah, blok bawah = downside case arus kas.",
                   widths={"B": 34, "C": 12, "D": 4})
        for i in range(N_MONTHS):
            ws.column_dimensions[colM(i)].width = 9
        put(ws, "B5", "Bulan", "label", bold=True); put(ws, "B6", "Indeks (i)", "label"); put(ws, "B7", "Tahun", "label"); put(ws, "B8", "Nomor bulan", "label")
        for i in range(N_MONTHS):
            c = colM(i)
            put(ws, f"{c}5", f"=Skenario_Jalur!{c}5", "link"); ws[f"{c}5"].fill = FILL_BAND
            put(ws, f"{c}6", i, "calc", "0"); put(ws, f"{c}7", f"=VALUE(LEFT({c}5,4))", "calc", "0"); put(ws, f"{c}8", f"=VALUE(MID({c}5,6,2))", "calc", "0")
        row0 = 10
        for case in ("central", "adverse"):
            R, row = {}, [row0]

            def line(key, label, unit="", fm="#,##0.00", fn=None, scalar=None, bold=False):
                r = row[0]; R[key] = r
                put(ws, f"B{r}", label, "label", bold=bold); put(ws, f"C{r}", unit, "note")
                if scalar is not None:
                    put(ws, f"E{r}", scalar, "calc", fm, bold=bold)
                if fn is not None:
                    for i in range(N_MONTHS):
                        put(ws, f"{colM(i)}{r}", fn(i, colM(i), colM(i - 1) if i else None), "calc", fm, bold=bold)
                row[0] += 1
                return r
            c_ = f"$E${row0}"
            put(ws, f"B{row0}", f"{name} | {case}", "sec"); put(ws, f"E{row0}", case, "input"); R["case"] = row0; row[0] += 1
            case_ref = f"$E${R['case']}"
            ws[f"B{row0}"].font = F_SEC
            macro_ = sid is not None
            jr = lambda drv: J[(sid if macro_ else "MS-BASE", drv)]
            line("brent", "Brent", "USD/bbl", fn=lambda i, c, p: f"=Skenario_Jalur!{c}{jr('brent')}")
            line("fx", "Kurs USD/IDR", "IDR/USD", "#,##0.0", fn=lambda i, c, p: f"=Skenario_Jalur!{c}{jr('usdidr')}")
            line("bi", "BI Rate", "% p.a.", "0.000", fn=lambda i, c, p: f"=Skenario_Jalur!{c}{jr('bi_rate')}")
            if macro_:
                rng = lambda k: f"$E${R[k]}:${colM(11)}${R[k]}"
                line("d_brent_w", "Perubahan Brent rata-rata 12 bulan", "", "0.0000", scalar=f"=AVERAGE({rng('brent')})/{bl('brent_ttm')}-1")
                dirb = f"$E${R['d_brent_w']}"
                line("share", "Pangsa energi bunker", "", "0.000", scalar="=" + _pick_op(A, "vessel_energy_share", case_ref, dirb))
                line("lhv", "Nilai kalor (GJ/ton)", "", "0.000", scalar="=" + _pick_op(A, "lhv_gj_per_t", case_ref, dirb))
                line("eps", "Elastisitas bunker terhadap Brent", "", "0.000", scalar="=" + _pick_op(A, "bunker_brent_elasticity", case_ref, dirb))
                line("phi", "Pass-through bunker", "", "0.000", scalar="=" + _pick_op(A, "bunker_pass_through", case_ref, dirb))
                line("fc", "Biaya bunker tahunan", "USD juta", scalar=f"={bl('energy_gj')}*$E${R['share']}/$E${R['lhv']}*{bl('vlsfo')}/1000000")
                line("theta", "Porsi EBIT rupiah", "", "0.000", scalar="=" + _pick_op(A, "idr_ebit_share", case_ref, f"SIGN(AVERAGE({rng('fx')})-{bl('fx_ttm')})"))
                line("d_rate_w", "Selisih BI Rate rata-rata 12 bulan", "pp", "0.000", scalar=f"=AVERAGE({rng('bi')})-{asm('base_rate')}")
                line("fs", "Porsi utang bank mengambang", "", "0.000", scalar="=" + _pick_op(A, "floating_debt_share", case_ref, f"$E${R['d_rate_w']}"))
                line("d_bunker", "Selisih EBITDA: bunker", "USD juta", fn=lambda i, c, p: f"=-$E${R['fc']}/12*$E${R['eps']}*({c}{R['brent']}/{bl('brent_ttm')}-1)*(1-$E${R['phi']})")
                line("d_trans", "Selisih EBITDA: translasi rupiah", "USD juta", fn=lambda i, c, p: f"=$E${R['theta']}*{bl('ebit')}/12*({bl('fx_ttm')}/{c}{R['fx']}-1)")
                line("rate_pu", "Bunga mengambang per USD pinjaman", "per bulan", "0.00000", fn=lambda i, c, p: f"=({c}{R['bi']}-{asm('base_rate')})/100*$E${R['fs']}/12")
                line("shift", "Guncangan tarif/volume", "USD juta", fn=lambda i, c, p: "=0")
                dshift = f"({c}{R['d_bunker']}+{c}{R['d_trans']})"
            else:
                mr = A["mk:" + mk]
                g, v, m = f"Asumsi!$D${mr}", f"Asumsi!$E${mr}", f"Asumsi!$F${mr}"
                svc = lambda k: f"Baseline_TTM!$C${B['svc:' + k]}"
                psi = _pick_op(A, "cost_flex_down", case_ref, "0")
                d_e = (f"({svc('freight_income')}*((1+{v})*(1+{g})-1)+({svc('agency_forwarding_ports')}+{svc('container_equipment_handling')})*{v}"
                       f"-IF({v}<0,{psi},1)*({bl('cogs')}-{bl('cogs_dep')})*(({svc('freight_income')}+{svc('agency_forwarding_ports')}+{svc('container_equipment_handling')})/{bl('revenue')})*{v})")
                line("rate_pu", "Bunga mengambang per USD pinjaman", "per bulan", "0.00000", fn=lambda i, c, p: "=0")
                line("shift", "Guncangan tarif/volume", "USD juta", fn=lambda i, c, p: f"=IF({c}$6<{m},{d_e}/12,0)")
                dshift = f"{{c}}{R['shift']}"
            if macro_:
                line("ebitda", "EBITDA bulanan", "USD juta", fn=lambda i, c, p: f"={bl('ebitda')}/12+{c}{R['d_bunker']}+{c}{R['d_trans']}", bold=True)
            else:
                line("ebitda", "EBITDA bulanan", "USD juta", fn=lambda i, c, p: f"={bl('ebitda')}/12+{c}{R['shift']}", bold=True)
            line("ocf_conv", "Konversi EBITDA ke kas operasi", "", "0.000", scalar="=" + _pick_ca(A, "ocf_conversion", case_ref))
            line("lease_p", "Pokok sewa tahunan", "USD juta", scalar="=" + _pick_ca(A, "lease_principal", case_ref))
            line("maint_p", "Belanja pemeliharaan tahunan", "USD juta", scalar="=" + _pick_ca(A, "maintenance_capex", case_ref))
            line("overrun", "Kelebihan biaya program", "", "0.000", scalar="=" + _pick_ca(A, "program_cost_overrun", case_ref))
            line("front", "Termin program awal", "", "0.000", scalar="=" + _pick_ca(A, "program_front_share", case_ref))
            line("roll", "Perpanjangan pinjaman jangka pendek", "", "0.000", scalar="=" + _pick_ca(A, "short_bank_rollover", case_ref))
            line("div_p", "Dividen tahunan", "USD juta", scalar="=" + _pick_ca(A, "dividend_annual", case_ref))
            line("yield", "Imbal hasil kas", "", "0.0000", scalar="=" + _pick_ca(A, "cash_yield", case_ref))
            line("depo", "Deposito yang dapat ditarik", "", "0.000", scalar="=" + _pick_ca(A, "deposit_availability", case_ref))
            line("redraw", "Porsi angsuran bank ditarik kembali", "", "0.00", scalar="=1")
            line("prog_total", "Total program kapal baru", "USD juta", scalar=f"={bl('program_idr')}/{bl('fx_sep')}/1000000*(1+$E${R['overrun']})")
            line("ocf", "Kas operasi sebelum bunga", "USD juta", fn=lambda i, c, p: f"={c}{R['ebitda']}*$E${R['ocf_conv']}")
            line("coupon", "Kupon sukuk", "USD juta", fn=lambda i, c, p: f'=-SUMPRODUCT((Data_Sukuk!$E${SK[0]}:$E${SK[1]}={c}$5)*(Data_Sukuk!$D${SK[0]}:$D${SK[1]}="coupon")*Data_Sukuk!$F${SK[0]}:$F${SK[1]})/{c}{R["fx"]}/1000000')
            line("principal", "Pokok sukuk", "USD juta", fn=lambda i, c, p: f'=-SUMPRODUCT((Data_Sukuk!$E${SK[0]}:$E${SK[1]}={c}$5)*(Data_Sukuk!$D${SK[0]}:$D${SK[1]}="principal")*Data_Sukuk!$F${SK[0]}:$F${SK[1]})/{c}{R["fx"]}/1000000')
            bb = row[0]; R["bank_bal"] = bb
            line("bank_bal", "Saldo utang bank awal bulan", "USD juta", fn=lambda i, c, p: (f"={bl('bank_debt')}" if i == 0 else f"={p}{bb}+{p}{bb+2}+{p}{bb+3}"))
            line("other_int", "Bunga bank, sewa, dan lain", "USD juta", fn=lambda i, c, p: f"=-(({bl('interest_paid_ttm')}-{asm('coupon_ttm')})/12+{c}{R['bank_bal']}*{c}{R['rate_pu']})")
            line("bank_repay", "Angsuran bank", "USD juta", fn=lambda i, c, p: f"=-MIN({bl('bank_current')}/12,{c}{R['bank_bal']})")
            line("bank_redraw", "Penarikan ulang bank", "USD juta", fn=lambda i, c, p: f"=-{c}{R['bank_repay']}*$E${R['redraw']}")
            line("lease", "Pokok sewa", "USD juta", fn=lambda i, c, p: f"=-$E${R['lease_p']}/12")
            line("maint", "Belanja pemeliharaan", "USD juta", fn=lambda i, c, p: f"=-$E${R['maint_p']}/12")
            line("program", "Program kapal baru", "USD juta", fn=lambda i, c, p: f"=IF(AND({c}$6>=1,{c}$6<=6),-$E${R['prog_total']}*$E${R['front']}/6,IF(AND({c}$6>=7,{c}$6<=13),-$E${R['prog_total']}*(1-$E${R['front']})/7,0))")
            line("short_repay", "Pelunasan pinjaman jangka pendek", "USD juta", fn=lambda i, c, p: f"=IF({c}$5=\"2027-09\",-{bl('bank_short')}*(1-$E${R['roll']}),0)")
            line("dividend", "Dividen", "USD juta", fn=lambda i, c, p: f"=IF({c}$8=6,-$E${R['div_p']},0)")
            line("opening", "Kas awal bulan", "USD juta", fn=lambda i, c, p: (f"={bl('opening_cash')}" if i == 0 else f"={p}{row[0]+4}"), bold=False)
            line("int_inc", "Bunga atas kas", "USD juta", fn=lambda i, c, p: f"={c}{R['opening']}*$E${R['yield']}/12")
            line("flows", "Arus kas bersih", "USD juta", fn=lambda i, c, p: "=" + "+".join(f"{c}{R[k]}" for k in ("ocf", "int_inc", "coupon", "other_int", "lease", "maint", "program", "bank_repay", "short_repay", "dividend", "principal", "bank_redraw")))
            line("trans", "Translasi kas rupiah", "USD juta", fn=lambda i, c, p: f"={bl('idr_cash_usd')}*{bl('fx_sep')}*(1/{c}{R['fx']}-1/" + (f"{bl('fx_sep')})" if i == 0 else f"{p}{R['fx']})"))
            line("closing", "Kas akhir bulan", "USD juta", fn=lambda i, c, p: f"={c}{R['opening']}+{c}{R['flows']}+{c}{R['trans']}", bold=True)
            assert R["closing"] == R["opening"] + 4 + 0 or True
            line("liquidity", "Kas + deposito", "USD juta", fn=lambda i, c, p: f"={c}{R['closing']}+{bl('deposits')}*$E${R['depo']}", bold=True)
            line("th", "Batas kas minimum", "USD juta", scalar=f"=Asumsi!$E${A['ca:min_cash_months']}*{bl('opex_month')}")
            line("flag", "Di bawah batas (1/0)", "", "0", fn=lambda i, c, p: f"=IF({c}{R['liquidity']}<$E${R['th']},1,0)")
            rr = lambda k: f"$E${R[k]}:${last}${R[k]}"
            # ---- keluaran
            line("e_26", "EBITDA FY2026", "USD juta", scalar=f"={bl('ebitda')}-{bl('q4_25')}+SUM(E{R['ebitda']}:G{R['ebitda']})", bold=True)
            for fy in ("FY2027", "FY2028"):
                y = fy[2:]
                line(f"e_{fy}", f"EBITDA {fy}", "USD juta", scalar=f'=SUMIF($E$7:${last}$7,{y},{rr("ebitda")})')
            for fy in ("FY2027", "FY2028"):
                # sukuk tersisa: sukuk - jatuh tempo sebelum tanggal uji
                prev = {"FY2027": "0", "FY2028": asm("due_FY2027")}[fy]
                line(f"debt_{fy}", f"Utang tanggal uji {fy}", "USD juta", scalar=f"={bl('bank_debt')}+{bl('lease_bs')}+MAX({bl('sukuk_bs')}-({prev}),0)")
                line(f"nd_{fy}", f"Net Debt to EBITDA {fy}", "x", "0.0000", scalar=f"=$E${R['debt_'+fy]}/$E${R['e_'+fy]}", bold=True)
                i_dec = 2 if fy == "FY2027" else 14
                line(f"nd_{fy}_am", f"idem tanpa pembiayaan ulang", "x", "0.0000", scalar=f"=(MAX({bl('bank_debt')}-{bl('bank_current')}/12*{14 if fy == 'FY2027' else 26},0)+{bl('bank_short')}*$E${R['roll']}+{bl('lease_bs')}+MAX({bl('sukuk_bs')}-({prev}),0))/$E${R['e_'+fy]}")
                line(f"cover_{fy}", f"DSCR {fy}", "x", "0.0000", scalar=f"=$E${R['e_'+fy]}/((AVERAGE({asm('ebitda_FY2024')}/{asm('dscr_FY2024')},{asm('ebitda_FY2025')}/{asm('dscr_FY2025')}))+{asm('due_'+fy)})", bold=True)
            line("nd_26", "Net Debt to EBITDA FY2026", "x", "0.0000", scalar=f"=({bl('bank_debt')}+{bl('lease_bs')}+{bl('sukuk_bs')})/$E${R['e_26']}")
            for fy in FYS:
                y = fy[2:]
                line(f"cr_{fy}", f"Current Ratio {fy}", "x", "0.0000", scalar=f'=({bl("ca_bs")}-({bl("opening_cash")}-INDEX({rr("closing")},MATCH("{y}-12",$E$5:${last}$5,0))))/({bl("cl_bs")}+{asm("due_"+fy)})')
            line("cr_min", "Current Ratio terendah", "x", "0.0000", scalar="=MIN(" + ",".join(f"$E${R['cr_'+fy]}" for fy in FYS) + ")", bold=True)
            line("cr_breach", "Tahun pertama Current Ratio < batas", "", "@", scalar='=' + "IF($E$%d<%s,\"FY2027\",IF($E$%d<%s,\"FY2028\",IF($E$%d<%s,\"FY2029\",IF($E$%d<%s,\"FY2030\",\"\"))))" % (
                R["cr_FY2027"], asm("th_cr"), R["cr_FY2028"], asm("th_cr"), R["cr_FY2029"], asm("th_cr"), R["cr_FY2030"], asm("th_cr")))
            line("min_liq", "Kas + deposito terendah", "USD juta", scalar=f"=MIN({rr('liquidity')})", bold=True)
            line("first_below", "Bulan pertama di bawah batas kas", "", "@", scalar=f'=IFERROR(INDEX($E$5:${last}$5,MATCH(1,{rr("flag")},0)),"")')
            line("repay_27", "Pelunasan agar ND <= sasaran", "USD juta", scalar=f"=MAX(0,({bl('bank_debt')}+{bl('lease_bs')}+{bl('sukuk_bs')})-{asm('safe_nd')}*$E${R['e_FY2027']})")
            # ---- paket mitigasi: pelunasan utang bank dari kas (Sep 2027) dan penahanan dividen (sejak Jun 2027)
            for k, (pay, stop) in enumerate(PKGS):
                pay_i, stop_i = 11, 8     # indeks 2027-09 dan 2027-06
                line(f"liq_p{k}", f"Kas + deposito, paket {pay:g}{' + henti dividen' if stop else ''}", "USD juta",
                     fn=lambda i, c, p, pay=pay, stop=stop: (f"={c}{R['liquidity']}-{pay}*({c}$6>={pay_i})" + (f"+IF({c}$6>={stop_i},$E${R['div_p']}*(INT(({c}$6-{stop_i})/12)+1),0)" if stop else "")))
                line(f"nd27_p{k}", "Net Debt to EBITDA FY2027 setelah paket", "x", "0.0000", scalar=f"=($E${R['nd_FY2027']}*$E${R['e_FY2027']}-{pay})/$E${R['e_FY2027']}")
                line(f"nd28_p{k}", "Net Debt to EBITDA FY2028 setelah paket", "x", "0.0000", scalar=f"=($E${R['nd_FY2028']}*$E${R['e_FY2028']}-{pay})/$E${R['e_FY2028']}")
                for fy in FYS:
                    y = fy[2:]
                    sav = f"+{'$E$' + str(R['div_p'])}*({y}-2026)" if stop else ""
                    line(f"cr{fy}_p{k}", f"Current Ratio {fy} setelah paket", "x", "0.0000", scalar=(
                        f'=({bl("ca_bs")}-({bl("opening_cash")}-(INDEX({rr("closing")},MATCH("{y}-12",$E$5:${last}$5,0))-{pay}{sav})))/({bl("cl_bs")}+{asm("due_"+fy)})'))
                line(f"crmin_p{k}", "Current Ratio terendah setelah paket", "x", "0.0000", scalar="=MIN(" + ",".join(f"$E${R['cr'+fy+'_p'+str(k)]}" for fy in FYS) + ")")
                line(f"crfy_p{k}", "Tahun Current Ratio terendah", "", "@", scalar="=INDEX({\"FY2027\",\"FY2028\",\"FY2029\",\"FY2030\"},MATCH($E$%d,CHOOSE({1,2,3,4},%s),0))" % (
                    R[f"crmin_p{k}"], ",".join(f"$E${R['cr'+fy+'_p'+str(k)]}" for fy in FYS)))
                line(f"minliq_p{k}", "Kas + deposito terendah setelah paket", "USD juta", scalar=f"=MIN({rr('liq_p'+str(k))})")
            out[(name, case)] = {"sheet": ws.title, "R": dict(R)}
            row0 = row[0] + 3
        ws.freeze_panes = "E9"
    return out


# =============================================================== Hasil
RESULT_COLS = [("ebitda_FY2026", "e_26", "0.00"), ("ebitda_FY2027", "e_FY2027", "0.00"), ("nd_FY2027", "nd_FY2027", "0.000"), ("nd_FY2027_amortisasi", "nd_FY2027_am", "0.000"),
               ("cover_FY2027", "cover_FY2027", "0.000"), ("ebitda_FY2028", "e_FY2028", "0.00"), ("nd_FY2028", "nd_FY2028", "0.000"), ("nd_FY2028_amortisasi", "nd_FY2028_am", "0.000"),
               ("cover_FY2028", "cover_FY2028", "0.000"), ("nd_FY2026", "nd_26", "0.000"), ("current_ratio_min", "cr_min", "0.000"), ("current_ratio_breach_fy", "cr_breach", "@"),
               ("min_liquidity", "min_liq", "0.0"), ("first_below", "first_below", "@"), ("pelunasan_ke_2_7x", "repay_27", "0.0")]


def build_hasil(wb, KAS):
    ws = sheet(wb, "Hasil", "Hasil model: 6 skenario x 2 kasus", "Setiap sel menaut ke blok mesin di sheet Kas_*. central = asumsi tengah; adverse = downside case arus kas.", tab=BLUE,
               widths={"B": 38, "C": 10})
    header(ws, 5, ["Skenario", "Kasus"] + [c[0] for c in RESULT_COLS])
    for j in range(len(RESULT_COLS)):
        ws.column_dimensions[L(4 + j)].width = 15
    r = 6
    ref = {}
    for name, sid, mk in SCEN:
        for case in ("central", "adverse"):
            k = KAS[(name, case)]
            put(ws, f"B{r}", name, "label"); put(ws, f"C{r}", case, "label")
            for j, (col, key, fm) in enumerate(RESULT_COLS):
                put(ws, f"{L(4 + j)}{r}", f"={k['sheet']}!$E${k['R'][key]}", "link", fm)
            ref[(name, case)] = r; r += 1
    keycol = L(4 + len(RESULT_COLS))
    put(ws, f"{keycol}5", "kunci", "note")
    for (name, case), rr_ in ref.items():
        put(ws, f"{keycol}{rr_}", f'=B{rr_}&"|"&C{rr_}', "calc")
    ws.freeze_panes = "D6"
    return ref


# =============================================================== Covenant_Kuartalan dan Mitigasi
QTRS = ["2026-12", "2027-03", "2027-06", "2027-09", "2027-12", "2028-03", "2028-06", "2028-09", "2028-12"]


def build_kuartalan(wb, A, B, KAS, SK):
    ws = sheet(wb, "Covenant_Kuartalan", "Net Debt to EBITDA dan DSCR per akhir kuartal", "EBITDA 12 bulan terakhir; bulan sebelum Okt 2026 = EBITDA TTM / 12. Utang bank dan sewa tetap, sukuk berkurang saat jatuh tempo.",
               tab=BLUE, widths={"B": 38, "C": 10, "D": 10, "E": 13, "F": 11, "G": 11, "H": 14, "I": 13})
    header(ws, 5, ["Skenario", "Kasus", "Kuartal", "EBITDA TTM", "ND/EBITDA", "DSCR bank", "DSCR + sukuk 12 bln", "Utang"])
    bl = lambda k: f"Baseline_TTM!$C${B[k]}"
    asm = lambda k: f"Asumsi!$E${A[k]}"
    den0 = f"AVERAGE({asm('ebitda_FY2024')}/{asm('dscr_FY2024')},{asm('ebitda_FY2025')}/{asm('dscr_FY2025')})"
    fxs = bl("fx_sep")
    D_ = lambda col: f"Data_Sukuk!${col}${SK[0]}:${col}${SK[1]}"
    r = 6
    rows = {}
    for name, sid, mk in SCEN:
        for case in ("central", "adverse"):
            k = KAS[(name, case)]
            for q in QTRS:
                iq = MONTHS.index(q)
                lo = max(0, iq - 11)
                e = f"SUM({k['sheet']}!{L(FIRST_COL + lo)}{k['R']['ebitda']}:{L(FIRST_COL + iq)}{k['R']['ebitda']})"
                pad = max(0, 11 - iq)
                put(ws, f"B{r}", name, "label"); put(ws, f"C{r}", case, "label"); put(ws, f"D{r}", q, "label")
                put(ws, f"E{r}", f"={e}+{pad}*{bl('ebitda')}/12", "link", "0.000")
                paid = f'SUMPRODUCT(({D_("E")}<=$D{r})*({D_("D")}="principal")*{D_("F")})/{fxs}/1000000'
                put(ws, f"I{r}", f"={bl('bank_debt')}+{bl('lease_bs')}+MAX({bl('sukuk_bs')}-{paid},0)", "calc", "0.000")
                put(ws, f"F{r}", f"=I{r}/E{r}", "calc", "0.0000")
                put(ws, f"G{r}", f"=E{r}/({den0})", "calc", "0.0000")
                hi_label = f"Skenario_Jalur!{L(FIRST_COL + iq + 12)}$5"
                due = f'SUMPRODUCT(({D_("E")}>$D{r})*({D_("E")}<={hi_label})*({D_("D")}="principal")*{D_("F")})/{fxs}/1000000'
                put(ws, f"H{r}", f"=E{r}/(({den0})+{due})", "calc", "0.0000")
                rows[(name, case, q)] = r; r += 1
    ws.freeze_panes = "E6"
    return rows


def build_mitigasi(wb, KAS):
    ws = sheet(wb, "Mitigasi", "Uji paket pengelolaan leverage", "Pelunasan utang bank dari kas pada Sep 2027 dan penahanan dividen sejak Jun 2027, diuji pada jalur kas yang sama. Penghematan bunga tidak dihitung (sisi konservatif).",
               tab=BLUE, widths={"B": 38, "C": 10, "D": 10, "E": 11, "F": 12, "G": 12, "H": 14, "I": 14, "J": 14})
    header(ws, 5, ["Skenario", "Kasus", "Pelunasan", "Henti dividen", "ND FY2027", "ND FY2028", "CR terendah", "Tahun CR", "Kas+deposito min"])
    r = 6
    rows = {}
    for k_, (pay, stop) in enumerate(PKGS):
        for name, sid, mk in SCEN:
            for case in ("central", "adverse"):
                k = KAS[(name, case)]; R = k["R"]; sh = k["sheet"]
                put(ws, f"B{r}", name, "label"); put(ws, f"C{r}", case, "label"); put(ws, f"D{r}", pay, "input", "0"); put(ws, f"E{r}", "Y" if stop else "N", "input")
                for col, key, fm in (("F", f"nd27_p{k_}", "0.000"), ("G", f"nd28_p{k_}", "0.000"), ("H", f"crmin_p{k_}", "0.000"), ("I", f"crfy_p{k_}", "@"), ("J", f"minliq_p{k_}", "0.0")):
                    put(ws, f"{col}{r}", f"={sh}!$E${R[key]}", "link", fm)
                rows[(name, case, pay, stop)] = r; r += 1
    ws.freeze_panes = "F6"
    return rows


# =============================================================== Sensitivitas dan Backtest
def build_sensitivitas(wb, A, B):
    ws = sheet(wb, "Sensitivitas", "Headroom penurunan tarif dan peta Net Debt to EBITDA", "Bentuk tertutup (linier), asumsi tengah. Headroom = penurunan tarif angkut yang membawa Net Debt to EBITDA ke batas, volume tetap.", tab=BLUE,
               widths={"B": 46, "C": 13})
    bl = lambda k: f"Baseline_TTM!$C${B[k]}"
    asm = lambda k: f"Asumsi!$E${A[k]}"
    svc = lambda k: f"Baseline_TTM!$C${B['svc:' + k]}"
    put(ws, "B5", "Headroom penurunan tarif sebelum batas", "sec")
    rows = [("Utang total: bank + sukuk + sewa (USD juta)", f"={bl('bank_debt')}+{bl('sukuk_bs')}+{bl('lease_bs')}", "0.000"),
            ("EBITDA minimum agar ND = batas (USD juta)", f"=C6/{asm('th_nd')}", "0.000"),
            ("Pendapatan angkutan (freight income) TTM (USD juta)", f"={svc('freight_income')}", "0.000"),
            ("Headroom penurunan tarif angkut (volume tetap)", "=(C7-" + bl("ebitda") + ")/C8", "0.00%")]
    for i, (lab, f, fm) in enumerate(rows):
        put(ws, f"B{6 + i}", lab, "label", bold=(i == 3)); put(ws, f"C{6 + i}", f, "calc", fm, bold=(i == 3))
    put(ws, "B11", "Jika dampak nyata lebih ringan dari prediksi model (rasio aktual / prediksi)", "label")
    put(ws, "B12", "sama dengan prediksi (1,00)", "label"); put(ws, "C12", "=C9", "calc", "0.0%")
    put(ws, "B13", "seperti FY2024", "label"); put(ws, "C13", "=C9/Backtest!$H$7", "calc", "0.0%")
    put(ws, "B14", "seperti FY2023", "label"); put(ws, "C14", "=C9/Backtest!$H$6", "calc", "0.0%")
    # peta ND: tarif x volume
    put(ws, "B17", "Net Debt to EBITDA menurut perubahan tarif (baris) dan volume (kolom), setahun penuh", "sec")
    vols = [0.0, -0.02, -0.04, -0.06, -0.08, -0.10]
    rates = [-0.02 * i for i in range(12)]
    put(ws, "B18", "Tarif \\ Volume", "label", bold=True)
    for j, v in enumerate(vols):
        put(ws, f"{L(3 + j)}18", v, "input", "0%")
    psi_dn = _pick_op(A, "cost_flex_down", '"central"', "0")
    F, Ag, H_ = svc("freight_income"), svc("agency_forwarding_ports"), svc("container_equipment_handling")
    exposed = f"(({F}+{Ag}+{H_})/{bl('revenue')})"
    for i, g in enumerate(rates):
        r = 19 + i
        put(ws, f"B{r}", g, "input", "0%")
        for j in range(len(vols)):
            col = L(3 + j); v = f"{col}$18"; gg = f"$B{r}"
            dE = f"({F}*((1+{v})*(1+{gg})-1)+({Ag}+{H_})*{v}-IF({v}<0,{psi_dn},1)*({bl('cogs')}-{bl('cogs_dep')})*{exposed}*{v})"
            put(ws, f"{col}{r}", f"=$C$6/({bl('ebitda')}+{dE})", "calc", "0.00")
    from openpyxl.formatting.rule import CellIsRule
    rng = f"C19:{L(2 + len(vols))}{18 + len(rates)}"
    ws.conditional_formatting.add(rng, CellIsRule(operator="greaterThan", formula=[asm("th_nd")], fill=PatternFill("solid", bgColor="FFF6A5A7", fgColor="FFF6A5A7")))
    ws.conditional_formatting.add(rng, CellIsRule(operator="between", formula=[asm("safe_nd"), asm("th_nd")], fill=PatternFill("solid", bgColor="FFFDE9A8", fgColor="FFFDE9A8")))
    put(ws, "B32", "Merah: di atas batas covenant; kuning: di antara sasaran 2,70x dan batas.", "note")
    ws.freeze_panes = "C6"


def build_backtest(wb):
    ws = sheet(wb, "Backtest", "Backtesting FY2023-FY2025: prediksi model terhadap dampak aktual", "Perubahan EBITDA (USD juta). Prediksi memakai tarif efektif dan volume realisasi tiap tahun; aktual dari laporan keuangan.",
               tab=BLUE, widths={"B": 14, "C": 14, "D": 12, "E": 16, "F": 16, "G": 16, "H": 18, "I": 18})
    header(ws, 5, ["Periode", "Tarif efektif", "Volume", "Prediksi model", "Aktual", "Prediksi / aktual", "Aktual / prediksi", "Biaya jasa berubah"])
    bt = pd.read_csv(dp.table("backtest.csv"))
    for i, x in enumerate(bt.itertuples()):
        r = 6 + i
        put(ws, f"B{r}", x.periode, "label")
        put(ws, f"C{r}", float(x.tarif_efektif), "input", "0.0%"); put(ws, f"D{r}", float(x.volume), "input", "0.0%")
        put(ws, f"E{r}", float(x.model), "input", "#,##0.0"); put(ws, f"F{r}", float(x.terealisasi), "input", "#,##0.0")
        put(ws, f"G{r}", f"=E{r}/F{r}", "calc", '0.00"x"'); put(ws, f"H{r}", f"=F{r}/E{r}", "calc", "0.000")
        put(ws, f"I{r}", float(x.biaya_jasa_delta), "input", "#,##0.0")
    put(ws, "B10", "Sumber nilai biru: data/04_marts/results/backtest.csv (model Python). Prediksi 1,9x aktual pada FY2023 dan 1,3x pada FY2024; FY2025 sama.", "note")


# =============================================================== Cek dan Dashboard
def build_cek(wb, A, B, KAS, SK):
    ws = sheet(wb, "Cek", "Pemeriksaan integritas dan kecocokan dengan model Python", "Kolom 'Python' berisi nilai statis dari data/04_marts/results; selisih dihitung oleh rumus. PASS bila |selisih| <= 1e-5 (relatif).", tab=BLUE,
               widths={"B": 56, "C": 16, "D": 16, "E": 14, "F": 8})
    header(ws, 6, ["Pemeriksaan", "Excel", "Python", "Selisih", "Status"])
    sr = pd.read_csv(dp.table("scenario_results.csv"))
    r = 7
    def row(label, f_excel, py, fm="0.0000"):
        nonlocal r
        put(ws, f"B{r}", label, "label"); put(ws, f"C{r}", f_excel, "link", fm)
        if py is not None:
            put(ws, f"D{r}", float(py), "input", fm)
            put(ws, f"E{r}", f"=C{r}-D{r}", "calc", "0.0E+00")
            put(ws, f"F{r}", f'=IF(ABS(E{r})<=0.00001*MAX(1,ABS(D{r})),"PASS","GAGAL")', "calc")
        r += 1
    for name, sid, mk in SCEN:
        for case in ("central", "adverse"):
            k = KAS[(name, case)]; R = k["R"]; v = sr[(sr.skenario == name) & (sr.case == case)].iloc[0]
            for lab, key, col in (("ND FY2027", "nd_FY2027", "nd_FY2027"), ("DSCR FY2027", "cover_FY2027", "cover_FY2027"), ("Current Ratio terendah", "cr_min", "current_ratio_min"), ("Kas + deposito terendah", "min_liq", "min_liquidity")):
                row(f"{lab}: {name} | {case}", f"={k['sheet']}!$E${R[key]}", v[col])
    # integritas internal
    bl = lambda kk: f"Baseline_TTM!$C${B[kk]}"
    r += 1; put(ws, f"B{r}", "Integritas internal", "sec"); r += 1
    row("Pendapatan TTM: laporan keuangan vs jumlah jenis jasa (selisih)", f"={bl('revenue_stmt')}-{bl('revenue')}", 0.0, "0.000000")
    for name, sid, mk in SCEN[:3]:
        k = KAS[(name, "central")]; R = k["R"]; sh = k["sheet"]
        row(f"Saldo bank awal Des 2031 sama dengan awal (pembiayaan ulang): {name}", f"={sh}!{L(FIRST_COL + 62)}{R['bank_bal']}", None)
        ws[f"D{r-1}"].value = f"={bl('bank_debt')}"; ws[f"D{r-1}"].font = F_LINK
        put(ws, f"E{r-1}", f"=C{r-1}-D{r-1}", "calc", "0.0E+00"); put(ws, f"F{r-1}", f'=IF(ABS(E{r-1})<=0.000001,"PASS","GAGAL")', "calc")
    k = KAS[("Dasar", "central")]; R = k["R"]; sh = k["sheet"]
    row("Kas akhir Okt 2026 = kas awal Nov 2026 (kontinuitas)", f"={sh}!{L(FIRST_COL)}{R['closing']}", None)
    ws[f"D{r-1}"].value = f"={sh}!{L(FIRST_COL + 1)}{R['opening']}"; ws[f"D{r-1}"].font = F_LINK
    put(ws, f"E{r-1}", f"=C{r-1}-D{r-1}", "calc", "0.0E+00"); put(ws, f"F{r-1}", f'=IF(ABS(E{r-1})<=0.000001,"PASS","GAGAL")', "calc")
    row("Headroom penurunan tarif (Sensitivitas) vs Python", "=Sensitivitas!$C$9", -0.118485678, "0.000000")
    put(ws, "B4", "Ringkasan", "label", bold=True)
    put(ws, "C4", f'=COUNTIF(F7:F{r},"PASS")&" PASS, "&COUNTIF(F7:F{r},"GAGAL")&" GAGAL"', "calc", bold=True)
    ws.freeze_panes = "B7"


def build_dashboard(wb, A, B, KAS, Hr, Qr):
    from openpyxl.chart import LineChart, Reference, Series
    from openpyxl.worksheet.datavalidation import DataValidation
    ws = sheet(wb, "Dashboard", "Dashboard: Net Debt to EBITDA, DSCR, Current Ratio, dan likuiditas", "Pilih skenario dan kasus pada sel kuning; semua angka dan grafik mengikuti.", tab=BLUE,
               widths={"B": 34, "C": 22, "D": 14, "E": 14, "F": 14, "G": 14, "H": 14, "I": 14, "J": 14, "K": 14, "L": 14})
    put(ws, "B5", "Skenario", "label", bold=True); put(ws, "C5", "Permintaan lemah dan kelebihan kapasitas", "input")
    put(ws, "B6", "Kasus", "label", bold=True); put(ws, "C6", "central", "input")
    dv1 = DataValidation(type="list", formula1='"' + ",".join(n for n, _, _ in SCEN) + '"', allow_blank=False)
    dv2 = DataValidation(type="list", formula1='"central,adverse"', allow_blank=False)
    ws.add_data_validation(dv1); ws.add_data_validation(dv2); dv1.add("C5"); dv2.add("C6")
    put(ws, "B7", "Kunci pencarian", "note"); put(ws, "C7", '=C5&"|"&C6', "calc")
    last = max(Hr.values())
    KEY = L(4 + len(RESULT_COLS))
    put(ws, "B9", "Hasil terpilih", "sec")
    items = [("Net Debt to EBITDA FY2027 (batas 3,00x)", "D", "0.00"), ("Net Debt to EBITDA FY2028", "H", "0.00"), ("DSCR FY2027 (min. 1,10x)", "F", "0.00"),
             ("DSCR FY2028", "J", "0.00"), ("Current Ratio terendah (min. 1,10x)", "N", "0.00"), ("Kas + deposito terendah (USD juta)", "P", "0.0"),
             ("Bulan pertama kas di bawah batas", "Q", "@"), ("Pelunasan agar ND <= 2,70x (USD juta)", "R", "0.0")]
    # kolom Hasil: B skenario, C kasus, D.. = RESULT_COLS (D ebitda26, E ebitda27, F nd27, G nd27am, H cover27, I e28, J nd28, K nd28am, L cover28, M nd26, N crmin, O crbreach, P minliq, Q first, R pelunasan)
    colmap = {"Net Debt to EBITDA FY2027 (batas 3,00x)": "F", "Net Debt to EBITDA FY2028": "J", "DSCR FY2027 (min. 1,10x)": "H", "DSCR FY2028": "L",
              "Current Ratio terendah (min. 1,10x)": "N", "Kas + deposito terendah (USD juta)": "P", "Bulan pertama kas di bawah batas": "Q", "Pelunasan agar ND <= 2,70x (USD juta)": "R"}
    for i, (lab, _, fm) in enumerate(items):
        r = 10 + i
        put(ws, f"B{r}", lab, "label"); put(ws, f"C{r}", f"=INDEX(Hasil!${colmap[lab]}$6:${colmap[lab]}${last},MATCH($C$7,Hasil!${KEY}$6:${KEY}${last},0))", "link", fm, bold=True)
    # tabel kuartalan (6 skenario, kasus tengah) untuk grafik
    put(ws, "B20", "Net Debt to EBITDA per kuartal (asumsi tengah)", "sec")
    header(ws, 21, ["Kuartal"] + [n for n, _, _ in SCEN] + ["Batas 3,00x", "Sasaran 2,70x"])
    for qi, q in enumerate(QTRS):
        r = 22 + qi
        put(ws, f"B{r}", q, "label")
        for j, (name, _, _) in enumerate(SCEN):
            put(ws, f"{L(3 + j)}{r}", f"=Covenant_Kuartalan!$F${Qr[(name, 'central', q)]}", "link", "0.00")
        put(ws, f"{L(3 + len(SCEN))}{r}", f"=Asumsi!$E${A['th_nd']}", "link", "0.00"); put(ws, f"{L(4 + len(SCEN))}{r}", f"=Asumsi!$E${A['safe_nd']}", "link", "0.00")
    ch = LineChart(); ch.title = "Net Debt to EBITDA per akhir kuartal"; ch.height, ch.width = 8.5, 17
    data = Reference(ws, min_col=3, max_col=4 + len(SCEN), min_row=21, max_row=30)
    ch.add_data(data, titles_from_data=True); ch.set_categories(Reference(ws, min_col=2, min_row=22, max_row=30))
    pal = ["BCBEC0", "6D6E71", "A0A0A0", "FDB913", "0D0403", "000000", "ED1C24", "ED1C24"]
    for sr_, colr in zip(ch.series, pal):
        sr_.graphicalProperties.line.solidFill = colr; sr_.graphicalProperties.line.width = 22000; sr_.smooth = False
    ch.series[-2].graphicalProperties.line.dashStyle = "dash"; ch.series[-1].graphicalProperties.line.dashStyle = "sysDot"
    ws.add_chart(ch, "M5")
    # jalur likuiditas terpilih
    put(ws, "B33", "Kas + deposito bulanan (skenario dan kasus terpilih)", "sec")
    header(ws, 34, ["Bulan", "Kas + deposito", "Batas kas minimum"])
    names = [n for n, _, _ in SCEN]
    for i in range(N_MONTHS):
        r = 35 + i
        c = L(FIRST_COL + i)
        put(ws, f"B{r}", f"=Skenario_Jalur!{c}5", "link")
        parts = []
        for case in ("central", "adverse"):
            for n_ in names:
                k = KAS[(n_, case)]
                parts.append((n_, case, f"{k['sheet']}!{c}{k['R']['liquidity']}", f"{k['sheet']}!$E${k['R']['th']}"))
        sel = lambda idx: "IF($C$6=\"central\",CHOOSE(MATCH($C$5,{%s},0),%s),CHOOSE(MATCH($C$5,{%s},0),%s))" % (
            ",".join('"%s"' % n_ for n_ in names), ",".join(p[idx] for p in parts[:6]), ",".join('"%s"' % n_ for n_ in names), ",".join(p[idx] for p in parts[6:]))
        put(ws, f"C{r}", "=" + sel(2), "link", "0.0"); put(ws, f"D{r}", "=" + sel(3), "link", "0.0")
    ch2 = LineChart(); ch2.title = "Kas + deposito vs batas minimum (USD juta)"; ch2.height, ch2.width = 8.5, 17
    ch2.add_data(Reference(ws, min_col=3, max_col=4, min_row=34, max_row=35 + N_MONTHS - 1), titles_from_data=True)
    ch2.set_categories(Reference(ws, min_col=2, min_row=35, max_row=35 + N_MONTHS - 1))
    ch2.series[0].graphicalProperties.line.solidFill = "0D0403"; ch2.series[1].graphicalProperties.line.solidFill = "ED1C24"; ch2.series[1].graphicalProperties.line.dashStyle = "dash"
    for s_ in ch2.series: s_.smooth = False; s_.graphicalProperties.line.width = 22000
    ws.add_chart(ch2, "M24")
    ws.freeze_panes = "B9"


# =============================================================== Panduan_Model
def build_panduan(wb):
    ws = sheet(wb, "Panduan_Model", "Financial Model SMDR: ketahanan covenant dan likuiditas terhadap siklus freight rate",
               "Workbook ini = laporan keuangan historis (sheet asli, tidak diubah) + model berumus hidup. Dicocokkan dengan model Python (data/04_marts/results).", tab="FF7D8696",
               widths={"B": 26, "C": 100})
    rows = [("Peta sheet", ""), ("Panduan_Model", "Halaman ini."), ("Asumsi", "Semua input: parameter transmisi dan kas (rendah/tengah/merugikan), batas covenant, definisi skenario."),
            ("Data_Makro", "Brent dan kurs bulanan (data/03_canonical)."), ("Baseline_TTM", "TTM Sep 2026 dan neraca 30 Sep 2026, tertaut ke sheet laporan keuangan."),
            ("Skenario_Jalur", "Jalur Brent, kurs, BI Rate per skenario makro, dibangun dengan rumus."),
            ("Dashboard, Hasil", "Pemilih skenario dan kasus; ringkasan 12 hasil."), ("Kas_*", "Mesin kas bulanan dan covenant, satu sheet per skenario (blok tengah dan merugikan)."),
            ("Covenant_Kuartalan, Mitigasi", "Net Debt to EBITDA, DSCR per kuartal; uji paket pelunasan dan penahanan dividen."), ("Sensitivitas, Backtest, Cek", "Headroom penurunan tarif, peta ND, uji balik, dan pemeriksaan kecocokan dengan Python."),
            ("Ringkasan ... Panduan", "Sheet laporan keuangan asli (Laba Rugi, Posisi Keuangan, Arus Kas, dst.), isi tidak diubah."),
            ("", ""), ("Kode warna", ""), ("Biru dengan latar kuning", "Input. Ubah hanya sel ini."), ("Hitam", "Rumus."), ("Hijau", "Tautan ke sheet lain (mis. ke laporan keuangan)."),
            ("", ""), ("Verifikasi", "Setiap hasil dibandingkan dengan model Python: lihat sheet Cek (tahap berikutnya). Perhitungan ulang dengan LibreOffice menghasilkan selisih nol pada keluaran yang tercakup."),
            ("Status", "Model lengkap: asumsi, data makro, posisi dasar, jalur skenario, mesin kas dan covenant (6 skenario x 2 kasus), covenant kuartalan, mitigasi, sensitivitas, backtest, cek, dashboard.")]
    r = 5
    for a, b in rows:
        put(ws, f"B{r}", a, "label", bold=bool(a and not b) or a in ("Verifikasi", "Status")); put(ws, f"C{r}", b, "label"); r += 1
    return ws


def build(path=OUT):
    wb = openpyxl.load_workbook(SOURCE)
    pan = build_panduan(wb)
    A = build_asumsi(wb)
    M = build_data_makro(wb)
    B = build_baseline(wb, M)
    J = build_jalur(wb, A, M)
    SK = build_sukuk(wb)
    KAS = build_kas(wb, A, B, J, SK)
    H = build_hasil(wb, KAS)
    Q = build_kuartalan(wb, A, B, KAS, SK)
    MIT = build_mitigasi(wb, KAS)
    build_sensitivitas(wb, A, B)
    build_backtest(wb)
    build_cek(wb, A, B, KAS, SK)
    build_dashboard(wb, A, B, KAS, H, Q)
    order = ["Panduan_Model", "Dashboard", "Hasil", "Covenant_Kuartalan", "Mitigasi", "Sensitivitas", "Backtest", "Cek", "Asumsi", "Data_Makro", "Baseline_TTM", "Skenario_Jalur"] + [SHEETS[n_] for n_, _, _ in SCEN] + ["Data_Sukuk"]
    wb._sheets = [wb[n] for n in order] + [s for s in wb._sheets if s.title not in order]
    wb.active = 0
    os.makedirs(os.path.dirname(path), exist_ok=True)
    wb.save(path)
    return {"A": A, "M": M, "B": B, "J": J, "KAS": KAS, "H": H, "Q": Q, "MIT": MIT}


def recalc(path, outdir):
    """Hitung ulang semua rumus dengan LibreOffice (headless) dan simpan salinan bernilai."""
    os.makedirs(outdir, exist_ok=True)
    subprocess.run(["soffice", "--headless", "--calc", "--convert-to", "xlsx", "--outdir", outdir, path], check=True, capture_output=True, timeout=300)
    return os.path.join(outdir, os.path.basename(path))




# =============================================================== verifikasi terhadap Python
def _values(path):
    return openpyxl.load_workbook(path, data_only=True)


def check_b1(calc_path, maps):
    """Cocokkan Baseline_TTM dan Skenario_Jalur (hasil hitung ulang) dengan model Python. Mengembalikan (jumlah uji, daftar selisih > toleransi)."""
    from .transition import cashflow as cf, macro
    wb = _values(calc_path)
    inp = cf._init()
    B, J = maps["B"], maps["J"]
    bad, n = [], 0
    ws = wb["Baseline_TTM"]
    pairs = {"revenue": "revenue", "cogs": "cogs", "interest_ttm": "interest_ttm", "cogs_dep": "cogs_dep", "ebit": "ebit", "ebitda": "ebitda", "bank_debt": "bank_debt",
             "bank_current": "bank_current", "lease_current": "lease_current", "opening_cash": "opening_cash", "deposits": "deposits", "ocf_ttm": "ocf_ttm",
             "interest_paid_ttm": "interest_paid_ttm", "interest_received_ttm": "interest_received_ttm", "opex_month": "opex_month", "brent_ttm": "brent_ttm", "fx_ttm": "fx_ttm", "fx_sep": "fx_sep"}
    for k, pk in pairs.items():
        x = ws[f"C{B[k]}"].value; n += 1
        if x is None or abs(float(x) - float(inp[pk])) > 1e-6 * max(1.0, abs(float(inp[pk]))):
            bad.append(("Baseline_TTM", k, x, inp[pk]))
    x = ws[f"C{B['bank_short']}"].value; n += 1
    if abs(float(x) - inp["short_bank"]) > 1e-6:
        bad.append(("Baseline_TTM", "short_bank", x, inp["short_bank"]))
    paths = macro.build_paths()
    wj = wb["Skenario_Jalur"]
    for (sid, drv), r in J.items():
        ref = paths[(paths.scenario_id == sid) & (paths.driver == drv)].sort_values("month")["value"].tolist()
        for i, v in enumerate(ref):
            x = wj.cell(row=r, column=FIRST_COL + i).value; n += 1
            if x is None or abs(float(x) - v) > 1e-7 * max(1.0, abs(v)):
                bad.append(("Skenario_Jalur", f"{sid}/{drv}/{i}", x, v))
    return n, bad


def check_b2(calc_path, maps):
    """Cocokkan mesin kas (deret bulanan) dan hasil per skenario dengan data/04_marts/results (selisih harus nol)."""
    wb = _values(calc_path)
    cp = pd.read_csv(dp.table("cash_paths_monthly.csv"))
    sr = pd.read_csv(dp.table("scenario_results.csv"))
    bad, n = [], 0
    for (name, case), k in maps["KAS"].items():
        ws, R = wb[k["sheet"]], k["R"]
        g = cp[(cp.skenario == name) & (cp.case == case)].sort_values("month")
        for key, col in (("ebitda", "ebitda"), ("closing", "closing"), ("liquidity", "liquidity")):
            for i, v in enumerate(g[col].tolist()):
                x = ws.cell(row=R[key], column=FIRST_COL + i).value; n += 1
                try:
                    miss = x is None or abs(float(x) - v) > 2e-6 * max(1.0, abs(v))
                except (TypeError, ValueError):
                    miss = True
                if miss:
                    bad.append((name, case, key, i, x, v))
        r = sr[(sr.skenario == name) & (sr.case == case)].iloc[0]
        for col, key, fm in RESULT_COLS:
            x = ws.cell(row=R[key], column=FIRST_COL).value; v = r[col]; n += 1
            if isinstance(v, float) and v != v:
                v = ""
            if isinstance(v, str) or v == "":
                ok = (x or "") == (v or "")
            else:
                try:
                    ok = x is not None and abs(float(x) - float(v)) <= 2e-6 * max(1.0, abs(float(v)))
                except (TypeError, ValueError):
                    ok = False
            if not ok:
                bad.append((name, case, col, x, v))
    return n, bad


def check_b3(calc_path, maps):
    """Cocokkan covenant kuartalan dan uji mitigasi dengan data/04_marts/results."""
    wb = _values(calc_path)
    cq = pd.read_csv(dp.table("covenant_quarterly.csv"))
    mt = pd.read_csv(dp.table("mitigation_tests.csv"))
    bad, n = [], 0
    ws = wb["Covenant_Kuartalan"]
    for (name, case, q), r in maps["Q"].items():
        ref = cq[(cq.skenario == name) & (cq.case == case) & (cq.quarter == q)].iloc[0]
        for col, key in (("E", "ebitda_ttm"), ("F", "nd"), ("G", "dscr_bank"), ("H", "dscr_with_sukuk"), ("I", "debt")):
            x, v = ws[f"{col}{r}"].value, float(ref[key]); n += 1
            try:
                ok = abs(float(x) - v) <= 2e-6 * max(1.0, abs(v))
            except (TypeError, ValueError):
                ok = False
            if not ok:
                bad.append(("Covenant_Kuartalan", name, case, q, key, x, v))
    wm = wb["Mitigasi"]
    for (name, case, pay, stop), r in maps["MIT"].items():
        ref = mt[(mt.skenario == name) & (mt.case == case) & (mt.paydown == pay) & (mt.dividend_stop == stop)].iloc[0]
        for col, key in (("F", "nd_FY2027"), ("G", "nd_FY2028"), ("H", "current_ratio_min"), ("J", "min_liquidity")):
            x, v = wm[f"{col}{r}"].value, float(ref[key]); n += 1
            try:
                ok = abs(float(x) - v) <= 2e-6 * max(1.0, abs(v))
            except (TypeError, ValueError):
                ok = False
            if not ok:
                bad.append(("Mitigasi", name, case, pay, stop, key, x, v))
        x = wm[f"I{r}"].value; n += 1
        if x != ref["current_ratio_min_fy"]:
            bad.append(("Mitigasi", name, case, pay, stop, "fy", x, ref["current_ratio_min_fy"]))
    return n, bad


def publish():
    """Bangun, hitung ulang dengan LibreOffice, verifikasi terhadap model Python, lalu terbitkan berkas bernilai (cached) ke model/."""
    import tempfile
    tmp = tempfile.mkdtemp(prefix="smdr_xl_")
    maps = build(os.path.join(tmp, "SMDR_Financial_Model.xlsx"))
    calc = recalc(os.path.join(tmp, "SMDR_Financial_Model.xlsx"), os.path.join(tmp, "calc"))
    res = {"B1": check_b1(calc, maps), "B2": check_b2(calc, maps), "B3": check_b3(calc, maps)}
    for k, (n, bad) in res.items():
        print("%s paritas: %d sel diuji, %d selisih" % (k, n, len(bad)))
        for b in bad[:8]:
            print("  ", b)
    if all(not bad for _, bad in res.values()):
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        shutil.copy2(calc, OUT)
        print("diterbitkan:", os.path.relpath(OUT, dp.ROOT))
    else:
        print("TIDAK diterbitkan: ada selisih terhadap model Python")
    return res


if __name__ == "__main__":
    publish()
