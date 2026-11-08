"""Kamus baris laporan keuangan SMDR.

Setiap baris di workbook sumber diberi kunci tetap (line_key). Kolom `parent` dan `sign`
menyatakan bagaimana baris itu masuk ke subtotalnya, sehingga validasi penjumlahan
bisa dibaca langsung dari kamus ini.

Tanda mengikuti konvensi sumber: beban dan pembayaran tercatat positif, dan bersign -1
ketika dikurangkan. Baris yang sudah bertanda (mis. pajak, kas lainnya) bersign +1.

Label harus sama persis dengan kolom B pada sheet sumber. Label yang tidak terdaftar
akan menghentikan ingest, supaya baris baru tidak lolos tanpa dipetakan.

Jika satu subtotal punya dua dekomposisi yang berbeda, parent diberi akhiran "#nama"
(mis. laba komprehensif = laba + OCI, dan = induk + non-pengendali).
"""

# (label sumber, line_key, parent, sign)
INCOME_STATEMENT = [
    ("Pendapatan usaha", "revenue", "gross_profit", 1),
    ("Beban pokok pendapatan", "cogs", "gross_profit", -1),
    ("Laba bruto", "gross_profit", "profit_before_tax", 1),
    ("Beban umum dan administrasi", "ga_expense", "profit_before_tax", -1),
    ("Pendapatan keuangan", "finance_income", "profit_before_tax", 1),
    ("Beban bunga dan keuangan", "finance_expense", "profit_before_tax", -1),
    ("Keuntungan (kerugian) selisih kurs mata uang asing", "fx_gain_loss", "profit_before_tax", 1),
    ("Bagian laba (rugi) entitas asosiasi", "associates_share", "profit_before_tax", 1),
    ("Pendapatan lainnya", "other_income", "profit_before_tax", 1),
    ("Keuntungan (kerugian) lainnya", "other_gains_losses", "profit_before_tax", 1),
    ("Laba (rugi) sebelum pajak", "profit_before_tax", "profit_continuing", 1),
    ("Pendapatan (beban) pajak", "tax_income_expense", "profit_continuing", 1),
    ("Laba (rugi) operasi yang dilanjutkan", "profit_continuing", None, 1),
    ("Laba (rugi) periode berjalan", "profit_period", "comprehensive_income", 1),
    ("Penyesuaian OCI yang tidak direklasifikasi, setelah pajak", "oci_nonreclass_adj", None, 1),
    ("Jumlah OCI yang tidak direklasifikasi, setelah pajak", "oci_nonreclass_total", None, 1),
    ("Selisih kurs penjabaran, setelah pajak", "oci_translation", None, 1),
    ("Bagian OCI entitas asosiasi, setelah pajak", "oci_associates", None, 1),
    ("Bagian OCI ventura bersama, setelah pajak", "oci_joint_venture", None, 1),
    ("Penyesuaian OCI yang akan direklasifikasi, setelah pajak", "oci_reclass_adj", None, 1),
    ("Jumlah OCI yang akan direklasifikasi, setelah pajak", "oci_reclass_total", None, 1),
    ("Jumlah OCI, setelah pajak", "oci_total", "comprehensive_income", 1),
    ("Jumlah laba (rugi) komprehensif", "comprehensive_income", None, 1),
    ("Laba (rugi) pemilik entitas induk", "profit_parent", "profit_period", 1),
    ("Laba (rugi) kepentingan non-pengendali", "profit_nci", "profit_period", 1),
    ("Laba komprehensif pemilik entitas induk", "ci_parent", "comprehensive_income#atribusi", 1),
    ("Laba komprehensif kepentingan non-pengendali", "ci_nci", "comprehensive_income#atribusi", 1),
    ("EPS dasar, operasi dilanjutkan (USD/saham)", "eps_basic", None, 1),
]

