# Arsitektur data

Seluruh data riset ini berupa **teks terbuka**: CSV UTF-8, akhir baris LF, tanggal ISO 8601, titik desimal, tanpa sel gabungan. Tiap berkas dapat dibuka dengan editor teks, `grep`, atau pustaka apa pun. Tidak ada format biner di dalam `data/`.

Data mengalir satu arah melalui lima lapisan. Tiap lapisan hanya boleh membaca lapisan di sebelah kirinya.

```
 SUMBER EKSTERNAL                                                              KONSUMEN
 (IDX, FRED, Drewry, ...)                                                      (deck, Excel, naskah)
        |                                                                            ^
        v                                                                            |
 +-------------+    +---------------+    +---------------+    +----------------+   +------------+
 | 01_raw      | -> | 02_curated    | -> | 03_canonical  | -> | 04_marts       | ->|  hasil     |
 | teks apa    |    | kurasi tangan |    | tabel analitik|    | keluaran model |   |  final     |
 | adanya      |    | + alamat      |    | bentukan kode |    | (hasil angka   |   |            |
 | dari        |    | sumber        |    | + kontrol     |    |  yang tampil)  |   |            |
 | penyedia    |    | (asumsi,      |    | mutu          |    |                |   |            |
 |             |    |  keputusan)   |    |               |    |                |   |            |
 +-------------+    +---------------+    +---------------+    +----------------+   +------------+
        ^                   ^                    ^                     ^
        |                   |                    |                     |
 +--------------------------------------------------------------------------------------------+
 | 00_registry : registri sumber (SHA-256), lineage, kamus kolom, kontrak skema, celah data   |
 +--------------------------------------------------------------------------------------------+
```

Satu pintu jalur: modul `smdr.datapaths` menerjemahkan nama tabel ke lapisan fisiknya. Tidak ada kode yang menulis jalur data secara manual.

## Isi tiap lapisan

| Lapisan | Isi | Tabel | Aturan |
|---|---|---|---|
| `00_registry` | Registri sumber, lineage, kamus kolom, kontrak skema, manifes, celah data | 7 | Diperbarui oleh `python -m smdr.registry`; dijaga `tests/test_data_architecture.py` |
| `01_raw` | Teks apa adanya dari penyedia: 4.196 butir IDX (alamat sel asli), Brent dan kurs FRED, kurs penyedia, Drewry WCI | 6 | Tidak diubah. Hash SHA-256 tiap berkas ada di `00_registry/sources.csv` |
| `02_curated` | Tabel kurasi tangan beralamat sumber: asumsi, skenario, bukti, pembiayaan, keputusan, pengecualian yang diketahui | 26 | Tiap baris memuat sumber, status, dan alasan |
| `03_canonical` | Tabel analitik bentukan kode (`fs_long`, `macro_*`, `financing_events`) dan hasil kontrol mutu | 10 | Dibangun ulang oleh kode; tidak diedit tangan |
| `04_marts` | Keluaran model: jalur dasar (`baseline/`) dan hasil final (`results/`) | 12 | Konsumsi bersama deck, Excel, dan naskah |

Peta lengkap tiap tabel (produsen, masukan, pembaca, pemakaian deck) ada di [`00_registry/lineage.csv`](00_registry/lineage.csv). Kamus 517 kolom ada di [`dictionary.csv`](00_registry/dictionary.csv), dan 125 aturan kontrak di [`schemas.csv`](00_registry/schemas.csv).

## Perlakuan data (ringkas)

Rincian lengkap: [`docs/data-treatment.md`](../docs/data-treatment.md).

```
 diperoleh -> didaftar -> dipertahankan -> distandarkan -> divalidasi -> diberi aturan -> dimodelkan
 (sumber)    (SHA-256)    (01_raw, teks)   (03_canonical)  (cek + uji)   (n.d., zero-fill,  (04_marts)
                                                                          TTM, restatement)
```

Tiga aturan yang paling sering menentukan angka:

1. **`n.d.` bukan nol.** Sel yang tidak diisi pada sumber berstatus `nd` dengan nilai kosong. Isian nol hanya lewat aturan tertulis di `02_curated/assumptions/zero_fill_rules.csv`.
2. **Interim bersifat kumulatif.** 6M26 adalah Januari sampai Juni. Kuartal diskrit dan TTM dihitung dari seri ini (`04_marts/baseline`).
3. **Tanda dan satuan mengikuti sumber.** Angka laporan keuangan dalam USD penuh; grafik memakai USD juta.

## Membangun ulang

Dari akar repositori, dengan `.venv` aktif:

```
PYTHONPATH=src python -m smdr.raw_export       # 01_raw/idx dari workbook kurasi
PYTHONPATH=src python -m smdr.fs_ingest        # 03_canonical/fs_long + registri laporan keuangan
PYTHONPATH=src python -m smdr.fs_checks        # kontrol identitas akuntansi
PYTHONPATH=src python -m smdr.macro_ingest     # 03_canonical/macro_*
PYTHONPATH=src python -m smdr.macro_checks
PYTHONPATH=src python -m smdr.baseline         # 04_marts/baseline
PYTHONPATH=src python -m smdr.marts            # 04_marts/results
PYTHONPATH=src python -m smdr.registry         # 00_registry (sources, lineage, kamus, kontrak)
PYTHONPATH=src python -m unittest discover -s tests
```

Pipeline ini deterministik: dibangun ulang dari lapisan mentah dan kurasi, hasilnya sama byte per byte dengan berkas yang ada.

## Bukti jejak

`tests/test_data_architecture.py` memeriksa, antara lain, bahwa:

- isi folder `data/` sama persis dengan peta `datapaths.LAYOUT` dan `lineage.csv`;
- lapisan mentah berupa teks UTF-8 sah dengan akhir baris LF, dan hash-nya cocok dengan `sources.csv`;
- seluruh tabel memenuhi kontrak (kunci unik, kolom wajib, domain nilai, aturan `n.d.`);
- **2.156 dari 2.156 angka `fs_long` berstatus `reported` dapat ditelusuri ke satu baris mentah dengan nilai yang sama.**

## Status redistribusi

Kolom `redistribution` pada `sources.csv` menandai tiap sumber. Data FRED terbuka dengan atribusi. Ekstraksi IDX dipublikasikan per butir, bukan berkas aslinya. **Drewry WCI dan kurs penyedia berstatus "perlu verifikasi"**: atribusi dicantumkan, tetapi izin redistribusi belum dipastikan. Dokumen sumber (Annual Report, prospektus, laporan riset) tidak dipublikasikan, hanya manifes beserta hash dan halaman rujukannya.
