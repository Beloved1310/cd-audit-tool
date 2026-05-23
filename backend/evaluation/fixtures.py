"""Build audit reports from ground truth for offline accuracy tests (no LLM)."""

from __future__ import annotations

from datetime import datetime, timezone

from backend.evaluation.ground_truth import GroundTruthLabel, _REQUIRED_OUTCOMES
from backend.pipeline.scorer import criteria_defs_for_outcome
from backend.schemas.audit import (
    AuditReport,
    AuditStatus,
    ConfidenceLevel,
    CriterionScore,
    OutcomeScore,
    RAGRating,
    rating_from_score_10,
)


def audit_report_from_ground_truth(
    label: GroundTruthLabel,
    *,
    pipeline_version: str = "accuracy_fixture",
) -> AuditReport:
    """Synthetic COMPLETE report whose per-criterion scores mirror expert labels."""
    outcomes: list[OutcomeScore] = []
    for outcome_name in _REQUIRED_OUTCOMES:
        defs = criteria_defs_for_outcome(outcome_name)
        outcome_label = label.outcomes[outcome_name]
        criteria_scores: list[CriterionScore] = []
        for d in defs:
            crit = outcome_label.criteria[str(d.criterion_id)]
            awarded = min(crit.awarded, d.max_points)
            criteria_scores.append(
                CriterionScore(
                    criterion_id=d.criterion_id,
                    criterion_name=d.name,
                    max_points=d.max_points,
                    awarded_points=awarded,
                    met=awarded == d.max_points,
                    evidence=crit.note or "Fixture evidence.",
                    page_url=label.url,
                ),
            )
        score = sum(c.awarded_points for c in criteria_scores)
        outcomes.append(
            OutcomeScore(
                outcome_name=outcome_name,
                rating=rating_from_score_10(score),
                score=score,
                confidence=ConfidenceLevel.HIGH,
                confidence_note="Fixture derived from ground truth.",
                summary=outcome_label.notes or "Fixture outcome.",
                criteria_scores=criteria_scores,
                findings=[],
                recommendations=[],
            ),
        )

    overall = label.overall_score()
    return AuditReport(
        insufficient_data=False,
        url=label.url,
        audited_at=datetime.now(timezone.utc),
        pipeline_version=pipeline_version,
        status=AuditStatus.COMPLETE,
        overall_rating=rating_from_score_10(overall),
        overall_score=overall,
        pages_crawled=[label.url],
        total_words_analysed=5000,
        crawl_duration_seconds=1.0,
        pipeline_duration_seconds=1.0,
        outcomes=outcomes,
        dark_patterns=[],
        vulnerability_gaps=[],
    )
