"""Tests for per-criterion FCA retrieval query generation."""

from __future__ import annotations

import unittest

from backend.pipeline.outcome_queries import criterion_queries_for_outcome


class TestPerCriterionQueries(unittest.TestCase):
    def test_ten_queries_per_outcome(self):
        for name in (
            "Products & Services",
            "Price & Value",
            "Consumer Understanding",
            "Consumer Support",
        ):
            queries = criterion_queries_for_outcome(name)
            self.assertEqual(len(queries), 10, name)
            self.assertEqual(len(set(queries)), 10, f"duplicate queries for {name}")


if __name__ == "__main__":
    unittest.main()
