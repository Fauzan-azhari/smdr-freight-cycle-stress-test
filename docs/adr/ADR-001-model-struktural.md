# ADR-001: Model akuntansi terstruktur, bukan ekonometrika, sebagai inti

**Status:** diterima (Nov 2026)

**Konteks.** Pertanyaan riset menuntut hubungan tarif/volume → EBITDA → *covenant*. Hanya tiga tahun (FY2023–FY2025) memiliki data tarif efektif dan EBITDA yang sebanding, dan periode itu memuat patahan struktural (lonjakan 2021–2022, koreksi 2023).

**Keputusan.** Besaran guncangan dikalibrasi statistik (persentil historis), dan transmisinya memakai model akuntansi terstruktur yang setiap mata rantainya dapat diperiksa terhadap laporan keuangan. Ekonometrika dipakai untuk kalibrasi dan uji ketahanan, bukan sebagai inti.

**Konsekuensi.** Koefisien tidak diestimasi dari tiga titik; parameter berupa rentang dengan sumber dan status. Kelemahannya: model linier dan deterministik, dan klaim "tidak meremehkan dampak" bertumpu pada tiga pengamatan *backtest*. Hal ini dinyatakan pada naskah (Bab 6 dan 8).
