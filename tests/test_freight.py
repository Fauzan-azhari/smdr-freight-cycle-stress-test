import unittest

import pandas as pd

from smdr import freight


class TestFreight(unittest.TestCase):
    def test_position(self):
        s = pd.Series([100.0] * 48 + [120.0] * 4)
        p = freight.position(s, window=52, short=4)
        self.assertAlmostEqual(p["rata_pendek"], 120.0)
        self.assertAlmostEqual(p["vs_rata_panjang"], 120.0 / (100.0 * 48 / 52 + 120.0 * 4 / 52) - 1)
        self.assertAlmostEqual(p["persentil"], 1.0)


if __name__ == "__main__":
    unittest.main()
