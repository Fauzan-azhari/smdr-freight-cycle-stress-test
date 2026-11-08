import unittest

from smdr import baseline
from smdr.transition import covenants as cv


class TestCovenants(unittest.TestCase):
    def test_nd_ebitda_reproduces_reported(self):
        w = baseline.load_wide()
        from smdr import covenant_band as cb
        e22 = cb.ebitda_operating(w, "FY2022") / 1e6
        e25 = cb.ebitda_operating(w, "FY2025") / 1e6
        self.assertAlmostEqual(cv.reported_nd_ebitda(w, "FY2022", e22), 0.66, places=2)
        self.assertAlmostEqual(cv.reported_nd_ebitda(w, "FY2025", e25), 2.52, places=2)

    def test_cure_requirement(self):
        self.assertEqual(cv.cure_requirement({"penyebut": 100.0, "ebitda": 120.0}), 0.0)
        self.assertAlmostEqual(cv.cure_requirement({"penyebut": 100.0, "ebitda": 99.0}), 10.0)


if __name__ == "__main__":
    unittest.main()
