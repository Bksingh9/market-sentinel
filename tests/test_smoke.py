import unittest


class SmokeTest(unittest.TestCase):
    def test_package_exposes_version(self):
        import market_sentinel

        self.assertEqual(market_sentinel.__version__, "0.1.0")


if __name__ == "__main__":
    unittest.main()
