# Perlakuan data: dari perolehan sampai hasil

Dokumen ini menjelaskan bagaimana data diperlakukan pada setiap tahap, dan di mana aturan itu ditegakkan. Tiap aturan merujuk ke berkas atau test yang menjaganya, sehingga pembaca dapat memeriksa, bukan sekadar percaya.

```
 1 PEROLEHAN      2 PENDAFTARAN    3 PEMELIHARAAN    4 STANDARDISASI    5 VALIDASI       6 ATURAN         7 PEMODELAN
 sumber publik -> SHA-256, tanggal -> teks apa adanya -> tipe, satuan,  -> identitas,    -> n.d., zero-fill -> skenario,
 (IDX, FRED,      akses, status       (01_raw)           tanggal, kunci     paritas,         kumulatif->TTM,    covenant, kas
  Drewry, ...)    redistribusi                           (03_canonical)     kontrak          restatement        (04_marts)
```

## 1. Perolehan

Seluruh data berasal dari sumber publik. Tidak ada data internal perusahaan.

| Jenis | Sumber | Cara memperoleh |
|---|---|---|
| Laporan keuangan | Tujuh berkas Excel IDX (FY2022 sampai 9M26) | Diunduh dari pengungkapan emiten; FY2021 diambil dari kolom pembanding FY2022 |
| Dokumen perusahaan | Informasi Tambahan Sukuk, Annual Report 2021 sampai 2025 | PDF publik, dibaca halaman per halaman |
| Makro | Brent (EIA via FRED), kurs USD/IDR (OECD via FRED dan penyedia pasar) | Unduhan CSV |
| Pasar pelayaran | Drewry World Container Index | Grafik publik Drewry |
| Riset dan berita | Mandiri OCE, Linerlytica, SIRI, media | Dokumen dan artikel publik |

## 2. Pendaftaran

Setiap sumber didaftar di [`data/00_registry/sources.csv`](../data/00_registry/sources.csv) dengan penerbit, jenis, tanggal akses, status redistribusi, dan SHA-256 berkas mentahnya. Dokumen PDF dan Excel IDX didaftar per berkas di `fs_source_manifest.csv` dan `source_manifest.csv`, lengkap dengan hash dan jumlah halaman. Test `test_raw_hashes_match_source_registry` memastikan hash cocok.

## 3. Pemeliharaan lapisan mentah

Lapisan mentah menyimpan nilai **seperti diperoleh**, sebagai teks, tanpa konversi tipe, satuan, atau pembersihan.

- Butir IDX: `smdr.raw_export` mengekspor sheet "Data Sumber" menjadi `01_raw/idx/idx_line_items.csv` (4.196 baris). Setiap baris membawa berkas, sheet, dan alamat sel asli IDX.
- Seri FRED, kurs penyedia, dan WCI disimpan apa adanya di `01_raw/`.
- Test `test_raw_layer_is_plain_text` menjaga bahwa berkas mentah berupa UTF-8 sah dengan akhir baris LF.

## 4. Standardisasi (mentah ke kanonik)

`smdr.fs_ingest` dan `smdr.macro_ingest` mengubah teks mentah menjadi tabel panjang (*tidy*): satu baris per pengamatan.

| Aspek | Perlakuan | Tempat penegakan |
|---|---|---|
| Nama kolom dan baris | `snake_case`; baris laporan dipetakan ke `line_key` lewat kamus baris | `00_registry/fs_line_dictionary.csv` |
| Periode | FY, 3M/6M/9M; basis `fy`, `ytd` (kumulatif), `instant` (saldo) | kolom `period`, `basis` pada `fs_long.csv` |
| Satuan | Laporan keuangan USD penuh; grafik USD juta | kontrak skema |
| Tanggal | ISO 8601 (`YYYY-MM-DD`) | kontrak skema |
| Format angka | Format Indonesia (titik ribuan, koma desimal) dan format Inggris diurai terpisah | `macro_ingest.num_id`, `num_en`; `test_number_parsing` |
| Tanda | Tanda sumber dipertahankan | `docs`, workbook Panduan |
| Jejak | Setiap baris kanonik membawa berkas, sheet, dan sel asal | `source_file_id`, `source_sheet`, `source_cell` |

## 5. Validasi

Tiga lapis pemeriksaan, semuanya otomatis.

1. **Identitas akuntansi** (`smdr.fs_checks`): 698 pemeriksaan jumlah komponen, persamaan ekuitas, dan tautan antarlaporan, dengan toleransi USD 1. Hasil: 695 PASS dan 3 KNOWN, tanpa FAIL. Selisih yang diketahui penyebabnya didaftar di `02_curated/quality/fs_known_exceptions.csv`, lengkap dengan penjelasan.
2. **Kualitas seri makro** (`smdr.macro_checks`): urutan tanggal, duplikasi, harga positif, kelengkapan Brent bulanan, dan konsistensi OHLC kurs. Hasil: 9 PASS, 2 INFO, 1 KNOWN (tiga bulan penutupan kurs 2020 di bawah nilai terendah, penyebab tidak diketahui; kolom lain dipakai hanya untuk penutupan).
3. **Angka dari dokumen** (`smdr.operating`): setiap angka dari Annual Report diuji bahwa tokennya tercetak pada halaman PDF yang dikutip (303 token), ditambah uji aritmetika (jumlah jenis jasa, pangsa segmen).

