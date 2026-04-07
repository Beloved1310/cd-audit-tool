import unittest

from backend.schemas.audit import RAGRating
from backend.schemas.llm_io import OutcomeGroqOutput, outcome_from_groq_output


class TestOutcomeFromGroqOutput(unittest.TestCase):
    def test_score_derived_from_criteria_when_model_score_mismatches(self):
        raw = OutcomeGroqOutput(
            outcome_name="Products & Services",
            score=6,
            confidence="high",
            summary="Summary",
            criteria_scores=[
                {
                    "criterion_id": 1,
                    "criterion_name": "A",
                    "max_points": 2,
                    "awarded_points": 2,
                    "met": True,
                    "evidence": "",
                    "page_url": "",
                },
                {
                    "criterion_id": 2,
                    "criterion_name": "B",
                    "max_points": 2,
                    "awarded_points": 2,
                    "met": True,
                    "evidence": "",
                    "page_url": "",
                },
            ],
        )
        out = outcome_from_groq_output(raw)
        self.assertEqual(out.score, 4)
        self.assertEqual(out.rating, RAGRating.RED)

    def test_coerces_when_criteria_sum_exceeds_10(self):
        raw = OutcomeGroqOutput(
            outcome_name="X",
            score=10,
            confidence="low",
            summary="S",
            criteria_scores=[
                {
                    "criterion_id": 1,
                    "criterion_name": "A",
                    "max_points": 5,
                    "awarded_points": 5,
                    "met": True,
                    "evidence": "",
                    "page_url": "",
                },
                {
                    "criterion_id": 2,
                    "criterion_name": "B",
                    "max_points": 5,
                    "awarded_points": 5,
                    "met": True,
                    "evidence": "",
                    "page_url": "",
                },
                {
                    "criterion_id": 3,
                    "criterion_name": "C",
                    "max_points": 5,
                    "awarded_points": 5,
                    "met": True,
                    "evidence": "",
                    "page_url": "",
                },
            ],
        )
        out = outcome_from_groq_output(raw)
        self.assertEqual(out.score, 10)
        self.assertEqual(sum(c.awarded_points for c in out.criteria_scores), 10)


if __name__ == "__main__":
    unittest.main()
