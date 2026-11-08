# ADR-003: Satu sumber untuk angka deck, Excel, dan naskah

**Status:** diterima (Nov 2026)

**Konteks.** Angka yang sama tampil di slide, model Excel, dan naskah; mengetiknya manual berisiko menyimpang saat model berubah.

**Keputusan.** Hasil model ditulis sebagai CSV pada `data/04_marts/results` oleh fungsi yang sama dengan deck. Naskah dibangun dengan mengganti token dengan nilai dari marts; model Excel dicocokkan sel per sel dengan marts; slide memakai angka yang dihitung, bukan diketik.

**Konsekuensi.** Perubahan model mengubah angka di seluruh keluaran secara konsisten, dan test (`tests/test_paper.py`, `tests/test_excel_model.py`, `tests/test_docs.py`) mendeteksi penyimpangan.
