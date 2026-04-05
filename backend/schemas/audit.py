"""Pydantic models for Consumer Duty audit reports and API responses.

These types are the contract for persisted JSON, FastAPI responses, and the
downstream UI. Regulatory citations on :class:`Finding` must originate only
from retrieved FCA chunks (enforced in the pipeline, not in this module).
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal, Self

from pydantic import BaseModel, Field, model_validator


class RAGRating(str, Enum):
    """Traffic-light assessment derived from a 0–10 score scale."""

    RED = "RED"
    AMBER = "AMBER"
    GREEN = "GREEN"


class ConfidenceLevel(str, Enum):
    """How much site content was available when scoring an outcome."""

    HIGH = "high"  # 10+ pages crawled AND 5000+ words analysed
    MEDIUM = "medium"  # 5–9 pages OR 2000–4999 words (see scorer logic)
    LOW = "low"  # fewer than 5 pages OR under 2000 words


class AuditStatus(str, Enum):
    """Lifecycle status for a single-URL audit run."""

    COMPLETE = "complete"
    INSUFFICIENT_DATA = "insufficient_data"
    CRAWL_FAILED = "crawl_failed"


def rating_from_score_10(score: int) -> RAGRating:
    """Map a 0–10 score to RAG bands."""
    if score >= 8:
        return RAGRating.GREEN
    if score >= 5:
        return RAGRating.AMBER
    return RAGRating.RED


class CriterionScore(BaseModel):
    """One checklist row for an outcome; points are summed into the outcome score."""

    criterion_id: int = Field(ge=1)
    criterion_name: str
    max_points: int = Field(ge=0)
    awarded_points: int = Field(ge=0)
    met: bool = Field(
        description="True when awarded_points equals max_points for this criterion.",
    )
    evidence: str = Field(
        default="",
        description="Exact text from the website that informed this score.",
    )
    page_url: str = Field(
        default="",
        description="Page URL where evidence was found; empty if none.",
    )

    @model_validator(mode="after")
    def _points_range_and_met(self) -> Self:
        if self.awarded_points > self.max_points:
            raise ValueError("awarded_points cannot exceed max_points")
        expected = self.awarded_points == self.max_points
        if self.met is not expected:
            raise ValueError(
                "met must be True if and only if awarded_points == max_points",
            )
        return self


class Finding(BaseModel):
    """Structured issue tied to page evidence and a single FCA reference string."""

    description: str
    page_url: str
    evidence_text: str = Field(
        description="Verbatim extracted text from the page.",
    )
    fca_reference: str = Field(
        description='Chunk-grounded reference, e.g. "FG22/5 §3.2" or "Document.pdf, p.12".',
    )
    severity: Literal["critical", "moderate", "minor"]


class DarkPattern(BaseModel):
    """Suspected dark pattern or sludge; does not affect outcome checklist scores."""

    pattern_type: str = Field(
        description='Machine-oriented label, e.g. "urgency_manipulation".',
    )
    description: str
    page_url: str
    evidence_text: str = Field(
        description="Exact on-page text that triggered detection.",
    )


class VulnerabilityGap(BaseModel):
    """Gap in support for customers in vulnerable circumstances."""

    gap_type: str
    description: str
    fca_reference: str = Field(
        description="Duty-aligned reference string sourced from retrieved chunks only.",
    )


class OutcomeScore(BaseModel):
    """Scores and narrative for one Consumer Duty outcome (e.g. Understanding)."""

    outcome_name: str
    rating: RAGRating = Field(
        description="Always derived from score in validation (input value is overwritten).",
    )
    score: int = Field(ge=0, le=10, description="Sum of criteria awarded_points (0–10).")
    confidence: ConfidenceLevel
    confidence_note: str = Field(
        default="",
        description="Human-readable note on crawl depth, e.g. missing pricing page.",
    )
    summary: str
    criteria_scores: list[CriterionScore] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _score_matches_criteria_and_derive_rating(self) -> Self:
        total = sum(c.awarded_points for c in self.criteria_scores)
        if total != self.score:
            raise ValueError(
                f"score ({self.score}) must equal sum of criteria awarded_points ({total})",
            )
        self.rating = rating_from_score_10(self.score)
        return self


class AuditReport(BaseModel):
    """Full result of auditing one URL (complete, insufficient data, or crawl error)."""

    url: str
    audited_at: datetime
    status: AuditStatus
    overall_rating: RAGRating | None = Field(
        default=None,
        description="Populated when status is COMPLETE via compute_overall().",
    )
    overall_score: int | None = Field(
        default=None,
        description="Weighted 0–10 summary when status is COMPLETE.",
    )
    outcomes: list[OutcomeScore] = Field(default_factory=list)
    dark_patterns: list[DarkPattern] = Field(default_factory=list)
    vulnerability_gaps: list[VulnerabilityGap] = Field(default_factory=list)
    pages_crawled: list[str] = Field(
        default_factory=list,
        description="URLs of pages included in the crawl.",
    )
    total_words_analysed: int = Field(ge=0)
    crawl_duration_seconds: float = Field(ge=0)
    pipeline_duration_seconds: float = Field(ge=0)
    insufficient_data_reason: str | None = Field(
        default=None,
        description="Human-readable reason when status is INSUFFICIENT_DATA; also used for CRAWL_FAILED error text.",
    )

    def compute_overall(self) -> None:
        """Set overall_score (50/50 Understanding vs Support) and overall_rating.

        Raises:
            ValueError: If status is not COMPLETE or required outcomes are missing.
        """
        if self.status != AuditStatus.COMPLETE:
            raise ValueError("compute_overall() requires status COMPLETE")
        by_name = {o.outcome_name: o for o in self.outcomes}
        u = by_name.get("Consumer Understanding")
        s = by_name.get("Consumer Support")
        if u is None or s is None:
            raise ValueError(
                "compute_overall() requires outcomes 'Consumer Understanding' and 'Consumer Support'",
            )
        self.overall_score = int(round((u.score + s.score) / 2))
        self.overall_rating = rating_from_score_10(self.overall_score)


class ComparisonReport(BaseModel):
    """Side-by-side comparison of two completed audits for the same criteria."""

    url_a: str
    url_b: str
    compared_at: datetime
    report_a: AuditReport
    report_b: AuditReport
    winner_by_outcome: dict[str, str] = Field(
        default_factory=dict,
        description='Maps outcome_name to "url_a", "url_b", or "tied".',
    )
    overall_winner: str | None = Field(
        default=None,
        description='One of "url_a", "url_b", "tied", or None if either audit incomplete.',
    )

    def compute_comparison(self) -> None:
        """Fill winner_by_outcome and overall_winner from paired outcome scores."""
        ra, rb = self.report_a, self.report_b
        aw: dict[str, str] = {}

        by_a = {o.outcome_name: o for o in ra.outcomes}
        by_b = {o.outcome_name: o for o in rb.outcomes}
        for name in sorted(set(by_a) & set(by_b)):
            sa, sb = by_a[name].score, by_b[name].score
            if sa > sb:
                aw[name] = "url_a"
            elif sb > sa:
                aw[name] = "url_b"
            else:
                aw[name] = "tied"
        self.winner_by_outcome = aw

        if (
            ra.status == AuditStatus.COMPLETE
            and rb.status == AuditStatus.COMPLETE
            and ra.overall_score is not None
            and rb.overall_score is not None
        ):
            if ra.overall_score > rb.overall_score:
                self.overall_winner = "url_a"
            elif rb.overall_score > ra.overall_score:
                self.overall_winner = "url_b"
            else:
                self.overall_winner = "tied"
        else:
            self.overall_winner = None
