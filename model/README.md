# Financial Model SMDR

`SMDR_Financial_Model.xlsx` memadukan dua hal dalam satu workbook:

1. **Laporan keuangan historis** (10 sheet asli: Ringkasan, Laba Rugi, Posisi Keuangan, Arus Kas, dan seterusnya). Isinya tidak diubah: 51.347 sel identik dengan `Financial-Statements/SMDR_Financial_Statements_2021_9M26.xlsx`.
2. **Model berumus hidup** (19 sheet baru) yang mengukur ketahanan covenant dan likuiditas SMDR terhadap siklus freight rate.

Template mengikuti workbook sumber (Open Sans untuk judul, Arial Narrow untuk isi, pita biru muda, gridlines mati). Kode warna: biru dengan latar kuning = input; hitam = rumus; hijau = tautan antar sheet.

## Alur model

```
 Asumsi + Data_Makro + Sheet laporan ──> Baseline_TTM ──> Skenario_Jalur ──> Kas_* (6 skenario x 2 kasus)
 (input beralamat sumber)                (TTM, neraca)     (Brent, kurs,       (EBITDA, kas, covenant)
                                                            BI Rate bulanan)          │
        Dashboard <── Hasil <── Covenant_Kuartalan, Mitigasi, Sensitivitas, Backtest ─┘
                                        Cek (kecocokan dengan model Python)
```

| Sheet | Isi |
|---|---|
| `Dashboard` | Pemilih skenario dan kasus; angka kunci; grafik ND per kuartal dan kas + deposito |
| `Hasil` | 12 hasil (6 skenario x central/adverse): ND, DSCR, Current Ratio, kas minimum, pelunasan |
| `Covenant_Kuartalan` | Net Debt to EBITDA dan DSCR per akhir kuartal Des 2026 sampai Des 2028 (108 baris) |
| `Mitigasi` | Paket pelunasan utang bank dan penahanan dividen (36 uji) |
| `Sensitivitas` | Headroom penurunan tarif (11,8%) dan peta ND menurut tarif x volume |
| `Backtest` | Prediksi model vs dampak aktual FY2023 sampai FY2025 |
| `Cek` | 54 pemeriksaan: kecocokan dengan Python dan integritas internal |
| `Asumsi`, `Data_Makro`, `Data_Sukuk`, `Baseline_TTM`, `Skenario_Jalur` | Input, data, posisi dasar yang tertaut ke laporan keuangan, dan jalur driver |
| `Kas_Dasar` ... `Kas_Terburuk` | Mesin kas bulanan dan covenant, Okt 2026 sampai Des 2031 |

## Bukti kecocokan

Setiap hasil dihitung ulang dengan LibreOffice dan dicocokkan sel per sel dengan model Python (`data/04_marts/results`):

| Tahap | Cakupan | Sel diuji | Selisih |
|---|---|---|---|
| B1 | Posisi dasar TTM dan jalur makro | 586 | 0 |
| B2 | Mesin kas: EBITDA, kas, likuiditas bulanan (12 blok) dan 15 hasil per blok | 2.448 | 0 |
| B3 | Covenant kuartalan dan uji mitigasi | 720 | 0 |

Sheet `Cek` memuat bukti yang sama di dalam workbook, sehingga pembaca tanpa Python tetap dapat memeriksanya.

## Membangun ulang

```
PYTHONPATH=src python -m smdr.excel_model     # bangun, hitung ulang (LibreOffice), verifikasi, terbitkan
PYTHONPATH=src python -m unittest tests.test_excel_model
```

Berkas hanya diterbitkan bila seluruh pemeriksaan kecocokan lolos.

## Batas yang perlu diketahui

- Jalur makro dibangun dengan rumus dari definisi pada `Asumsi`. Rasio preseden Brent diturunkan dari data bulanan 2022 sampai 2023 di `Data_Makro`.
- **Dihitung di Python dan tidak ditiru dalam rumus:** sensitivitas tornado kas (menjalankan ulang model per parameter), uji keparahan Brent dan kurs dari riwayat FRED 1987 sampai 2026, dan kupon sukuk TTM (nilai input).
- Hasil bersifat pro forma atas posisi 30 September 2026 (belum diaudit), bukan proyeksi atau pernyataan probabilitas.
