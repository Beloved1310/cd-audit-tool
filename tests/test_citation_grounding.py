"""Unit tests for citation grounding and RAG ablation detection."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone

from backend.pipeline.citation_grounding import (
    apply_outcome_citation_grounding,
    citation_is_grounded,
    ground_dark_patterns,
    ground_vulnerability_gaps,
    parse_numbered_fca_sources,
)
from backend.evaluation.rag_ablation import compare_rag_ablation
from backend.schemas.audit import (
    AuditReport,
    AuditStatus,
    ConfidenceLevel,
    CriterionScore,
    DarkPattern,
    Finding,
    OutcomeScore,
    RAGRating,
    VulnerabilityGap,
)


class TestCitationGrounding(unittest.TestCase):
    def test_parse_numbered_sources(self):
        text = "1. FG22/5, p.12\n2. PS22/9, p.3\n"
        self.assertEqual(parse_numbered_fca_sources(text), ["FG22/5, p.12", "PS22/9, p.3"])

    def test_exact_and_base_match(self):
        allowed = ["FG22/5, p.53", "PS22/9, p.1"]
        self.assertTrue(citation_is_grounded("FG22/5, p.53", allowed))
        self.assertTrue(citation_is_grounded("FG22/5", allowed))
        self.assertFalse(citation_is_grounded("FG21/1, p.1", allowed))

    def test_removes_ungrounded_findings_and_downgrades(self):
        outcome = OutcomeScore(
            outcome_name="Consumer Support",
            rating=RAGRating.GREEN,
            score=0,
            confidence=ConfidenceLevel.HIGH,
            summary="s",
            criteria_scores=[],
            findings=[
                Finding(
                    description="bad cite",
                    page_url="https://x.test/",
                    evidence_text="text",
                    fca_reference="Invented Doc, p.99",
                    severity="moderate",
                ),
                Finding(
                    description="good cite",
                    page_url="https://x.test/",
                    evidence_text="text",
                    fca_reference="FG22/5, p.12",
                    severity="minor",
                ),
            ],
        )
        grounded, note = apply_outcome_citation_grounding(
            outcome,
            ["FG22/5, p.12"],
        )
        self.assertEqual(len(grounded.findings), 1)
        self.assertEqual(grounded.findings[0].fca_reference, "FG22/5, p.12")
        self.assertEqual(grounded.confidence, ConfidenceLevel.MEDIUM)
        self.assertIn("removed", note.lower())

    def test_ground_dark_patterns(self):
        patterns = [
            DarkPattern(
                pattern_type="hidden_fee",
                description="d",
                page_url="https://x.test/",
                evidence_text="e",
                fca_reference="FG22/5",
            ),
            DarkPattern(
                pattern_type="bad",
                description="d",
                page_url="https://x.test/",
                evidence_text="e",
                fca_reference="Fake",
            ),
        ]
        kept = ground_dark_patterns(patterns, ["FG22/5, p.1"])
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0].pattern_type, "hidden_fee")

    def test_ground_vulnerability_gaps(self):
        gaps = [
            VulnerabilityGap(
                gap_type="accessibility",
                description="d",
                fca_reference="Consumer Support Good Practice, p.2",
            ),
            VulnerabilityGap(gap_type="x", description="d", fca_reference="Not Retrieved"),
        ]
        kept = ground_vulnerability_gaps(
            gaps,
            ["Consumer Support Good Practice, p.2"],
        )
        self.assertEqual(len(kept), 1)


class TestRagAblationDetection(unittest.TestCase):
    def _report(self, *, scores: tuple[int, int, int, int], findings: int, cite: str) -> AuditReport:
        names = (
            "Products & Services",
            "Price & Value",
            "Consumer Understanding",
            "Consumer Support",
        )
        outcomes = []
        for name, score in zip(names, scores):
            findings_list = []
            if findings:
                findings_list = [
                    Finding(
                        description="f",
                        page_url="https://x.test/",
                        evidence_text="e",
                        fca_reference=cite if cite else "",
                        severity="minor",
                    ),
                ]
            criteria = [
                CriterionScore(
                    criterion_id=i,
                    criterion_name=f"c{i}",
                    max_points=1,
                    awarded_points=1 if i <= score else 0,
                    met=i <= score,
                    evidence="e",
                    page_url="https://x.test/",
                )
                for i in range(1, 11)
            ]
            outcomes.append(
                OutcomeScore(
                    outcome_name=name,
                    rating=RAGRating.GREEN,
                    score=score,
                    confidence=ConfidenceLevel.HIGH,
                    summary="s",
                    criteria_scores=criteria,
                    findings=findings_list,
                ),
            )
        return AuditReport(
            url="https://x.test/",
            audited_at=datetime.now(timezone.utc),
            status=AuditStatus.COMPLETE,
            overall_score=7,
            overall_rating=RAGRating.GREEN,
            outcomes=outcomes,
            dark_patterns=[],
            vulnerability_gaps=[],
            pages_crawled=["https://x.test/"],
            total_words_analysed=5000,
            crawl_duration_seconds=1.0,
            pipeline_duration_seconds=1.0,
        )

    def test_detects_decorative_rag(self):
        report = self._report(scores=(7, 7, 7, 7), findings=1, cite="FG22/5")
        result = compare_rag_ablation(
            site_id="t",
            with_rag=report,
            without_rag=report,
            min_score_delta=0.25,
            min_citation_delta=0.05,
        )
        self.assertTrue(result.rag_decorative)

    def test_detects_meaningful_rag_delta(self):
        with_rag = self._report(scores=(8, 8, 8, 8), findings=1, cite="FG22/5")
        without = self._report(scores=(4, 4, 4, 4), findings=0, cite="")
        result = compare_rag_ablation(
            site_id="t",
            with_rag=with_rag,
            without_rag=without,
        )
        self.assertFalse(result.rag_decorative)
        self.assertGreater(result.score_mae, 0.25)


if __name__ == "__main__":
    unittest.main()
