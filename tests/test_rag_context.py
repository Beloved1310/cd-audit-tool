"""Tests for shared FCA retrieval configuration and compile-time criteria checks."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from backend.pipeline.scorer import PRODUCTS_SERVICES_CRITERIA, validate_outcome_criteria
from backend.pipeline.rag_context import build_fca_prompt_context
from backend.schemas.audit import ConfidenceLevel, CriterionScore, OutcomeScore, RAGRating
from langchain_core.documents import Document


class TestValidateOutcomeCriteria(unittest.TestCase):
    def _outcome(self, criteria: list[CriterionScore]) -> OutcomeScore:
        return OutcomeScore(
            outcome_name="Products & Services",
            rating=RAGRating.GREEN,
            score=sum(c.awarded_points for c in criteria),
            confidence=ConfidenceLevel.HIGH,
            summary="test",
            criteria_scores=criteria,
        )

    def test_valid_ten_rows_passes(self):
        criteria = [
            CriterionScore(
                criterion_id=d.criterion_id,
                criterion_name=d.name,
                max_points=d.max_points,
                awarded_points=1,
                met=True,
                evidence="e",
                page_url="https://x.test/",
            )
            for d in PRODUCTS_SERVICES_CRITERIA
        ]
        violations = validate_outcome_criteria(
            "Products & Services",
            criteria,
            PRODUCTS_SERVICES_CRITERIA,
        )
        self.assertEqual(violations, [])

    def test_missing_rows_reported(self):
        violations = validate_outcome_criteria(
            "Products & Services",
            [],
            PRODUCTS_SERVICES_CRITERIA,
        )
        self.assertTrue(any("expected 10" in v for v in violations))


class TestBuildFcaPromptContext(unittest.TestCase):
    def test_merges_multiple_queries(self):
        doc_a = Document(
            page_content="FG22/5 excerpt",
            metadata={"citation": "FG22/5, p.1"},
        )
        doc_b = Document(
            page_content="PS22/9 excerpt",
            metadata={"citation": "PS22/9, p.2"},
        )
        retriever = MagicMock()
        retriever.invoke.side_effect = [[doc_a], [doc_b]]

        ctx = build_fca_prompt_context(
            retriever,
            "query one",
            "query two",
            k_per_query=4,
            max_chunks=8,
        )
        self.assertEqual(ctx.chunk_count, 2)
        self.assertIn("FG22/5", ctx.fca_sources)
        self.assertIn("FG22/5 excerpt", ctx.fca_context)
        self.assertEqual(ctx.allowed_citations, ("FG22/5, p.1", "PS22/9, p.2"))
        self.assertEqual(retriever.invoke.call_count, 2)

    def test_empty_retrieval_returns_empty_context(self):
        retriever = MagicMock()
        retriever.invoke.return_value = []
        ctx = build_fca_prompt_context(retriever, "anything")
        self.assertEqual(ctx.chunk_count, 0)
        self.assertEqual(ctx.allowed_citations, ())
        self.assertEqual(ctx.fca_context, "")


if __name__ == "__main__":
    unittest.main()