BALANCE_SHEET = [
    ("Kas dan setara kas", "cash", "total_current_assets", 1),
    ("Aset keuangan lancar lainnya", "other_fin_assets_current", "total_current_assets", 1),
    ("Piutang usaha pihak ketiga", "trade_rec_third", "total_current_assets", 1),
    ("Piutang usaha pihak berelasi", "trade_rec_related", "total_current_assets", 1),
    ("Piutang lainnya pihak ketiga", "other_rec_third", "total_current_assets", 1),
    ("Piutang lainnya pihak berelasi", "other_rec_related", "total_current_assets", 1),
    ("Persediaan lancar", "inventories", "total_current_assets", 1),
    ("Biaya dibayar dimuka lancar", "prepaid_current", "total_current_assets", 1),
    ("Uang muka lancar", "advances_current", "total_current_assets", 1),
    ("Pajak dibayar dimuka lancar", "prepaid_tax_current", "total_current_assets", 1),
    ("Aset / kelompok lepasan dimiliki untuk dijual", "assets_held_for_sale", "total_current_assets", 1),
    ("Jumlah aset lancar", "total_current_assets", "total_assets", 1),
    ("Investasi pada entitas asosiasi", "investments_associates", "total_noncurrent_assets", 1),
    ("Uang muka tidak lancar", "advances_noncurrent", "total_noncurrent_assets", 1),
    ("Aset keuangan tidak lancar lainnya", "other_fin_assets_noncurrent", "total_noncurrent_assets", 1),
    ("Aset pajak tangguhan", "deferred_tax_assets", "total_noncurrent_assets", 1),
    ("Properti investasi", "investment_property", "total_noncurrent_assets", 1),
    ("Aset tetap", "fixed_assets", "total_noncurrent_assets", 1),
    ("Aset imbalan pasca kerja", "post_employment_asset", "total_noncurrent_assets", 1),
    ("Aset tidak lancar non-keuangan lainnya", "other_nonfin_assets_noncurrent", "total_noncurrent_assets", 1),
    ("Jumlah aset tidak lancar", "total_noncurrent_assets", "total_assets", 1),
    ("Jumlah aset", "total_assets", None, 1),
    ("Utang bank jangka pendek", "bank_short_term", "total_current_liabilities", 1),
    ("Utang usaha pihak ketiga", "trade_pay_third", "total_current_liabilities", 1),
    ("Utang usaha pihak berelasi", "trade_pay_related", "total_current_liabilities", 1),
    ("Utang lainnya pihak ketiga", "other_pay_third", "total_current_liabilities", 1),
    ("Utang lainnya pihak berelasi", "other_pay_related", "total_current_liabilities", 1),
    ("Beban akrual jangka pendek", "accrued_expenses", "total_current_liabilities", 1),
    ("Utang pajak", "taxes_payable", "total_current_liabilities", 1),
    ("Pendapatan ditangguhkan jangka pendek", "deferred_revenue_current", "total_current_liabilities", 1),
    ("Utang bank jatuh tempo dalam satu tahun", "bank_long_term_current", "total_current_liabilities", 1),
    ("Liabilitas sewa jatuh tempo dalam satu tahun", "lease_current", "total_current_liabilities", 1),
    ("Sukuk jatuh tempo dalam satu tahun", "sukuk_current", "total_current_liabilities", 1),
    ("Jumlah liabilitas jangka pendek", "total_current_liabilities", "total_liabilities", 1),
    ("Liabilitas pajak tangguhan", "deferred_tax_liabilities", "total_noncurrent_liabilities", 1),
    ("Utang bank jangka panjang", "bank_long_term", "total_noncurrent_liabilities", 1),
    ("Liabilitas sewa jangka panjang", "lease_long_term", "total_noncurrent_liabilities", 1),
    ("Sukuk jangka panjang", "sukuk_long_term", "total_noncurrent_liabilities", 1),
    ("Kewajiban imbalan pasca kerja jangka panjang", "post_employment_liability", "total_noncurrent_liabilities", 1),
    ("Jumlah liabilitas jangka panjang", "total_noncurrent_liabilities", "total_liabilities", 1),
    ("Jumlah liabilitas", "total_liabilities", "total_liabilities_equity", 1),
    ("Saham biasa", "share_capital", "equity_parent", 1),
    ("Tambahan modal disetor", "additional_paid_in_capital", "equity_parent", 1),
    ("Cadangan selisih kurs penjabaran", "translation_reserve", "equity_parent", 1),
    ("Cadangan pengukuran kembali program imbalan pasti", "remeasurement_reserve", "equity_parent", 1),
    ("Cadangan lainnya", "other_reserves", "equity_parent", 1),
    ("Komponen ekuitas lainnya", "other_equity_components", "equity_parent", 1),
    ("Saldo laba yang telah ditentukan penggunaannya", "retained_appropriated", "equity_parent", 1),
    ("Saldo laba yang belum ditentukan penggunaannya", "retained_unappropriated", "equity_parent", 1),
    ("Ekuitas pemilik entitas induk", "equity_parent", "total_equity", 1),
    ("Kepentingan non-pengendali", "equity_nci", "total_equity", 1),
    ("Jumlah ekuitas", "total_equity", "total_liabilities_equity", 1),
    ("Jumlah liabilitas dan ekuitas", "total_liabilities_equity", None, 1),
]

