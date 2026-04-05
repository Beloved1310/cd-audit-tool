"""Structured output shapes for LLM calls (parsed into public audit models)."""

from typing import Any

from pydantic import BaseModel, Field, field_validator


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
