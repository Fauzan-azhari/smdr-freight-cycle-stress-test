# Naskah penelitian

`paper.ipynb` adalah naskah penelitian dalam satu notebook bergaya artikel jurnal ekonomi: abstrak (Inggris), pendahuluan, tinjauan pustaka, metodologi dengan persamaan bernomor, data, hasil, uji ketahanan, pembahasan, keterbatasan, kesimpulan, referensi, dan lampiran verifikasi. `paper.html` adalah salinan terbaca tanpa kode.

## Cara naskah dibangun

```
data/04_marts + data/03_canonical ──> build_paper.py ──> paper.ipynb ──> paper.html
```

- **Angka pada teks tidak diketik.** `build_paper.py` mengganti setiap token (mis. `@nd27_ovr_c:2@`) dengan nilai yang dihitung dari data saat naskah dibangun.
- **Tabel dan gambar dieksekusi** dari data; keluarannya tersimpan pada notebook.
- **Persamaan dibuktikan.** Lampiran A menghitung ulang persamaan (1)-(7) dan (13)-(17) dari masukan dan membandingkannya dengan keluaran model; notebook gagal dibangun bila ada selisih. Persamaan (8)-(12) diverifikasi lewat kecocokan 3.754 sel antara model Python dan model Excel berumus hidup.
- **Rujukan hanya yang terverifikasi** pada basis data bibliografi (DOI atau BIS).

## Membangun ulang

```
PYTHONPATH=src python notebooks/build_paper.py
```

Notebook-notebook analisis lama (sepuluh buah, belum sinkron dengan model akhir) sudah digantikan oleh naskah ini.
