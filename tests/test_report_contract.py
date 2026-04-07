import unittest


class TestReportContract(unittest.TestCase):
    def test_outcome_scope_fields_exist(self):
        from backend.schemas.audit import ConfidenceLevel, OutcomeScore, RAGRating

        o = OutcomeScore(
            outcome_name="Consumer Understanding",
            rating=RAGRating.RED,
            score=0,
            confidence=ConfidenceLevel.LOW,
            confidence_note="",
            summary="",
            criteria_scores=[],
            findings=[],
            recommendations=[],
        )
        # Defaults should exist and be serialisable.
        self.assertTrue(hasattr(o, "assessment_scope"))
        self.assertTrue(hasattr(o, "scope_note"))
        self.assertEqual(o.assessment_scope, "public_website_only")


if __name__ == "__main__":
    unittest.main()

