"""Unit tests for hybrid RRF fusion (no Chroma required)."""

from __future__ import annotations

import unittest

from langchain_core.documents import Document

from backend.ingestion.hybrid_retriever import reciprocal_rank_fusion


class TestReciprocalRankFusion(unittest.TestCase):
    def test_prefers_docs_ranked_high_in_both_lists(self):
        shared = Document(page_content="shared", metadata={"citation": "FG22/5, p.1"})
        vector_only = Document(page_content="v", metadata={"citation": "PS22/9, p.2"})
        bm25_only = Document(page_content="b", metadata={"citation": "FG22/5, p.3"})
        merged = reciprocal_rank_fusion(
            [[shared, vector_only], [shared, bm25_only]],
            max_docs=2,
            rrf_k=60,
        )
        self.assertEqual(len(merged), 2)
        self.assertEqual(_doc_key(merged[0]), "FG22/5, p.1")

    def test_respects_max_docs(self):
        docs = [
            Document(page_content=f"c{i}", metadata={"citation": f"Doc, p.{i}"})
            for i in range(5)
        ]
        merged = reciprocal_rank_fusion([docs], max_docs=3, rrf_k=60)
        self.assertEqual(len(merged), 3)


def _doc_key(doc: Document) -> str:
    return str(doc.metadata.get("citation"))


if __name__ == "__main__":
    unittest.main()
