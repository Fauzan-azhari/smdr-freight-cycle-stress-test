import unittest

try:
    import needs_sources as ns
except ImportError:   # dijalankan sebagai tests.test_x
    from tests import needs_sources as ns
from smdr.transition import exposure as ex


class ExposureTest(unittest.TestCase):
    @ns.needs("Annual-Report")
    def test_every_evidence_token_is_found_on_its_recorded_pdf_page(self):
        self.assertEqual(ex.verify(), [])

    def test_evidence_table_is_complete_and_sourced(self):
        d = ex.load()
        self.assertEqual(len(d), len(ex.ITEMS))
        self.assertTrue(d["source_url"].str.startswith("https://").all())
        self.assertTrue((d["pdf_page"] > 0).all())

    def test_network_and_share(self):
        n = ex.network_table()
        self.assertEqual(int(n.loc["Indonesia (dari hub Singapura)", "Layanan"]), 7)
        self.assertEqual(int(n["Layanan"].sum()), 7 + 20 + 19 + 1 + 2)
        s = ex.ssl_share()
        self.assertAlmostEqual(s["share"], 605.7 / s["smdr"], places=9)
        self.assertTrue(0.7 < s["share"] < 0.8)                        # batas atas: sebelum eliminasi antargrup
        self.assertLess(s["container"], s["ssl"])
        self.assertAlmostEqual(s["liftings"], 2_062_000)

    def test_fleet_charter_matches_operating_data(self):
        c = ex.fleet_charter()
        self.assertEqual((c["owned"], c["chartered_in"], c["chartered_out"]), (27.0, 27.0, 12.0))


if __name__ == "__main__":
    unittest.main()
