"""Price & Value outcome (PRIN 2A.3) — structured LLM + FCA RAG (Groq)."""

from __future__ import annotations

import json
import logging

from backend.observability import stage_timer
from backend.pipeline.content_builder import build_crawl_markdown
from backend.pipeline.rag_context import build_fca_prompt_context
from backend.pipeline.llm_errors import friendly_eval_error
from backend.pipeline.groq_llm import chat_groq, invoke_groq
from backend.pipeline.prompt_loader import load_prompt_text
from backend.pipeline.scorer import (
    PRICE_VALUE_CRITERIA,
    confidence_level,
    confidence_note,
    format_criteria_for_prompt,
    normalize_outcome_criteria,
)
from backend.pipeline.state import AuditState
from backend.security.prompt_injection import sanitise_website_content
from backend.schemas.audit import ConfidenceLevel, OutcomeScore, RAGRating
from backend.schemas.llm_io import OutcomeGroqOutput, outcome_from_groq_output

logger = logging.getLogger(__name__)

_QUERY = (
    "PRIN 2A.3 price value fair value fees charges costs "
    "APR interest total cost comparison introductory rate sludge transparency"
)
_RULEBOOK_QUERY = (
    "FG22/5 PS22/9 price value fair value fees charges policy statement "
    "rules framework"
)
_OUTCOME_NAME = "Price & Value"
_SCOPE_NOTE = (
    "Public-website evidence only: a full Price & Value assessment typically requires "
    "internal firm data (e.g. pricing methodology, distribution strategy, and value benchmarks)."
)


def _failed_outcome(exc: Exception) -> OutcomeScore:
    return OutcomeScore(
        outcome_name=_OUTCOME_NAME,
        rating=RAGRating.RED,
        score=0,
        confidence=ConfidenceLevel.LOW,
        confidence_note="Scoring did not complete for this outcome.",
        summary=friendly_eval_error(exc),
        criteria_scores=[],
    )


def price_value_node(state: AuditState) -> dict:
    cr = state["crawl_result"]
    retriever = state["retriever"]
    assert cr is not None

    with stage_timer("price_value_prepare"):
        website_content = sanitise_website_content(build_crawl_markdown(cr, max_chars=10_000))
    with stage_timer("price_value_retrieve"):
        fca = build_fca_prompt_context(retriever, _QUERY, _RULEBOOK_QUERY)

    template = load_prompt_text("price_value.txt")
    output_schema = json.dumps(
        OutcomeGroqOutput.model_json_schema(),
        separators=(",", ":"),
    )
    formatted_prompt = template.format(
        fca_sources=fca.fca_sources,
        fca_context=fca.fca_context,
        scoring_criteria=format_criteria_for_prompt(PRICE_VALUE_CRITERIA),
        website_content=website_content,
        output_schema=output_schema,
    )

    llm = chat_groq()
    structured = llm.with_structured_output(OutcomeGroqOutput)
    try:
        with stage_timer("price_value_llm"):
            raw = invoke_groq(structured, formatted_prompt)
        if not isinstance(raw, OutcomeGroqOutput):
            raw = OutcomeGroqOutput.model_validate(raw)
        result = outcome_from_groq_output(raw)
        result = result.model_copy(
            update={
                "criteria_scores": normalize_outcome_criteria(
                    result.criteria_scores,
                    PRICE_VALUE_CRITERIA,
                ),
            },
        )
    except Exception as e:  # noqa: BLE001
        logger.exception("Price & Value structured output failed")
        result = _failed_outcome(e)
    else:
        conf = confidence_level(len(cr.pages), cr.total_words)
        note = confidence_note(len(cr.pages), cr.total_words)
        score = sum(c.awarded_points for c in result.criteria_scores)
        result = result.model_copy(
            update={
                "outcome_name": _OUTCOME_NAME,
                "score": score,
                "confidence": conf,
                "confidence_note": note,
                "assessment_scope": "public_website_only",
                "scope_note": _SCOPE_NOTE,
            },
        )

    return {"price_value_score": result}
