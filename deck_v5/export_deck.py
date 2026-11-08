"""Gabungkan delapan slide PNG menjadi satu berkas PPTX dan PDF.

Keluar : deck_v5/export/SMDR_Stress_Test_Deck.{pptx,pdf}  (slide penutup tanpa email)
         deck_v5/out_private/SMDR_Stress_Test_Deck_presentasi.{pptx,pdf}  (tidak dilacak git; hanya bila slide_07 pribadi ada)
Catatan: tiap slide adalah gambar penuh 150 dpi, sehingga teks tidak dapat disunting di PowerPoint.
Butuh python-pptx (requirements-optional.txt).  Jalankan:  cd deck_v5 && python export_deck.py
"""
import os

from PIL import Image
from pptx import Presentation
from pptx.util import Inches

HERE = os.path.dirname(os.path.abspath(__file__))
N = 8


def build(files, stem, outdir):
    os.makedirs(outdir, exist_ok=True)
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    for f in files:
        s = prs.slides.add_slide(prs.slide_layouts[6])
        s.shapes.add_picture(f, 0, 0, prs.slide_width, prs.slide_height)
    prs.save(os.path.join(outdir, stem + ".pptx"))
    ims = [Image.open(f).convert("RGB") for f in files]
    ims[0].save(os.path.join(outdir, stem + ".pdf"), save_all=True, append_images=ims[1:], resolution=150)
    print("ok", os.path.join(outdir, stem))


if __name__ == "__main__":
    base = [os.path.join(HERE, "out", f"slide_{i:02d}.png") for i in range(N)]
    build(base, "SMDR_Stress_Test_Deck", os.path.join(HERE, "export"))
    priv = os.path.join(HERE, "out_private", "slide_07.png")
    if os.path.exists(priv):
        build(base[:-1] + [priv], "SMDR_Stress_Test_Deck_presentasi", os.path.join(HERE, "out_private"))
