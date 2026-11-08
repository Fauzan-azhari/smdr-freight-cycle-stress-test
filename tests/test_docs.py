"""Uji dokumen: angka kunci pada README dan model card sama dengan marts (tidak diketik lepas dari model)."""
import os
import unittest

import pandas as pd

from smdr import datapaths as dp

ROOT = dp.ROOT


def idn(x, d):
    return f"{x:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")


class DocsNumbersTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.readme = open(os.path.join(ROOT, "README.md"), encoding="utf-8").read()
        cls.card = open(os.path.join(ROOT, "docs", "model-card.md"), encoding="utf-8").read()
        cls.sr = pd.read_csv(dp.table("scenario_results.csv"))
        cls.bt = pd.read_csv(dp.table("backtest.csv")).set_index("periode")

    def _row(self, k, case="central"):
        return self.sr[(self.sr.skenario == k) & (self.sr.case == case)].iloc[0]

    def test_readme_headline_numbers_match_marts(self):
        ovr, wrs = self._row("Kelebihan kapasitas"), self._row("Permintaan lemah dan kelebihan kapasitas")
        for txt in (idn(ovr.nd_FY2027, 2) + "x", idn(wrs.nd_FY2027, 2) + "x"):
            self.assertIn(txt, self.readme)
        c = self.sr[self.sr.case == "central"]
        self.assertIn(idn(min(c.cover_FY2027.min(), c.cover_FY2028.min()), 2) + "x", self.readme)
        self.assertIn(idn(c.current_ratio_min.min(), 2) + "x", self.readme)
        self.assertIn("USD " + idn(c.min_liquidity.min(), 0) + " juta", self.readme)

    def test_headroom_and_backtest_numbers(self):
        for p, txt in (("FY2023", "1,9"), ("FY2024", "1,3")):
            self.assertIn(idn(self.bt.loc[p, "model"] / self.bt.loc[p, "terealisasi"], 1), (txt,))
            self.assertIn(txt + "×", self.readme + self.card)
        self.assertIn("11,8%", self.readme)

    def test_model_card_links_exist(self):
        for rel in ("docs/adr/ADR-001-model-struktural.md", "docs/data-treatment.md", "CHANGELOG.md", "notebooks/paper.html"):
            self.assertTrue(os.path.exists(os.path.join(ROOT, rel)), rel)


if __name__ == "__main__":
    unittest.main()
