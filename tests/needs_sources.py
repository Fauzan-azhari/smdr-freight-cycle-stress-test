"""Pembantu uji: lewati (bukan gagal) uji yang membutuhkan dokumen sumber lokal (PDF, Excel IDX) yang tidak dipublikasikan."""
import os
import unittest

from smdr import datapaths as dp


def have(*rel):
    return all(os.path.exists(os.path.join(dp.ROOT, r)) for r in rel)


def needs(*rel):
    """Dekorator: uji hanya dijalankan bila semua jalur relatif (terhadap akar repo) ada."""
    missing = [r for r in rel if not os.path.exists(os.path.join(dp.ROOT, r))]
    return unittest.skipIf(bool(missing), "dokumen sumber lokal tidak tersedia (%s): tingkat reproduksi 3" % (missing[0] if missing else ""))
