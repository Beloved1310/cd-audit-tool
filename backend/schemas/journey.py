"""User-defined journey audit — per-step friction and dark-pattern signals."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from backend.schemas.audit import DarkPattern


class JourneyStepInput(BaseModel):
    """One step in a path defined by the user (e.g. homepage → product → checkout)."""

    label: str = Field(
        default="",
        description="Optional human label, e.g. Checkout",
        max_length=120,
    )
    url: str = Field(description="Absolute http(s) URL for this step.")


class JourneyStepResult(BaseModel):
    """Analysis for one journey step after fetch + LLM."""

    step_index: int = Field(ge=0)
    label: str
    url: str
    page_title: str = ""
    word_count: int = 0
    fetch_error: str | None = None
    friction_flags: list[str] = Field(
        default_factory=list,
        description="Machine-oriented slugs, e.g. unclear_pricing, excessive_choice_complexity",
    )
    friction_evidence_quotes: list[str] = Field(
        default_factory=list,
        description="Short verbatim quotes supporting friction signals.",
    )
    dark_patterns: list[DarkPattern] = Field(default_factory=list)
    step_summary: str = ""


class JourneyStepLLMOutput(BaseModel):
    """Structured LLM output for a single journey step (merged into JourneyStepResult)."""

    friction_flag_slugs: list[str] = Field(default_factory=list)
    friction_evidence_quotes: list[str] = Field(default_factory=list)
    dark_patterns: list[DarkPattern] = Field(default_factory=list)
    step_summary: str = ""


class JourneyReport(BaseModel):
    """Full journey audit: ordered steps with per-step friction and dark-pattern evidence."""

    generated_at: datetime
    steps: list[JourneyStepResult] = Field(default_factory=list)
