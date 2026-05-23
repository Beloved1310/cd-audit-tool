"""Retrieval quality tests: assert each pipeline node's fixed query returns relevant FCA chunks.

These are integration tests that require ChromaDB to be populated.
Run `python -m backend.ingestion.fca_loader` once before running this suite.
Tests are skipped automatically when the collection is empty.
"""
from __future__ import annotations

import unittest

from backend.ingestion.fca_loader import retrieve_for_query, verify_chroma_populated

# Hardcoded from each node's module-level _QUERY — update here if a node's query changes.
_QUERY_PRODUCTS_SERVICES = (
    "PRIN 2A.2 products services target market design retail "
    "FG22/5 outcome manufacture distribution vulnerability "
    "fair value product governance closed products"
)
_QUERY_PRICE_VALUE = (
    "PRIN 2A.3 price value fair value fees charges costs "
    "FG22/5 PS22/9 APR interest total cost comparison "
    "introductory rate sludge transparency"
)
_QUERY_UNDERSTANDING = (
    "consumer understanding plain language risk warnings "
    "fee disclosure informed decisions promotional balance"
)
_QUERY_SUPPORT = (
    "consumer support complaints accessibility vulnerable "
    "customers contact channels ease of exit"
)
_QUERY_VULNERABILITY = (
    "vulnerable customers financial difficulty accessibility "
    "support obligations signposting"
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
    """Basic smoke tests: every node query returns at least one chunk."""

    @classmethod
    def setUpClass(cls):
        _skip_if_not_populated()

    def _chunks(self, query: str, k: int = 6) -> list[dict]:
        return retrieve_for_query(query, k=k)

    def test_products_services_returns_chunks(self):
        chunks = self._chunks(_QUERY_PRODUCTS_SERVICES)
        self.assertGreater(len(chunks), 0, "products_services query returned no chunks")

    def test_price_value_returns_chunks(self):
        chunks = self._chunks(_QUERY_PRICE_VALUE)
        self.assertGreater(len(chunks), 0, "price_value query returned no chunks")

    def test_understanding_returns_chunks(self):
        chunks = self._chunks(_QUERY_UNDERSTANDING)
        self.assertGreater(len(chunks), 0, "understanding query returned no chunks")

    def test_support_returns_chunks(self):
        chunks = self._chunks(_QUERY_SUPPORT)
        self.assertGreater(len(chunks), 0, "support query returned no chunks")

    def test_vulnerability_returns_chunks(self):
        chunks = self._chunks(_QUERY_VULNERABILITY)
        self.assertGreater(len(chunks), 0, "vulnerability query returned no chunks")


class TestChunkMetadata(unittest.TestCase):
    """Each returned chunk must carry the fields the pipeline expects."""

    @classmethod
    def setUpClass(cls):
        _skip_if_not_populated()

    def test_chunk_fields_present(self):
        chunks = retrieve_for_query(_QUERY_PRODUCTS_SERVICES, k=4)
        for chunk in chunks:
            with self.subTest(chunk_id=chunk.get("source_id")):
                self.assertIn("source_id", chunk)
                self.assertIn("text", chunk)
                self.assertIn("metadata", chunk)
                self.assertIn("document_label", chunk)
                self.assertTrue(chunk["text"].strip(), "chunk has empty text")

    def test_products_query_surfaces_core_rulebooks(self):
        chunks = retrieve_for_query(_QUERY_PRODUCTS_SERVICES, k=6)
        bases = {_base_label(c["document_label"]) for c in chunks}
        self.assertTrue(bases, "expected at least one retrieved chunk")
        core = bases & {"FG22/5", "PS22/9"}
        self.assertTrue(
            core,
            f"products_services query should surface FG22/5 and/or PS22/9; got {bases}",
        )

    def test_chunk_citation_in_metadata(self):
        chunks = retrieve_for_query(_QUERY_PRICE_VALUE, k=4)
        for chunk in chunks:
            meta = chunk.get("metadata", {})
            self.assertIn("citation", meta, "chunk metadata missing 'citation' key")
            self.assertTrue(meta["citation"].strip(), "chunk has empty citation in metadata")


class TestRetrievalRelevance(unittest.TestCase):
    """Assert that each node's query surfaces at least one expected source document."""

    @classmethod
    def setUpClass(cls):
        _skip_if_not_populated()

    def _base_labels(self, query: str, k: int = 6) -> set[str]:
        return {_base_label(c["document_label"]) for c in retrieve_for_query(query, k=k)}

    def test_products_services_surfaces_fg22_5(self):
        labels = self._base_labels(_QUERY_PRODUCTS_SERVICES)
        self.assertIn("FG22/5", labels, f"FG22/5 not in top results; got {labels}")

    def test_price_value_surfaces_fg22_5(self):
        labels = self._base_labels(_QUERY_PRICE_VALUE)
        self.assertIn("FG22/5", labels, f"FG22/5 not in top results; got {labels}")

    def test_ps22_9_retrievable_with_policy_query(self):
        """PS22/9 is a smaller doc; a dedicated query must surface it after ingest."""
        labels = self._base_labels("PS22/9 Consumer Duty policy statement rules framework")
        self.assertIn("PS22/9", labels, f"PS22/9 not in top results; got {labels}")

    def test_understanding_surfaces_understanding_doc(self):
        labels = self._base_labels(_QUERY_UNDERSTANDING)
        expected = {"Consumer Understanding Good Practice", "FG22/5"}
        overlap = labels & expected
        self.assertTrue(
            overlap,
            f"understanding query did not surface any of {expected}; got {labels}",
        )

    def test_support_surfaces_support_doc(self):
        labels = self._base_labels(_QUERY_SUPPORT)
        expected = {"Consumer Support Good Practice", "FG22/5"}
        overlap = labels & expected
        self.assertTrue(
            overlap,
            f"support query did not surface any of {expected}; got {labels}",
        )


if __name__ == "__main__":
    unittest.main()
