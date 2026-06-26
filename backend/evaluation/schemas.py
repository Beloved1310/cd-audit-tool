"""Structured output of the evaluation harness."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ReportQualityMetrics(BaseModel):
    """Heuristic quality / grounding metrics on a completed :class:`~backend.schemas.audit.AuditReport`.

    These do not measure regulatory *correctness* vs human experts; they measure
    internal consistency and evidence density for regression and QA gates.
    """

    fixture_id: str = ""
    pipeline_version: str = ""

    four_outcomes_present: bool = False
    overall_score_matches_mean: bool = False

    criteria_total: int = 0
    criteria_with_evidence_when_partial_or_fail: float = Field(
        ge=0.0,
        le=1.0,
        description="Share of criteria with awarded<max that still have evidence or page_url.",
    )
    criteria_evidence_any: float = Field(
        ge=0.0,
        le=1.0,
        description="Share of all criteria rows with non-empty evidence or page_url.",
    )
    criteria_with_fca_reference: float = Field(
        ge=0.0,
        le=1.0,
        description="Share of awarded criteria (points > 0) with non-empty fca_reference.",
    )

    findings_total: int = 0
    findings_with_verbatim_evidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Share of findings with non-empty evidence_text.",
    )
    findings_with_fca_reference: float = Field(
        ge=0.0,
        le=1.0,
        description="Share of findings with non-empty fca_reference.",
    )

    dark_patterns_total: int = 0
    dark_patterns_with_evidence: float = Field(ge=0.0, le=1.0)

    vulnerability_gaps_total: int = 0
    vulnerability_gaps_with_fca: float = Field(ge=0.0, le=1.0)

    all_scores_in_0_10: bool = True
    rating_matches_score_bands: bool = True

    violations: list[str] = Field(default_factory=list)
    """Human-readable issues (empty means no violations under these checks)."""

    harness_score_0_100: int = Field(
        ge=0,
        le=100,
        description="Weighted aggregate for quick pass/fail gates in CI.",
    )
