"""Retrieval quality tests: hybrid BM25+vector search against populated Chroma.

Run ``python -m backend.ingestion.fca_loader`` once before this suite.
Tests skip automatically when the collection is empty.
"""
from __future__ import annotations

import unittest

from backend.ingestion.fca_loader import retrieve_for_query, verify_chroma_populated
from backend.pipeline.outcome_queries import (
    CONSUMER_SUPPORT_QUERY,
    CONSUMER_UNDERSTANDING_QUERY,
    DARK_PATTERNS_QUERY,
    PRICE_VALUE_QUERY,
    PRODUCTS_SERVICES_QUERY,
    PS22_POLICY_QUERY,
    VULNERABILITY_QUERY,
)


def _base_label(document_label: str) -> str:
    """Strip page-number suffix: 'FG22/5, p.53' → 'FG22/5'."""
    return document_label.split(", p.")[0]


def _skip_if_not_populated():
    ok, msg = verify_chroma_populated()
    if not ok:
        raise unittest.SkipTest(
            f"ChromaDB not populated — run `python -m backend.ingestion.fca_loader` first. ({msg})"
        )


class TestRetrievalReturnsChunks(unittest.TestCase):
    """Basic smoke tests: every outcome query returns at least one chunk."""

    @classmethod
    def setUpClass(cls):
        _skip_if_not_populated()

    def _chunks(self, query: str, k: int = 6) -> list[dict]:
        return retrieve_for_query(query, k=k)

    def test_products_services_returns_chunks(self):
        chunks = self._chunks(PRODUCTS_SERVICES_QUERY)
        self.assertGreater(len(chunks), 0, "products_services query returned no chunks")

    def test_price_value_returns_chunks(self):
        chunks = self._chunks(PRICE_VALUE_QUERY)
        self.assertGreater(len(chunks), 0, "price_value query returned no chunks")

    def test_understanding_returns_chunks(self):
        chunks = self._chunks(CONSUMER_UNDERSTANDING_QUERY)
        self.assertGreater(len(chunks), 0, "understanding query returned no chunks")

    def test_support_returns_chunks(self):
        chunks = self._chunks(CONSUMER_SUPPORT_QUERY)
        self.assertGreater(len(chunks), 0, "support query returned no chunks")

    def test_vulnerability_returns_chunks(self):
        chunks = self._chunks(VULNERABILITY_QUERY)
        self.assertGreater(len(chunks), 0, "vulnerability query returned no chunks")

    def test_dark_patterns_returns_chunks(self):
        chunks = self._chunks(DARK_PATTERNS_QUERY)
        self.assertGreater(len(chunks), 0, "dark_patterns query returned no chunks")


class TestChunkMetadata(unittest.TestCase):
    """Each returned chunk must carry the fields the pipeline expects."""

    @classmethod
    def setUpClass(cls):
        _skip_if_not_populated()

    def test_chunk_fields_present(self):
        chunks = retrieve_for_query(PRODUCTS_SERVICES_QUERY, k=4)
        for chunk in chunks:
            with self.subTest(chunk_id=chunk.get("source_id")):
                self.assertIn("source_id", chunk)
                self.assertIn("text", chunk)
                self.assertIn("metadata", chunk)
                self.assertIn("document_label", chunk)
                self.assertTrue(chunk["text"].strip(), "chunk has empty text")

    def test_products_query_surfaces_core_rulebooks(self):
        chunks = retrieve_for_query(PRODUCTS_SERVICES_QUERY, k=6)
        bases = {_base_label(c["document_label"]) for c in chunks}
        self.assertTrue(bases, "expected at least one retrieved chunk")
        core = bases & {"FG22/5", "PS22/9"}
        self.assertTrue(
            core,
            f"products_services query should surface FG22/5 and/or PS22/9; got {bases}",
        )

    def test_chunk_citation_in_metadata(self):
        chunks = retrieve_for_query(PRICE_VALUE_QUERY, k=4)
        for chunk in chunks:
            meta = chunk.get("metadata", {})
            self.assertIn("citation", meta, "chunk metadata missing 'citation' key")
            self.assertTrue(meta["citation"].strip(), "chunk has empty citation in metadata")


class TestRetrievalRelevance(unittest.TestCase):
    """Assert that each outcome query surfaces at least one expected source document."""

    @classmethod
    def setUpClass(cls):
        _skip_if_not_populated()

    def _base_labels(self, query: str, k: int = 6) -> set[str]:
        return {_base_label(c["document_label"]) for c in retrieve_for_query(query, k=k)}

    def test_products_services_surfaces_fg22_5(self):
        labels = self._base_labels(PRODUCTS_SERVICES_QUERY)
        self.assertIn("FG22/5", labels, f"FG22/5 not in top results; got {labels}")

    def test_price_value_surfaces_fg22_5(self):
        labels = self._base_labels(PRICE_VALUE_QUERY)
        self.assertIn("FG22/5", labels, f"FG22/5 not in top results; got {labels}")

    def test_ps22_9_retrievable_with_policy_query(self):
        labels = self._base_labels(PS22_POLICY_QUERY)
        self.assertIn("PS22/9", labels, f"PS22/9 not in top results; got {labels}")

    def test_understanding_surfaces_understanding_doc(self):
        labels = self._base_labels(CONSUMER_UNDERSTANDING_QUERY)
        expected = {"Consumer Understanding Good Practice", "FG22/5"}
        overlap = labels & expected
        self.assertTrue(
            overlap,
            f"understanding query did not surface any of {expected}; got {labels}",
        )

    def test_support_surfaces_support_doc(self):
        labels = self._base_labels(CONSUMER_SUPPORT_QUERY)
        expected = {"Consumer Support Good Practice", "FG22/5"}
        overlap = labels & expected
        self.assertTrue(
            overlap,
            f"support query did not surface any of {expected}; got {labels}",
        )


if __name__ == "__main__":
    unittest.main()
