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

    def test_pipeline_version_field_exists(self):
        from datetime import datetime, timezone

        from backend.schemas.audit import AuditReport, AuditStatus

        r = AuditReport(
            insufficient_data=False,
            url="https://example.com",
            audited_at=datetime.now(timezone.utc),
            pipeline_version="p_test",
            status=AuditStatus.COMPLETE,
            outcomes=[],
            dark_patterns=[],
            vulnerability_gaps=[],
            pages_crawled=[],
            total_words_analysed=0,
            crawl_duration_seconds=0.0,
            pipeline_duration_seconds=0.0,
        )
        self.assertEqual(r.pipeline_version, "p_test")


if __name__ == "__main__":
    unittest.main()

