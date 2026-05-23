"""Prompt and scorer alignment for accuracy benchmarking."""

from __future__ import annotations

import unittest
from pathlib import Path

from backend.pipeline.scorer import OUTCOME_CRITERIA, criteria_json, format_criteria_for_prompt

_PROMPTS = Path(__file__).resolve().parents[1] / "backend/prompts"
_OUTCOME_PROMPTS = (
    "products_services.txt",
    "price_value.txt",
    "understanding.txt",
    "support.txt",
)
_RAG_PROMPTS = ("dark_patterns.txt",)


class TestCriteriaAlignment(unittest.TestCase):
    def test_outcome_prompts_include_scoring_criteria_placeholder(self):
        for name in _OUTCOME_PROMPTS:
            text = (_PROMPTS / name).read_text(encoding="utf-8")
            self.assertIn("{scoring_criteria}", text, msg=name)
            self.assertTrue(
                "IDs 1–10" in text or "IDs 1-10" in text,
                msg=name,
            )

    def test_each_outcome_has_ten_criteria(self):
        for outcome, defs in OUTCOME_CRITERIA.items():
            self.assertEqual(len(defs), 10, outcome)

    def test_criteria_json_matches_defs(self):
        import json

        for outcome, defs in OUTCOME_CRITERIA.items():
            parsed = json.loads(criteria_json(defs))
            self.assertEqual(len(parsed), 10)
            self.assertEqual(parsed[0]["id"], 1)
            self.assertEqual(parsed[-1]["id"], 10)

    def test_format_criteria_lists_all_ids(self):
        defs = OUTCOME_CRITERIA["Price & Value"]
        block = format_criteria_for_prompt(defs)
        self.assertIn("Criterion 1", block)
        self.assertIn("Criterion 10", block)

    def test_dark_patterns_prompt_uses_fca_rag_placeholders(self):
        for name in _RAG_PROMPTS:
            text = (_PROMPTS / name).read_text(encoding="utf-8")
            self.assertIn("{fca_sources}", text, msg=name)
            self.assertIn("{fca_context}", text, msg=name)


if __name__ == "__main__":
    unittest.main()
