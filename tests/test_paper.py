"""Uji naskah: notebook terbangun tanpa error, tanpa token tersisa, persamaan Lampiran A lolos semua, dan angka kunci cocok dengan marts."""
import os
import re
import unittest

import nbformat
import pandas as pd

from smdr import datapaths as dp

PAPER = os.path.join(dp.ROOT, "notebooks", "paper.ipynb")


class PaperTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.path.exists(PAPER):
            raise unittest.SkipTest("paper.ipynb belum dibangun (python notebooks/build_paper.py)")
        cls.nb = nbformat.read(PAPER, 4)
        cls.text = "\n".join(c.source for c in cls.nb.cells if c.cell_type == "markdown")

    def test_no_error_outputs_and_has_figures_and_tables(self):
        outs = [o for c in self.nb.cells if c.cell_type == "code" for o in c.outputs]
        self.assertFalse([o for o in outs if o.output_type == "error"])
        self.assertGreaterEqual(sum(1 for o in outs if o.output_type == "display_data" and "image/png" in o.data), 6)
        self.assertGreaterEqual(sum(1 for o in outs if o.output_type == "display_data" and "|---" in o.data.get("text/markdown", "")), 10)

    def test_no_unfilled_tokens(self):
        self.assertEqual(re.findall(r"@\w+(?::\d)?@", self.text), [])

    def test_equation_verification_all_pass(self):
        txt = "".join(o.data.get("text/markdown", "") for c in self.nb.cells if c.cell_type == "code" for o in c.outputs if o.output_type == "display_data")
        a1 = txt[txt.index("Tabel A1"):]
        self.assertIn("PASS", a1)
        self.assertNotIn("FAIL", a1)

    def test_headline_numbers_match_marts(self):
        sr = pd.read_csv(dp.table("scenario_results.csv"))
        w = sr[(sr.skenario == "Permintaan lemah dan kelebihan kapasitas") & (sr.case == "central")].iloc[0]
        o = sr[(sr.skenario == "Kelebihan kapasitas") & (sr.case == "central")].iloc[0]
        idn = lambda x: ("%.2f" % x).replace(".", ",")
        self.assertIn(idn(w.nd_FY2027) + "x", self.text)
        self.assertIn(idn(o.nd_FY2027) + "x", self.text)

    def test_abstract_is_english(self):
        self.assertIn("**Abstract.** This study examines", self.text)


if __name__ == "__main__":
    unittest.main()
