import unittest


class TestUrlNormalisation(unittest.TestCase):
    def test_canonical_url_drops_fragment_and_default_port(self):
        from backend.util.url_norm import canonical_url

        self.assertEqual(
            canonical_url("https://Example.COM:443/path#section"),
            "https://example.com/path",
        )

    def test_canonical_url_ensures_root_path(self):
        from backend.util.url_norm import canonical_url

        self.assertEqual(canonical_url("https://example.com"), "https://example.com/")


if __name__ == "__main__":
    unittest.main()

