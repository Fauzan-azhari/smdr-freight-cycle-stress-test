"""Indeks freight rate kontainer untuk KRI pasar: pengambilan data publik dan ukuran posisi siklus.

Sumber dan batasnya (diakses 6 November 2026):
- Drewry World Container Index (komposit, USD per FEU, mingguan): grafik publik Drewry (Infogram) lewat paket akshare. Atribusi:
  "Source: Drewry World Container Index". Embed berhenti pada 10 Sep 2026; pembacaan 5 Nov 2026 (4.389) diambil dari halaman publik Drewry.
Tidak ada indeks publik untuk rute domestik Indonesia; indeks eksternal hanya penanda pasar, bukan pengganti yield internal SMDR.
"""
import pandas as pd


def fetch_wci_composite():
    import akshare as ak
    d = ak.drewry_wci_index(symbol="composite")
    d["date"] = pd.to_datetime(d["date"])
    return d.dropna().sort_values("date").reset_index(drop=True)


def position(series, window=52, short=4):
    """Posisi siklus indeks mingguan: nilai terkini, rata-rata pendek terhadap rata-rata `window` pekan, dan persentil dalam seluruh riwayat."""
    s = series.dropna().astype(float)
    cur, avg_s, avg_l = float(s.iloc[-1]), float(s.iloc[-short:].mean()), float(s.iloc[-window:].mean())
    return {"terkini": cur, "rata_pendek": avg_s, "rata_panjang": avg_l, "vs_rata_panjang": avg_s / avg_l - 1, "persentil": float((s <= cur).mean())}
