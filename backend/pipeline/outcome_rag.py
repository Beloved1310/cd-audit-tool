"""FCA retrieval and post-LLM grounding helpers for outcome nodes."""

from __future__ import annotations

from typing import Any

from backend.config import get_settings
from backend.crawler.site_crawler import CrawlResult
from backend.pipeline.citation_grounding import apply_outcome_citation_grounding
from backend.pipeline.outcome_queries import OUTCOME_QUERIES, criterion_queries_for_outcome
from backend.pipeline.rag_context import FcaPromptContext, build_fca_prompt_context
from backend.pipeline.scorer import (
    CriterionDef,
    confidence_level,
    confidence_note,
    normalize_outcome_criteria,
)
from backend.schemas.audit import ConfidenceLevel, OutcomeScore


def retrieve_fca_for_outcome(retriever: Any, outcome_name: str) -> FcaPromptContext:
    """Retrieve FCA chunks — per-criterion queries when enabled, else one outcome query."""
    settings = get_settings()
    if settings.rag_per_criterion_enabled:
        queries = criterion_queries_for_outcome(outcome_name)
        return build_fca_prompt_context(
            retriever,
            *queries,
            k_per_query=settings.rag_per_criterion_k,
            max_chunks=settings.rag_per_criterion_max_chunks,
        )
    query = OUTCOME_QUERIES.get(outcome_name)
    if not query:
        raise ValueError(f"No FCA retrieval query for outcome: {outcome_name!r}")
    return build_fca_prompt_context(retriever, query)


def finalize_outcome_score(
    result: OutcomeScore,
    *,
    outcome_name: str,
    criteria_defs: tuple[CriterionDef, ...],
    fca: FcaPromptContext,
    crawl: CrawlResult,
    scope_note: str,
) -> OutcomeScore:
    """Normalize criteria, ground finding citations, and set crawl confidence."""
    result = result.model_copy(
        update={
            "criteria_scores": normalize_outcome_criteria(result.criteria_scores, criteria_defs),
        },
    )
    result, grounding_note = apply_outcome_citation_grounding(result, fca.allowed_citations)

    conf = confidence_level(len(crawl.pages), crawl.total_words)
    if result.confidence == ConfidenceLevel.LOW and conf != ConfidenceLevel.LOW:
        conf = result.confidence
    elif grounding_note and conf == ConfidenceLevel.HIGH:
        conf = ConfidenceLevel.MEDIUM

    note_parts = [confidence_note(len(crawl.pages), crawl.total_words)]
    if grounding_note:
        note_parts.append(grounding_note)
    if fca.chunk_count == 0:
        note_parts.append("No FCA chunks retrieved for this outcome.")
        conf = ConfidenceLevel.LOW

    score = sum(c.awarded_points for c in result.criteria_scores)
    return result.model_copy(
        update={
            "outcome_name": outcome_name,
            "score": score,
            "confidence": conf,
            "confidence_note": " ".join(note_parts),
            "assessment_scope": "public_website_only",
            "scope_note": scope_note,
        },
    )
