"""Unit tests for FCA PDF citation labels and corpus manifest (no Chroma / network)."""

from __future__ import annotations

import unittest

from backend.ingestion.fca_loader import _citation_label, corpus_manifest_digest


class TestCitationLabels(unittest.TestCase):
    def test_fg22_5_standard_filename(self):
        self.assertEqual(_citation_label("fg22-5.pdf"), "FG22/5")

    def test_ps22_9_standard_filename(self):
        self.assertEqual(_citation_label("ps22-9.pdf"), "PS22/9")

    def test_ps22_9_underscore_consumer_duty_filename(self):
        self.assertEqual(
            _citation_label("PS22_9_ A new Consumer Duty.pdf"),
            "PS22/9",
        )

    def test_understanding_good_practice(self):
        self.assertEqual(
            _citation_label("Consumer understanding good practice.pdf"),
            "Consumer Understanding Good Practice",
        )

    def test_portfolio_letter_fallback(self):
        self.assertEqual(
            _citation_label("consumer-duty-letter-credit-brokers.pdf"),
            "consumer duty letter credit brokers",
        )


class TestCorpusManifestDigest(unittest.TestCase):
    def test_digest_stable_for_same_dir(self):
        from backend.config import get_settings

        d = get_settings().fca_docs_dir
        self.assertEqual(corpus_manifest_digest(d), corpus_manifest_digest(d))


if __name__ == "__main__":
    unittest.main()
