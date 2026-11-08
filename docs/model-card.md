# Model card: stress test covenant dan likuiditas SMDR

## Tujuan dan ruang lingkup

Mengukur sensitivitas pemenuhan *covenant* (*Net Debt to EBITDA*, DSCR, *Current Ratio*) dan likuiditas PT Samudera Indonesia Tbk terhadap penurunan tarif angkut dan volume, serta guncangan biaya (bunker, kurs, bunga), pada horizon Okt 2026 sampai Des 2031. Hasil dipakai sebagai ukuran **sensitivitas dan urutan tekanan**, bukan prediksi.

## Rancangan

Hibrida: statistik untuk kalibrasi besaran guncangan; model akuntansi terstruktur untuk meneruskannya ke EBITDA, kas bulanan, dan rasio *covenant* kuartalan atas EBITDA 12 bulan. Ekonometrika tidak dijadikan inti karena hanya tersedia tiga observasi tahunan yang sebanding dan ada patahan struktural ([ADR-001](adr/ADR-001-model-struktural.md)). Persamaan dan alasan tiap pilihan: [naskah](../notebooks/paper.html), Bab 3.

## Masukan

Data publik: laporan keuangan SMDR, Informasi Tambahan Sukuk, *Annual Report*, FRED (Brent, kurs), Drewry WCI, proyeksi makro Mandiri OCE. Parameter dikurasi dengan rentang rendah/tengah/merugikan, sumber, dan status ([`data/02_curated/assumptions`](../data/02_curated/assumptions)). Tidak ada data internal perusahaan.

## Keluaran

Enam skenario (tiga makro, tiga pasar) × dua kasus (asumsi tengah dan *downside case* arus kas): EBITDA, *Net Debt to EBITDA*, DSCR, *Current Ratio*, kas + deposito, bulan pertama di bawah batas, uji paket pelunasan dan penahanan dividen. Tersedia sebagai CSV di [`data/04_marts/results`](../data/04_marts/results) dan sebagai model Excel.

## Evaluasi

| Uji | Hasil |
|---|---|
| *Backtesting* FY2023–FY2025 | Prediksi 1,9× dan 1,3× dampak aktual (FY2023, FY2024), sama pada FY2025: tidak meremehkan dampak, pada tiga pengamatan |
| Jejak mentah → kanonik | 2.156 dari 2.156 angka dilaporkan dapat ditelusuri ke satu baris mentah |
| Python ↔ Excel | 3.754 sel dicocokkan, 0 selisih |
| Persamaan ↔ kode | 10 persamaan dihitung ulang dari masukan (Lampiran A naskah), semua *pass* |
| Keparahan historis | Guncangan skenario dibandingkan persentil ke-90 Brent dan kurs dan penurunan tarif FY2024 |

## Keterbatasan

Tanpa data internal; frekuensi pengukuran *covenant* belum terkonfirmasi (diasumsikan kuartalan); model linier dan deterministik; tiga tahun *backtest*; *threshold Early Warning* dikalibrasi pada keluaran model yang sama; skenario normalisasi rute tidak ditampilkan; empat risiko operasional belum dikuantifikasi; posisi 30 September 2026 belum diaudit.

## Penggunaan yang tidak tepat

Bukan alat prediksi arah tarif, bukan pernyataan probabilitas, bukan penilaian kepatuhan atau pelanggaran *covenant*, dan bukan dasar keputusan investasi atau kredit.

## Versi dan reproduksi

Versi 1.0.0, sesuai presentasi 10 November 2026. Reproduksi: [README](../README.md) (tingkat reproduksi) dan [perlakuan data](data-treatment.md). Perubahan: [CHANGELOG](../CHANGELOG.md).