CASH_FLOW = [
    ("Penerimaan dari pelanggan", "receipts_customers", "cash_from_operations", 1),
    ("Pembayaran kepada pemasok atas barang dan jasa", "payments_suppliers", "cash_from_operations", -1),
    ("Pembayaran gaji dan tunjangan", "payments_payroll", "cash_from_operations", -1),
    ("Kas diperoleh dari (digunakan untuk) operasi", "cash_from_operations", "cfo", 1),
    ("Penerimaan bunga dari aktivitas operasi", "interest_received", "cfo", 1),
    ("Pembayaran bunga dari aktivitas operasi", "interest_paid", "cfo", -1),
    ("Pembayaran pajak penghasilan badan", "tax_paid_corporate", "cfo", -1),
    ("Pengembalian (pembayaran) pajak penghasilan operasi", "tax_refund_net", "cfo", 1),
    ("Arus kas bersih aktivitas operasi", "cfo", "net_change_cash", 1),
    ("Pembayaran uang muka pembelian aset tetap", "advances_fixed_assets", "cfi", -1),
    ("Penerimaan dari penjualan aset tetap", "proceeds_fixed_assets", "cfi", 1),
    ("Pembayaran untuk perolehan aset tetap", "capex_fixed_assets", "cfi", -1),
    ("Pencairan (penempatan) investasi jangka pendek", "short_term_investments_net", "cfi", 1),
    ("Pencairan (penempatan) aset keuangan FVTPL", "fvtpl_assets_net", "cfi", 1),
    ("Pembayaran tambahan kepemilikan entitas anak", "subsidiary_stake_purchase", "cfi", -1),
    ("Pembayaran kepemilikan entitas asosiasi", "associates_purchase", "cfi", -1),
    ("Penerimaan dividen dari aktivitas investasi", "dividends_received", "cfi", 1),
    ("Penerimaan (pengeluaran) kas lainnya dari aktivitas investasi", "other_investing", "cfi", 1),
    ("Arus kas bersih aktivitas investasi", "cfi", "net_change_cash", 1),
    ("Penerimaan pinjaman bank", "bank_loan_proceeds", "cff", 1),
    ("Pembayaran pinjaman bank", "bank_loan_repayments", "cff", -1),
    ("Penerimaan pinjaman tanpa agunan", "unsecured_loan_proceeds", "cff", 1),
    ("Pembayaran pinjaman tanpa agunan", "unsecured_loan_repayments", "cff", -1),
    ("Pembayaran liabilitas sewa pembiayaan", "lease_payments", "cff", -1),
    ("Penerimaan sukuk", "sukuk_proceeds", "cff", 1),
    ("Pembayaran sukuk", "sukuk_repayments", "cff", -1),
    ("Pembayaran dividen dari aktivitas pendanaan", "dividends_paid", "cff", -1),
    ("Penerimaan (pengeluaran) kas lainnya dari aktivitas pendanaan", "other_financing", "cff", 1),
    ("Arus kas bersih aktivitas pendanaan", "cff", "net_change_cash", 1),
    ("Kenaikan (penurunan) bersih kas dan setara kas", "net_change_cash", "cash_end", 1),
    ("Kas dan setara kas awal periode", "cash_begin", "cash_end", 1),
    ("Efek perubahan nilai kurs pada kas dan setara kas", "fx_effect_cash", "cash_end", 1),
    ("Kas dan setara kas akhir periode", "cash_end", None, 1),
]