Selain itu, hash berkas IDX diverifikasi terhadap berkas asli (F01 sampai F07: OK).

**Jejak mentah ke kanonik:** `raw_export.parity()` memeriksa bahwa setiap nilai berstatus `reported` pada `fs_long.csv` (2.156 baris) sama dengan satu baris mentah. Hasil: 0 selisih, 0 tidak ditemukan.

## 6. Aturan perlakuan

| Masalah | Aturan | Penegakan |
|---|---|---|
| Sel kosong pada sumber | **`n.d.` bukan nol.** Status `nd` dengan nilai kosong (449 dari 2.605 baris `fs_long`) | kontrak skema: `value_usd` kosong jika dan hanya jika `status = nd` |
| Kebutuhan nilai nol | Hanya lewat aturan tertulis, mis. Z01 (sukuk jatuh tempo kurang dari satu tahun pada 30 Sep 2026 = 0, karena pokok terdekat jatuh tempo 2 Agustus 2028) | `02_curated/assumptions/zero_fill_rules.csv` |
| Interim kumulatif | 6M26 = Januari sampai Juni. Kuartal diskrit = selisih kumulatif; TTM = FY terakhir + interim berjalan − interim pembanding | `smdr.baseline`, `04_marts/baseline` |
| Penyajian ulang (*restatement*) | FY2021 memakai pembanding FY2022; FY2022 sampai 9M26 memakai angka berjalan pada berkas masing-masing. Perbedaan versi ditampilkan di sheet Rekonsiliasi | workbook Panduan; `02_curated/quality` |
| EBITDA | Tidak ada pada sumber. Definisi operasi final: EBIT (laba bruto − beban umum dan administrasi) + penyusutan biaya jasa + penyusutan G&A, keduanya dari bukti PDF berstatus *usable*; penyusutan beban pokok FY2025 memakai PDF audit (keputusan D01). Gagal bila bukti tidak tunggal | `02_curated/decisions/decisions.csv`, `smdr.covenant_band.ebitda_operating` |
| Bulan parsial | Bulan terakhir tiap seri ditandai `partial = True` bila belum lengkap | `macro_monthly.csv`; `test_partial_months_flagged` |
| Seri bulanan dari harian | Rata-rata bulan dan observasi terakhir bulan; hari libur Brent berstatus `nd` (46 hari) | `smdr.macro_ingest` |
| Definisi covenant | Net Debt to EBITDA = (utang bank + sukuk + sewa) ÷ EBITDA, tanpa dikurangi kas, sesuai definisi pada perjanjian yang direproduksi (0,66x FY2022; 2,52x FY2025) | `smdr.transition.covenants` |

## 7. Kurasi tangan

Hal yang tidak dapat diekstraksi otomatis dikurasi dan diberi alamat sumber, status, dan alasan: asumsi (`02_curated/assumptions`, dengan rentang rendah/tengah/merugikan), skenario makro (`scenarios`), bukti beralamat halaman (`evidence`), fasilitas pembiayaan (`financing`), dan **catatan keputusan** (`decisions`). Celah data yang diketahui didaftar di `00_registry/data_gaps.csv`, beserta data yang diminta dan pengganti sementaranya.

## 8. Pemodelan dan keluaran

Model membaca hanya lapisan kanonik dan kurasi. Keluaran final ditulis ke `04_marts/results/` oleh `smdr.marts`, memakai fungsi yang sama dengan deck. Dengan begitu angka pada deck, workbook Excel, dan naskah berasal dari satu sumber. Pembaca dapat membandingkan keduanya.

## 9. Kontrol mutu dan reproduksi

- `tests/test_data_architecture.py`: isi folder, lineage, hash, kontrak skema, dan jejak mentah ke kanonik.
- Test fungsional per modul (data, transmisi, kas, covenant, mitigasi, ketahanan).
- Pipeline dibangun ulang dari lapisan mentah dan hasilnya sama byte per byte dengan berkas yang ada.

Perintah membangun ulang ada di [`data/README.md`](../data/README.md).

## 10. Keterbatasan data

- Laporan 9M26 belum diaudit; hasil bersifat pro forma atas posisi 30 September 2026.
- Frekuensi pengukuran covenant bank belum terkonfirmasi; diasumsikan kuartalan sebagai pendekatan konservatif.
- Penyedia seri kurs penyedia tidak tercatat pada berkasnya; Drewry WCI berstatus "perlu verifikasi" untuk redistribusi.
- Tidak ada indeks publik untuk rute domestik Indonesia; indeks global hanya penanda posisi siklus, bukan pengganti tarif efektif SMDR.
