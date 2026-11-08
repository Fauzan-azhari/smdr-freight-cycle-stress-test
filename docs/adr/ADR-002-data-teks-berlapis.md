# ADR-002: Data teks terbuka dalam lima lapisan

**Status:** diterima (Nov 2026)

**Konteks.** Data awalnya tersebar pada folder sumber, tabel kurasi, tabel bentukan kode, dan keluaran model tanpa pemisahan jelas, sehingga asal-usul angka sulit ditelusuri.

**Keputusan.** `data/` memakai lima lapisan (`00_registry`, `01_raw`, `02_curated`, `03_canonical`, `04_marts`), semuanya CSV UTF-8 (akhir baris LF). Satu modul (`smdr.datapaths`) menjadi satu-satunya tempat jalur didefinisikan; registri memuat sumber (SHA-256), *lineage*, kamus kolom, dan kontrak skema.

**Konsekuensi.** Isi folder, peta jalur, dan *lineage* dijaga test (`tests/test_data_architecture.py`); setiap angka kanonik dapat ditelusuri ke baris mentah. Lapisan mentah IDX adalah ekstraksi per butir, bukan berkas Excel IDX asli.