# Rincian beban pokok pendapatan (Catatan, baris 17-26). Depresiasi di sini termasuk
# aset hak guna dan berbeda dari "penambahan" pada jadwal aset tetap.
COGS_NOTE = [
    ("Beban jasa", "services_cost", "total_production_cost", 1),
    ("Pengangkutan dan bongkar muat", "freight_handling", "total_production_cost", 1),
    ("Upah, tenaga kerja langsung", "direct_labour", "total_production_cost", 1),
    ("Depresiasi", "depreciation", "total_production_cost", 1),
    ("Sewa", "rent", "total_production_cost", 1),
    ("Perbaikan dan pemeliharaan", "repair_maintenance", "total_production_cost", 1),
    ("Biaya pabrikasi lainya", "other_production_cost", "total_production_cost", 1),
    ("Jumlah biaya produksi", "total_production_cost", None, 1),
    ("Harga pokok produksi", "cost_of_production", None, 1),
    ("Beban pokok pendapatan", "cogs_note", None, 1),
]

STATEMENTS = {
    "IS": INCOME_STATEMENT,
    "BS": BALANCE_SHEET,
    "CF": CASH_FLOW,
    "COGS_NOTE": COGS_NOTE,
}

# Pasangan yang harus sama walau bukan hubungan induk-anak.
EQUALITIES = [
    ("IS", "profit_period", "profit_continuing"),
    ("BS", "total_assets", "total_liabilities_equity"),
    ("COGS_NOTE", "total_production_cost", "cost_of_production"),
    ("COGS_NOTE", "cost_of_production", "cogs_note"),
]


# --- Perluasan untuk roll-forward neraca (spesifikasi perubahan riset, bagian 9.7) ---------------
# Label sumber berbentuk "<judul blok> | <baris>", karena baris yang sama (mis. "Saldo awal")
# muncul di banyak blok.

_MOVES = [  # label baris, kunci, tanda terhadap saldo akhir
    ("Saldo awal", "opening", 1), ("Penambahan", "additions", 1), ("Pengurangan", "disposals", -1),
    ("Reklasifikasi", "reclass", 1), ("Penjabaran", "translation", 1),
    ("Penurunan/pemulihan nilai", "impairment", -1), ("Saldo akhir", "closing", 1),
]


def _ppe_groups(prefix_label, prefix_key, groups):
    out = []
    for suffix, gkey, parent in groups:
        header = "%s / %s" % (prefix_label, suffix)
        for label, mkey, sign in _MOVES:
            key = "%s.%s.%s" % (prefix_key, gkey, mkey)
            if mkey == "closing":
                par = ("%s.%s.closing#komposisi" % (prefix_key, parent)) if parent else None
            else:
                par = "%s.%s.closing" % (prefix_key, gkey)
            out.append(("%s | %s" % (header, label), key, par, sign if mkey != "closing" else 1))
    return out


