"""Uji lapisan data laporan keuangan. Jalankan ingest dan cek terlebih dahulu:

    PYTHONPATH=src python3 -m smdr.fs_ingest && PYTHONPATH=src python3 -m smdr.fs_checks
    PYTHONPATH=src python3 -m unittest discover -s tests
"""
import csv
import os
import unittest

from smdr import datapaths, fs_checks
from smdr.fs_lines import STATEMENTS



def read(name):
    with open(datapaths.table(name), encoding="utf-8") as f:
        return list(csv.DictReader(f))


class DictionaryTest(unittest.TestCase):
    def test_keys_unique_within_statement(self):
        for stmt, lines in STATEMENTS.items():
            keys = [k for _, k, _, _ in lines]
            self.assertEqual(len(keys), len(set(keys)), stmt)

    def test_parents_exist(self):
        for stmt, lines in STATEMENTS.items():
            keys = {k for _, k, _, _ in lines}
            for _, k, parent, _ in lines:
                if parent:
                    self.assertIn(parent.split("#")[0], keys, "%s.%s" % (stmt, k))


class TidyDataTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = read("fs_long.csv")
        cls.val = {(r["statement"], r["line_key"], r["period"]): r for r in cls.rows}

    def amount(self, stmt, key, period):
        return float(self.val[(stmt, key, period)]["value_usd"])

    def test_known_figures(self):
        self.assertEqual(self.amount("IS", "revenue", "9M26"), 647373561)
        self.assertEqual(self.amount("IS", "revenue", "9M25"), 571556818)
        self.assertEqual(self.amount("BS", "total_assets", "9M26"), 1502603871)
        self.assertEqual(self.amount("COGS_NOTE", "depreciation", "9M26"), 110098581)

    def test_ebit_definition(self):
        # EBIT = laba bruto - beban umum dan administrasi (workbook tidak punya baris EBIT)
        ebit = self.amount("IS", "gross_profit", "9M26") - self.amount("IS", "ga_expense", "9M26")
        self.assertAlmostEqual(ebit, 75382160, delta=1)

    def test_nd_is_not_zero(self):
        cell = self.val[("IS", "other_income", "9M26")]
        self.assertEqual(cell["status"], "nd")
        self.assertEqual(cell["value_usd"], "")

    def test_every_reported_value_has_source(self):
        for r in self.rows:
            if r["status"] == "reported":
                self.assertTrue(r["source_file_id"] and r["source_cell"], r["workbook_cell"])

    def test_source_files_match_hash(self):
        for m in read("fs_source_manifest.csv"):
            self.assertEqual(m["hash_check"], "OK", m["file_id"])


class ChecksTest(unittest.TestCase):
    def test_no_unexplained_failures(self):
        values, dictionary = fs_checks.load()
        results = fs_checks.run_checks(values, dictionary)
        exceptions = fs_checks.load_exceptions()
        failed = [r for r in results if r["status"] == "FAIL" and (r["check_id"], r["period"]) not in exceptions]
        self.assertEqual(failed, [])
        self.assertGreater(len(results), 200)


if __name__ == "__main__":
    unittest.main()
