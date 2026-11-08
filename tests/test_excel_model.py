"""Uji Financial Model Excel: berkas terbit memuat nilai, sheet asli utuh, dan hasil rumus hidup = model Python (via LibreOffice)."""
import os
import shutil
import tempfile
import unittest

import openpyxl

from smdr import excel_model as xm

HAVE_SOFFICE = shutil.which("soffice") is not None


class PublishedWorkbookTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.path.exists(xm.OUT):
            raise unittest.SkipTest("model/SMDR_Financial_Model.xlsx belum diterbitkan (python -m smdr.excel_model)")
        cls.wb = openpyxl.load_workbook(xm.OUT, data_only=True)

    def test_cached_values_present_and_checks_pass(self):
        self.assertEqual(self.wb["Cek"]["C4"].value, "54 PASS, 0 GAGAL")
        self.assertAlmostEqual(self.wb["Dashboard"]["C10"].value, 3.4119, places=3)

    def test_no_error_values_in_model_sheets(self):
        for ws in self.wb.worksheets:
            if ws.title in ("Catatan", "Data Sumber"):
                continue
            for row in ws.iter_rows():
                for c in row:
                    self.assertFalse(isinstance(c.value, str) and c.value.startswith("#"), f"{ws.title}!{c.coordinate} {c.value}")

    def test_original_statement_sheets_unchanged(self):
        src = openpyxl.load_workbook(xm.SOURCE)
        out = openpyxl.load_workbook(xm.OUT)
        for ws in src.worksheets:
            wo = out[ws.title]
            for row in ws.iter_rows():
                for c in row:
                    if c.value is not None:
                        self.assertEqual(wo[c.coordinate].value, c.value, f"{ws.title}!{c.coordinate}")


@unittest.skipUnless(HAVE_SOFFICE, "LibreOffice tidak terpasang")
class FormulaParityTest(unittest.TestCase):
    def test_live_formulas_match_python_model(self):
        tmp = tempfile.mkdtemp(prefix="smdr_xl_test_")
        try:
            maps = xm.build(os.path.join(tmp, "m.xlsx"))
            calc = xm.recalc(os.path.join(tmp, "m.xlsx"), os.path.join(tmp, "calc"))
            for name, fn in (("B1", xm.check_b1), ("B2", xm.check_b2), ("B3", xm.check_b3)):
                n, bad = fn(calc, maps)
                self.assertGreater(n, 500, name)
                self.assertEqual(bad, [], name)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