_COST = [("Tanah, dimiliki langsung", "land", "owned"), ("Bangunan dan fasilitasnya, dimiliki langsung", "buildings", "owned"),
         ("Mesin dan peralatan, dimiliki langsung", "machinery", "owned"),
         ("Perabot dan peralatan kantor, dimiliki langsung", "furniture", "owned"),
         ("Kapal, dimiliki langsung", "vessels", "owned"), ("Lainnya, dimiliki langsung", "owned_other", "owned"),
         ("Dimiliki langsung", "owned", "ppe"),
         ("Lainnya, aset hak guna", "rou_other", "rou"), ("Alat pengangkutan, aset hak guna", "rou_vehicles", "rou"),
         ("Bangunan, aset hak guna", "rou_buildings", "rou"), ("Kapal, aset hak guna", "rou_vessels", "rou"),
         ("Aset hak guna", "rou", "ppe"),
         ("Lainnya, dalam penyelesaian", "cip_other", "cip"), ("Aset dalam penyelesaian", "cip", "ppe"),
         ("Aset tetap", "ppe", None)]
_ACC = [g for g in _COST if not g[1].startswith("rou")]

PPE_NOTE = (_ppe_groups("Harga perolehan bruto", "cost", _COST) + _ppe_groups("Akumulasi depresiasi", "acc", _ACC)
            + [("Nilai buku bersih / Aset tetap | Saldo awal", "nbv.ppe.opening", None, 1),
               ("Nilai buku bersih / Aset tetap | Saldo akhir", "nbv.ppe.closing", None, 1)])

DEBT_NOTE = [
    ("Utang bank jangka pendek: jumlah kotor | Bank lokal lainnya / IDR", "bank_st_idr", "bank_st_total", 1),
    ("Utang bank jangka pendek: jumlah kotor | Bank lokal lainnya / USD", "bank_st_usd", "bank_st_total", 1),
    ("Utang bank jangka pendek: jumlah kotor | Bank lokal lainnya / Mata uang", "bank_st_total", None, 1),
    ("Utang bank jangka panjang | Current maturities of bank loans", "bank_lt_current", None, 1),
    ("Utang bank jangka panjang | Long-term bank loans", "bank_lt_noncurrent", None, 1),
]


def _equity(header, prefix, with_acq):
    rows = [("Saldo awal periode sebelum penyajian kembali", "opening_pre", None, 1),
            ("Posisi ekuitas, awal periode", "opening", "%s.closing" % prefix, 1),
            ("Laba (rugi)", "profit", "%s.closing" % prefix, 1),
            ("Pendapatan komprehensif lainnya", "oci", "%s.closing" % prefix, 1),
            ("Distribusi dividen kas", "dividends", "%s.closing" % prefix, -1)]
    if with_acq:
        rows.append(("Perubahan kepentingan non-pengendali atas akuisisi entitas anak", "nci_acquisition", "%s.closing" % prefix, 1))
    rows.append(("Posisi ekuitas, akhir periode", "closing", None, 1))
    return [("%s | %s" % (header, lab), "%s.%s" % (prefix, key), par, sg) for lab, key, par, sg in rows]


EQUITY_BLOCKS = [("Ekuitas", "total", True), ("Ekuitas yang dapat diatribusikan kepada entitas induk", "parent", True),
                 ("Kepentingan non-pengendali", "nci", False)]
EQUITY = [r for h, pfx, acq in EQUITY_BLOCKS for r in _equity(h, pfx, acq)]

STATEMENTS.update({"EQ": EQUITY, "PPE": PPE_NOTE, "DEBT_NOTE": DEBT_NOTE})
EQUALITIES.extend([("EQ", "total.opening_pre", "total.opening")])


def label_index(statement):
    """label -> (line_key, parent, sign) untuk satu laporan."""
    return {lab: (key, parent, sign) for lab, key, parent, sign in STATEMENTS[statement]}
