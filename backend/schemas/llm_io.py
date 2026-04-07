"""Structured output shapes for LLM calls (parsed into public audit models)."""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field, field_validator

from backend.schemas.audit import (
    CriterionScore,
    Finding,
    OutcomeScore,
    RAGRating,
    ConfidenceLevel,
)

logger = logging.getLogger(__name__)


class CriterionAssessment(BaseModel):
    """Per-criterion LLM assessment before server-side validation."""

    criterion_id: int = Field(ge=1)
    points_awarded: int = Field(ge=0, description="Must be 0 or the criterion max_points")
    met: bool
    rationale: str
    evidence: list[dict] = Field(
        default_factory=list,
        description='List of {"url": str, "quoted_text": str, "context": str | null}',
    )
    fca_source_ids: list[str] = Field(
        default_factory=list,
        description="Subset of source_id values from the prompt fca_sources list only",
    )

    @field_validator("criterion_id", mode="before")
    @classmethod
    def _coerce_id(cls, v: Any) -> int:
        if isinstance(v, str) and v.strip().isdigit():
            return int(v.strip())
        return v


class OutcomeLLMResult(BaseModel):
    """LLM output for one Consumer Duty outcome checklist."""

    criteria: list[CriterionAssessment] = Field(default_factory=list)
    summary: str = ""


class OutcomeGroqOutput(BaseModel):
    """Groq tool-call output for outcome scoring.

    Uses plain strings for ``confidence`` and ``rating`` so Groq's tool validator
    does not reject values that differ from strict JSON-schema enums (e.g. casing).
    Convert with :func:`outcome_from_groq_output` to :class:`~backend.schemas.audit.OutcomeScore`.
    """

    outcome_name: str = ""
    rating: str = Field(
        default="RED",
        description="RED, AMBER, or GREEN (informational; final rating is derived from score).",
    )
    score: int = Field(ge=0, le=10, description="Sum of criteria awarded_points (0–10).")
    confidence: str = Field(
        default="medium",
        description='Must be one of: "high", "medium", "low" (any common casing accepted).',
    )
    confidence_note: str = ""
    summary: str = ""
    criteria_scores: list[CriterionScore] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


def _coerce_criteria_sum_to_at_most_10(criteria: list[CriterionScore]) -> list[CriterionScore]:
    """Ensure the sum of awarded_points is at most 10 (LLMs sometimes exceed the cap)."""
    items = list(criteria)
    total = sum(c.awarded_points for c in items)
    if total <= 10:
        return items
    logger.warning(
        "Sum of criteria awarded_points is %s (>10); reducing highest buckets until total is 10",
        total,
    )
    while total > 10:
        idx = max(range(len(items)), key=lambda i: items[i].awarded_points)
        if items[idx].awarded_points <= 0:
            break
        c = items[idx]
        new_pts = c.awarded_points - 1
        items[idx] = c.model_copy(
            update={
                "awarded_points": new_pts,
                "met": new_pts == c.max_points,
            },
        )
        total -= 1
    return items


def _normalize_confidence_for_outcome(raw: str) -> ConfidenceLevel:
    s = (raw or "").strip().lower().replace(" ", "_")
    if s in ("high", "medium", "low"):
        return ConfidenceLevel(s)
    # Enum name e.g. HIGH
    for level in ConfidenceLevel:
        if s == level.name.lower():
            return level
    return ConfidenceLevel.LOW


def outcome_from_groq_output(raw: OutcomeGroqOutput) -> OutcomeScore:
    """Build a validated :class:`OutcomeScore` (rating is derived from score in validation).

    The headline ``score`` from the model is ignored when ``criteria_scores`` is non-empty:
    the outcome score is always the sum of ``awarded_points`` so it stays consistent with
    the checklist (Groq sometimes returns a mismatched top-level score).
    """
    criteria = _coerce_criteria_sum_to_at_most_10(list(raw.criteria_scores))
    if criteria:
        score = sum(c.awarded_points for c in criteria)
        if score != raw.score:
            logger.info(
                "Aligned outcome score with criteria sum: model score=%s, criteria_sum=%s (%s)",
                raw.score,
                score,
                raw.outcome_name or "?",
            )
    else:
        score = raw.score
    return OutcomeScore(
        outcome_name=raw.outcome_name,
        rating=RAGRating.RED,
        score=score,
        confidence=_normalize_confidence_for_outcome(raw.confidence),
        confidence_note=raw.confidence_note,
        summary=raw.summary,
        criteria_scores=criteria,
        findings=list(raw.findings),
        recommendations=list(raw.recommendations),
    )


class DarkPatternLLMItem(BaseModel):
    title: str
    description: str
    severity: str
    evidence: list[dict] = Field(default_factory=list)
    fca_source_ids: list[str] = Field(default_factory=list)
    recommendation: str = ""


class DarkPatternsLLMResult(BaseModel):
    findings: list[DarkPatternLLMItem] = Field(default_factory=list)


class VulnerabilityLLMItem(BaseModel):
    title: str
    description: str
    severity: str
    evidence: list[dict] = Field(default_factory=list)
    fca_source_ids: list[str] = Field(default_factory=list)
    recommendation: str = ""


class VulnerabilityLLMResult(BaseModel):
    findings: list[VulnerabilityLLMItem] = Field(default_factory=list)
