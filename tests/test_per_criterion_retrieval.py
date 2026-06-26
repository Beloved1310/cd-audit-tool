"""Tests for per-criterion and per-aspect FCA retrieval query generation."""

from __future__ import annotations

import unittest

from backend.pipeline.outcome_queries import (
    OUTCOME_ASPECTS,
    aspect_queries_for_outcome,
    criterion_queries_for_outcome,
    retrieval_queries_for_outcome,
)


class TestPerCriterionQueries(unittest.TestCase):
    def test_ten_queries_per_scored_outcome(self):
        for name in (
            "Products & Services",
            "Price & Value",
            "Consumer Understanding",
            "Consumer Support",
        ):
            queries = criterion_queries_for_outcome(name)
            self.assertEqual(len(queries), 10, name)
            self.assertEqual(len(set(queries)), 10, f"duplicate queries for {name}")


class TestPerAspectQueries(unittest.TestCase):
    def test_ten_queries_per_detection_stage(self):
        for name in OUTCOME_ASPECTS:
            queries = aspect_queries_for_outcome(name)
            self.assertEqual(len(queries), 10, name)
            self.assertEqual(len(set(queries)), 10, f"duplicate queries for {name}")
            self.assertTrue(all("Focus:" in q for q in queries), name)

    def test_retrieval_queries_unified_when_multi_enabled(self):
        for name in (
            "Products & Services",
            "Dark Patterns",
            "Vulnerability",
        ):
            queries = retrieval_queries_for_outcome(name, per_aspect_enabled=True)
            self.assertEqual(len(queries), 10, name)

    def test_retrieval_queries_single_when_disabled(self):
        queries = retrieval_queries_for_outcome("Dark Patterns", per_aspect_enabled=False)
        self.assertEqual(len(queries), 1)


if __name__ == "__main__":
    unittest.main()
