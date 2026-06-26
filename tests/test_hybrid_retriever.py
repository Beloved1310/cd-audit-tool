"""Unit tests for hybrid RRF fusion (no Chroma required)."""

from __future__ import annotations

import importlib.util
import unittest

from langchain_core.documents import Document

from backend.ingestion.hybrid_retriever import HybridFcaRetriever, reciprocal_rank_fusion


def _rank_bm25_available() -> bool:
    return importlib.util.find_spec("rank_bm25") is not None


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


class TestHybridRetrieverBuild(unittest.TestCase):
    @unittest.skipUnless(_rank_bm25_available(), "rank-bm25 not installed")
    def test_build_hybrid_retriever_uses_fusion(self):
        from backend.config import get_settings
        from backend.ingestion.fca_loader import get_retriever, load_fca_docs, verify_chroma_populated
        from backend.ingestion.hybrid_retriever import build_hybrid_retriever

        ok, msg = verify_chroma_populated()
        if not ok:
            raise unittest.SkipTest(msg)

        settings = get_settings()
        chroma = load_fca_docs(str(settings.fca_docs_dir))
        retriever = build_hybrid_retriever(chroma, k=4)
        self.assertIsInstance(retriever, HybridFcaRetriever)

        via_loader = get_retriever(chroma, k=4)
        self.assertIsInstance(via_loader, HybridFcaRetriever)


if __name__ == "__main__":
    unittest.main()
