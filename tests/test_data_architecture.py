"""Uji arsitektur data: isi folder = peta jalur = lineage; lapisan mentah berupa teks murni; hash cocok; kontrak terpenuhi; jejak mentah -> kanonik utuh."""
import os
import unittest

import pandas as pd

from smdr import datapaths as dp, raw_export, registry

OPEN_OK = {"README.md", "run_manifest.json"}


class ArchitectureTest(unittest.TestCase):
    def test_every_file_in_data_is_registered_and_every_entry_exists(self):
        on_disk = {}
        for d, _, fs in os.walk(dp.DATA):
            for f in fs:
                if f in OPEN_OK or f == ".DS_Store":
                    continue
                on_disk[f] = os.path.relpath(d, dp.DATA)
        self.assertEqual(set(on_disk), set(dp.LAYOUT), "berkas di disk dan peta paths.LAYOUT harus sama")
        for f, folder in on_disk.items():
            self.assertEqual(folder, dp.LAYOUT[f], f)

    def test_file_names_unique_across_layers(self):
        self.assertEqual(len(dp.LAYOUT), len(set(dp.LAYOUT)))

    def test_raw_layer_is_plain_text(self):
        raws = [n for n in dp.LAYOUT if dp.layer_of(n) == "01_raw"]
        self.assertGreaterEqual(len(raws), 6)
        for n in raws:
            b = open(dp.table(n), "rb").read()
            self.assertNotIn(b"\x00", b, n)
            b.decode("utf-8")                       # harus UTF-8 sah
            self.assertNotIn(b"\r", b, n + ": akhir baris harus LF")
            self.assertTrue(n.endswith(".csv"))

    def test_lower_layers_are_text_csv_with_header(self):
        for n in dp.LAYOUT:
            if dp.layer_of(n) in ("00_registry", "02_curated", "03_canonical", "04_marts"):
                d = pd.read_csv(dp.table(n), nrows=3)
                self.assertGreater(len(d.columns), 0, n)

    def test_raw_hashes_match_source_registry(self):
        s = pd.read_csv(dp.table("sources.csv"), dtype=str, keep_default_na=False)
        seen = set()
        for r in s.itertuples():
            files = [x for x in r.raw_files.split(";") if x]
            hashes = [x for x in r.raw_sha256.split(";") if x]
            self.assertEqual(len(files), len(hashes), r.source_id)
            for f, h in zip(files, hashes):
                self.assertEqual(registry.sha256(dp.table(f)), h, f)
                seen.add(f)
        self.assertEqual(seen, {n for n in dp.LAYOUT if dp.layer_of(n) == "01_raw"}, "setiap berkas mentah harus terdaftar di sources.csv")

    def test_lineage_covers_every_table(self):
        l = pd.read_csv(dp.table("lineage.csv"))
        self.assertEqual(set(l["dataset"]), set(dp.LAYOUT) - set(registry.META))
        for r in l.itertuples():
            self.assertEqual(len(pd.read_csv(dp.table(r.dataset))), r.rows, r.dataset)
            self.assertTrue(r.produced_by)

    def test_dictionary_describes_core_tables(self):
        d = pd.read_csv(dp.table("dictionary.csv"), keep_default_na=False)
        for n in ("idx_line_items.csv", "fs_long.csv", "macro_monthly.csv", "scenario_results.csv", "covenant_quarterly.csv"):
            sub = d[d["dataset"] == n]
            self.assertTrue((sub["description_status"] == "kurasi").all(), n + ": kolom tabel inti harus berdeskripsi")

    def test_data_contracts_hold(self):
        self.assertEqual(registry.validate_contracts(), [])

    def test_canonical_values_trace_to_raw_rows(self):
        tested, mismatch, missing = raw_export.parity()
        self.assertGreater(tested, 2000)
        self.assertEqual((mismatch, missing), ([], []))


if __name__ == "__main__":
    unittest.main()
